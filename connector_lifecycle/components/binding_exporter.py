import logging
from contextlib import contextmanager

import psycopg2

import odoo

from odoo.addons.component.core import AbstractComponent
from odoo.addons.connector.exception import IDMissingInBackend, RetryableJobError

_logger = logging.getLogger(__name__)


class BaseConnectorBindingExporter(AbstractComponent):
    """Shared export lifecycle for connector bindings."""

    _name = "base.connector.binding.exporter"
    _inherit = ["base.exporter", "base.connector"]
    _usage = "record.exporter"
    _default_binding_field = None

    def __init__(self, work_context):
        super().__init__(work_context)
        self.binding = None
        self.external_id = None
        self.export_result = None

    def _should_import(self):
        return False

    def _delay_import(self):
        assert self.external_id
        self.binding.with_delay().import_record(
            self.backend_record,
            self.external_id,
            force=True,
        )

    def run(self, binding, *args, **kwargs):
        self.binding = binding
        self.export_result = None
        self.external_id = self.binder.to_external(self.binding)

        try:
            should_import = self._should_import()
        except IDMissingInBackend:
            self.external_id = None
            should_import = False
        if should_import:
            self._delay_import()

        result = self._run(*args, **kwargs)

        if self.external_id or self.external_id == 0:
            self.binder.bind(self.external_id, self.binding)
        if not odoo.tools.config["test_enable"]:
            self.env.cr.commit()  # pylint: disable=E8102

        self._after_export()
        return result

    def _run(self, fields=None):
        assert self.binding

        if not self.external_id:
            fields = None

        if self._has_to_skip():
            return

        self._export_dependencies()
        self._lock()

        map_record = self._map_data()

        if self.external_id:
            record = self._update_data(map_record, fields=fields)
            if not record:
                return self.env._("Nothing to export.")
            try:
                self._update(record)
            except IDMissingInBackend:
                self.external_id = None
                record = self._create_data(map_record, fields=None)
                if not record:
                    return self.env._("Nothing to export.")
                self.external_id = self._create(record)
        else:
            record = self._create_data(map_record, fields=fields)
            if not record:
                return self.env._("Nothing to export.")
            self.external_id = self._create(record)
        return self.env._("Record exported with ID %s on Backend.", self.external_id)

    def _after_export(self):
        return self.export_result

    def _lock(self):
        sql = f"SELECT id FROM {self.model._table} WHERE id = %s FOR UPDATE NOWAIT"
        try:
            self.env.cr.execute(sql, (self.binding.id,), log_exceptions=False)
        except psycopg2.OperationalError as err:
            _logger.info(
                (
                    "A concurrent job is already exporting the same record "
                    "(%s with id %s). Job delayed later."
                ),
                self.model._name,
                self.binding.id,
            )
            raise RetryableJobError(
                "A concurrent job is already exporting the same record "
                f"({self.model._name} with id {self.binding.id}). "
                "The job will be retried later."
            ) from err

    def _has_to_skip(self):
        return False

    @contextmanager
    def _retry_unique_violation(self):
        try:
            yield
        except psycopg2.IntegrityError as err:
            if err.pgcode == psycopg2.errorcodes.UNIQUE_VIOLATION:
                raise RetryableJobError(
                    "A database error caused the failure of the job:\n"
                    f"{err}\n\n"
                    "Likely due to 2 concurrent jobs wanting to create "
                    "the same record. The job will be retried later."
                ) from err
            raise

    def _export_dependency(
        self,
        relation,
        binding_model,
        component_usage="record.exporter",
        binding_field=None,
        binding_extra_vals=None,
    ):
        if binding_field is None:
            binding_field = self._default_binding_field
        if not relation:
            return

        rel_binder = self.binder_for(binding_model)
        wrap = relation._name != binding_model

        if wrap:
            domain = [
                ("odoo_id", "=", relation.id),
                ("backend_id", "=", self.backend_record.id),
            ]
            binding = self.env[binding_model].search(domain)
            if binding:
                assert len(binding) == 1, (
                    "only 1 binding for a backend is supported in _export_dependency"
                )
            else:
                bind_values = {
                    "backend_id": self.backend_record.id,
                    "odoo_id": relation.id,
                }
                if binding_extra_vals:
                    bind_values.update(binding_extra_vals)
                with self._retry_unique_violation():
                    binding = (
                        self.env[binding_model]
                        .with_context(connector_no_export=True)
                        .sudo()
                        .create(bind_values)
                    )
                    if not odoo.tools.config["test_enable"]:
                        self.env.cr.commit()  # pylint: disable=E8102
        else:
            binding = relation

        if not rel_binder.to_external(binding):
            exporter = self.component(usage=component_usage, model_name=binding_model)
            exporter.run(binding)

    def _export_dependencies(self):
        return None

    def _map_data(self):
        return self.mapper.map_record(self.binding)

    def _validate_create_data(self, data):
        return data

    def _validate_update_data(self, data):
        return data

    def _create_data(self, map_record, fields=None, **kwargs):
        return map_record.values(for_create=True, fields=fields, **kwargs)

    def _set_export_result(self, export_result):
        self.export_result = export_result
        return export_result

    def _get_exported_external_id(self, export_result, *, fallback=None):
        if isinstance(export_result, dict):
            external_id = export_result.get("id")
            if external_id or external_id == 0:
                return external_id
            return fallback
        return export_result if export_result or export_result == 0 else fallback

    def _create(self, data):
        self._validate_create_data(data)
        export_result = self.backend_adapter.create(data)
        self._set_export_result(export_result)
        fallback = None if isinstance(export_result, dict) else export_result
        return self._get_exported_external_id(export_result, fallback=fallback)

    def _update_data(self, map_record, fields=None, **kwargs):
        return map_record.values(fields=fields, **kwargs)

    def _update(self, data):
        assert self.external_id
        self._validate_update_data(data)
        self._set_export_result(self.backend_adapter.write(self.external_id, data))
