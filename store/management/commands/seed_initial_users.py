from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.utils import OperationalError
import time


class Command(BaseCommand):
    help = "Seeds initial users for the SMS system"

    def _create_user_if_missing(self, User, *, username, email, password, is_superuser=False):
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"⚠️ User already exists: {username}"))
            return

        if is_superuser:
            User.objects.create_superuser(username=username, email=email, password=password)
        else:
            User.objects.create_user(username=username, email=email, password=password)

        self.stdout.write(self.style.SUCCESS(f"✅ Created: {username} / {password}"))

    def handle(self, *args, **options):
        User = get_user_model()

        users_to_seed = [
            dict(username="admin", email="admin@sms.com", password="Admin12345", is_superuser=True),
            dict(username="management", email="management@sms.com", password="Management12345", is_superuser=False),
            dict(username="storekeeper", email="storekeeper@sms.com", password="Storekeeper12345", is_superuser=False),
        ]

        # Retry once if the remote DB drops connection mid-run
        for attempt in (1, 2):
            try:
                with transaction.atomic():
                    for u in users_to_seed:
                        self._create_user_if_missing(User, **u)

                self.stdout.write(self.style.SUCCESS("🎉 Seeding complete."))
                return

            except OperationalError as e:
                if attempt == 2:
                    raise
                self.stdout.write(self.style.WARNING(f"⚠️ DB connection dropped, retrying... ({e})"))
                time.sleep(2)