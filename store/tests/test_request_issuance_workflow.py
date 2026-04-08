from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from store.models import Activity, Category, Department, Issuance, IssuanceItem, Item, Request, RequestActivity, RequestItem, Staff
from store.services.issuance_service import IssuanceError, edit_issuance_service, fulfill_request_service


class RequestBasedIssuanceWorkflowTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Engineering")
        self.category = Category.objects.create(name="Tools")

        self.item_1 = Item.objects.create(
            name="Safety Helmet",
            category=self.category,
            quantity=30,
            unit_of_measurement="pcs",
            reorder_level=3,
        )
        self.item_2 = Item.objects.create(
            name="Hand Gloves",
            category=self.category,
            quantity=20,
            unit_of_measurement="pairs",
            reorder_level=2,
        )

        self.staff_user_1 = User.objects.create_user(username="staff1", password="pass")
        self.staff_user_2 = User.objects.create_user(username="staff2", password="pass")
        self.storekeeper_user = User.objects.create_user(username="storekeeper", password="pass")
        self.management_user = User.objects.create_user(username="manager1", password="pass")

        self.staff_group, _ = Group.objects.get_or_create(name="Staff")
        self.storekeeper_group, _ = Group.objects.get_or_create(name="StoreKeeper")
        self.management_group, _ = Group.objects.get_or_create(name="Management")

        self.staff_user_1.groups.add(self.staff_group)
        self.staff_user_2.groups.add(self.staff_group)
        self.storekeeper_user.groups.add(self.storekeeper_group)
        self.management_user.groups.add(self.management_group)

        self.staff_1 = Staff.objects.create(
            user=self.staff_user_1,
            staff_id="STF001",
            name="Staff One",
            department=self.department,
            job_roles="worker",
        )
        self.staff_2 = Staff.objects.create(
            user=self.staff_user_2,
            staff_id="STF002",
            name="Staff Two",
            department=self.department,
            job_roles="worker",
        )
        self.management_staff = Staff.objects.create(
            user=self.management_user,
            staff_id="MGT001",
            name="Manager One",
            department=self.department,
            job_roles="project manager",
        )

        Staff.objects.create(
            user=self.storekeeper_user,
            staff_id="SK001",
            name="Store Keeper",
            department=self.department,
            job_roles="store-keeper",
        )

    def _create_submitted_request(self, requester, requested_qty=5):
        request_obj = Request.objects.create(
            requester=requester,
            status=Request.Status.SUBMITTED,
            purpose="Site work",
        )
        request_item = RequestItem.objects.create(
            request=request_obj,
            item=self.item_1,
            requested_qty=requested_qty,
        )
        return request_obj, request_item

    def _fulfill_via_view(self, request_obj, request_item, fulfilled_qty):
        self.client.force_login(self.storekeeper_user)
        return self.client.post(
            reverse("store:request_fulfill", kwargs={"request_id": request_obj.id}),
            {
                "comment": "Fulfilled by storekeeper",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "1",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-request_item_id": str(request_item.id),
                "lines-0-fulfilled_qty": str(fulfilled_qty),
            },
        )

    def test_01_staff_can_create_and_edit_own_request_before_fulfillment(self):
        self.client.force_login(self.staff_user_1)

        create_response = self.client.post(
            reverse("store:request_create"),
            {
                "purpose": "Initial request",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "3",
            },
        )
        self.assertEqual(create_response.status_code, 302)

        request_obj = Request.objects.get(requester=self.staff_1)
        request_item = RequestItem.objects.get(request=request_obj, item=self.item_1)
        self.assertEqual(request_obj.status, Request.Status.DRAFT)
        self.assertEqual(request_item.requested_qty, 3)

        edit_response = self.client.post(
            reverse("store:request_edit", kwargs={"request_id": request_obj.id}),
            {
                "purpose": "Updated request",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "5",
            },
        )
        self.assertEqual(edit_response.status_code, 302)

        request_obj.refresh_from_db()
        updated_item = RequestItem.objects.get(request=request_obj, item=self.item_1)
        self.assertEqual(request_obj.purpose, "Updated request")
        self.assertEqual(updated_item.requested_qty, 5)

    def test_02_staff_cannot_edit_request_after_fulfillment(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=4)
        fulfill_request_service(
            request_obj=request_obj,
            issued_by=self.storekeeper_user,
            items_with_qty=[{"request_item_id": request_item.id, "fulfilled_qty": 4}],
            comment="Initial fulfillment",
        )

        self.client.force_login(self.staff_user_1)
        response = self.client.post(
            reverse("store:request_edit", kwargs={"request_id": request_obj.id}),
            {
                "purpose": "Attempted edit after fulfillment",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "2",
            },
        )

        self.assertEqual(response.status_code, 302)
        request_obj.refresh_from_db()
        request_item.refresh_from_db()
        self.assertEqual(request_obj.status, Request.Status.FULFILLED)
        self.assertEqual(request_item.requested_qty, 4)

    def test_03_staff_cannot_edit_another_staff_request(self):
        request_obj = Request.objects.create(
            requester=self.staff_2,
            status=Request.Status.DRAFT,
            purpose="Staff 2 request",
        )
        RequestItem.objects.create(request=request_obj, item=self.item_1, requested_qty=3)

        self.client.force_login(self.staff_user_1)
        response = self.client.post(
            reverse("store:request_edit", kwargs={"request_id": request_obj.id}),
            {
                "purpose": "Malicious update",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "10",
            },
        )

        self.assertEqual(response.status_code, 404)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.purpose, "Staff 2 request")

    def test_04_storekeeper_can_fulfill_submitted_request(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=4)

        response = self._fulfill_via_view(request_obj, request_item, fulfilled_qty=4)

        self.assertEqual(response.status_code, 302)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status, Request.Status.FULFILLED)

    def test_05_fulfilling_request_creates_issuance_automatically(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=3)

        self._fulfill_via_view(request_obj, request_item, fulfilled_qty=3)

        self.assertTrue(Issuance.objects.filter(request=request_obj).exists())
        issuance = Issuance.objects.get(request=request_obj)
        self.assertTrue(IssuanceItem.objects.filter(issuance=issuance, item=self.item_1, quantity=3).exists())

    def test_06_fulfilling_deducts_stock_correctly(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=6)

        self._fulfill_via_view(request_obj, request_item, fulfilled_qty=6)

        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.quantity, 24)

    def test_07_storekeeper_cannot_fulfill_request_twice(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=2)

        first = self._fulfill_via_view(request_obj, request_item, fulfilled_qty=2)
        second = self._fulfill_via_view(request_obj, request_item, fulfilled_qty=2)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Issuance.objects.filter(request=request_obj).count(), 1)

    def test_08_issuance_edit_within_6_hours_updates_stock_by_delta(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=5)
        self._fulfill_via_view(request_obj, request_item, fulfilled_qty=4)

        self.client.force_login(self.storekeeper_user)
        response = self.client.post(
            reverse("store:request_edit_issuance", kwargs={"request_id": request_obj.id}),
            {
                "reason": "Correction after recount",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-request_item_id": str(request_item.id),
                "lines-0-fulfilled_qty": "2",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.item_1.refresh_from_db()
        request_item.refresh_from_db()
        self.assertEqual(request_item.fulfilled_qty, 2)
        self.assertEqual(self.item_1.quantity, 28)

    def test_09_issuance_edit_cannot_exceed_requested_quantity(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=3)
        self._fulfill_via_view(request_obj, request_item, fulfilled_qty=2)

        self.client.force_login(self.storekeeper_user)
        response = self.client.post(
            reverse("store:request_edit_issuance", kwargs={"request_id": request_obj.id}),
            {
                "reason": "Attempt invalid increase",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-request_item_id": str(request_item.id),
                "lines-0-fulfilled_qty": "4",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.item_1.refresh_from_db()
        request_item.refresh_from_db()
        self.assertEqual(request_item.fulfilled_qty, 2)
        self.assertEqual(self.item_1.quantity, 28)

    def test_10_issuance_edit_cannot_add_new_items(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=4)
        self._fulfill_via_view(request_obj, request_item, fulfilled_qty=2)

        self.client.force_login(self.storekeeper_user)
        response = self.client.post(
            reverse("store:request_edit_issuance", kwargs={"request_id": request_obj.id}),
            {
                "reason": "Attempt to add extra item",
                "lines-TOTAL_FORMS": "2",
                "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-request_item_id": str(request_item.id),
                "lines-0-fulfilled_qty": "2",
                "lines-1-request_item_id": "99999",
                "lines-1-fulfilled_qty": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request_obj.items.count(), 1)
        self.assertFalse(
            IssuanceItem.objects.filter(issuance__request=request_obj, item=self.item_2).exists()
        )

    def test_11_issuance_edit_after_6_hours_fails(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=4)
        self._fulfill_via_view(request_obj, request_item, fulfilled_qty=3)

        request_obj.refresh_from_db()
        request_obj.fulfilled_at = timezone.now() - timedelta(hours=7)
        request_obj.editable_until = timezone.now() - timedelta(hours=1)
        request_obj.status = Request.Status.FULFILLED
        request_obj.save(update_fields=["fulfilled_at", "editable_until", "status", "updated_at"])

        with self.assertRaises(IssuanceError):
            edit_issuance_service(
                request_obj=request_obj,
                edited_by=self.storekeeper_user,
                items_with_qty=[{"request_item_id": request_item.id, "fulfilled_qty": 1}],
                reason="Late edit",
            )

        request_obj.refresh_from_db()
        request_item.refresh_from_db()
        self.item_1.refresh_from_db()
        self.assertIn(request_obj.status, [Request.Status.FULFILLED, Request.Status.LOCKED])
        self.assertEqual(request_item.fulfilled_qty, 3)
        self.assertEqual(self.item_1.quantity, 27)

    def test_12_non_storekeeper_cannot_access_fulfill_or_edit_issuance_views(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=2)
        self.client.force_login(self.staff_user_1)

        fulfill_response = self.client.get(
            reverse("store:request_fulfill", kwargs={"request_id": request_obj.id})
        )
        self.assertEqual(fulfill_response.status_code, 404)

        fulfill_request_service(
            request_obj=request_obj,
            issued_by=self.storekeeper_user,
            items_with_qty=[{"request_item_id": request_item.id, "fulfilled_qty": 2}],
            comment="Fulfilled",
        )

        edit_response = self.client.get(
            reverse("store:request_edit_issuance", kwargs={"request_id": request_obj.id})
        )
        self.assertEqual(edit_response.status_code, 404)

    def test_13_request_list_shows_only_logged_in_staff_requests(self):
        own_request = Request.objects.create(requester=self.staff_1, status=Request.Status.DRAFT, purpose="Own")
        Request.objects.create(requester=self.staff_2, status=Request.Status.DRAFT, purpose="Other")
        RequestItem.objects.create(request=own_request, item=self.item_1, requested_qty=1)

        self.client.force_login(self.staff_user_1)
        response = self.client.get(reverse("store:request_list"))

        self.assertEqual(response.status_code, 200)
        listed_ids = {obj.id for obj in response.context["requests"]}
        self.assertIn(own_request.id, listed_ids)
        self.assertEqual(len(listed_ids), 1)

    def test_14_request_list_renders_staff_history_title(self):
        self.client.force_login(self.staff_user_1)
        response = self.client.get(reverse("store:request_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Requests")
        self.assertContains(response, "Request History and Status Tracking")

    def test_15_staff_sees_read_only_request_page_after_fulfillment(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=4)
        fulfill_request_service(
            request_obj=request_obj,
            issued_by=self.storekeeper_user,
            items_with_qty=[{"request_item_id": request_item.id, "fulfilled_qty": 4}],
            comment="Fulfilled",
        )

        self.client.force_login(self.staff_user_1)
        response = self.client.get(reverse("store:request_edit", kwargs={"request_id": request_obj.id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This request is fulfilled and is now read-only for staff.")
        self.assertNotContains(response, "Add Item")
    def test_16_management_can_use_request_workspace_for_own_requests_only(self):
        own_request = Request.objects.create(requester=self.management_staff, status=Request.Status.DRAFT, purpose="Mgt own")
        RequestItem.objects.create(request=own_request, item=self.item_1, requested_qty=2)

        other_request = Request.objects.create(requester=self.staff_1, status=Request.Status.DRAFT, purpose="Staff own")
        RequestItem.objects.create(request=other_request, item=self.item_1, requested_qty=1)

        self.client.force_login(self.management_user)
        response = self.client.get(reverse("store:request_list"))

        self.assertEqual(response.status_code, 200)

    def test_17_staff_group_cannot_access_storekeeper_inventory_view(self):
        self.client.force_login(self.staff_user_1)
        response = self.client.get(reverse("store:inventory_store_v2"))
        self.assertEqual(response.status_code, 403)

    def test_18_submit_button_reactivates_only_after_edit(self):
        self.client.force_login(self.staff_user_1)

        create_response = self.client.post(
            reverse("store:request_create"),
            {
                "purpose": "Need tools",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "2",
            },
        )
        self.assertEqual(create_response.status_code, 302)

        request_obj = Request.objects.get(requester=self.staff_1)

        first_submit = self.client.post(reverse("store:request_submit", kwargs={"request_id": request_obj.id}))
        self.assertEqual(first_submit.status_code, 302)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status, Request.Status.SUBMITTED)
        self.assertFalse(request_obj.needs_resubmission)

        after_submit_page = self.client.get(reverse("store:request_edit", kwargs={"request_id": request_obj.id}))
        self.assertEqual(after_submit_page.status_code, 200)
        self.assertFalse(after_submit_page.context["can_submit"])

        edit_response = self.client.post(
            reverse("store:request_edit", kwargs={"request_id": request_obj.id}),
            {
                "purpose": "Need tools (updated)",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "3",
            },
        )
        self.assertEqual(edit_response.status_code, 302)

        request_obj.refresh_from_db()
        self.assertTrue(request_obj.needs_resubmission)

        after_edit_page = self.client.get(reverse("store:request_edit", kwargs={"request_id": request_obj.id}))
        self.assertEqual(after_edit_page.status_code, 200)
        self.assertTrue(after_edit_page.context["can_submit"])

        second_submit = self.client.post(reverse("store:request_submit", kwargs={"request_id": request_obj.id}))
        self.assertEqual(second_submit.status_code, 302)
        request_obj.refresh_from_db()
        self.assertFalse(request_obj.needs_resubmission)

    def test_19_request_history_scoped_to_current_staff(self):
        own_request, own_item = self._create_submitted_request(self.staff_1, requested_qty=2)
        other_request, other_item = self._create_submitted_request(self.staff_2, requested_qty=2)

        fulfill_request_service(
            request_obj=own_request,
            issued_by=self.storekeeper_user,
            items_with_qty=[{"request_item_id": own_item.id, "fulfilled_qty": 2}],
            comment="Fulfilled own",
        )
        fulfill_request_service(
            request_obj=other_request,
            issued_by=self.storekeeper_user,
            items_with_qty=[{"request_item_id": other_item.id, "fulfilled_qty": 2}],
            comment="Fulfilled other",
        )

        self.client.force_login(self.staff_user_1)
        response = self.client.get(reverse("store:request_history"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("store:history_issuance_management"))
    def test_20_storekeeper_issuance_history_shows_requester_column(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=2)
        fulfill_request_service(
            request_obj=request_obj,
            issued_by=self.storekeeper_user,
            items_with_qty=[{"request_item_id": request_item.id, "fulfilled_qty": 2}],
            comment="Fulfilled",
        )

        self.client.force_login(self.storekeeper_user)
        response = self.client.get(reverse("store:history_issuance_storekeeper_v2"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Requester")
        self.assertContains(response, self.staff_1.name)
        self.assertContains(response, request_obj.purpose)


    def test_21_management_dashboard_activity_excludes_request_created(self):
        Activity.objects.create(
            actor=self.staff_user_1,
            verb=Activity.Verb.REQUEST_CREATED,
            target_type="Request",
            target_id=1,
            summary="Staff One created Request #1",
        )
        Activity.objects.create(
            actor=self.staff_user_1,
            verb=Activity.Verb.REQUEST_SUBMITTED,
            target_type="Request",
            target_id=1,
            summary="Staff One submitted Request #1",
        )
        Activity.objects.create(
            actor=self.storekeeper_user,
            verb=Activity.Verb.REQUEST_FULFILLED,
            target_type="Request",
            target_id=1,
            summary="Store Keeper fulfilled Request #1",
        )
        Activity.objects.create(
            actor=self.storekeeper_user,
            verb=Activity.Verb.REQUEST_UPDATED,
            target_type="Request",
            target_id=1,
            summary="Store Keeper updated Request #1",
        )

        self.client.force_login(self.management_user)
        response = self.client.get(reverse("store:dashboard_management_v2"))

        self.assertEqual(response.status_code, 200)
        verbs = [row["verb"] for row in response.context["recent_activity"]]
        self.assertNotIn(Activity.Verb.REQUEST_CREATED, verbs)
        self.assertIn(Activity.Verb.REQUEST_SUBMITTED, verbs)
        self.assertIn(Activity.Verb.REQUEST_FULFILLED, verbs)
        self.assertIn(Activity.Verb.REQUEST_UPDATED, verbs)

    def test_22_storekeeper_dashboard_shows_request_edit_activity(self):
        Activity.objects.create(
            actor=self.storekeeper_user,
            verb=Activity.Verb.REQUEST_UPDATED,
            target_type="Request",
            target_id=99,
            summary="Store Keeper updated Request #99",
        )
        Activity.objects.create(
            actor=self.staff_user_1,
            verb=Activity.Verb.REQUEST_CREATED,
            target_type="Request",
            target_id=100,
            summary="Staff One created Request #100",
        )

        self.client.force_login(self.storekeeper_user)
        response = self.client.get(reverse("store:dashboard_storekeeper_v2"))

        self.assertEqual(response.status_code, 200)
        verbs = [row["verb"] for row in response.context["recent_activity"]]
        self.assertIn(Activity.Verb.REQUEST_UPDATED, verbs)
        self.assertNotIn(Activity.Verb.REQUEST_CREATED, verbs)

    def test_23_storekeeper_request_list_shows_requester_and_submitted_time(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=2)
        request_obj.submitted_at = timezone.now()
        request_obj.save(update_fields=["submitted_at", "updated_at"])

        self.client.force_login(self.storekeeper_user)
        response = self.client.get(reverse("store:request_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Incoming Requests")
        self.assertContains(response, self.staff_1.name)
        self.assertContains(response, "Submitted")
        self.assertNotContains(response, "Edit Request")
        self.assertNotContains(response, "View Items")
        self.assertNotContains(response, "Submit Request")

    def test_24_storekeeper_cannot_increase_request_qty_before_fulfillment(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=4)

        self.client.force_login(self.storekeeper_user)
        response = self.client.post(
            reverse("store:request_edit", kwargs={"request_id": request_obj.id}),
            {
                "purpose": "Storekeeper attempted increase",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "5",
            },
        )

        self.assertEqual(response.status_code, 200)
        request_item.refresh_from_db()
        self.assertEqual(request_item.requested_qty, 4)

    def test_25_storekeeper_cannot_increase_fulfilled_qty_after_fulfillment(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=5)
        self._fulfill_via_view(request_obj, request_item, fulfilled_qty=2)

        self.client.force_login(self.storekeeper_user)
        response = self.client.post(
            reverse("store:request_edit_issuance", kwargs={"request_id": request_obj.id}),
            {
                "reason": "Attempted increase",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-request_item_id": str(request_item.id),
                "lines-0-fulfilled_qty": "3",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("store:request_edit", kwargs={"request_id": request_obj.id}))
        request_item.refresh_from_db()
        self.item_1.refresh_from_db()
        self.assertEqual(request_item.fulfilled_qty, 3)
        self.assertEqual(self.item_1.quantity, 27)

    def test_26_storekeeper_cannot_edit_request_purpose(self):
        request_obj, _ = self._create_submitted_request(self.staff_1, requested_qty=4)
        original_purpose = request_obj.purpose

        self.client.force_login(self.storekeeper_user)
        response = self.client.post(
            reverse("store:request_edit", kwargs={"request_id": request_obj.id}),
            {
                "purpose": "Storekeeper attempted purpose change",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "3",
            },
        )

        self.assertEqual(response.status_code, 302)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.purpose, original_purpose)

    def test_27_storekeeper_request_edit_page_shows_fulfill_action_only(self):
        request_obj, _ = self._create_submitted_request(self.staff_1, requested_qty=4)

        self.client.force_login(self.storekeeper_user)
        response = self.client.get(reverse("store:request_edit", kwargs={"request_id": request_obj.id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fulfill Request")
        self.assertNotContains(response, "Save Changes")
    def test_28_storekeeper_can_reincrease_up_to_original_requested_qty(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=10)

        self.client.force_login(self.storekeeper_user)

        reduce_response = self.client.post(
            reverse("store:request_edit", kwargs={"request_id": request_obj.id}),
            {
                "purpose": "Storekeeper reduce",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "8",
            },
        )
        self.assertEqual(reduce_response.status_code, 302)

        request_item = RequestItem.objects.get(request=request_obj, item=self.item_1)
        self.assertEqual(request_item.requested_qty, 8)
        self.assertEqual(request_item.original_requested_qty, 10)

        increase_within_cap_response = self.client.post(
            reverse("store:request_edit", kwargs={"request_id": request_obj.id}),
            {
                "purpose": "Storekeeper increase within cap",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "10",
            },
        )
        self.assertEqual(increase_within_cap_response.status_code, 302)

        request_item = RequestItem.objects.get(request=request_obj, item=self.item_1)
        self.assertEqual(request_item.requested_qty, 10)
        self.assertEqual(request_item.original_requested_qty, 10)

        above_cap_response = self.client.post(
            reverse("store:request_edit", kwargs={"request_id": request_obj.id}),
            {
                "purpose": "Storekeeper increase above cap",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "11",
            },
        )
        self.assertEqual(above_cap_response.status_code, 200)

        request_item = RequestItem.objects.get(request=request_obj, item=self.item_1)
        self.assertEqual(request_item.requested_qty, 10)

    def test_29_storekeeper_cap_recovers_from_history_when_stored_cap_is_stale(self):
        request_obj, request_item = self._create_submitted_request(self.staff_1, requested_qty=10)

        # Simulate a previously broken persisted cap after reduction.
        request_item.requested_qty = 8
        request_item.original_requested_qty = 8
        request_item.save(update_fields=["requested_qty", "original_requested_qty"])

        RequestActivity.objects.create(
            request=request_obj,
            actor=self.storekeeper_user,
            action=RequestActivity.Action.STORE_EDITED,
            description="Storekeeper edited request",
            metadata={
                "changes": [
                    {
                        "item_id": request_item.item_id,
                        "item_name": request_item.item.name,
                        "old_qty": 10,
                        "new_qty": 8,
                    }
                ]
            },
        )

        self.client.force_login(self.storekeeper_user)
        response = self.client.post(
            reverse("store:request_edit", kwargs={"request_id": request_obj.id}),
            {
                "purpose": "Raise back to original cap",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "10",
            },
        )

        self.assertEqual(response.status_code, 302)
        request_item = RequestItem.objects.get(request=request_obj, item=self.item_1)
        self.assertEqual(request_item.requested_qty, 10)
        self.assertEqual(request_item.original_requested_qty, 10)

    def test_30_storekeeper_request_edit_can_save_and_fulfill_in_one_post(self):
        request_obj, _ = self._create_submitted_request(self.staff_1, requested_qty=4)

        self.client.force_login(self.storekeeper_user)
        response = self.client.post(
            reverse("store:request_edit", kwargs={"request_id": request_obj.id}),
            {
                "action": "fulfill",
                "store_note": "Fulfilled from request edit page",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": str(self.item_1.id),
                "items-0-requested_qty": "3",
            },
        )

        self.assertEqual(response.status_code, 302)
        request_obj.refresh_from_db()
        request_item = RequestItem.objects.get(request=request_obj, item=self.item_1)
        self.item_1.refresh_from_db()

        self.assertEqual(request_obj.status, Request.Status.FULFILLED)
        self.assertEqual(request_obj.store_note, "Fulfilled from request edit page")
        self.assertEqual(request_item.requested_qty, 3)
        self.assertEqual(request_item.fulfilled_qty, 3)
        self.assertTrue(Issuance.objects.filter(request=request_obj).exists())
        self.assertEqual(self.item_1.quantity, 27)

