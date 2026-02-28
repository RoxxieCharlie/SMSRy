from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator

from store.decorators import group_required
from store.models import StockIn


@login_required
@group_required("Management")
def history_stockin_mgt(request):
    search_query = (request.GET.get("q") or "").strip()
    received_by_id = (request.GET.get("received_by") or "").strip()
    item_id = (request.GET.get("item") or "").strip()

    stockins = (
        StockIn.objects
        .select_related("received_by")
        .prefetch_related("lines__item")
        .order_by("-received_at")
    )

    if received_by_id.isdigit():
        stockins = stockins.filter(received_by__id=int(received_by_id))

    if item_id.isdigit():
        stockins = stockins.filter(lines__item__id=int(item_id)).distinct()

    if search_query:
        stockins = stockins.filter(
            Q(lines__item__name__icontains=search_query) |
            Q(received_by__username__icontains=search_query) |
            Q(received_by__first_name__icontains=search_query) |
            Q(received_by__last_name__icontains=search_query)
        ).distinct()

    paginator = Paginator(stockins, 30)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_range = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=1)

    return render(
        request,
        "store/history_stockin_mgt_v2.html",
        {
            "page_obj": page_obj,
            "page_range": page_range,
            "search_query": search_query,
            "received_by_id": int(received_by_id) if received_by_id.isdigit() else "",
            "item_id": int(item_id) if item_id.isdigit() else "",
        }
    )