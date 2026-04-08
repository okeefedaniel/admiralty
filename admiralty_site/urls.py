"""Admiralty — Standalone FOIA URL Configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView, RedirectView

from allauth.account import views as allauth_views
from keel.core.views import health_check, LandingView
from keel.core.demo import demo_login_view

admin.site.site_header = 'Admiralty Administration'
admin.site.site_title = 'Admiralty Admin'
admin.site.index_title = 'FOIA Management'


urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),

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

    # Canonical suite-wide post-login URL. Every DockLabs product exposes
    # /dashboard/ so login redirects are identical across the suite. Here
    # it aliases the real FOIA dashboard at /foia/dashboard/.
    path('dashboard/', RedirectView.as_view(url='/foia/dashboard/', permanent=False), name='dashboard_alias'),

    # Demo
    path('demo/', TemplateView.as_view(template_name='admiralty/demo.html'), name='demo'),
    path('demo-login/', demo_login_view, name='demo_login'),

    # Auth
    path('auth/login/', allauth_views.LoginView.as_view(
        template_name='account/login.html',
    ), name='login'),
    path('auth/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/', include('allauth.urls')),

    # Convenience named URL for the "Sign in with Microsoft" button
    path(
        'auth/sso/microsoft/',
        RedirectView.as_view(url='/accounts/microsoft/login/?process=login', query_string=False),
        name='microsoft_login',
    ),

    # Notifications (via Keel)
    path('notifications/', include('keel.notifications.urls')),

    # FOIA app
    path('foia/', include('foia.urls')),

    # Keel integrations
    path('keel/requests/', include('keel.requests.urls')),
    path('keel/', include('keel.accounts.urls')),
    path('keel/', include('keel.core.foia_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
