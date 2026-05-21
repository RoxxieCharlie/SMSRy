from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from store.models import Category, Department, Item, Request, RequestItem, Staff
from store.services.issuance_service import IssuanceError, fulfill_request_service
from store.services.stockin_service import create_bulk_stockin


class StockInServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="storekeeper", password="test123")
        self.category = Category.objects.create(name="Building Materials")
        self.item = Item.objects.create(
            name="Cement",
            category=self.category,
            quantity=10,
            unit_of_measurement="pcs",
            reorder_level=5,
        )

    def test_stockin_increases_item_quantity(self):
        create_bulk_stockin(
            received_by=self.user,
            lines=[{"item_id": self.item.id, "quantity": 5}],
            comment="New delivery",
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 15)


class RequestFulfillmentServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="storekeeper", password="test123")

        self.department = Department.objects.create(name="Engineering")
        self.staff = Staff.objects.create(
            staff_id="ENG001",
            name="John Doe",
            department=self.department,
            job_roles="worker",
        )

        self.category = Category.objects.create(name="Safety")
        self.item = Item.objects.create(
            name="Helmet",
            category=self.category,
            quantity=10,
            unit_of_measurement="pcs",
            reorder_level=2,
        )

    def _make_submitted_request(self, requested_qty):
        request_obj = Request.objects.create(
            requester=self.staff,
            status=Request.Status.APPROVED,
            purpose="Site work",
        )
        request_item = RequestItem.objects.create(
            request=request_obj,
            item=self.item,
            requested_qty=requested_qty,
        )
        return request_obj, request_item

    def test_fulfillment_reduces_item_quantity(self):
        request_obj, request_item = self._make_submitted_request(requested_qty=3)

        issuance = fulfill_request_service(
            request_obj=request_obj,
            issued_by=self.user,
            items_with_qty=[
                {
                    "request_item_id": request_item.id,
                    "fulfilled_qty": 3,
                }
            ],
            comment="Site work",
        )

        self.item.refresh_from_db()
        request_obj.refresh_from_db()
        request_item.refresh_from_db()

        self.assertEqual(self.item.quantity, 7)
        self.assertEqual(request_obj.status, Request.Status.FULFILLED)
        self.assertEqual(request_item.fulfilled_qty, 3)
        self.assertEqual(issuance.request_id, request_obj.id)

    def test_cannot_fulfill_more_than_available(self):
        request_obj, request_item = self._make_submitted_request(requested_qty=11)

        with self.assertRaises(IssuanceError) as cm:
            fulfill_request_service(
                request_obj=request_obj,
                issued_by=self.user,
                items_with_qty=[
                    {
                        "request_item_id": request_item.id,
                        "fulfilled_qty": 11,
                    }
                ],
                comment="Attempt over-issuance",
            )

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)
        self.assertIn("Not enough stock", str(cm.exception))
