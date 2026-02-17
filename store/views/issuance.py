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


@login_required
@storekeeper_required
def issuance_create(request):

    if request.method == "POST":
        staff_id = request.POST.get("staff")
        item_ids = request.POST.getlist("item[]")
        quantities = request.POST.getlist("quantity[]")
        comment = request.POST.get("comment", "")

        if not staff_id:
            messages.error(request, "Staff is required.")
            return redirect("store:issuance_create")

        staff = get_object_or_404(Staff, id=staff_id)

        items_with_qty = []

        for idx, (item_id, qty) in enumerate(zip(item_ids, quantities), start=1):
            if not item_id or not qty:
                messages.error(request, f"Row {idx}: Item and quantity required.")
                return redirect("store:issuance_create")

            items_with_qty.append({
                "item_id": item_id,
                "quantity": qty
            })

        try:
            create_issuance_service(
                staff=staff,
                issued_by=request.user,
                items_with_qty=items_with_qty,
                comment=comment,
            )

            messages.success(request, "Issuance saved successfully.")
            return redirect("store:issuance_create")

        except IssuanceError as e:
            emit_failed_issuance_activity(actor=request.user, error=str(e))
            messages.error(request, str(e))
            return redirect("store:issuance_create")

    return render(
        request,
        "store/issuance_create.html",
        {
            "staff_list": Staff.objects.all().order_by("name"),
            "items": Item.objects.order_by("name"),
        },
    )



@login_required
@storekeeper_required
def reverse_issuance(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden("POST only")

    issuance = get_object_or_404(Issuance, pk=pk)

    try:
        reverse_issuance(issuance, request.user)
        #messages.success(request, "Issuance reversed successfully.")

    except ValidationError as e:
        if hasattr(e, "messages"):
            for msg in e.messages:
                messages.error(request, msg)
        else:
            messages.error(request, str(e))

    return redirect("store:issuance_history")
