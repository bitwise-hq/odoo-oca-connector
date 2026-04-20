from odoo import SUPERUSER_ID

from odoo.addons.component.core import Component


class ConnectorBindingImportScheduler(Component):
    """Queue stable inbound import jobs for connector collections."""

    _name = "base.connector.binding.import.scheduler"
    _inherit = "base.connector"

    def _normalize_metadata(self, metadata=None):
        normalized = dict(metadata or {})
        normalized.update(
            {
                "source": normalized.get("source") or False,
                "routing_key": normalized.get("routing_key") or False,
                "dedupe_key": normalized.get("dedupe_key") or False,
                "source_reference": normalized.get("source_reference") or False,
                "occurred_at": normalized.get("occurred_at") or False,
            }
        )
        return normalized

    def _get_job_description(
        self,
        *,
        payload,
        routing_key=None,
        binding_model_name=None,
        metadata=None,
        dispatch_component_name=None,
        dispatch_model_name=None,
        source_model_name=None,
        source_res_id=None,
    ):
        del payload, metadata, dispatch_component_name, source_model_name, source_res_id
        target_name = (
            binding_model_name
            or routing_key
            or dispatch_model_name
            or self.collection._name
        )
        return self.env._("Import connector payload for %s", target_name)

    def _get_identity_key(
        self,
        *,
        payload,
        routing_key=None,
        binding_model_name=None,
        metadata=None,
        dispatch_component_name=None,
        dispatch_model_name=None,
        source_model_name=None,
        source_res_id=None,
    ):
        del dispatch_component_name
        if source_model_name and source_res_id:
            return f"connector_binding_import:{source_model_name}:{source_res_id}"

        normalized_metadata = self._normalize_metadata(metadata)
        identity_value = (
            normalized_metadata.get("dedupe_key")
            or normalized_metadata.get("source_reference")
            or False
        )
        if not identity_value and isinstance(payload, dict):
            identity_value = payload.get("id") or payload.get("external_id") or False
        if not identity_value:
            identity_value = "adhoc"

        return (
            f"connector_binding_import:{self.collection._name}:{self.collection.id}:"
            f"{dispatch_model_name or self.work.model_name}:"
            f"{binding_model_name or routing_key or 'unknown'}:"
            f"{identity_value}"
        )

    def _get_schedule_parameter(self, method_name):
        method = getattr(self, method_name, None)
        if callable(method):
            return method
        return getattr(ConnectorBindingImportScheduler, method_name).__get__(
            self, type(self)
        )

    def schedule(
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
        self.collection.ensure_one()
        dispatch_model_name = dispatch_model_name or self.work.model_name
        normalized_metadata = self._normalize_metadata(metadata)

        description_getter = ConnectorBindingImportScheduler._get_schedule_parameter(
            self, "_get_job_description"
        )
        identity_key_getter = ConnectorBindingImportScheduler._get_schedule_parameter(
            self, "_get_identity_key"
        )

        delayed_collection = self.collection.with_user(SUPERUSER_ID).with_delay(
            description=description_getter(
                payload=payload,
                routing_key=routing_key,
                binding_model_name=binding_model_name,
                metadata=normalized_metadata,
                dispatch_component_name=dispatch_component_name,
                dispatch_model_name=dispatch_model_name,
                source_model_name=source_model_name,
                source_res_id=source_res_id,
            ),
            identity_key=identity_key_getter(
                payload=payload,
                routing_key=routing_key,
                binding_model_name=binding_model_name,
                metadata=normalized_metadata,
                dispatch_component_name=dispatch_component_name,
                dispatch_model_name=dispatch_model_name,
                source_model_name=source_model_name,
                source_res_id=source_res_id,
            ),
        )
        delayed_collection._run_import_dispatch(
            payload=payload,
            routing_key=routing_key,
            binding_model_name=binding_model_name,
            metadata=normalized_metadata,
            dispatch_component_name=dispatch_component_name,
            dispatch_model_name=dispatch_model_name,
            source_model_name=source_model_name or False,
            source_res_id=source_res_id or False,
        )
        return True
