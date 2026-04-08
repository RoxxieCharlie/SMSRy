from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import NoReverseMatch, reverse


class ManualIssuanceDisabledTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="legacy-check", password="pass")
        self.client.force_login(self.user)

    def test_manual_issuance_named_route_is_removed(self):
        with self.assertRaises(NoReverseMatch):
            reverse("store:issuance_create_v2")

    def test_reversal_named_route_is_removed(self):
        with self.assertRaises(NoReverseMatch):
            reverse("store:issuance_reverse", kwargs={"issuance_id": 1})

    def test_manual_issuance_legacy_path_not_usable(self):
        response = self.client.get("/issuance/new/")
        self.assertEqual(response.status_code, 404)

    def test_reversal_legacy_path_not_usable(self):
        response = self.client.post("/issuance/1/reverse/")
        self.assertEqual(response.status_code, 404)
