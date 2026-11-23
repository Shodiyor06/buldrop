from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AdminStatsTests(APITestCase):
    def test_customer_cannot_access_admin_stats(self):
        user = User.objects.create_user(username='customer', password='StrongPass!23')
        self.client.force_authenticate(user=user)
        response = self.client.get(reverse('admin-stats'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_role_and_access(self):
        admin = User.objects.create_superuser(username='site-admin', password='StrongPass!23', email='admin@example.com')
        self.assertEqual(admin.role, User.ROLE_ADMIN)
        self.client.force_authenticate(user=admin)
        response = self.client.get(reverse('admin-stats'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('simulated_orders', response.data)
