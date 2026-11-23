from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Product, Supplier
from games.models import Category, Game


class CatalogTests(APITestCase):
    def setUp(self):
        category = Category.objects.create(name='FPS', slug='fps')
        game, _ = Game.objects.get_or_create(
            slug='cs2',
            defaults={'name': 'CS2', 'description': 'Counter-Strike', 'is_active': True, 'category': category},
        )
        supplier = Supplier.objects.create(name='Demo Supplier', slug='demo-supplier', code='demo', provider_type='mock', is_active=True)
        Product.objects.create(
            game=game,
            supplier=supplier,
            name='CS2 Starter Pack',
            slug='cs2-starter-pack',
            description='starter pack',
            price='12.50',
            currency='USD',
            is_active=True,
        )

    def test_catalog_list_endpoint(self):
        response = self.client.get(reverse('products'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['count'], 0)

    def test_game_account_validation_endpoint_requires_auth(self):
        response = self.client.post(reverse('validate-game-account'), {'player_id': '123', 'game_slug': 'cs2'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
