from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import render

from store.decorators import group_required
from store.models import Item, Category


@login_required
@group_required("StoreKeeper")
def inventory_view(request):
    search_query = (request.GET.get("q") or "").strip()
    item_id = (request.GET.get("item") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    status = (request.GET.get("status") or "all").strip().lower()  # all | low | out | in

    items = Item.objects.select_related("category").all()

    # Exact item drilldown
    if item_id.isdigit():
        items = items.filter(id=int(item_id))

    # Search
    if search_query:
        items = items.filter(name__icontains=search_query)

    # Category
    if category_id.isdigit():
        items = items.filter(category_id=int(category_id))
    else:
        category_id = ""

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
    paginator = Paginator(items.order_by("name"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    categories = Category.objects.all().order_by("name")

    # KPI counts are global (not affected by current filters)
    total_items = Item.objects.count()
    out_of_stock = Item.objects.filter(quantity=0).count()
    low_stock = Item.objects.filter(quantity__gt=0, quantity__lte=F("reorder_level")).count()
    in_stock = Item.objects.filter(quantity__gt=F("reorder_level")).count()

    context = {
        "active_nav": "inventory",

        "page_obj": page_obj,
        "categories": categories,
        "search_query": search_query,
        "item_id": int(item_id) if item_id.isdigit() else "",
        "category_id": int(category_id) if str(category_id).isdigit() else "",
        "status": status,

        "total_items": total_items,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "in_stock": in_stock,
    }
    return render(request, "store/inventory_store_v2.html", context)