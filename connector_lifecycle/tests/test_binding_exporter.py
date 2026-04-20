from unittest import mock

from odoo.tests.common import BaseCase, tagged

from odoo.addons.connector.exception import IDMissingInBackend
from odoo.addons.connector_lifecycle.components.binding_exporter import (
    BaseConnectorBindingExporter,
)
from odoo.addons.connector_lifecycle.components.export_scheduler import (
    ConnectorBindingExportScheduler,
)
from odoo.addons.connector_lifecycle.models.binding_export_mixin import (
    ConnectorBindingExportMixin,
)


class _StubExporter:
    pass


class _StubBindingModel:
    pass


@tagged("standard", "at_install")
class TestConnectorBindingExporter(BaseCase):
    def test_run_binds_external_id_and_calls_after_export(self):
        exporter = mock.Mock(name="exporter")
        binding = mock.Mock(name="binding")

        exporter.binder = mock.Mock(name="binder")
        exporter.binder.to_external.return_value = "ext_existing"
        exporter._should_import.return_value = False
        exporter._run.return_value = "exported"

        result = BaseConnectorBindingExporter.run(exporter, binding, fields=["name"])

        self.assertEqual(result, "exported")
        exporter.binder.to_external.assert_called_once_with(binding)
        exporter._run.assert_called_once_with(fields=["name"])
        exporter.binder.bind.assert_called_once_with("ext_existing", binding)
        exporter._after_export.assert_called_once_with()

    def test_default_run_falls_back_to_create_when_backend_record_is_missing(self):
        exporter = _StubExporter()
        exporter.binding = mock.Mock(name="binding")
        exporter.external_id = "ext_existing"
        exporter.env = mock.Mock(name="env")
        exporter.env._ = lambda message, *args: message % args if args else message
        exporter._has_to_skip = mock.Mock(return_value=False)
        exporter._export_dependencies = mock.Mock()
        exporter._lock = mock.Mock()
        exporter._map_data = mock.Mock(return_value="map_record")
        exporter._update_data = mock.Mock(return_value={"name": "updated"})
        exporter._update = mock.Mock(side_effect=IDMissingInBackend("missing"))
        exporter._create_data = mock.Mock(return_value={"name": "created"})
        exporter._create = mock.Mock(return_value="ext_created")

        result = BaseConnectorBindingExporter._run(exporter, fields=["name"])

        self.assertEqual(result, "Record exported with ID ext_created on Backend.")
        exporter._update.assert_called_once_with({"name": "updated"})
        exporter._create_data.assert_called_once_with("map_record", fields=None)
        exporter._create.assert_called_once_with({"name": "created"})
        self.assertEqual(exporter.external_id, "ext_created")

    def test_create_stores_export_result_and_derives_external_id_from_mapping(self):
        exporter = _StubExporter()
        exporter.backend_adapter = mock.Mock(name="backend_adapter")
        exporter.backend_adapter.create.return_value = {
            "id": "ext_created",
            "status": "draft",
        }
        exporter._validate_create_data = mock.Mock()
        exporter._set_export_result = (
            BaseConnectorBindingExporter._set_export_result.__get__(
                exporter,
                _StubExporter,
            )
        )
        exporter._get_exported_external_id = (
            BaseConnectorBindingExporter._get_exported_external_id.__get__(
                exporter,
                _StubExporter,
            )
        )

        result = BaseConnectorBindingExporter._create(exporter, {"name": "Example"})

        self.assertEqual(result, "ext_created")
        exporter._validate_create_data.assert_called_once_with({"name": "Example"})
        self.assertEqual(
            exporter.export_result, {"id": "ext_created", "status": "draft"}
        )

    def test_scheduler_enqueues_export_record(self):
        scheduler = _StubExporter()
        binding = mock.Mock(name="binding")
        delay_binding = mock.Mock(name="delay_binding")

        scheduler.env = mock.Mock(name="env")
        scheduler.env._ = lambda message, *args: message % args if args else message
        binding.with_user.return_value = binding
        binding.with_delay.return_value = delay_binding

        ConnectorBindingExportScheduler.schedule(scheduler, binding)

        binding.with_user.assert_called_once()
        binding.with_delay.assert_called_once()
        delay_binding.export_record.assert_called_once_with()

    def test_model_mixin_resets_last_sync_error_on_success(self):
        record = _StubBindingModel()
        exporter = mock.Mock(name="exporter")
        work = mock.Mock(name="work")
        work.component.return_value = exporter
        record._name = "connector.binding"
        record._fields = {"last_sync_error": object(), "sync_date": object()}
        record.backend_id = mock.MagicMock(name="backend_id")
        record.backend_id.work_on.return_value.__enter__.return_value = work
        record.ensure_one = mock.Mock()
        record.with_context = mock.Mock(return_value=record)
        record.write = mock.Mock()
        record._get_export_component_usage = (
            ConnectorBindingExportMixin._get_export_component_usage.__get__(
                record,
                _StubBindingModel,
            )
        )
        record._get_export_sync_field = (
            ConnectorBindingExportMixin._get_export_sync_field.__get__(
                record,
                _StubBindingModel,
            )
        )
        record._get_export_error_field = (
            ConnectorBindingExportMixin._get_export_error_field.__get__(
                record,
                _StubBindingModel,
            )
        )
        exporter.run.return_value = "done"

        result = ConnectorBindingExportMixin.export_record(record, fields=["name"])

        self.assertEqual(result, "done")
        exporter.run.assert_called_once_with(record, fields=["name"])
        record.write.assert_called_once()
        write_call = record.write.call_args
        write_values = write_call.args[0]
        self.assertFalse(write_values["last_sync_error"])
        self.assertIn("sync_date", write_values)

    def test_legacy_export_hook_names_delegate_to_canonical_names(self):
        record = _StubBindingModel()
        record._get_export_component_usage = (
            ConnectorBindingExportMixin._get_export_component_usage.__get__(
                record,
                _StubBindingModel,
            )
        )
        record._get_export_sync_field = (
            ConnectorBindingExportMixin._get_export_sync_field.__get__(
                record,
                _StubBindingModel,
            )
        )

        usage = ConnectorBindingExportMixin._get_record_exporter_usage(record)
        sync_field = ConnectorBindingExportMixin._get_export_sync_date_field(record)

        self.assertEqual(usage, "record.exporter")
        self.assertEqual(sync_field, "sync_date")
