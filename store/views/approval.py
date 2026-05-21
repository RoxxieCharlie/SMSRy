"""
Approval views — Supervisor request queue and action views.
All views require the user to be the active supervisor.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from store.models import Request, UserProfile
from store.services.sla_service import escalate_overdue_requests
from store.services.approval_service import (
    approve_request,
    reject_request,
    delete_request_item,
)


def supervisor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("store:login")
        try:
            profile = request.user.profile
            if not profile.is_active_supervisor:
                messages.error(request, "You do not have supervisor access.")
                return redirect("store:dashboard")
        except UserProfile.DoesNotExist:
            messages.error(request, "You do not have supervisor access.")
            return redirect("store:dashboard")
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@supervisor_required
def approval_queue(request):
    from django.utils import timezone
    escalate_overdue_requests()

    pending_requests = (
        Request.objects
        .filter(status__in=[Request.Status.PENDING, Request.Status.ESCALATED])
        .select_related("requester", "requester__department")
        .prefetch_related("items__item")
        .order_by("supervisor_deadline", "-submitted_at")
    )

    actioned_requests = (
        Request.objects
        .filter(approved_by=request.user)
        .select_related("requester", "requester__department")
        .order_by("-approved_at")[:20]
    )

    rejected_requests = (
        Request.objects
        .filter(rejected_by=request.user)
        .select_related("requester", "requester__department")
        .order_by("-rejected_at")[:20]
    )

    now = timezone.now()
    context = {
        "pending_requests": pending_requests,
        "actioned_requests": actioned_requests,
        "rejected_requests": rejected_requests,
        "now": now,
        "base_template": "store/mgt_base_v2.html",
    }
    return render(request, "store/approval_queue.html", context)


@login_required
@supervisor_required
def approval_detail(request, pk):
    from django.utils import timezone
    request_obj = get_object_or_404(
        Request.objects
        .select_related("requester", "requester__department")
        .prefetch_related("items__item", "activities__actor"),
        pk=pk,
        status__in=[Request.Status.PENDING, Request.Status.ESCALATED],
    )
    now = timezone.now()
    context = {
        "request_obj": request_obj,
        "now": now,
        "items": request_obj.items.select_related("item").all(),
        "base_template": "store/mgt_base_v2.html",
    }
    return render(request, "store/approval_detail.html", context)


@login_required
@supervisor_required
def approve_request_view(request, pk):
    if request.method != "POST":
        return redirect("store:approval_queue")

    request_obj = get_object_or_404(
        Request,
        pk=pk,
        status__in=[Request.Status.PENDING, Request.Status.ESCALATED],
    )

    edited_items = {}
    for key, value in request.POST.items():
        if key.startswith("qty_"):
            try:
                item_id = int(key.split("_")[1])
                new_qty = int(value)
                edited_items[item_id] = new_qty
            except (ValueError, IndexError):
                continue

    try:
        approve_request(request_obj, request.user, edited_items or None)
        messages.success(request, f"Request #{request_obj.id} approved successfully.")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("store:approval_detail", pk=pk)

    return redirect("store:approval_queue")


@login_required
@supervisor_required
def reject_request_view(request, pk):
    if request.method != "POST":
        return redirect("store:approval_queue")

    request_obj = get_object_or_404(
        Request,
        pk=pk,
        status__in=[Request.Status.PENDING, Request.Status.ESCALATED],
    )

    reason = request.POST.get("rejection_reason", "").strip()
    if not reason:
        messages.error(request, "A rejection reason is required.")
        return redirect("store:approval_detail", pk=pk)

    try:
        reject_request(request_obj, request.user, reason)
        messages.success(request, f"Request #{request_obj.id} rejected.")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("store:approval_detail", pk=pk)

    return redirect("store:approval_queue")


@login_required
@supervisor_required
def delete_item_view(request, pk, item_id):
    if request.method != "POST":
        return redirect("store:approval_detail", pk=pk)

    request_obj = get_object_or_404(
        Request,
        pk=pk,
        status__in=[Request.Status.PENDING, Request.Status.ESCALATED],
    )

    try:
        delete_request_item(request_obj, request.user, item_id)
        messages.success(request, "Item removed from request.")
    except ValueError as e:
        messages.error(request, str(e))

    return redirect("store:approval_detail", pk=pk)
