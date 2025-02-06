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
    Users can only edit/delete their own posts/comments. Admins can do anything.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated:
            return request.user.is_staff or obj.author == request.user  # Users can only modify their own posts/comments
        return False