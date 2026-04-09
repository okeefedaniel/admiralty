"""Admiralty's /api/v1/helm-feed/ endpoint.

Exposes FOIA request metrics for Helm's executive dashboard.
"""
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from keel.feed.views import helm_feed_view


def _product_url():
    if getattr(settings, 'DEMO_MODE', False):
        return 'https://demo-admiralty.docklabs.ai'
    return 'https://admiralty.docklabs.ai'


@helm_feed_view
def admiralty_helm_feed(request):
    from foia.models import FOIARequest

    now = timezone.now()
    base_url = _product_url()

    # ── Metrics ──────────────────────────────────────────────────
    open_statuses = [
        'received', 'scope_defined', 'searching',
        'under_review', 'package_ready', 'senior_review',
    ]
    open_requests = FOIARequest.objects.filter(
        status__in=open_statuses,
    ).count()

    overdue_count = FOIARequest.objects.filter(
        status__in=open_statuses,
        statutory_deadline__lt=now.date(),
    ).count()

    # Average response time for completed requests (last 90 days)
    from django.db.models import Avg, F, ExpressionWrapper, DurationField
    responded_recently = FOIARequest.objects.filter(
        status__in=['responded', 'closed'],
        date_responded__isnull=False,
        date_responded__gte=now.date() - __import__('datetime').timedelta(days=90),
    )
    avg_days = None
    if responded_recently.exists():
        from django.db.models.functions import Cast
        avg_result = responded_recently.aggregate(
            avg_days=Avg(
                ExpressionWrapper(
                    F('date_responded') - F('date_received'),
                    output_field=DurationField(),
                )
            )
        )
        if avg_result['avg_days']:
            avg_days = round(avg_result['avg_days'].days, 1)

    appealed_count = FOIARequest.objects.filter(status='appealed').count()

    metrics = [
        {
            'key': 'open_requests',
            'label': 'Open Requests',
            'value': open_requests,
            'unit': None,
            'trend': None, 'trend_value': None, 'trend_period': None,
            'severity': 'normal',
            'deep_link': f'{base_url}/foia/',
        },
        {
            'key': 'avg_response_time',
            'label': 'Avg Response',
            'value': avg_days if avg_days is not None else 0,
            'unit': 'days',
            'trend': None, 'trend_value': None, 'trend_period': None,
            'severity': 'normal',
            'deep_link': f'{base_url}/foia/',
        },
        {
            'key': 'overdue_requests',
            'label': 'Overdue',
            'value': overdue_count,
            'unit': None,
            'trend': None, 'trend_value': None, 'trend_period': None,
            'severity': 'warning' if overdue_count > 0 else 'normal',
            'deep_link': f'{base_url}/foia/?overdue=true',
        },
    ]

    if appealed_count > 0:
        metrics.append({
            'key': 'appeals',
            'label': 'Appeals',
            'value': appealed_count,
            'unit': None,
            'trend': None, 'trend_value': None, 'trend_period': None,
            'severity': 'warning',
            'deep_link': f'{base_url}/foia/?status=appealed',
        })

    # ── Action Items ─────────────────────────────────────────────
    action_items = []

    # Requests approaching deadline
    approaching_deadline = FOIARequest.objects.filter(
        status__in=open_statuses,
        statutory_deadline__isnull=False,
        statutory_deadline__gte=now.date(),
        statutory_deadline__lte=now.date() + __import__('datetime').timedelta(days=3),
    ).order_by('statutory_deadline')[:5]

    for req in approaching_deadline:
        action_items.append({
            'id': f'admiralty-deadline-{req.pk}',
            'type': 'response',
            'title': f'Respond: FOIA #{req.pk} — deadline {req.statutory_deadline.strftime("%b %d")}',
            'description': f'Status: {req.get_status_display()}',
            'priority': 'high',
            'due_date': req.statutory_deadline.isoformat(),
            'assigned_to_role': 'foia_officer',
            'deep_link': f'{base_url}/foia/{req.pk}/',
            'created_at': req.created_at.isoformat() if req.created_at else '',
        })

    # Requests pending senior review
    senior_review = FOIARequest.objects.filter(
        status='senior_review',
    ).order_by('statutory_deadline')[:3]
    for req in senior_review:
        action_items.append({
            'id': f'admiralty-senior-{req.pk}',
            'type': 'review',
            'title': f'Senior review: FOIA #{req.pk}',
            'description': f'Package ready for senior approval',
            'priority': 'medium',
            'due_date': req.statutory_deadline.isoformat() if req.statutory_deadline else '',
            'assigned_to_role': 'foia_officer',
            'deep_link': f'{base_url}/foia/{req.pk}/',
            'created_at': '',
        })

    # ── Alerts ───────────────────────────────────────────────────
    alerts = []
    if overdue_count > 0:
        alerts.append({
            'id': 'admiralty-overdue',
            'type': 'overdue',
            'title': f'{overdue_count} FOIA request{"s" if overdue_count != 1 else ""} past statutory deadline',
            'severity': 'critical',
            'since': '',
            'deep_link': f'{base_url}/foia/?overdue=true',
        })

    return {
        'product': 'admiralty',
        'product_label': 'Admiralty',
        'product_url': f'{base_url}/dashboard/',
        'metrics': metrics,
        'action_items': action_items,
        'alerts': alerts,
        'sparklines': {},
    }
