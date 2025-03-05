from rest_framework import permissions

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Admins can do anything; users can only read.
    """
    def has_permission(self, request, view):
        if request.user.is_authenticated:
            return request.user.is_staff or request.method in permissions.SAFE_METHODS
        return False

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow owners of an object or admins to edit or delete it.
    """
    def has_object_permission(self, request, view, obj):
        # Allow safe methods (GET, OPTIONS, HEAD) for anyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # Allow the owner or an admin to perform the action
        return obj.author == request.user or request.user.is_staff