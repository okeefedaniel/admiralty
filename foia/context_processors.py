"""FOIA context processors — inject template switching variables."""
from django.conf import settings as django_settings
from django.utils import timezone

from foia.compat import is_beacon, get_base_template, get_dashboard_url, get_brand


def foia_context(request):
    """Inject FOIA-aware template variables into every template context."""
    ctx = {
        'foia_base_template': get_base_template(),
        'foia_dashboard_url': get_dashboard_url(),
        'foia_brand': get_brand(),
        'foia_is_beacon': is_beacon(),
        'CURRENT_YEAR': timezone.now().year,
        'DEMO_MODE': getattr(django_settings, 'DEMO_MODE', False),
    }

    return ctx
