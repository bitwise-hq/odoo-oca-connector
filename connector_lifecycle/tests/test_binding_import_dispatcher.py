from unittest import mock

from odoo.tests.common import BaseCase, tagged

from odoo.addons.connector_lifecycle.components.binding_import_dispatcher import (
    BaseConnectorBindingImportDispatcher,
)


@tagged("standard", "at_install")
class TestConnectorBindingImportDispatcher(BaseCase):
    def test_get_binding_model_mapping_accumulates_inbound_layers(self):
        class ParentDispatcher:
            _inbound_binding_model_mapping = {"customer": "res.partner"}

        class ChildDispatcher(ParentDispatcher):
            _inbound_binding_model_mapping = {"subscription": "sale.order"}

        class GrandchildDispatcher(ChildDispatcher):
            _inbound_binding_model_mapping = {"price": "product.pricelist.item"}

        dispatcher = GrandchildDispatcher()

        self.assertEqual(
            BaseConnectorBindingImportDispatcher._get_binding_model_mapping(dispatcher),
            {
                "customer": "res.partner",
                "subscription": "sale.order",
                "price": "product.pricelist.item",
            },
        )

    def test_enrich_inbound_payload_adds_canonical_metadata_aliases(self):
        dispatcher = BaseConnectorBindingImportDispatcher.__new__(
            BaseConnectorBindingImportDispatcher
        )

        payload = BaseConnectorBindingImportDispatcher._enrich_inbound_payload(
            dispatcher,
            {"id": "ext_1"},
            routing_key="customer.updated",
            metadata={
                "source": "webhook",
                "dedupe_key": "ntf_1",
                "source_reference": "evt_1",
                "occurred_at": "2026-04-19T10:00:00Z",
            },
        )

        self.assertEqual(payload["_inbound_source"], "webhook")
        self.assertEqual(payload["_inbound_routing_key"], "customer.updated")
        self.assertEqual(payload["_inbound_dedupe_key"], "ntf_1")
        self.assertEqual(payload["_inbound_source_reference"], "evt_1")
        self.assertEqual(payload["_inbound_occurred_at"], "2026-04-19T10:00:00Z")

    def test_dispatch_inbound_runs_importer_for_resolved_binding_model(self):
        dispatcher = mock.MagicMock(name="dispatcher")
        work = dispatcher.collection.work_on.return_value.__enter__.return_value
        importer = mock.Mock(name="importer")

        dispatcher._normalize_inbound_metadata.return_value = {
            "source": "manual",
            "routing_key": "customer",
            "dedupe_key": "manual:1",
            "source_reference": "manual",
            "occurred_at": False,
        }
        dispatcher._enrich_inbound_payload.return_value = {
            "id": "ext_1",
            "_inbound_source": "manual",
            "_inbound_routing_key": "customer",
        }
        dispatcher._get_binding_model_name.return_value = "res.partner"
        work.component.return_value = importer

        result = BaseConnectorBindingImportDispatcher.dispatch_inbound(
            dispatcher,
            payload={"id": "ext_1"},
            routing_key="customer",
            metadata={"source": "manual"},
        )

        self.assertTrue(result)
        dispatcher._normalize_inbound_metadata.assert_called_once_with(
            {"source": "manual"}
        )
        dispatcher._enrich_inbound_payload.assert_called_once_with(
            {"id": "ext_1"},
            routing_key="customer",
            metadata={
                "source": "manual",
                "routing_key": "customer",
                "dedupe_key": "manual:1",
                "source_reference": "manual",
                "occurred_at": False,
            },
        )
        dispatcher._get_binding_model_name.assert_called_once_with(
            "customer",
            payload={
                "id": "ext_1",
                "_inbound_source": "manual",
                "_inbound_routing_key": "customer",
            },
            metadata={
                "source": "manual",
                "routing_key": "customer",
                "dedupe_key": "manual:1",
                "source_reference": "manual",
                "occurred_at": False,
            },
        )
        dispatcher.collection.work_on.assert_called_once_with("res.partner")
        work.component.assert_called_once_with(usage="record.importer")
        importer.run.assert_called_once_with(
            {
                "id": "ext_1",
                "_inbound_source": "manual",
                "_inbound_routing_key": "customer",
            }
        )
