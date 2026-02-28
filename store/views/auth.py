from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

class StoreLoginView(LoginView):
    template_name = "store/login.html"
    redirect_authenticated_user = True
    success_url = reverse_lazy("dashboard")





@method_decorator(csrf_protect, name="dispatch")
class StoreLogoutView(View):
    def post(self, request):
        logout(request)
        return redirect("store:login")
