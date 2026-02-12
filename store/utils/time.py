from datetime import timedelta
from django.utils import timezone

def is_within_edit_window(issuance, hours=6):
    return timezone.now() <= issuance.created_at + timedelta(hours=hours)
