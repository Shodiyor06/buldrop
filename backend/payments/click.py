"""Click SHOP API (Prepare / Complete) implementation.

Protocol reference: https://docs.click.uz (merchant API, "Shop-API").
Amounts are in UZS. Responses always use HTTP 200 with an `error` code in the body.
"""
import hashlib
import hmac
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction

from orders.models import Order

from .models import Payment
from .services import SETTLED_ORDER_STATUSES, order_is_payable, settle_payment

ACTION_PREPARE = 0
ACTION_COMPLETE = 1

SUCCESS = 0
SIGN_CHECK_FAILED = -1
INCORRECT_AMOUNT = -2
ACTION_NOT_FOUND = -3
ALREADY_PAID = -4
ORDER_NOT_FOUND = -5
TRANSACTION_NOT_FOUND = -6
UPDATE_FAILED = -7
REQUEST_ERROR = -8
TRANSACTION_CANCELLED = -9

ERROR_NOTES = {
    SUCCESS: 'Success',
    SIGN_CHECK_FAILED: 'SIGN CHECK FAILED!',
    INCORRECT_AMOUNT: 'Incorrect parameter amount',
    ACTION_NOT_FOUND: 'Action not found',
    ALREADY_PAID: 'Already paid',
    ORDER_NOT_FOUND: 'Order not found',
    TRANSACTION_NOT_FOUND: 'Transaction does not exist',
    UPDATE_FAILED: 'Failed to update user',
    REQUEST_ERROR: 'Error in request from click',
    TRANSACTION_CANCELLED: 'Transaction cancelled',
}

BASE_FIELDS = ['click_trans_id', 'service_id', 'click_paydoc_id', 'merchant_trans_id', 'amount', 'action', 'error', 'sign_time', 'sign_string']


def _md5(*parts):
    return hashlib.md5(''.join(str(part) for part in parts).encode()).hexdigest()


def verify_signature(data):
    action = str(data.get('action'))
    if action == str(ACTION_COMPLETE):
        expected = _md5(
            data['click_trans_id'], data['service_id'], settings.CLICK_SECRET_KEY, data['merchant_trans_id'],
            data.get('merchant_prepare_id', ''), data['amount'], data['action'], data['sign_time'],
        )
    else:
        expected = _md5(
            data['click_trans_id'], data['service_id'], settings.CLICK_SECRET_KEY, data['merchant_trans_id'],
            data['amount'], data['action'], data['sign_time'],
        )
    return hmac.compare_digest(expected, str(data['sign_string']))


def _respond(data, code, **extra):
    body = {
        'click_trans_id': data.get('click_trans_id'),
        'merchant_trans_id': data.get('merchant_trans_id'),
        'error': code,
        'error_note': ERROR_NOTES.get(code, 'Error'),
    }
    body.update(extra)
    return body


def _parse_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return amount if amount.is_finite() else None


def handle(data):
    """Process a Click callback payload (dict-like) and return the JSON response body."""
    data = {key: (value[0] if isinstance(value, list) else value) for key, value in dict(data).items()}
    required = BASE_FIELDS + (['merchant_prepare_id'] if str(data.get('action')) == str(ACTION_COMPLETE) else [])
    if any(data.get(field) in (None, '') for field in required if field != 'error'):
        return _respond(data, REQUEST_ERROR)
    if 'error' not in data:
        return _respond(data, REQUEST_ERROR)
    if not verify_signature(data):
        return _respond(data, SIGN_CHECK_FAILED)
    if str(data['service_id']) != str(settings.CLICK_SERVICE_ID):
        return _respond(data, REQUEST_ERROR)

    action = str(data['action'])
    if action == str(ACTION_PREPARE):
        return _prepare(data)
    if action == str(ACTION_COMPLETE):
        return _complete(data)
    return _respond(data, ACTION_NOT_FOUND)


def _find_order(data):
    merchant_trans_id = str(data['merchant_trans_id'])
    if not merchant_trans_id.isdigit():
        return None
    return Order.objects.select_for_update().filter(pk=int(merchant_trans_id)).first()


@transaction.atomic
def _prepare(data):
    order = _find_order(data)
    if order is None:
        return _respond(data, ORDER_NOT_FOUND)
    amount = _parse_amount(data['amount'])
    if amount is None or amount != order.total_amount or order.currency != settings.PROVIDER_CURRENCY:
        return _respond(data, INCORRECT_AMOUNT)

    existing = Payment.objects.select_for_update().filter(
        method=Payment.METHOD_CLICK, provider_payment_id=str(data['click_trans_id'])
    ).first()
    if existing:
        if existing.status == Payment.STATUS_PAID:
            return _respond(data, ALREADY_PAID)
        if existing.status in {Payment.STATUS_CANCELLED, Payment.STATUS_FAILED}:
            return _respond(data, TRANSACTION_CANCELLED)
        return _respond(data, SUCCESS, merchant_prepare_id=existing.pk)

    if order.status in SETTLED_ORDER_STATUSES:
        return _respond(data, ALREADY_PAID)
    if not order_is_payable(order):
        return _respond(data, TRANSACTION_CANCELLED)

    payment = Payment.objects.select_for_update().filter(
        order_id=str(order.pk), method=Payment.METHOD_CLICK, status=Payment.STATUS_PENDING, provider_payment_id='',
    ).first()
    if payment is None:
        payment = Payment(user=order.user, order_id=str(order.pk), method=Payment.METHOD_CLICK,
                          amount=order.total_amount, currency=order.currency)
    payment.provider_payment_id = str(data['click_trans_id'])
    payment.provider_state = 0
    payment.callback_payload = {'prepare': {k: v for k, v in data.items() if k != 'sign_string'}}
    payment.save()
    return _respond(data, SUCCESS, merchant_prepare_id=payment.pk)


@transaction.atomic
def _complete(data):
    prepare_id = str(data['merchant_prepare_id'])
    payment = None
    if prepare_id.isdigit():
        payment = Payment.objects.select_for_update().filter(
            pk=int(prepare_id), method=Payment.METHOD_CLICK, provider_payment_id=str(data['click_trans_id']),
        ).first()
    if payment is None:
        return _respond(data, TRANSACTION_NOT_FOUND)
    if str(payment.order_id) != str(data['merchant_trans_id']):
        return _respond(data, TRANSACTION_NOT_FOUND)
    amount = _parse_amount(data['amount'])
    if amount is None or amount != payment.amount:
        return _respond(data, INCORRECT_AMOUNT)
    if payment.status == Payment.STATUS_PAID:
        return _respond(data, ALREADY_PAID, merchant_confirm_id=payment.pk)
    if payment.status in {Payment.STATUS_CANCELLED, Payment.STATUS_FAILED}:
        return _respond(data, TRANSACTION_CANCELLED, merchant_confirm_id=payment.pk)

    payload = dict(payment.callback_payload or {})
    payload['complete'] = {k: v for k, v in data.items() if k != 'sign_string'}
    payment.callback_payload = payload

    try:
        click_error = int(data['error'])
    except (TypeError, ValueError):
        return _respond(data, REQUEST_ERROR)
    if click_error < 0:
        payment.status = Payment.STATUS_CANCELLED
        payment.provider_state = -1
        payment.save(update_fields=['status', 'provider_state', 'callback_payload', 'updated_at'])
        return _respond(data, TRANSACTION_CANCELLED, merchant_confirm_id=payment.pk)

    order = Order.objects.select_for_update().filter(pk=int(payment.order_id)).first()
    if order is None:
        return _respond(data, ORDER_NOT_FOUND)
    if not order_is_payable(order):
        # The order was cancelled/expired before Click confirmed it: refuse so Click refunds the user.
        payment.status = Payment.STATUS_CANCELLED
        payment.provider_state = -1
        payment.save(update_fields=['status', 'provider_state', 'callback_payload', 'updated_at'])
        return _respond(data, TRANSACTION_CANCELLED, merchant_confirm_id=payment.pk)

    payment.provider_state = 2
    payment.save(update_fields=['provider_state', 'callback_payload', 'updated_at'])
    settle_payment(payment, order, actor='click')
    return _respond(data, SUCCESS, merchant_confirm_id=payment.pk)
