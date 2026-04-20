from django.apps import AppConfig


class AdmiraltyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    label = 'admiralty_core'  # Keep DB table prefix for migration compatibility
    verbose_name = 'Admiralty Core'

    def ready(self):
        # Register FOIA models for signal-based audit logging
        from keel.core.audit_signals import register_audited_model, connect_audit_signals

        register_audited_model('foia.FOIARequest', 'FOIA Request')
        register_audited_model('foia.FOIAScope', 'FOIA Scope')
        register_audited_model('foia.FOIADocument', 'FOIA Document')
        register_audited_model('foia.FOIAResponsePackage', 'FOIA Response Package')
        register_audited_model('foia.FOIADetermination', 'FOIA Determination')
        register_audited_model('foia.FOIASearchResult', 'FOIA Search Result')
        register_audited_model('foia.FOIAAppeal', 'FOIA Appeal')
        register_audited_model('foia.StatutoryExemption', 'Statutory Exemption')

        connect_audit_signals()
