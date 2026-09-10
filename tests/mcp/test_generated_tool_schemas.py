from __future__ import annotations

from enum import Enum
from typing import ClassVar

import pytest

from aksara import Model, fields
from aksara.ai.registry import discover_tools_from_viewset
from aksara.api.schemas import clear_schema_cache
from aksara.api.viewsets import ModelViewSet
from aksara.registry import ModelRegistry


class Phase(Enum):
    DRAFT = "draft"
    LIVE = "live"


@pytest.fixture(autouse=True)
def clear_schema_state():
    ModelRegistry.clear()
    clear_schema_cache()
    yield
    ModelRegistry.clear()
    clear_schema_cache()


def _tool_map():
    class Owner(Model):
        __tablename__ = "mcp_schema_owners"

        label = fields.String(max_length=40)

    class Tag(Model):
        __tablename__ = "mcp_schema_tags"

        label = fields.String(max_length=40)

    class Contract(Model):
        __tablename__ = "mcp_schema_contracts"

        required_name = fields.String(
            min_length=2,
            max_length=12,
            regex=r"^[a-z]+$",
            ai_description="Required machine name",
        )
        optional_note = fields.Text(nullable=True)
        phase = fields.Enum(Phase, default=Phase.DRAFT)
        payload = fields.JSON(nullable=True)
        labels = fields.Array(item_type=str, nullable=False)
        embedding = fields.Vector(dimensions=3, nullable=True)
        owner = fields.ForeignKey(Owner, nullable=True)
        tags = fields.ManyToMany(Tag)
        secret = fields.String(ai_sensitive=True)
        server_score = fields.Integer(default=0, ai_agent_writable=False)

    class ContractViewSet(ModelViewSet):
        model = Contract
        prefix = "/api/contracts"

    return {tool.name: tool for tool in discover_tools_from_viewset(ContractViewSet)}


def test_generated_crud_schemas_preserve_field_contracts() -> None:
    tools = _tool_map()
    assert set(tools) == {
        "contract_list",
        "contract_retrieve",
        "contract_create",
        "contract_update",
        "contract_delete",
    }

    create = tools["contract_create"].input_schema
    properties = create["properties"]
    assert create["additionalProperties"] is False
    assert set(create["required"]) == {"required_name", "labels"}
    assert properties["required_name"] == {
        "description": "Required machine name",
        "title": "Required Name",
        "type": "string",
        "minLength": 2,
        "maxLength": 12,
        "pattern": "^[a-z]+$",
    }
    assert properties["phase"]["enum"] == ["draft", "live"]
    assert {option["type"] for option in properties["payload"]["anyOf"]} >= {
        "object",
        "array",
        "string",
        "null",
    }
    assert properties["labels"]["items"] == {"type": "string"}
    assert properties["embedding"]["minItems"] == 3
    assert properties["embedding"]["maxItems"] == 3
    assert properties["owner_id"]["anyOf"][0] == {
        "format": "uuid",
        "type": "string",
    }
    assert properties["tags"]["anyOf"][0]["items"] == {
        "format": "uuid",
        "type": "string",
    }
    assert "secret" not in properties
    assert "server_score" not in properties
    assert "id" not in properties
    assert "created_at" not in properties

    update = tools["contract_update"].input_schema
    assert update["required"] == ["pk"]
    assert update["additionalProperties"] is False
    assert "secret" not in update["properties"]
    assert "server_score" not in update["properties"]


def test_generated_read_and_filter_schemas_hide_sensitive_fields() -> None:
    tools = _tool_map()
    list_input = tools["contract_list"].input_schema
    assert list_input["properties"]["limit"]["maximum"] == 100
    assert list_input["properties"]["offset"]["minimum"] == 0
    assert "secret" not in list_input["properties"]

    read = tools["contract_retrieve"].output_schema
    assert "secret" not in read["properties"]
    assert read["properties"]["phase"]["enum"] == ["draft", "live"]
    assert read["properties"]["embedding"]["minItems"] == 3
    assert read["properties"]["embedding"]["maxItems"] == 3


def test_generated_tool_metadata_marks_tenant_and_approval_boundaries() -> None:
    from aksara import TenantModel

    class ProtectedRecord(TenantModel):
        __tablename__ = "mcp_protected_records"

        value = fields.String(max_length=20)

    class ProtectedViewSet(ModelViewSet):
        model = ProtectedRecord
        prefix = "/api/protected"
        mcp_approval_required_actions: ClassVar[set[str]] = {"delete"}

    tools = {
        tool.name: tool for tool in discover_tools_from_viewset(ProtectedViewSet)
    }
    assert all(tool.tenant_scoped for tool in tools.values())
    assert all(tool.server_controlled_fields == ["tenant_id"] for tool in tools.values())
    assert tools["protectedrecord_delete"].approval_required is True
    assert tools["protectedrecord_create"].approval_required is False
