from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from store.models import Staff, Item, Issuance, IssuanceItem, Activity
from store.services.activity_service import emit_activity


class IssuanceError(Exception):
    """Raised for issuance flow errors that should show to user."""
    pass


@transaction.atomic
def create_issuance_service(*, staff: Staff, issued_by, items_with_qty: List[Dict[str, Any]], comment: str = "") -> Issuance:
    """
    Pure service: NO request, NO messages, NO redirect, NO render.
    items_with_qty = [{"item_id": 1, "quantity": 2}, ...]
    """

    if not staff:
        raise IssuanceError("Staff is required.")

    if not items_with_qty:
        raise IssuanceError("Add at least one item.")

    # Normalize + validate lines
    seen = set()
    normalized = []
    for i, line in enumerate(items_with_qty, start=1):
        item_id = line.get("item_id")
        qty = line.get("quantity")

        if item_id in (None, "") or qty in (None, ""):
            raise IssuanceError(f"Row {i}: Item and quantity are required.")

        try:
            item_id = int(item_id)
            qty = int(qty)
        except (TypeError, ValueError):
            raise IssuanceError(f"Row {i}: Item and quantity must be numbers.")

        if qty <= 0:
            raise IssuanceError(f"Row {i}: Quantity must be greater than zero.")

        if item_id in seen:
            raise IssuanceError(f"Row {i}: Duplicate item selected.")

        seen.add(item_id)
        normalized.append({"item_id": item_id, "quantity": qty})

    # Lock all items used in this issuance
    items = Item.objects.select_for_update().filter(id__in=seen)
    if items.count() != len(seen):
        raise IssuanceError("One or more items do not exist.")

    item_map = {it.id: it for it in items}

    # Check stock
    for line in normalized:
        it = item_map[line["item_id"]]
        qty = line["quantity"]
        if it.quantity < qty:
            raise IssuanceError(
                f"Not enough stock for {it.name}. Available: {it.quantity}, Requested: {qty}"
            )

    # Create issuance header
    issuance = Issuance.objects.create(
        staff=staff,
        issued_by=issued_by,
        comment=comment,
        issued_at=timezone.now(),
    )

    issuance_items = []
    # Apply mutations
    for line in normalized:
        it = item_map[line["item_id"]]
        qty = line["quantity"]

        it.quantity -= qty
        it.save(update_fields=["quantity"])

        issuance_items.append(
            IssuanceItem.objects.create(
                issuance=issuance,
                item=it,
                quantity=qty,
            )
        )

    # Emit success activity
    emit_activity(
        actor=issued_by,
        verb=Activity.Verb.ISSUANCE_CREATED,
        target=issuance,
        summary=f"{issued_by.get_full_name()} issued {len(issuance_items)} item(s) to {staff.name}",
        metadata={
            "staff_id": staff.id,
            "staff_name": staff.name,
            "department": staff.department.name if staff.department else "",
            "items": [
                {"item_id": li.item.id, "item": li.item.name, "quantity": li.quantity}
                for li in issuance_items
            ],
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
        summary=f"{actor.get_full_name()} attempted an issuance but failed: {error}",
        metadata={"error": error},
    )
