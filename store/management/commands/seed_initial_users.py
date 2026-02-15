from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.utils import OperationalError
import time


class Command(BaseCommand):
    help = "Seeds initial users for the SMS system (users + groups + assignments)"

    def _create_user_if_missing(self, User, *, username, email, password, is_superuser=False):
        """
        Create user only if missing.
        Returns the user object.
        """
        user = User.objects.filter(username=username).first()
        if user:
            self.stdout.write(self.style.WARNING(f"⚠️ User already exists: {username}"))
            return user

        if is_superuser:
            user = User.objects.create_superuser(username=username, email=email, password=password)
        else:
            user = User.objects.create_user(username=username, email=email, password=password)

        self.stdout.write(self.style.SUCCESS(f"✅ Created: {username} / {password}"))
        return user

    def handle(self, *args, **options):
        User = get_user_model()

        users_to_seed = [
            dict(username="admin", email="admin@sms.com", password="Admin12345", is_superuser=True),
            dict(username="management", email="management@sms.com", password="Management12345", is_superuser=False),
            dict(username="storekeeper", email="storekeeper@sms.com", password="Storekeeper12345", is_superuser=False),
        ]

        for attempt in (1, 2):
            try:
                with transaction.atomic():
                    # 1) Ensure groups exist
                    mgmt_group, _ = Group.objects.get_or_create(name="Management")
                    sk_group, _ = Group.objects.get_or_create(name="StoreKeeper")

                    # 2) Ensure users exist
                    created_users = {}
                    for u in users_to_seed:
                        created_users[u["username"]] = self._create_user_if_missing(User, **u)

                    # 3) Assign group memberships (idempotent)
                    management_user = created_users["management"]
                    storekeeper_user = created_users["storekeeper"]

                    management_user.groups.add(mgmt_group)
                    storekeeper_user.groups.add(sk_group)

                    self.stdout.write(self.style.SUCCESS("✅ Groups assigned to users."))

                self.stdout.write(self.style.SUCCESS("🎉 Seeding complete."))
                return

            except OperationalError as e:
                if attempt == 2:
                    raise
                self.stdout.write(self.style.WARNING(f"⚠️ DB connection dropped, retrying... ({e})"))
                time.sleep(2)