"""FOIA workflow definition using the shared Keel WorkflowEngine.

In Beacon mode, imports from keel.core.workflow directly.
In standalone Admiralty mode, uses keel.core.workflow as a plain Python
import but overrides role checking so that Django's built-in
User.is_staff grants all FOIA permissions.
"""
from foia.compat import is_beacon

if is_beacon():
    from keel.core.workflow import Transition, WorkflowEngine
else:
    # Standalone: use keel.core.workflow as a plain Python import (it has no
    # app-registry dependencies), but override role checking so that
    # Django's built-in User.is_staff grants all FOIA permissions.
    from keel.core.workflow import Transition, WorkflowEngine as _BaseWorkflowEngine

    class WorkflowEngine(_BaseWorkflowEngine):
        # Roles that act as "any FOIA staff" — they cover every transition
        # not pinned to a more specific role. ``agency_admin`` is included
        # so the customer-side admin can advance the workflow without
        # holding ``is_staff`` (Django staff = backend access, which is
        # IT-only and should NOT be granted to agency admins).
        _ANY_STAFF_ROLES = frozenset({
            'system_admin', 'admin', 'agency_admin',
            'foia_manager', 'foia_officer', 'foia_attorney',
        })

        @classmethod
        def _user_has_role(cls, user, required_roles, obj=None):
            # ``obj`` accepted for compatibility with keel >=0.16.0
            # (see keel/core/workflow.py — base passes the bound instance
            # through so subclasses can resolve object-scoped roles).
            if not required_roles or 'any' in required_roles:
                return True
            user_role = getattr(user, 'role', None)
            if user_role and user_role in required_roles:
                return True
            # Admin-tier roles always satisfy the gate, even when not
            # explicitly listed on the Transition (matches the standalone
            # is_staff escape hatch for Django-staff users).
            if user_role in cls._ANY_STAFF_ROLES:
                return True
            if getattr(user, 'is_staff', False):
                return True
            return False


FOIA_WORKFLOW = WorkflowEngine(
    transitions=[
        Transition(
            from_status='received',
            to_status='scope_defined',
            roles=['foia_staff', 'foia_manager'],
            label='Define Scope',
            description='Define search parameters for the FOIA request.',
        ),
        Transition(
            from_status='scope_defined',
            to_status='searching',
            roles=['foia_staff', 'foia_manager'],
            label='Begin Search',
            description='Start searching for responsive records.',
        ),
        Transition(
            from_status='searching',
            to_status='under_review',
            roles=['foia_staff', 'foia_manager'],
            label='Submit for Review',
            description='Submit search results for legal review.',
        ),
        Transition(
            from_status='under_review',
            to_status='searching',
            roles=['foia_manager'],
            label='Return to Search',
            description='Additional search needed based on review.',
            require_comment=True,
        ),
        Transition(
            from_status='under_review',
            to_status='package_ready',
            roles=['foia_attorney', 'foia_manager'],
            label='Approve Package',
            description='Legal review complete, package ready for senior review.',
        ),
        Transition(
            from_status='package_ready',
            to_status='senior_review',
            roles=['foia_manager'],
            label='Submit to Senior Review',
            description='Submit response package for senior leadership review.',
        ),
        Transition(
            from_status='senior_review',
            to_status='under_review',
            roles=['foia_manager', 'agency_admin', 'system_admin'],
            label='Return to Review',
            description='Senior leadership requests changes.',
            require_comment=True,
        ),
        Transition(
            from_status='senior_review',
            to_status='responded',
            roles=['foia_manager', 'agency_admin', 'system_admin'],
            label='Send Response',
            description='Approve and send final response to requester.',
        ),
        Transition(
            from_status='responded',
            to_status='appealed',
            roles=['foia_staff', 'foia_manager'],
            label='Record Appeal',
            description='Requester has filed an appeal.',
        ),
        Transition(
            from_status='responded',
            to_status='closed',
            roles=['foia_staff', 'foia_manager'],
            label='Close Request',
            description='Close the completed FOIA request.',
        ),
        Transition(
            from_status='appealed',
            to_status='closed',
            roles=['foia_manager'],
            label='Close After Appeal',
            description='Close the request after appeal resolution.',
        ),
    ],
    history_model='foia.FOIARequestStatusHistory',
    history_fk_field='foia_request',
)
