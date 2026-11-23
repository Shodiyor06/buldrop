from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Product
from delivery.models import DeliveryAttempt
from delivery.tasks import process_delivery
from games.models import Game
from inventory.models import InventoryAsset
from orders.models import Order

User = get_user_model()


class OrderWorkflowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', password='StrongPass!23')
        self.game = Game.objects.create(name='Test game', slug='test-game')
        self.product = Product.objects.create(
            game=self.game,
            name='Test UC pack',
            slug='test-uc-pack',
            price='3.75',
            currency='USD',
            fulfillment_type=Product.FULFILLMENT_TOPUP,
        )
        self.client.force_authenticate(self.user)

    def create_order(self, *, key='order-1', payload=None):
        data = payload or {
            'items': [{
                'product_id': self.product.pk,
                'quantity': 2,
                'game_account': {'player_id': 'player-123'},
                'price': '0.01',
                'name': 'Client supplied name',
            }],
        }
        return self.client.post(
            reverse('orders'),
            data,
            format='json',
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_order_price_is_calculated_from_database(self):
        response = self.create_order()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['total_amount'], '7.50')
        self.assertEqual(response.data['items'][0]['name'], 'Test UC pack')
        self.assertEqual(response.data['items'][0]['price'], '3.75')

    def test_idempotency_reuses_order_and_rejects_changed_request(self):
        first = self.create_order(key='same-key')
        second = self.create_order(key='same-key')
        changed = self.create_order(
            key='same-key',
            payload={'items': [{'product_id': self.product.pk, 'quantity': 1, 'game_account': {'player_id': 'other'}}]},
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(changed.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 1)

    def test_inventory_is_reserved_on_order_and_released_on_test_failure(self):
        product = Product.objects.create(
            game=self.game,
            name='CS2 item',
            slug='cs2-item',
            price='5.00',
            fulfillment_type=Product.FULFILLMENT_INVENTORY,
        )
        asset = InventoryAsset.objects.create(product=product)
        order_response = self.create_order(
            key='inventory-key',
            payload={'items': [{'product_id': product.pk, 'quantity': 1}]},
        )
        self.assertEqual(order_response.status_code, status.HTTP_201_CREATED)
        asset.refresh_from_db()
        self.assertEqual(asset.status, InventoryAsset.STATUS_RESERVED)

        payment_response = self.client.post(
            reverse('payment-initialize'),
            {'order_id': order_response.data['id']},
            format='json',
        )
        finish_response = self.client.post(
            reverse('test-payment-finish', args=[payment_response.data['payment_id']]),
            {'outcome': 'failed'},
            format='json',
        )
        self.assertEqual(finish_response.status_code, status.HTTP_200_OK)
        asset.refresh_from_db()
        self.assertEqual(asset.status, InventoryAsset.STATUS_AVAILABLE)

    def test_test_payment_finishes_as_simulated_not_real_delivery(self):
        order_response = self.create_order()
        payment_response = self.client.post(
            reverse('payment-initialize'),
            {'order_id': order_response.data['id']},
            format='json',
        )
        with self.captureOnCommitCallbacks(execute=True):
            finish_response = self.client.post(
                reverse('test-payment-finish', args=[payment_response.data['payment_id']]),
                {'outcome': 'paid'},
                format='json',
            )
        self.assertEqual(finish_response.status_code, status.HTTP_200_OK)
        order = Order.objects.get(pk=order_response.data['id'])
        self.assertEqual(order.status, Order.STATUS_SIMULATED)
        self.assertEqual(order.delivery.status, 'simulated')
        self.assertIn('No top-up', order.delivery.details['message'])
        process_delivery(order.delivery.pk)
        self.assertEqual(DeliveryAttempt.objects.filter(delivery=order.delivery).count(), 1)

    def test_customer_cannot_view_another_users_order(self):
        order_response = self.create_order()
        other_user = User.objects.create_user(username='other', password='StrongPass!23')
        self.client.force_authenticate(other_user)
        response = self.client.get(reverse('order-detail', args=[order_response.data['id']]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
