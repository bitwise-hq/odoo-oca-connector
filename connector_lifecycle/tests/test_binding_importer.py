from unittest import mock

from odoo.tests.common import BaseCase, tagged

from odoo.addons.connector_lifecycle.components.binding_importer import (
    BaseConnectorBindingImporter,
)


@tagged("standard", "at_install")
class TestConnectorBindingImporter(BaseCase):
    def test_inbound_metadata_helpers_read_canonical_inbound_keys(self):
        importer = BaseConnectorBindingImporter.__new__(BaseConnectorBindingImporter)

        self.assertEqual(
            importer._get_inbound_routing_key(
                {"_inbound_routing_key": "customer.updated"}
            ),
            "customer.updated",
        )

    def test_run_orchestrates_binding_lifecycle(self):
        importer = mock.Mock(name="importer")
        normalized_record = {"id": "ext_1", "name": "Example"}
        record = mock.Mock(name="record")
        binding = mock.Mock(name="binding")
        mapped_values = {"external_id": "ext_1", "name": "Example"}

        importer._normalize_external_record.return_value = normalized_record
        importer._get_external_id.return_value = "ext_1"
        importer._find_binding_for_external_id.return_value = False
        importer._resolve_target_record.return_value = record
        importer._prepare_mapped_values.return_value = mapped_values
        importer._ensure_binding.return_value = binding
        importer._after_import.return_value = binding
        importer.binder = mock.Mock(name="binder")

        result = BaseConnectorBindingImporter.run(importer, {"id": "ext_1"})

        self.assertIs(result, binding)
        importer._normalize_external_record.assert_called_once_with({"id": "ext_1"})
        importer._get_external_id.assert_called_once_with(normalized_record)
        importer._find_binding_for_external_id.assert_called_once_with("ext_1")
        importer._resolve_target_record.assert_called_once_with(
            normalized_record, binding=False
        )
        importer._prepare_mapped_values.assert_called_once_with(
            normalized_record, record, binding=False
        )
        importer._ensure_binding.assert_called_once_with(
            record, mapped_values, binding=False
        )
        importer._validate_binding_assignment.assert_called_once_with(
            binding, "ext_1", record
        )
        importer._write_binding_values.assert_called_once_with(binding, mapped_values)
        importer.binder.bind.assert_called_once_with("ext_1", binding)
        importer._after_import.assert_called_once_with(binding, normalized_record)

    def test_import_dependency_binding_reads_remote_record_by_default(self):
        importer = mock.MagicMock(name="importer")
        dependency_binding = mock.Mock(name="dependency_binding")
        dependency_importer = mock.Mock(name="dependency_importer")
        adapter = mock.Mock(name="adapter")
        dependency_record = {"id": "dep_1"}
        work = importer.backend_record.work_on.return_value.__enter__.return_value

        dependency_importer.run.return_value = dependency_binding
        adapter.read.return_value = dependency_record
        work.component.side_effect = (
            lambda usage: dependency_importer if usage == "record.importer" else adapter
        )

        result = BaseConnectorBindingImporter._import_dependency_binding(
            importer,
            "dep.model",
            external_id="dep_1",
        )

        self.assertIs(result, dependency_binding)
        importer.backend_record.work_on.assert_called_once_with("dep.model")
        adapter.read.assert_called_once_with("dep_1")
        dependency_importer.run.assert_called_once_with(dependency_record)

    def test_import_dependency_binding_returns_empty_recordset_when_missing(self):
        importer = mock.MagicMock(name="importer")
        empty_recordset = mock.Mock(name="empty_recordset")
        dependency_importer = mock.Mock(name="dependency_importer")
        adapter = mock.Mock(name="adapter")
        loader = mock.Mock(name="loader", return_value=None)
        work = importer.backend_record.work_on.return_value.__enter__.return_value

        importer.env.__getitem__.return_value = empty_recordset
        work.component.side_effect = (
            lambda usage: dependency_importer if usage == "record.importer" else adapter
        )

        result = BaseConnectorBindingImporter._import_dependency_binding(
            importer,
            "dep.model",
            external_id="dep_1",
            loader=loader,
            empty_if_missing=True,
        )

        self.assertIs(result, empty_recordset)
        loader.assert_called_once_with(adapter)
        adapter.read.assert_not_called()
        dependency_importer.run.assert_not_called()
        importer.env.__getitem__.assert_called_once_with("dep.model")
