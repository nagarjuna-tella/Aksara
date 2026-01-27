"""
Initial migration for aksara.contrib.auth

Creates the aksara_users table for the built-in User model.
"""

from aksara.migrations import Migration, operations as op


class InitialAuthMigration(Migration):
    """
    Initial migration for aksara.contrib.auth.
    
    Creates the aksara_users table with all fields from AbstractUser.
    """
    
    # Mark as internal migration (not user-visible in makemigrations)
    internal = True
    app_label = "aksara.contrib.auth"
    
    dependencies = []
    
    operations = [
        op.CreateTable(
            name="aksara_users",
            fields=[
                ("id", op.UUIDField(primary_key=True)),
                ("email", op.StringField(max_length=255, unique=True, nullable=False)),
                ("hashed_password", op.StringField(max_length=255, nullable=False)),
                ("is_active", op.BooleanField(default=True)),
                ("is_staff", op.BooleanField(default=False)),
                ("is_superuser", op.BooleanField(default=False)),
                ("metadata", op.JSONField(nullable=True)),
                ("created_at", op.DateTimeField(auto_now_add=True)),
                ("updated_at", op.DateTimeField(auto_now_add=True)),
            ],
            indexes=[
                op.IndexOp(
                    name="idx_aksara_users_email",
                    table="aksara_users",
                    columns=["email"],
                ),
                op.IndexOp(
                    name="idx_aksara_users_is_active",
                    table="aksara_users",
                    columns=["is_active"],
                ),
            ],
        ),
    ]


# Export the migration class for discovery
Migration = InitialAuthMigration
