from django.contrib import admin

from .models import (
    FOIAAppeal,
    FOIADetermination,
    FOIADocument,
    FOIARequest,
    FOIAResponsePackage,
    FOIAScope,
    FOIASearchResult,
    StatutoryExemption,
)


@admin.register(StatutoryExemption)
class StatutoryExemptionAdmin(admin.ModelAdmin):
    list_display = ('subdivision', 'label', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('subdivision', 'label', 'statutory_text')


class FOIAScopeInline(admin.StackedInline):
    model = FOIAScope
    extra = 0


@admin.register(FOIARequest)
class FOIARequestAdmin(admin.ModelAdmin):
    list_display = (
        'request_number', 'subject', 'status', 'priority',
        'requester_name', 'date_received', 'statutory_deadline', 'assigned_to',
    )
    list_filter = ('status', 'priority')
    search_fields = ('request_number', 'subject', 'requester_name', 'requester_organization')
    raw_id_fields = ('assigned_to', 'reviewing_attorney', 'created_by')
    date_hierarchy = 'date_received'
    inlines = [FOIAScopeInline]

    def get_list_display(self, request):
        fields = list(super().get_list_display(request))
        return fields

    def get_filter_horizontal(self, request):
        if hasattr(FOIARequest, 'related_companies'):
            return ('related_companies',)
        return ()


@admin.register(FOIADocument)
class FOIADocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'document_date', 'uploaded_by', 'created_at')
    list_filter = ('source',)
    search_fields = ('title', 'description', 'content')
    raw_id_fields = ('uploaded_by',)


@admin.register(FOIASearchResult)
class FOIASearchResultAdmin(admin.ModelAdmin):
    list_display = ('record_type', 'record_id', 'pre_classification', 'foia_request')
    list_filter = ('pre_classification', 'record_type')
    raw_id_fields = ('foia_request',)


@admin.register(FOIADetermination)
class FOIADeterminationAdmin(admin.ModelAdmin):
    list_display = ('search_result', 'decision', 'exemption_review', 'reviewed_by')
    list_filter = ('decision', 'exemption_review')
    raw_id_fields = ('search_result', 'reviewed_by')


@admin.register(FOIAResponsePackage)
class FOIAResponsePackageAdmin(admin.ModelAdmin):
    list_display = (
        'foia_request', 'total_records_found', 'records_released',
        'records_withheld', 'is_complete', 'is_approved_by_senior',
    )
    list_filter = ('is_complete', 'is_reviewed_by_attorney', 'is_approved_by_senior')
    raw_id_fields = ('foia_request', 'generated_by')


@admin.register(FOIAAppeal)
class FOIAAppealAdmin(admin.ModelAdmin):
    list_display = ('appeal_number', 'foia_request', 'appeal_status', 'filed_date', 'decision_date')
    list_filter = ('appeal_status',)
    search_fields = ('appeal_number', 'foia_request__request_number')
    raw_id_fields = ('foia_request',)
