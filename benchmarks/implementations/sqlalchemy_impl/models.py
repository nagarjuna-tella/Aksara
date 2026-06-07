"""SQLAlchemy async InvoiceOps benchmark models."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class SACompany(Base):
    __tablename__ = "bench_sqlalchemy_companies"

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    external_ref: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)


class SAVendor(Base):
    __tablename__ = "bench_sqlalchemy_vendors"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="bench_sqlalchemy_uq_vendors_company_name"),
        Index("bench_sqlalchemy_idx_vendors_company_status", "company_id", "status"),
    )

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    company_id = mapped_column(UUID(as_uuid=True), ForeignKey("bench_sqlalchemy_companies.id", ondelete="CASCADE"), nullable=False)
    name = mapped_column(String(255), nullable=False)
    tax_id = mapped_column(String(80), unique=True, nullable=True)
    email = mapped_column(String(255), nullable=True)
    status = mapped_column(String(24), nullable=False, default="active", server_default="active")
    meta = mapped_column("metadata", JSONB, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)

    company = relationship("SACompany")


class SAUser(Base):
    __tablename__ = "bench_sqlalchemy_users"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    company_id = mapped_column(UUID(as_uuid=True), ForeignKey("bench_sqlalchemy_companies.id", ondelete="CASCADE"), nullable=False)
    email = mapped_column(String(255), nullable=False, unique=True)
    name = mapped_column(String(255), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    meta = mapped_column("metadata", JSONB, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)

    roles = relationship("SARole", secondary="bench_sqlalchemy_user_roles", lazy="selectin")


class SARole(Base):
    __tablename__ = "bench_sqlalchemy_roles"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name = mapped_column(String(80), nullable=False, unique=True)
    description = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)


class SAUserRole(Base):
    __tablename__ = "bench_sqlalchemy_user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="bench_sqlalchemy_uq_user_roles_user_role"),
        Index("bench_sqlalchemy_idx_user_roles_user", "user_id"),
    )

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = mapped_column(UUID(as_uuid=True), ForeignKey("bench_sqlalchemy_users.id", ondelete="CASCADE"), nullable=False)
    role_id = mapped_column(UUID(as_uuid=True), ForeignKey("bench_sqlalchemy_roles.id", ondelete="CASCADE"), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)


class SAInvoice(Base):
    __tablename__ = "bench_sqlalchemy_invoices"
    __table_args__ = (
        Index("bench_sqlalchemy_idx_invoices_vendor", "vendor_id"),
        Index("bench_sqlalchemy_idx_invoices_status", "status"),
        Index("bench_sqlalchemy_idx_invoices_issued_at", "issued_at"),
        Index("bench_sqlalchemy_idx_invoices_vendor_status_date", "vendor_id", "status", "issued_at"),
    )

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    company_id = mapped_column(UUID(as_uuid=True), ForeignKey("bench_sqlalchemy_companies.id", ondelete="CASCADE"), nullable=False)
    vendor_id = mapped_column(UUID(as_uuid=True), ForeignKey("bench_sqlalchemy_vendors.id", ondelete="RESTRICT"), nullable=False)
    invoice_number = mapped_column(String(80), nullable=False, unique=True)
    status = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    issued_at = mapped_column(DateTime(timezone=True), nullable=False)
    due_at = mapped_column(DateTime(timezone=True), nullable=True)
    subtotal = mapped_column(Numeric(14, 2), nullable=False)
    tax = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    total = mapped_column(Numeric(14, 2), nullable=False)
    currency = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    meta = mapped_column("metadata", JSONB, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)

    vendor = relationship("SAVendor", lazy="selectin")
    lines = relationship("SAInvoiceLine", lazy="selectin", cascade="all, delete-orphan")


class SAInvoiceLine(Base):
    __tablename__ = "bench_sqlalchemy_invoice_lines"
    __table_args__ = (
        UniqueConstraint("invoice_id", "line_no", name="bench_sqlalchemy_uq_invoice_lines_invoice_line"),
        Index("bench_sqlalchemy_idx_invoice_lines_invoice", "invoice_id"),
    )

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    invoice_id = mapped_column(UUID(as_uuid=True), ForeignKey("bench_sqlalchemy_invoices.id", ondelete="CASCADE"), nullable=False)
    line_no = mapped_column(Integer, nullable=False)
    description = mapped_column(Text, nullable=False)
    quantity = mapped_column(Integer, nullable=False)
    unit_price = mapped_column(Numeric(14, 2), nullable=False)
    amount = mapped_column(Numeric(14, 2), nullable=False)
    meta = mapped_column("metadata", JSONB, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)


class SAPayment(Base):
    __tablename__ = "bench_sqlalchemy_payments"
    __table_args__ = (Index("bench_sqlalchemy_idx_payments_invoice", "invoice_id"),)

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    invoice_id = mapped_column(UUID(as_uuid=True), ForeignKey("bench_sqlalchemy_invoices.id", ondelete="CASCADE"), nullable=False)
    amount = mapped_column(Numeric(14, 2), nullable=False)
    paid_at = mapped_column(DateTime(timezone=True), nullable=True)
    method = mapped_column(String(32), nullable=False)
    reference = mapped_column(String(120), unique=True, nullable=True)
    meta = mapped_column("metadata", JSONB, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)


class SAAuditLog(Base):
    __tablename__ = "bench_sqlalchemy_audit_logs"
    __table_args__ = (Index("bench_sqlalchemy_idx_audit_logs_entity", "entity_type", "entity_id"),)

    id = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    company_id = mapped_column(UUID(as_uuid=True), ForeignKey("bench_sqlalchemy_companies.id", ondelete="CASCADE"), nullable=False)
    user_id = mapped_column(UUID(as_uuid=True), ForeignKey("bench_sqlalchemy_users.id", ondelete="SET NULL"), nullable=True)
    entity_type = mapped_column(String(80), nullable=False)
    entity_id = mapped_column(UUID(as_uuid=True), nullable=False)
    action = mapped_column(String(80), nullable=False)
    meta = mapped_column("metadata", JSONB, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)

