from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone

from store.models import Category, Department, Item, Request, RequestItem, Staff
from store.services.issuance_service import IssuanceError, edit_issuance_service, fulfill_request_service


class IssuanceEditWindowTests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name="StoreKeeper")

        self.user = User.objects.create_user(username="store1", password="pass")
        self.user.groups.add(self.group)

        dept = Department.objects.create(name="Operations")

        self.staff = Staff.objects.create(
            staff_id="SK001",
            name="Store Keeper",
            department=dept,
            job_roles="store-keeper",
        )

        cat = Category.objects.create(name="General")

        self.item1 = Item.objects.create(
            name="Item A",
            quantity=50,
            category=cat,
            unit_of_measurement="pcs",
            reorder_level=5,
        )
        self.item2 = Item.objects.create(
            name="Item B",
            quantity=20,
            category=cat,
            unit_of_measurement="pcs",
            reorder_level=5,
        )

        self.request_obj = Request.objects.create(
            requester=self.staff,
            status=Request.Status.SUBMITTED,
            purpose="Operations request",
        )
        self.request_item1 = RequestItem.objects.create(
            request=self.request_obj,
            item=self.item1,
            requested_qty=5,
        )
        self.request_item2 = RequestItem.objects.create(
            request=self.request_obj,
            item=self.item2,
            requested_qty=10,
        )

        self.issuance = fulfill_request_service(
            request_obj=self.request_obj,
            issued_by=self.user,
            items_with_qty=[
                {"request_item_id": self.request_item1.id, "fulfilled_qty": 5},
                {"request_item_id": self.request_item2.id, "fulfilled_qty": 10},
            ],
            comment="Initial fulfillment",
        )

    def test_edit_issuance_success(self):
        edit_issuance_service(
            request_obj=self.request_obj,
            edited_by=self.user,
            items_with_qty=[
                {"request_item_id": self.request_item1.id, "fulfilled_qty": 3},
                {"request_item_id": self.request_item2.id, "fulfilled_qty": 8},
            ],
            reason="Correcting counted quantities",
        )

        self.item1.refresh_from_db()
        self.item2.refresh_from_db()
        self.request_item1.refresh_from_db()
        self.request_item2.refresh_from_db()

        self.assertEqual(self.item1.quantity, 47)
        self.assertEqual(self.item2.quantity, 12)
        self.assertEqual(self.request_item1.fulfilled_qty, 3)
        self.assertEqual(self.request_item2.fulfilled_qty, 8)

    def test_edit_after_window_fails(self):
        self.request_obj.fulfilled_at = timezone.now() - timedelta(hours=7)
        self.request_obj.editable_until = timezone.now() - timedelta(hours=1)
        self.request_obj.status = Request.Status.FULFILLED
        self.request_obj.save(update_fields=["fulfilled_at", "editable_until", "status", "updated_at"])

        with self.assertRaises(IssuanceError):
            edit_issuance_service(
                request_obj=self.request_obj,
                edited_by=self.user,
                items_with_qty=[
                    {"request_item_id": self.request_item1.id, "fulfilled_qty": 4},
                    {"request_item_id": self.request_item2.id, "fulfilled_qty": 9},
                ],
                reason="Late update attempt",
            )
