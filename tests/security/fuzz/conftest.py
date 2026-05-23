from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from hypothesis import HealthCheck, settings, strategies as st

from aksara import Model, fields
from aksara.api.serializers import ModelSerializer
from aksara.manager import QuerySet
from aksara.security.principal import Principal


FUZZ_SETTINGS = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)

HEAVY_FUZZ_SETTINGS = settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)

MALICIOUS_IDENTIFIERS = [
    "id; DROP TABLE users; --",
    "name OR 1=1",
    "tenant_id",
    "tenant_id__ne",
    "tenant_id.raw",
    "tenant_id->>'x'",
    "__class__",
    "../../../etc/passwd",
    "' OR '1'='1",
    '"; SELECT * FROM users; --',
    "tenant_id;--",
    "metadata__tenant_id",
    "$.tenant_id",
]

SCALAR_VALUES = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(10**6), max_value=10**6),
    st.text(max_size=256),
)

PAYLOADS = st.dictionaries(
    keys=st.text(min_size=0, max_size=64),
    values=SCALAR_VALUES,
    max_size=20,
)


class FuzzAccount(Model):
    tenant_id = fields.String(max_length=64, nullable=True)
    name = fields.String(max_length=64)
    status = fields.String(max_length=32, nullable=True)
    metadata = fields.JSON(nullable=True)
    secret_note = fields.String(
        max_length=128,
        nullable=True,
        ai_sensitive=True,
        ai_agent_writable=False,
    )
    locked_note = fields.String(
        max_length=128,
        nullable=True,
        ai_agent_writable=False,
    )

    class Meta:
        table_name = "security_fuzz_accounts"


class FuzzAccountSerializer(ModelSerializer):
    class Meta:
        model = FuzzAccount
        fields = [
            "id",
            "tenant_id",
            "name",
            "status",
            "metadata",
            "secret_note",
            "locked_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


@dataclass
class FakePolicyField:
    name: str
    ai_sensitive: bool = False
    ai_agent_writable: bool = True
    read_only: bool = False
    system_only: bool = False


@dataclass
class FakePolicyModel:
    _fields: dict[str, FakePolicyField] = field(default_factory=dict)

    @classmethod
    def with_fields(cls, *field_list: FakePolicyField) -> "FakePolicyModel":
        return cls(_fields={item.name: item for item in field_list})


@dataclass
class FakeState:
    principal: Any = None
    user: Any = None
    is_ai_agent: bool = False
    tenant_id: Any = None


@dataclass
class FakeRequest:
    query_params: dict[str, Any] = field(default_factory=dict)
    state: FakeState = field(default_factory=FakeState)
    headers: dict[str, str] = field(default_factory=dict)
    user: Any = None


class TrackingQuerySet:
    def __init__(self, filters: dict[str, Any] | None = None):
        self.filters = filters or {}
        self.count_calls = 0

    def filter(self, **kwargs: Any) -> "TrackingQuerySet":
        merged = {**self.filters, **kwargs}
        return TrackingQuerySet(merged)

    async def count(self) -> int:
        self.count_calls += 1
        return 0


class CaptureConnection:
    def __init__(self):
        self.sql: list[str] = []

    async def execute(self, sql: str) -> str:
        self.sql.append(sql)
        return "OK"


def encoded_cursor(payload: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


@pytest.fixture
def user_principal() -> Principal:
    return Principal.for_user(user_id="u1", tenant_id="tenant-a")


@pytest.fixture
def ai_principal() -> Principal:
    return Principal.for_ai_agent(agent_id="agent-1", tenant_id="tenant-a")


@pytest.fixture
def mcp_principal() -> Principal:
    return Principal.for_mcp_agent(tenant_id="tenant-a", scopes=["mcp:write:account"])


@pytest.fixture
def policy_model() -> FakePolicyModel:
    return FakePolicyModel.with_fields(
        FakePolicyField("name"),
        FakePolicyField("metadata"),
        FakePolicyField("tenant_id"),
        FakePolicyField("created_at", read_only=True),
        FakePolicyField("locked_note", ai_agent_writable=False),
        FakePolicyField("system_flag", system_only=True),
        FakePolicyField("secret_note", ai_sensitive=True, ai_agent_writable=False),
    )


@pytest.fixture
def account_queryset() -> QuerySet[FuzzAccount]:
    return QuerySet(FuzzAccount)
