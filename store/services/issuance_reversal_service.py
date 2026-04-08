from django.core.exceptions import ValidationError


def reverse_issuance(*, issuance_id, reversed_by):
    """
    Legacy reversal service is disabled.
    Issuance must be corrected only through request-based fulfillment edits.
    """
    raise ValidationError("Issuance reversal is disabled. Use request fulfillment edit flow.")
