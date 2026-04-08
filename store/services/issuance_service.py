from typing import List, Dict, Any

from django.db import transaction
from django.utils import timezone

from store.models import (
    Item,
    Issuance,
    IssuanceItem,
    Activity,
    Request,
    RequestItem,
    RequestActivity,
)
from store.services.activity_service import emit_activity


class IssuanceError(Exception):
    """Raised for issuance flow errors that should show to user."""
    pass


def _summarize_change_log(change_log: List[Dict[str, Any]]) -> str:
    parts = []
    for change in change_log:
        direction = "increased" if change["new_qty"] > change["old_qty"] else "reduced"
        parts.append(
            f'{direction} {change["item_name"]} from {change["old_qty"]} to {change["new_qty"]}'
        )

    if not parts:
        return ""

    if len(parts) == 1:
        return parts[0]

    if len(parts) == 2:
        return f'{parts[0]} and {parts[1]}'

    return f'{", ".join(parts[:-1])}, and {parts[-1]}'

def _normalize_edit_lines(
    *,
    request_obj: Request,
    items_with_qty: List[Dict[str, Any]],
    quantity_cap_attr: str = "requested_qty",
) -> List[Dict[str, int]]:
    """
    Normalize edit payload for request fulfillment / issuance edit.

    Expected input:
    [
        {"request_item_id": 1, "fulfilled_qty": 2},
        ...
    ]

    Rules:
    - request_item_id must belong to the request
    - no new items can be introduced
    - fulfilled_qty must be >= 0
    - fulfilled_qty must be <= the configured request quantity cap
    """
    if not items_with_qty:
        raise IssuanceError("At least one request item is required.")

    request_items = request_obj.items.select_related("item").all()
    request_item_map = {ri.id: ri for ri in request_items}

    normalized = []
    seen = set()

    for idx, line in enumerate(items_with_qty, start=1):
        request_item_id = line.get("request_item_id")
        fulfilled_qty = line.get("fulfilled_qty")

        if request_item_id in (None, "") or fulfilled_qty in (None, ""):
            raise IssuanceError(f"Row {idx}: Request item and quantity are required.")

        try:
            request_item_id = int(request_item_id)
            fulfilled_qty = int(fulfilled_qty)
        except (TypeError, ValueError):
            raise IssuanceError(f"Row {idx}: Request item and quantity must be numbers.")

        if request_item_id in seen:
            raise IssuanceError(f"Row {idx}: Duplicate request item submitted.")

        seen.add(request_item_id)

        request_item = request_item_map.get(request_item_id)
        if not request_item:
            raise IssuanceError(f"Row {idx}: Invalid request item.")

        if fulfilled_qty < 0:
            raise IssuanceError(f"Row {idx}: Quantity cannot be less than zero.")

        max_allowed_qty = getattr(request_item, quantity_cap_attr, 0) or request_item.requested_qty
        if fulfilled_qty > max_allowed_qty:
            raise IssuanceError(
                f"Row {idx}: Fulfilled quantity for {request_item.item.name} "
                f"cannot exceed allowed quantity ({max_allowed_qty})."
            )
        normalized.append(
            {
                "request_item_id": request_item_id,
                "item_id": request_item.item_id,
                "fulfilled_qty": fulfilled_qty,
            }
        )

    # Ensure caller did not omit existing request items to hide them.
    submitted_ids = {row["request_item_id"] for row in normalized}
    actual_ids = set(request_item_map.keys())

    if submitted_ids != actual_ids:
        raise IssuanceError(
            "Invalid fulfillment payload. All existing request items must be included."
        )

    return normalized


@transaction.atomic
def fulfill_request_service(
    *,
    request_obj: Request,
    issued_by,
    items_with_qty: List[Dict[str, Any]],
    comment: str = "",
) -> Issuance:
    """
    Create issuance strictly from a submitted request.

    items_with_qty format:
    [
        {"request_item_id": 1, "fulfilled_qty": 3},
        ...
    ]
    """
    request_obj = (
        Request.objects.select_for_update(of=("self",))
        .select_related("requester", "requester__department")
        .get(pk=request_obj.pk)
    )

    if request_obj.status != Request.Status.SUBMITTED:
        raise IssuanceError("Only submitted requests can be fulfilled.")

    if hasattr(request_obj, "issuance"):
        raise IssuanceError("This request has already been fulfilled.")

    normalized = _normalize_edit_lines(
        request_obj=request_obj,
        items_with_qty=items_with_qty,
    )

    item_ids = [row["item_id"] for row in normalized]
    items = Item.objects.select_for_update().filter(id__in=item_ids)
    item_map = {item.id: item for item in items}

    if len(item_map) != len(item_ids):
        raise IssuanceError("One or more items in the request no longer exist.")

    # Stock validation
    for row in normalized:
        item = item_map[row["item_id"]]
        fulfilled_qty = row["fulfilled_qty"]
        if item.quantity < fulfilled_qty:
            raise IssuanceError(
                f"Not enough stock for {item.name}. "
                f"Available: {item.quantity}, Requested for fulfillment: {fulfilled_qty}"
            )

    issuance = Issuance.objects.create(
        request=request_obj,
        staff=request_obj.requester,
        issued_by=issued_by,
        comment=comment,
    )

    issuance_items = []
    request_items = {
        ri.id: ri for ri in request_obj.items.select_related("item").all()
    }

    for row in normalized:
        request_item = request_items[row["request_item_id"]]
        item = item_map[row["item_id"]]
        fulfilled_qty = row["fulfilled_qty"]

        # Deduct stock
        item.quantity -= fulfilled_qty
        item.save(update_fields=["quantity"])

        # Update request line
        request_item.fulfilled_qty = fulfilled_qty
        request_item.save(update_fields=["fulfilled_qty"])

        # Create issuance line only for qty > 0
        if fulfilled_qty > 0:
            issuance_item = IssuanceItem.objects.create(
                issuance=issuance,
                item=item,
                quantity=fulfilled_qty,
            )
            issuance_items.append(issuance_item)

    request_obj.mark_fulfilled(issued_by)

    RequestActivity.objects.create(
        request=request_obj,
        actor=issued_by,
        action=RequestActivity.Action.FULFILLED,
        description=f"Request fulfilled by {issued_by.get_full_name() or issued_by.username}.",
        metadata={
            "issuance_id": issuance.id,
            "items": [
                {
                    "request_item_id": row["request_item_id"],
                    "item_id": row["item_id"],
                    "fulfilled_qty": row["fulfilled_qty"],
                }
                for row in normalized
            ],
        },
    )

    emit_activity(
        actor=issued_by,
        verb=Activity.Verb.ISSUANCE_CREATED,
        target=issuance,
        summary=(
            f"{issued_by.get_full_name() or issued_by.username} fulfilled "
            f"Request #{request_obj.id} for {request_obj.requester.name}"
        ),
        metadata={
            "request_id": request_obj.id,
            "staff_id": request_obj.requester.id,
            "staff_name": request_obj.requester.name,
            "department": (
                request_obj.requester.department.name
                if request_obj.requester.department
                else ""
            ),
            "items": [
                {
                    "request_item_id": row["request_item_id"],
                    "item_id": row["item_id"],
                    "item": request_items[row["request_item_id"]].item.name,
                    "fulfilled_qty": row["fulfilled_qty"],
                }
                for row in normalized
            ],
        },
    )

    emit_activity(
        actor=issued_by,
        verb=Activity.Verb.REQUEST_FULFILLED,
        target=request_obj,
        summary=f"Request #{request_obj.id} was fulfilled for {request_obj.requester.name}",
        metadata={
            "issuance_id": issuance.id,
        },
    )

    return issuance


@transaction.atomic
def edit_issuance_service(
    *,
    request_obj: Request,
    edited_by,
    items_with_qty: List[Dict[str, Any]],
    reason: str,
) -> Issuance:
    """
    Edit fulfilled issuance within the 6-hour window.

    items_with_qty format:
    [
        {"request_item_id": 1, "fulfilled_qty": 2},
        ...
    ]

    Rules:
    - request must already be fulfilled
    - request must still be within editable window
    - no new items can be added
    - fulfilled qty cannot exceed requested qty
    - stock must be adjusted by delta
    """
    if not reason or not reason.strip():
        raise IssuanceError("Edit reason is required.")

    request_obj = (
        Request.objects.select_for_update(of=("self",))
        .select_related("requester", "requester__department")
        .get(pk=request_obj.pk)
    )

    request_obj.lock_if_due()
    if request_obj.status == Request.Status.LOCKED:
        raise IssuanceError("This issuance is locked and can no longer be edited.")

    if request_obj.status != Request.Status.FULFILLED:
        raise IssuanceError("Only fulfilled requests can have issuance edited.")

    if not request_obj.can_store_edit_fulfillment:
        raise IssuanceError("The 6-hour edit window has expired.")

    try:
        issuance = Issuance.objects.select_for_update().get(request=request_obj)
    except Issuance.DoesNotExist:
        raise IssuanceError("No issuance exists for this request.")

    normalized = _normalize_edit_lines(
        request_obj=request_obj,
        items_with_qty=items_with_qty,
        quantity_cap_attr="original_requested_qty",
    )

    request_items = {
        ri.id: ri for ri in request_obj.items.select_related("item").all()
    }

    item_ids = [row["item_id"] for row in normalized]
    items = Item.objects.select_for_update().filter(id__in=item_ids)
    item_map = {item.id: item for item in items}

    issuance_item_map = {
        ii.item_id: ii
        for ii in issuance.items.select_for_update().all()
    }

    change_log = []

    # First pass: validate stock for any increase.
    for row in normalized:
        request_item = request_items[row["request_item_id"]]
        item = item_map[row["item_id"]]

        old_qty = request_item.fulfilled_qty
        new_qty = row["fulfilled_qty"]
        delta = new_qty - old_qty

        if delta > 0 and item.quantity < delta:
            raise IssuanceError(
                f"Not enough stock to increase {item.name}. "
                f"Available: {item.quantity}, Additional needed: {delta}."
            )

    # Second pass: apply delta
    for row in normalized:
        request_item = request_items[row["request_item_id"]]
        item = item_map[row["item_id"]]

        old_qty = request_item.fulfilled_qty
        new_qty = row["fulfilled_qty"]
        delta = new_qty - old_qty

        if delta < 0:
            item.quantity += abs(delta)
        elif delta > 0:
            item.quantity -= delta

        item.save(update_fields=["quantity"])

        request_item.fulfilled_qty = new_qty
        request_item.save(update_fields=["fulfilled_qty"])

        existing_issuance_item = issuance_item_map.get(item.id)

        if new_qty == 0:
            if existing_issuance_item:
                existing_issuance_item.delete()
        else:
            if existing_issuance_item:
                existing_issuance_item.quantity = new_qty
                existing_issuance_item.save(update_fields=["quantity"])
            else:
                IssuanceItem.objects.create(
                    issuance=issuance,
                    item=item,
                    quantity=new_qty,
                )

        if old_qty != new_qty:
            change_log.append(
                {
                    "request_item_id": request_item.id,
                    "item_id": item.id,
                    "item_name": item.name,
                    "old_qty": old_qty,
                    "new_qty": new_qty,
                }
            )

    if not change_log:
        raise IssuanceError("No changes were made.")

    change_summary = _summarize_change_log(change_log)

    request_obj.last_edited_by = edited_by
    request_obj.save(update_fields=["last_edited_by", "updated_at"])

    RequestActivity.objects.create(
        request=request_obj,
        actor=edited_by,
        action=RequestActivity.Action.FULFILLMENT_EDITED,
        description=(
            f"Storekeeper {change_summary}."
            if change_summary
            else f"Fulfillment edited by {edited_by.get_full_name() or edited_by.username}."
        ),
        metadata={
            "reason": reason,
            "changes": change_log,
        },
    )

    emit_activity(
        actor=edited_by,
        verb=Activity.Verb.ISSUANCE_UPDATED,
        target=issuance,
        summary=(
            f"{edited_by.get_full_name() or edited_by.username} {change_summary} for Request #{request_obj.id}"
            if change_summary
            else f"{edited_by.get_full_name() or edited_by.username} edited issuance for Request #{request_obj.id}"
        ),
        metadata={
            "request_id": request_obj.id,
            "reason": reason,
            "changes": change_log,
        },
    )

    emit_activity(
        actor=edited_by,
        verb=Activity.Verb.REQUEST_UPDATED,
        target=request_obj,
        summary=(
            f"Request #{request_obj.id}: {change_summary}"
            if change_summary
            else f"Fulfillment for Request #{request_obj.id} was edited"
        ),
        metadata={
            "reason": reason,
            "changes": change_log,
        },
    )

    return issuance


def emit_failed_issuance_activity(*, actor, error: str):
    """
    Helper to log failed issuance attempts without creating issuance.
    """
    emit_activity(
        actor=actor,
        verb=Activity.Verb.ISSUANCE_FAILED,
        target_type="Issuance",
        target_id=0,
        summary=f"{actor.get_full_name() or actor.username} attempted an issuance but failed: {error}",
        metadata={"error": error},
    )









