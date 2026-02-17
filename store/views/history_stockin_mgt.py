from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from store.decorators import group_required
from store.models import StockIn


@login_required
@group_required("Management")


def history_stockin_mgt(request):
    user = request.user
    search_query = request.GET.get("q", "")

    stockins = (
        StockIn.objects
        .select_related("received_by")
        .prefetch_related("lines__item")
        .order_by("-received_at")
    )

    if search_query:
        stockins = stockins.filter(
            Q(lines__item__name__icontains=search_query) |
            Q(received_by__first_name__icontains=search_query) |
            Q(received_by__last_name__icontains=search_query)
        ).distinct()

    paginator = Paginator(stockins, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "store/history_stockin_mgt.html",
        {
            "page_obj": page_obj,
            "search_query": search_query,
        }
    )
