from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db import models
from store.decorators import group_required
from store.models import Item
from store.services.stockin_service import create_bulk_stockin


@login_required
@group_required("StoreKeeper")
def stockin_view(request):
    if request.method == "POST":
        item_ids = request.POST.getlist("item[]")
        quantities = request.POST.getlist("quantity[]")
        comment = request.POST.get("comment", "")
        document = request.FILES.get("document")  # 🔴 THIS WAS MISSING

        lines = []

        for item_id, qty in zip(item_ids, quantities):
            if not item_id or not qty:
                continue

            lines.append({
                "item_id": int(item_id),
                "quantity": int(qty),
            })

        if not lines:
            messages.error(request, "Add at least one item.")
            return redirect("store:stockin")

        try:
            create_bulk_stockin(
                received_by=request.user,
                lines=lines,
                comment=comment,
                document=document,  # 🔴 PASS FILE DOWN
            )
            messages.success(request, "Stock-In saved successfully.")
            return redirect("store:stockin")

        except Exception as e:
            messages.error(request, str(e))
            return redirect("store:stockin")

    return render(
        request,
        "store/stockin.html",
        {"items": Item.objects.order_by("name")}
    )
