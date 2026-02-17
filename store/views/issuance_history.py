from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from store.models import Issuance, Department
from store.decorators import group_required

@login_required
@group_required("StoreKeeper")
def history_issuance_storekeeper(request):
    user = request.user

    # Fetch issuances for this storekeeper
    issuances = (
        Issuance.objects
        .select_related("staff", "issued_by", "staff__department")
        .prefetch_related("items__item")
        .filter(issued_by=user)
        .order_by("-issued_at")
    )

    # Search & filter
    search_query = request.GET.get("q", "")
    department_id = request.GET.get("department", "")

    if search_query:
        issuances = issuances.filter(
            Q(staff__name__icontains=search_query) |
            Q(items__item__name__icontains=search_query)
        ).distinct()

    if department_id:
        issuances = issuances.filter(staff__department__id=department_id)

    paginator = Paginator(issuances, 30)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "department_id": int(department_id) if department_id else "",
        "departments": Department.objects.all(),
    }

    return render(request, "store/store:history_issuance_storekeeper.html", context)


