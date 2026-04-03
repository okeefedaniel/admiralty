from django.apps import AppConfig


class AdmiraltyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    label = 'admiralty_core'  # Keep DB table prefix for migration compatibility
    verbose_name = 'Admiralty Core'
