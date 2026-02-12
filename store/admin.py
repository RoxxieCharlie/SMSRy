from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    Department,
    Staff,
    Category,
    Item,
    StockIn,
    Issuance,
    IssuanceItem,
    StockInItem
)

from store.services.stockin_service import create_bulk_stockin
from store.services.issuance_service import create_issuance_service


# ===============================
# BASIC REGISTRATIONS
# ===============================

admin.site.register(Department)
admin.site.register(Staff)
admin.site.register(Category)
admin.site.register(Item)



# ===============================
# STOCK IN ADMIN
# ===============================




from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from store.models import StockIn, StockInItem
from store.services.stockin_service import create_bulk_stockin


class StockInLineInline(admin.TabularInline):
    model = StockInItem
    extra = 1


@admin.register(StockIn)
class StockInAdmin(admin.ModelAdmin):
    inlines = [StockInLineInline]
    readonly_fields = ("received_by", "received_at")

    def save_model(self, request, obj, form, change):
        """
        Prevent Django from saving StockIn directly.
        Creation must go through the service layer.
        """
        if change:
            raise ValidationError("Stock-in records cannot be edited.")

        # Intentionally do nothing.
        # Stock-in is created in save_related via the service layer.
        return

    def save_related(self, request, form, formsets, change):
        if change:
            return

        items_with_qty = []

        for formset in formsets:
            if formset.model is StockInItem:
                for f in formset.forms:
                    if not f.cleaned_data:
                        continue
                    if f.cleaned_data.get("DELETE"):
                        continue

                    item = f.cleaned_data.get("item")
                    quantity = f.cleaned_data.get("quantity")

                    if not item or not quantity:
                        continue

                    items_with_qty.append({
                        "item": item,
                        "quantity": quantity,
                    })

        if not items_with_qty:
            self.message_user(
                request,
                "At least one item is required for stock-in.",
                level=messages.ERROR,
            )
            return

        try:
            create_stockin(
                received_by=request.user,
                items_with_qty=items_with_qty,
                comment=form.instance.comment or "",
            )

            self.message_user(
                request,
                "Stock-in created successfully.",
                level=messages.SUCCESS,
            )

        except (ValueError, ValidationError) as e:
            self.message_user(request, str(e), level=messages.ERROR)







# ===============================
# ISSUANCE ADMIN
# ===============================

class IssuanceItemInline(admin.TabularInline):
    model = IssuanceItem
    extra = 1
    can_delete = True


@admin.register(Issuance)
class IssuanceAdmin(admin.ModelAdmin):
    inlines = [IssuanceItemInline]
    readonly_fields = ("issued_by", "issued_at")

    def save_model(self, request, obj, form, change):
        """
        Block Django from saving Issuance.
        The service will create it instead.
        """
        if change:
            raise ValidationError("Issuance records cannot be edited.")

        # DO NOTHING — intentional
        return

    def save_related(self, request, form, formsets, change):
        if change:
            return

        items_with_qty = []

        for formset in formsets:
            if formset.model is IssuanceItem:
                for f in formset.forms:
                    if not f.cleaned_data:
                        continue
                    if f.cleaned_data.get("DELETE"):
                        continue

                    item = f.cleaned_data.get("item")
                    quantity = f.cleaned_data.get("quantity")

                    if not item or not quantity:
                        continue

                    items_with_qty.append({
                        "item": item,
                        "quantity": quantity,
                    })

        if not items_with_qty:
            self.message_user(
                request,
                "At least one item is required for issuance.",
                level=messages.ERROR,
            )
            return



        try:
            create_issuance(
                staff=form.instance.staff,
                issued_by=request.user,
                items_with_qty=items_with_qty,
                comment=form.instance.comment or "",
            )

            self.message_user(
                request,
                "Issuance created successfully.",
                level=messages.SUCCESS,
            )

        except (ValueError, PermissionError, ValidationError) as e:
            self.message_user(request, str(e), level=messages.ERROR)
