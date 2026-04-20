from unittest import mock

from odoo.tests.common import BaseCase, tagged

from odoo.addons.connector_lifecycle.components.inbound_listener import (
    BaseConnectorInboundListener,
)


@tagged("standard", "at_install")
class TestConnectorInboundListener(BaseCase):
    def test_schedule_event_queues_import_job_and_returns_false(self):
        listener = BaseConnectorInboundListener.__new__(BaseConnectorInboundListener)
        scheduler = mock.Mock(name="scheduler")
        dispatcher = mock.Mock(name="dispatcher")
        event = mock.Mock(name="event")
        event._name = "paddle.webhook.event"
        event.id = 17

        listener.work = mock.Mock(name="work")
        listener.work.model_name = "paddle.webhook.event"
        listener._scheduler = scheduler
        listener.component_by_name = mock.Mock(return_value=dispatcher)
        dispatcher.prepare_event_dispatch.return_value = {
            "payload": {"id": "ext_1"},
            "routing_key": "customer.updated",
            "binding_model_name": "paddle.res.partner.customer",
            "metadata": {"source": "webhook"},
        }

        result = BaseConnectorInboundListener.schedule_event(
            listener,
            event,
            dispatch_component_name="paddle.binding.import.dispatcher",
        )

        self.assertFalse(result)
        listener.component_by_name.assert_called_once_with(
            "paddle.binding.import.dispatcher",
            model_name="paddle.webhook.event",
        )
        scheduler.schedule.assert_called_once_with(
            payload={"id": "ext_1"},
            routing_key="customer.updated",
            binding_model_name="paddle.res.partner.customer",
            metadata={"source": "webhook"},
            dispatch_component_name="paddle.binding.import.dispatcher",
            dispatch_model_name="paddle.webhook.event",
            source_model_name="paddle.webhook.event",
            source_res_id=17,
        )

    def test_schedule_event_returns_true_when_dispatcher_has_no_work(self):
        listener = BaseConnectorInboundListener.__new__(BaseConnectorInboundListener)
        scheduler = mock.Mock(name="scheduler")
        dispatcher = mock.Mock(name="dispatcher")
        event = mock.Mock(name="event")

        listener.work = mock.Mock(name="work")
        listener.work.model_name = "paddle.webhook.event"
        listener._scheduler = scheduler
        listener.component_by_name = mock.Mock(return_value=dispatcher)
        dispatcher.prepare_event_dispatch.return_value = False

        result = BaseConnectorInboundListener.schedule_event(listener, event)

        self.assertTrue(result)
        scheduler.schedule.assert_not_called()

    def test_schedule_inbound_delegates_to_scheduler(self):
        listener = BaseConnectorInboundListener.__new__(BaseConnectorInboundListener)
        scheduler = mock.Mock(name="scheduler")

        listener.work = mock.Mock(name="work")
        listener.work.model_name = "webhook.event"
        listener._scheduler = scheduler

        result = BaseConnectorInboundListener.schedule_inbound(
            listener,
            payload={"id": "ext_2"},
            routing_key="customer.updated",
            metadata={"source": "manual"},
        )

        self.assertTrue(result)
        scheduler.schedule.assert_called_once_with(
            payload={"id": "ext_2"},
            routing_key="customer.updated",
            binding_model_name=None,
            metadata={"source": "manual"},
            dispatch_component_name="base.connector.binding.import.dispatcher",
            dispatch_model_name="webhook.event",
            source_model_name=None,
            source_res_id=None,
        )
