from django.db import transaction

from audit.models import AuditLog
from orders.models import Order

from .models import Delivery, DeliveryAttempt


@transaction.atomic
def complete_manual_delivery(delivery, *, actor='', note=''):
    """Operator confirms they delivered a top-up/manual order. Returns True when the order was completed."""
    delivery = Delivery.objects.select_for_update().get(pk=delivery.pk)
    order = Order.objects.select_for_update().get(pk=delivery.order_id)
    if order.status != Order.STATUS_PROCESSING or delivery.details.get('mode') != 'manual_review':
        return False
    delivery.status = Delivery.STATUS_COMPLETED
    delivery.details = {
        **delivery.details,
        'mode': 'live',
        'message': note or 'Delivered by an operator.',
        'completed_by': actor,
    }
    delivery.save(update_fields=['status', 'details', 'updated_at'])
    DeliveryAttempt.objects.create(delivery=delivery, status='completed', result={'by': actor, 'manual': True})
    order.status = Order.STATUS_COMPLETED
    order.save(update_fields=['status', 'updated_at'])
    AuditLog.objects.create(actor=actor, action='delivery.manual_completed', payload={'order_id': order.pk})
    return True
