from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from store.models import Issuance, Activity
from store.services.activity_service import emit_activity

def issuance_reverse_view(request, issuance_id):
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("history_issuance_storekeeper")

    issuance = get_object_or_404(Issuance, id=issuance_id)

    if not issuance.can_reverse:
        messages.error(request, "Cannot reverse this issuance (time window expired or already reversed).")
        return redirect("history_issuance_storekeeper")

    # Reverse items
    for line in issuance.items.all():
        line.item.quantity += line.quantity
        line.item.save(update_fields=["quantity"])

    issuance.is_reversed = True
    issuance.reversed_at = timezone.now()
    issuance.reversed_by = request.user
    issuance.save(update_fields=["is_reversed", "reversed_at", "reversed_by"])

    # Emit activity
    emit_activity(
        actor=request.user,
        verb=Activity.Verb.ISSUANCE_REVERSED,
        target=issuance,
        summary=f"{request.user.get_full_name()} reversed Issuance #{issuance.id} for {issuance.staff.name}",
        metadata={
            "staff_id": issuance.staff.id,
            "staff_name": issuance.staff.name,
            "department": issuance.staff.department.name if issuance.staff.department else "",
            "items": [{"item_id": i.item.id, "item": i.item.name, "quantity": i.quantity} for i in issuance.items.all()]
        }
    )

    messages.success(request, "Issuance reversed successfully.")
    return redirect("history_issuance_storekeeper")
