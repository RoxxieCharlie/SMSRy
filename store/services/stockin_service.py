from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import models
from store.models import Item, StockIn, StockInItem, Activity
from store.services.activity_service import emit_activity


@transaction.atomic
def create_bulk_stockin(*, received_by, lines, comment="", received_at=None, document=None):
    """
    lines = [
        {"item_id": 1, "quantity": 5},
        {"item_id": 2, "quantity": 10},
    ]
    """
    if not lines:
        raise ValidationError("At least one item is required.")

    if received_at is None:
        received_at = timezone.now()

    seen_item_ids = set()
    normalized_lines = []

    # 1️⃣ VALIDATE + NORMALIZE INPUT (NO DB TOUCH)
    for line in lines:
        item_id = line.get("item_id")
        quantity = line.get("quantity")

        if item_id is None or quantity is None:
            raise ValidationError("Item and quantity are required.")

        try:
            item_id = int(item_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise ValidationError("Item ID and quantity must be integers.")

        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")

        if item_id in seen_item_ids:
            raise ValidationError(f"Duplicate item detected in stock-in (item_id={item_id}).")

        seen_item_ids.add(item_id)
        normalized_lines.append({"item_id": item_id, "quantity": quantity})

    # 2️⃣ LOCK ALL ITEMS AT ONCE
    items = Item.objects.select_for_update().filter(id__in=seen_item_ids)
    if items.count() != len(seen_item_ids):
        raise ValidationError("One or more items do not exist.")

    item_map = {item.id: item for item in items}

    # 3️⃣ CREATE STOCK-IN HEADER
    stockin = StockIn.objects.create(
        received_by=received_by,
        comment=comment,
        received_at = models.DateTimeField(default=timezone.now),
        document=document
    )

    # 4️⃣ CREATE STOCK-IN ITEMS + UPDATE QUANTITIES
    stockin_items = []
    for line in normalized_lines:
        item = item_map[line["item_id"]]
        quantity = line["quantity"]

        item.quantity += quantity
        item.save(update_fields=["quantity"])

        stockin_items.append(
            StockInItem(stockin=stockin, item=item, quantity=quantity)
        )

    StockInItem.objects.bulk_create(stockin_items)

    # 5️⃣ EMIT ACTIVITY AFTER SUCCESSFUL STOCK-IN
    try:
        emit_activity(
            actor=received_by,
            verb=Activity.Verb.STOCKIN_CREATED,
            target=stockin,
            summary=f"{received_by.get_full_name()} stocked in {len(stockin_items)} item(s)",
            metadata={
                "items": [
                    {"item_id": si.item.id, "item": si.item.name, "quantity": si.quantity}
                    for si in stockin_items
                ]
            }
        )
    except Exception as e:
        # Logging failure should NOT break stock-in
        print(f"[Activity Logging Error] {e}")

    return stockin
