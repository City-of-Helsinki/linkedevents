import freezegun
from django.contrib import admin
from django.test import TestCase
from django.utils import timezone, translation
from knox import crypto
from knox.settings import CONSTANTS, knox_settings
from rest_framework import status

from data_analytics.models import DataAnalyticsApiToken
from data_analytics.tests.factories import DataAnalyticsApiTokenFactory
from helevents.tests.factories import UserFactory


class TestLocalAuthTokenAdmin(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = UserFactory(username="testadmin", is_staff=True, is_superuser=True)
        cls.site = admin.AdminSite()
        cls.base_url = "/admin/data_analytics/dataanalyticsapitoken/"
        cls.add_url = f"{cls.base_url}add/"

        cls.plaintext_auth_token = crypto.create_token_string()
        cls.auth_token = DataAnalyticsApiTokenFactory(
            digest=crypto.hash_token(cls.plaintext_auth_token),
            token_key=cls.plaintext_auth_token[: CONSTANTS.TOKEN_KEY_LENGTH],
        )
        cls.auth_token_edit_url = f"{cls.base_url}{cls.auth_token.digest}/change/"

        token2 = crypto.create_token_string()
        cls.auth_token2 = DataAnalyticsApiTokenFactory(
            digest=crypto.hash_token(token2),
            token_key=token2[: CONSTANTS.TOKEN_KEY_LENGTH],
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_local_auth_token_admin_is_registered(self):
        self.assertTrue(admin.site.is_registered(DataAnalyticsApiToken))

    def test_get_auth_token_add_page(self):
        response = self.client.get(self.add_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(
            response,
            "NOTE: Copy this to a secure location and use it as "
            "the API key in the data analytics system.",
        )

    def test_get_auth_token_edit_page(self):
        response = self.client.get(self.auth_token_edit_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, self.auth_token.name)
        self.assertNotContains(response, self.auth_token2.name)
        self.assertNotContains(
            response,
            "NOTE: Copy this to a secure location and use it as "
            "the API key in the data analytics system.",
        )

    def test_get_auth_token_list_page(self):
        response = self.client.get(self.base_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, self.auth_token.name)
        self.assertContains(response, self.auth_token2.name)

    @freezegun.freeze_time("2024-05-17 13:00:00+03:00")
    def test_add_auth_token(self):
        new_plaintext_token = crypto.create_token_string()
        new_digest = crypto.hash_token(new_plaintext_token)
        data = {
            "name": "New Unique Name",
            "digest": new_plaintext_token,
        }

        self.assertEqual(
            DataAnalyticsApiToken.objects.filter(digest=new_digest).count(), 0
        )

        self.assertEqual(DataAnalyticsApiToken.objects.count(), 2)
        self.client.post(self.add_url, data)
        self.assertEqual(DataAnalyticsApiToken.objects.count(), 3)

        new_token = DataAnalyticsApiToken.objects.get(digest=new_digest)
        self.assertEqual(new_token.name, data["name"])
        self.assertEqual(
            new_token.token_key, new_plaintext_token[: CONSTANTS.TOKEN_KEY_LENGTH]
        )
        self.assertEqual(new_token.expiry, timezone.now() + knox_settings.TOKEN_TTL)

    def test_edit_auth_token(self):
        old_expiry = self.auth_token.expiry
        data = {
            "name": "New Unique Name",
        }

        self.assertNotEqual(self.auth_token.name, data["name"])

        self.assertEqual(DataAnalyticsApiToken.objects.count(), 2)
        self.client.post(self.auth_token_edit_url, data)
        self.assertEqual(DataAnalyticsApiToken.objects.count(), 2)

        self.auth_token.refresh_from_db()
        self.assertEqual(self.auth_token.name, data["name"])
        self.assertEqual(
            self.auth_token.token_key,
            self.plaintext_auth_token[: CONSTANTS.TOKEN_KEY_LENGTH],
        )
        self.assertEqual(self.auth_token.expiry, old_expiry)

    def test_cannot_add_auth_token_with_same_name(self):
        data = {
            "name": self.auth_token.name,
            "digest": crypto.create_token_string(),
        }

        self.assertEqual(DataAnalyticsApiToken.objects.count(), 2)

        with translation.override("en"):
            response = self.client.post(self.add_url, data)
        self.assertContains(
            response, "Data analytics api token with this Name already exists."
        )

        self.assertEqual(DataAnalyticsApiToken.objects.count(), 2)
