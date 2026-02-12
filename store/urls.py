from django.urls import path
from django.shortcuts import redirect

# Auth
from store.views.auth import StoreLoginView, StoreLogoutView

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

app_name = "store"

urlpatterns = [
    # Root -> dashboard
    path("", lambda request: redirect("store:dashboard"), name="root"),

    # Authentication
    path("login/", StoreLoginView.as_view(), name="login"),
    path("logout/", StoreLogoutView.as_view(next_page="store:login"), name="logout"),

    # Dashboards
    path("dashboard/", dashboard_router, name="dashboard"),
    path("dashboard/management/", dashboard_management, name="dashboard_management"),
    path("dashboard/storekeeper/", dashboard_storekeeper, name="dashboard_storekeeper"),

    # Inventory & Stock
    path("inventory/store/", inventory_view, name="inventory_store"),
    path("inventory/management/", inventory_view_mgt, name="inventory_mgt"),
    path("stockin/", stockin_view, name="stockin"),

    # Issuance
    path("issuance/new/", issuance_create, name="issuance_create"),
    path("issuance/<int:issuance_id>/reverse/", issuance_reverse_view, name="issuance_reverse"),

    # History
    path("history/issuance/storekeeper/", history_issuance_storekeeper, name="history_issuance_storekeeper"),
    path("history/issuance/management/", history_issuance_management, name="history_issuance_management"),
    path("history/stockin/store/", history_stockin, name="history_stockin_store"),
    path("history/stockin/management/", history_stockin_mgt, name="history_stockin_mgt"),

    # Reports
    path("weekly/", weekly_report, name="weekly"),
]