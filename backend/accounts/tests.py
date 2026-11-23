from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AuthTests(APITestCase):
    def test_user_registration(self):
        payload = {
            'username': 'newbuyer',
            'email': 'buyer@example.com',
            'password': 'Str0ngPass!',
            'first_name': 'Buyer',
            'last_name': 'Test',
            'phone': '+123456789',
        }
        response = self.client.post(reverse('register'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='newbuyer').exists())

    def test_login_and_me_endpoint(self):
        user = User.objects.create_user(username='demo', email='demo@example.com', password='Str0ngPass!')
        login = self.client.post(reverse('token-obtain-pair'), {'username': 'demo', 'password': 'Str0ngPass!'}, format='json')
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        access_token = login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get(reverse('me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'demo')
