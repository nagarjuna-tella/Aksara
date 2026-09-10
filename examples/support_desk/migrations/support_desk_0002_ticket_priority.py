"""Add explicit ticket priority as an upgrade migration."""

from typing import ClassVar

from aksara.migrations import Migration
from aksara.migrations import operations as op


class Migration(Migration):
    dependencies: ClassVar = [("support_desk", "support_desk_0001_initial")]

    operations: ClassVar = [
        op.AddField(
            table="support_tickets",
            name="priority",
            field=op.StringField(20, default="normal"),
        ),
    ]
