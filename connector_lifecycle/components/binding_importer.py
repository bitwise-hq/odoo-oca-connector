from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError

from odoo.addons.component.core import AbstractComponent


class BaseConnectorBindingImporter(AbstractComponent):
    """Shared import lifecycle for connector bindings backed by Odoo records."""

    _name = "base.connector.binding.importer"
    _inherit = ["base.importer", "base.connector"]
    _usage = "record.importer"

    def run(self, external_record):
        external_record = self._normalize_external_record(external_record)
        external_id = self._get_external_id(external_record)
        if not external_id:
            raise ValidationError(self._missing_external_id_message())

        binding = self._find_binding_for_external_id(external_id)
        record = self._resolve_target_record(external_record, binding=binding)
        mapped_values = self._prepare_mapped_values(
            external_record, record, binding=binding
        )
        binding = self._ensure_binding(record, mapped_values, binding=binding)
        self._validate_binding_assignment(binding, external_id, record)
        self._write_binding_values(binding, mapped_values)
        self.binder.bind(external_id, binding)
        self._after_import(binding, external_record)
        return binding

    def _normalize_external_record(self, external_record):
        return external_record or {}

    def _get_inbound_metadata_value(self, external_record, key):
        external_record = external_record or {}
        return external_record.get(f"_inbound_{key}") or False

    def _get_inbound_routing_key(self, external_record):
        return self._get_inbound_metadata_value(external_record, "routing_key")

    def _get_inbound_dedupe_key(self, external_record):
        return self._get_inbound_metadata_value(external_record, "dedupe_key")

    def _get_inbound_source_reference(self, external_record):
        return self._get_inbound_metadata_value(external_record, "source_reference")

    def _get_inbound_occurred_at(self, external_record):
        return self._get_inbound_metadata_value(external_record, "occurred_at")

    def _get_external_resource_label(self):
        return self.env._("External record")

    def _get_local_resource_label(self):
        return self.env._("Odoo record")

    def _missing_external_id_message(self):
        return self.env._(
            "The %s is missing an id.",
            self._get_external_resource_label(),
        )

    def _get_external_id(self, external_record):
        return external_record.get("id")

    def _find_binding_for_external_id(self, external_id):
        return self.binder.to_internal(external_id)

    def _find_binding_for_record(self, record):
        record.ensure_one()
        return self.model.with_context(active_test=False).search(
            [
                ("backend_id", "=", self.backend_record.id),
                ("odoo_id", "=", record.id),
            ],
            limit=1,
        )

    def _find_backend_binding(self, model_name, external_id, *, limit=2):
        if not external_id:
            return self.env[model_name]
        return (
            self.env[model_name]
            .with_context(active_test=False)
            .search(
                [
                    ("backend_id", "=", self.backend_record.id),
                    ("external_id", "=", external_id),
                ],
                limit=limit,
            )
        )

    def _import_dependency_binding(
        self,
        model_name,
        *,
        external_record=None,
        external_id=None,
        loader=None,
        empty_if_missing=False,
    ):
        with self.backend_record.work_on(model_name) as work:
            importer = work.component(usage="record.importer")
            dependency_record = external_record
            if dependency_record is None:
                adapter = work.component(usage="backend.adapter")
                if loader is None:
                    dependency_record = adapter.read(external_id)
                else:
                    dependency_record = loader(adapter)
            if dependency_record in (None, False):
                return self.env[model_name] if empty_if_missing else dependency_record
            return importer.run(dependency_record)

    def _resolve_target_record(self, external_record, *, binding=None):
        raise NotImplementedError

    def _prepare_mapped_values(self, external_record, record, *, binding=None):
        return {}

    def _prepare_binding_create_values(self, record, mapped_values):
        binding_values = {
            "backend_id": self.backend_record.id,
            "odoo_id": record.id,
        }
        binding_values.update(mapped_values)
        return binding_values

    def _ensure_binding(self, record, mapped_values, *, binding=None):
        if binding:
            return binding

        binding = self._find_binding_for_record(record)
        if binding:
            return binding

        try:
            with self.env.cr.savepoint():
                return self.model.with_context(connector_no_export=True).create(
                    self._prepare_binding_create_values(record, mapped_values)
                )
        except IntegrityError:
            binding = self._find_binding_for_record(record)
            if not binding:
                raise
            return binding

    def _validate_binding_assignment(self, binding, external_id, record):
        binding.ensure_one()
        record.ensure_one()
        if binding.odoo_id != record:
            raise ValidationError(
                self.env._(
                    (
                        "The %(external_resource)s %(external_id)s is already "
                        "bound to %(current)s and cannot be rebound to "
                        "%(target)s."
                    ),
                    external_resource=self._get_external_resource_label(),
                    external_id=external_id,
                    current=binding.odoo_id.display_name,
                    target=record.display_name,
                )
            )

        binding_external_id = binding.external_id or False
        if binding_external_id and binding_external_id != external_id:
            raise ValidationError(
                self.env._(
                    (
                        "The %(local_resource)s %(record)s is already bound "
                        "to %(current)s and cannot be rebound to %(target)s."
                    ),
                    local_resource=self._get_local_resource_label(),
                    record=binding.odoo_id.display_name,
                    current=binding_external_id,
                    target=external_id,
                )
            )

    def _write_binding_values(self, binding, mapped_values):
        if mapped_values:
            binding.with_context(connector_no_export=True).write(mapped_values)

    def _after_import(self, binding, external_record):
        return binding
