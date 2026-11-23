from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from catalog.models import Product, ProductVariant
from games.models import Game
from orders.models import Coupon, Order, SupportTicket
from orders.services import cancel_order

User = get_user_model()


class FeatureBase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', email='b@example.com', password='StrongPass!23')
        self.game = Game.objects.create(name='G', slug='g')
        self.product = Product.objects.create(game=self.game, name='Pack', slug='pack', price='0', currency='UZS',
                                              fulfillment_type=Product.FULFILLMENT_MANUAL)
        self.small = ProductVariant.objects.create(product=self.product, name='Small', sku='s', price='10000', currency='UZS')
        self.big = ProductVariant.objects.create(product=self.product, name='Big', sku='b', price='50000', currency='UZS',
                                                 track_stock=True, stock=2)
        self.client.force_authenticate(self.user)

    def order(self, items, **extra):
        return self.client.post(reverse('orders'), {'items': items, **extra}, format='json')


class VariantAndStockTests(FeatureBase):
    def test_variant_price_is_used(self):
        response = self.order([{'product_id': self.product.pk, 'variant_id': self.small.pk, 'quantity': 3}])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['total_amount'], '30000.00')

    def test_variant_required_when_product_price_is_zero(self):
        response = self.order([{'product_id': self.product.pk, 'quantity': 1}])
        self.assertEqual(response.status_code, 400)

    def test_stock_is_decremented_limited_and_restored(self):
        response = self.order([{'product_id': self.product.pk, 'variant_id': self.big.pk, 'quantity': 2}])
        self.assertEqual(response.status_code, 201)
        self.big.refresh_from_db()
        self.assertEqual(self.big.stock, 0)
        sold_out = self.order([{'product_id': self.product.pk, 'variant_id': self.big.pk, 'quantity': 1}])
        self.assertEqual(sold_out.status_code, 400)
        cancel_order(Order.objects.get(pk=response.data['id']))
        self.big.refresh_from_db()
        self.assertEqual(self.big.stock, 2)
        # Cancelling twice must not restore stock twice
        cancel_order(Order.objects.get(pk=response.data['id']))
        self.big.refresh_from_db()
        self.assertEqual(self.big.stock, 2)

    def test_product_list_exposes_variants_and_availability(self):
        body = self.client.get(reverse('products')).json()
        product = body['results'][0]
        self.assertEqual(len(product['variants']), 2)
        self.assertTrue(product['available'])

    def test_invalid_price_filter_returns_400_not_500(self):
        self.assertEqual(self.client.get(reverse('products'), {'min_price': 'abc'}).status_code, 400)
        self.assertEqual(self.client.get(reverse('products'), {'min_price': '9', 'max_price': '1'}).status_code, 400)


class CouponTests(FeatureBase):
    def test_percent_coupon_with_cap(self):
        Coupon.objects.create(code='SAVE20', percent_off=20, max_discount=Decimal('5000'))
        response = self.order([{'product_id': self.product.pk, 'variant_id': self.small.pk, 'quantity': 5}], coupon_code='save20')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['discount_amount'], '5000.00')
        self.assertEqual(response.data['total_amount'], '45000.00')
        self.assertEqual(Coupon.objects.get().used_count, 1)

    def test_coupon_limits_and_release_on_cancel(self):
        Coupon.objects.create(code='ONCE', percent_off=10, usage_limit=1)
        first = self.order([{'product_id': self.product.pk, 'variant_id': self.small.pk, 'quantity': 1}], coupon_code='ONCE')
        self.assertEqual(first.status_code, 201)
        second = self.order([{'product_id': self.product.pk, 'variant_id': self.small.pk, 'quantity': 2}], coupon_code='ONCE')
        self.assertEqual(second.status_code, 400)
        cancel_order(Order.objects.get(pk=first.data['id']))
        self.assertEqual(Coupon.objects.get().used_count, 0)

    def test_expired_and_unknown_coupons(self):
        Coupon.objects.create(code='OLD', percent_off=10, valid_until=timezone.now() - timedelta(days=1))
        for code in ('OLD', 'NOPE'):
            response = self.order([{'product_id': self.product.pk, 'variant_id': self.small.pk, 'quantity': 1}], coupon_code=code)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)


class AccountFeatureTests(FeatureBase):
    def test_game_accounts_crud_is_scoped_to_owner(self):
        created = self.client.post(reverse('game-accounts'), {'game_slug': 'g', 'player_id': ' 123 ', 'label': 'main'}, format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['player_id'], '123')
        listing = self.client.get(reverse('game-accounts')).json()
        self.assertEqual(len(listing), 1)
        other = User.objects.create_user(username='other', password='StrongPass!23')
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(reverse('game-accounts')).json(), [])
        self.assertEqual(self.client.delete(reverse('game-account-detail', args=[created.data['id']])).status_code, 404)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.delete(reverse('game-account-detail', args=[created.data['id']])).status_code, 204)

    def test_reviews_require_completed_purchase(self):
        url = reverse('product-reviews', args=['pack'])
        self.assertEqual(self.client.post(url, {'rating': 5, 'comment': 'great'}, format='json').status_code, 403)
        order_id = self.order([{'product_id': self.product.pk, 'variant_id': self.small.pk, 'quantity': 1}]).data['id']
        Order.objects.filter(pk=order_id).update(status=Order.STATUS_COMPLETED)
        self.assertEqual(self.client.post(url, {'rating': 9}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url, {'rating': 4, 'comment': 'ok'}, format='json').status_code, 201)
        self.assertEqual(self.client.post(url, {'rating': 5, 'comment': 'better'}, format='json').status_code, 200)
        anonymous = self.client.__class__()
        listing = anonymous.get(url).json()
        self.assertEqual(listing['count'], 1)
        self.assertEqual(listing['results'][0]['rating'], 5)
        product = anonymous.get(reverse('product-detail', args=['pack'])).json()
        self.assertEqual(product['review_count'], 1)
        self.assertEqual(product['rating_average'], 5.0)

    def test_registration_rejects_duplicate_email_and_similar_password(self):
        ok = self.client.post(reverse('register'), {'username': 'new', 'email': 'NEW@example.com', 'password': 'Str0ngPass!9'}, format='json')
        self.assertEqual(ok.status_code, 201)
        dup = self.client.post(reverse('register'), {'username': 'new2', 'email': 'new@example.com', 'password': 'Str0ngPass!9'}, format='json')
        self.assertEqual(dup.status_code, 400)
        similar = self.client.post(reverse('register'), {'username': 'johnsmith', 'email': 'j@example.com', 'password': 'johnsmith1'}, format='json')
        self.assertEqual(similar.status_code, 400)

    def test_staff_can_answer_tickets_customers_cannot(self):
        created = self.client.post(reverse('ticket-list'), {'title': 'Help', 'message': 'Where is my order?'}, format='json')
        self.assertEqual(created.status_code, 201)
        url = reverse('ticket-detail', args=[created.data['id']])
        self.assertEqual(self.client.patch(url, {'status': 'closed'}, format='json').status_code, 403)
        staff = User.objects.create_user(username='op', password='StrongPass!23', role=User.ROLE_SUPPORT)
        self.client.force_authenticate(staff)
        answered = self.client.patch(url, {'status': 'answered', 'admin_reply': 'Shipped.'}, format='json')
        self.assertEqual(answered.status_code, 200)
        self.assertEqual(SupportTicket.objects.get().admin_reply, 'Shipped.')
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(url).json()['admin_reply'], 'Shipped.')
