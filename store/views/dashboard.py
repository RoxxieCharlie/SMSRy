from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import HttpResponseForbidden
from django.db.models import F

from store.models import Activity, Item


@login_required
def dashboard_router(request):
    user = request.user

    if user.groups.filter(name="Management").exists():
        return redirect("dashboard_management")

    if user.groups.filter(name="StoreKeeper").exists():
        return redirect("dashboard_storekeeper")

    return HttpResponseForbidden("No dashboard assigned.")


@login_required
def dashboard_storekeeper(request):
    if not request.user.groups.filter(name="StoreKeeper").exists():
        return HttpResponseForbidden("Forbidden")

    activities = Activity.objects.order_by("-created_at")[:15]

    out_of_stock_items = Item.objects.filter(quantity=0).order_by("name")
    low_stock_items = Item.objects.filter(
        quantity__gt=0,
        quantity__lte=F("reorder_level"),
    ).order_by("quantity")

    context = {
        "activities": activities,
        "out_of_stock_items": out_of_stock_items,
        "low_stock_items": low_stock_items,
    }

    return render(request, "store/dashboard_storekeeper.html", context)


@login_required
def dashboard_management(request):
    if not request.user.groups.filter(name="Management").exists():
        return HttpResponseForbidden("Forbidden")

    activities = Activity.objects.order_by("-created_at")[:20]

    out_of_stock_items = Item.objects.filter(quantity=0).order_by("name")
    low_stock_items = Item.objects.filter(
        quantity__gt=0,
        quantity__lte=F("reorder_level"),
    ).order_by("quantity")

    context = {
        "activities": activities,
        "out_of_stock_items": out_of_stock_items,
        "low_stock_items": low_stock_items,
    }

    return render(request, "store/dashboard_management.html", context)
