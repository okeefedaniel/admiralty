#!/usr/bin/env python
"""Railway startup script — run migrations, configure site, collectstatic, then gunicorn."""
import os
import subprocess
import sys

os.environ['PYTHONUNBUFFERED'] = '1'


def log(msg):
    print(f"[startup] {msg}", flush=True)


def run(cmd, fatal=False):
    log(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, stdout=sys.stdout, stderr=sys.stderr)  # nosec B602 — internal boot script with hardcoded commands, no user input
    if result.returncode != 0:
        log(f"Command exited with code {result.returncode}: {cmd}")
        if fatal:
            sys.exit(result.returncode)
        return False
    return True


def main():
    log("=" * 50)
    log("Admiralty — FOIA Request Management")
    log("Container starting")
    log("=" * 50)

    port = os.environ.get('PORT', '8080')
    manage = f"{sys.executable} manage.py"

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'admiralty_site.settings')
    import django
    django.setup()

    log("=== Running migrations ===")
    # If admin.0001_initial was applied before keel_accounts.0001_initial (i.e. the
    # project switched AUTH_USER_MODEL to KeelUser after initial deploy), Django raises
    # InconsistentMigrationHistory.  Fix: apply keel_accounts first, bypassing the
    # history check that would otherwise block it.
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM django_migrations WHERE app='admin' AND name='0001_initial'"
        )
        admin_applied = cursor.fetchone()
        cursor.execute(
            "SELECT 1 FROM django_migrations WHERE app='keel_accounts' AND name='0001_initial'"
        )
        keel_applied = cursor.fetchone()
    if admin_applied and not keel_applied:
        log("  Fixing migration order: applying keel_accounts migrations first")
        from django.core.management import call_command
        from django.db.migrations.loader import MigrationLoader
        _orig_check = MigrationLoader.check_consistent_history
        MigrationLoader.check_consistent_history = lambda self, conn: None
        try:
            call_command('migrate', 'keel_accounts', verbosity=1, no_input=True)
        finally:
            MigrationLoader.check_consistent_history = _orig_check

    run(f"{manage} migrate --noinput", fatal=True)

    # Ensure django.contrib.sites has the correct Site record (required by allauth)
    log("=== Configuring Site object ===")
    try:
        from django.contrib.sites.models import Site
        domain = os.environ.get('SITE_DOMAIN', 'admiralty.docklabs.ai')
        site, created = Site.objects.update_or_create(
            id=1, defaults={'domain': domain, 'name': 'Admiralty'},
        )
        log(f"  Site {'created' if created else 'updated'}: {site.domain}")
    except Exception as e:
        log(f"  WARNING: Could not configure Site: {e}")

    log("=== Collecting static files ===")
    run(f"{manage} collectstatic --noinput")

    if os.environ.get('DEMO_MODE', '').lower() in ('true', '1', 'yes'):
        log("=== Seeding demo users ===")
        run(f"{manage} seed_keel_users")
        run(f"{manage} seed_demo_admiralty")
        log("=== Seeding demo FOIA data ===")
        run(f"{manage} seed_admiralty_demo")

    log(f"=== Starting gunicorn on port {port} ===")
    os.execvp("gunicorn", [
        "gunicorn", "admiralty_site.wsgi",
        "--bind", f"0.0.0.0:{port}",
        "--workers", "2",
        "--access-logfile", "-",
        "--error-logfile", "-",
        "--timeout", "120",
    ])


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)
