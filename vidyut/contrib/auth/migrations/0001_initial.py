"""
Initial migration for vidyut.contrib.auth

Creates the vidyut_users table for the built-in User model.
"""

from vidyut.migrations import Migration, operations as op


class InitialAuthMigration(Migration):
    """
    Initial migration for vidyut.contrib.auth.
    
    Creates the vidyut_users table with all fields from AbstractUser.
    """
    
    # Mark as internal migration (not user-visible in makemigrations)
    internal = True
    app_label = "vidyut.contrib.auth"
    
    dependencies = []
    
    operations = [
        op.CreateTable(
            name="vidyut_users",
            fields=[
                ("id", op.IntegerField(primary_key=True, auto_increment=True)),
                ("email", op.StringField(max_length=255, unique=True, nullable=False)),
                ("hashed_password", op.StringField(max_length=255, nullable=False)),
                ("is_active", op.BooleanField(default=True)),
                ("is_staff", op.BooleanField(default=False)),
                ("is_superuser", op.BooleanField(default=False)),
                ("metadata", op.JSONField(nullable=True)),
                ("created_at", op.TimestampField(auto_now_add=True)),
                ("updated_at", op.TimestampField(auto_now=True)),
            ],
        ),
        op.CreateIndex(
            table_name="vidyut_users",
            index_name="idx_vidyut_users_email",
            columns=["email"],
        ),
        op.CreateIndex(
            table_name="vidyut_users",
            index_name="idx_vidyut_users_is_active",
            columns=["is_active"],
        ),
    ]


# Export the migration class for discovery
Migration = InitialAuthMigration
