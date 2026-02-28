# store/views/search.py
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.db.models import Q
from django.urls import reverse

from store.models import Item, Staff, Department


def _is_ajax(request) -> bool:
    # works for fetch/XHR
    return request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in (request.headers.get("accept") or "")


def global_search(request):
    q = (request.GET.get("q") or "").strip()
    fmt = (request.GET.get("format") or "").lower()  # optional: json/html

    if not q:
        if _is_ajax(request) or fmt == "json":
            return JsonResponse({"items": [], "staff": [], "storekeepers": [], "departments": []})
        # non-ajax: just bounce back to dashboard
        return HttpResponseRedirect(reverse("store:dashboard"))

    # --- querysets (light + fast) ---
    items_qs = Item.objects.filter(name__icontains=q).order_by("name")[:5]

    staffs_qs = (
        Staff.objects.select_related("department")
        .filter(Q(name__icontains=q) | Q(staff_id__icontains=q))
        .order_by("name")[:5]
    )

    departments_qs = Department.objects.filter(name__icontains=q).order_by("name")[:5]

    storekeepers_qs = (
        User.objects.filter(groups__name__iexact="StoreKeeper")
        .filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
        .order_by("first_name", "username")[:5]
    )

    # --- non-ajax HTML behavior (smart redirect) ---
    if not (_is_ajax(request) or fmt == "json"):
        # Priority: exact item match -> item issuance filter
        exact_item = Item.objects.filter(name__iexact=q).first()
        if exact_item:
            url = reverse("store:history_issuance_storekeeper") + f"?item={exact_item.id}"
            return HttpResponseRedirect(url)

        # Exact staff_id -> staff issuances
        exact_staff = Staff.objects.filter(staff_id__iexact=q).first()
        if exact_staff:
            url = reverse("store:history_issuance_storekeeper") + f"?staff={exact_staff.id}"
            return HttpResponseRedirect(url)

        # User/storekeeper match -> their issuance history (management)
        exact_user = (
            User.objects.filter(groups__name__iexact="StoreKeeper")
            .filter(Q(username__iexact=q) | Q(first_name__iexact=q) | Q(last_name__iexact=q))
            .first()
        )
        if exact_user:
            url = reverse("store:history_issuance_management") + f"?issued_by={exact_user.id}"
            return HttpResponseRedirect(url)

        # Otherwise go to inventory filtered by q (best general landing)
        url = reverse("store:inventory_store") + f"?q={q}"
        return HttpResponseRedirect(url)

    # --- JSON (autocomplete) ---
    return JsonResponse({
        "items": [
            {
                "label": it.name,
                "meta": f"Qty: {it.quantity}",
                "actions": [
                    {"label": "Inventory", "url": reverse("store:inventory_store") + f"?q={it.name}"},
                    {"label": "Issuances", "url": reverse("store:history_issuance_storekeeper") + f"?item={it.id}"},
                    {"label": "Stock-ins", "url": reverse("store:history_stockin_store") + f"?item={it.id}"},
                ],
            }
            for it in items_qs
        ],
        "staff": [
            {
                "label": s.name,
                "meta": f"{s.department.name if s.department else 'No dept'} • {s.staff_id}",
                "actions": [
                    {"label": "Issuances", "url": reverse("store:history_issuance_storekeeper") + f"?staff={s.id}"},
                ],
            }
            for s in staffs_qs
        ],
        "storekeepers": [
            {
                "label": (u.get_full_name() or u.username),
                "meta": f"@{u.username}",
                "actions": [
                    {"label": "Issuances", "url": reverse("store:history_issuance_management") + f"?issued_by={u.id}"},
                    {"label": "Stock-ins", "url": reverse("store:history_stockin_mgt") + f"?received_by={u.id}"},
                ],
            }
            for u in storekeepers_qs
        ],
        "departments": [
            {
                "label": d.name,
                "meta": "Department",
                "actions": [
                    {"label": "Issuances", "url": reverse("store:history_issuance_storekeeper") + f"?department={d.id}"},
                ],
            }
            for d in departments_qs
        ],
    })