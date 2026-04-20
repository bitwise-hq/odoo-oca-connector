from odoo import fields, models


class ConnectorBindingImportMixin(models.AbstractModel):
    """Collection-scoped helpers for scheduled inbound dispatch jobs."""

    _inherit = "collection.base"

    def _get_import_dispatch_component_name(self, dispatch_component_name=None):
        self.ensure_one()
        return dispatch_component_name or "base.connector.binding.import.dispatcher"

    def _get_scheduled_inbound_dispatch_component_name(
        self, dispatch_component_name=None
    ):
        return self._get_import_dispatch_component_name(dispatch_component_name)

    def _get_import_dispatch_model_name(self, dispatch_model_name=None):
        self.ensure_one()
        return dispatch_model_name or self._name

    def _get_scheduled_inbound_dispatch_model_name(self, dispatch_model_name=None):
        return self._get_import_dispatch_model_name(dispatch_model_name)

    def _get_import_source(self, source_model_name=None, source_res_id=None):
        self.ensure_one()
        if (
            not source_model_name
            or not source_res_id
            or not self.env.registry.get(source_model_name)
        ):
            return False
        return (
            self.env[source_model_name]
            .with_context(active_test=False)
            .browse(source_res_id)
            .exists()
        )

    def _get_scheduled_inbound_source(self, source_model_name=None, source_res_id=None):
        return self._get_import_source(source_model_name, source_res_id)

    def _get_import_state_values(self, source, *, state, processing_error=False):
        source = source[:1]
        if not source:
            return {}

        values = {}
        if "state" in source._fields:
            values["state"] = state
        if "processing_error" in source._fields:
            values["processing_error"] = processing_error or False
        if "processed_at" in source._fields:
            values["processed_at"] = (
                fields.Datetime.now() if state in ("done", "error") else False
            )
        return values

    def _get_scheduled_inbound_source_state_values(
        self, source, *, state, processing_error=False
    ):
        return self._get_import_state_values(
            source,
            state=state,
            processing_error=processing_error,
        )

    def _write_import_state(self, source, values):
        source = source[:1]
        if source and values:
            source.with_context(connector_no_export=True).write(values)
        return source

    def _write_scheduled_inbound_source_state(self, source, values):
        return self._write_import_state(source, values)

    def import_record(
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
        return self._run_import_dispatch(
            payload=payload,
            routing_key=routing_key,
            binding_model_name=binding_model_name,
            metadata=metadata,
            dispatch_component_name=dispatch_component_name,
            dispatch_model_name=dispatch_model_name,
            source_model_name=source_model_name,
            source_res_id=source_res_id,
        )

    def _run_import_dispatch(
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
        self.ensure_one()
        source = self._get_import_source(source_model_name, source_res_id)
        if source:
            self._write_import_state(
                source,
                self._get_import_state_values(source, state="processing"),
            )

        try:
            with self.work_on(
                self._get_import_dispatch_model_name(dispatch_model_name)
            ) as work:
                dispatcher = work.component_by_name(
                    self._get_import_dispatch_component_name(dispatch_component_name)
                )
                result = dispatcher.dispatch_inbound(
                    payload=payload,
                    routing_key=routing_key,
                    binding_model_name=binding_model_name,
                    metadata=metadata,
                )
        except Exception as err:
            if source:
                self._write_import_state(
                    source,
                    self._get_import_state_values(
                        source,
                        state="error",
                        processing_error=str(err),
                    ),
                )
            raise

        if source:
            self._write_import_state(
                source,
                self._get_import_state_values(source, state="done"),
            )
        return result

    def _run_scheduled_inbound_dispatch(
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
        return self._run_import_dispatch(
            payload=payload,
            routing_key=routing_key,
            binding_model_name=binding_model_name,
            metadata=metadata,
            dispatch_component_name=dispatch_component_name,
            dispatch_model_name=dispatch_model_name,
            source_model_name=source_model_name,
            source_res_id=source_res_id,
        )
