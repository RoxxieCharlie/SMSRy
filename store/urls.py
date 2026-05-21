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
    dashboard_staff,
)

# Core modules
from store.views.inventory import inventory_view
from store.views.inventory_mgt import inventory_view_mgt
from store.views.stockin import stockin_view

# Request system
from store.views.request import (
    request_list,
    request_history,
    request_history_table,
    request_create,
    request_edit,
    request_submit,
    request_fulfill,
    request_edit_issuance,
)

# Supervisor approval
from store.views.approval import (
    approval_queue,
    approval_detail,
    approve_request_view,
    reject_request_view,
    delete_item_view,
)

# History
from store.views.history_stockin import history_stockin
from store.views.history_stockin_mgt import history_stockin_mgt
from store.views.issuance_history import history_issuance_storekeeper
from store.views.issuance_history_mgt import history_issuance_management

# Reports
from store.views.weekly import weekly_report
from .views.landing import landing


app_name = "store"


urlpatterns = [

    # =========================
    # ROOT
    # =========================
    path("", landing, name="landing"),
    path("", lambda request: redirect("store:dashboard"), name="root"),


    # =========================
    # AUTH
    # =========================
    path("login/", StoreLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="store:login"), name="logout"),


    # =========================
    # DASHBOARDS
    # =========================
    path("dashboard/", dashboard_router, name="dashboard"),

    path("dashboard/management/", dashboard_management, name="dashboard_management_v2"),
    path("dashboard/storekeeper/", dashboard_storekeeper, name="dashboard_storekeeper_v2"),
    path("dashboard/staff/", dashboard_staff, name="dashboard_staff_v2"),

    path("dashboard/management/", dashboard_management, name="dashboard_management"),
    path("dashboard/storekeeper/", dashboard_storekeeper, name="dashboard_storekeeper"),


    # =========================
    # INVENTORY
    # =========================
    path("inventory/store/", inventory_view, name="inventory_store_v2"),
    path("inventory/management/", inventory_view_mgt, name="inventory_mgt_v2"),

    path("inventory/store/", inventory_view, name="inventory_store"),
    path("inventory/management/", inventory_view_mgt, name="inventory_mgt"),


    # =========================
    # STOCK IN
    # =========================
    path("stockin/", stockin_view, name="stockin_v2"),
    path("stockin/", stockin_view, name="stockin"),


    # =========================
    # REQUEST SYSTEM
    # =========================

    # staff request list
    path("requests/", request_list, name="request_list"),
    path("requests/history/", request_history, name="request_history"),
    path("requests/history/table/", request_history_table, name="request_history_table"),

    # staff create request
    path("requests/new/", request_create, name="request_create"),

    # staff edit request (before fulfillment)
    path("requests/<int:request_id>/edit/", request_edit, name="request_edit"),

    # submit request
    path("requests/<int:request_id>/submit/", request_submit, name="request_submit"),

    # storekeeper fulfill request
    path("requests/<int:request_id>/fulfill/", request_fulfill, name="request_fulfill"),

    # storekeeper edit issuance within 6 hours
    path(
        "requests/<int:request_id>/edit-issuance/",
        request_edit_issuance,
        name="request_edit_issuance",
    ),


    # =========================
    # GLOBAL SEARCH
    # =========================
    path("search/", global_search, name="global_search"),


    # =========================
    # HISTORY
    # =========================
    path(
        "history/issuance/storekeeper/",
        history_issuance_storekeeper,
        name="history_issuance_storekeeper_v2",
    ),
    path(
        "history/issuance/management/",
        history_issuance_management,
        name="history_issuance_management_v2",
    ),
    path(
        "history/stockin/store/",
        history_stockin,
        name="history_stockin_store_v2",
    ),
    path(
        "history/stockin/management/",
        history_stockin_mgt,
        name="history_stockin_mgt_v2",
    ),

    path(
        "history/issuance/storekeeper/",
        history_issuance_storekeeper,
        name="history_issuance_storekeeper",
    ),
    path(
        "history/issuance/management/",
        history_issuance_management,
        name="history_issuance_management",
    ),
    path(
        "history/stockin/store/",
        history_stockin,
        name="history_stockin_store",
    ),
    path(
        "history/stockin/management/",
        history_stockin_mgt,
        name="history_stockin_mgt",
    ),


    # =========================
    # REPORTS
    # =========================
    path("weekly/", weekly_report, name="weekly_v2"),
    path("weekly/", weekly_report, name="weekly"),


    # =========================
    # SUPERVISOR APPROVAL
    # =========================
    path("approvals/", approval_queue, name="approval_queue"),
    path("approvals/<int:pk>/", approval_detail, name="approval_detail"),
    path("approvals/<int:pk>/approve/", approve_request_view, name="approve_request"),
    path("approvals/<int:pk>/reject/", reject_request_view, name="reject_request"),
    path("approvals/<int:pk>/items/<int:item_id>/delete/", delete_item_view, name="approval_delete_item"),

]
