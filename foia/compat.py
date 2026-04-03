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
    """Return True if running inside Beacon CRM (core app installed)."""
    return apps.is_installed('core')


# ---------------------------------------------------------------------------
# Permission Mixins
# ---------------------------------------------------------------------------

class _StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Standalone fallback: any staff user can access FOIA views."""

    def test_func(self):
        return self.request.user.is_staff


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
    return User.objects.filter(is_staff=True, is_active=True)


def user_is_foia_staff(user):
    """Check if a user has FOIA staff permissions."""
    if is_beacon():
        return getattr(user, 'is_foia_staff', False)
    return user.is_staff


def user_can_manage_foia(user):
    """Check if a user can manage FOIA requests."""
    if is_beacon():
        return getattr(user, 'can_manage_foia', False)
    return user.is_staff


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
    return 'foia:dashboard'


def get_brand():
    """Return the product brand name."""
    if is_beacon():
        return 'Beacon'
    return 'Admiralty'
