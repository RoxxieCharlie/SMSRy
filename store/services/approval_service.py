"""
Approval Service — Supervisor approval, rejection, and item editing.
All supervisor actions go through this service, never directly through views.
"""

from django.db import models, transaction
from django.utils import timezone
from store.models import (
    Request, RequestItem, RequestActivity, Activity, UserProfile
)


def get_active_supervisor():
    """Returns the User who is currently active supervisor, or None."""
    try:
        profile = UserProfile.objects.select_related("user").get(
            is_active_supervisor=True
        )
        return profile.user
    except UserProfile.DoesNotExist:
        return None


def approve_request(request_obj, supervisor_user, edited_items=None):
    """
    Approves a PENDING or ESCALATED request.

    edited_items: optional dict of {request_item_id: new_qty}
    Supervisor may only reduce quantities, not increase beyond
    the original staff-requested quantity.
    Sets approved_qty on each RequestItem.
    """
    if request_obj.status not in [
        Request.Status.PENDING,
        Request.Status.ESCALATED,
    ]:
        raise ValueError("Only pending or escalated requests can be approved.")

    with transaction.atomic():
        if edited_items:
            for item_id, new_qty in edited_items.items():
                try:
                    ri = RequestItem.objects.get(pk=item_id, request=request_obj)
                except RequestItem.DoesNotExist:
                    raise ValueError(f"RequestItem {item_id} not found on this request.")

                if new_qty <= 0:
                    raise ValueError(
                        f"Quantity for {ri.item.name} must be greater than zero."
                    )
                if new_qty > ri.original_requested_qty:
                    raise ValueError(
                        f"Supervisor cannot increase quantity beyond original "
                        f"requested amount ({ri.original_requested_qty}) "
                        f"for {ri.item.name}."
                    )
                ri.requested_qty = new_qty
                ri.approved_qty = new_qty
                ri.save(update_fields=["requested_qty", "approved_qty"])

        # Set approved_qty = requested_qty for untouched items
        request_obj.items.filter(approved_qty__isnull=True).update(
            approved_qty=models.F("requested_qty")
        )

        request_obj.mark_approved(supervisor_user)

        RequestActivity.objects.create(
            request=request_obj,
            actor=supervisor_user,
            action=RequestActivity.Action.APPROVED,
            description=f"Request approved by {supervisor_user.get_full_name() or supervisor_user.username}.",
        )

        Activity.objects.create(
            actor=supervisor_user,
            verb=Activity.Verb.REQUEST_APPROVED,
            target_type="Request",
            target_id=request_obj.id,
            summary=f"Request #{request_obj.id} approved by {supervisor_user.get_full_name() or supervisor_user.username}.",
        )

        _notify_approval(request_obj, supervisor_user)


def reject_request(request_obj, supervisor_user, reason):
    """
    Rejects a PENDING or ESCALATED request with a mandatory reason.
    Rejection is permanent — the request cannot be resubmitted.
    """
    if not reason or not reason.strip():
        raise ValueError("A rejection reason is required.")

    if request_obj.status not in [
        Request.Status.PENDING,
        Request.Status.ESCALATED,
    ]:
        raise ValueError("Only pending or escalated requests can be rejected.")

    with transaction.atomic():
        request_obj.mark_rejected(supervisor_user, reason.strip())

        RequestActivity.objects.create(
            request=request_obj,
            actor=supervisor_user,
            action=RequestActivity.Action.REJECTED,
            description=(
                f"Request rejected by {supervisor_user.get_full_name() or supervisor_user.username}. "
                f"Reason: {reason.strip()}"
            ),
            metadata={"reason": reason.strip()},
        )

        Activity.objects.create(
            actor=supervisor_user,
            verb=Activity.Verb.REQUEST_REJECTED,
            target_type="Request",
            target_id=request_obj.id,
            summary=f"Request #{request_obj.id} rejected. Reason: {reason.strip()}",
        )

        _notify_rejection(request_obj, supervisor_user, reason)


def delete_request_item(request_obj, supervisor_user, item_id):
    """
    Removes a single line item from a PENDING or ESCALATED request.
    At least one item must remain — cannot delete all items.
    """
    if request_obj.status not in [
        Request.Status.PENDING,
        Request.Status.ESCALATED,
    ]:
        raise ValueError("Can only remove items from pending or escalated requests.")

    if request_obj.items.count() <= 1:
        raise ValueError(
            "Cannot remove the last item. Reject the entire request instead."
        )

    with transaction.atomic():
        try:
            ri = RequestItem.objects.get(pk=item_id, request=request_obj)
        except RequestItem.DoesNotExist:
            raise ValueError("Item not found on this request.")

        item_name = ri.item.name
        ri.delete()

        RequestActivity.objects.create(
            request=request_obj,
            actor=supervisor_user,
            action=RequestActivity.Action.SUPERVISOR_EDITED,
            description=(
                f"Item '{item_name}' removed by supervisor "
                f"{supervisor_user.get_full_name() or supervisor_user.username}."
            ),
            metadata={"removed_item": item_name},
        )


def toggle_supervisor(admin_user, target_user_id, activate):
    """
    Toggles the supervisor role for a management user.
    Only users in the Management group may be made supervisor.
    """
    from django.contrib.auth.models import User

    try:
        target_user = User.objects.get(pk=target_user_id)
    except User.DoesNotExist:
        raise ValueError("User not found.")

    if not target_user.groups.filter(name="Management").exists():
        raise ValueError("Only Management users can be assigned as supervisor.")

    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    profile.is_active_supervisor = activate
    profile.save()

    from django.contrib.auth.models import Permission
    try:
        perm = Permission.objects.get(codename="can_approve_requests")
        if activate:
            target_user.user_permissions.add(perm)
        else:
            target_user.user_permissions.remove(perm)
    except Permission.DoesNotExist:
        pass


def _notify_approval(request_obj, supervisor_user):
    from store.models import Notification
    from django.contrib.auth.models import User
    try:
        recipients = User.objects.filter(groups__name="StoreKeeper")
        for user in recipients:
            Notification.objects.create(
                recipient=user,
                event_type=Notification.EventType.REQUEST_APPROVED,
                message=(
                    f"Request #{request_obj.id} by {request_obj.requester.name} "
                    f"has been approved and is ready for fulfillment."
                ),
                target_type="Request",
                target_id=request_obj.id,
            )
    except Exception:
        pass


def _notify_rejection(request_obj, supervisor_user, reason):
    from store.models import Notification
    try:
        requester_user = request_obj.requester.user
        if requester_user:
            Notification.objects.create(
                recipient=requester_user,
                event_type=Notification.EventType.REQUEST_REJECTED,
                message=(
                    f"Your request #{request_obj.id} has been rejected. "
                    f"Reason: {reason}"
                ),
                target_type="Request",
                target_id=request_obj.id,
            )
    except Exception:
        pass
