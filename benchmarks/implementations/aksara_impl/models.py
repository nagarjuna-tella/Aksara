"""Aksara InvoiceOps benchmark models."""

from __future__ import annotations

from aksara import CASCADE, RESTRICT, SET_NULL, Model, fields


class BenchCompany(Model):
    __tablename__ = "bench_aksara_companies"

    name = fields.String(max_length=200)
    external_ref = fields.String(max_length=80, unique=True)
    metadata = fields.JSON(nullable=True)


class BenchVendor(Model):
    __tablename__ = "bench_aksara_vendors"

    company = fields.ForeignKey(BenchCompany, on_delete=CASCADE, related_name="vendors")
    name = fields.String(max_length=255)
    tax_id = fields.String(max_length=80, unique=True, nullable=True)
    email = fields.String(max_length=255, nullable=True)
    status = fields.String(max_length=24, default="active")
    metadata = fields.JSON(nullable=True)


class BenchUser(Model):
    __tablename__ = "bench_aksara_users"

    company = fields.ForeignKey(BenchCompany, on_delete=CASCADE, related_name="users")
    email = fields.String(max_length=255, unique=True)
    name = fields.String(max_length=255)
    is_active = fields.Boolean(default=True)
    metadata = fields.JSON(nullable=True)


class BenchRole(Model):
    __tablename__ = "bench_aksara_roles"

    name = fields.String(max_length=80, unique=True)
    description = fields.Text(nullable=True)


class BenchUserRole(Model):
    __tablename__ = "bench_aksara_user_roles"

    user = fields.ForeignKey(BenchUser, on_delete=CASCADE, related_name="user_roles")
    role = fields.ForeignKey(BenchRole, on_delete=CASCADE, related_name="user_roles")


class BenchInvoice(Model):
    __tablename__ = "bench_aksara_invoices"

    company = fields.ForeignKey(BenchCompany, on_delete=CASCADE, related_name="invoices")
    vendor = fields.ForeignKey(BenchVendor, on_delete=RESTRICT, related_name="invoices")
    invoice_number = fields.String(max_length=80, unique=True)
    status = fields.String(max_length=24, default="draft")
    issued_at = fields.DateTime()
    due_at = fields.DateTime(nullable=True)
    subtotal = fields.Decimal(max_digits=14, decimal_places=2)
    tax = fields.Decimal(max_digits=14, decimal_places=2, default=0)
    total = fields.Decimal(max_digits=14, decimal_places=2)
    currency = fields.String(max_length=3, default="USD")
    metadata = fields.JSON(nullable=True)


class BenchInvoiceLine(Model):
    __tablename__ = "bench_aksara_invoice_lines"

    invoice = fields.ForeignKey(BenchInvoice, on_delete=CASCADE, related_name="lines")
    line_no = fields.Integer()
    description = fields.Text()
    quantity = fields.Integer()
    unit_price = fields.Decimal(max_digits=14, decimal_places=2)
    amount = fields.Decimal(max_digits=14, decimal_places=2)
    metadata = fields.JSON(nullable=True)


class BenchPayment(Model):
    __tablename__ = "bench_aksara_payments"

    invoice = fields.ForeignKey(BenchInvoice, on_delete=CASCADE, related_name="payments")
    amount = fields.Decimal(max_digits=14, decimal_places=2)
    paid_at = fields.DateTime(nullable=True)
    method = fields.String(max_length=32)
    reference = fields.String(max_length=120, unique=True, nullable=True)
    metadata = fields.JSON(nullable=True)


class BenchAuditLog(Model):
    __tablename__ = "bench_aksara_audit_logs"

    company = fields.ForeignKey(BenchCompany, on_delete=CASCADE, related_name="audit_logs")
    user = fields.ForeignKey(BenchUser, on_delete=SET_NULL, nullable=True, related_name="audit_logs")
    entity_type = fields.String(max_length=80)
    entity_id = fields.UUID()
    action = fields.String(max_length=80)
    metadata = fields.JSON(nullable=True)


MODELS = (
    BenchCompany,
    BenchVendor,
    BenchUser,
    BenchRole,
    BenchUserRole,
    BenchInvoice,
    BenchInvoiceLine,
    BenchPayment,
    BenchAuditLog,
)

