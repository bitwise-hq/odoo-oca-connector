from odoo.addons.component.core import AbstractComponent


class BaseConnectorInboundListener(AbstractComponent):
    """Shared helpers for inbound connector event scheduling."""

    _name = "base.connector.inbound.listener"
    _inherit = "base.connector"

    def __init__(self, work_context):
        super().__init__(work_context)
        self._scheduler = None

    @property
    def scheduler(self):
        if self._scheduler is None:
            self._scheduler = self.component_by_name(
                "base.connector.binding.import.scheduler"
            )
        return self._scheduler

    def schedule_event(
        self,
        event,
        *,
        dispatch_component_name="base.connector.binding.import.dispatcher",
        dispatch_model_name=None,
    ):
        event.ensure_one()
        dispatch_model_name = dispatch_model_name or self.work.model_name
        dispatcher = self.component_by_name(
            dispatch_component_name, model_name=dispatch_model_name
        )
        dispatch_kwargs = dispatcher.prepare_event_dispatch(event)
        if not dispatch_kwargs:
            return True

        self.scheduler.schedule(
            dispatch_component_name=dispatch_component_name,
            dispatch_model_name=dispatch_model_name,
            source_model_name=event._name,
            source_res_id=event.id,
            **dispatch_kwargs,
        )
        return False

    def schedule_inbound(
        self,
        *,
        payload,
        routing_key=None,
        binding_model_name=None,
        metadata=None,
        dispatch_component_name="base.connector.binding.import.dispatcher",
        dispatch_model_name=None,
        source_model_name=None,
        source_res_id=None,
    ):
        self.scheduler.schedule(
            payload=payload,
            routing_key=routing_key,
            binding_model_name=binding_model_name,
            metadata=metadata,
            dispatch_component_name=dispatch_component_name,
            dispatch_model_name=dispatch_model_name or self.work.model_name,
            source_model_name=source_model_name,
            source_res_id=source_res_id,
        )
        return True
