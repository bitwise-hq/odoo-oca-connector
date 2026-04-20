from odoo import SUPERUSER_ID

from odoo.addons.component.core import AbstractComponent


class BaseConnectorOutboundListener(AbstractComponent):
    """Shared helpers for outbound connector event listeners."""

    _name = "base.connector.outbound.listener"
    _inherit = "base.connector.listener"

    def _root_env(self):
        return self.env(user=SUPERUSER_ID)

    def _get_collection_recordset(self):
        collection_model_name = getattr(self, "_collection", None)
        if not collection_model_name:
            raise NotImplementedError
        return self._root_env()[collection_model_name]

    def _backend_is_outbound_enabled(self, backend):
        del backend
        return True

    def _get_existing_component_backends(self, record):
        del record
        raise NotImplementedError

    def _should_include_bootstrap_backends(self, record):
        del record
        return False

    def _get_bootstrap_backends(self, record):
        del record
        return self._get_collection_recordset().browse()

    def _get_component_backends(self, record):
        existing_backends = self._get_existing_component_backends(record)
        if not self._should_include_bootstrap_backends(record):
            return existing_backends.filtered(self._backend_is_outbound_enabled)
        return (existing_backends | self._get_bootstrap_backends(record)).filtered(
            self._backend_is_outbound_enabled
        )

    def _components_by_name_for_record(self, record, component_name):
        for backend in self._get_component_backends(record):
            with backend.work_on(record._name) as work:
                yield work.component_by_name(component_name)
