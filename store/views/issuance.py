from django.http import Http404


def issuance_create(request):
    """
    Legacy manual issuance entrypoint is permanently disabled.
    Issuance must only be created via request fulfillment.
    """
    raise Http404("Manual issuance is disabled. Use request fulfillment.")
