from django.db.models import Q
from kishan.models import Notification


def notifications(request):
    if request.user.is_authenticated:
        unread = (
            Notification.objects.filter(user=request.user, read=False)
            .filter(Q(booking__isnull=True) | Q(booking__id__isnull=False))
            .order_by("-created_at")
        )

        return {
            "unread_notifications": unread,
            "unread_notifications_count": unread.count(),
        }
    return {}
