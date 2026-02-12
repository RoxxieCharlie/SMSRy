from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy

class StoreLoginView(LoginView):
    template_name = "store/login.html"
    redirect_authenticated_user = True
    success_url = reverse_lazy("dashboard")





class StoreLogoutView(LogoutView):
    next_page = reverse_lazy("login")
