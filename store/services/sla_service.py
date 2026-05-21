"""
SLA Service — Supervisor approval deadline and lazy escalation.

Business hours: 06:00 – 17:00 WAT (UTC+1), Monday to Sunday.
The 2-hour supervisor deadline only ticks during business hours.
Escalation is checked lazily on page load of supervisor,
storekeeper, and management pages.
"""

from datetime import timedelta, time, timezone as dt_timezone
from zoneinfo import ZoneInfo
from django.utils import timezone

WAT = ZoneInfo("Africa/Lagos")
BUSINESS_START = time(6, 0)
BUSINESS_END = time(17, 0)
SLA_HOURS = 2


def _is_business_hour(dt_wat):
    return BUSINESS_START <= dt_wat.time() <= BUSINESS_END


def compute_supervisor_deadline(submitted_at_utc):
    """
    Given a UTC submission datetime, compute the UTC deadline
    by adding SLA_HOURS of business time. Returns a UTC datetime.
    """
    remaining = timedelta(hours=SLA_HOURS)
    current = submitted_at_utc.astimezone(WAT)

    while remaining.total_seconds() > 0:
        if _is_business_hour(current):
            end_of_day = current.replace(
                hour=BUSINESS_END.hour,
                minute=BUSINESS_END.minute,
                second=0,
                microsecond=0,
            )
            available = end_of_day - current
            if available >= remaining:
                current = current + remaining
                remaining = timedelta(0)
            else:
                remaining -= available
                current = (current + timedelta(days=1)).replace(
                    hour=BUSINESS_START.hour,
                    minute=BUSINESS_START.minute,
                    second=0,
                    microsecond=0,
                )
        else:
            if current.time() < BUSINESS_START:
                current = current.replace(
                    hour=BUSINESS_START.hour,
                    minute=BUSINESS_START.minute,
                    second=0,
                    microsecond=0,
                )
            else:
                current = (current + timedelta(days=1)).replace(
                    hour=BUSINESS_START.hour,
                    minute=BUSINESS_START.minute,
                    second=0,
                    microsecond=0,
                )

    return current.astimezone(dt_timezone.utc)


def escalate_overdue_requests():
    """
    Lazily escalates all PENDING requests whose supervisor_deadline
    has passed. Called on page load — no Celery required.
    Returns the count of newly escalated requests.
    """
    from store.models import Request, RequestActivity, Activity

    now = timezone.now()
    overdue = Request.objects.filter(
        status=Request.Status.PENDING,
        supervisor_deadline__lt=now,
    )

    count = 0
    system_user = _get_system_user()

    for request in overdue:
        request.mark_escalated()

        RequestActivity.objects.create(
            request=request,
            actor=system_user,
            action=RequestActivity.Action.ESCALATED,
            description="Request automatically escalated — supervisor SLA exceeded.",
            metadata={"deadline": str(request.supervisor_deadline)},
        )

        Activity.objects.create(
            actor=system_user,
            verb=Activity.Verb.REQUEST_ESCALATED,
            target_type="Request",
            target_id=request.id,
            summary=f"Request #{request.id} escalated — SLA exceeded.",
        )

        _notify_escalation(request, system_user)
        count += 1

    return count


def _get_system_user():
    from django.contrib.auth.models import User
    user, _ = User.objects.get_or_create(
        username="__system__",
        defaults={
            "first_name": "System",
            "last_name": "Automated",
            "is_active": False,
        }
    )
    return user


def _notify_escalation(request_obj, system_user):
    from store.models import Notification
    from django.contrib.auth.models import User, Group
    try:
        recipients = User.objects.filter(
            groups__name__in=["StoreKeeper", "Management"]
        ).distinct()
        for user in recipients:
            Notification.objects.create(
                recipient=user,
                event_type=Notification.EventType.REQUEST_ESCALATED,
                message=(
                    f"Request #{request_obj.id} by {request_obj.requester.name} "
                    f"has been escalated — supervisor SLA exceeded. "
                    f"Storekeeper may now fulfill."
                ),
                target_type="Request",
                target_id=request_obj.id,
            )
    except Exception:
        pass
