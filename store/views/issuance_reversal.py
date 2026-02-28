from datetime import timedelta
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from store.decorators import group_required
from store.models import Issuance

@require_POST
@login_required
@group_required("StoreKeeper")
def issuance_reverse_view(request, issuance_id):
    issuance = get_object_or_404(Issuance, id=issuance_id, issued_by=request.user)

    if issuance.is_reversed:
        messages.info(request, "This issuance is already reversed.")
        return redirect("store:history_issuance_storekeeper_v2")

    cutoff = timezone.now() - timedelta(hours=6)
    if issuance.issued_at < cutoff:
        messages.error(request, "Reversal window expired. This issuance is locked.")
        return redirect("store:history_issuance_storekeeper_v2")

    issuance.is_reversed = True
    issuance.reversed_by = request.user
    issuance.reversed_at = timezone.now()
    issuance.save(update_fields=["is_reversed", "reversed_by", "reversed_at"])

    messages.success(request, "Issuance reversed successfully.")
    return redirect("store:history_issuance_storekeeper_v2")