"""Correctness helpers used by every benchmark workload."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable


@dataclass(frozen=True)
class CorrectnessCheck:
    """A pass/fail correctness result with diagnostic detail."""

    name: str
    passed: bool
    details: str = ""
    errors: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def ok(cls, name: str, details: str = "") -> "CorrectnessCheck":
        return cls(name=name, passed=True, details=details)

    @classmethod
    def fail(cls, name: str, error: str) -> "CorrectnessCheck":
        return cls(name=name, passed=False, errors=(error,))

    @classmethod
    def combine(cls, name: str, checks: Iterable["CorrectnessCheck"]) -> "CorrectnessCheck":
        collected = tuple(checks)
        errors = tuple(error for check in collected for error in check.errors if not check.passed)
        return cls(
            name=name,
            passed=all(check.passed for check in collected),
            details="; ".join(check.details for check in collected if check.details),
            errors=errors,
        )


def require(condition: bool, message: str, *, name: str = "require") -> CorrectnessCheck:
    return CorrectnessCheck.ok(name) if condition else CorrectnessCheck.fail(name, message)


def require_equal(actual: Any, expected: Any, *, name: str = "require_equal") -> CorrectnessCheck:
    if actual == expected:
        return CorrectnessCheck.ok(name)
    return CorrectnessCheck.fail(name, f"expected {expected!r}, got {actual!r}")


def require_decimal_equal(
    actual: Decimal | int | str,
    expected: Decimal | int | str,
    *,
    name: str = "require_decimal_equal",
) -> CorrectnessCheck:
    actual_decimal = Decimal(str(actual))
    expected_decimal = Decimal(str(expected))
    if actual_decimal == expected_decimal:
        return CorrectnessCheck.ok(name)
    return CorrectnessCheck.fail(name, f"expected {expected_decimal}, got {actual_decimal}")


def validate_no_duplicate_page_rows(ids: Iterable[Any]) -> CorrectnessCheck:
    values = list(ids)
    return require(len(values) == len(set(values)), "paginated result contains duplicate IDs", name="page_unique")


def validate_invoice_totals(invoice: dict[str, Any], lines: Iterable[dict[str, Any]]) -> CorrectnessCheck:
    line_rows = list(lines)
    subtotal = sum(Decimal(str(row["amount"])) for row in line_rows)
    return CorrectnessCheck.combine(
        "invoice_totals",
        [
            require(line_rows, "invoice has no lines", name="lines_exist"),
            require_decimal_equal(subtotal, invoice["subtotal"], name="subtotal_matches_lines"),
            require_decimal_equal(
                Decimal(str(invoice["subtotal"])) + Decimal(str(invoice["tax"])),
                invoice["total"],
                name="total_matches_subtotal_tax",
            ),
        ],
    )

