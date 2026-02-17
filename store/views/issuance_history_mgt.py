from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q

from store.models import Issuance, Department
from store.decorators import group_required


@login_required
@group_required("Management")
def history_issuance_management(request):
    # ✅ Management should see ALL issuances, not only what they issued
    issuances = (
        Issuance.objects
        .select_related("staff", "issued_by", "staff__department")
        .prefetch_related("items__item")
        .order_by("-issued_at")
    )

    # Search & filter
    search_query = request.GET.get("q", "").strip()
    department_id = request.GET.get("department", "").strip()

    if search_query:
        issuances = issuances.filter(
            Q(staff__name__icontains=search_query)
            | Q(items__item__name__icontains=search_query)
            | Q(issued_by__username__icontains=search_query)
            | Q(issued_by__first_name__icontains=search_query)
            | Q(issued_by__last_name__icontains=search_query)
        ).distinct()

    if department_id:
        issuances = issuances.filter(staff__department__id=department_id)

    paginator = Paginator(issuances, 30)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "department_id": department_id,  # ✅ keep as string
        "departments": Department.objects.all().order_by("name"),
    }
    return render(request, "store/store:history_issuance_management.html", context)
