from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, BooleanField
from django.utils import timezone

from store.models import Issuance, Department
from store.decorators import group_required


@login_required
@group_required("Management")
def history_issuance_management(request):
    now = timezone.now()
    today = timezone.localdate()
    cutoff = now - timedelta(hours=6)

    issuances = (
        Issuance.objects
        .select_related("staff", "issued_by", "staff__department")
        .prefetch_related("items__item")
        .order_by("-issued_at")
        .annotate(
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
    # Filters
    # -------------------------
    search_query = (request.GET.get("q") or "").strip()
    department_id = (request.GET.get("department") or "").strip()

    staff_id = (request.GET.get("staff") or "").strip()
    item_id = (request.GET.get("item") or "").strip()
    issued_by_id = (request.GET.get("issued_by") or "").strip()

    start = (request.GET.get("start") or "").strip()
    end = (request.GET.get("end") or "").strip()
    state = (request.GET.get("state") or "").strip().lower()  # "" | today | locked | reversed

    if search_query:
        issuances = issuances.filter(
            Q(staff__name__icontains=search_query)
            | Q(staff__staff_id__icontains=search_query)
            | Q(items__item__name__icontains=search_query)
            | Q(issued_by__username__icontains=search_query)
            | Q(issued_by__first_name__icontains=search_query)
            | Q(issued_by__last_name__icontains=search_query)
        ).distinct()

    if department_id.isdigit():
        issuances = issuances.filter(staff__department__id=int(department_id))

    if staff_id.isdigit():
        issuances = issuances.filter(staff__id=int(staff_id))

    if item_id.isdigit():
        issuances = issuances.filter(items__item__id=int(item_id)).distinct()

    if issued_by_id.isdigit():
        issuances = issuances.filter(issued_by__id=int(issued_by_id))

    if start:
        issuances = issuances.filter(issued_at__date__gte=start)

    if end:
        issuances = issuances.filter(issued_at__date__lte=end)

    # KPIs from filtered set (excluding "state")
    base_qs = issuances
    kpi_total = base_qs.count()
    kpi_today = base_qs.filter(issued_at__date=today).count()
    kpi_reversed = base_qs.filter(is_reversed=True).count()
    kpi_locked = base_qs.filter(is_reversed=False, issued_at__lt=cutoff).count()

    if state == "today":
        issuances = base_qs.filter(issued_at__date=today)
    elif state == "reversed":
        issuances = base_qs.filter(is_reversed=True)
    elif state == "locked":
        issuances = base_qs.filter(is_reversed=False, issued_at__lt=cutoff)
    else:
        issuances = base_qs

    paginator = Paginator(issuances, 30)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_range = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=1)

    context = {
        "page_obj": page_obj,
        "page_range": page_range,
        "total_count": paginator.count,

        "search_query": search_query,
        "department_id": int(department_id) if department_id.isdigit() else "",
        "staff_id": int(staff_id) if staff_id.isdigit() else "",
        "item_id": int(item_id) if item_id.isdigit() else "",
        "issued_by_id": int(issued_by_id) if issued_by_id.isdigit() else "",
        "start": start,
        "end": end,
        "state": state,

        "departments": Department.objects.all().order_by("name"),

        "kpi_total": kpi_total,
        "kpi_today": kpi_today,
        "kpi_locked": kpi_locked,
        "kpi_reversed": kpi_reversed,
    }
    return render(request, "store/history_issuance_management_v2.html", context)