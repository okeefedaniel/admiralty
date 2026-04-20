"""Seed demo FOIA domain data for Admiralty dashboards.

Creates a handful of FOIARequest rows across statuses so demo-admiralty
dashboards render non-zero numbers. Idempotent — skips if >=3 requests
already exist.
"""
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from foia.models import FOIARequest


DEMO_REQUESTS = [
    {
        'request_number': 'DEMO-2026-001',
        'status': FOIARequest.Status.UNDER_REVIEW,
        'priority': FOIARequest.Priority.HIGH,
        'requester_name': 'Alex Reporter',
        'requester_email': 'alex@ctnews.demo',
        'requester_organization': 'CT News',
        'subject': 'Records of procurement contracts 2025',
        'description': 'All contracts awarded over $100K in FY2025.',
    },
    {
        'request_number': 'DEMO-2026-002',
        'status': FOIARequest.Status.SEARCHING,
        'priority': FOIARequest.Priority.NORMAL,
        'requester_name': 'Jamie Citizen',
        'requester_email': 'jamie@citizens.demo',
        'requester_organization': '',
        'subject': 'Correspondence with Department of Labor',
        'description': 'Emails between DECD leadership and DOL from Q1 2026.',
    },
    {
        'request_number': 'DEMO-2026-003',
        'status': FOIARequest.Status.RESPONDED,
        'priority': FOIARequest.Priority.NORMAL,
        'requester_name': 'Pat Researcher',
        'requester_email': 'pat@uconn.demo',
        'requester_organization': 'UConn',
        'subject': 'Grant program outcomes 2024',
        'description': 'Outcome data for Small Business Express grants.',
    },
    {
        'request_number': 'DEMO-2026-004',
        'status': FOIARequest.Status.PACKAGE_READY,
        'priority': FOIARequest.Priority.URGENT,
        'requester_name': 'Robin Advocate',
        'requester_email': 'robin@advocate.demo',
        'requester_organization': 'CT Transparency Project',
        'subject': 'Executive travel expenses',
        'description': 'Travel expense reports for agency directors.',
    },
    {
        'request_number': 'DEMO-2026-005',
        'status': FOIARequest.Status.RECEIVED,
        'priority': FOIARequest.Priority.LOW,
        'requester_name': 'Sam Student',
        'requester_email': 'sam@school.demo',
        'requester_organization': 'Yale Law',
        'subject': 'Historical meeting minutes',
        'description': 'Board meeting minutes from 2020-2022.',
    },
]


class Command(BaseCommand):
    help = 'Seed demo FOIA requests for Admiralty dashboard demos.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        if not getattr(settings, 'DEMO_MODE', False) and not options['force']:
            self.stdout.write(self.style.WARNING(
                'DEMO_MODE is not enabled. Use --force to override.'
            ))
            return

        existing = FOIARequest.objects.count()
        if existing >= len(DEMO_REQUESTS):
            self.stdout.write(
                f'Admiralty already has {existing} FOIA requests; skipping.'
            )
            return

        User = get_user_model()
        created_by = User.objects.filter(username='foia_officer').first() \
            or User.objects.filter(is_superuser=True).first()

        today = date.today()
        for i, req in enumerate(DEMO_REQUESTS):
            received = today - timedelta(days=14 - i * 2)
            FOIARequest.objects.update_or_create(
                request_number=req['request_number'],
                defaults={
                    **req,
                    'date_received': received,
                    'statutory_deadline': received + timedelta(days=4),
                    'original_request_text': req['description'],
                    'created_by': created_by,
                    'assigned_to': created_by,
                },
            )
            self.stdout.write(self.style.SUCCESS(
                f'  Seeded: {req["request_number"]} ({req["status"]})'
            ))
