"""FOIA views — full attorney workflow from intake through response."""
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import UploadedFile
from django.db import models as db_models
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import generic, View

from .forms import (
    FOIARequestForm, FOIAScopeForm, FOIADeterminationForm, FOIAAppealForm,
)
from .models import (
    FOIARequest, FOIAScope, FOIASearchResult, FOIADetermination,
    FOIAResponsePackage, FOIAAppeal, StatutoryExemption, FOIADocument,
)

try:
    from keel.security.scanning import FileSecurityValidator
except ImportError:  # pragma: no cover — keel is always installed in prod
    FileSecurityValidator = None


_FOIA_ROLES = (
    'foia_admin', 'foia_officer', 'foia_reviewer', 'foia_manager',
    'foia_attorney', 'system_admin', 'agency_admin', 'admin',
)


def _has_foia_role(user) -> bool:
    """Gate upload / admin endpoints to FOIA-authorized staff only."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    role = getattr(user, 'role', '') or ''
    return role in _FOIA_ROLES


class FOIARoleRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not _has_foia_role(request.user):
            raise PermissionDenied('FOIA role required.')
        return super().dispatch(request, *args, **kwargs)


def _validate_upload(uploaded_file: UploadedFile) -> None:
    """Enforce FileSecurityValidator + KEEL_MAX_UPLOAD_SIZE on every upload.

    FOIA uploads previously accepted any file (finding #102). This ensures
    extension allowlist + magic-byte validation + optional ClamAV before
    the file hits MEDIA_ROOT where an attorney might later fetch and
    open it.
    """
    max_size = getattr(settings, 'KEEL_MAX_UPLOAD_SIZE', 20 * 1024 * 1024)
    if uploaded_file.size > max_size:
        raise PermissionDenied(
            f'Upload exceeds {max_size} bytes.'
        )
    if FileSecurityValidator is not None:
        FileSecurityValidator()(uploaded_file)


# ---------------------------------------------------------------------------
# Dashboard & List Views
# ---------------------------------------------------------------------------

class FOIADashboardView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'foia/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = FOIARequest.objects
        now = timezone.now().date()
        ctx['total'] = qs.count()
        ctx['open'] = qs.exclude(status__in=['responded', 'closed']).count()
        open_qs = qs.exclude(status__in=['responded', 'closed'])
        ctx['overdue'] = open_qs.filter(statutory_deadline__lt=now).count()
        ctx['pending_review'] = qs.filter(status='under_review').count()
        ctx['recent'] = qs.order_by('-date_received')[:10]
        ctx['my_assigned'] = qs.filter(
            assigned_to=self.request.user
        ).exclude(status__in=['responded', 'closed']).order_by('statutory_deadline')[:10]
        list_url = reverse('foia:request_list')
        ctx['total_url'] = list_url
        ctx['open_url'] = f'{list_url}?open=1' if ctx['open'] else list_url
        ctx['overdue_url'] = f'{list_url}?overdue=1' if ctx['overdue'] else list_url
        ctx['pending_review_url'] = f'{list_url}?status=under_review' if ctx['pending_review'] else list_url

        # Zone distribution across all search results
        all_results = FOIASearchResult.objects.all()
        ctx['zone_shared_count'] = sum(
            1 for r in all_results if r.snapshot_metadata.get('zone') == 'shared'
        )
        ctx['zone_decd_count'] = sum(
            1 for r in all_results if r.snapshot_metadata.get('zone') == 'decd_internal'
        )
        ctx['zone_act_count'] = sum(
            1 for r in all_results if r.snapshot_metadata.get('zone') == 'act_private'
        )
        ctx['zone_total'] = ctx['zone_shared_count'] + ctx['zone_decd_count'] + ctx['zone_act_count']
        if ctx['zone_total'] > 0:
            ctx['zone_shared_pct'] = round(ctx['zone_shared_count'] / ctx['zone_total'] * 100)
            ctx['zone_decd_pct'] = round(ctx['zone_decd_count'] / ctx['zone_total'] * 100)
            ctx['zone_act_pct'] = round(ctx['zone_act_count'] / ctx['zone_total'] * 100)
        else:
            ctx['zone_shared_pct'] = 0
            ctx['zone_decd_pct'] = 0
            ctx['zone_act_pct'] = 0

        return ctx


class FOIARequestListView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'foia/request_list.html'
    context_object_name = 'requests'
    paginate_by = 25

    def get_queryset(self):
        qs = FOIARequest.objects.select_related('assigned_to', 'reviewing_attorney')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(subject__icontains=q)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        if self.request.GET.get('open') == '1':
            qs = qs.exclude(status__in=['responded', 'closed'])
        if self.request.GET.get('overdue') == '1':
            now = timezone.now().date()
            qs = qs.exclude(status__in=['responded', 'closed']).filter(statutory_deadline__lt=now)
        if self.request.GET.get('mine') == '1':
            qs = qs.filter(assigned_to=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['status_filter'] = self.request.GET.get('status', '')
        ctx['status_choices'] = FOIARequest.Status.choices
        return ctx


class FOIAReviewQueueView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'foia/review_queue.html'
    context_object_name = 'requests'
    paginate_by = 25

    def get_queryset(self):
        return (
            FOIARequest.objects
            .filter(status__in=['received', 'scope_defined', 'searching', 'under_review', 'package_ready', 'senior_review'])
            .select_related('assigned_to', 'reviewing_attorney')
            .order_by('statutory_deadline')
        )


# ---------------------------------------------------------------------------
# Request CRUD
# ---------------------------------------------------------------------------

class FOIARequestCreateView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = FOIARequest
    form_class = FOIARequestForm
    template_name = 'foia/request_form.html'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'FOIA request {self.object.request_number} created.')
        return response

    def get_success_url(self):
        return reverse('foia:request_detail', kwargs={'pk': self.object.pk})


class FOIARequestDetailView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.DetailView):
    model = FOIARequest
    template_name = 'foia/request_detail.html'
    context_object_name = 'foia'

    def get_queryset(self):
        qs = FOIARequest.objects.select_related(
            'assigned_to', 'reviewing_attorney', 'created_by',
        ).prefetch_related('search_results', 'appeals')
        if hasattr(FOIARequest, 'related_companies'):
            qs = qs.prefetch_related('related_companies')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        foia = self.object

        # Scope
        try:
            ctx['scope'] = foia.scope
        except FOIAScope.DoesNotExist:
            ctx['scope'] = None

        # Search results with determinations
        results = foia.search_results.all().order_by('record_type', 'snapshot_taken_at')
        ctx['search_results'] = results
        ctx['results_count'] = results.count()
        ctx['results_reviewed'] = sum(1 for r in results if hasattr(r, 'determination'))

        # Classification stats
        ctx['likely_responsive'] = results.filter(pre_classification='likely_responsive').count()
        ctx['likely_exempt'] = results.filter(pre_classification='likely_exempt').count()
        ctx['needs_review'] = results.filter(pre_classification='needs_review').count()

        # Response package
        try:
            ctx['response_package'] = foia.response_package
        except FOIAResponsePackage.DoesNotExist:
            ctx['response_package'] = None

        # Appeals
        ctx['appeals'] = foia.appeals.all()

        # Available status transitions
        from .workflow import FOIA_WORKFLOW
        ctx['transitions'] = FOIA_WORKFLOW.get_available_transitions(
            foia.status, self.request.user
        ) if hasattr(FOIA_WORKFLOW, 'get_available_transitions') else []

        # Statutory exemptions for reference
        ctx['exemptions'] = StatutoryExemption.objects.filter(is_active=True)

        return ctx


class FOIARequestUpdateView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = FOIARequest
    form_class = FOIARequestForm
    template_name = 'foia/request_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'FOIA request {self.object.request_number} updated.')
        return response

    def get_success_url(self):
        return reverse('foia:request_detail', kwargs={'pk': self.object.pk})


# ---------------------------------------------------------------------------
# Status Transition
# ---------------------------------------------------------------------------

class FOIATransitionView(FOIARoleRequiredMixin, LoginRequiredMixin, View):
    """Advance a FOIA request to a new status."""

    def post(self, request, pk):
        foia = get_object_or_404(FOIARequest, pk=pk)
        target_status = request.POST.get('target_status', '').strip()
        comment = request.POST.get('comment', '').strip()

        # Validate transition
        from .workflow import FOIA_WORKFLOW
        if not FOIA_WORKFLOW.can_transition(foia.status, target_status, request.user):
            messages.error(request, f'Cannot transition from {foia.get_status_display()} to {target_status}.')
            return redirect('foia:request_detail', pk=pk)

        # Enforce per-transition `require_comment=True` policy. Some transitions
        # (e.g. "Return to Search", "Return to Review") require a written
        # justification for the audit trail. Without this check the workflow
        # declaration was advisory only.
        transition = next(
            (t for t in getattr(FOIA_WORKFLOW, 'transitions', [])
             if t.from_status == foia.status and t.to_status == target_status),
            None,
        )
        if transition is not None and getattr(transition, 'require_comment', False) and not comment:
            messages.error(
                request,
                f'A comment is required to transition to {dict(FOIARequest.Status.choices).get(target_status, target_status)}.',
            )
            return redirect('foia:request_detail', pk=pk)

        old_status = foia.status
        foia.status = target_status
        foia.save(update_fields=['status', 'updated_at'])

        messages.success(
            request,
            f'{foia.request_number}: {dict(FOIARequest.Status.choices).get(old_status)} → {foia.get_status_display()}'
        )
        return redirect('foia:request_detail', pk=pk)


# ---------------------------------------------------------------------------
# Scope Definition
# ---------------------------------------------------------------------------

class FOIAScopeView(FOIARoleRequiredMixin, LoginRequiredMixin, View):
    """Define or update search scope for a FOIA request."""

    def get(self, request, pk):
        foia = get_object_or_404(FOIARequest, pk=pk)
        try:
            scope = foia.scope
            form = FOIAScopeForm(instance=scope)
        except FOIAScope.DoesNotExist:
            form = FOIAScopeForm()

        from django.shortcuts import render
        return render(request, 'foia/scope_form.html', {
            'foia': foia, 'form': form,
        })

    def post(self, request, pk):
        foia = get_object_or_404(FOIARequest, pk=pk)
        try:
            scope = foia.scope
            form = FOIAScopeForm(request.POST, instance=scope)
        except FOIAScope.DoesNotExist:
            form = FOIAScopeForm(request.POST)

        if form.is_valid():
            scope = form.save(commit=False)
            scope.foia_request = foia
            scope.defined_by = request.user
            scope.save()

            # Auto-advance status if still at 'received'
            if foia.status == 'received':
                foia.status = 'scope_defined'
                foia.save(update_fields=['status', 'updated_at'])

            messages.success(request, f'Search scope defined for {foia.request_number}.')
            return redirect('foia:request_detail', pk=pk)

        from django.shortcuts import render
        return render(request, 'foia/scope_form.html', {
            'foia': foia, 'form': form,
        })


# ---------------------------------------------------------------------------
# Search Execution
# ---------------------------------------------------------------------------

class FOIARunSearchView(FOIARoleRequiredMixin, LoginRequiredMixin, View):
    """Execute the FOIA search based on defined scope."""

    def post(self, request, pk):
        foia = get_object_or_404(FOIARequest, pk=pk)

        try:
            foia.scope
        except FOIAScope.DoesNotExist:
            messages.error(request, 'Define a search scope before running the search.')
            return redirect('foia:scope', pk=pk)

        from .search import run_search
        count = run_search(foia)

        # Advance status
        if foia.status in ('scope_defined', 'received'):
            foia.status = 'searching'
            foia.save(update_fields=['status', 'updated_at'])

        messages.success(request, f'Search complete: {count} records found for {foia.request_number}.')
        return redirect('foia:search_results', pk=pk)


# ---------------------------------------------------------------------------
# Search Results & Review
# ---------------------------------------------------------------------------

class FOIASearchResultsView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.DetailView):
    """View all search results for a FOIA request."""
    model = FOIARequest
    template_name = 'foia/search_results.html'
    context_object_name = 'foia'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        results = self.object.search_results.all().order_by('pre_classification', 'record_type')

        # Count determinations
        determined_ids = set(
            FOIADetermination.objects.filter(
                search_result__foia_request=self.object
            ).values_list('search_result_id', flat=True)
        )

        for r in results:
            r.has_determination = r.pk in determined_ids

        ctx['results'] = results
        ctx['total'] = results.count()
        ctx['determined'] = len(determined_ids)
        ctx['remaining'] = ctx['total'] - ctx['determined']
        ctx['exemptions'] = StatutoryExemption.objects.filter(is_active=True)

        # Zone-grouped results for zone view (exclude Zone 3 / act_private)
        zone_shared = [r for r in results if r.snapshot_metadata.get('zone') == 'shared']
        zone_decd = [r for r in results if r.snapshot_metadata.get('zone') == 'decd_internal']
        ctx['zone_shared'] = zone_shared
        ctx['zone_shared_count'] = len(zone_shared)
        ctx['zone_decd'] = zone_decd
        ctx['zone_decd_count'] = len(zone_decd)

        # AI review flags (stored in session after running AI review)
        ai_flags = self.request.session.get(f'foia_ai_review_{self.object.pk}', [])
        if ai_flags:
            flag_map = {f.get('id') or f.get('result_id'): f for f in ai_flags}
            for r in results:
                r.ai_flag = flag_map.get(str(r.pk), {})
            ctx['ai_review_ran'] = True
            ctx['ai_issues'] = sum(1 for f in ai_flags if f.get('flag') != 'ok')
        else:
            ctx['ai_review_ran'] = False

        return ctx


class FOIADeterminationView(FOIARoleRequiredMixin, LoginRequiredMixin, View):
    """Attorney makes a determination on a single search result."""

    def get(self, request, pk, result_pk):
        foia = get_object_or_404(FOIARequest, pk=pk)
        result = get_object_or_404(FOIASearchResult, pk=result_pk, foia_request=foia)

        try:
            determination = result.determination
            form = FOIADeterminationForm(instance=determination)
        except FOIADetermination.DoesNotExist:
            form = FOIADeterminationForm()

        from django.shortcuts import render
        return render(request, 'foia/determination_form.html', {
            'foia': foia, 'result': result, 'form': form,
            'exemptions': StatutoryExemption.objects.filter(is_active=True),
        })

    def post(self, request, pk, result_pk):
        foia = get_object_or_404(FOIARequest, pk=pk)
        result = get_object_or_404(FOIASearchResult, pk=result_pk, foia_request=foia)

        try:
            determination = result.determination
            form = FOIADeterminationForm(request.POST, instance=determination)
        except FOIADetermination.DoesNotExist:
            form = FOIADeterminationForm(request.POST)

        if form.is_valid():
            det = form.save(commit=False)
            det.search_result = result
            det.reviewed_by = request.user
            det.reviewed_at = timezone.now()
            det.save()

            # Handle exemptions M2M
            exemptions = form.cleaned_data.get('exemptions', [])
            det.exemptions_claimed.set(exemptions)

            messages.success(request, f'Determination recorded: {det.get_decision_display()}')
            return redirect('foia:search_results', pk=pk)

        from django.shortcuts import render
        return render(request, 'foia/determination_form.html', {
            'foia': foia, 'result': result, 'form': form,
            'exemptions': StatutoryExemption.objects.filter(is_active=True),
        })


# ---------------------------------------------------------------------------
# Response Package
# ---------------------------------------------------------------------------

class FOIACompileResponseView(FOIARoleRequiredMixin, LoginRequiredMixin, View):
    """Compile search results into a response package."""

    def post(self, request, pk):
        foia = get_object_or_404(FOIARequest, pk=pk)
        results = foia.search_results.all()
        determinations = FOIADetermination.objects.filter(search_result__foia_request=foia)

        package, created = FOIAResponsePackage.objects.get_or_create(
            foia_request=foia,
            defaults={
                'generated_by': request.user,
                'generated_at': timezone.now(),
            }
        )

        package.total_records_found = results.count()
        package.records_released = determinations.filter(decision='release').count()
        package.records_withheld = determinations.filter(decision='withhold').count()
        package.records_partially_released = determinations.filter(decision='partial_release').count()
        package.generated_at = timezone.now()
        package.generated_by = request.user
        package.save()

        # Advance to package_ready if under_review
        if foia.status == 'under_review':
            foia.status = 'package_ready'
            foia.save(update_fields=['status', 'updated_at'])

        messages.success(request, f'Response package compiled for {foia.request_number}.')
        return redirect('foia:request_detail', pk=pk)


# ---------------------------------------------------------------------------
# Appeals
# ---------------------------------------------------------------------------

class FOIAAIReviewView(FOIARoleRequiredMixin, LoginRequiredMixin, View):
    """Run AI classification review on all search results."""

    # Per-user-per-FOIA cooldown. Without this, an authenticated FOIA-role
    # user can repeatedly POST to this endpoint and burn Anthropic API credit
    # — every invocation makes one Claude call per 10 search results.
    AI_REVIEW_COOLDOWN_SECONDS = 60

    def post(self, request, pk):
        foia = get_object_or_404(FOIARequest, pk=pk)

        cache_key = f'foia_ai_review_cooldown:{request.user.pk}:{foia.pk}'
        if cache.get(cache_key):
            messages.warning(
                request,
                f'AI review is rate-limited to one run per {self.AI_REVIEW_COOLDOWN_SECONDS} seconds per request. Try again shortly.',
            )
            return redirect('foia:search_results', pk=pk)
        cache.set(cache_key, True, self.AI_REVIEW_COOLDOWN_SECONDS)

        from .ai_review import review_classifications
        flags = review_classifications(foia)

        # Store in session for display
        request.session[f'foia_ai_review_{pk}'] = flags

        issues = sum(1 for f in flags if f.get('flag') != 'ok')
        if issues:
            messages.warning(request, f'AI review found {issues} potential issue(s) across {len(flags)} records.')
        else:
            messages.success(request, f'AI review complete: all {len(flags)} classifications look correct.')

        return redirect('foia:search_results', pk=pk)


class FOIAExemptionListView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.ListView):
    """View and manage statutory exemptions."""
    model = StatutoryExemption
    template_name = 'foia/exemption_list.html'
    context_object_name = 'exemptions'

    def get_queryset(self):
        return StatutoryExemption.objects.filter(is_active=True).order_by('subdivision')


class FOIAExemptionUpdateView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    """Update statutory exemption text and guidance."""
    model = StatutoryExemption
    template_name = 'foia/exemption_form.html'
    context_object_name = 'exemption'
    fields = ['subdivision', 'label', 'statutory_text', 'citation', 'guidance_notes', 'is_active']
    success_url = reverse_lazy('foia:exemption_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name in form.fields:
            widget = form.fields[field_name].widget
            if hasattr(widget, 'attrs'):
                if isinstance(widget, (forms.Textarea,)):
                    widget.attrs.update({'class': 'form-control', 'rows': 4})
                elif isinstance(widget, (forms.CheckboxInput,)):
                    widget.attrs.update({'class': 'form-check-input'})
                else:
                    widget.attrs.update({'class': 'form-control'})
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Exemption {self.object.subdivision} updated.')
        return response


class FOIAAppealCreateView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = FOIAAppeal
    form_class = FOIAAppealForm
    template_name = 'foia/appeal_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.foia = get_object_or_404(FOIARequest, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['foia'] = self.foia
        return ctx

    def form_valid(self, form):
        form.instance.foia_request = self.foia
        response = super().form_valid(form)

        # Update request status
        if self.foia.status == 'responded':
            self.foia.status = 'appealed'
            self.foia.save(update_fields=['status', 'updated_at'])

        messages.success(self.request, f'Appeal recorded for {self.foia.request_number}.')
        return response

    def get_success_url(self):
        return reverse('foia:request_detail', kwargs={'pk': self.foia.pk})


class FOIAAppealUpdateView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = FOIAAppeal
    form_class = FOIAAppealForm
    template_name = 'foia/appeal_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['foia'] = self.object.foia_request
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Appeal updated.')
        return response

    def get_success_url(self):
        return reverse('foia:request_detail', kwargs={'pk': self.object.foia_request_id})


# ---------------------------------------------------------------------------
# Document Management (searchable document repository)
# ---------------------------------------------------------------------------

class FOIADocumentListView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.ListView):
    """List all uploaded FOIA documents."""
    model = FOIADocument
    template_name = 'foia/document_list.html'
    context_object_name = 'documents'
    paginate_by = 25

    def get_queryset(self):
        qs = FOIADocument.objects.select_related('uploaded_by')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                db_models.Q(title__icontains=q)
                | db_models.Q(description__icontains=q)
                | db_models.Q(content__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class FOIADocumentCreateView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.CreateView):
    """Upload a new document for FOIA search."""
    model = FOIADocument
    template_name = 'foia/document_form.html'
    fields = ['title', 'description', 'content', 'file', 'document_date', 'source', 'tags']

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name in form.fields:
            widget = form.fields[field_name].widget
            if hasattr(widget, 'attrs'):
                if isinstance(widget, (forms.Textarea,)):
                    widget.attrs.update({'class': 'form-control', 'rows': 4})
                elif isinstance(widget, (forms.FileInput,)):
                    widget.attrs.update({'class': 'form-control'})
                elif isinstance(widget, (forms.DateInput,)):
                    widget.attrs.update({'class': 'form-control', 'type': 'date'})
                else:
                    widget.attrs.update({'class': 'form-control'})
        return form

    def form_valid(self, form):
        uploaded = form.cleaned_data.get('file')
        if uploaded:
            _validate_upload(uploaded)
        form.instance.uploaded_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'Document "{self.object.title}" uploaded.')
        return response

    def get_success_url(self):
        return reverse('foia:document_list')


class FOIADocumentBulkUploadView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.TemplateView):
    """Upload multiple documents at once."""
    template_name = 'foia/document_bulk_upload.html'

    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist('files')
        if not files:
            messages.warning(request, 'No files selected.')
            return redirect('foia:document_bulk_upload')
        source = request.POST.get('source', '').strip()
        count = 0
        for f in files:
            _validate_upload(f)
            title = f.name.rsplit('.', 1)[0] if '.' in f.name else f.name
            FOIADocument.objects.create(
                title=title,
                file=f,
                source=source,
                uploaded_by=request.user,
            )
            count += 1
        messages.success(request, f'{count} document{"s" if count != 1 else ""} uploaded.')
        return redirect('foia:document_list')


class FOIADocumentDetailView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.DetailView):
    """View document details."""
    model = FOIADocument
    template_name = 'foia/document_detail.html'
    context_object_name = 'document'


class FOIADocumentUpdateView(FOIARoleRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    """Edit document metadata."""
    model = FOIADocument
    template_name = 'foia/document_form.html'
    fields = ['title', 'description', 'content', 'file', 'document_date', 'source', 'tags']

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name in form.fields:
            widget = form.fields[field_name].widget
            if hasattr(widget, 'attrs'):
                if isinstance(widget, (forms.Textarea,)):
                    widget.attrs.update({'class': 'form-control', 'rows': 4})
                elif isinstance(widget, (forms.FileInput,)):
                    widget.attrs.update({'class': 'form-control'})
                elif isinstance(widget, (forms.DateInput,)):
                    widget.attrs.update({'class': 'form-control', 'type': 'date'})
                else:
                    widget.attrs.update({'class': 'form-control'})
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Document "{self.object.title}" updated.')
        return response

    def get_success_url(self):
        return reverse('foia:document_detail', kwargs={'pk': self.object.pk})
