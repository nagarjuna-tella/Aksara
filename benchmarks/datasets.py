"""Deterministic InvoiceOps dataset generation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Iterator

from benchmarks.config import DatasetProfile


NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "aksara.orm.benchmarks")
STATUSES = ("draft", "sent", "paid", "overdue", "void")
PAYMENT_METHODS = ("ach", "card", "wire")
BASE_TIME = datetime(2025, 1, 1, tzinfo=timezone.utc)


def stable_uuid(label: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, label)


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def batched(iterable: Iterable[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


@dataclass(frozen=True)
class DatasetSummary:
    companies: int
    vendors: int
    invoices: int
    invoice_lines: int
    payments: int
    users: int
    roles: int
    user_roles: int
    audit_logs: int

    def to_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


class InvoiceDataset:
    """Generate the same logical rows for every implementation."""

    def __init__(self, profile: DatasetProfile, *, seed: int = 42):
        self.profile = profile
        self.seed = seed
        self.user_count = max(10, profile.companies * 5)
        self.role_count = 4
        self.audit_log_count = max(50, min(profile.invoices, profile.invoices // 5))

    def summary(self) -> DatasetSummary:
        paid_count = sum(1 for i in range(self.profile.invoices) if self.invoice_status(i) == "paid")
        return DatasetSummary(
            companies=self.profile.companies,
            vendors=self.profile.vendors,
            invoices=self.profile.invoices,
            invoice_lines=self.profile.invoice_lines,
            payments=paid_count,
            users=self.user_count,
            roles=self.role_count,
            user_roles=self.user_count * 2,
            audit_logs=self.audit_log_count,
        )

    def id_for(self, kind: str, index: int) -> uuid.UUID:
        return stable_uuid(f"{self.seed}:{kind}:{index}")

    def sample_invoice_id(self, index: int = 0) -> uuid.UUID:
        return self.id_for("invoice", index % self.profile.invoices)

    def sample_invoice_number(self, index: int = 0) -> str:
        return f"INV-{index % self.profile.invoices:08d}"

    def sample_vendor_id(self, index: int = 0) -> uuid.UUID:
        return self.id_for("vendor", index % self.profile.vendors)

    def sample_company_id(self, index: int = 0) -> uuid.UUID:
        return self.id_for("company", index % self.profile.companies)

    def invoice_status(self, index: int) -> str:
        return STATUSES[index % len(STATUSES)]

    def issued_at(self, index: int) -> datetime:
        return BASE_TIME + timedelta(days=index % 365, minutes=index % 1440)

    def line_amount(self, invoice_index: int, line_no: int) -> Decimal:
        quantity = Decimal((line_no % 5) + 1)
        unit_price = money(Decimal("19.50") + Decimal((invoice_index % 23) * 7 + line_no) / Decimal("10"))
        return money(quantity * unit_price)

    def invoice_amounts(self, invoice_index: int) -> tuple[Decimal, Decimal, Decimal]:
        subtotal = sum(
            self.line_amount(invoice_index, line_no)
            for line_no in range(1, self.profile.invoice_lines_per_invoice + 1)
        )
        tax = money(subtotal * Decimal("0.0825"))
        total = money(subtotal + tax)
        return money(subtotal), tax, total

    def companies(self) -> Iterator[dict[str, Any]]:
        for i in range(self.profile.companies):
            yield {
                "id": self.id_for("company", i),
                "name": f"Company {i:04d}",
                "external_ref": f"CO-{i:04d}",
                "metadata": {"tier": "enterprise" if i % 2 == 0 else "growth", "seed": self.seed},
            }

    def vendors(self) -> Iterator[dict[str, Any]]:
        for i in range(self.profile.vendors):
            yield {
                "id": self.id_for("vendor", i),
                "company_id": self.sample_company_id(i),
                "name": f"Vendor {i:06d}",
                "tax_id": f"TAX-{i:08d}",
                "email": f"vendor{i:06d}@example.com",
                "status": "active" if i % 11 else "review",
                "metadata": {"category": f"category-{i % 7}", "risk": i % 5},
            }

    def users(self) -> Iterator[dict[str, Any]]:
        for i in range(self.user_count):
            yield {
                "id": self.id_for("user", i),
                "company_id": self.sample_company_id(i),
                "email": f"user{i:05d}@example.com",
                "name": f"User {i:05d}",
                "is_active": i % 13 != 0,
                "metadata": {"department": f"dept-{i % 6}"},
            }

    def roles(self) -> Iterator[dict[str, Any]]:
        names = ("admin", "finance", "auditor", "approver")
        for i, name in enumerate(names):
            yield {
                "id": self.id_for("role", i),
                "name": name,
                "description": f"{name.title()} role",
            }

    def user_roles(self) -> Iterator[dict[str, Any]]:
        for i in range(self.user_count):
            for offset in (0, 1):
                role_index = (i + offset) % self.role_count
                yield {
                    "id": stable_uuid(f"{self.seed}:user-role:{i}:{role_index}"),
                    "user_id": self.id_for("user", i),
                    "role_id": self.id_for("role", role_index),
                }

    def invoices(self, *, start: int = 0, count: int | None = None) -> Iterator[dict[str, Any]]:
        stop = self.profile.invoices if count is None else min(self.profile.invoices, start + count)
        for i in range(start, stop):
            subtotal, tax, total = self.invoice_amounts(i)
            issued = self.issued_at(i)
            yield {
                "id": self.id_for("invoice", i),
                "company_id": self.sample_company_id(i),
                "vendor_id": self.sample_vendor_id(i),
                "invoice_number": self.sample_invoice_number(i),
                "status": self.invoice_status(i),
                "issued_at": issued,
                "due_at": issued + timedelta(days=30),
                "subtotal": subtotal,
                "tax": tax,
                "total": total,
                "currency": "USD",
                "metadata": {"source": "seed", "bucket": i % 17},
            }

    def invoice_lines(self, *, start_invoice: int = 0, invoice_count: int | None = None) -> Iterator[dict[str, Any]]:
        stop = self.profile.invoices if invoice_count is None else min(
            self.profile.invoices,
            start_invoice + invoice_count,
        )
        for invoice_index in range(start_invoice, stop):
            invoice_id = self.id_for("invoice", invoice_index)
            for line_no in range(1, self.profile.invoice_lines_per_invoice + 1):
                amount = self.line_amount(invoice_index, line_no)
                quantity = (line_no % 5) + 1
                yield {
                    "id": stable_uuid(f"{self.seed}:invoice-line:{invoice_index}:{line_no}"),
                    "invoice_id": invoice_id,
                    "line_no": line_no,
                    "description": f"Line {line_no} for invoice {invoice_index}",
                    "quantity": quantity,
                    "unit_price": money(amount / Decimal(quantity)),
                    "amount": amount,
                    "metadata": {"sku": f"SKU-{invoice_index % 97:03d}-{line_no}"},
                }

    def payments(self) -> Iterator[dict[str, Any]]:
        for i in range(self.profile.invoices):
            if self.invoice_status(i) != "paid":
                continue
            _subtotal, _tax, total = self.invoice_amounts(i)
            yield {
                "id": self.id_for("payment", i),
                "invoice_id": self.id_for("invoice", i),
                "amount": total,
                "paid_at": self.issued_at(i) + timedelta(days=12),
                "method": PAYMENT_METHODS[i % len(PAYMENT_METHODS)],
                "reference": f"PAY-{i:08d}",
                "metadata": {"processor": "seed"},
            }

    def audit_logs(self) -> Iterator[dict[str, Any]]:
        actions = ("created", "updated", "approved", "paid")
        for i in range(self.audit_log_count):
            yield {
                "id": self.id_for("audit", i),
                "company_id": self.sample_company_id(i),
                "user_id": self.id_for("user", i % self.user_count),
                "entity_type": "invoice",
                "entity_id": self.id_for("invoice", i % self.profile.invoices),
                "action": actions[i % len(actions)],
                "metadata": {"ip": f"10.0.{i % 255}.{(i * 7) % 255}"},
                "created_at": BASE_TIME + timedelta(minutes=i),
            }

    def runtime_vendor(self, implementation: str, index: int) -> dict[str, Any]:
        token = f"{implementation}:runtime:vendor:{index}"
        return {
            "id": stable_uuid(token),
            "company_id": self.sample_company_id(index),
            "name": f"Runtime Vendor {implementation} {index:06d}",
            "tax_id": f"RT-{implementation[:3].upper()}-{index:08d}",
            "email": f"runtime-vendor-{implementation}-{index:06d}@example.com",
            "status": "active",
            "metadata": {"runtime": True, "index": index},
        }

    def runtime_invoice(self, implementation: str, index: int, *, line_count: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        invoice_id = stable_uuid(f"{implementation}:runtime:invoice:{index}")
        line_amounts = [money(Decimal("25.00") + Decimal(i)) for i in range(1, line_count + 1)]
        subtotal = money(sum(line_amounts))
        tax = money(subtotal * Decimal("0.0825"))
        issued = BASE_TIME + timedelta(days=400 + index % 31)
        invoice = {
            "id": invoice_id,
            "company_id": self.sample_company_id(index),
            "vendor_id": self.sample_vendor_id(index),
            "invoice_number": f"RT-{implementation[:3].upper()}-{index:08d}",
            "status": "draft",
            "issued_at": issued,
            "due_at": issued + timedelta(days=30),
            "subtotal": subtotal,
            "tax": tax,
            "total": money(subtotal + tax),
            "currency": "USD",
            "metadata": {"runtime": True, "index": index},
        }
        lines = [
            {
                "id": stable_uuid(f"{implementation}:runtime:invoice-line:{index}:{line_no}"),
                "invoice_id": invoice_id,
                "line_no": line_no,
                "description": f"Runtime line {line_no}",
                "quantity": 1,
                "unit_price": amount,
                "amount": amount,
                "metadata": {"runtime": True},
            }
            for line_no, amount in enumerate(line_amounts, start=1)
        ]
        return invoice, lines

