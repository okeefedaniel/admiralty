"""FOIA search engine — finds records matching a FOIA scope.

In Beacon mode: searches Interactions and Notes (Zone 1 and Zone 2 only —
Zone 3 is never FOIA-responsive), plus any FOIADocuments.

In standalone Admiralty mode: searches FOIADocuments only.

Creates FOIASearchResult records with pre-classification suggestions.
"""
import logging

from django.db.models import Q
from django.utils import timezone

from foia.compat import is_beacon
from .models import FOIADocument, FOIAScope, FOIASearchResult

logger = logging.getLogger(__name__)


def _build_keyword_q(scope, text_fields):
    """Build a Q object for keyword search across the given fields."""
    filters = Q()
    for keyword in (scope.keywords or []):
        kw = keyword.strip()
        if not kw:
            continue
        kw_q = Q()
        for field in text_fields:
            kw_q |= Q(**{f'{field}__icontains': kw})
        filters |= kw_q
    return filters


def _build_search_q(scope):
    """Build a Q object from scope parameters for Interaction search."""
    filters = Q()

    # Keyword search across text fields
    for keyword in (scope.keywords or []):
        kw = keyword.strip()
        if not kw:
            continue
        filters |= Q(subject__icontains=kw) | Q(description__icontains=kw)

    # Company name matching
    for company_name in (scope.company_names or []):
        cn = company_name.strip()
        if not cn:
            continue
        filters |= Q(company__name__icontains=cn)

    return filters


def _build_note_search_q(scope):
    """Build Q for note-specific searches."""
    filters = Q()

    for keyword in (scope.keywords or []):
        kw = keyword.strip()
        if not kw:
            continue
        filters |= Q(subject__icontains=kw) | Q(content__icontains=kw)

    for company_name in (scope.company_names or []):
        cn = company_name.strip()
        if not cn:
            continue
        filters |= Q(company__name__icontains=cn)

    for contact_name in (scope.contact_names or []):
        cn = contact_name.strip()
        if not cn:
            continue
        name_parts = cn.split()
        if len(name_parts) >= 2:
            filters |= Q(contact__first_name__icontains=name_parts[0], contact__last_name__icontains=name_parts[-1])
        else:
            filters |= Q(contact__first_name__icontains=cn) | Q(contact__last_name__icontains=cn)

    return filters


def _build_document_search_q(scope):
    """Build Q for FOIADocument searches."""
    filters = Q()

    for keyword in (scope.keywords or []):
        kw = keyword.strip()
        if not kw:
            continue
        filters |= (
            Q(title__icontains=kw)
            | Q(description__icontains=kw)
            | Q(content__icontains=kw)
        )

    for company_name in (scope.company_names or []):
        cn = company_name.strip()
        if not cn:
            continue
        filters |= (
            Q(title__icontains=cn)
            | Q(content__icontains=cn)
            | Q(description__icontains=cn)
        )

    for contact_name in (scope.contact_names or []):
        cn = contact_name.strip()
        if not cn:
            continue
        filters |= (
            Q(title__icontains=cn)
            | Q(content__icontains=cn)
            | Q(description__icontains=cn)
        )

    return filters


def _pre_classify(zone=None, foia_status=None):
    """Suggest a pre-classification based on zone and existing FOIA status."""
    if zone == 'act_private':
        return FOIASearchResult.PreClassification.NOT_RELEVANT

    if foia_status == 'exempt':
        return FOIASearchResult.PreClassification.LIKELY_EXEMPT
    elif foia_status == 'responsive':
        return FOIASearchResult.PreClassification.LIKELY_RESPONSIVE
    elif zone == 'decd_internal':
        return FOIASearchResult.PreClassification.NEEDS_REVIEW
    else:  # shared zone or standalone (no zone)
        return FOIASearchResult.PreClassification.LIKELY_RESPONSIVE


def _search_interactions(foia_request, scope):
    """Search Beacon Interactions (Zone 1 + 2 only). Returns count."""
    from interactions.models import Interaction

    ix_q = _build_search_q(scope)
    if not ix_q:
        return 0

    ix_qs = Interaction.objects.filter(ix_q).exclude(zone='act_private')

    if scope.date_range_start:
        ix_qs = ix_qs.filter(date__gte=scope.date_range_start)
    if scope.date_range_end:
        ix_qs = ix_qs.filter(date__lte=scope.date_range_end)

    ix_qs = ix_qs.select_related('company', 'created_by').distinct()
    count = 0

    for ix in ix_qs:
        contacts = ', '.join(c.full_name for c in ix.contacts.all())
        snapshot = f"Subject: {ix.subject}\n"
        if ix.description:
            snapshot += f"Notes: {ix.description}\n"
        if contacts:
            snapshot += f"Contacts: {contacts}\n"
        snapshot += f"Date: {ix.date}\nType: {ix.get_interaction_type_display()}\nZone: {ix.zone}"

        FOIASearchResult.objects.create(
            foia_request=foia_request,
            record_type='interaction',
            record_id=ix.pk,
            record_description=f"{ix.get_interaction_type_display()} with {ix.company.name}: {ix.subject}",
            snapshot_content=snapshot,
            snapshot_metadata={
                'company': ix.company.name,
                'date': str(ix.date),
                'type': ix.interaction_type,
                'zone': ix.zone,
                'created_by': str(ix.created_by) if ix.created_by else None,
            },
            pre_classification=_pre_classify(ix.zone),
        )
        count += 1

    return count


def _search_notes(foia_request, scope):
    """Search Beacon Notes (Zone 1 + 2 only). Returns count."""
    from notes.models import Note

    note_q = _build_note_search_q(scope)
    if not note_q:
        return 0

    note_qs = Note.objects.filter(note_q).exclude(zone='act_private')

    if scope.date_range_start:
        note_qs = note_qs.filter(created_at__date__gte=scope.date_range_start)
    if scope.date_range_end:
        note_qs = note_qs.filter(created_at__date__lte=scope.date_range_end)

    note_qs = note_qs.select_related('company', 'contact', 'created_by').distinct()
    count = 0

    for note in note_qs:
        target = note.company or note.contact or note.opportunity
        snapshot = f"Subject: {note.subject or 'Untitled'}\n"
        snapshot += f"Content: {note.content}\n"
        snapshot += f"Zone: {note.zone}\nFOIA Status: {note.foia_status}"

        FOIASearchResult.objects.create(
            foia_request=foia_request,
            record_type='note',
            record_id=note.pk,
            record_description=f"Note: {note.subject or 'Untitled'} ({target})",
            snapshot_content=snapshot,
            snapshot_metadata={
                'target': str(target) if target else None,
                'zone': note.zone,
                'foia_status': note.foia_status,
                'created_by': str(note.created_by) if note.created_by else None,
            },
            pre_classification=_pre_classify(note.zone, note.foia_status),
        )
        count += 1

    return count


def _search_documents(foia_request, scope):
    """Search FOIADocuments. Returns count."""
    doc_q = _build_document_search_q(scope)
    if not doc_q:
        return 0

    doc_qs = FOIADocument.objects.filter(doc_q)

    if scope.date_range_start:
        doc_qs = doc_qs.filter(document_date__gte=scope.date_range_start)
    if scope.date_range_end:
        doc_qs = doc_qs.filter(document_date__lte=scope.date_range_end)

    doc_qs = doc_qs.select_related('uploaded_by').distinct()
    count = 0

    for doc in doc_qs:
        snapshot = f"Title: {doc.title}\n"
        if doc.description:
            snapshot += f"Description: {doc.description}\n"
        if doc.content:
            snapshot += f"Content: {doc.content[:2000]}\n"
        snapshot += f"Date: {doc.document_date or 'Unknown'}\nSource: {doc.source or 'N/A'}"

        FOIASearchResult.objects.create(
            foia_request=foia_request,
            record_type='document',
            record_id=doc.pk,
            record_description=f"Document: {doc.title}",
            snapshot_content=snapshot,
            snapshot_metadata={
                'source': doc.source,
                'date': str(doc.document_date) if doc.document_date else None,
                'uploaded_by': str(doc.uploaded_by) if doc.uploaded_by else None,
                'tags': doc.tags,
            },
            pre_classification=_pre_classify(),
        )
        count += 1

    return count


def run_search(foia_request):
    """Execute a FOIA search based on the request's scope.

    Creates FOIASearchResult records for each matching record.
    Returns the count of results found.
    """
    try:
        scope = foia_request.scope
    except FOIAScope.DoesNotExist:
        logger.warning('No scope defined for FOIA request %s', foia_request.request_number)
        return 0

    # Clear any existing results from a previous search run
    foia_request.search_results.all().delete()

    results_created = 0

    # In Beacon mode, search Interactions and Notes
    if is_beacon():
        results_created += _search_interactions(foia_request, scope)
        results_created += _search_notes(foia_request, scope)

    # Always search FOIADocuments (both modes)
    results_created += _search_documents(foia_request, scope)

    logger.info('FOIA search for %s found %d results', foia_request.request_number, results_created)
    return results_created
