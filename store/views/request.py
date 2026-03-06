from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from store.forms import RequestForm, RequestItemFormSet
from store.models import Request, RequestItem, RequestActivity, Staff, Activity
from store.services.activity_service import emit_activity


def _get_staff_for_user(user):
    try:
        return Staff.objects.select_related("department").get(user=user)
    except Staff.DoesNotExist:
        raise Http404("No staff profile is linked to this user.")


def _serialize_request_items(request_obj):
    """
    Build initial data for RequestItemFormSet from existing RequestItem rows.
    """
    return [
        {
            "item": request_item.item,
            "requested_qty": request_item.requested_qty,
        }
        for request_item in request_obj.items.select_related("item").all()
    ]


@login_required
def request_list(request):
    staff = _get_staff_for_user(request.user)

    if staff.job_roles == "store-keeper":
        requests_qs = (
            Request.objects.select_related("requester", "requester__department", "fulfilled_by")
            .prefetch_related("items__item")
            .all()
        )
    else:
        requests_qs = (
            Request.objects.select_related("requester", "requester__department", "fulfilled_by")
            .prefetch_related("items__item")
            .filter(requester=staff)
        )

    status = request.GET.get("status", "").strip()
    if status:
        requests_qs = requests_qs.filter(status=status)

    context = {
        "requests": requests_qs,
        "selected_status": status,
        "status_choices": Request.Status.choices,
        "page_title": "Requests",
    }
    return render(request, "store/requests/request_list.html", context)


@login_required
@transaction.atomic
def request_create(request):
    staff = _get_staff_for_user(request.user)

    if request.method == "POST":
        form = RequestForm(request.POST)
        formset = RequestItemFormSet(request.POST, prefix="items")

        if form.is_valid() and formset.is_valid():
            request_obj = form.save(commit=False)
            request_obj.requester = staff
            request_obj.status = Request.Status.DRAFT
            request_obj.last_edited_by = request.user
            request_obj.save()

            request_items = []
            for item_form in formset:
                if not item_form.cleaned_data or item_form.cleaned_data.get("DELETE"):
                    continue

                item = item_form.cleaned_data["item"]
                requested_qty = item_form.cleaned_data["requested_qty"]

                request_item = RequestItem.objects.create(
                    request=request_obj,
                    item=item,
                    requested_qty=requested_qty,
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

            emit_activity(
                actor=request.user,
                verb=Activity.Verb.REQUEST_CREATED,
                target=request_obj,
                summary=f"{staff.name} created Request #{request_obj.id}",
                metadata={
                    "request_id": request_obj.id,
                    "staff_id": staff.id,
                    "staff_name": staff.name,
                    "department": staff.department.name if staff.department else "",
                },
            )

            messages.success(request, "Request created successfully.")
            return redirect("store:request_edit", request_id=request_obj.id)

    else:
        form = RequestForm()
        formset = RequestItemFormSet(prefix="items")

    context = {
        "form": form,
        "formset": formset,
        "request_obj": None,
        "page_title": "Create Request",
        "submit_label": "Save Request",
        "is_edit_mode": False,
    }
    return render(request, "store/requests/request_form.html", context)


@login_required
@transaction.atomic
def request_edit(request, request_id):
    staff = _get_staff_for_user(request.user)

    request_obj = get_object_or_404(
        Request.objects.select_related("requester", "requester__department"),
        pk=request_id,
    )

    if request_obj.requester_id != staff.id and staff.job_roles != "store-keeper":
        raise Http404("You do not have permission to edit this request.")

    if not request_obj.can_staff_edit and staff.job_roles != "store-keeper":
        messages.error(request, "This request can no longer be edited.")
        return redirect("store:request_list")

    if request_obj.status in [Request.Status.FULFILLED, Request.Status.LOCKED]:
        messages.error(request, "Fulfilled or locked requests cannot be edited here.")
        return redirect("store:request_list")

    existing_items = _serialize_request_items(request_obj)

    if request.method == "POST":
        form = RequestForm(request.POST, instance=request_obj)
        formset = RequestItemFormSet(request.POST, prefix="items")

        if form.is_valid() and formset.is_valid():
            request_obj = form.save(commit=False)
            request_obj.last_edited_by = request.user
            request_obj.save()

            old_items = {
                row.item_id: row.requested_qty
                for row in request_obj.items.all()
            }

            request_obj.items.all().delete()

            new_items = []
            for item_form in formset:
                if not item_form.cleaned_data or item_form.cleaned_data.get("DELETE"):
                    continue

                item = item_form.cleaned_data["item"]
                requested_qty = item_form.cleaned_data["requested_qty"]

                request_item = RequestItem.objects.create(
                    request=request_obj,
                    item=item,
                    requested_qty=requested_qty,
                )
                new_items.append(request_item)

            changes = []
            new_items_map = {row.item_id: row.requested_qty for row in new_items}
            all_item_ids = set(old_items.keys()) | set(new_items_map.keys())

            item_name_map = {
                row.item_id: row.item.name
                for row in new_items
            }

            for old_row in request_obj.items.select_related("item").all():
                item_name_map[old_row.item_id] = old_row.item.name

            for item_id in all_item_ids:
                old_qty = old_items.get(item_id)
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

            if changes:
                action = (
                    RequestActivity.Action.STORE_EDITED
                    if staff.job_roles == "store-keeper" and request_obj.requester_id != staff.id
                    else RequestActivity.Action.STAFF_EDITED
                )

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

            messages.success(request, "Request updated successfully.")
            return redirect("store:request_edit", request_id=request_obj.id)

    else:
        form = RequestForm(instance=request_obj)
        formset = RequestItemFormSet(
            initial=existing_items,
            prefix="items",
        )

    context = {
        "form": form,
        "formset": formset,
        "request_obj": request_obj,
        "page_title": f"Edit Request #{request_obj.id}",
        "submit_label": "Update Request",
        "is_edit_mode": True,
    }
    return render(request, "store/requests/request_form.html", context)


@login_required
@transaction.atomic
def request_submit(request, request_id):
    if request.method != "POST":
        return redirect("store:request_list")

    staff = _get_staff_for_user(request.user)

    request_obj = get_object_or_404(
        Request.objects.select_related("requester", "requester__department"),
        pk=request_id,
        requester=staff,
    )

    if request_obj.status not in [Request.Status.DRAFT, Request.Status.SUBMITTED]:
        messages.error(request, "Only draft or editable submitted requests can be submitted.")
        return redirect("store:request_edit", request_id=request_obj.id)

    if not request_obj.items.exists():
        messages.error(request, "You must add at least one item before submitting.")
        return redirect("store:request_edit", request_id=request_obj.id)

    request_obj.status = Request.Status.SUBMITTED
    request_obj.submitted_at = timezone.now()
    request_obj.last_edited_by = request.user
    request_obj.save(update_fields=["status", "submitted_at", "last_edited_by", "updated_at"])

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
def request_fulfill(request, request_id):
    raise NotImplementedError("request_fulfill will be added in the next phase.")


@login_required
def request_edit_issuance(request, request_id):
    raise NotImplementedError("request_edit_issuance will be added in the next phase.")