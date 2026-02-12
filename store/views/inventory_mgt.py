from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from store.decorators import group_required
from store.models import Item, Category

@login_required
@group_required("Management")
def inventory_view_mgt(request):
    # Get search query and category filter from GET parameters
    search_query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "")

    # Base queryset
    items = Item.objects.select_related("category").all()

    # Apply search filter
    if search_query:
        items = items.filter(name__icontains=search_query)

    # Apply category filter
    if category_id:
        items = items.filter(category_id=category_id)

    # Pagination: 30 items per page
    paginator = Paginator(items, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get all categories for the filter dropdown
    categories = Category.objects.all()

    context = {
        "page_obj": page_obj,
        "categories": categories,
        "search_query": search_query,
        "category_id": category_id,
    }
    return render(request, "store/inventory_mgt.html", context)
