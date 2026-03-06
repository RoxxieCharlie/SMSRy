from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    Department,
    Staff,
    Category,
    Item,
    StockIn,
    StockInItem,
    Issuance,
    IssuanceItem,
    Request,
    RequestItem,
    RequestActivity,
)

from store.services.stockin_service import create_bulk_stockin


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
            create_bulk_stockin(
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
# REQUEST ADMIN
# ===============================

class RequestItemInline(admin.TabularInline):
    model = RequestItem
    extra = 0
    readonly_fields = ("requested_qty", "fulfilled_qty")


class RequestActivityInline(admin.TabularInline):
    model = RequestActivity
    extra = 0
    readonly_fields = (
        "actor",
        "action",
        "description",
        "created_at",
    )
    can_delete = False


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "requester",
        "status",
        "created_at",
        "submitted_at",
        "fulfilled_at",
    )

    list_filter = ("status", "created_at")

    search_fields = (
        "requester__name",
        "requester__staff_id",
    )

    readonly_fields = (
        "status",
        "created_at",
        "submitted_at",
        "fulfilled_at",
        "editable_until",
        "fulfilled_by",
        "last_edited_by",
    )

    inlines = [
        RequestItemInline,
        RequestActivityInline,
    ]

    def has_add_permission(self, request):
        return False  # Requests are created from the app, not admin


# ===============================
# ISSUANCE ADMIN (READ ONLY)
# ===============================

class IssuanceItemInline(admin.TabularInline):
    model = IssuanceItem
    extra = 0
    readonly_fields = ("item", "quantity")
    can_delete = False


@admin.register(Issuance)
class IssuanceAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "staff",
        "issued_by",
        "issued_at",
    )

    readonly_fields = (
        "request",
        "staff",
        "issued_by",
        "issued_at",
        "comment",
    )

    inlines = [IssuanceItemInline]

    def has_add_permission(self, request):
        """
        Issuances must only be created from fulfilled requests.
        """
        return False

    def has_change_permission(self, request, obj=None):
        return False