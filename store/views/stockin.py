from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from store.decorators import group_required
from store.models import Item
from store.services.stockin_service import create_bulk_stockin


@login_required
@group_required("StoreKeeper")
def stockin_view(request):
    if request.method == "POST":
        comment = request.POST.get("comment", "").strip()
        document = request.FILES.get("document")

        lines = []
        index = 0

        # Parse the dynamic rows created by your JS:
        # items[0][item_id], items[0][qty], items[1][item_id], items[1][qty], ...
        while True:
            item_id = request.POST.get(f"items[{index}][item_id]")
            qty = request.POST.get(f"items[{index}][qty]")

            # When there is no next row, stop.
            if item_id is None and qty is None:
                break

            # Skip incomplete rows (but keep scanning)
            if not item_id or not qty:
                index += 1
                continue

            try:
                item_id_int = int(item_id)
                qty_int = int(qty)
            except (TypeError, ValueError):
                messages.error(request, "Invalid item or quantity value.")
                return redirect("store:stockin_v2")

            if qty_int < 1:
                messages.error(request, "Quantity must be at least 1.")
                return redirect("store:stockin_v2")

            lines.append({
                "item_id": item_id_int,
                "quantity": qty_int,
            })

            index += 1

        if not lines:
            messages.error(request, "Add at least one item.")
            return redirect("store:stockin_v2")

        try:
            create_bulk_stockin(
                received_by=request.user,
                lines=lines,
                comment=comment,
                document=document,
            )
            messages.success(request, "Stock-In saved successfully.")
            return redirect("store:stockin_v2")

        except Exception as e:
            messages.error(request, str(e))
            return redirect("store:stockin_v2")

    # GET: show items in dropdown
    items_list = Item.objects.all().order_by("name")
    return render(request, "store/stockin_v2.html", {"items_list": items_list})