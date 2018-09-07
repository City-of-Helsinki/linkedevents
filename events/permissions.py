from .models import PublicationStatus


class UserModelPermissionMixin:
    """Permission mixin for user models

    A mixin class that provides permission check methods
    for user models.
    """
    def is_admin(self, publisher):
        """Check if current user is an admin user of the publisher organization"""
        raise NotImplementedError()

    def is_regular_user(self, publisher):
        """Check if current user is a regular user of the publisher organization"""
        raise NotImplementedError()

    def can_edit_event(self, publisher, publication_status):
        """Check if current user can edit (create, change, modify)
        event with the given publisher and publication_status"""
        if self.is_admin(publisher):
            return True
        if self.is_regular_user(publisher) and publication_status == PublicationStatus.DRAFT:
            return True
        return False

    def get_editable_events(self, publisher, queryset):
        """Get eidtable events queryset from given queryset for current user"""
        if self.is_admin(publisher):
            return queryset
        if self.is_regular_user(publisher):
            return queryset.filter(publication_status=PublicationStatus.DRAFT)
        return queryset.none()
