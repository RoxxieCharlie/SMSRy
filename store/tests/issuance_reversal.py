from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User, Group

from store.models import (
    Issuance,
    IssuanceItem,
    IssuanceReversal,
    Item,
    Category,
    Staff,
    Department
)
from store.services.issuance_reversal_service import reverse_issuance


class IssuanceReversalTests(TestCase):

    def setUp(self):
        self.group = Group.objects.create(name="StoreKeeper")

        self.user = User.objects.create_user(
            username="store1",
            password="pass"
        )
        self.user.groups.add(self.group)

        dept = Department.objects.create(name="Operations")

        self.staff = Staff.objects.create(
            staff_id="SK001",
            name="Store Keeper",
            department=dept,
            job_roles="store-keeper"
        )

        cat = Category.objects.create(name="General")

        self.item1 = Item.objects.create(name="Item A", quantity=50, category=cat)
        self.item2 = Item.objects.create(name="Item B", quantity=20, category=cat)

        self.issuance = Issuance.objects.create(
            staff=self.staff,
            issued_by=self.user,
            issued_at=timezone.now(),
            comment="Test issuance"
        )

        IssuanceItem.objects.create(
            issuance=self.issuance,
            item=self.item1,
            quantity=5
        )
        IssuanceItem.objects.create(
            issuance=self.issuance,
            item=self.item2,
            quantity=10
        )

    def test_reverse_issuance_success(self):
        reverse_issuance(
            issuance_id=self.issuance.id,
            reversed_by=self.user,
            reversal_reason="Test"
        )

        self.item1.refresh_from_db()
        self.item2.refresh_from_db()

        self.assertEqual(self.item1.quantity, 55)
        self.assertEqual(self.item2.quantity, 30)

        self.assertTrue(
            IssuanceReversal.objects.filter(
                issuance=self.issuance
            ).exists()
        )

    def test_reverse_twice_fails(self):
        reverse_issuance(
            issuance_id=self.issuance.id,
            reversed_by=self.user,
            reversal_reason="First reversal"
        )

        with self.assertRaises(ValueError):
            reverse_issuance(
                issuance_id=self.issuance.id,
                reversed_by=self.user,
                reversal_reason="Second reversal"
            )

    def test_reverse_after_6_hours_fails(self):
        self.issuance.issued_at = timezone.now() - timedelta(hours=7)
        self.issuance.save()

        with self.assertRaises(PermissionError):
            reverse_issuance(
                issuance_id=self.issuance.id,
                reversed_by=self.user,
                reversal_reason="Too late"
            )
