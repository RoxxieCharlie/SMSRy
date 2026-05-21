from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, BooleanField, Exists, OuterRef
from django.utils import timezone

from store.models import Issuance, Department, RequestActivity
from store.decorators import group_required
from store.views.request import _build_storekeeper_history


@login_required
@group_required("StoreKeeper")
def history_issuance_storekeeper(request):
    user = request.user
    now = timezone.now()
    today = timezone.localdate()
    cutoff = now - timedelta(hours=6)

    qs = (
        Issuance.objects
        .select_related("staff", "issued_by", "staff__department", "request__requester")
        .prefetch_related("items__item", "request__items__item", "request__activities")
        .filter(issued_by=user)
        .order_by("-issued_at")
        .annotate(
            is_edited_ui=Exists(
                RequestActivity.objects.filter(
                    request_id=OuterRef("request_id"),
                    action__in=[
                        RequestActivity.Action.STAFF_EDITED,
                        RequestActivity.Action.STORE_EDITED,
                        RequestActivity.Action.FULFILLMENT_EDITED,
                    ],
                )
            ),
            can_reverse_ui=Case(
                When(is_reversed=False, issued_at__gte=cutoff, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
            is_locked_ui=Case(
                When(is_reversed=False, issued_at__lt=cutoff, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
    )

    # -------------------------
    # Filters from querystring
    # -------------------------
    q = (request.GET.get("q") or "").strip()
    department_id = (request.GET.get("department") or "").strip()
    staff_id = (request.GET.get("staff") or "").strip()
    item_id = (request.GET.get("item") or "").strip()

    start = (request.GET.get("start") or "").strip()
    end = (request.GET.get("end") or "").strip()
    state = (request.GET.get("state") or "").strip().lower()  # "" | today | locked | edited

    # Free-text search (staff name or item name)
    if q:
        qs = qs.filter(
            Q(staff__name__icontains=q) |
            Q(staff__staff_id__icontains=q) |
            Q(items__item__name__icontains=q) | Q(request__requester__name__icontains=q) | Q(request__purpose__icontains=q)
        ).distinct()

    # Department filter
    if department_id.isdigit():
        qs = qs.filter(staff__department__id=int(department_id))

    # Specific staff filter (collected-by)
    if staff_id.isdigit():
        qs = qs.filter(staff__id=int(staff_id))

    # Specific item filter (issuances containing item)
    if item_id.isdigit():
        qs = qs.filter(items__item__id=int(item_id)).distinct()

    # Date filters
    if start:
        qs = qs.filter(issued_at__date__gte=start)

    if end:
        qs = qs.filter(issued_at__date__lte=end)

    # -------------------------
    # KPIs should reflect filters but NOT "state" narrowing
    # -------------------------
    base_qs = qs

    kpi_total = base_qs.count()
    kpi_today = base_qs.filter(issued_at__date=today).count()
    kpi_edited = base_qs.filter(is_edited_ui=True).count()
    kpi_locked = base_qs.filter(is_reversed=False, issued_at__lt=cutoff).count()

    # KPI card filters (state)
    if state == "today":
        qs = base_qs.filter(issued_at__date=today)
    elif state == "edited":
        qs = base_qs.filter(is_edited_ui=True)
    elif state == "locked":
        qs = base_qs.filter(is_reversed=False, issued_at__lt=cutoff)
    else:
        qs = base_qs
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_range = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=1)

    for issuance in page_obj.object_list:
        issuance.storekeeper_history = (
            _build_storekeeper_history(issuance.request, issuance) if issuance.request_id else []
        )

    context = {
        "page_obj": page_obj,
        "page_range": page_range,
        "total_count": paginator.count,

        "search_query": q,
        "department_id": int(department_id) if department_id.isdigit() else "",
        "staff_id": int(staff_id) if staff_id.isdigit() else "",
        "item_id": int(item_id) if item_id.isdigit() else "",
        "start": start,
        "end": end,
        "state": state,

        "departments": Department.objects.order_by("name"),

        "kpi_total": kpi_total,
        "kpi_today": kpi_today,
        "kpi_locked": kpi_locked,
        "kpi_edited": kpi_edited,

        "base_template": "store/base_v2.html",
        "clear_url_name": "store:history_issuance_storekeeper_v2",
    }
    return render(request, "store/history_issuance_v2.html", context)


