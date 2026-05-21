from django.contrib.auth.models import Group
from store.models import Request


def store_nav_context(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "is_storekeeper_user": False,
            "storekeeper_pending_request_count": 0,
        }

    is_storekeeper = user.groups.filter(name__iexact="StoreKeeper").exists()
    pending_count = 0
    if is_storekeeper:
        pending_count = Request.objects.filter(
            status__in=[Request.Status.APPROVED, Request.Status.ESCALATED]
        ).count()

    return {
        "is_storekeeper_user": is_storekeeper,
        "storekeeper_pending_request_count": pending_count,
    }
