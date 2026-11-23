import hashlib
import json
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import get_random_string
from rest_framework.exceptions import ValidationError

from audit.models import AuditLog
from catalog.models import Product, ProductVariant
from inventory.models import InventoryAsset

from .models import Coupon, Order, OrderItem

TWO_PLACES = Decimal('0.01')


def _fingerprint(items, coupon_code=''):
    canonical = json.dumps({'items': items, 'coupon': coupon_code}, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def create_order(*, user, items, idempotency_key=None, coupon_code=''):
    coupon_code = (coupon_code or '').strip().upper()
    fingerprint = _fingerprint(items, coupon_code)
    try:
        return _create_order(
            user=user,
            items=items,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            coupon_code=coupon_code,
        )
    except IntegrityError:
        if not idempotency_key:
            raise
        existing = Order.objects.filter(user=user, idempotency_key=idempotency_key).first()
        if existing is None:
            raise
        if existing.request_fingerprint != fingerprint:
            raise ValidationError({'idempotency_key': 'This key was already used for a different order.'})
        return existing, False


def _apply_coupon(code, total):
    """Return (coupon, discount). Raises ValidationError when the coupon cannot be used."""
    try:
        coupon = Coupon.objects.select_for_update().get(code__iexact=code, is_active=True)
    except Coupon.DoesNotExist as exc:
        raise ValidationError({'coupon_code': 'Coupon is invalid or inactive.'}) from exc
    if coupon.valid_until and coupon.valid_until < timezone.now():
        raise ValidationError({'coupon_code': 'Coupon has expired.'})
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise ValidationError({'coupon_code': 'Coupon usage limit has been reached.'})
    discount = (total * Decimal(coupon.percent_off) / Decimal(100)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if coupon.max_discount and coupon.max_discount > 0:
        discount = min(discount, coupon.max_discount)
    discount = min(discount, total)
    return coupon, discount


@transaction.atomic
def _create_order(*, user, items, idempotency_key, fingerprint, coupon_code):
    if idempotency_key:
        existing = Order.objects.filter(user=user, idempotency_key=idempotency_key).first()
        if existing:
            if existing.request_fingerprint != fingerprint:
                raise ValidationError({'idempotency_key': 'This key was already used for a different order.'})
            return existing, False

    order = Order.objects.create(
        user=user,
        order_number=f'BD-{get_random_string(12).upper()}',
        idempotency_key=idempotency_key or None,
        request_fingerprint=fingerprint,
    )
    total = Decimal('0.00')
    currency = None

    for requested_item in items:
        try:
            product = Product.objects.select_for_update().select_related('game', 'supplier').get(
                pk=requested_item['product_id'],
                is_active=True,
                game__is_active=True,
            )
        except Product.DoesNotExist as exc:
            raise ValidationError({'items': f"Product {requested_item['product_id']} is unavailable."}) from exc
        if product.supplier_id and not product.supplier.is_active:
            raise ValidationError({'items': f'{product.name} is currently unavailable.'})

        variant = None
        if requested_item.get('variant_id') is not None:
            try:
                variant = ProductVariant.objects.select_for_update().get(
                    pk=requested_item['variant_id'],
                    product=product,
                    is_active=True,
                )
            except ProductVariant.DoesNotExist as exc:
                raise ValidationError({'items': 'The selected product variant is unavailable.'}) from exc
        elif product.variants.filter(is_active=True).exists() and product.price <= 0:
            raise ValidationError({'items': f'Please choose a variant of {product.name}.'})

        price = variant.price if variant else product.price
        item_currency = variant.currency if variant else product.currency
        quantity = requested_item['quantity']
        if price <= 0:
            raise ValidationError({'items': f'{product.name} does not have a valid price.'})
        if currency is not None and currency != item_currency:
            raise ValidationError({'items': 'All products in an order must use the same currency.'})
        currency = item_currency

        account_data = requested_item.get('game_account', {})
        if product.fulfillment_type == Product.FULFILLMENT_TOPUP and not account_data.get('player_id'):
            raise ValidationError({'items': f'A player_id is required for {product.name}.'})

        item_snapshot = {
            'product_slug': product.slug,
            'game_slug': product.game.slug,
            'fulfillment_type': product.fulfillment_type,
        }
        if variant:
            item_snapshot['variant_sku'] = variant.sku
            item_snapshot['variant_name'] = variant.name
        if account_data:
            item_snapshot['game_account'] = {
                'player_id': str(account_data['player_id']),
                'server_id': str(account_data.get('server_id', '')),
            }

        if variant and variant.track_stock:
            if variant.stock < quantity:
                raise ValidationError({'items': f'Not enough stock for {product.name} - {variant.name}.'})
            ProductVariant.objects.filter(pk=variant.pk).update(stock=F('stock') - quantity)
            item_snapshot['stock_reserved'] = quantity

        order_item = OrderItem.objects.create(
            order=order,
            product=product,
            variant=variant,
            name=f'{product.name} - {variant.name}' if variant else product.name,
            price=price,
            quantity=quantity,
            currency=item_currency,
            provider_id=product.supplier.code if product.supplier_id else '',
            item_snapshot=item_snapshot,
        )

        if product.fulfillment_type == Product.FULFILLMENT_INVENTORY:
            assets = list(
                InventoryAsset.objects.select_for_update()
                .filter(product=product, status=InventoryAsset.STATUS_AVAILABLE)
                .order_by('id')[:quantity]
            )
            if len(assets) != quantity:
                raise ValidationError({'items': f'Not enough inventory is available for {product.name}.'})
            InventoryAsset.objects.filter(pk__in=[asset.pk for asset in assets]).update(
                status=InventoryAsset.STATUS_RESERVED,
                reserved_for=order_item,
            )

        total += price * quantity

    discount = Decimal('0.00')
    if coupon_code:
        coupon, discount = _apply_coupon(coupon_code, total)
        Coupon.objects.filter(pk=coupon.pk).update(used_count=F('used_count') + 1)
        order.coupon_code = coupon.code
    if total - discount <= 0:
        raise ValidationError({'items': 'The order total must be greater than zero.'})

    order.total_amount = total - discount
    order.discount_amount = discount
    order.currency = currency or 'USD'
    order.snapshot = {
        'items': [
            {
                'name': item.name,
                'price': str(item.price),
                'quantity': item.quantity,
                'currency': item.currency,
                'provider_id': item.provider_id,
                'details': item.item_snapshot,
            }
            for item in order.items.all()
        ],
        'subtotal': str(total),
        'discount': str(discount),
    }
    order.save(update_fields=['total_amount', 'discount_amount', 'coupon_code', 'currency', 'snapshot', 'updated_at'])
    AuditLog.objects.create(
        actor=str(user.pk),
        action='order.created',
        payload={'order_id': order.pk, 'order_number': order.order_number, 'total': str(order.total_amount)},
    )
    return order, True


@transaction.atomic
def release_reserved_inventory(order):
    """Give back everything an unpaid/failed order was holding: inventory assets, tracked stock, coupon use."""
    InventoryAsset.objects.select_for_update().filter(
        reserved_for__order=order,
        status=InventoryAsset.STATUS_RESERVED,
    ).update(status=InventoryAsset.STATUS_AVAILABLE, reserved_for=None)

    for item in order.items.select_related('variant').all():
        reserved = item.item_snapshot.get('stock_reserved')
        if reserved and item.variant_id:
            ProductVariant.objects.filter(pk=item.variant_id).update(stock=F('stock') + reserved)
            item.item_snapshot = {**item.item_snapshot, 'stock_reserved': 0}
            item.save(update_fields=['item_snapshot'])

    if order.coupon_code and not order.snapshot.get('coupon_released'):
        Coupon.objects.filter(code=order.coupon_code, used_count__gt=0).update(used_count=F('used_count') - 1)
        order.snapshot = {**order.snapshot, 'coupon_released': True}
        order.save(update_fields=['snapshot', 'updated_at'])


@transaction.atomic
def cancel_order(order, *, reason='cancelled', actor=''):
    """Cancel an order that has not been paid. Returns True when the order was cancelled."""
    from payments.models import Payment

    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.STATUS_PENDING_PAYMENT:
        return False
    if Payment.objects.filter(order_id=str(order.pk), status=Payment.STATUS_PAID).exists():
        return False
    Payment.objects.filter(order_id=str(order.pk), status=Payment.STATUS_PENDING).update(status=Payment.STATUS_CANCELLED)
    order.status = Order.STATUS_CANCELLED
    order.notes = (order.notes + f'\n{reason}').strip()
    order.save(update_fields=['status', 'notes', 'updated_at'])
    release_reserved_inventory(order)
    AuditLog.objects.create(actor=actor, action='order.cancelled', payload={'order_id': order.pk, 'reason': reason})
    return True


def expire_pending_orders(minutes=None):
    """Cancel unpaid orders older than the expiry window so reserved stock is freed."""
    from payments.models import Payment

    minutes = settings.ORDER_EXPIRY_MINUTES if minutes is None else minutes
    cutoff = timezone.now() - timedelta(minutes=minutes)
    active_provider_orders = Payment.objects.filter(
        status=Payment.STATUS_PENDING,
        provider_state=1,
    ).values_list('order_id', flat=True)
    candidates = Order.objects.filter(status=Order.STATUS_PENDING_PAYMENT, created_at__lt=cutoff).exclude(
        pk__in=[int(pk) for pk in active_provider_orders if str(pk).isdigit()]
    )
    cancelled = 0
    for order in candidates:
        if cancel_order(order, reason='expired: payment not completed in time', actor='system'):
            cancelled += 1
    return cancelled
