from odoo.addons.component.core import Component


class BaseConnectorBindingImportDispatcher(Component):
    """Route inbound payloads to the binding importer for the resolved model."""

    _name = "base.connector.binding.import.dispatcher"
    _collection = None
    _inbound_binding_model_mapping = {}

    def _get_binding_model_mapping(self):
        mapping = {}
        for cls in reversed(type(self).mro()):
            class_mapping = getattr(cls, "_inbound_binding_model_mapping", None)
            if class_mapping:
                mapping.update(class_mapping)
        return mapping

    def _get_binding_model_name(self, inbound_key, *, payload=None, metadata=None):
        del payload, metadata
        return self._get_binding_model_mapping().get(inbound_key)

    def _normalize_inbound_payload(self, payload):
        return payload or {}

    def _normalize_inbound_metadata(self, metadata=None):
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

    def _enrich_inbound_payload(self, payload, *, routing_key=None, metadata=None):
        inbound_payload = self._normalize_inbound_payload(payload)
        if not isinstance(inbound_payload, dict):
            return inbound_payload

        inbound_payload = dict(inbound_payload)
        normalized_metadata = self._normalize_inbound_metadata(metadata)
        inbound_routing_key = (
            routing_key or normalized_metadata.get("routing_key") or False
        )

        inbound_payload.update(
            {
                "_inbound_source": normalized_metadata.get("source") or False,
                "_inbound_routing_key": inbound_routing_key,
                "_inbound_dedupe_key": normalized_metadata.get("dedupe_key") or False,
                "_inbound_source_reference": normalized_metadata.get("source_reference")
                or False,
                "_inbound_occurred_at": normalized_metadata.get("occurred_at") or False,
            }
        )
        return inbound_payload

    def _get_event_inbound_metadata(self, event, payload):
        metadata_getter = getattr(event, "_get_inbound_event_metadata", None)
        if callable(metadata_getter):
            return self._normalize_inbound_metadata(metadata_getter(payload))

        return self._normalize_inbound_metadata(
            {
                "source": False,
                "routing_key": getattr(event, "routing_key", False) or False,
                "dedupe_key": getattr(event, "dedupe_key", False) or False,
                "source_reference": getattr(event, "source_reference", False) or False,
                "occurred_at": payload.get("occurred_at")
                if isinstance(payload, dict)
                else False,
            }
        )

    def prepare_event_dispatch(self, event):
        event.ensure_one()
        payload_getter = getattr(event, "_get_inbound_event_payload", None)
        if callable(payload_getter):
            payload = payload_getter()
        else:
            payload = event._parse_payload(event.request_body)
        if not isinstance(payload, dict):
            return False

        resource_data = payload.get("data") or {}
        family_getter = getattr(event, "_get_inbound_event_family", None)
        if callable(family_getter):
            inbound_key = family_getter(payload=payload)
        else:
            inbound_key = event._get_event_family(event.routing_key)
        if not inbound_key or not isinstance(resource_data, dict):
            return False

        metadata = self._get_event_inbound_metadata(event, payload)
        binding_model_name = self._get_binding_model_name(
            inbound_key,
            payload=resource_data,
            metadata=metadata,
        )
        return {
            "payload": resource_data,
            "routing_key": metadata["routing_key"],
            "binding_model_name": binding_model_name,
            "metadata": metadata,
        }

    def dispatch_inbound(
        self, *, payload, routing_key=None, binding_model_name=None, metadata=None
    ):
        normalized_metadata = self._normalize_inbound_metadata(metadata)
        inbound_routing_key = (
            routing_key or normalized_metadata.get("routing_key") or False
        )
        inbound_payload = self._enrich_inbound_payload(
            payload,
            routing_key=inbound_routing_key,
            metadata=normalized_metadata,
        )
        if not isinstance(inbound_payload, dict):
            return True

        model_name = binding_model_name or self._get_binding_model_name(
            inbound_routing_key,
            payload=inbound_payload,
            metadata=normalized_metadata,
        )
        if not model_name:
            return True

        with self.collection.work_on(model_name) as work:
            importer = work.component(usage="record.importer")
            importer.run(inbound_payload)
        return True
