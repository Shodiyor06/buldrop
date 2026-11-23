"""Shared payment state transitions used by the test flow and the real provider callbacks."""
from django.db import transaction
from django.utils import timezone

from audit.models import AuditLog
from delivery.models import Delivery
from delivery.tasks import process_delivery
from orders.models import Order
from orders.services import release_reserved_inventory

from .models import Payment

# Orders in these states already have a confirmed payment.
SETTLED_ORDER_STATUSES = {
    Order.STATUS_PAID,
    Order.STATUS_PROCESSING,
    Order.STATUS_COMPLETED,
    Order.STATUS_SIMULATED,
    Order.STATUS_REFUND_PENDING,
    Order.STATUS_REFUNDED,
}


def settle_payment(payment, order, *, actor=''):
    """Mark a pending payment as paid and queue delivery. Must run inside transaction.atomic()."""
    payment.status = Payment.STATUS_PAID
    payment.save(update_fields=['status', 'updated_at'])
    order.status = Order.STATUS_PROCESSING
    order.paid_at = timezone.now()
    order.save(update_fields=['status', 'paid_at', 'updated_at'])
    delivery, _ = Delivery.objects.get_or_create(
        order=order,
        defaults={'provider': 'mock' if payment.method == Payment.METHOD_TEST else 'internal'},
    )
    AuditLog.objects.create(
        actor=actor or payment.method,
        action=f'payment.{payment.method}_paid',
        payload={'payment_id': payment.pk, 'order_id': order.pk, 'amount': str(payment.amount)},
    )
    transaction.on_commit(lambda: process_delivery.delay(delivery.pk))
    return delivery


def fail_test_payment(payment, order, *, actor=''):
    """The local test flow treats a failed payment as a failed order and frees its reservation."""
    payment.status = Payment.STATUS_FAILED
    payment.save(update_fields=['status', 'updated_at'])
    order.status = Order.STATUS_FAILED
    order.save(update_fields=['status', 'updated_at'])
    release_reserved_inventory(order)
    AuditLog.objects.create(
        actor=actor,
        action='payment.test_failed',
        payload={'payment_id': payment.pk, 'order_id': order.pk},
    )


def order_is_payable(order):
    return order.status == Order.STATUS_PENDING_PAYMENT
