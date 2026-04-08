from django.http import Http404


def issuance_reverse_view(request, issuance_id):
    """
    Legacy reversal entrypoint is permanently disabled.
    Use request-based issuance edit within the fulfillment edit window.
    """
    raise Http404("Issuance reversal is disabled.")
