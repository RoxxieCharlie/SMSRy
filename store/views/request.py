from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db import transaction
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from store.forms import (
    FulfillmentFormSet,
    IssuanceEditFormSet,
    IssuanceEditReasonForm,
    RequestForm,
    RequestItemFormSet,
    StorekeeperRequestItemFormSet,
)
from store.models import Activity, Department, Item, Request, RequestActivity, RequestItem, Staff
from store.services.activity_service import emit_activity
from store.services.issuance_service import IssuanceError, edit_issuance_service, fulfill_request_service


def _is_in_group(user, name):
    return user.groups.filter(name__iexact=name).exists()


def _is_storekeeper(user):
    return _is_in_group(user, "StoreKeeper")


def _is_requester_role(user):
    return _is_in_group(user, "Staff") or _is_in_group(user, "Management")


def _can_access_request_workspace(user):
    return _is_requester_role(user) or _is_storekeeper(user)


def _request_base_template(user):
    if _is_storekeeper(user):
        return "store/base_v2.html"
    if _is_in_group(user, "Management"):
        return "store/mgt_base_v2.html"
    return "store/staff_base_v2.html"


def _get_staff_for_user(user, *, required=False):
    try:
        return Staff.objects.select_related("department").get(user=user)
    except Staff.DoesNotExist:
        if required and _is_requester_role(user):
            department, _ = Department.objects.get_or_create(name="General")
            base_prefix = "MGT" if _is_in_group(user, "Management") else "STF"
            base_id = f"{base_prefix}{user.id or 0:04d}"
            staff_id = base_id
            idx = 1
            while Staff.objects.filter(staff_id=staff_id).exists():
                staff_id = f"{base_id}-{idx}"
                idx += 1

            role = "project manager" if _is_in_group(user, "Management") else "worker"
            return Staff.objects.create(
                user=user,
                staff_id=staff_id,
                name=user.get_full_name() or user.username,
                department=department,
                job_roles=role,
            )

        if required:
            raise Http404("No staff profile is linked to this user.")
        return None


def _requester_meta_for_staff(staff, user):
    if staff is None:
        return {
            "name": user.get_full_name() or user.username,
            "staff_id": "-",
            "department": "-",
            "role": "-",
        }

    return {
        "name": staff.name,
        "staff_id": staff.staff_id,
        "department": staff.department.name if staff.department else "-",
        "role": staff.get_job_roles_display() if staff.job_roles else "-",
    }


def _serialize_request_items(request_obj):
    return [
        {"item": request_item.item, "requested_qty": request_item.requested_qty}
        for request_item in request_obj.items.select_related("item").all()
    ]


def _serialize_fulfillment_items(request_obj):
    return [
        {
            "request_item_id": request_item.id,
            "item_name": request_item.item.name,
            "requested_qty": request_item.requested_qty,
            "fulfilled_qty": request_item.requested_qty,
        }
        for request_item in request_obj.items.select_related("item").all()
    ]


def _recent_activity_for_requester(staff, *, request_obj=None, limit=8):
    qs = RequestActivity.objects.select_related("actor", "request")
    if request_obj is not None:
        qs = qs.filter(request=request_obj)
    else:
        qs = qs.filter(request__requester=staff)
    return qs.order_by("-created_at")[:limit]


def _recent_activity_for_storekeeper(limit=8):
    return (
        RequestActivity.objects.select_related("actor", "request", "request__requester")
        .filter(
            action__in=[
                RequestActivity.Action.SUBMITTED,
                RequestActivity.Action.FULFILLED,
                RequestActivity.Action.STORE_EDITED,
                RequestActivity.Action.FULFILLMENT_EDITED,
            ]
        )
        .order_by("-created_at")[:limit]
    )


@login_required
@transaction.atomic
def request_create(request):
    if not _can_access_request_workspace(request.user):
        return HttpResponseForbidden("You do not have access to request pages.")
    if _is_storekeeper(request.user):
        return HttpResponseForbidden("Storekeepers cannot create requests.")

    staff = _get_staff_for_user(request.user, required=True)
    requester_meta = _requester_meta_for_staff(staff, request.user)

    if request.method == "POST":
        form = RequestForm(request.POST)
        formset = RequestItemFormSet(request.POST, prefix="items")
        submit_now = (request.POST.get("action") or "").strip().lower() == "submit"

        if form.is_valid() and formset.is_valid():
            request_obj = form.save(commit=False)
            request_obj.requester = staff
            request_obj.status = Request.Status.SUBMITTED if submit_now else Request.Status.DRAFT
            request_obj.submitted_at = timezone.now() if submit_now else None
            request_obj.needs_resubmission = False
            request_obj.last_edited_by = request.user
            request_obj.save()

            request_items = []
            for item_form in formset:
                if not item_form.cleaned_data or item_form.cleaned_data.get("DELETE"):
                    continue

                request_item = RequestItem.objects.create(
                    request=request_obj,
                    item=item_form.cleaned_data["item"],
                    requested_qty=item_form.cleaned_data["requested_qty"],
                    original_requested_qty=item_form.cleaned_data["requested_qty"],
                )
                request_items.append(request_item)

            RequestActivity.objects.create(
                request=request_obj,
                actor=request.user,
                action=RequestActivity.Action.CREATED,
                description=f"Request created by {request.user.get_full_name() or request.user.username}.",
                metadata={
                    "items": [
                        {
                            "item_id": line.item_id,
                            "item_name": line.item.name,
                            "requested_qty": line.requested_qty,
                        }
                        for line in request_items
                    ]
                },
            )

            if submit_now:
                RequestActivity.objects.create(
                    request=request_obj,
                    actor=request.user,
                    action=RequestActivity.Action.SUBMITTED,
                    description=f"Request submitted by {request.user.get_full_name() or request.user.username}.",
                    metadata={},
                )

            emit_activity(
                actor=request.user,
                verb=Activity.Verb.REQUEST_CREATED,
                target=request_obj,
                summary=f"{requester_meta['name']} created Request #{request_obj.id}",
                metadata={
                    "request_id": request_obj.id,
                    "staff_id": staff.id,
                    "staff_name": staff.name,
                    "department": staff.department.name if staff.department else "",
                },
            )

            if submit_now:
                emit_activity(
                    actor=request.user,
                    verb=Activity.Verb.REQUEST_SUBMITTED,
                    target=request_obj,
                    summary=f"{staff.name} submitted Request #{request_obj.id}",
                    metadata={
                        "request_id": request_obj.id,
                        "staff_id": staff.id,
                        "staff_name": staff.name,
                        "department": staff.department.name if staff.department else "",
                    },
                )

            messages.success(
                request,
                "Request submitted successfully." if submit_now else "Request created successfully.",
            )
            return redirect("store:request_edit", request_id=request_obj.id)
    else:
        form = RequestForm()
        formset = RequestItemFormSet(prefix="items")

    return render(
        request,
        "store/requests/request_form.html",
        {
            "form": form,
            "formset": formset,
            "request_obj": None,
            "requester_meta": requester_meta,
            "request_status": Request.Status.DRAFT,
            "submit_label": "Save Draft",
            "can_submit": True,
            "recent_activities": _recent_activity_for_requester(staff, limit=6),
            "page_title": "New Request",
            "base_template": _request_base_template(request.user),
            "can_add_items": True,
            "is_storekeeper_editor": False,
            "staff": staff,
        },
    )


@login_required
@transaction.atomic
def request_edit(request, request_id):
    if not _can_access_request_workspace(request.user):
        return HttpResponseForbidden("You do not have access to request pages.")

    is_storekeeper = _is_storekeeper(request.user)
    next_url = request.POST.get("next") or request.GET.get("next") or request.META.get("HTTP_REFERER") or reverse("store:request_list")
    requester_staff = None if is_storekeeper else _get_staff_for_user(request.user, required=True)

    request_obj = get_object_or_404(
        Request.objects.select_related("requester", "requester__department"),
        pk=request_id,
    )

    if not is_storekeeper and request_obj.requester_id != requester_staff.id:
        raise Http404("You do not have permission to edit this request.")

    is_owner = (not is_storekeeper) and request_obj.requester_id == requester_staff.id
    is_storekeeper_editor = is_storekeeper and request_obj.status == Request.Status.SUBMITTED
    is_read_only = (is_owner or is_storekeeper) and request_obj.status in [Request.Status.FULFILLED, Request.Status.LOCKED]


    if is_storekeeper and request.method == "POST" and request_obj.status != Request.Status.SUBMITTED:
        messages.error(request, "This request is no longer editable from the request page.")
        return redirect("store:request_edit", request_id=request_obj.id)

    if request.method == "POST" and is_read_only:
        messages.error(request, "This fulfilled request is read-only for staff.")
        return redirect("store:request_edit", request_id=request_obj.id)

    if not is_storekeeper and not request_obj.can_staff_edit and not is_read_only:
        messages.error(request, "This request can no longer be edited.")
        return redirect("store:request_list")

    existing_items = _serialize_request_items(request_obj)

    if request.method == "POST":
        old_purpose = request_obj.purpose or ""
        should_fulfill = (
            is_storekeeper_editor
            and request_obj.status == Request.Status.SUBMITTED
            and request.POST.get("action") == "fulfill"
        )
        store_note = (request.POST.get("store_note") or request_obj.store_note or "").strip() if is_storekeeper_editor else request_obj.store_note
        old_items = list(request_obj.items.select_related("item").all())
        old_items_map = {row.item_id: row.requested_qty for row in old_items}
        old_original_map = {row.item_id: row.original_requested_qty for row in old_items}
        historical_cap_map = _historical_requested_qty_cap_map(request_obj) if is_storekeeper_editor else {}
        effective_cap_map = {
            item_id: max(
                old_items_map.get(item_id, 0),
                old_original_map.get(item_id, 0),
                historical_cap_map.get(item_id, 0),
            )
            for item_id in old_items_map.keys()
        }
        old_item_ids = set(old_items_map.keys())
        item_name_map = {row.item_id: row.item.name for row in old_items}

        form_data = request.POST
        if is_storekeeper_editor:
            # Storekeeper cannot edit purpose on request edit page.
            form_data = request.POST.copy()
            form_data["purpose"] = old_purpose

        form = RequestForm(form_data, instance=request_obj)
        formset = (StorekeeperRequestItemFormSet if is_storekeeper_editor else RequestItemFormSet)(request.POST, prefix="items")

        if is_storekeeper_editor:
            for item_form in formset:
                item_form.fields["requested_qty"].widget.attrs.update({"min": 1, "step": 1, "inputmode": "numeric"})
                item_value = item_form.data.get(item_form.add_prefix("item"))
                item_obj = Item.objects.filter(pk=item_value).first() if item_value else None
                item_form.item_label = item_obj.name if item_obj else "-"
                item_form.in_stock = item_obj.quantity if item_obj else 0
                item_form.display_requested_qty = item_form.data.get(item_form.add_prefix("requested_qty"))
                item_form.override_requested_qty = None

        if form.is_valid() and formset.is_valid():
            posted_items = []
            for item_form in formset:
                if not item_form.cleaned_data or item_form.cleaned_data.get("DELETE"):
                    continue
                posted_items.append(
                    {
                        "item": item_form.cleaned_data["item"],
                        "requested_qty": item_form.cleaned_data["requested_qty"],
                    }
                )

            if is_storekeeper_editor:
                new_item_ids = {line["item"].id for line in posted_items}
                added_item_ids = new_item_ids - old_item_ids
                if added_item_ids:
                    form.add_error(None, "Storekeeper cannot add new items to an existing request.")

                for line in posted_items:
                    item = line["item"]
                    new_qty = line["requested_qty"]
                    max_allowed_qty = effective_cap_map.get(item.id, old_items_map.get(item.id, 0))
                    if new_qty > max_allowed_qty:
                        form.add_error(
                            None,
                            f"{item.name} cannot exceed original requested quantity ({max_allowed_qty}).",
                        )
                        for item_form in formset:
                            cleaned_item = item_form.cleaned_data.get("item") if hasattr(item_form, "cleaned_data") else None
                            if cleaned_item and cleaned_item.id == item.id:
                                item_form.override_requested_qty = old_items_map.get(item.id, "")
                                break

            if not form.errors:
                savepoint_id = transaction.savepoint() if should_fulfill else None
                request_obj = form.save(commit=False)
                if is_storekeeper_editor:
                    request_obj.purpose = old_purpose
                    request_obj.store_note = store_note
                request_obj.last_edited_by = request.user
                request_obj.save()

                request_obj.items.all().delete()

                new_items = []
                for line in posted_items:
                    request_item = RequestItem.objects.create(
                        request=request_obj,
                        item=line["item"],
                        requested_qty=line["requested_qty"],
                    )
                    if is_storekeeper_editor:
                        request_item.original_requested_qty = effective_cap_map.get(
                            request_item.item_id,
                            max(request_item.requested_qty, old_items_map.get(request_item.item_id, 0)),
                        )
                    else:
                        request_item.original_requested_qty = request_item.requested_qty
                    request_item.save(update_fields=["original_requested_qty"])
                    new_items.append(request_item)
                    item_name_map[line["item"].id] = line["item"].name

                changes = []
                new_items_map = {row.item_id: row.requested_qty for row in new_items}
                all_item_ids = set(old_items_map.keys()) | set(new_items_map.keys())

                new_purpose = request_obj.purpose or ""
                if old_purpose != new_purpose:
                    changes.append(
                        {
                            "field": "purpose",
                            "old_value": old_purpose,
                            "new_value": new_purpose,
                        }
                    )

                for item_id in all_item_ids:
                    old_qty = old_items_map.get(item_id)
                    new_qty = new_items_map.get(item_id)
                    if old_qty != new_qty:
                        changes.append(
                            {
                                "item_id": item_id,
                                "item_name": item_name_map.get(item_id, f"Item {item_id}"),
                                "old_qty": old_qty,
                                "new_qty": new_qty,
                            }
                        )

                if request_obj.status == Request.Status.SUBMITTED and changes and not is_storekeeper_editor:
                    request_obj.needs_resubmission = True
                    request_obj.save(update_fields=["needs_resubmission", "updated_at"])

                action = RequestActivity.Action.STORE_EDITED if is_storekeeper_editor else RequestActivity.Action.STAFF_EDITED

                RequestActivity.objects.create(
                    request=request_obj,
                    actor=request.user,
                    action=action,
                    description=f"Request edited by {request.user.get_full_name() or request.user.username}.",
                    metadata={"changes": changes},
                )

                emit_activity(
                    actor=request.user,
                    verb=Activity.Verb.REQUEST_UPDATED,
                    target=request_obj,
                    summary=f"Request #{request_obj.id} was updated",
                    metadata={"changes": changes},
                )

                if should_fulfill:
                    try:
                        fulfill_request_service(
                            request_obj=request_obj,
                            issued_by=request.user,
                            items_with_qty=[
                                {
                                    "request_item_id": row.id,
                                    "fulfilled_qty": row.requested_qty,
                                }
                                for row in new_items
                            ],
                            comment=store_note,
                        )
                    except IssuanceError as exc:
                        transaction.savepoint_rollback(savepoint_id)
                        messages.error(request, str(exc))
                    else:
                        transaction.savepoint_commit(savepoint_id)
                        messages.success(request, f"Request #{request_obj.id} fulfilled successfully.")
                        return redirect("store:request_edit", request_id=request_obj.id)
                else:
                    messages.success(request, "Request updated successfully.")
                    return redirect(next_url)

            else:
                for err in form.non_field_errors():
                    messages.error(request, err)

        else:
            for err in form.non_field_errors():
                messages.error(request, err)
            for field_name, error_list in form.errors.items():
                if field_name == "__all__":
                    continue
                for err in error_list:
                    messages.error(request, err)
            for form_errors in formset.errors:
                for field_name, error_list in form_errors.items():
                    for err in error_list:
                        messages.error(request, err)
            for err in formset.non_form_errors():
                messages.error(request, err)
    else:
        form = RequestForm(instance=request_obj)
        formset = (StorekeeperRequestItemFormSet if is_storekeeper_editor else RequestItemFormSet)(initial=existing_items, prefix="items")

        if is_storekeeper_editor:
            for item_form in formset:
                item_form.fields["requested_qty"].widget.attrs.update({"min": 1, "step": 1, "inputmode": "numeric"})
                item_value = item_form.initial.get("item") if item_form.initial else None
                item_form.display_requested_qty = item_form.initial.get("requested_qty") if item_form.initial else ""
                item_form.override_requested_qty = None
                item_obj = item_value if hasattr(item_value, "id") else (Item.objects.filter(pk=item_value).first() if item_value else None)
                item_form.item_label = item_obj.name if item_obj else "-"
                item_form.in_stock = item_obj.quantity if item_obj else 0

    store_note_value = store_note if request.method == "POST" else request_obj.store_note
    return render(
        request,
        "store/requests/request_form.html",
        {
            "form": form,
            "formset": formset,
            "request_obj": request_obj,
            "requester_meta": _requester_meta_for_staff(request_obj.requester, request_obj.requester.user),
            "request_status": request_obj.status,
            "submit_label": ("Save Changes" if is_storekeeper_editor else ("Save Draft" if not is_read_only else "View Only")),
            "can_submit": is_owner and request_obj.can_staff_submit,
            "recent_activities": (
                _recent_activity_for_storekeeper(limit=8)
                if is_storekeeper_editor
                else _recent_activity_for_requester(request_obj.requester, request_obj=request_obj, limit=8)
            ),
            "page_title": "Request Details" if is_read_only else "Edit Request",
            "is_read_only": is_read_only,
            "request_items": request_obj.items.select_related("item").all(),
            "base_template": _request_base_template(request.user),
            "can_add_items": not is_storekeeper_editor,
            "is_storekeeper_editor": is_storekeeper_editor,
            "staff": request_obj.requester,
            "next_url": next_url,
            "store_note": store_note_value,
            "modal_redirect_url": next_url if (request.method == "POST" and not is_storekeeper_editor and not form.errors and not formset.errors) else "",
        },
    )


@login_required
@transaction.atomic
def request_submit(request, request_id):
    if not _can_access_request_workspace(request.user):
        return HttpResponseForbidden("You do not have access to request pages.")
    if _is_storekeeper(request.user):
        return HttpResponseForbidden("Storekeepers cannot submit requests.")
    if request.method != "POST":
        return redirect("store:request_list")

    staff = _get_staff_for_user(request.user, required=True)

    request_obj = get_object_or_404(
        Request.objects.select_related("requester", "requester__department"),
        pk=request_id,
        requester=staff,
    )

    if request_obj.status not in [Request.Status.DRAFT, Request.Status.SUBMITTED]:
        messages.error(request, "Only draft or editable submitted requests can be submitted.")
        return redirect("store:request_edit", request_id=request_obj.id)

    if request_obj.status == Request.Status.SUBMITTED and not request_obj.needs_resubmission:
        messages.info(request, "Request already submitted. Edit it to enable re-submission.")
        return redirect("store:request_edit", request_id=request_obj.id)

    if not request_obj.items.exists():
        messages.error(request, "You must add at least one item before submitting.")
        return redirect("store:request_edit", request_id=request_obj.id)

    request_obj.status = Request.Status.SUBMITTED
    request_obj.submitted_at = timezone.now()
    request_obj.needs_resubmission = False
    request_obj.last_edited_by = request.user
    request_obj.save(update_fields=["status", "submitted_at", "needs_resubmission", "last_edited_by", "updated_at"])

    RequestActivity.objects.create(
        request=request_obj,
        actor=request.user,
        action=RequestActivity.Action.SUBMITTED,
        description=f"Request submitted by {request.user.get_full_name() or request.user.username}.",
        metadata={},
    )

    emit_activity(
        actor=request.user,
        verb=Activity.Verb.REQUEST_SUBMITTED,
        target=request_obj,
        summary=f"{staff.name} submitted Request #{request_obj.id}",
        metadata={
            "request_id": request_obj.id,
            "staff_id": staff.id,
            "staff_name": staff.name,
            "department": staff.department.name if staff.department else "",
        },
    )

    messages.success(request, "Request submitted successfully.")
    return redirect("store:request_list")


@login_required
@transaction.atomic
def request_fulfill(request, request_id):
    if not _is_storekeeper(request.user):
        raise Http404("Only store-keepers can fulfill requests.")

    request_obj = get_object_or_404(
        Request.objects.select_related("requester", "requester__department"),
        pk=request_id,
    )

    if request_obj.status != Request.Status.SUBMITTED:
        messages.error(request, "Only submitted requests can be fulfilled.")
        return redirect("store:request_list")

    if not request_obj.items.exists():
        messages.error(request, "This request has no items to fulfill.")
        return redirect("store:request_list")

    initial_lines = _serialize_fulfillment_items(request_obj)

    if request.method == "POST":
        formset = FulfillmentFormSet(
            request.POST,
            prefix="lines",
            request_obj=request_obj,
            initial=initial_lines,
        )
        comment = (request.POST.get("comment") or "").strip()

        if formset.is_valid():
            items_with_qty = [
                {
                    "request_item_id": form.cleaned_data["request_item_id"],
                    "fulfilled_qty": form.cleaned_data["fulfilled_qty"],
                }
                for form in formset.forms
                if hasattr(form, "cleaned_data") and form.cleaned_data
            ]

            try:
                fulfill_request_service(
                    request_obj=request_obj,
                    issued_by=request.user,
                    items_with_qty=items_with_qty,
                    comment=comment,
                )
            except IssuanceError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Request #{request_obj.id} fulfilled successfully.")
                return redirect("store:request_edit", request_id=request_obj.id)
    else:
        formset = FulfillmentFormSet(
            prefix="lines",
            request_obj=request_obj,
            initial=initial_lines,
        )
        comment = request_obj.store_note or ""

    return render(
        request,
        "store/requests/request_fulfill.html",
        {
            "request_obj": request_obj,
            "formset": formset,
            "comment": comment,
            "page_title": f"Fulfill Request #{request_obj.id}",
            "base_template": _request_base_template(request.user),
        },
    )


@login_required
@transaction.atomic
def request_edit_issuance(request, request_id):
    if not _is_storekeeper(request.user):
        raise Http404("Only store-keepers can edit fulfillment.")

    request_obj = get_object_or_404(
        Request.objects.select_related("requester", "requester__department"),
        pk=request_id,
    )

    if request_obj.status not in [Request.Status.FULFILLED, Request.Status.LOCKED]:
        messages.error(request, "Only fulfilled requests can be edited here.")
        return redirect("store:request_list")

    if request.method == "POST":
        formset = IssuanceEditFormSet(request.POST, prefix="lines", request_obj=request_obj)
        reason_form = IssuanceEditReasonForm(request.POST)

        if formset.is_valid() and reason_form.is_valid():
            items_with_qty = [
                {
                    "request_item_id": form.cleaned_data["request_item_id"],
                    "fulfilled_qty": form.cleaned_data["fulfilled_qty"],
                }
                for form in formset.forms
                if hasattr(form, "cleaned_data") and form.cleaned_data
            ]

            reason = reason_form.cleaned_data["reason"]

            try:
                edit_issuance_service(
                    request_obj=request_obj,
                    edited_by=request.user,
                    items_with_qty=items_with_qty,
                    reason=reason,
                )
            except IssuanceError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Fulfillment for Request #{request_obj.id} updated.")
                return redirect("store:request_edit", request_id=request_obj.id)
        else:
            for form_errors in formset.errors:
                for field_name, error_list in form_errors.items():
                    for err in error_list:
                        messages.error(request, err)
            for err in formset.non_form_errors():
                messages.error(request, err)
            for field_name, error_list in reason_form.errors.items():
                for err in error_list:
                    messages.error(request, err)
    else:
        initial_lines = [
            {
                "request_item_id": request_item.id,
                "item_name": request_item.item.name,
                "requested_qty": request_item.requested_qty,
                "current_fulfilled_qty": request_item.fulfilled_qty,
                "fulfilled_qty": request_item.fulfilled_qty,
            }
            for request_item in request_obj.items.select_related("item").all()
        ]
        formset = IssuanceEditFormSet(prefix="lines", request_obj=request_obj, initial=initial_lines)
        reason_form = IssuanceEditReasonForm()

    return render(
        request,
        "store/requests/request_edit_issuance.html",
        {
            "request_obj": request_obj,
            "formset": formset,
            "reason_form": reason_form,
            "can_edit_now": request_obj.can_store_edit_fulfillment,
            "page_title": f"Edit Fulfilled Request #{request_obj.id}",
            "base_template": _request_base_template(request.user),
        },
    )


@login_required
def request_history(request):
    if not _can_access_request_workspace(request.user):
        return HttpResponseForbidden("You do not have access to request pages.")

    target = "store:history_issuance_storekeeper" if _is_storekeeper(request.user) else "store:history_issuance_management"
    return redirect(target)


@login_required
def request_history_table(request):
    if not _can_access_request_workspace(request.user):
        return HttpResponseForbidden("You do not have access to request pages.")
    if _is_storekeeper(request.user) or _is_in_group(request.user, "Management"):
        return redirect("store:request_history")

    requester_staff = _get_staff_for_user(request.user, required=True)
    base_qs = (
        Request.objects.select_related("requester", "requester__department", "fulfilled_by")
        .prefetch_related("items__item")
        .filter(requester=requester_staff)
        .order_by("-updated_at", "-created_at")
    )

    status = request.GET.get("status", "").strip()
    requests_qs = base_qs
    if status:
        requests_qs = requests_qs.filter(status=status)

    return render(
        request,
        "store/requests/request_history.html",
        {
            "requests": requests_qs,
            "selected_status": status,
            "status_choices": Request.Status.choices,
            "total_count": base_qs.count(),
            "draft_count": base_qs.filter(status=Request.Status.DRAFT).count(),
            "submitted_count": base_qs.filter(status=Request.Status.SUBMITTED).count(),
            "fulfilled_count": base_qs.filter(status=Request.Status.FULFILLED).count(),
            "locked_count": base_qs.filter(status=Request.Status.LOCKED).count(),
            "is_storekeeper": False,
            "base_template": _request_base_template(request.user),
        },
    )

# Override with role-specific queue experience for storekeepers.
@login_required
def request_list(request):
    if not _can_access_request_workspace(request.user):
        return HttpResponseForbidden("You do not have access to request pages.")

    is_storekeeper = _is_storekeeper(request.user)
    is_management = _is_in_group(request.user, "Management")

    base_qs = Request.objects.select_related("requester", "requester__department", "fulfilled_by").prefetch_related(
        "items__item"
    )

    if is_storekeeper:
        selected_kpi = (request.GET.get("kpi") or "pending").strip().lower()
        today = timezone.localdate()

        pending_requests = base_qs.filter(status=Request.Status.SUBMITTED).order_by("-submitted_at", "-updated_at")
        editable_fulfilled_requests = base_qs.filter(
            status=Request.Status.FULFILLED,
            editable_until__gte=timezone.now(),
        ).order_by("-fulfilled_at")
        fulfilled_today_requests = base_qs.filter(
            status=Request.Status.FULFILLED,
            fulfilled_at__date=today,
        ).order_by("-fulfilled_at")

        active_requests = Request.objects.none()
        active_title = "Select a KPI Card"
        active_empty_message = "Select a KPI card above to load queue data."

        if selected_kpi == "pending":
            active_requests = pending_requests
            active_title = "Submitted Queue"
            active_empty_message = "No submitted requests waiting for fulfillment."
        elif selected_kpi == "editable":
            active_requests = editable_fulfilled_requests
            active_title = "Fulfilled (Editable Window)"
            active_empty_message = "No fulfilled requests currently editable."
        elif selected_kpi == "today":
            active_requests = fulfilled_today_requests
            active_title = "Fulfilled Today"
            active_empty_message = "No requests were fulfilled today."

        context = {
            "active_requests": active_requests,
            "active_title": active_title,
            "active_empty_message": active_empty_message,
            "selected_kpi": selected_kpi,
            "pending_count": pending_requests.count(),
            "editable_count": editable_fulfilled_requests.count(),
            "fulfilled_today_count": fulfilled_today_requests.count(),
            "total_fulfilled_count": base_qs.filter(
                status__in=[Request.Status.FULFILLED, Request.Status.LOCKED],
            ).count(),
            "pending_note": "Submitted requests waiting storekeeper action.",
            "is_storekeeper": True,
            "is_management": is_management,
            "page_title": "Incoming Requests",
            "base_template": _request_base_template(request.user),
        }
        return render(request, "store/requests/request_queue_storekeeper.html", context)

    requester_staff = _get_staff_for_user(request.user, required=True)
    requests_qs = base_qs.filter(requester=requester_staff).order_by("-updated_at")

    status = request.GET.get("status", "").strip()
    if status:
        requests_qs = requests_qs.filter(status=status)

    kpi_qs = base_qs.filter(requester=requester_staff)
    summary_requests = list(requests_qs[:5])
    total_requests = kpi_qs.count()
    open_requests = kpi_qs.filter(status__in=[Request.Status.DRAFT, Request.Status.SUBMITTED]).count()
    archived_requests = kpi_qs.filter(status__in=[Request.Status.FULFILLED, Request.Status.LOCKED]).count()
    top_requested_items = list(
        RequestItem.objects.filter(request__requester=requester_staff)
        .values("item__name", "item__unit_of_measurement")
        .annotate(request_count=Count("request_id", distinct=True), total_qty=Sum("requested_qty"))
        .order_by("-request_count", "-total_qty", "item__name")[:5]
    )

    context = {
        "requests": requests_qs,
        "summary_requests": summary_requests,
        "top_requested_items": top_requested_items,
        "selected_status": status,
        "status_choices": Request.Status.choices,
        "is_storekeeper": False,
        "is_management": is_management,
        "page_title": "My Requests",
        "show_status_filter": True,
        "draft_count": kpi_qs.filter(status=Request.Status.DRAFT).count(),
        "submitted_count": kpi_qs.filter(status=Request.Status.SUBMITTED).count(),
        "fulfilled_count": kpi_qs.filter(status=Request.Status.FULFILLED).count(),
        "locked_count": kpi_qs.filter(status=Request.Status.LOCKED).count(),
        "total_requests": total_requests,
        "open_requests": open_requests,
        "archived_requests": archived_requests,
        "recent_activities": _recent_activity_for_requester(requester_staff, limit=8),
        "base_template": _request_base_template(request.user),
    }
    return render(request, "store/requests/request_list.html", context)









def _historical_requested_qty_cap_map(request_obj):
    caps = {}

    activities = request_obj.activities.filter(
        action__in=[
            RequestActivity.Action.CREATED,
            RequestActivity.Action.STAFF_EDITED,
            RequestActivity.Action.STORE_EDITED,
        ]
    ).order_by("created_at", "id")

    def _push(item_id, qty):
        try:
            item_id = int(item_id)
            qty = int(qty)
        except (TypeError, ValueError):
            return
        if qty <= 0:
            return
        caps[item_id] = max(caps.get(item_id, 0), qty)

    for activity in activities:
        metadata = activity.metadata or {}
        for row in metadata.get("items", []):
            _push(row.get("item_id"), row.get("requested_qty"))

        for change in metadata.get("changes", []):
            item_id = change.get("item_id")
            _push(item_id, change.get("old_qty"))
            _push(item_id, change.get("new_qty"))

    return caps









