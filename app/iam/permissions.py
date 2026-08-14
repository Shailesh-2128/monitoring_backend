from rest_framework.permissions import BasePermission, SAFE_METHODS

class HasModulePermission(BasePermission):
    """
    Custom permission class that checks user module-level permissions.
    Usage: permission_classes = [HasModulePermission('servers')]
    """
    message = "Permission Denied: You do not have permission to perform this action on this module."

    def __init__(self, module_name=None):
        self.module_name = module_name

    def __call__(self):
        return self

    def has_permission(self, request, view):
        module_name = self.module_name or getattr(view, 'module_name', None)
        if not module_name:
            return True

        user = request.user
        if not user or not user.is_authenticated:
            self.message = "Authentication credentials were not provided or are invalid."
            return False

        profile = getattr(user, 'profile', None)
        if user.is_superuser or (profile and profile.is_superadmin):
            return True

        from app.iam.views import get_user_permissions
        permissions_map = get_user_permissions(user)
        access_level = permissions_map.get(module_name, 'none')

        if access_level == 'none':
            self.message = f"Permission Denied: Access to '{module_name}' module is disabled for your role/team."
            return False

        if request.method in SAFE_METHODS:
            if access_level in ['read', 'write']:
                return True
            self.message = f"Permission Denied: You do not have read permission for '{module_name}' module."
            return False
        else:
            if access_level == 'write':
                return True
            self.message = f"Permission Denied: You have Read-Only access for '{module_name}' module and cannot create or modify resources."
            return False

def module_permission(module_name):
    """Factory helper to return an instance of HasModulePermission with a specific module."""
    class ModulePermissionClass(HasModulePermission):
        def __init__(self):
            super().__init__(module_name=module_name)
    return ModulePermissionClass
