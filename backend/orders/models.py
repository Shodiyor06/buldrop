from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from catalog.models import Product


class Order(models.Model):
    STATUS_PENDING_PAYMENT = 'pending_payment'
    STATUS_PAID = 'paid'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_REFUND_PENDING = 'refund_pending'
    STATUS_REFUNDED = 'refunded'
    STATUS_SIMULATED = 'simulated'
    STATUS_CHOICES = [
        (STATUS_PENDING_PAYMENT, 'Pending payment'),
        (STATUS_PAID, 'Paid'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_REFUND_PENDING, 'Refund pending'),
        (STATUS_REFUNDED, 'Refunded'),
        (STATUS_SIMULATED, 'Simulated (test mode)'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=40, unique=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True)
    request_fingerprint = models.CharField(max_length=64, blank=True, default='')
    status = models.CharField(max_length=28, choices=STATUS_CHOICES, default=STATUS_PENDING_PAYMENT)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    coupon_code = models.CharField(max_length=40, blank=True, default='')
    currency = models.CharField(max_length=8, default='USD')
    paid_at = models.DateTimeField(null=True, blank=True)
    provider_order_id = models.CharField(max_length=120, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['provider_order_id'],
                condition=~Q(provider_order_id=''),
                name='unique_nonempty_provider_order_id',
            ),
            models.UniqueConstraint(
                fields=['user', 'idempotency_key'],
                condition=Q(idempotency_key__isnull=False),
                name='unique_order_idempotency_per_user',
            ),
        ]

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT, null=True, blank=True, related_name='order_items')
    name = models.CharField(max_length=180)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    quantity = models.PositiveIntegerField(default=1)
    currency = models.CharField(max_length=8, default='USD')
    provider_id = models.CharField(max_length=120, blank=True, default='')
    item_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} x{self.quantity}'


class Coupon(models.Model):
    code = models.CharField(max_length=40, unique=True)
    percent_off = models.PositiveIntegerField(default=0, validators=[MinValueValidator(1), MaxValueValidator(100)])
    max_discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='0 means no cap.',
    )
    valid_until = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text='Empty means unlimited.')
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='unique_review_per_user_product'),
        ]


class SupportTicket(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    title = models.CharField(max_length=180)
    message = models.TextField()
    STATUS_OPEN = 'open'
    STATUS_ANSWERED = 'answered'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_ANSWERED, 'Answered'),
        (STATUS_CLOSED, 'Closed'),
    ]

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_OPEN)
    admin_reply = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
