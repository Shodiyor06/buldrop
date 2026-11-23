"""Payme Merchant API (JSON-RPC 2.0) implementation.

Protocol reference: https://developer.help.paycom.uz (Merchant API).
Amounts are in tiyin (1 UZS = 100 tiyin). Every response is HTTP 200; failures are JSON-RPC errors.
"""
import base64
import hmac
import time
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from orders.models import Order
from orders.services import release_reserved_inventory

from .models import Payment
from .services import order_is_payable, settle_payment

TIMEOUT_MS = 12 * 60 * 60 * 1000  # a created transaction may stay pending for 12 hours

STATE_CREATED = 1
STATE_PERFORMED = 2
STATE_CANCELLED = -1
STATE_CANCELLED_AFTER_PERFORM = -2

REASON_TIMEOUT = 4

ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INSUFFICIENT_PRIVILEGE = -32504
ERR_SYSTEM = -32400
ERR_WRONG_AMOUNT = -31001
ERR_TRANSACTION_NOT_FOUND = -31003
ERR_CANNOT_CANCEL = -31007
ERR_CANNOT_PERFORM = -31008
ERR_ORDER_NOT_FOUND = -31050
ERR_ORDER_UNAVAILABLE = -31099

MESSAGES = {
    ERR_PARSE: {'ru': 'Ошибка разбора JSON', 'uz': 'JSON xato', 'en': 'Parse error'},
    ERR_INVALID_REQUEST: {'ru': 'Неверный запрос', 'uz': "Noto'g'ri so'rov", 'en': 'Invalid request'},
    ERR_METHOD_NOT_FOUND: {'ru': 'Метод не найден', 'uz': 'Metod topilmadi', 'en': 'Method not found'},
    ERR_INSUFFICIENT_PRIVILEGE: {'ru': 'Недостаточно привилегий', 'uz': 'Huquq yetarli emas', 'en': 'Insufficient privilege'},
    ERR_SYSTEM: {'ru': 'Системная ошибка', 'uz': 'Tizim xatosi', 'en': 'System error'},
    ERR_WRONG_AMOUNT: {'ru': 'Неверная сумма', 'uz': "Noto'g'ri summa", 'en': 'Wrong amount'},
    ERR_TRANSACTION_NOT_FOUND: {'ru': 'Транзакция не найдена', 'uz': 'Tranzaksiya topilmadi', 'en': 'Transaction not found'},
    ERR_CANNOT_CANCEL: {'ru': 'Невозможно отменить транзакцию', 'uz': "Tranzaksiyani bekor qilib bo'lmaydi", 'en': 'Transaction cannot be cancelled'},
    ERR_CANNOT_PERFORM: {'ru': 'Невозможно выполнить операцию', 'uz': "Operatsiyani bajarib bo'lmaydi", 'en': 'Cannot perform this operation'},
    ERR_ORDER_NOT_FOUND: {'ru': 'Заказ не найден', 'uz': 'Buyurtma topilmadi', 'en': 'Order not found'},
    ERR_ORDER_UNAVAILABLE: {'ru': 'Заказ недоступен для оплаты', 'uz': "Buyurtma to'lov uchun mavjud emas", 'en': 'Order is not available for payment'},
}


class PaymeError(Exception):
    """A JSON-RPC error. With commit=True the database changes made before raising are kept."""

    def __init__(self, code, data=None, commit=False):
        super().__init__(code)
        self.code = code
        self.data = data
        self.commit = commit


def now_ms():
    return int(time.time() * 1000)


def authorized(header):
    if not header or not header.startswith('Basic '):
        return False
    try:
        decoded = base64.b64decode(header[6:].strip()).decode()
    except Exception:  # noqa: BLE001 - any malformed header is simply unauthorized
        return False
    return hmac.compare_digest(decoded, f'Paycom:{settings.PAYME_SECRET_KEY}')


def error_body(rpc_id, code, data=None):
    error = {'code': code, 'message': MESSAGES.get(code, MESSAGES[ERR_SYSTEM])}
    if data is not None:
        error['data'] = data
    return {'jsonrpc': '2.0', 'id': rpc_id, 'error': error}


def to_tiyin(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


def handle(payload, auth_header):
    """Return the JSON-RPC response body for a decoded request payload."""
    rpc_id = payload.get('id') if isinstance(payload, dict) else None
    if not authorized(auth_header):
        return error_body(rpc_id, ERR_INSUFFICIENT_PRIVILEGE)
    if not isinstance(payload, dict) or 'method' not in payload:
        return error_body(rpc_id, ERR_INVALID_REQUEST)
    params = payload.get('params') or {}
    if not isinstance(params, dict):
        return error_body(rpc_id, ERR_INVALID_REQUEST)
    method = payload['method']
    handler = METHODS.get(method)
    if handler is None:
        return error_body(rpc_id, ERR_METHOD_NOT_FOUND, method)
    failure = None
    result = None
    try:
        with transaction.atomic():
            try:
                result = handler(params)
            except PaymeError as exc:
                if not exc.commit:
                    raise
                failure = exc
    except PaymeError as exc:
        failure = exc
    if failure is not None:
        return error_body(rpc_id, failure.code, failure.data)
    return {'jsonrpc': '2.0', 'id': rpc_id, 'result': result}


# -- helpers -----------------------------------------------------------------

def _get_order_for_check(params, *, lock=False):
    account = params.get('account') or {}
    order_id = str(account.get('order_id', ''))
    if not order_id.isdigit():
        raise PaymeError(ERR_ORDER_NOT_FOUND, 'order_id')
    queryset = Order.objects.select_for_update() if lock else Order.objects
    order = queryset.filter(pk=int(order_id)).first()
    if order is None:
        raise PaymeError(ERR_ORDER_NOT_FOUND, 'order_id')
    amount = params.get('amount')
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise PaymeError(ERR_WRONG_AMOUNT)
    if order.currency != settings.PROVIDER_CURRENCY or to_tiyin(order.total_amount) != amount:
        raise PaymeError(ERR_WRONG_AMOUNT)
    if not order_is_payable(order):
        raise PaymeError(ERR_ORDER_UNAVAILABLE, 'order_id')
    return order


def _get_payment(params, *, lock=True):
    transaction_id = params.get('id')
    if not transaction_id:
        raise PaymeError(ERR_TRANSACTION_NOT_FOUND)
    queryset = Payment.objects.select_for_update() if lock else Payment.objects
    payment = queryset.filter(method=Payment.METHOD_PAYME, provider_payment_id=str(transaction_id)).first()
    if payment is None:
        raise PaymeError(ERR_TRANSACTION_NOT_FOUND)
    return payment


def _expired(payment):
    return now_ms() - (payment.provider_time or payment.provider_create_time or 0) > TIMEOUT_MS


def _cancel_for_timeout(payment):
    payment.status = Payment.STATUS_CANCELLED
    payment.provider_state = STATE_CANCELLED
    payment.provider_reason = REASON_TIMEOUT
    payment.provider_cancel_time = now_ms()
    payment.save(update_fields=['status', 'provider_state', 'provider_reason', 'provider_cancel_time', 'updated_at'])


# -- JSON-RPC methods ----------------------------------------------------------

def check_perform_transaction(params):
    _get_order_for_check(params)
    return {'allow': True}


def create_transaction(params):
    transaction_id = params.get('id')
    request_time = params.get('time')
    if not transaction_id or not isinstance(request_time, int):
        raise PaymeError(ERR_INVALID_REQUEST)

    existing = Payment.objects.select_for_update().filter(
        method=Payment.METHOD_PAYME, provider_payment_id=str(transaction_id)
    ).first()
    if existing is not None:
        if existing.provider_state != STATE_CREATED:
            raise PaymeError(ERR_CANNOT_PERFORM)
        if _expired(existing):
            _cancel_for_timeout(existing)
            raise PaymeError(ERR_CANNOT_PERFORM, commit=True)
        return _create_result(existing)

    order = _get_order_for_check(params, lock=True)
    active = Payment.objects.select_for_update().filter(
        order_id=str(order.pk), method=Payment.METHOD_PAYME, provider_state=STATE_CREATED,
    ).first()
    if active is not None:
        if _expired(active):
            _cancel_for_timeout(active)
        else:
            raise PaymeError(ERR_ORDER_UNAVAILABLE, 'order_id')

    payment = Payment.objects.select_for_update().filter(
        order_id=str(order.pk), method=Payment.METHOD_PAYME, status=Payment.STATUS_PENDING, provider_payment_id='',
    ).first()
    if payment is None:
        payment = Payment(user=order.user, order_id=str(order.pk), method=Payment.METHOD_PAYME,
                          amount=order.total_amount, currency=order.currency)
    payment.provider_payment_id = str(transaction_id)
    payment.provider_state = STATE_CREATED
    payment.provider_time = request_time
    payment.provider_create_time = now_ms()
    payment.callback_payload = {'create': {'id': transaction_id, 'time': request_time, 'amount': params.get('amount')}}
    payment.save()
    return _create_result(payment)


def _create_result(payment):
    return {
        'create_time': payment.provider_create_time,
        'transaction': str(payment.pk),
        'state': payment.provider_state,
    }


def perform_transaction(params):
    payment = _get_payment(params)
    if payment.provider_state == STATE_PERFORMED:
        return _perform_result(payment)
    if payment.provider_state != STATE_CREATED:
        raise PaymeError(ERR_CANNOT_PERFORM)
    if _expired(payment):
        _cancel_for_timeout(payment)
        raise PaymeError(ERR_CANNOT_PERFORM, commit=True)

    order = Order.objects.select_for_update().filter(pk=int(payment.order_id)).first()
    if order is None or not order_is_payable(order):
        raise PaymeError(ERR_CANNOT_PERFORM)

    payment.provider_state = STATE_PERFORMED
    payment.provider_perform_time = now_ms()
    payment.save(update_fields=['provider_state', 'provider_perform_time', 'updated_at'])
    settle_payment(payment, order, actor='payme')
    return _perform_result(payment)


def _perform_result(payment):
    return {
        'transaction': str(payment.pk),
        'perform_time': payment.provider_perform_time,
        'state': payment.provider_state,
    }


def cancel_transaction(params):
    payment = _get_payment(params)
    reason = params.get('reason')

    if payment.provider_state in {STATE_CANCELLED, STATE_CANCELLED_AFTER_PERFORM}:
        return _cancel_result(payment)

    order = Order.objects.select_for_update().filter(pk=int(payment.order_id)).first()
    if payment.provider_state == STATE_CREATED:
        payment.provider_state = STATE_CANCELLED
    elif payment.provider_state == STATE_PERFORMED:
        # Refunds are only possible while nothing has been handed over to the customer.
        if order is None or order.status != Order.STATUS_PROCESSING or _has_released_goods(order):
            raise PaymeError(ERR_CANNOT_CANCEL)
        payment.provider_state = STATE_CANCELLED_AFTER_PERFORM
        order.status = Order.STATUS_REFUNDED
        order.notes = (order.notes + '\nrefunded via Payme').strip()
        order.save(update_fields=['status', 'notes', 'updated_at'])
        release_reserved_inventory(order)
    else:
        raise PaymeError(ERR_CANNOT_CANCEL)

    payment.status = Payment.STATUS_CANCELLED
    payment.provider_reason = reason if isinstance(reason, int) else None
    payment.provider_cancel_time = now_ms()
    payment.save(update_fields=['status', 'provider_state', 'provider_reason', 'provider_cancel_time', 'updated_at'])
    return _cancel_result(payment)


def _has_released_goods(order):
    delivery = getattr(order, 'delivery', None)
    return bool(delivery and delivery.details.get('codes_released'))


def _cancel_result(payment):
    return {
        'transaction': str(payment.pk),
        'cancel_time': payment.provider_cancel_time,
        'state': payment.provider_state,
    }


def check_transaction(params):
    payment = _get_payment(params, lock=False)
    return {
        'create_time': payment.provider_create_time,
        'perform_time': payment.provider_perform_time or 0,
        'cancel_time': payment.provider_cancel_time or 0,
        'transaction': str(payment.pk),
        'state': payment.provider_state,
        'reason': payment.provider_reason,
    }


def get_statement(params):
    start, end = params.get('from'), params.get('to')
    if not isinstance(start, int) or not isinstance(end, int):
        raise PaymeError(ERR_INVALID_REQUEST)
    payments = Payment.objects.filter(
        method=Payment.METHOD_PAYME, provider_time__gte=start, provider_time__lte=end,
    ).exclude(provider_payment_id='').order_by('provider_time')
    return {
        'transactions': [
            {
                'id': payment.provider_payment_id,
                'time': payment.provider_time,
                'amount': to_tiyin(payment.amount),
                'account': {'order_id': payment.order_id},
                'create_time': payment.provider_create_time,
                'perform_time': payment.provider_perform_time or 0,
                'cancel_time': payment.provider_cancel_time or 0,
                'transaction': str(payment.pk),
                'state': payment.provider_state,
                'reason': payment.provider_reason,
            }
            for payment in payments
        ]
    }


METHODS = {
    'CheckPerformTransaction': check_perform_transaction,
    'CreateTransaction': create_transaction,
    'PerformTransaction': perform_transaction,
    'CancelTransaction': cancel_transaction,
    'CheckTransaction': check_transaction,
    'GetStatement': get_statement,
}
