import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from store.decorators import storekeeper_required
from store.models import Staff, Item
from store.services.issuance_service import (
    create_issuance_service,
    IssuanceError,
    emit_failed_issuance_activity,
)

# Matches: items[0][item_id] and items[0][qty]
ITEM_ID_KEY_RE = re.compile(r"^items\[(\d+)\]\[item_id\]$")
QTY_KEY_RE     = re.compile(r"^items\[(\d+)\]\[qty\]$")


@login_required
@storekeeper_required
def issuance_create(request):
    if request.method == "POST":
        staff_id = request.POST.get("staff_id")  # ✅ matches template
        comment = (request.POST.get("comment") or "").strip()

        if not staff_id:
            messages.error(request, "Staff is required.")
            return redirect("store:issuance_create_v2")

        staff = get_object_or_404(Staff, id=staff_id)

        # Collect rows by index from POST keys like items[0][item_id], items[0][qty]
        row_map = {}  # {idx: {"item_id": "...", "qty": "..."}}

        for key, value in request.POST.items():
            m_item = ITEM_ID_KEY_RE.match(key)
            if m_item:
                idx = int(m_item.group(1))
                row_map.setdefault(idx, {})["item_id"] = value
                continue

            m_qty = QTY_KEY_RE.match(key)
            if m_qty:
                idx = int(m_qty.group(1))
                row_map.setdefault(idx, {})["qty"] = value
                continue

        if not row_map:
            messages.error(request, "Please add at least one item row.")
            return redirect("store:issuance_create_v2")

        items_with_qty = []
        # Sort indices so errors map to the row order the user sees
        for idx in sorted(row_map.keys()):
            item_id = (row_map[idx].get("item_id") or "").strip()
            qty_raw = (row_map[idx].get("qty") or "").strip()

            # If user added an empty row, treat it as an error (strict)
            if not item_id or not qty_raw:
                messages.error(request, f"Row {idx + 1}: Item and quantity are required.")
                return redirect("store:issuance_create_v2")

            # Validate qty
            try:
                qty = int(qty_raw)
            except ValueError:
                messages.error(request, f"Row {idx + 1}: Quantity must be a whole number.")
                return redirect("store:issuance_create_v2")

            if qty < 1:
                messages.error(request, f"Row {idx + 1}: Quantity must be at least 1.")
                return redirect("store:issuance_create_v2")

            items_with_qty.append({"item_id": item_id, "quantity": qty})

        try:
            create_issuance_service(
                staff=staff,
                issued_by=request.user,
                items_with_qty=items_with_qty,
                comment=comment,
            )
            messages.success(request, "Issuance saved successfully.")
            return redirect("store:issuance_create_v2")

        except IssuanceError as e:
            emit_failed_issuance_activity(actor=request.user, error=str(e))
            messages.error(request, str(e))
            return redirect("store:issuance_create_v2")

    # GET
    return render(
        request,
        "store/issuance_create_v2.html",  # ✅ use the template path you showed earlier
        {
            "active_nav": "issuance",
            "staff_list": Staff.objects.all().order_by("name"),
            "items_list": Item.objects.all().order_by("name"),
        },
    )