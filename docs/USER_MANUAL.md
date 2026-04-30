# Admiralty User Manual

Admiralty is the FOIA workflow management system in the DockLabs suite. It
takes a Freedom of Information Act request from intake through scope
definition, cross-product search, attorney review, response packaging,
and appeal — with statutory deadline tracking, exemption claims, and a
full immutable audit trail at every step.

This manual covers the user-facing surface end to end. For operations,
see [CLAUDE.md](../CLAUDE.md).

---

## Contents

1. [Overview](#overview)
2. [Roles](#roles)
3. [Getting Started](#getting-started)
4. [Dashboard](#dashboard)
5. [Request Lifecycle](#request-lifecycle)
6. [Intake](#intake)
7. [Scope Definition](#scope-definition)
8. [Search](#search)
9. [Review & Determinations](#review--determinations)
10. [AI-Assisted Review](#ai-assisted-review)
11. [Response Package](#response-package)
12. [Appeals](#appeals)
13. [Statutory Exemptions](#statutory-exemptions)
14. [Document Repository](#document-repository)
15. [Statutory Deadline](#statutory-deadline)
16. [Suite Integrations](#suite-integrations)
17. [Notifications](#notifications)
18. [Status Reference](#status-reference)
19. [Keyboard Shortcuts](#keyboard-shortcuts)
20. [Support](#support)

---

## Overview

Admiralty implements the Connecticut Freedom of Information Act (CGS
§1-200 et seq.) workflow as a structured, audit-ready pipeline. Each
request moves through nine well-defined statuses from **Received** to
**Closed**, and every transition is logged.

The product is **dual-mode**:

- **Standalone Admiralty** — deployed alone as a FOIA management tool.
  The document repository (`FOIADocument`) is the primary search target.
- **Beacon-embedded** — when deployed alongside Beacon CRM, the same
  FOIA app gains cross-product search across Beacon's interactions and
  notes (Zone 1 and Zone 2 only — Zone 3 is never FOIA-responsive),
  plus uploaded FOIA documents.

This manual describes the standalone surface. Beacon-mode behavior is
called out where it differs.

---

## Roles

Admiralty's role gates use Django's `is_staff` flag in standalone mode,
and Beacon's richer FOIA role taxonomy when deployed inside Beacon. The
intent in either case is:

| Role | Capability |
|---|---|
| **FOIA Officer** | Intake new requests, define scope, run search, pre-classify results, compile response packages. |
| **FOIA Attorney / Reviewer** | Apply statutory exemptions, write redactions, sign off on legal determinations. |
| **FOIA Manager** | Everything FOIA Officer + Attorney can do, plus return packages for additional search and submit to senior review. |
| **Senior Reviewer / Agency Admin** | Final approval of the response package before it goes out. May return to review with comments. |
| **System Admin** | Full access. |

In standalone mode, any user with `is_staff=True` can hold any of these
roles. In Beacon mode, the role gates are enforced by the
`foia_officer` / `foia_attorney` / `foia_manager` / `agency_admin` /
`system_admin` roles on the user record.

---

## Getting Started

### Signing in

1. From any DockLabs product, click **Admiralty** in the fleet
   switcher, or visit `https://admiralty.docklabs.ai/`.
2. Click **Sign in with DockLabs** (the suite OIDC button) or **Sign in
   with Microsoft** (direct Entra) when configured.
3. You'll land on `/dashboard/`.

If you're already signed in to another DockLabs product, the redirect
is seamless — no second login form.

### What you'll see first

The dashboard shows total / open / overdue request counts, your
assigned requests, recent intake, and a zone distribution if records
have been searched.

---

## Dashboard

`/dashboard/` is the canonical post-login URL. It surfaces:

- **Total** — every FOIA request in the system.
- **Open** — anything not yet **Responded** or **Closed**.
- **Overdue** — open requests past their statutory deadline.
- **Pending Review** — requests in **Under Review** status awaiting
  attorney action.
- **My Assigned** — open requests assigned to you, ordered by
  statutory deadline.
- **Recent intake** — the ten most recently received requests.
- **Zone distribution** (Beacon-embedded mode) — share of search
  results from public-facing records vs DECD internal vs ACT private,
  helpful for triaging large search batches.

Each summary card links through to the underlying list with the right
filter applied — clicking **Overdue** lands you on
`/foia/?overdue=1`, clicking **Open** on `/foia/?open=1`, and so on.

---

## Request Lifecycle

Admiralty's nine statuses encode the FOIA pipeline:

```
received → scope_defined → searching → under_review → package_ready →
senior_review → responded → (appealed →) closed
```

| From | To | Action | Required role | Notes |
|---|---|---|---|---|
| received | scope_defined | Define Scope | FOIA staff / manager | |
| scope_defined | searching | Begin Search | FOIA staff / manager | |
| searching | under_review | Submit for Review | FOIA staff / manager | |
| under_review | searching | Return to Search | FOIA manager | comment required |
| under_review | package_ready | Approve Package | FOIA attorney / manager | |
| package_ready | senior_review | Submit to Senior Review | FOIA manager | |
| senior_review | under_review | Return to Review | FOIA manager / agency admin / system admin | comment required |
| senior_review | responded | Send Response | FOIA manager / agency admin / system admin | |
| responded | appealed | Record Appeal | FOIA staff / manager | |
| responded | closed | Close Request | FOIA staff / manager | |
| appealed | closed | Close After Appeal | FOIA manager | |

Every transition writes a `FOIARequestStatusHistory` row capturing the
actor, the from / to status, the timestamp, and any required comment.

---

## Intake

`/foia/create/` — start a new FOIA request.

Required fields:

- **Request number** — agency-assigned identifier (e.g.
  `FOIA-2026-001`). Must be unique.
- **Status** — defaults to **Received**.
- **Priority** — Low / Normal / High / Urgent.
- **Requester name** + at least one of email / phone.
- **Subject** and **description** — what records the requester is
  asking for.
- **Date received** — drives the statutory clock.
- **Statutory deadline** — auto-suggested as 4 business days from
  receipt per CT CGS §1-206(a). Editable for federal requests (5 USC
  552 — 20 business days) or other regimes.
- **Assigned to** — the FOIA officer driving the request.
- **Reviewing attorney** — set later, before the request hits **Under
  Review**.

After save, the request lands at `/foia/<id>/` with all of its lifecycle
controls.

---

## Scope Definition

`/foia/<id>/scope/` — define what to search for.

A scope carries:

- **Date range** — start and end dates for the search window.
- **Keywords** — one term or phrase per line. Matched as
  case-insensitive `icontains` across record content.
- **Company names** — one per line (Beacon mode only — matches
  `Company.name`).
- **Contact names** — one per line.
- **Record types** — which kinds of records to include (notes,
  interactions, documents).
- **Scope notes** — free-text description of the search strategy for
  the audit trail.

Saving a scope on a `received` request automatically advances it to
`scope_defined`.

---

## Search

`/foia/<id>/search/` (POST) — run the search against the configured
scope. Results land at `/foia/<id>/results/`.

The search engine differs by deployment mode:

- **Standalone Admiralty** — searches `FOIADocument` rows by extracted
  text content.
- **Beacon-embedded** — searches Beacon `Interaction` and `Note` rows
  in Zone 1 (shared public records) and Zone 2 (DECD internal). Zone 3
  (`act_private`) is never returned — those records are never
  FOIA-responsive by policy. Plus `FOIADocument` rows.

Each match becomes a `FOIASearchResult` row capturing:

- **Record reference** — the type and primary key of the source row.
- **Record description** — short label.
- **Snapshot content** — the record's content frozen at search time
  so it doesn't drift if the source is later edited.
- **Snapshot metadata** — JSON, including the source `zone` for Beacon
  mode and any other useful context.
- **Pre-classification** — initial AI / rules-based suggestion: Likely
  Responsive / Likely Exempt / Needs Review / Not Relevant. Editable
  during review.

A successful search advances the request to **Searching**.

---

## Review & Determinations

`/foia/<id>/results/` — the review queue. Per result you see the
record's snapshot content, its pre-classification, any AI flags, and
whether a determination has been recorded.

Click into a result and write a determination:

- **Decision** — Release / Withhold / Partial Release / Refer to
  Another Agency.
- **Exemptions claimed** (multi-select) — the statutory exemptions
  that justify a Withhold or Partial Release. Pulled from the active
  `StatutoryExemption` table.
- **Justification** — free-text legal reasoning that lands in the
  audit trail and the privilege log.
- **Redacted content** — the sanitized version of the record (for
  Partial Release).
- **Attorney notes** — optional internal notes.

Saving a determination stamps the reviewing attorney and the time, and
the request stays in **Under Review** until every result has a
determination and the package has been compiled.

---

## AI-Assisted Review

`/foia/<id>/results/ai-review/` — staff-only AI sweep. When the
`ANTHROPIC_API_KEY` is configured, Admiralty asks Claude to read every
search result and flag classification mismatches:

- **`should_release`** — a record currently marked Withhold / Likely
  Exempt that AI thinks is responsive and not exempt.
- **`should_withhold`** — a record currently marked for Release that
  contains likely-exempt content.
- **`review_recommended`** — a record where the AI's confidence is
  high but the current human classification is `needs_review`.
- **`ok`** — AI agrees with the current classification.

Each flag carries the AI recommendation, confidence (high / medium /
low), and reasoning. Flags are stored in the session keyed by request
ID and surface inline on the search results page.

AI review is advisory. Every determination still requires an
attorney's sign-off.

---

## Response Package

`/foia/<id>/compile/` (POST) — compiles all determinations into a
`FOIAResponsePackage` row carrying:

- **Counts** — total records found, released, withheld, partially
  released.
- **Generated files** (when uploaded) — cover letter, response, and
  privilege log.
- **Compliance flags** — `is_complete`, `is_reviewed_by_attorney`,
  `is_approved_by_senior` — track the package through senior review.

Compiling on a request in **Under Review** advances it to **Package
Ready**.

From there:

- **Submit to Senior Review** advances to **Senior Review**.
- The senior reviewer can **Send Response** (→ **Responded**) or
  **Return to Review** (→ **Under Review**, comment required).

When the response goes out, set the **Date responded** field on the
request — this stops the statutory clock for compliance reporting.

---

## Appeals

`/foia/<id>/appeal/` — record an appeal filed against the agency's
response.

An appeal carries:

- **Appeal number** + **filed date**.
- **Appeal status** — Filed / Hearing Scheduled / Hearing Completed /
  Decision Pending / Upheld / Overturned / Settled / Withdrawn.
- **Appellant arguments** + **agency response**.
- **Hearing date** and **hearing notes**.
- **Decision date**, **decision summary**, and an uploaded
  **decision document**.
- **Lessons learned** — internal notes for future requests.

Recording an appeal on a **Responded** request advances it to
**Appealed**. The request stays appealed until **Close After Appeal**
moves it to **Closed**.

---

## Statutory Exemptions

`/foia/exemptions/` — the reference table of Connecticut FOIA
exemptions. Each `StatutoryExemption` row carries:

- **Subdivision** — e.g. `1-210(b)(5)(A)`.
- **Label** — short human-readable name.
- **Statutory text** — verbatim citation.
- **Citation** — formal cite for the privilege log.
- **Guidance notes** — internal interpretation guidance for FOIA staff.
- **Active flag** — toggle to retire an exemption without deleting
  historical determinations that cited it.

Exemption records are immutable from the determination perspective —
historical determinations always preserve which exemption was claimed
even if the row is later deactivated.

---

## Document Repository

`/foia/documents/` — uploaded files searchable by full text. In
standalone Admiralty this is the primary corpus; in Beacon mode it
supplements the Interaction / Note search.

Each `FOIADocument` carries:

- **Title** + **description**.
- **Content** — extracted text (PDF / DOC text extraction populates
  this; plain text uploads use the file content directly).
- **File** — the uploaded original.
- **Document date** — the date of the original record (distinct from
  the upload date).
- **Source** — where the document came from (department, system,
  custodian).
- **Tags** — JSON list for categorization.

Uploads are validated by `keel.security.scanning.FileSecurityValidator`
(extension allowlist + magic-byte check + optional ClamAV) and capped
at `KEEL_MAX_UPLOAD_SIZE` (default 10 MB).

`/foia/documents/bulk-upload/` — drag-and-drop multiple files at once.

---

## Statutory Deadline

Connecticut FOIA (CGS §1-206) gives an agency **4 business days from
receipt** to acknowledge a request and a reasonable time to produce
records. Federal FOIA (5 USC 552) gives **20 business days**.

Admiralty stores three deadline-relevant fields:

- **`date_received`** — when the agency got the request. Triggers the
  clock.
- **`statutory_deadline`** — computed deadline. Indexed; powers the
  Overdue summary and the Awaiting Me column in Helm.
- **`extended_deadline`** — set when an extension has been negotiated
  with the requester; surfaces as the effective deadline when present.

The dashboard's **Overdue** count compares
`statutory_deadline < today` against open requests (anything not
**Responded** or **Closed**).

---

## Suite Integrations

### Helm executive dashboard

Admiralty publishes two endpoints for Helm:

- **`/api/v1/helm-feed/`** — aggregate counts for the fleet metric
  grid. Auth: `Authorization: Bearer $HELM_FEED_API_KEY`.
- **`/api/v1/helm-feed/inbox/?user_sub=<oidc_sub>`** — per-user inbox.
  Returns FOIA requests assigned to that user where the status is in
  `{received, scope_defined, searching, under_review, package_ready}`,
  carrying the `statutory_deadline` as the due date so Helm's
  Awaiting Me column can sort by urgency.

Both endpoints are no-ops when `HELM_FEED_API_KEY` is unset, so
standalone deployments don't need to configure them.

### Beacon CRM

When deployed inside Beacon, Admiralty's search engine reaches into
Beacon's `Interaction` and `Note` corpus directly (through the shared
ORM). Zone 3 (`act_private`) records are never returned. The same
`StatutoryExemption` and `FOIARequest` rows persist regardless of
deployment mode.

### Cross-product FOIA export

Other DockLabs products register records with `keel.foia.export` so
their content is FOIA-discoverable. Admiralty consumes those exports
into the search corpus when configured, and the agency's response
package can cite records originating in Beacon, Harbor, Manifest, and
others.

---

## Notifications

`/notifications/` — the in-app notification list, with preferences at
`/notifications/preferences/`.

Channels (in-app + email) are user-configurable per event type. Email
delivery uses Resend in production; the console backend in development.

---

## Status Reference

### FOIA request status

| Status | Meaning |
|---|---|
| **Received** | Intake complete; awaiting scope. |
| **Scope Defined** | Search parameters set; ready to run. |
| **Searching** | Search in progress; results being collected. |
| **Under Review** | Attorney is determining responsiveness and exemptions. |
| **Package Ready** | All determinations made; compiled package awaiting senior review. |
| **Senior Review** | Senior leadership reviewing the final package. |
| **Responded** | Response sent to the requester. |
| **Appealed** | Requester has filed an appeal. |
| **Closed** | Terminal. Request fully resolved. |

### FOIA priority

| Priority | Meaning |
|---|---|
| **Low** | Routine; no rush. |
| **Normal** | Default. |
| **High** | Senior staff or media attention; expedite. |
| **Urgent** | Litigation hold or hearing-driven; same-day attention. |

### Search-result pre-classification

| Class | Meaning |
|---|---|
| **Likely Responsive** | The record matches the scope and appears releasable. |
| **Likely Exempt** | The record matches but contains content covered by a statutory exemption. |
| **Needs Review** | Match found; classification deferred to attorney. |
| **Not Relevant** | False positive — included for audit completeness. |

### Determination decision

| Decision | Meaning |
|---|---|
| **Release** | Record released in full. |
| **Withhold** | Record withheld in full. Requires at least one cited exemption. |
| **Partial Release** | Record released with redactions. Requires cited exemption + redacted content. |
| **Refer** | Forwarded to another agency that holds the responsive record. |

### Appeal status

| Status | Meaning |
|---|---|
| **Filed** | Appeal received. |
| **Hearing Scheduled** | Hearing date set. |
| **Hearing Completed** | Hearing held; awaiting decision. |
| **Decision Pending** | Decision being drafted. |
| **Upheld** | Agency decision stands. |
| **Overturned** | Agency must release additional records. |
| **Settled** | Resolved by negotiation. |
| **Withdrawn** | Appellant withdrew the appeal. |

### CT FOIA jurisdiction

| Jurisdiction | Statute | Initial window |
|---|---|---|
| **Connecticut** | CGS §1-206 | 4 business days to acknowledge |
| **Federal** | 5 USC 552 | 20 business days |

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| **⌘K** / **Ctrl+K** | Open the suite-wide search modal. |

---

## Support

- **Email** — info@docklabs.ai (1–2 business day response).
- **Feedback widget** — bottom-right corner of every page; routes to
  the shared support queue.
- **Per-product help** — for questions specific to Helm, Harbor,
  Beacon, etc., open the help link inside that product.

---

*Last updated: 2026-04-30.*
