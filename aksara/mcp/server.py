"""Official-SDK MCP Streamable HTTP server for generated Aksara tools."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import replace
from typing import Any
from urllib.parse import quote

import httpx
import mcp.types as mcp_types
from jsonschema import (  # type: ignore[import-untyped]
    ValidationError as JsonSchemaValidationError,
)
from jsonschema.validators import validator_for  # type: ignore[import-untyped]
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel.server import Server
from mcp.server.transport_security import TransportSecuritySettings

from aksara.ai.models import AiTool
from aksara.ai.registry import get_ai_tools_for_request
from aksara.db import atomic
from aksara.mcp.approval import ApprovalContext, ApprovalError, ApprovalManager
from aksara.mcp.audit import (
    LoggingMCPAuditSink,
    MCPAuditSink,
    MCPExecutionAuditEvent,
    safe_argument_summary,
)
from aksara.mcp.context import (
    AgentInvocationContext,
    push_agent_invocation_context,
    reset_agent_invocation_context,
)
from aksara.mcp.errors import ToolError, from_http
from aksara.security.context import principal_from_request
from aksara.security.mcp import require_mcp_audience, require_mcp_tenant
from aksara.security.principal import Principal

logger = logging.getLogger("aksara.mcp")


class _RollbackResponse(Exception):
    def __init__(self, response: httpx.Response):
        super().__init__(f"generated API returned {response.status_code}")
        self.response = response


class _ReplayGuard:
    """Bounded per-process duplicate protection; persistence is not implied."""

    def __init__(self, ttl_seconds: float, max_entries: int = 10_000):
        self.ttl_seconds = max(0.0, ttl_seconds)
        self.max_entries = max_entries
        self._seen: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def claim(self, key: str) -> bool:
        if not self.ttl_seconds:
            return True
        now = time.monotonic()
        async with self._lock:
            expired = [item for item, deadline in self._seen.items() if deadline <= now]
            for item in expired:
                self._seen.pop(item, None)
            if key in self._seen:
                return False
            if len(self._seen) >= self.max_entries:
                oldest = min(self._seen, key=self._seen.__getitem__)
                self._seen.pop(oldest, None)
            self._seen[key] = now + self.ttl_seconds
            return True


def _meta_value(meta: Mapping[str, Any] | None, *keys: str) -> str | None:
    for key in keys:
        value = (meta or {}).get(key)
        if value is not None:
            return str(value)
    return None


def _operation(tool: AiTool) -> str:
    return tool.name.rsplit("_", 1)[-1]


def _required_scope(tool: AiTool) -> str:
    access = "read" if tool.http_method.upper() == "GET" else "write"
    return f"mcp:{access}:{(tool.model or 'application').lower()}"


def _tool_schema(tool: AiTool) -> dict[str, Any]:
    schema = json.loads(json.dumps(tool.input_schema))
    if tool.approval_required:
        schema.setdefault("properties", {})["_approval_token"] = {
            "type": "string",
            "description": "Application-issued approval bound to this exact invocation",
        }
    return schema


def _mcp_tool(tool: AiTool) -> mcp_types.Tool:
    read_only = tool.http_method.upper() == "GET"
    return mcp_types.Tool(
        name=tool.name,
        title=tool.title,
        description=tool.description,
        input_schema=_tool_schema(tool),
        output_schema=tool.output_schema,
        annotations=mcp_types.ToolAnnotations(
            read_only_hint=read_only,
            destructive_hint=tool.http_method.upper() == "DELETE",
            idempotent_hint=read_only,
            open_world_hint=False,
        ),
        _meta={
            "aksara/httpMethod": tool.http_method,
            "aksara/path": tool.path,
            "aksara/tenantScoped": tool.tenant_scoped,
            "aksara/approvalRequired": tool.approval_required,
            "aksara/serverControlledFields": tool.server_controlled_fields,
        },
    )


class MCPRuntime:
    """Own the MCP SDK server, sessions, execution policy, and audit hook."""

    def __init__(self, app: Any, *, audit_sink: MCPAuditSink | None = None):
        from aksara._version import __version__
        from aksara.conf import settings

        self.app = app
        self.settings = settings
        self.audit_sink = audit_sink or LoggingMCPAuditSink()
        self.approvals = ApprovalManager(settings.mcp_approval_secret)
        self._replay = _ReplayGuard(settings.mcp_replay_ttl_seconds)
        self._session_context: AbstractAsyncContextManager[Any] | None = None
        self._started = False
        self.server = Server(
            "aksara",
            version=__version__,
            title=app.title,
            description="Generated Aksara application tools with execution-time authorization",
            on_list_tools=self._list_tools,
            on_call_tool=self._call_tool,
        )
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(settings.mcp_allowed_hosts),
            allowed_origins=list(settings.mcp_allowed_origins),
        )
        self.asgi_app = self.server.streamable_http_app(
            streamable_http_path="/",
            json_response=False,
            stateless_http=False,
            max_request_body_size=settings.mcp_max_request_body_size,
            transport_security=security,
            host=settings.mcp_transport_host,
            debug=bool(getattr(app, "debug", False)),
        )

    async def start(self) -> None:
        if self._started:
            return
        self._session_context = self.server.session_manager.run()
        try:
            await self._session_context.__aenter__()
        except BaseException:
            self._session_context = None
            raise
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        context, self._session_context = self._session_context, None
        self._started = False
        assert context is not None
        await context.__aexit__(None, None, None)

    def _request(self, ctx: ServerRequestContext[Any, Any]) -> Any | None:
        return ctx.request

    async def _list_tools(
        self,
        ctx: ServerRequestContext[Any, Any],
        params: mcp_types.PaginatedRequestParams | None,
    ) -> mcp_types.ListToolsResult:
        request = self._request(ctx)
        if request is None:
            return mcp_types.ListToolsResult(tools=[])
        tools = await get_ai_tools_for_request(request, self.app)
        principal = principal_from_request(request)
        if self.settings.mcp_require_scoped_tokens and principal.auth_method == "mcp_token":
            tools = [tool for tool in tools if principal.has_scope(_required_scope(tool))]
        return mcp_types.ListToolsResult(tools=[_mcp_tool(tool) for tool in tools])

    async def _call_tool(
        self,
        ctx: ServerRequestContext[Any, Any],
        params: mcp_types.CallToolRequestParams,
    ) -> mcp_types.CallToolResult:
        started_at = time.monotonic()
        request = self._request(ctx)
        arguments = dict(params.arguments or {})
        tool = self.app.ai_registry.get_tool(params.name)
        request_id = str(ctx.request_id or uuid.uuid4().hex)
        run_id = _meta_value(ctx.meta, "aksara.run_id", "aksara/runId") or request_id
        explicit_call_id = _meta_value(ctx.meta, "aksara.tool_call_id", "aksara/toolCallId")
        tool_call_id = explicit_call_id or request_id
        principal = principal_from_request(request) if request is not None else Principal.anonymous()
        operation = _operation(tool) if tool else "unknown"
        invocation = AgentInvocationContext(
            principal=principal,
            request_id=request_id,
            run_id=run_id,
            tool_call_id=tool_call_id,
            tool_name=params.name,
            operation=operation,
            policy_context={"surface": "mcp", "protocol_version": ctx.protocol_version},
        )
        token = push_agent_invocation_context(invocation)
        approval: ApprovalContext | None = None
        policy_decision = "not_evaluated"
        status: int | None = None
        error: ToolError | None = None
        try:
            if tool is None:
                error = ToolError("unknown_tool", "client", "The requested tool does not exist.")
                return self._error_result(error)
            if not principal.is_authenticated:
                error = ToolError("unauthenticated", "authorization", "Authentication is required.")
                return self._error_result(error)
            if not principal.is_ai_agent:
                error = ToolError("invalid_principal_type", "authorization", "MCP execution requires an AI-agent principal.")
                return self._error_result(error)
            if principal.is_expired:
                error = ToolError("credential_expired", "authorization", "The MCP credential has expired.")
                return self._error_result(error)
            if self.settings.mcp_token_audience:
                decision = require_mcp_audience(principal, self.settings.mcp_token_audience)
                if decision.denied:
                    error = ToolError("wrong_audience", "authorization", decision.reason)
                    return self._error_result(error)
            if tool.tenant_scoped:
                decision = require_mcp_tenant(principal)
                if decision.denied:
                    error = ToolError("tenant_context_required", "authorization", decision.reason)
                    return self._error_result(error)
            if self.settings.mcp_require_scoped_tokens:
                required_scope = _required_scope(tool)
                if not principal.has_scope(required_scope):
                    error = ToolError(
                        "missing_scope", "authorization", "The credential lacks the required tool scope.",
                        details={"required_scope": required_scope},
                    )
                    return self._error_result(error)
            if explicit_call_id:
                replay_key = f"{principal.token_id}:{params.name}:{explicit_call_id}"
                if not await self._replay.claim(replay_key):
                    error = ToolError("repeated_tool_request", "client", "This tool-call ID has already been used.")
                    return self._error_result(error)

            validation_error = self._validate_arguments(tool, arguments)
            if validation_error:
                error = validation_error
                return self._error_result(error)

            if tool.approval_required:
                try:
                    approval = self.approvals.verify(
                        arguments.get("_approval_token"),
                        principal=principal,
                        tool_name=tool.name,
                        arguments=arguments,
                    )
                except ApprovalError as exc:
                    error = ToolError(exc.code, "authorization", str(exc))
                    return self._error_result(error)
                invocation = replace(
                    invocation,
                    approval_context={
                        "approval_id": approval.approval_id,
                        "approved_by": approval.approved_by,
                    },
                )
                reset_agent_invocation_context(token)
                token = push_agent_invocation_context(invocation)

            policy_decision = "delegated_to_generated_api"
            try:
                async with asyncio.timeout(self.settings.mcp_tool_timeout_seconds):
                    response = await self._invoke_generated_api(request, tool, arguments, invocation)
            except TimeoutError:
                error = ToolError("tool_timeout", "transient", "The tool exceeded its execution timeout.", True)
                return self._error_result(error)
            status = response.status_code
            payload = self._response_payload(response)
            if response.is_error:
                error = from_http(response.status_code, payload)
                policy_decision = "denied" if response.status_code in {401, 403} else "api_rejected"
                return self._error_result(error, details=payload)
            policy_decision = "allowed"
            return self._success_result(payload)
        except asyncio.CancelledError:
            error = ToolError("cancelled", "transient", "The tool invocation was cancelled.", True)
            raise
        except Exception:
            logger.exception("Unhandled MCP tool failure for %s", params.name)
            error = ToolError("internal_error", "internal", "The framework could not complete the tool invocation.")
            return self._error_result(error)
        finally:
            reset_agent_invocation_context(token)
            await self._emit_audit(
                invocation=invocation,
                tool=tool,
                arguments=arguments,
                approval=approval,
                policy_decision=policy_decision,
                status=status,
                error=error,
                started_at=started_at,
            )

    def _validate_arguments(self, tool: AiTool, arguments: Mapping[str, Any]) -> ToolError | None:
        schema = _tool_schema(tool)
        try:
            validator_cls = validator_for(schema)
            validator_cls.check_schema(schema)
            validator_cls(schema).validate(arguments)
        except JsonSchemaValidationError as exc:
            code = "forbidden_field" if exc.validator == "additionalProperties" else "schema_mismatch"
            return ToolError(
                code,
                "client",
                "Tool arguments do not match the published schema.",
                details={"path": [str(item) for item in exc.absolute_path], "rule": exc.validator},
            )
        except Exception:
            logger.exception("Invalid generated MCP schema for %s", tool.name)
            return ToolError("invalid_tool_schema", "internal", "The generated tool schema is invalid.")
        return None

    async def _invoke_generated_api(
        self,
        request: Any,
        tool: AiTool,
        arguments: Mapping[str, Any],
        invocation: AgentInvocationContext,
    ) -> httpx.Response:
        path_arguments = dict(arguments)
        path_arguments.pop("_approval_token", None)
        pk = path_arguments.pop("pk", None)
        path = tool.path
        if "{pk}" in path:
            path = path.replace("{pk}", quote(str(pk), safe=""))

        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in {"content-length", "host", "connection", "transfer-encoding"}
        }
        headers.update({
            "x-aksara-request-id": invocation.request_id,
            "x-aksara-run-id": invocation.run_id,
            "x-aksara-tool-call-id": invocation.tool_call_id,
        })
        method = tool.http_method.upper()
        kwargs: dict[str, Any] = {"headers": headers}
        if method == "GET":
            kwargs["params"] = list(path_arguments.items())
        elif path_arguments:
            kwargs["json"] = path_arguments

        transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://aksara.internal") as client:
            if method in {"POST", "PUT", "PATCH", "DELETE"} and self.app.db is not None:
                try:
                    async with atomic(db=self.app.db):
                        response = await client.request(method, path, **kwargs)
                        if response.is_error:
                            raise _RollbackResponse(response)
                        return response
                except _RollbackResponse as exc:
                    return exc.response
            return await client.request(method, path, **kwargs)

    @staticmethod
    def _response_payload(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return {"detail": "Application returned a non-JSON response."}

    @staticmethod
    def _success_result(payload: Any) -> mcp_types.CallToolResult:
        text = json.dumps(payload, sort_keys=True, default=str)
        return mcp_types.CallToolResult(
            content=[mcp_types.TextContent(type="text", text=text)],
            structured_content=payload,
            is_error=False,
        )

    @staticmethod
    def _error_result(error: ToolError, *, details: Any = None) -> mcp_types.CallToolResult:
        payload: dict[str, Any] = {"ok": False, "error": error.to_dict()}
        if details is not None:
            payload["application_error"] = details
        return mcp_types.CallToolResult(
            content=[mcp_types.TextContent(type="text", text=json.dumps(payload, sort_keys=True, default=str))],
            structured_content=payload,
            is_error=True,
        )

    async def _emit_audit(
        self,
        *,
        invocation: AgentInvocationContext,
        tool: AiTool | None,
        arguments: Mapping[str, Any],
        approval: ApprovalContext | None,
        policy_decision: str,
        status: int | None,
        error: ToolError | None,
        started_at: float,
    ) -> None:
        principal = invocation.principal
        event = MCPExecutionAuditEvent(
            timestamp=MCPExecutionAuditEvent.timestamp_now(),
            request_id=invocation.request_id,
            run_id=invocation.run_id,
            tool_call_id=invocation.tool_call_id,
            tool_name=invocation.tool_name,
            operation=invocation.operation,
            http_method=tool.http_method if tool else "UNKNOWN",
            resource=tool.model if tool else None,
            object_id=str(arguments.get("pk")) if arguments.get("pk") is not None else None,
            principal_type=principal.auth_method,
            user_id=principal.user_id,
            human_owner_id=principal.human_owner_id,
            agent_id=principal.agent_id,
            token_id=principal.token_id,
            tenant_id=principal.tenant_id,
            argument_summary=safe_argument_summary(arguments),
            policy_decision=policy_decision,
            approval_required=bool(tool and tool.approval_required),
            approval_id=approval.approval_id if approval else None,
            approved_by=approval.approved_by if approval else None,
            outcome="error" if error else "success",
            error_code=error.code if error else None,
            http_status=status,
            duration_ms=round((time.monotonic() - started_at) * 1000, 3),
            metadata={"protocol": "mcp", "transport": "streamable-http"},
        )
        try:
            await self.audit_sink.emit(event)
        except Exception:
            logger.exception("MCP audit sink failed")


__all__ = ["MCPRuntime"]
