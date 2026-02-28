from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import render

from store.decorators import group_required
from store.models import Item, Category


@login_required
@group_required("Management")
def inventory_view_mgt(request):
    search_query = request.GET.get("q", "").strip()
    category_id = (request.GET.get("category", "") or "").strip()
    status = (request.GET.get("status", "all") or "all").strip().lower()  # all | low | out | in

    items = Item.objects.select_related("category").all()

    # Search
    if search_query:
        items = items.filter(name__icontains=search_query)

    # Category
    if category_id:
        items = items.filter(category_id=category_id)

    # Status filter
    if status == "out":
        items = items.filter(quantity=0)
    elif status == "low":
        items = items.filter(quantity__gt=0, quantity__lte=F("reorder_level"))
    elif status == "in":
        items = items.filter(quantity__gt=F("reorder_level"))
    else:
        status = "all"

    # Pagination
    paginator = Paginator(items.order_by("name"), 30)
    page_obj = paginator.get_page(request.GET.get("page"))

    categories = Category.objects.all().order_by("name")

    # ✅ KPI counts MUST be global (ignore current filters)
    total_items = Item.objects.count()
    out_of_stock = Item.objects.filter(quantity=0).count()
    low_stock = Item.objects.filter(quantity__gt=0, quantity__lte=F("reorder_level")).count()
    in_stock = Item.objects.filter(quantity__gt=F("reorder_level")).count()

    context = {
        "active_nav": "inventory",

        "page_obj": page_obj,
        "categories": categories,
        "search_query": search_query,
        "category_id": category_id,
        "status": status,

        # ✅ KPIs for the cards
        "total_items": total_items,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "in_stock": in_stock,
    }
    return render(request, "store/inventory_mgt_v2.html", context)