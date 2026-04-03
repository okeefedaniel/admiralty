from keel.core.models import AbstractAuditLog, AbstractNotification
from keel.notifications.models import (
    AbstractNotificationPreference,
    AbstractNotificationLog,
)


class AuditLog(AbstractAuditLog):
    """Admiralty audit trail."""

    class Meta(AbstractAuditLog.Meta):
        pass


class Notification(AbstractNotification):
    class Meta(AbstractNotification.Meta):
        pass


class NotificationPreference(AbstractNotificationPreference):
    class Meta(AbstractNotificationPreference.Meta):
        pass


class NotificationLog(AbstractNotificationLog):
    class Meta(AbstractNotificationLog.Meta):
        pass
