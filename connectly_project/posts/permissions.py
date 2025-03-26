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
        if request.method in permissions.SAFE_METHODS:
            return True
        return hasattr(obj, "author") and obj.author == request.user or request.user.is_staff