from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from decouple import config


class Command(BaseCommand):
    help = "Create or promote a bootstrap admin user from environment variables."

    def handle(self, *args, **options):
        username = config("BOOTSTRAP_ADMIN_USERNAME", default="").strip()
        password = config("BOOTSTRAP_ADMIN_PASSWORD", default="").strip()
        email = config("BOOTSTRAP_ADMIN_EMAIL", default="").strip()

        if not username or not password:
            self.stdout.write("Bootstrap admin skipped.")
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_active": True,
                "is_superuser": True,
                "is_staff": False,
            },
        )

        changed = False

        if email and user.email != email:
            user.email = email
            changed = True

        if not user.is_active:
            user.is_active = True
            changed = True

        if not user.is_superuser:
            user.is_superuser = True
            changed = True

        if user.is_staff:
            user.is_staff = False
            changed = True

        user.set_password(password)
        changed = True

        if created or changed:
            user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Bootstrap admin created: {username}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Bootstrap admin updated: {username}"))
