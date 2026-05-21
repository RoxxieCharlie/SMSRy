from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from store.models import UserProfile
from store.services.approval_service import toggle_supervisor


@login_required
def supervisor_toggle_view(request):
    from django.contrib.auth.models import User, Group

    if not request.user.is_staff:
        messages.error(request, "Admin access required.")
        return redirect("store:dashboard")

    management_group = Group.objects.get(name="Management")
    management_users = (
        User.objects.filter(groups=management_group)
        .order_by("username")
    )

    for user in management_users:
        UserProfile.objects.get_or_create(user=user)

    management_users = management_users.select_related("profile")

    current_supervisor = None
    try:
        current_supervisor = UserProfile.objects.select_related("user").get(
            is_active_supervisor=True
        ).user
    except UserProfile.DoesNotExist:
        pass

    if request.method == "POST":
        action = request.POST.get("action")
        target_id = request.POST.get("user_id")

        try:
            if action == "activate":
                toggle_supervisor(request.user, target_id, activate=True)
                messages.success(request, "Supervisor activated successfully.")
            elif action == "deactivate":
                toggle_supervisor(request.user, target_id, activate=False)
                messages.success(request, "Supervisor deactivated.")
            else:
                messages.error(request, "Invalid action.")
        except ValueError as e:
            messages.error(request, str(e))

        return redirect("store:supervisor_toggle")

    context = {
        "management_users": management_users,
        "current_supervisor": current_supervisor,
        "base_template": "store/mgt_base_v2.html",
    }
    return render(request, "store/supervisor_toggle.html", context)
