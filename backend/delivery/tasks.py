from celery import shared_task
from django.db import transaction

from inventory.models import InventoryAsset
from orders.models import Order
from orders.services import release_reserved_inventory

from .models import Delivery, DeliveryAttempt


def _paid_with_test_payment(order):
    from payments.models import Payment

    payment = Payment.objects.filter(order_id=str(order.pk), status=Payment.STATUS_PAID).order_by('-id').first()
    return payment is None or payment.method == Payment.METHOD_TEST


@shared_task
def process_delivery(delivery_id):
    with transaction.atomic():
        delivery = Delivery.objects.select_for_update().select_related('order').get(id=delivery_id)
        order = Order.objects.select_for_update().get(pk=delivery.order_id)
        if delivery.status in {Delivery.STATUS_COMPLETED, Delivery.STATUS_SIMULATED, Delivery.STATUS_FAILED}:
            return {'status': delivery.status, 'delivery_id': delivery_id}
        if delivery.details.get('mode') == 'manual_review':
            return {'status': 'manual_review', 'delivery_id': delivery_id}
        if order.status != Order.STATUS_PROCESSING:
            return {'status': 'not_ready', 'delivery_id': delivery_id}

        attempt = DeliveryAttempt.objects.create(delivery=delivery, status='started')
        items = list(order.items.select_related('product').all())
        if _paid_with_test_payment(order):
            return _process_test_delivery(delivery, order, attempt, items)
        return _process_live_delivery(delivery, order, attempt, items)


def _process_test_delivery(delivery, order, attempt, items):
    """Test payments never hand over goods; they only exercise the order state machine."""
    if any(item.product.fulfillment_type == 'manual' for item in items):
        delivery.status = Delivery.STATUS_PENDING
        delivery.details = {
            'mode': 'manual_review',
            'message': 'This order requires admin review; no delivery was simulated.',
        }
        delivery.save(update_fields=['status', 'details', 'updated_at'])
        attempt.status = 'manual_review'
        attempt.result = {'mode': 'manual_review'}
        attempt.save(update_fields=['status', 'result'])
        release_reserved_inventory(order)
        return {'status': 'manual_review', 'delivery_id': delivery.pk}

    for item in items:
        if item.product.fulfillment_type == 'inventory':
            assets = item.reserved_assets.select_for_update().filter(status=InventoryAsset.STATUS_RESERVED)
            if assets.count() != item.quantity:
                delivery.status = Delivery.STATUS_FAILED
                delivery.details = {'mode': 'test', 'message': 'Reserved inventory no longer matches this order.'}
                delivery.save(update_fields=['status', 'details', 'updated_at'])
                order.status = Order.STATUS_FAILED
                order.save(update_fields=['status', 'updated_at'])
                attempt.status = 'failed'
                attempt.result = {'reason': 'reserved_inventory_mismatch'}
                attempt.save(update_fields=['status', 'result'])
                return {'status': 'failed', 'delivery_id': delivery.pk}
            # A simulation must not consume (or reveal) real stock: put it back on the shelf.
            assets.update(status=InventoryAsset.STATUS_AVAILABLE, reserved_for=None)

    delivery.status = Delivery.STATUS_SIMULATED
    delivery.details = {
        'mode': 'test',
        'message': 'Test simulation only. No top-up or external item was delivered.',
    }
    delivery.save(update_fields=['status', 'details', 'updated_at'])
    order.status = Order.STATUS_SIMULATED
    order.save(update_fields=['status', 'updated_at'])
    attempt.status = 'simulated'
    attempt.result = {'mode': 'test', 'delivered': False}
    attempt.save(update_fields=['status', 'result'])
    return {'status': 'simulated', 'delivery_id': delivery.pk}


def _process_live_delivery(delivery, order, attempt, items):
    """Real payment: hand over inventory codes immediately; top-ups/manual goods go to an operator."""
    needs_operator = False
    skins_granted = 0
    released = []
    for item in items:
        fulfillment = item.product.fulfillment_type
        if fulfillment == 'inventory':
            assets = list(item.reserved_assets.select_for_update().filter(status=InventoryAsset.STATUS_RESERVED))
            if len(assets) != item.quantity:
                delivery.status = Delivery.STATUS_FAILED
                delivery.details = {'mode': 'live', 'message': 'Reserved inventory no longer matches this paid order.'}
                delivery.save(update_fields=['status', 'details', 'updated_at'])
                order.status = Order.STATUS_REFUND_PENDING
                order.notes = (order.notes + '\nInventory mismatch after payment: refund required.').strip()
                order.save(update_fields=['status', 'notes', 'updated_at'])
                attempt.status = 'failed'
                attempt.result = {'reason': 'reserved_inventory_mismatch'}
                attempt.save(update_fields=['status', 'result'])
                return {'status': 'failed', 'delivery_id': delivery.pk}
            item.reserved_assets.filter(pk__in=[asset.pk for asset in assets]).update(status=InventoryAsset.STATUS_SOLD)
            if item.product.is_skin:
                from skins.services import grant_skin

                for asset in assets:
                    grant_skin(user=order.user, asset=asset, order_item=item)
                skins_granted += len(assets)
            released.append(item.pk)
        else:
            needs_operator = True

    if needs_operator:
        delivery.status = Delivery.STATUS_PENDING
        delivery.details = {
            'mode': 'manual_review',
            'codes_released': bool(released),
            'message': 'Payment received. An operator is processing your top-up/order and will complete it shortly.',
        }
        attempt.status = 'manual_review'
        attempt.result = {'mode': 'manual_review', 'inventory_items': released}
    else:
        delivery.status = Delivery.STATUS_COMPLETED
        delivery.details = {
            'mode': 'live',
            'codes_released': bool(released),
            'message': (
                'Delivered. Your skins are in your inventory: sell them for coins or withdraw them to Steam.'
                if skins_granted
                else 'Delivered. Your codes are shown on the order page.'
            ),
        }
        order.status = Order.STATUS_COMPLETED
        order.save(update_fields=['status', 'updated_at'])
        attempt.status = 'completed'
        attempt.result = {'mode': 'live', 'inventory_items': released}
    delivery.save(update_fields=['status', 'details', 'updated_at'])
    attempt.save(update_fields=['status', 'result'])
    return {'status': delivery.status, 'delivery_id': delivery.pk}
