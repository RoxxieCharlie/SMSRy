from django.http import HttpResponseForbidden
from functools import wraps
from django.contrib.auth.decorators import user_passes_test

from functools import wraps
from django.http import HttpResponseForbidden

def group_required(*group_names):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Authentication required.")

            if not request.user.groups.filter(name__in=group_names).exists():
                return HttpResponseForbidden("You do not have access to this page.")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator



def storekeeper_required(view_func):
    return user_passes_test(
        lambda u: u.is_authenticated and u.groups.filter(name="StoreKeeper").exists()
    )(view_func)


