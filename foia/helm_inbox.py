"""Admiralty's /api/v1/helm-feed/inbox/ endpoint — per-user FOIA inbox.

Items where the requesting user is the gating dependency right now in
Admiralty: open FOIA requests assigned to them where action is required
to advance them toward response. Carries the statutory deadline so the
dashboard can prioritise.

Conforms to the UserInbox shape in helm.dashboard.feed_contract.
Auth + cache + sub resolution all come from keel.feed.helm_inbox_view.
"""
from django.conf import settings
from keel.feed.views import helm_inbox_view

from .helm_feed import _product_url
from .models import FOIARequest


# Statuses where the assignee owes the next material action. Senior
# review and responded/closed/appealed are excluded — they belong to a
# different actor or no one (resolved).
_AWAITING_ME_STATUSES = (
    FOIARequest.Status.RECEIVED,
    FOIARequest.Status.SCOPE_DEFINED,
    FOIARequest.Status.SEARCHING,
    FOIARequest.Status.UNDER_REVIEW,
    FOIARequest.Status.PACKAGE_READY,
)


@helm_inbox_view
def admiralty_helm_feed_inbox(request, user):
    from core.models import Notification

    base_url = _product_url().rstrip('/')
    items = []

    qs = (
        FOIARequest.objects
        .filter(assigned_to=user, status__in=_AWAITING_ME_STATUSES)
        .order_by('statutory_deadline', '-date_received')
    )
    for foia in qs:
        title = f'FOIA #{foia.request_number} — {foia.subject[:60]}'
        items.append({
            'id': str(foia.id),
            'type': 'response',
            'title': title,
            'deep_link': f'{base_url}/foia/{foia.id}/',
            'waiting_since': foia.updated_at.isoformat() if hasattr(foia, 'updated_at') and foia.updated_at else '',
            'due_date': foia.statutory_deadline.isoformat() if foia.statutory_deadline else None,
            'priority': (foia.priority or 'normal').lower(),
        })

    unread = (
        Notification.objects
        .filter(recipient=user, is_read=False)
        .order_by('-created_at')[:50]
    )
    notifications = []
    for n in unread:
        link = n.link or ''
        if link and base_url and link.startswith('/'):
            link = f'{base_url}{link}'
        notifications.append({
            'id': str(n.id),
            'title': n.title,
            'body': getattr(n, 'message', '') or '',
            'deep_link': link,
            'created_at': n.created_at.isoformat(),
            'priority': (n.priority or 'normal').lower(),
        })

    return {
        'product': getattr(settings, 'KEEL_PRODUCT_CODE', 'admiralty'),
        'product_label': getattr(settings, 'KEEL_PRODUCT_NAME', 'Admiralty'),
        'product_url': base_url,
        'user_sub': '',  # filled by decorator
        'items': items,
        'unread_notifications': notifications,
        'fetched_at': '',  # filled by decorator
    }
