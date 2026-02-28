# store/urls.py
from django.urls import path
from django.shortcuts import redirect
from django.contrib.auth.views import LogoutView

# Auth
from store.views.auth import StoreLoginView

# Search
from store.views.search import global_search

# Dashboards
from store.views.dashboard import (
    dashboard_router,
    dashboard_management,
    dashboard_storekeeper,
)

# Core modules
from store.views.inventory import inventory_view
from store.views.inventory_mgt import inventory_view_mgt
from store.views.stockin import stockin_view
from store.views.issuance import issuance_create

# History
from store.views.history_stockin import history_stockin
from store.views.history_stockin_mgt import history_stockin_mgt
from store.views.issuance_history import history_issuance_storekeeper
from store.views.issuance_history_mgt import history_issuance_management

# Issuance reversal
from store.views.issuance_reversal import issuance_reverse_view

# Reports
from store.views.weekly import weekly_report
from .views.landing import landing

app_name = "store"

urlpatterns = [
    # Root -> dashboard
    path("", landing, name="landing"),
    path("", lambda request: redirect("store:dashboard"), name="root"),

    # Authentication
    path("login/", StoreLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="store:login"), name="logout"),

    # Dashboards (canonical)
    path("dashboard/", dashboard_router, name="dashboard"),
    path("dashboard/management/", dashboard_management, name="dashboard_management_v2"),
    path("dashboard/storekeeper/", dashboard_storekeeper, name="dashboard_storekeeper_v2"),

    # Dashboards (aliases for old template links)
    path("dashboard/management/", dashboard_management, name="dashboard_management"),
    path("dashboard/storekeeper/", dashboard_storekeeper, name="dashboard_storekeeper"),

    # Inventory & Stock (canonical)
    path("inventory/store/", inventory_view, name="inventory_store_v2"),
    path("inventory/management/", inventory_view_mgt, name="inventory_mgt_v2"),
    path("stockin/", stockin_view, name="stockin_v2"),

    # Inventory & Stock (aliases)
    path("inventory/store/", inventory_view, name="inventory_store"),
    path("inventory/management/", inventory_view_mgt, name="inventory_mgt"),
    path("stockin/", stockin_view, name="stockin"),

    # Global Search
    path("search/", global_search, name="global_search"),

    # Issuance (canonical)
    path("issuance/new/", issuance_create, name="issuance_create_v2"),
    path("issuance/<int:issuance_id>/reverse/", issuance_reverse_view, name="issuance_reverse"),

    # Issuance (aliases)
    path("issuance/new/", issuance_create, name="issuance_create"),

    # History (canonical)
    path("history/issuance/storekeeper/", history_issuance_storekeeper, name="history_issuance_storekeeper_v2"),
    path("history/issuance/management/", history_issuance_management, name="history_issuance_management_v2"),
    path("history/stockin/store/", history_stockin, name="history_stockin_store_v2"),
    path("history/stockin/management/", history_stockin_mgt, name="history_stockin_mgt_v2"),

    # History (aliases)
    path("history/issuance/storekeeper/", history_issuance_storekeeper, name="history_issuance_storekeeper"),
    path("history/issuance/management/", history_issuance_management, name="history_issuance_management"),
    path("history/stockin/store/", history_stockin, name="history_stockin_store"),
    path("history/stockin/management/", history_stockin_mgt, name="history_stockin_mgt"),

    # Reports (canonical)
    path("weekly/", weekly_report, name="weekly_v2"),

    # Reports (alias)
    path("weekly/", weekly_report, name="weekly"),
]