from django.test import TestCase
from django.contrib.auth.models import User
from store.models import Category, Item
from store.services.stockin_service import create_stockin
from django.core.exceptions import ValidationError
from store.models import (
    Category,
    Item,
    Department,
    Staff,
)
from store.services.issuance_service import create_issuance



# Stockin Test case

class StockInServiceTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="storekeeper",
            password="test123"
        )

        self.category = Category.objects.create(
            name="Building Materials"
        )

        self.item = Item.objects.create(
            name="Cement",
            category=self.category,
            quantity=10,
            unit_of_measurement="pcs",
            reorder_level=5
        )

    def test_stockin_increases_item_quantity(self):
        create_stockin(
            item=self.item,
            quantity=5,
            received_by=self.user,
            comment="New delivery"
        )

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 15)

#issuance test case

class IssuanceServiceTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="storekeeper",
            password="test123"
        )

        self.department = Department.objects.create(
            name="Engineering"
        )

        self.staff = Staff.objects.create(
            staff_id="ENG001",
            name="John Doe",
            department=self.department,
            job_roles="Engineer",
        )

        self.category = Category.objects.create(
            name="Safety"
        )

        self.item = Item.objects.create(
            name="Helmet",
            category=self.category,
            quantity=10,
            unit_of_measurement="pcs",
            reorder_level=2,
        )

    def test_issuance_reduces_item_quantity(self):
        create_issuance(
            staff=self.staff,
            issued_by=self.user,
            lines=[
                {
                    "item": self.item,
                    "quantity": 3,
                }
            ],
            comment="Site work"
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 7)

#Test Case for negative stock


class IssuanceOverIssueTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="storekeeper",
            password="test123"
        )

        self.department = Department.objects.create(name="Engineering")

        self.staff = Staff.objects.create(
            staff_id="ENG001",
            name="John Doe",
            department=self.department,
            job_roles="Engineer"
        )

        self.category = Category.objects.create(name="Safety")

        self.item = Item.objects.create(
            name="Helmet",
            category=self.category,
            quantity=5,  # limited stock
            unit_of_measurement="pcs",
            reorder_level=2
        )

    def test_cannot_issue_more_than_available(self):
        with self.assertRaises(ValidationError) as cm:
            create_issuance(
                staff=self.staff,
                issued_by=self.user,
                lines=[
                    {"item": self.item, "quantity": 10}  # > available
                ],
                comment="Attempt over-issuance"
            )

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 5)  # quantity unchanged

        # Optional: check error message
        self.assertIn("Insufficient stock", str(cm.exception))
