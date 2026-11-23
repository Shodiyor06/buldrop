from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q


class Payment(models.Model):
    METHOD_CLICK = 'click'
    METHOD_PAYME = 'payme'
    METHOD_TEST = 'test'
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'

    METHOD_CHOICES = [
        (METHOD_CLICK, 'Click'),
        (METHOD_PAYME, 'Payme'),
        (METHOD_TEST, 'Test'),
    ]
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    order_id = models.CharField(max_length=120, db_index=True)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_TEST)
    provider_payment_id = models.CharField(max_length=160, blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=8, default='USD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    callback_payload = models.JSONField(default=dict, blank=True)
    # Provider protocol state (Payme transaction state machine / Click prepare id).
    provider_state = models.SmallIntegerField(null=True, blank=True)
    provider_reason = models.SmallIntegerField(null=True, blank=True)
    provider_create_time = models.BigIntegerField(null=True, blank=True, help_text='Unix ms')
    provider_perform_time = models.BigIntegerField(null=True, blank=True, help_text='Unix ms')
    provider_cancel_time = models.BigIntegerField(null=True, blank=True, help_text='Unix ms')
    provider_time = models.BigIntegerField(null=True, blank=True, help_text='Provider-reported time (Unix ms)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['provider_payment_id'],
                condition=~Q(provider_payment_id=''),
                name='unique_nonempty_provider_payment_id',
            ),
        ]

    def __str__(self):
        return f'{self.method} {self.order_id}'
