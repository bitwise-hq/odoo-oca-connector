from odoo import SUPERUSER_ID

from odoo.addons.component.core import Component


class ConnectorBindingExportScheduler(Component):
    """Queue stable export jobs for connector binding records."""

    _name = "base.connector.binding.export.scheduler"
    _inherit = "base.connector"

    def _get_job_description(self, binding):
        binding.ensure_one()
        return self.env._("Export connector binding %s", binding.display_name)

    def _get_identity_key(self, binding):
        binding.ensure_one()
        return f"connector_binding_export:{binding._name}:{binding.id}"

    def _get_schedule_parameter(self, method_name):
        method = getattr(self, method_name, None)
        if callable(method):
            return method
        return getattr(ConnectorBindingExportScheduler, method_name).__get__(
            self, type(self)
        )

    def schedule(self, binding):
        binding.ensure_one()
        description_getter = ConnectorBindingExportScheduler._get_schedule_parameter(
            self, "_get_job_description"
        )
        identity_key_getter = ConnectorBindingExportScheduler._get_schedule_parameter(
            self, "_get_identity_key"
        )
        binding.with_user(SUPERUSER_ID).with_delay(
            description=description_getter(binding),
            identity_key=identity_key_getter(binding),
        ).export_record()
        return True

    def schedule_bindings(self, bindings):
        for binding in bindings:
            self.schedule(binding)
        return True
