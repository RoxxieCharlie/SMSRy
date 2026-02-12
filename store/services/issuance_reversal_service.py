from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from store.models import Issuance, Item


@transaction.atomic
def reverse_issuance(*, issuance_id, reversed_by):
    issuance = (
        Issuance.objects
        .select_for_update()
        .prefetch_related("items__item")
        .get(id=issuance_id)
    )

    if issuance.is_reversed:
        raise ValidationError("This issuance has already been reversed.")

    if not issuance.can_reverse:
        raise ValidationError("Reversal window has expired.")

    # Return items to stock
    for line in issuance.items.all():
        item = line.item
        item.quantity += line.quantity
        item.save(update_fields=["quantity"])

    issuance.is_reversed = True
    issuance.reversed_at = timezone.now()
    issuance.reversed_by = reversed_by
    issuance.save(
        update_fields=["is_reversed", "reversed_at", "reversed_by"]
    )
