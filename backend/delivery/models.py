from django.db import models

from orders.models import Order


class Delivery(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_SIMULATED = 'simulated'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_SIMULATED, 'Simulated (test mode)'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)
    provider = models.CharField(max_length=60, default='mock')
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DeliveryAttempt(models.Model):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='attempts')
    status = models.CharField(max_length=30, default='queued')
    result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
