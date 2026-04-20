from unittest import mock

from odoo.tests.common import BaseCase, tagged

from odoo.addons.connector_lifecycle.components.import_scheduler import (
    ConnectorBindingImportScheduler,
)
from odoo.addons.connector_lifecycle.models.binding_import_mixin import (
    ConnectorBindingImportMixin,
)


class _StubImportScheduler:
    pass


@tagged("standard", "at_install")
class TestConnectorImportScheduler(BaseCase):
    def test_scheduler_enqueues_scheduled_inbound_dispatch(self):
        scheduler = _StubImportScheduler()
        collection = mock.Mock(name="collection")
        delay_collection = mock.Mock(name="delay_collection")

        scheduler.collection = collection
        scheduler.work = mock.Mock(name="work")
        scheduler.work.model_name = "webhook.event"
        scheduler.env = mock.Mock(name="env")
        scheduler.env._ = lambda message, *args: message % args if args else message
        collection.with_user.return_value = collection
        collection.with_delay.return_value = delay_collection

        for method_name in (
            "_normalize_metadata",
            "_get_job_description",
            "_get_identity_key",
            "_get_schedule_parameter",
        ):
            setattr(
                scheduler,
                method_name,
                getattr(ConnectorBindingImportScheduler, method_name).__get__(
                    scheduler,
                    _StubImportScheduler,
                ),
            )

        ConnectorBindingImportScheduler.schedule(
            scheduler,
            payload={"id": "ext_1"},
            routing_key="customer.updated",
            binding_model_name="res.partner",
            metadata={"source": "manual", "dedupe_key": "manual:1"},
            dispatch_component_name="base.connector.binding.import.dispatcher",
            dispatch_model_name="webhook.event",
            source_model_name="webhook.event",
            source_res_id=12,
        )

        collection.ensure_one.assert_called_once_with()
        collection.with_user.assert_called_once()
        collection.with_delay.assert_called_once()
        delay_collection._run_import_dispatch.assert_called_once_with(
            payload={"id": "ext_1"},
            routing_key="customer.updated",
            binding_model_name="res.partner",
            metadata={
                "source": "manual",
                "routing_key": False,
                "dedupe_key": "manual:1",
                "source_reference": False,
                "occurred_at": False,
            },
            dispatch_component_name="base.connector.binding.import.dispatcher",
            dispatch_model_name="webhook.event",
            source_model_name="webhook.event",
            source_res_id=12,
        )

    def test_scheduled_dispatch_marks_source_done_on_success(self):
        class _StubCollection:
            pass

        collection = _StubCollection()
        source_model = mock.Mock(name="source_model")
        source = mock.MagicMock(name="source")
        dispatcher = mock.Mock(name="dispatcher")
        work = mock.Mock(name="work")

        collection.ensure_one = mock.Mock()
        collection.env = mock.MagicMock(name="env")
        collection.env.registry.get.return_value = True
        collection.env.__getitem__.return_value = source_model
        collection.work_on = mock.MagicMock()
        collection.work_on.return_value.__enter__.return_value = work

        source_model.with_context.return_value = source_model
        source_model.browse.return_value.exists.return_value = source
        source.__getitem__.side_effect = lambda item: source
        source._fields = {
            "state": object(),
            "processing_error": object(),
            "processed_at": object(),
        }
        source.with_context.return_value = source
        work.component_by_name.return_value = dispatcher
        dispatcher.dispatch_inbound.return_value = True

        for method_name in (
            "_get_import_dispatch_component_name",
            "_get_import_dispatch_model_name",
            "_get_import_source",
            "_get_import_state_values",
            "_write_import_state",
        ):
            bound_method = getattr(
                ConnectorBindingImportMixin,
                method_name,
            ).__get__(collection, _StubCollection)
            setattr(
                collection,
                method_name,
                bound_method,
            )

        result = ConnectorBindingImportMixin._run_import_dispatch(
            collection,
            payload={"id": "ext_1"},
            routing_key="customer.updated",
            binding_model_name="res.partner",
            metadata={"source": "manual"},
            dispatch_component_name="base.connector.binding.import.dispatcher",
            dispatch_model_name="webhook.event",
            source_model_name="webhook.event",
            source_res_id=12,
        )

        self.assertTrue(result)
        work.component_by_name.assert_called_once_with(
            "base.connector.binding.import.dispatcher"
        )
        dispatcher.dispatch_inbound.assert_called_once_with(
            payload={"id": "ext_1"},
            routing_key="customer.updated",
            binding_model_name="res.partner",
            metadata={"source": "manual"},
        )
        self.assertEqual(source.write.call_args_list[0].args[0]["state"], "processing")
        self.assertEqual(source.write.call_args_list[1].args[0]["state"], "done")

    def test_scheduled_dispatch_marks_source_error_on_failure(self):
        class _StubCollection:
            pass

        collection = _StubCollection()
        source_model = mock.Mock(name="source_model")
        source = mock.MagicMock(name="source")
        dispatcher = mock.Mock(name="dispatcher")
        work = mock.Mock(name="work")

        collection.ensure_one = mock.Mock()
        collection.env = mock.MagicMock(name="env")
        collection.env.registry.get.return_value = True
        collection.env.__getitem__.return_value = source_model
        collection.work_on = mock.MagicMock()
        collection.work_on.return_value.__enter__.return_value = work

        source_model.with_context.return_value = source_model
        source_model.browse.return_value.exists.return_value = source
        source.__getitem__.side_effect = lambda item: source
        source._fields = {
            "state": object(),
            "processing_error": object(),
            "processed_at": object(),
        }
        source.with_context.return_value = source
        work.component_by_name.return_value = dispatcher
        dispatcher.dispatch_inbound.side_effect = RuntimeError("boom")

        for method_name in (
            "_get_import_dispatch_component_name",
            "_get_import_dispatch_model_name",
            "_get_import_source",
            "_get_import_state_values",
            "_write_import_state",
        ):
            bound_method = getattr(
                ConnectorBindingImportMixin,
                method_name,
            ).__get__(collection, _StubCollection)
            setattr(
                collection,
                method_name,
                bound_method,
            )

        with self.assertRaisesRegex(RuntimeError, "boom"):
            ConnectorBindingImportMixin._run_import_dispatch(
                collection,
                payload={"id": "ext_1"},
                routing_key="customer.updated",
                binding_model_name="res.partner",
                metadata={"source": "manual"},
                dispatch_component_name="base.connector.binding.import.dispatcher",
                dispatch_model_name="webhook.event",
                source_model_name="webhook.event",
                source_res_id=12,
            )

        self.assertEqual(source.write.call_args_list[0].args[0]["state"], "processing")
        self.assertEqual(source.write.call_args_list[1].args[0]["state"], "error")
        self.assertEqual(
            source.write.call_args_list[1].args[0]["processing_error"], "boom"
        )

    def test_import_record_wraps_canonical_import_runner(self):
        collection = mock.Mock(name="collection")
        collection._run_import_dispatch = mock.Mock(return_value=True)

        result = ConnectorBindingImportMixin.import_record(
            collection,
            payload={"id": "ext_1"},
            routing_key="customer.updated",
            binding_model_name="res.partner",
            metadata={"source": "manual"},
            dispatch_component_name="base.connector.binding.import.dispatcher",
            dispatch_model_name="webhook.event",
            source_model_name="webhook.event",
            source_res_id=12,
        )

        self.assertTrue(result)
        collection._run_import_dispatch.assert_called_once_with(
            payload={"id": "ext_1"},
            routing_key="customer.updated",
            binding_model_name="res.partner",
            metadata={"source": "manual"},
            dispatch_component_name="base.connector.binding.import.dispatcher",
            dispatch_model_name="webhook.event",
            source_model_name="webhook.event",
            source_res_id=12,
        )

    def test_legacy_import_helper_names_delegate_to_canonical_names(self):
        collection = mock.Mock(name="collection")
        collection._get_import_dispatch_component_name = mock.Mock(
            return_value="dispatcher"
        )
        collection._get_import_dispatch_model_name = mock.Mock(return_value="model")
        collection._get_import_source = mock.Mock(return_value="source")
        collection._get_import_state_values = mock.Mock(return_value={"state": "done"})
        collection._write_import_state = mock.Mock(return_value="written")
        collection._run_import_dispatch = mock.Mock(return_value=True)

        self.assertEqual(
            ConnectorBindingImportMixin._get_scheduled_inbound_dispatch_component_name(
                collection,
                "custom.dispatcher",
            ),
            "dispatcher",
        )
        self.assertEqual(
            ConnectorBindingImportMixin._get_scheduled_inbound_dispatch_model_name(
                collection,
                "webhook.event",
            ),
            "model",
        )
        self.assertEqual(
            ConnectorBindingImportMixin._get_scheduled_inbound_source(
                collection,
                "webhook.event",
                12,
            ),
            "source",
        )
        self.assertEqual(
            ConnectorBindingImportMixin._get_scheduled_inbound_source_state_values(
                collection,
                "source",
                state="done",
                processing_error=False,
            ),
            {"state": "done"},
        )
        self.assertEqual(
            ConnectorBindingImportMixin._write_scheduled_inbound_source_state(
                collection,
                "source",
                {"state": "done"},
            ),
            "written",
        )
        self.assertTrue(
            ConnectorBindingImportMixin._run_scheduled_inbound_dispatch(
                collection,
                payload={"id": "ext_1"},
                routing_key="customer.updated",
                binding_model_name="res.partner",
                metadata={"source": "manual"},
                dispatch_component_name="base.connector.binding.import.dispatcher",
                dispatch_model_name="webhook.event",
                source_model_name="webhook.event",
                source_res_id=12,
            )
        )

        collection._get_import_dispatch_component_name.assert_called_once_with(
            "custom.dispatcher"
        )
        collection._get_import_dispatch_model_name.assert_called_once_with(
            "webhook.event"
        )
        collection._get_import_source.assert_called_once_with("webhook.event", 12)
        collection._get_import_state_values.assert_called_once_with(
            "source",
            state="done",
            processing_error=False,
        )
        collection._write_import_state.assert_called_once_with(
            "source",
            {"state": "done"},
        )
        collection._run_import_dispatch.assert_called_once_with(
            payload={"id": "ext_1"},
            routing_key="customer.updated",
            binding_model_name="res.partner",
            metadata={"source": "manual"},
            dispatch_component_name="base.connector.binding.import.dispatcher",
            dispatch_model_name="webhook.event",
            source_model_name="webhook.event",
            source_res_id=12,
        )
