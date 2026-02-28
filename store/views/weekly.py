from __future__ import annotations

import csv
from datetime import datetime, timedelta, time

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone

from store.models import IssuanceItem


# New-report cutover time: Sunday 6:00 PM
SUNDAY_EVENING_START_HOUR = 18  # 6 PM


# ------------------------------------------------------------
# OLD TIME-BOUND ACCESS WINDOW (COMMENTED OUT FOR NOW)
# Keep it here so you can re-enable later if you truly want.
# ------------------------------------------------------------
# def _weekly_report_window_open(now):
#     weekday = now.weekday()  # Mon=0 ... Sun=6
#     hour = now.hour
#     if weekday == 6:
#         return (hour >= SUNDAY_EVENING_START_HOUR, "Sunday 6:00 PM → Tuesday 11:59 PM")
#     if weekday in (0, 1):
#         return (True, "Sunday 6:00 PM → Tuesday 11:59 PM")
#     return (False, "Sunday 6:00 PM → Tuesday 11:59 PM")


def _week_bounds_from_monday(monday_date, tzinfo):
    """
    monday_date: date object for Monday
    returns aware datetimes:
      start: Monday 00:00:00
      end:   Sunday 23:59:59.999999
    """
    start_dt = timezone.make_aware(datetime.combine(monday_date, time.min), tzinfo)
    sunday_date = monday_date + timedelta(days=6)
    end_dt = timezone.make_aware(datetime.combine(sunday_date, time.max), tzinfo)
    return start_dt, end_dt


def _report_week_range(now_local):
    """
    Rule you asked for:
      - Reports are Monday → Sunday (full week)
      - A new one becomes available ONLY on Sunday 6PM.
      - Until Sunday 6PM, users keep seeing the PREVIOUS completed week.
      - From Sunday 6PM onward, users see the CURRENT week (Mon→Sun) as the "just concluded" week.

    Returns: (start_dt, end_dt, window_label, is_new_week_available)
    """
    tzinfo = now_local.tzinfo

    # Monday of the current week
    this_monday_date = (now_local - timedelta(days=now_local.weekday())).date()

    is_sunday = (now_local.weekday() == 6)
    is_after_cutoff = is_sunday and (now_local.hour >= SUNDAY_EVENING_START_HOUR)

    if is_after_cutoff:
        # New report is available: show current week Mon→Sun
        start_dt, end_dt = _week_bounds_from_monday(this_monday_date, tzinfo)
        window_label = f"{start_dt.date()} → {end_dt.date()}"
        return start_dt, end_dt, window_label, True

    # Not yet Sunday 6PM: show previous completed week Mon→Sun
    prev_monday_date = this_monday_date - timedelta(days=7)
    start_dt, end_dt = _week_bounds_from_monday(prev_monday_date, tzinfo)
    window_label = f"{start_dt.date()} → {end_dt.date()}"
    return start_dt, end_dt, window_label, False


@login_required
def weekly_report(request):
    user = request.user

    # Management only (case-insensitive safer)
    if not user.groups.filter(name__iexact="Management").exists():
        return HttpResponseForbidden("You do not have access to this page.")

    now = timezone.localtime(timezone.now())

    # ✅ Correct weekly range per your spec
    start_dt, end_dt, window_label, new_week_available = _report_week_range(now)

    # Only count valid (non-reversed) issuances
    qs = (
        IssuanceItem.objects
        .filter(
            issuance__is_reversed=False,
            issuance__issued_at__gte=start_dt,
            issuance__issued_at__lte=end_dt,
        )
        .select_related("item", "issuance__staff__department")
    )

    # Weekly total (all quantities issued)
    weekly_total = qs.aggregate(total=Sum("quantity"))["total"] or 0

    # Aggregate:
    # item_name -> {"total": int, "dept_counts": {dept_name: int}}
    agg = {}
    dept_totals = {}  # dept_name -> total_qty

    for line in qs:
        item_name = line.item.name
        dept_name = (
            line.issuance.staff.department.name
            if line.issuance.staff.department
            else "Unassigned"
        )

        if item_name not in agg:
            agg[item_name] = {"total": 0, "dept_counts": {}}

        agg[item_name]["total"] += line.quantity
        agg[item_name]["dept_counts"][dept_name] = (
            agg[item_name]["dept_counts"].get(dept_name, 0) + line.quantity
        )

        dept_totals[dept_name] = dept_totals.get(dept_name, 0) + line.quantity

    # Build item rows
    report_list = []
    for item_name, data in agg.items():
        dept_parts = [
            f"{dept} ({qty})"
            for dept, qty in sorted(data["dept_counts"].items(), key=lambda x: (-x[1], x[0]))
        ]
        report_list.append({
            "item": item_name,
            "total_quantity": data["total"],
            "departments_with_usage": ", ".join(dept_parts),
        })

    report_list.sort(key=lambda r: (-r["total_quantity"], r["item"]))

    # Build department summary rows
    dept_summary = []
    for dept_name, qty in sorted(dept_totals.items(), key=lambda x: (-x[1], x[0])):
        pct = 0 if weekly_total == 0 else round((qty / weekly_total) * 100)
        dept_summary.append({
            "department": dept_name,
            "total_quantity": qty,
            "pct": pct,
        })

    # Export CSV (Item + Total + Department usage string)
    if request.GET.get("export") == "1":
        response = HttpResponse(content_type="text/csv")
        filename = f"weekly_report_{start_dt.date()}_to_{end_dt.date()}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(["Item", "Total Issued", "Departments with Usage"])
        for row in report_list:
            writer.writerow([row["item"], row["total_quantity"], row["departments_with_usage"]])
        return response

    return render(request, "store/weekly_v2.html", {
        "active_nav": "weekly",

        # always accessible
        "report_closed": False,

        # period
        "start_date": start_dt.date(),
        "end_date": end_dt.date(),
        "window_label": window_label,

        # whether current week's report has switched in (Sun 6PM+)
        "new_week_available": new_week_available,
        "next_cutover_hint": "New report becomes available Sunday 6:00 PM.",

        # totals
        "weekly_total": weekly_total,

        # tables
        "report_list": report_list,
        "dept_summary": dept_summary,
    })