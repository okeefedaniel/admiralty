"""Admiralty — Standalone FOIA URL Configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import include, path
from django.views.generic import TemplateView, RedirectView

from keel.accounts.forms import LoginForm
from keel.core.views import health_check, favicon_view, robots_txt, LandingView, SuiteLogoutView
from keel.core.demo import demo_login_view
from keel.core.search_views import search_view
from foia.helm_feed import admiralty_helm_feed
from foia.views import FOIADashboardView

admin.site.site_header = 'Admiralty Administration'
admin.site.site_title = 'Admiralty Admin'
admin.site.index_title = 'FOIA Management'


urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('favicon.ico', favicon_view, name='favicon'),
    path('admin/', admin.site.urls),

    # Support (shared keel page — linked from 500.html)
    path('support/', TemplateView.as_view(template_name='keel/support.html'), name='support'),

    # Public landing page
    path('', LandingView.as_view(
        template_name='admiralty/home.html',
        stats=[
            {'value': '5', 'label': 'Lifecycle Stages'},
            {'value': '11', 'label': 'FOIA Exemptions'},
            {'value': 'AI', 'label': 'Pre-Classification'},
            {'value': 'Cross-product', 'label': 'Discovery'},
        ],
        features=[
            {'icon': 'bi-inbox', 'title': 'Request Intake',
             'description': 'Single intake form routes requests to the right agency with auto-classification and deadline tracking.',
             'color': 'blue'},
            {'icon': 'bi-search', 'title': 'Cross-Product Search',
             'description': 'Search for responsive records across every DockLabs product — Beacon, Harbor, Manifest, and more — from one screen.',
             'color': 'teal'},
            {'icon': 'bi-shield-check', 'title': 'Exemption Review',
             'description': 'Apply CGS §1-210 exemptions with citation tracking, AI-assisted pre-review, and full audit trails.',
             'color': 'yellow'},
        ],
        steps=[
            {'title': 'Intake', 'description': 'Requester submits a FOIA request through the public portal.'},
            {'title': 'Scope', 'description': 'FOIA officer defines the scope, custodians, and search parameters.'},
            {'title': 'Search', 'description': 'Cross-product search surfaces responsive records from every DockLabs system.'},
            {'title': 'Determine & Respond', 'description': 'Apply exemptions, package the response, and notify the requester.'},
        ],
        authenticated_redirect='foia:dashboard',
    ), name='home'),

    # Canonical suite-wide post-login URL. Mounts FOIADashboardView
    # directly so the URL bar stays at /dashboard/. The legacy
    # foia:dashboard URL still works at /foia/dashboard/.
    path('dashboard/', FOIADashboardView.as_view(), name='dashboard_alias'),

    # Demo
    path('demo/', TemplateView.as_view(template_name='admiralty/demo.html'), name='demo'),
    path('demo-login/', demo_login_view, name='demo_login'),

    # Custom login/logout views using the shared keel LoginForm so the
    # input fields render with Bootstrap styling. Mounted before the
    # allauth include so they shadow allauth's bare LoginView.
    path('accounts/login/', LoginView.as_view(
        template_name='account/login.html',
        authentication_form=LoginForm,
    ), name='account_login'),
    path('accounts/logout/', SuiteLogoutView.as_view(), name='account_logout'),
    path('accounts/', include('allauth.urls')),

    # Convenience named URL for the "Sign in with Microsoft" button
    path(
        'auth/sso/microsoft/',
        RedirectView.as_view(url='/accounts/microsoft/login/?process=login', query_string=False),
        name='microsoft_login',
    ),

    # Notifications (via Keel)
    path('notifications/', include('keel.notifications.urls')),

    # Helm executive dashboard feed
    path('api/v1/helm-feed/', admiralty_helm_feed, name='helm-feed'),

    # FOIA app
    path('foia/', include('foia.urls')),

    # Keel integrations
    path('search/', search_view, name='search'),
    path('keel/requests/', include('keel.requests.urls')),
    path('keel/', include('keel.accounts.urls')),
    path('keel/', include('keel.core.foia_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
