"""Compatibility layer for FOIA app dual-mode operation.

Detects whether the FOIA app is running inside Beacon CRM or as
standalone Admiralty, and provides appropriate fallbacks for:
- Permission checking
- Audit logging
- User queries
- Template resolution
"""
import logging

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

logger = logging.getLogger(__name__)


def is_beacon():
    """Return True if running inside Beacon CRM (not standalone Admiralty).

    We check for the 'core' app *label* (not module name). In Beacon CRM the
    core app has label='core'; in standalone Admiralty the same Python module
    is registered with label='admiralty_core' via AdmiraltyConfig.
    """
    try:
        cfg = apps.get_app_config('core')
        # Only Beacon's core app has label == name == 'core'
        return cfg.name == 'core' and cfg.label == 'core'
    except LookupError:
        return False


# ---------------------------------------------------------------------------
# Permission Mixins
# ---------------------------------------------------------------------------

# FOIA-relevant role allowlist used by the standalone-mode permission
# fallbacks. Includes the customer-side ``agency_admin`` so a customer
# admin can manage FOIA without holding Django ``is_staff`` (which would
# also grant /admin/ access — an IT-only surface). ``is_staff`` remains
# accepted as a fallback for legacy demo accounts.
_FOIA_STAFF_ROLES = frozenset({
    'system_admin', 'admin', 'agency_admin',
    'foia_manager', 'foia_officer', 'foia_attorney',
})


def _user_has_foia_role(user):
    role = getattr(user, 'role', None)
    return bool(role and role in _FOIA_STAFF_ROLES)


class _StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Standalone fallback: FOIA staff role OR Django is_staff grants access."""

    def test_func(self):
        user = self.request.user
        return _user_has_foia_role(user) or user.is_staff


def get_foia_staff_mixin():
    """Return the appropriate FOIA staff permission mixin."""
    if is_beacon():
        from core.mixins import FOIAStaffRequiredMixin
        return FOIAStaffRequiredMixin
    return _StaffRequiredMixin


def get_foia_manager_mixin():
    """Return the appropriate FOIA manager permission mixin."""
    if is_beacon():
        from core.mixins import FOIAManagerRequiredMixin
        return FOIAManagerRequiredMixin
    return _StaffRequiredMixin


# ---------------------------------------------------------------------------
# Audit Logging
# ---------------------------------------------------------------------------

def log_audit(user, action, entity_type, entity_id, description='',
              changes=None, ip_address=None):
    """Log an audit event — delegates to Beacon's AuditLog or Python logging."""
    if is_beacon():
        from core.audit import log_audit as _beacon_log_audit
        _beacon_log_audit(user, action, entity_type, entity_id,
                          description, changes, ip_address)
    else:
        logger.info(
            'AUDIT: user=%s action=%s entity=%s/%s desc=%s',
            user, action, entity_type, entity_id, description,
        )


# ---------------------------------------------------------------------------
# User Queries
# ---------------------------------------------------------------------------

def get_assignable_users():
    """Return users who can be assigned FOIA requests."""
    User = get_user_model()
    if is_beacon():
        return User.objects.filter(
            role__in=[
                'foia_officer', 'foia_attorney',
                'agency_admin', 'system_admin',
            ],
            is_active=True,
        )
    # Standalone: include role-bearing FOIA users via ProductAccess
    # (covers agency_admin / foia_manager / foia_officer / foia_attorney
    # who don't carry Django is_staff). Falls back to is_staff users so
    # legacy demo accounts remain assignable.
    from django.db.models import Q
    return User.objects.filter(
        Q(is_active=True)
        & (
            Q(is_staff=True)
            | Q(
                product_access__product='admiralty',
                product_access__role__in=list(_FOIA_STAFF_ROLES),
                product_access__is_active=True,
            )
        )
    ).distinct()


def user_is_foia_staff(user):
    """Check if a user has FOIA staff permissions."""
    if is_beacon():
        return getattr(user, 'is_foia_staff', False)
    return _user_has_foia_role(user) or user.is_staff


def user_can_manage_foia(user):
    """Check if a user can manage FOIA requests."""
    if is_beacon():
        return getattr(user, 'can_manage_foia', False)
    return _user_has_foia_role(user) or user.is_staff


# ---------------------------------------------------------------------------
# Template & Branding
# ---------------------------------------------------------------------------

def get_base_template():
    """Return the base template path for FOIA templates."""
    if is_beacon():
        return 'base.html'
    return 'admiralty/base.html'


def get_dashboard_url():
    """Return the URL name for the main dashboard."""
    if is_beacon():
        return 'dashboard'
    return 'dashboard_alias'


def get_brand():
    """Return the product brand name."""
    if is_beacon():
        return 'Beacon'
    return 'Admiralty'
