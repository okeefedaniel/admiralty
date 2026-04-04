"""Create demo user accounts for Admiralty (standalone FOIA)."""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD', 'demo2026!')

DEMO_USERS = [
    # (username, email, first, last, is_staff, is_superuser)
    ('admin', 'admin@admiralty.demo', 'System', 'Admin', True, True),
    ('foia_officer', 'foia.officer@admiralty.demo', 'Frank', 'Officer', True, False),
    ('foia_attorney', 'foia.attorney@admiralty.demo', 'Amy', 'Attorney', True, False),
]


class Command(BaseCommand):
    help = 'Create demo user accounts for Admiralty (standalone FOIA)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Run even if DEMO_MODE is not enabled',
        )

    def handle(self, *args, **options):
        if not getattr(settings, 'DEMO_MODE', False) and not options['force']:
            self.stdout.write(self.style.WARNING(
                'DEMO_MODE is not enabled. Use --force to override.'
            ))
            return

        User = get_user_model()
        for username, email, first, last, is_staff, is_superuser in DEMO_USERS:
            if User.objects.filter(username=username).exists():
                user = User.objects.get(username=username)
                user.set_password(DEMO_PASSWORD)
                user.save()
                self.stdout.write(f'  User {username}: exists (password reset)')
                continue

            User.objects.create_user(
                username=username,
                email=email,
                password=DEMO_PASSWORD,
                first_name=first,
                last_name=last,
                is_staff=is_staff,
                is_superuser=is_superuser,
            )
            self.stdout.write(self.style.SUCCESS(f'  User {username}: created'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Demo accounts ready. Password for all: [set via DEMO_PASSWORD env var]'))
        self.stdout.write('')
        self.stdout.write('Accounts:')
        for username, _, first, last, _, _ in DEMO_USERS:
            self.stdout.write(f'  {username:20s} {first} {last}')
