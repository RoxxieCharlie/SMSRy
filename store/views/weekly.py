from __future__ import annotations

import csv
from datetime import datetime, timedelta, time

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone

from store.models import IssuanceItem


# Access window: Sunday 6:00 PM → Tuesday 11:59 PM
SUNDAY_EVENING_START_HOUR = 18  # 6 PM


def _weekly_report_window_open(now):
    """
    Returns (is_open: bool, window_label: str)
    Django weekday: Monday=0 ... Sunday=6
    """
    weekday = now.weekday()
    hour = now.hour

    # Sunday: open only from 18:00 onward
    if weekday == 6:
        return (hour >= SUNDAY_EVENING_START_HOUR, "Sunday 6:00 PM → Tuesday 11:59 PM")

    # Monday and Tuesday: open
    if weekday in (0, 1):
        return (True, "Sunday 6:00 PM → Tuesday 11:59 PM")

    return (False, "Sunday 6:00 PM → Tuesday 11:59 PM")


def _monday_to_sunday_range_for_report(now):
    """
    Report week definition:
    - Start: Monday 00:00:00
    - End: Sunday 17:59:59 (because report is produced at Sunday 6:00 PM)
    We compute the Monday/Sunday of the week containing `now`.
    """
    # Monday of current week (00:00)
    monday_date = (now - timedelta(days=now.weekday())).date()
    start_dt = timezone.make_aware(datetime.combine(monday_date, time.min), now.tzinfo)

    # Sunday 17:59:59 of current week
    sunday_date = monday_date + timedelta(days=6)
    end_dt = timezone.make_aware(datetime.combine(sunday_date, time(17, 59, 59)), now.tzinfo)

    return start_dt, end_dt


@login_required
def weekly_report(request):
    user = request.user

    # Management only
    if not user.groups.filter(name="Management").exists():
        return HttpResponseForbidden("You do not have access to this page.")

    now = timezone.localtime(timezone.now())
    is_open, window_label = _weekly_report_window_open(now)

    # Compute Monday→Sunday(5:59:59 PM) range for *this* week
    start_dt, end_dt = _monday_to_sunday_range_for_report(now)

    # If within the access window but it's still before Sunday 6PM,
    # the range's end_dt may be in the future. We must clamp it to "now"
    # to avoid counting future records. But you said "produce by Sunday 6pm",
    # so we should NOT show partial weekly totals earlier than Sunday 6pm anyway.
    # Therefore: if not open, show message page.
    if not is_open:
        return render(request, "store/weekly.html", {
            "report_closed": True,
            "window_label": window_label,
            "start_date": start_dt.date(),
            "end_date": end_dt.date(),
        })

    # When open (Sun 6pm+ / Mon / Tue), the week has ended.
    # Ensure we don't exceed now (in case someone opens on Sunday 6:01 PM, fine)
    effective_end = min(end_dt, now)

    qs = (
        IssuanceItem.objects
        .filter(issuance__issued_at__gte=start_dt, issuance__issued_at__lte=effective_end)
        .select_related("item", "issuance__staff__department")
    )

    # item_name -> {"total": int, "dept_counts": {dept_name: int}}
    agg = {}

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

    # Export CSV (include departments with usage)
    if request.GET.get("export") == "1":
        response = HttpResponse(content_type="text/csv")
        filename = f"weekly_report_{start_dt.date()}_to_{end_dt.date()}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(["Item", "Total Issued", "Departments with Usage"])
        for row in report_list:
            writer.writerow([row["item"], row["total_quantity"], row["departments_with_usage"]])

        return response

    return render(request, "store/weekly.html", {
        "report_closed": False,
        "report_list": report_list,
        "window_label": window_label,
        "start_date": start_dt.date(),
        "end_date": end_dt.date(),
    })

