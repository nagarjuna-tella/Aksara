"""
Soft Delete Mixin

Provides logical (soft) deletion for models.

Instead of permanently deleting records, soft deletes mark records with a
deleted_at timestamp. Queries automatically exclude soft-deleted records
unless explicitly requested.

v0.5.39: Initial implementation.

Usage:
    from aksara import Model, fields
    from aksara.contrib.soft_delete import SoftDeleteModel
    
    class User(SoftDeleteModel):
        email = fields.String(unique=True)
        name = fields.String()
    
    # Soft delete - sets deleted_at timestamp
    user = await User.objects.get(id=user_id)
    await user.delete()  # Sets deleted_at, doesn't remove record
    
    # Query excludes soft-deleted by default
    users = await User.objects.all()  # Only returns non-deleted
    
    # Include soft-deleted records
    from aksara.contrib.soft_delete import with_deleted
    all_users = await with_deleted(User.objects.all())
    
    # Restore a soft-deleted record
    user = await User.objects_with_deleted.get(id=user_id)
    await user.undelete()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aksara.model.base import Model


class SoftDeleteModel:
    """
    Mixin to add soft delete (logical deletion) support to models.
    
    Adds a deleted_at field and modifies delete() to set this field
    instead of removing the record. All queries automatically exclude
    soft-deleted records.
    
    To use, inherit from both Model and SoftDeleteModel:
        class User(Model, SoftDeleteModel):
            email = fields.String()
    
    Or simply inherit from SoftDeleteModel (which inherits from Model):
        class User(SoftDeleteModel):
            email = fields.String()
    """
    
    # This will be filled in by the model's __init_subclass__
    _soft_delete_field_added = False
    
    async def delete(self) -> None:
        """
        Soft delete this model instance.
        
        Sets the deleted_at timestamp instead of deleting the record.
        Fires pre_delete signal before marking as deleted.
        Fires post_delete signal after marking as deleted.
        """
        from aksara.db import Database
        from aksara.signals import pre_delete, post_delete
        
        if self._is_new:
            raise ValueError("Cannot delete a model that hasn't been saved yet")
        
        # Fire pre_delete signal
        await pre_delete.send(sender=self.__class__, instance=self)
        
        db = Database.get_instance()
        
        # Set deleted_at timestamp
        self._data['deleted_at'] = datetime.now(timezone.utc)
        
        # Update the record
        from aksara.db import quote_identifier
        set_clause = f'deleted_at = $1'
        table = quote_identifier(self.__tablename__)
        query = f"""
            UPDATE {table}
            SET {set_clause}
            WHERE id = $2
            RETURNING *
        """
        
        record = await db.fetchrow(
            query,
            self._data['deleted_at'],
            self._data['id'],
        )
        
        # Update instance with returned values
        if record:
            for field_name, field in self._fields.items():
                if field_name in record:
                    self._data[field_name] = field.to_python(record[field_name])
        
        # Fire post_delete signal
        await post_delete.send(sender=self.__class__, instance=self)
    
    async def undelete(self) -> None:
        """
        Restore a soft-deleted model instance.
        
        Sets deleted_at back to None, restoring the record to active status.
        """
        from aksara.db import Database
        from aksara.db import quote_identifier
        
        if self._is_new:
            raise ValueError("Cannot undelete a model that hasn't been saved yet")
        
        db = Database.get_instance()
        
        # Clear deleted_at timestamp
        self._data['deleted_at'] = None
        
        # Update the record
        set_clause = f'deleted_at = NULL'
        table = quote_identifier(self.__tablename__)
        query = f"""
            UPDATE {table}
            SET {set_clause}
            WHERE id = $1
            RETURNING *
        """
        
        record = await db.fetchrow(query, self._data['id'])
        
        # Update instance with returned values
        if record:
            for field_name, field in self._fields.items():
                if field_name in record:
                    self._data[field_name] = field.to_python(record[field_name])


def with_deleted(queryset: "QuerySet") -> "QuerySet":
    """
    Include soft-deleted records in the query.
    
    By default, queries on SoftDeleteModel exclude deleted_at IS NOT NULL.
    Use this to include soft-deleted records.
    
    Args:
        queryset: A QuerySet for a SoftDeleteModel
        
    Returns:
        The queryset without the automatic soft-delete filter
        
    Usage:
        from aksara.contrib.soft_delete import with_deleted
        
        # Only active
        active_users = await User.objects.all()
        
        # Active + deleted
        all_users = await with_deleted(User.objects.all())
    """
    # Remove the automatic soft-delete filter
    # The filter is added in Manager.filter() for SoftDeleteModel subclasses
    qs = queryset
    
    # Mark the queryset as including deleted records
    qs._include_deleted = True
    
    return qs


def only_deleted(queryset: "QuerySet") -> "QuerySet":
    """
    Query only soft-deleted records.
    
    Args:
        queryset: A QuerySet for a SoftDeleteModel
        
    Returns:
        The queryset filtered to only deleted_at IS NOT NULL
        
    Usage:
        from aksara.contrib.soft_delete import only_deleted
        
        deleted_users = await only_deleted(User.objects.all())
    """
    qs = queryset
    
    # Filter to only deleted records
    if hasattr(qs, '_deleted_only'):
        qs._deleted_only = True
    else:
        # If it's already a QuerySet, mark it
        qs._deleted_only = True
    
    return qs
