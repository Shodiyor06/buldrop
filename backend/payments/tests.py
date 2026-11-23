from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class PaymentTests(APITestCase):
    def test_payment_initialization_requires_auth(self):
        response = self.client.post(reverse('payment-initialize'), {'order_id': '1'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_payment_initialization_for_order(self):
        user = User.objects.create_user(username='owner', email='owner@example.com', password='Str0ngPass!')
        self.client.force_authenticate(user=user)
        response = self.client.post(reverse('payment-initialize'), {'order_id': '999'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(TEST_PAYMENT_ENABLED=False)
    def test_test_payment_is_disabled_outside_explicit_test_mode(self):
        user = User.objects.create_user(username='disabled', email='disabled@example.com', password='StrongPass!23')
        self.client.force_authenticate(user=user)
        response = self.client.post(reverse('payment-initialize'), {'order_id': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_payment_callbacks_do_not_confirm_without_provider_protocol(self):
        response = self.client.post(
            reverse('click-callback'),
            {'order_id': '1', 'status': 'success', 'signature': 'anything'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
