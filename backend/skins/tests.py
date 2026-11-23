import hashlib
import hmac
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from catalog.models import Product
from delivery.models import Delivery
from delivery.tasks import process_delivery
from games.models import Game
from inventory.models import InventoryAsset
from orders.models import Order
from orders.services import create_order
from payments.models import Payment

from . import steam
from .models import SteamWithdrawal, UserSkin, Wallet
from .services import grant_skin

User = get_user_model()
TRADE_URL = 'https://steamcommunity.com/tradeoffer/new/?partner=123456&token=AbCd1234'


class SkinBase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'a@example.com', 'S3cure-pass-1')
        self.other = User.objects.create_user('bob', 'b@example.com', 'S3cure-pass-2')
        game = Game.objects.get_or_create(slug='cs2', defaults={'name': 'CS2'})[0]
        self.product = Product.objects.create(
            game=game, name='AK-47 | Redline', slug='ak-redline', price=Decimal('50000'), currency='UZS',
            fulfillment_type=Product.FULFILLMENT_INVENTORY, is_skin=True, coin_price=Decimal('120.50'),
        )
        self.asset = InventoryAsset.objects.create(
            product=self.product, external_id='9001', status=InventoryAsset.STATUS_SOLD,
            metadata={'appid': 730, 'contextid': '2'},
        )
        self.skin = grant_skin(user=self.user, asset=self.asset)
        self.client.force_authenticate(self.user)

    def save_trade_url(self):
        self.user.steam_trade_url = TRADE_URL
        self.user.save()


class SellTests(SkinBase):
    def test_sell_credits_fixed_price_and_restocks(self):
        response = self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data['balance']), Decimal('120.50'))
        self.skin.refresh_from_db()
        self.asset.refresh_from_db()
        self.assertEqual(self.skin.status, UserSkin.STATUS_SOLD)
        self.assertEqual(self.skin.sold_price, Decimal('120.50'))
        self.assertEqual(self.asset.status, InventoryAsset.STATUS_AVAILABLE)
        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.transactions.count(), 1)
        self.assertEqual(wallet.transactions.first().balance_after, Decimal('120.50'))

    def test_price_changes_do_not_affect_other_math_but_use_current_price(self):
        Product.objects.filter(pk=self.product.pk).update(coin_price=Decimal('200'))
        self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/')
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal('200.00'))

    def test_cannot_sell_twice(self):
        self.assertEqual(self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/').status_code, 409)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal('120.50'))

    def test_cannot_sell_someone_elses_skin(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/').status_code, 404)
        self.assertFalse(Wallet.objects.filter(user=self.other, balance__gt=0).exists())

    def test_no_coin_price_blocks_sale(self):
        Product.objects.filter(pk=self.product.pk).update(coin_price=None)
        self.assertEqual(self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/').status_code, 400)
        self.skin.refresh_from_db()
        self.assertEqual(self.skin.status, UserSkin.STATUS_IN_INVENTORY)

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/').status_code, 401)

    def test_sold_skin_can_be_bought_and_granted_again(self):
        self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/')
        self.asset.refresh_from_db()
        self.asset.status = InventoryAsset.STATUS_SOLD
        self.asset.save()
        grant_skin(user=self.other, asset=self.asset)
        self.assertEqual(UserSkin.objects.filter(asset=self.asset, status='in_inventory').count(), 1)

    def test_list_defaults_to_active(self):
        response = self.client.get('/api/v1/skins/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['sell_price'], '120.50')
        self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/')
        self.assertEqual(len(self.client.get('/api/v1/skins/').data['results']), 0)
        self.assertEqual(len(self.client.get('/api/v1/skins/?status=sold').data['results']), 1)


class SteamProfileTests(SkinBase):
    def test_save_and_derive_steam_id(self):
        response = self.client.patch('/api/v1/me/steam/', {'steam_trade_url': TRADE_URL}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['steam_id'], str(76561197960265728 + 123456))

    def test_rejects_bad_url(self):
        for bad in ['https://evil.com/tradeoffer/new/?partner=1&token=abcd', 'http://steamcommunity.com/x', 'abc']:
            r = self.client.patch('/api/v1/me/steam/', {'steam_trade_url': bad}, format='json')
            self.assertEqual(r.status_code, 400, bad)

    def test_clear(self):
        self.save_trade_url()
        r = self.client.patch('/api/v1/me/steam/', {'steam_trade_url': ''}, format='json')
        self.assertEqual(r.data['steam_trade_url'], '')


class WithdrawTests(SkinBase):
    def test_requires_trade_url(self):
        self.assertEqual(self.client.post(f'/api/v1/skins/{self.skin.pk}/withdraw/').status_code, 400)

    def test_manual_flow_accept(self):
        self.save_trade_url()
        r = self.client.post(f'/api/v1/skins/{self.skin.pk}/withdraw/')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['status'], 'pending')
        self.skin.refresh_from_db()
        self.assertEqual(self.skin.status, UserSkin.STATUS_WITHDRAWING)
        # a skin that is being withdrawn can be neither sold nor withdrawn again
        self.assertEqual(self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/').status_code, 409)
        self.assertEqual(self.client.post(f'/api/v1/skins/{self.skin.pk}/withdraw/').status_code, 409)
        from .services import apply_withdrawal_result
        apply_withdrawal_result(r.data['id'], 'sent')
        apply_withdrawal_result(r.data['id'], 'accepted')
        self.skin.refresh_from_db()
        self.assertEqual(self.skin.status, UserSkin.STATUS_WITHDRAWN)
        self.assertEqual(self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/').status_code, 409)

    def test_failed_returns_skin(self):
        self.save_trade_url()
        wid = self.client.post(f'/api/v1/skins/{self.skin.pk}/withdraw/').data['id']
        from .services import apply_withdrawal_result
        apply_withdrawal_result(wid, 'failed', error='nope')
        self.skin.refresh_from_db()
        self.assertEqual(self.skin.status, UserSkin.STATUS_IN_INVENTORY)
        # finished withdrawals never change again (idempotent)
        apply_withdrawal_result(wid, 'accepted')
        self.skin.refresh_from_db()
        self.assertEqual(self.skin.status, UserSkin.STATUS_IN_INVENTORY)
        self.assertEqual(self.client.post(f'/api/v1/skins/{self.skin.pk}/sell/').status_code, 200)

    def test_cancel_only_while_pending(self):
        self.save_trade_url()
        wid = self.client.post(f'/api/v1/skins/{self.skin.pk}/withdraw/').data['id']
        r = self.client.post(f'/api/v1/skins/withdrawals/{wid}/cancel/')
        self.assertEqual(r.status_code, 200)
        self.skin.refresh_from_db()
        self.assertEqual(self.skin.status, UserSkin.STATUS_IN_INVENTORY)
        wid2 = self.client.post(f'/api/v1/skins/{self.skin.pk}/withdraw/').data['id']
        from .services import apply_withdrawal_result
        apply_withdrawal_result(wid2, 'sent')
        self.assertEqual(self.client.post(f'/api/v1/skins/withdrawals/{wid2}/cancel/').status_code, 409)

    def test_cannot_cancel_other_users_withdrawal(self):
        self.save_trade_url()
        wid = self.client.post(f'/api/v1/skins/{self.skin.pk}/withdraw/').data['id']
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(f'/api/v1/skins/withdrawals/{wid}/cancel/').status_code, 404)

    @override_settings(STEAM_TRADE_MODE='bot', STEAM_BOT_URL='http://bot', STEAM_BOT_API_KEY='k')
    def test_bot_mode_sends_offer(self):
        self.save_trade_url()
        fake = mock.Mock(status_code=200)
        fake.json.return_value = {'offer_id': '555'}
        with mock.patch('skins.steam.requests.post', return_value=fake) as post, self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(f'/api/v1/skins/{self.skin.pk}/withdraw/')
        self.assertEqual(r.data['status'], 'pending')  # the response is sent before the task runs
        w = SteamWithdrawal.objects.get()
        self.assertEqual((w.status, w.trade_offer_id), ('sent', '555'))
        body = post.call_args.kwargs['json']
        self.assertEqual(body['items'], [{'appid': 730, 'contextid': '2', 'assetid': '9001'}])
        self.assertEqual(post.call_args.kwargs['headers'], {'X-Api-Key': 'k'})

    @override_settings(STEAM_TRADE_MODE='bot', STEAM_BOT_URL='http://bot', STEAM_BOT_API_KEY='k')
    def test_bot_rejection_returns_skin(self):
        self.save_trade_url()
        fake = mock.Mock(status_code=400)
        fake.json.return_value = {'error': 'trade url invalid'}
        with mock.patch('skins.steam.requests.post', return_value=fake), self.captureOnCommitCallbacks(execute=True):
            self.client.post(f'/api/v1/skins/{self.skin.pk}/withdraw/')
        self.skin.refresh_from_db()
        w = SteamWithdrawal.objects.get()
        self.assertEqual((w.status, w.error), ('failed', 'trade url invalid'))
        self.assertEqual(self.skin.status, UserSkin.STATUS_IN_INVENTORY)

    @override_settings(STEAM_TRADE_MODE='bot')
    def test_bot_mode_needs_steam_asset_id(self):
        self.save_trade_url()
        InventoryAsset.objects.filter(pk=self.asset.pk).update(external_id='')
        self.assertEqual(self.client.post(f'/api/v1/skins/{self.skin.pk}/withdraw/').status_code, 400)


@override_settings(STEAM_BOT_WEBHOOK_SECRET='shh')
class WebhookTests(SkinBase):
    def post(self, payload, secret='shh'):
        body = json.dumps(payload).encode()
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        self.client.force_authenticate(None)
        return self.client.post('/api/v1/steam/webhook/', data=body, content_type='application/json', HTTP_X_SIGNATURE=sig)

    def setUp(self):
        super().setUp()
        self.save_trade_url()
        self.wid = self.client.post(f'/api/v1/skins/{self.skin.pk}/withdraw/').data['id']

    def test_accept_via_webhook(self):
        self.assertEqual(self.post({'withdrawal_id': self.wid, 'status': 'sent', 'offer_id': '7'}).status_code, 200)
        self.assertEqual(self.post({'withdrawal_id': self.wid, 'status': 'accepted'}).data['status'], 'accepted')
        self.skin.refresh_from_db()
        self.assertEqual(self.skin.status, UserSkin.STATUS_WITHDRAWN)

    def test_declined_via_webhook(self):
        self.post({'withdrawal_id': self.wid, 'status': 'declined'})
        self.skin.refresh_from_db()
        self.assertEqual(self.skin.status, UserSkin.STATUS_IN_INVENTORY)

    def test_bad_signature(self):
        self.assertEqual(self.post({'withdrawal_id': self.wid, 'status': 'accepted'}, secret='wrong').status_code, 401)
        self.skin.refresh_from_db()
        self.assertEqual(self.skin.status, UserSkin.STATUS_WITHDRAWING)

    def test_bad_payload_and_unknown_id(self):
        self.assertEqual(self.post({'withdrawal_id': self.wid, 'status': 'weird'}).status_code, 400)
        self.assertEqual(self.post({'withdrawal_id': 99999, 'status': 'accepted'}).status_code, 404)

    @override_settings(STEAM_BOT_WEBHOOK_SECRET='')
    def test_disabled_without_secret(self):
        self.assertEqual(self.post({'withdrawal_id': self.wid, 'status': 'accepted'}).status_code, 503)


class PurchaseGrantsSkinTests(SkinBase):
    def _buy(self, method):
        asset = InventoryAsset.objects.create(product=self.product, external_id='9002', metadata={'appid': 730})
        order, _ = create_order(user=self.other, items=[{'product_id': self.product.pk, 'quantity': 1}])
        Payment.objects.create(user=self.other, order_id=str(order.pk), method=method, status=Payment.STATUS_PAID,
                               amount=order.total_amount, currency=order.currency)
        order.status = Order.STATUS_PROCESSING
        order.save()
        delivery = Delivery.objects.create(order=order)
        process_delivery(delivery.pk)
        return order, asset

    def test_real_payment_puts_skin_in_inventory(self):
        order, asset = self._buy(Payment.METHOD_CLICK)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_COMPLETED)
        skin = UserSkin.objects.get(user=self.other, asset=asset)
        self.assertEqual(skin.status, UserSkin.STATUS_IN_INVENTORY)
        # the secret asset data is not leaked as a code on the order
        self.client.force_authenticate(self.other)
        items = self.client.get(f'/api/v1/orders/{order.pk}/').data['items']
        self.assertEqual(items[0]['delivered_codes'], [])

    def test_test_payment_grants_nothing(self):
        order, asset = self._buy(Payment.METHOD_TEST)
        self.assertFalse(UserSkin.objects.filter(user=self.other).exists())
        asset.refresh_from_db()
        self.assertEqual(asset.status, InventoryAsset.STATUS_AVAILABLE)


class TradeUrlParsingTests(SkinBase):
    def test_parse(self):
        self.assertEqual(steam.parse_trade_url(TRADE_URL)[:2], (123456, 'AbCd1234'))
        with self.assertRaises(ValueError):
            steam.parse_trade_url('https://steamcommunity.com/tradeoffer/new/?partner=0&token=abcd')
