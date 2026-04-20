from unittest import mock

from odoo.tests.common import BaseCase, tagged

from odoo.addons.connector_lifecycle.components.binding_export_dispatcher import (
    BaseConnectorBindingExportDispatcher,
)


class _StubExportDispatcher:
    _name = "stub.export.dispatcher"
    _binding_change_fields = {"name"}


@tagged("standard", "at_install")
class TestConnectorBindingExportDispatcher(BaseCase):
    def test_scheduler_property_uses_generic_scheduler_component(self):
        dispatcher = _StubExportDispatcher()
        dispatcher._scheduler = None
        dispatcher.component_by_name = mock.Mock(return_value="scheduler")

        scheduler = BaseConnectorBindingExportDispatcher.scheduler.__get__(
            dispatcher,
            _StubExportDispatcher,
        )

        self.assertEqual(scheduler, "scheduler")
        dispatcher.component_by_name.assert_called_once_with(
            "base.connector.binding.export.scheduler"
        )

    def test_dispatch_with_bindings_uses_dispatcher_ensure_bindings(self):
        dispatcher = _StubExportDispatcher()
        record = mock.Mock(name="record")
        bindings = mock.Mock(name="bindings")
        dispatcher.ensure_bindings = mock.Mock(return_value=bindings)
        dispatcher._schedule_bindings = mock.Mock()
        dispatcher._normalize_changed_fields = (
            BaseConnectorBindingExportDispatcher._normalize_changed_fields.__get__(
                dispatcher,
                _StubExportDispatcher,
            )
        )
        dispatcher._should_schedule_bindings = (
            BaseConnectorBindingExportDispatcher._should_schedule_bindings.__get__(
                dispatcher,
                _StubExportDispatcher,
            )
        )

        result = BaseConnectorBindingExportDispatcher._dispatch_with_bindings(
            dispatcher,
            record,
            {"name"},
            watched_fields={"name"},
        )

        self.assertIs(result, bindings)
        dispatcher.ensure_bindings.assert_called_once_with(record)
        dispatcher._schedule_bindings.assert_called_once_with(bindings)

    def test_dispatch_with_bindings_schedules_matching_fields(self):
        dispatcher = _StubExportDispatcher()
        record = mock.Mock(name="record")
        bindings = mock.Mock(name="bindings")
        dispatcher.ensure_bindings = mock.Mock(return_value=bindings)
        dispatcher._schedule_bindings = mock.Mock()
        dispatcher._normalize_changed_fields = (
            BaseConnectorBindingExportDispatcher._normalize_changed_fields.__get__(
                dispatcher,
                _StubExportDispatcher,
            )
        )
        dispatcher._should_schedule_bindings = (
            BaseConnectorBindingExportDispatcher._should_schedule_bindings.__get__(
                dispatcher,
                _StubExportDispatcher,
            )
        )

        result = BaseConnectorBindingExportDispatcher._dispatch_with_bindings(
            dispatcher,
            record,
            {"name"},
            watched_fields={"name"},
        )

        self.assertIs(result, bindings)
        record.ensure_one.assert_called_once_with()
        dispatcher._schedule_bindings.assert_called_once_with(bindings)

    def test_dispatch_with_bindings_skips_non_matching_fields(self):
        dispatcher = _StubExportDispatcher()
        record = mock.Mock(name="record")
        bindings = mock.Mock(name="bindings")
        dispatcher.ensure_bindings = mock.Mock(return_value=bindings)
        dispatcher._schedule_bindings = mock.Mock()
        dispatcher._normalize_changed_fields = (
            BaseConnectorBindingExportDispatcher._normalize_changed_fields.__get__(
                dispatcher,
                _StubExportDispatcher,
            )
        )
        dispatcher._should_schedule_bindings = (
            BaseConnectorBindingExportDispatcher._should_schedule_bindings.__get__(
                dispatcher,
                _StubExportDispatcher,
            )
        )

        result = BaseConnectorBindingExportDispatcher._dispatch_with_bindings(
            dispatcher,
            record,
            {"description"},
            watched_fields={"name"},
        )

        self.assertIs(result, bindings)
        dispatcher._schedule_bindings.assert_not_called()
