from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator

from store.decorators import group_required
from store.models import StockIn


@login_required
@group_required("StoreKeeper")
def history_stockin(request):
    user = request.user
    q = (request.GET.get("q") or "").strip()
    item_id = (request.GET.get("item") or "").strip()

    stockins = (
        StockIn.objects
        .select_related("received_by")
        .prefetch_related("lines__item")
        .filter(received_by=user)          # ✅ scope to this storekeeper
        .order_by("-received_at")
    )

    if item_id.isdigit():
        stockins = stockins.filter(lines__item__id=int(item_id)).distinct()

    if q:
        stockins = stockins.filter(
            Q(lines__item__name__icontains=q) |
            Q(received_by__first_name__icontains=q) |
            Q(received_by__last_name__icontains=q) |
            Q(received_by__username__icontains=q)
        ).distinct()

    paginator = Paginator(stockins, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_range = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=1)

    return render(
        request,
        "store/history_stockin_store_v2.html",
        {
            "page_obj": page_obj,
            "page_range": page_range,
            "q": q,
            "item_id": int(item_id) if item_id.isdigit() else "",
        }
    )