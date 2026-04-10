# store/views/dashboard.py
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from store.models import Activity, Item, IssuanceItem, Request, RequestActivity, RequestItem, Staff


def _time_ago(dt):
    if not dt:
        return ""
    now = timezone.now()
    diff = now - dt
    secs = int(diff.total_seconds())

    if secs < 60:
        return "just now"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs}h ago"
    days = hrs // 24
    if days < 7:
        return f"{days}d ago"
    weeks = days // 7
    return f"{weeks}w ago"


def _activity_ui(a: Activity):
    actor = a.actor.get_full_name() or a.actor.username
    verb = a.verb

    ui_type = "ok"
    action = a.get_verb_display()

    if verb in (Activity.Verb.LOW_STOCK_ALERT,):
        ui_type = "warning"
        action = "triggered a low stock warning"
    elif verb in (Activity.Verb.ISSUANCE_FAILED,):
        ui_type = "danger"
        action = "attempted an issuance (failed)"
    elif verb in (Activity.Verb.ISSUANCE_REVERSED,):
        ui_type = "ok"
        action = "reversed an issuance"
    elif verb in (Activity.Verb.ISSUANCE_CREATED,):
        ui_type = "ok"
        action = "issued items"
    elif verb in (Activity.Verb.STOCKIN_CREATED,):
        ui_type = "ok"
        action = "stocked in items"
    elif verb in (Activity.Verb.REQUEST_UPDATED,):
        ui_type = "ok"
        action = "updated a request"
    elif verb in (Activity.Verb.REQUEST_SUBMITTED,):
        ui_type = "ok"
        action = "submitted a request"
    elif verb in (Activity.Verb.REQUEST_FULFILLED,):
        ui_type = "ok"
        action = "fulfilled a request"

    obj = a.summary or ""
    return {
        "actor": actor,
        "verb": verb,
        "action": action,
        "object": obj,
        "time_ago": _time_ago(a.created_at),
        "type": "danger" if ui_type == "danger" else ("warning" if ui_type == "warning" else "ok"),
    }


def _dashboard_recent_activity(limit=10):
    allowed_verbs = [
        Activity.Verb.STOCKIN_CREATED,
        Activity.Verb.ISSUANCE_CREATED,
        Activity.Verb.ISSUANCE_UPDATED,
        Activity.Verb.ISSUANCE_FAILED,
        Activity.Verb.ISSUANCE_REVERSED,
        Activity.Verb.LOW_STOCK_ALERT,
        Activity.Verb.REQUEST_SUBMITTED,
        Activity.Verb.REQUEST_FULFILLED,
        Activity.Verb.REQUEST_UPDATED,
    ]
    return Activity.objects.filter(verb__in=allowed_verbs).order_by("-created_at")[:limit]

@login_required
def dashboard_router(request):
    user = request.user

    if user.groups.filter(name__iexact="Management").exists():
        return redirect("store:dashboard_management_v2")

    if user.groups.filter(name__iexact="StoreKeeper").exists():
        return redirect("store:dashboard_storekeeper_v2")

    if user.groups.filter(name__iexact="Staff").exists():
        return redirect("store:dashboard_staff_v2")

    return HttpResponseForbidden("No dashboard assigned.")


@login_required
def dashboard_storekeeper(request):
    if not request.user.groups.filter(name__iexact="StoreKeeper").exists():
        return HttpResponseForbidden("Forbidden")

    user = request.user

    timeframe = request.GET.get("t", "7d")
    days = 30 if timeframe == "30d" else 7
    now = timezone.now()

    start = now - timedelta(days=days)
    prev_start = start - timedelta(days=days)
    prev_end = start

    # KPIs: inventory counts
    total_items = Item.objects.count()
    out_of_stock_count = Item.objects.filter(quantity=0).count()
    low_stock_count = Item.objects.filter(quantity__gt=0, quantity__lte=F("reorder_level")).count()

    # Issuance aggregation (storekeeper's own issuances)
    base_lines = (
        IssuanceItem.objects
        .select_related("item", "issuance")
        .filter(issuance__issued_by=user)
    )

    curr = (
        base_lines
        .filter(issuance__issued_at__gte=start)
        .values("item_id", "item__name")
        .annotate(issued=Sum("quantity"))
        .order_by("-issued")
    )

    prev = (
        base_lines
        .filter(issuance__issued_at__gte=prev_start, issuance__issued_at__lt=prev_end)
        .values("item_id")
        .annotate(issued=Sum("quantity"))
    )
    prev_map = {r["item_id"]: (r["issued"] or 0) for r in prev}

    top_raw = list(curr[:4])
    max_issued = max([r["issued"] or 0 for r in top_raw], default=0)

    top_issued_items = []
    for r in top_raw:
        item_id = r["item_id"]
        name = r["item__name"]
        issued = int(r["issued"] or 0)
        prev_issued = int(prev_map.get(item_id, 0))

        if prev_issued == 0:
            delta_pct = None if issued == 0 else 100
        else:
            delta_pct = round(((issued - prev_issued) / prev_issued) * 100)

        bar_pct = 0 if max_issued == 0 else round((issued / max_issued) * 100)

        top_issued_items.append({
            "item_id": item_id,
            "name": name,
            "issued": issued,
            "delta_pct": delta_pct,
            "bar_pct": bar_pct,
            # drilldown URL
            "url": reverse("store:history_issuance_storekeeper") + f"?item={item_id}",
        })

    if top_raw:
        best = top_raw[0]
        most_issued_item_id = best["item_id"]
        most_issued_item_name = best["item__name"]
        most_issued_count = int(best["issued"] or 0)

        prev_best = int(prev_map.get(most_issued_item_id, 0))
        if prev_best == 0:
            most_issued_delta_pct = None if most_issued_count == 0 else 100
        else:
            most_issued_delta_pct = round(((most_issued_count - prev_best) / prev_best) * 100)
    else:
        most_issued_item_id = None
        most_issued_item_name = None
        most_issued_count = 0
        most_issued_delta_pct = None

    # Activity
    activities = _dashboard_recent_activity(limit=10)
    recent_activity = [_activity_ui(a) for a in activities]

    # KPI drilldowns
    inventory_url = reverse("store:inventory_store")
    issuance_history_url = reverse("store:history_issuance_storekeeper")

    context = {
        "active_nav": "dashboard",

        "total_items": total_items,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,

        # KPI drilldown URLs
        "kpi_low_stock_url": inventory_url + "?status=low",
        "kpi_out_of_stock_url": inventory_url + "?status=out",
        "kpi_total_items_url": inventory_url,
        "kpi_most_issued_url": (issuance_history_url + f"?item={most_issued_item_id}") if most_issued_item_id else issuance_history_url,

        # Most issued
        "most_issued_item_id": most_issued_item_id,
        "most_issued_item_name": most_issued_item_name,
        "most_issued_count": most_issued_count,
        "most_issued_delta_pct": most_issued_delta_pct,

        # Top issued panel
        "top_issued_items": top_issued_items,
        "timeframe": timeframe,

        # Activity
        "recent_activity": recent_activity,
    }

    return render(request, "store/dashboard_storekeeper_v2.html", context)


@login_required
def dashboard_management(request):
    if not request.user.groups.filter(name__iexact="Management").exists():
        return HttpResponseForbidden("Forbidden")

    # timeframe toggle: 7d or 30d (default 7d)
    timeframe = request.GET.get("t", "7d")
    days = 30 if timeframe == "30d" else 7
    now = timezone.now()

    start = now - timedelta(days=days)
    prev_start = start - timedelta(days=days)
    prev_end = start

    # KPIs: inventory counts (global)
    total_items = Item.objects.count()
    out_of_stock_count = Item.objects.filter(quantity=0).count()
    low_stock_count = Item.objects.filter(quantity__gt=0, quantity__lte=F("reorder_level")).count()

    # Issuance aggregation (management sees ALL issuances)
    base_lines = (
        IssuanceItem.objects
        .select_related("item", "issuance")
    )

    # Current period top items
    curr = (
        base_lines
        .filter(issuance__issued_at__gte=start)
        .values("item_id", "item__name")
        .annotate(issued=Sum("quantity"))
        .order_by("-issued")
    )

    # Previous period
    prev = (
        base_lines
        .filter(issuance__issued_at__gte=prev_start, issuance__issued_at__lt=prev_end)
        .values("item_id")
        .annotate(issued=Sum("quantity"))
    )
    prev_map = {r["item_id"]: (r["issued"] or 0) for r in prev}

    # Build top list (max 4)
    top_raw = list(curr[:4])
    max_issued = max([r["issued"] or 0 for r in top_raw], default=0)

    top_issued_items = []
    for r in top_raw:
        item_id = r["item_id"]
        name = r["item__name"]
        issued = int(r["issued"] or 0)
        prev_issued = int(prev_map.get(item_id, 0))

        if prev_issued == 0:
            delta_pct = None if issued == 0 else 100
        else:
            delta_pct = round(((issued - prev_issued) / prev_issued) * 100)

        bar_pct = 0 if max_issued == 0 else round((issued / max_issued) * 100)

        top_issued_items.append({
            "item_id": item_id,
            "name": name,
            "issued": issued,
            "delta_pct": delta_pct,
            "bar_pct": bar_pct,
            # management drilldown
            "url": reverse("store:history_issuance_management") + f"?item={item_id}",
        })

    # Most issued item
    if top_raw:
        best = top_raw[0]
        most_issued_item_id = best["item_id"]
        most_issued_item_name = best["item__name"]
        most_issued_count = int(best["issued"] or 0)

        prev_best = int(prev_map.get(most_issued_item_id, 0))
        if prev_best == 0:
            most_issued_delta_pct = None if most_issued_count == 0 else 100
        else:
            most_issued_delta_pct = round(((most_issued_count - prev_best) / prev_best) * 100)
    else:
        most_issued_item_id = None
        most_issued_item_name = None
        most_issued_count = 0
        most_issued_delta_pct = None

    # Recent activity (global)
    activities = _dashboard_recent_activity(limit=10)
    recent_activity = [_activity_ui(a) for a in activities]

    # KPI drilldowns
    inventory_url = reverse("store:inventory_mgt")
    issuance_history_url = reverse("store:history_issuance_management")

    context = {
        "active_nav": "dashboard",

        # KPIs
        "total_items": total_items,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,

        # KPI drilldown URLs (optional if you want to use them in template)
        "kpi_low_stock_url": inventory_url + "?status=low",
        "kpi_out_of_stock_url": inventory_url + "?status=out",
        "kpi_total_items_url": inventory_url,
        "kpi_most_issued_url": (issuance_history_url + f"?item={most_issued_item_id}") if most_issued_item_id else issuance_history_url,

        # Most issued
        "most_issued_item_id": most_issued_item_id,
        "most_issued_item_name": most_issued_item_name,
        "most_issued_count": most_issued_count,
        "most_issued_delta_pct": most_issued_delta_pct,

        # Top issued panel
        "top_issued_items": top_issued_items,
        "timeframe": timeframe,

        # Activity panel
        "recent_activity": recent_activity,
    }

    return render(request, "store/dashboard_management_v2.html", context)

@login_required
def dashboard_staff(request):
    if not request.user.groups.filter(name__iexact="Staff").exists():
        return HttpResponseForbidden("Forbidden")

    try:
        staff = Staff.objects.select_related("department").get(user=request.user)
    except Staff.DoesNotExist:
        return HttpResponseForbidden("No staff profile is linked to this user.")

    my_requests = Request.objects.filter(requester=staff)
    total_requests = my_requests.count()
    draft_count = my_requests.filter(status=Request.Status.DRAFT).count()
    submitted_count = my_requests.filter(status=Request.Status.SUBMITTED).count()
    fulfilled_count = my_requests.filter(status=Request.Status.FULFILLED).count()
    locked_count = my_requests.filter(status=Request.Status.LOCKED).count()
    open_requests = draft_count + submitted_count
    archived_requests = fulfilled_count + locked_count
    selected_filter = (request.GET.get("kpi") or "all").strip().lower()

    recent_requests_qs = my_requests.order_by("-updated_at")
    if selected_filter == "open":
        recent_requests_qs = recent_requests_qs.filter(status__in=[Request.Status.DRAFT, Request.Status.SUBMITTED])
    elif selected_filter == "archived":
        recent_requests_qs = recent_requests_qs.filter(status__in=[Request.Status.FULFILLED, Request.Status.LOCKED])
    else:
        selected_filter = "all"

    top_requested_items = list(
        RequestItem.objects.filter(request__requester=staff)
        .values("item__name", "item__unit_of_measurement")
        .annotate(request_count=Count("request_id", distinct=True), total_qty=Sum("requested_qty"))
        .order_by("-request_count", "-total_qty", "item__name")[:5]
    )

    display_name = (
        getattr(staff, "name", "").strip()
        or request.user.get_full_name().strip()
        or request.user.username
    )

    context = {
        "active_nav": "dashboard",
        "staff": staff,
        "display_name": display_name,
        "total_requests": total_requests,
        "draft_count": draft_count,
        "submitted_count": submitted_count,
        "fulfilled_count": fulfilled_count,
        "locked_count": locked_count,
        "open_requests": open_requests,
        "archived_requests": archived_requests,
        "selected_filter": selected_filter,
        "top_requested_items": top_requested_items,
        "recent_requests": recent_requests_qs[:6],
        "recent_request_activity": RequestActivity.objects.select_related("request").filter(request__requester=staff).order_by("-created_at")[:8],
    }
    return render(request, "store/dashboard_staff_v2.html", context)
