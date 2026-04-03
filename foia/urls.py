from django.urls import path
from . import views

app_name = 'foia'

urlpatterns = [
    # Dashboard & lists
    path('', views.FOIARequestListView.as_view(), name='request_list'),
    path('dashboard/', views.FOIADashboardView.as_view(), name='dashboard'),
    path('review/', views.FOIAReviewQueueView.as_view(), name='review_queue'),

    # Statutory exemptions management
    path('exemptions/', views.FOIAExemptionListView.as_view(), name='exemption_list'),
    path('exemptions/<uuid:pk>/edit/', views.FOIAExemptionUpdateView.as_view(), name='exemption_edit'),

    # Document repository
    path('documents/', views.FOIADocumentListView.as_view(), name='document_list'),
    path('documents/upload/', views.FOIADocumentCreateView.as_view(), name='document_upload'),
    path('documents/bulk-upload/', views.FOIADocumentBulkUploadView.as_view(), name='document_bulk_upload'),
    path('documents/<uuid:pk>/', views.FOIADocumentDetailView.as_view(), name='document_detail'),
    path('documents/<uuid:pk>/edit/', views.FOIADocumentUpdateView.as_view(), name='document_edit'),

    # Request CRUD
    path('create/', views.FOIARequestCreateView.as_view(), name='request_create'),
    path('<uuid:pk>/', views.FOIARequestDetailView.as_view(), name='request_detail'),
    path('<uuid:pk>/edit/', views.FOIARequestUpdateView.as_view(), name='request_edit'),

    # Workflow
    path('<uuid:pk>/transition/', views.FOIATransitionView.as_view(), name='transition'),
    path('<uuid:pk>/scope/', views.FOIAScopeView.as_view(), name='scope'),
    path('<uuid:pk>/search/', views.FOIARunSearchView.as_view(), name='run_search'),
    path('<uuid:pk>/results/', views.FOIASearchResultsView.as_view(), name='search_results'),
    path('<uuid:pk>/results/<uuid:result_pk>/determine/', views.FOIADeterminationView.as_view(), name='determination'),
    path('<uuid:pk>/results/ai-review/', views.FOIAAIReviewView.as_view(), name='ai_review'),
    path('<uuid:pk>/compile/', views.FOIACompileResponseView.as_view(), name='compile_response'),

    # Appeals
    path('<uuid:pk>/appeal/', views.FOIAAppealCreateView.as_view(), name='appeal_create'),
    path('appeal/<uuid:pk>/edit/', views.FOIAAppealUpdateView.as_view(), name='appeal_edit'),
]
