from psycopg2 import IntegrityError

from odoo.addons.component.core import AbstractComponent


class BaseConnectorBindingExportDispatcher(AbstractComponent):
    """Shared helpers for field-driven binding export dispatch."""

    _name = "base.connector.binding.export.dispatcher"
    _inherit = "base.connector"

    _binding_change_fields = frozenset()

    def __init__(self, work_context):
        super().__init__(work_context)
        self._scheduler = None

    @property
    def scheduler(self):
        if self._scheduler is None:
            self._scheduler = self.component_by_name(
                "base.connector.binding.export.scheduler"
            )
        return self._scheduler

    def _create_binding(self, binding_model, values, domain):
        try:
            with self.env.cr.savepoint():
                return binding_model.with_context(connector_no_export=True).create(
                    values
                )
        except IntegrityError:
            return binding_model.search(domain, limit=1)

    def _normalize_changed_fields(self, changed_fields):
        return set(changed_fields or [])

    def _should_schedule_bindings(self, changed_fields, *, watched_fields=None):
        changed_fields = self._normalize_changed_fields(changed_fields)
        watched_fields = set(
            watched_fields
            if watched_fields is not None
            else self._binding_change_fields or ()
        )
        return (
            not changed_fields
            or not watched_fields
            or bool(changed_fields & watched_fields)
        )

    def _schedule_bindings(self, bindings):
        if bindings:
            self.scheduler.schedule_bindings(bindings)
        return bindings

    def ensure_bindings(self, record):
        raise NotImplementedError

    def _dispatch_with_bindings(self, record, changed_fields, *, watched_fields=None):
        record.ensure_one()
        bindings = self.ensure_bindings(record)
        if bindings and self._should_schedule_bindings(
            changed_fields, watched_fields=watched_fields
        ):
            self._schedule_bindings(bindings)
        return bindings
