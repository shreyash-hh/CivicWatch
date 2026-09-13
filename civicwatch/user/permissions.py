from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

# ================= PREDICATE HELPERS =================

def is_verified_worker_or_admin(user):
    """Returns True if the user is authenticated and is a superuser or verified worker/admin."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return getattr(user, 'role', None) in ['admin', 'volunteer', 'organization'] and getattr(user, 'is_verified', False)

def is_reporter(user, violation):
    """Returns True if user is the author of the reported violation."""
    if not user or not user.is_authenticated or not violation:
        return False
    return violation.reported_by_id == user.id

def is_assigned_worker(user, violation):
    """Returns True if user is the assigned worker for the adopted violation."""
    if not user or not user.is_authenticated or not violation:
        return False
    return violation.adopted_by_id == user.id

def can_adopt_violation(user, violation):
    """
    Checks if a user can adopt a violation:
    1. Must be a verified worker or admin.
    2. Issue must be in PENDING status.
    3. Self-dealing prevention: Reporter cannot adopt their own issue.
    """
    if not is_verified_worker_or_admin(user):
        return False
    if violation.status != 'Pending':
        return False
    if is_reporter(user, violation):
        return False
    return True

def can_submit_proof(user, violation):
    """
    Checks if a user can submit proof of work:
    1. Must be the assigned worker.
    2. Status must be ADOPTED or PENDING_VERIFICATION.
    3. Self-dealing prevention: Assigned worker cannot be the reporter.
    """
    if not is_assigned_worker(user, violation):
        return False
    if violation.status not in ['Adopted', 'Pending Verification']:
        return False
    if is_reporter(user, violation):
        return False
    return True

def can_verify_resolution(user, violation):
    """
    Checks if a user can verify resolution:
    1. Must be the original reporter OR an independent admin/superuser.
    2. Status must be PENDING_VERIFICATION.
    3. Self-dealing prevention: Assigned worker cannot verify their own work.
    """
    if not user or not user.is_authenticated:
        return False
    if violation.status != 'Pending Verification':
        return False
    
    # Assigned worker cannot verify their own work
    if is_assigned_worker(user, violation):
        return False

    is_admin = user.is_superuser or (getattr(user, 'role', None) == 'admin' and getattr(user, 'is_verified', False))
    return is_reporter(user, violation) or is_admin

# ================= DECORATORS =================

def role_required(roles, require_verified=True, redirect_url='violation_list'):
    """
    Decorator requiring the user to have one of the specified roles.
    If require_verified is True, volunteer/organization/admin accounts must be verified.
    """
    if isinstance(roles, str):
        roles = [roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "Please log in to perform this action.")
                return redirect('login')

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            user_role = getattr(request.user, 'role', None)
            is_verified = getattr(request.user, 'is_verified', False)

            if user_role not in roles:
                messages.error(request, "You do not have permission to access this resource.")
                return redirect(redirect_url)

            if require_verified and not is_verified and user_role != 'citizen':
                messages.warning(request, "Your account is currently pending verification by an administrator.")
                return redirect('profile')

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def verified_worker_required(view_func):
    """Decorator requiring a verified worker (volunteer/org) or admin/superuser."""
    return role_required(['admin', 'volunteer', 'organization'], require_verified=True)(view_func)

def admin_required(view_func):
    """Decorator requiring admin role or superuser status."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access this page.")
            return redirect('login')
        if request.user.is_superuser or (getattr(request.user, 'role', None) == 'admin' and getattr(request.user, 'is_verified', False)):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Administrator privileges required.")
        return redirect('violation_list')
    return _wrapped_view

# ================= CBV MIXINS =================

class RoleRequiredMixin:
    allowed_roles = []
    require_verified = True
    redirect_url = 'violation_list'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        user_role = getattr(request.user, 'role', None)
        is_verified = getattr(request.user, 'is_verified', False)
        if user_role not in self.allowed_roles:
            messages.error(request, "Permission denied.")
            return redirect(self.redirect_url)
        if self.require_verified and not is_verified and user_role != 'citizen':
            messages.warning(request, "Account verification required.")
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

class VerifiedWorkerRequiredMixin(RoleRequiredMixin):
    allowed_roles = ['admin', 'volunteer', 'organization']
    require_verified = True
