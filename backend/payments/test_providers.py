import base64
import hashlib
import json

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from catalog.models import Product
from games.models import Game
from inventory.models import InventoryAsset
from orders.models import Order
from orders.services import create_order, expire_pending_orders
from payments import payme
from payments.models import Payment

User = get_user_model()

CLICK = dict(CLICK_SERVICE_ID='1001', CLICK_MERCHANT_ID='2002', CLICK_SECRET_KEY='click-secret', CLICK_ENABLED=True)
PAYME = dict(PAYME_MERCHANT_KEY='merchant-id', PAYME_SECRET_KEY='payme-secret', PAYME_ENABLED=True)


def md5(*parts):
    return hashlib.md5(''.join(str(p) for p in parts).encode()).hexdigest()


class ProviderBase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', email='b@example.com', password='StrongPass!23')
        self.game = Game.objects.create(name='G', slug='g')
        self.code_product = Product.objects.create(
            game=self.game, name='Gift code', slug='gift-code', price='50000', currency='UZS',
            fulfillment_type=Product.FULFILLMENT_INVENTORY,
        )
        self.topup_product = Product.objects.create(
            game=self.game, name='Top-up', slug='topup', price='10000', currency='UZS',
            fulfillment_type=Product.FULFILLMENT_TOPUP,
        )
        InventoryAsset.objects.create(product=self.code_product, external_id='c1', metadata={'code': 'SECRET-1'})

    def make_order(self, product=None, quantity=1, **extra):
        product = product or self.code_product
        item = {'product_id': product.pk, 'quantity': quantity}
        if product.fulfillment_type == Product.FULFILLMENT_TOPUP:
            item['game_account'] = {'player_id': '777'}
        order, _ = create_order(user=self.user, items=[item], **extra)
        return order


@override_settings(**CLICK)
class ClickTests(ProviderBase):
    url_name = 'click-callback'

    def payload(self, order, action, **kw):
        data = {
            'click_trans_id': '555', 'service_id': '1001', 'click_paydoc_id': '9', 'merchant_trans_id': str(order.pk),
            'amount': f'{order.total_amount:.2f}', 'action': str(action), 'error': '0', 'error_note': 'Success',
            'sign_time': '2026-10-21 12:00:00',
        }
        data.update(kw)
        if action == 1:
            data.setdefault('merchant_prepare_id', '')
            sign = md5(data['click_trans_id'], data['service_id'], 'click-secret', data['merchant_trans_id'],
                       data['merchant_prepare_id'], data['amount'], data['action'], data['sign_time'])
        else:
            sign = md5(data['click_trans_id'], data['service_id'], 'click-secret', data['merchant_trans_id'],
                       data['amount'], data['action'], data['sign_time'])
        data.setdefault('sign_string', sign)
        return data

    def post(self, data):
        return self.client.post(reverse(self.url_name), data).json()

    def test_bad_signature(self):
        order = self.make_order()
        body = self.post(self.payload(order, 0, sign_string='0' * 32))
        self.assertEqual(body['error'], -1)

    def test_wrong_amount(self):
        order = self.make_order()
        body = self.post(self.payload(order, 0, amount='1.00'))
        self.assertEqual(body['error'], -2)

    def test_unknown_order(self):
        order = self.make_order()
        body = self.post(self.payload(order, 0, merchant_trans_id='99999'))
        self.assertEqual(body['error'], -5)

    def test_full_flow_delivers_code(self):
        order = self.make_order()
        prepare = self.post(self.payload(order, 0))
        self.assertEqual(prepare['error'], 0)
        # Prepare is idempotent
        self.assertEqual(self.post(self.payload(order, 0))['merchant_prepare_id'], prepare['merchant_prepare_id'])
        with self.captureOnCommitCallbacks(execute=True):
            complete = self.post(self.payload(order, 1, merchant_prepare_id=str(prepare['merchant_prepare_id'])))
        self.assertEqual(complete['error'], 0)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_COMPLETED)
        self.assertEqual(Payment.objects.get(pk=prepare['merchant_prepare_id']).status, Payment.STATUS_PAID)

        self.client.force_authenticate(self.user)
        detail = self.client.get(reverse('order-detail', args=[order.pk])).json()
        self.assertEqual(detail['items'][0]['delivered_codes'][0]['code'], 'SECRET-1')
        # Replayed complete reports "already paid"
        again = self.post(self.payload(order, 1, merchant_prepare_id=str(prepare['merchant_prepare_id'])))
        self.assertEqual(again['error'], -4)

    def test_click_cancel_keeps_order_payable(self):
        order = self.make_order()
        prepare = self.post(self.payload(order, 0))
        body = self.post(self.payload(order, 1, merchant_prepare_id=str(prepare['merchant_prepare_id']), error='-5017'))
        self.assertEqual(body['error'], -9)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PENDING_PAYMENT)

    def test_topup_goes_to_operator_queue(self):
        order = self.make_order(self.topup_product)
        prepare = self.post(self.payload(order, 0))
        with self.captureOnCommitCallbacks(execute=True):
            self.post(self.payload(order, 1, merchant_prepare_id=str(prepare['merchant_prepare_id'])))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PROCESSING)
        self.assertEqual(order.delivery.details['mode'], 'manual_review')

    @override_settings(CLICK_ENABLED=False)
    def test_disabled_without_credentials(self):
        order = self.make_order()
        response = self.client.post(reverse(self.url_name), self.payload(order, 0))
        self.assertEqual(response.status_code, 503)

    def test_initialize_returns_checkout_url(self):
        order = self.make_order()
        self.client.force_authenticate(self.user)
        response = self.client.post(reverse('payment-initialize'), {'order_id': order.pk, 'method': 'click'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('service_id=1001', response.data['checkout_url'])
        self.assertIn(f'transaction_param={order.pk}', response.data['checkout_url'])

    def test_initialize_rejects_non_uzs_order(self):
        usd = Product.objects.create(game=self.game, name='USD', slug='usd', price='5', currency='USD',
                                     fulfillment_type=Product.FULFILLMENT_MANUAL)
        order, _ = create_order(user=self.user, items=[{'product_id': usd.pk, 'quantity': 1}])
        self.client.force_authenticate(self.user)
        response = self.client.post(reverse('payment-initialize'), {'order_id': order.pk, 'method': 'click'}, format='json')
        self.assertEqual(response.status_code, 400)


@override_settings(**PAYME)
class PaymeTests(ProviderBase):
    def rpc(self, method, params, auth=True, rpc_id=1):
        headers = {}
        if auth:
            token = base64.b64encode(b'Paycom:payme-secret').decode()
            headers['HTTP_AUTHORIZATION'] = f'Basic {token}'
        response = self.client.post(
            reverse('payme-callback'),
            data=json.dumps({'jsonrpc': '2.0', 'id': rpc_id, 'method': method, 'params': params}),
            content_type='application/json',
            **headers,
        )
        return response.json()

    def params(self, order, **extra):
        data = {'amount': int(order.total_amount * 100), 'account': {'order_id': str(order.pk)}}
        data.update(extra)
        return data

    def test_requires_basic_auth(self):
        order = self.make_order()
        body = self.rpc('CheckPerformTransaction', self.params(order), auth=False)
        self.assertEqual(body['error']['code'], -32504)

    def test_check_perform_errors(self):
        order = self.make_order()
        self.assertTrue(self.rpc('CheckPerformTransaction', self.params(order))['result']['allow'])
        self.assertEqual(self.rpc('CheckPerformTransaction', self.params(order, amount=100))['error']['code'], -31001)
        missing = self.params(order)
        missing['account'] = {'order_id': '424242'}
        self.assertEqual(self.rpc('CheckPerformTransaction', missing)['error']['code'], -31050)

    def test_unknown_method(self):
        self.assertEqual(self.rpc('Nope', {})['error']['code'], -32601)

    def test_full_flow(self):
        order = self.make_order()
        now = payme.now_ms()
        created = self.rpc('CreateTransaction', self.params(order, id='tx1', time=now))['result']
        self.assertEqual(created['state'], 1)
        # Same id again is idempotent; a second transaction for the same order is refused
        self.assertEqual(self.rpc('CreateTransaction', self.params(order, id='tx1', time=now))['result']['transaction'], created['transaction'])
        self.assertEqual(self.rpc('CreateTransaction', self.params(order, id='tx2', time=now))['error']['code'], -31099)

        with self.captureOnCommitCallbacks(execute=True):
            performed = self.rpc('PerformTransaction', {'id': 'tx1'})['result']
        self.assertEqual(performed['state'], 2)
        self.assertEqual(self.rpc('PerformTransaction', {'id': 'tx1'})['result']['perform_time'], performed['perform_time'])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_COMPLETED)

        checked = self.rpc('CheckTransaction', {'id': 'tx1'})['result']
        self.assertEqual(checked['state'], 2)
        statement = self.rpc('GetStatement', {'from': now - 1000, 'to': now + 1000})['result']['transactions']
        self.assertEqual([t['id'] for t in statement], ['tx1'])
        self.assertEqual(statement[0]['account'], {'order_id': str(order.pk)})

        # Goods were already handed over, so a refund is impossible
        self.assertEqual(self.rpc('CancelTransaction', {'id': 'tx1', 'reason': 5})['error']['code'], -31007)

    def test_cancel_before_perform(self):
        order = self.make_order()
        self.rpc('CreateTransaction', self.params(order, id='tx9', time=payme.now_ms()))
        cancelled = self.rpc('CancelTransaction', {'id': 'tx9', 'reason': 1})['result']
        self.assertEqual(cancelled['state'], -1)
        self.assertEqual(self.rpc('CancelTransaction', {'id': 'tx9', 'reason': 1})['result']['state'], -1)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PENDING_PAYMENT)

    def test_refund_after_perform_for_undelivered_order(self):
        order = self.make_order(self.topup_product)
        self.rpc('CreateTransaction', self.params(order, id='tx5', time=payme.now_ms()))
        with self.captureOnCommitCallbacks(execute=True):
            self.rpc('PerformTransaction', {'id': 'tx5'})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PROCESSING)
        result = self.rpc('CancelTransaction', {'id': 'tx5', 'reason': 5})['result']
        self.assertEqual(result['state'], -2)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_REFUNDED)

    def test_timeout_cancels_transaction(self):
        order = self.make_order()
        old = payme.now_ms() - payme.TIMEOUT_MS - 1000
        self.rpc('CreateTransaction', self.params(order, id='old', time=old))
        # created just now by us, so age it by rewinding the stored Payme time
        Payment.objects.filter(provider_payment_id='old').update(provider_time=old)
        self.assertEqual(self.rpc('PerformTransaction', {'id': 'old'})['error']['code'], -31008)
        payment = Payment.objects.get(provider_payment_id='old')
        self.assertEqual(payment.provider_state, -1)
        self.assertEqual(payment.provider_reason, 4)

    def test_invalid_json(self):
        response = self.client.post(reverse('payme-callback'), data='{oops', content_type='application/json')
        self.assertEqual(response.json()['error']['code'], -32700)

    @override_settings(PAYME_ENABLED=False)
    def test_disabled_without_credentials(self):
        response = self.client.post(reverse('payme-callback'), data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 503)

    def test_initialize_returns_checkout_url(self):
        order = self.make_order()
        self.client.force_authenticate(self.user)
        response = self.client.post(reverse('payment-initialize'), {'order_id': order.pk, 'method': 'payme'}, format='json')
        self.assertEqual(response.status_code, 201)
        prefix = 'https://checkout.paycom.uz/'
        self.assertTrue(response.data['checkout_url'].startswith(prefix))
        encoded = response.data['checkout_url'][len(prefix):]
        decoded = base64.b64decode(encoded).decode()
        self.assertIn('m=merchant-id', decoded)
        self.assertIn(f'ac.order_id={order.pk}', decoded)
        self.assertIn(f'a={int(order.total_amount * 100)}', decoded)


class OrderLifecycleTests(ProviderBase):
    def test_expiry_releases_inventory_and_stock(self):
        order = self.make_order()
        self.assertEqual(InventoryAsset.objects.get().status, InventoryAsset.STATUS_RESERVED)
        Order.objects.filter(pk=order.pk).update(created_at=order.created_at.replace(year=2020))
        self.assertEqual(expire_pending_orders(minutes=10), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CANCELLED)
        self.assertEqual(InventoryAsset.objects.get().status, InventoryAsset.STATUS_AVAILABLE)

    def test_customer_cancel_endpoint(self):
        order = self.make_order()
        self.client.force_authenticate(self.user)
        response = self.client.post(reverse('order-cancel', args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'cancelled')
        self.assertEqual(self.client.post(reverse('order-cancel', args=[order.pk])).status_code, 409)

    def test_test_mode_does_not_consume_or_reveal_inventory(self):
        order = self.make_order()
        self.client.force_authenticate(self.user)
        payment = self.client.post(reverse('payment-initialize'), {'order_id': order.pk}, format='json').data
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('test-payment-finish', args=[payment['payment_id']]), {'outcome': 'paid'}, format='json')
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_SIMULATED)
        self.assertEqual(InventoryAsset.objects.get().status, InventoryAsset.STATUS_AVAILABLE)
        detail = self.client.get(reverse('order-detail', args=[order.pk])).json()
        self.assertEqual(detail['items'][0]['delivered_codes'], [])

    def test_methods_endpoint(self):
        body = self.client.get(reverse('payment-methods')).json()
        self.assertEqual(set(body), {'test', 'click', 'payme', 'provider_currency'})
