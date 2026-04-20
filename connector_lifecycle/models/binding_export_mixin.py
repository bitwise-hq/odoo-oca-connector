from odoo import fields as odoo_fields
from odoo import models


class ConnectorBindingExportMixin(models.AbstractModel):
    """Shared model wrapper for component-driven binding exports."""

    _name = "connector.binding.export.mixin"
    _description = "Connector Binding Export Mixin"

    def _get_export_component_usage(self):
        return "record.exporter"

    def _get_record_exporter_usage(self):
        return self._get_export_component_usage()

    def _get_export_sync_field(self):
        return "sync_date"

    def _get_export_sync_date_field(self):
        return self._get_export_sync_field()

    def _get_export_error_field(self):
        return "last_sync_error"

    def export_record(self, fields=None):
        self.ensure_one()
        try:
            with self.backend_id.work_on(self._name) as work:
                exporter = work.component(usage=self._get_export_component_usage())
                result = exporter.run(self, fields=fields)

            write_values = {}
            sync_date_field = self._get_export_sync_field()
            if sync_date_field and sync_date_field in self._fields:
                write_values[sync_date_field] = odoo_fields.Datetime.now()

            error_field = self._get_export_error_field()
            if error_field and error_field in self._fields:
                write_values[error_field] = False

            if write_values:
                self.with_context(connector_no_export=True).write(write_values)
            return result
        except Exception as err:
            error_field = self._get_export_error_field()
            if error_field and error_field in self._fields:
                self.with_context(connector_no_export=True).write(
                    {
                        error_field: str(err),
                    }
                )
            raise
