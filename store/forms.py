from django import forms
from django.core.exceptions import ValidationError

from store.models import Item, Request, RequestItem


# =========================
# STAFF REQUEST FORMS
# =========================

class RequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = ["purpose"]
        widgets = {
            "purpose": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "State why these materials are needed...",
                }
            )
        }


class RequestItemForm(forms.Form):
    item = forms.ModelChoiceField(
        queryset=Item.objects.all().order_by("name"),
        empty_label="Select item",
    )
    requested_qty = forms.IntegerField(min_value=1)

    def clean_requested_qty(self):
        qty = self.cleaned_data["requested_qty"]
        if qty <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        return qty


class BaseRequestItemFormSet(forms.BaseFormSet):
    def clean(self):
        if any(self.errors):
            return

        seen_items = set()
        non_deleted_count = 0

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            item = form.cleaned_data.get("item")
            requested_qty = form.cleaned_data.get("requested_qty")

            if not item or requested_qty in (None, ""):
                continue

            non_deleted_count += 1

            if item.id in seen_items:
                raise ValidationError(f"Duplicate item selected: {item.name}")

            seen_items.add(item.id)

        if non_deleted_count == 0:
            raise ValidationError("Add at least one item.")


RequestItemFormSet = forms.formset_factory(
    RequestItemForm,
    formset=BaseRequestItemFormSet,
    extra=1,
    can_delete=True,
)


# =========================
# STORE FULFILLMENT FORMS
# =========================

class FulfillmentLineForm(forms.Form):
    request_item_id = forms.IntegerField(widget=forms.HiddenInput())
    item_name = forms.CharField(required=False, disabled=True)
    requested_qty = forms.IntegerField(required=False, disabled=True)
    fulfilled_qty = forms.IntegerField(min_value=0)

    def __init__(self, *args, request_item=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_item = request_item

        if request_item is not None:
            self.fields["request_item_id"].initial = request_item.id
            self.fields["item_name"].initial = request_item.item.name
            self.fields["requested_qty"].initial = request_item.requested_qty
            self.fields["fulfilled_qty"].initial = request_item.requested_qty

    def clean(self):
        cleaned = super().clean()

        fulfilled_qty = cleaned.get("fulfilled_qty")
        request_item_id = cleaned.get("request_item_id")

        if request_item_id in (None, ""):
            raise ValidationError("Invalid request item.")

        if self.request_item is None:
            raise ValidationError("Request item context is missing.")

        if fulfilled_qty is None:
            raise ValidationError("Fulfilled quantity is required.")

        if fulfilled_qty < 0:
            raise ValidationError("Fulfilled quantity cannot be negative.")

        if fulfilled_qty > self.request_item.requested_qty:
            raise ValidationError(
                f"Fulfilled quantity for {self.request_item.item.name} "
                f"cannot exceed requested quantity ({self.request_item.requested_qty})."
            )

        return cleaned


class BaseFulfillmentFormSet(forms.BaseFormSet):
    def __init__(self, *args, request_obj=None, **kwargs):
        self.request_obj = request_obj
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)

        if self.request_obj is not None:
            request_items = list(self.request_obj.items.select_related("item").all())
            if 0 <= index < len(request_items):
                kwargs["request_item"] = request_items[index]

        return kwargs

    def clean(self):
        if any(self.errors):
            return

        if self.request_obj is None:
            raise ValidationError("Request context is required.")

        forms_count = 0
        request_item_ids = set()

        actual_ids = set(self.request_obj.items.values_list("id", flat=True))

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            request_item_id = form.cleaned_data.get("request_item_id")
            fulfilled_qty = form.cleaned_data.get("fulfilled_qty")

            if request_item_id in (None, "") or fulfilled_qty is None:
                continue

            forms_count += 1

            if request_item_id in request_item_ids:
                raise ValidationError("Duplicate request item submitted.")

            request_item_ids.add(int(request_item_id))

        if forms_count == 0:
            raise ValidationError("No fulfillment lines were submitted.")

        if request_item_ids != actual_ids:
            raise ValidationError("All request items must be included in fulfillment.")


FulfillmentFormSet = forms.formset_factory(
    FulfillmentLineForm,
    formset=BaseFulfillmentFormSet,
    extra=0,
    can_delete=False,
)


# =========================
# ISSUANCE EDIT FORMS
# =========================

class IssuanceEditLineForm(forms.Form):
    request_item_id = forms.IntegerField(widget=forms.HiddenInput())
    item_name = forms.CharField(required=False, disabled=True)
    requested_qty = forms.IntegerField(required=False, disabled=True)
    current_fulfilled_qty = forms.IntegerField(required=False, disabled=True)
    fulfilled_qty = forms.IntegerField(min_value=0)

    def __init__(self, *args, request_item=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_item = request_item

        if request_item is not None:
            self.fields["request_item_id"].initial = request_item.id
            self.fields["item_name"].initial = request_item.item.name
            self.fields["requested_qty"].initial = request_item.requested_qty
            self.fields["current_fulfilled_qty"].initial = request_item.fulfilled_qty
            self.fields["fulfilled_qty"].initial = request_item.fulfilled_qty

    def clean(self):
        cleaned = super().clean()

        fulfilled_qty = cleaned.get("fulfilled_qty")

        if self.request_item is None:
            raise ValidationError("Request item context is missing.")

        if fulfilled_qty is None:
            raise ValidationError("Updated quantity is required.")

        if fulfilled_qty < 0:
            raise ValidationError("Updated quantity cannot be negative.")

        if fulfilled_qty > self.request_item.requested_qty:
            raise ValidationError(
                f"Updated quantity for {self.request_item.item.name} "
                f"cannot exceed requested quantity ({self.request_item.requested_qty})."
            )

        return cleaned


class BaseIssuanceEditFormSet(forms.BaseFormSet):
    def __init__(self, *args, request_obj=None, **kwargs):
        self.request_obj = request_obj
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)

        if self.request_obj is not None:
            request_items = list(self.request_obj.items.select_related("item").all())
            if 0 <= index < len(request_items):
                kwargs["request_item"] = request_items[index]

        return kwargs

    def clean(self):
        if any(self.errors):
            return

        if self.request_obj is None:
            raise ValidationError("Request context is required.")

        submitted_ids = set()
        actual_ids = set(self.request_obj.items.values_list("id", flat=True))

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            request_item_id = form.cleaned_data.get("request_item_id")
            fulfilled_qty = form.cleaned_data.get("fulfilled_qty")

            if request_item_id in (None, "") or fulfilled_qty is None:
                continue

            request_item_id = int(request_item_id)

            if request_item_id in submitted_ids:
                raise ValidationError("Duplicate request item submitted.")

            submitted_ids.add(request_item_id)

        if submitted_ids != actual_ids:
            raise ValidationError("All existing request items must be included.")


IssuanceEditFormSet = forms.formset_factory(
    IssuanceEditLineForm,
    formset=BaseIssuanceEditFormSet,
    extra=0,
    can_delete=False,
)


class IssuanceEditReasonForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "State why the fulfilled quantities are being changed...",
            }
        )
    )

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise ValidationError("Edit reason is required.")
        return reason