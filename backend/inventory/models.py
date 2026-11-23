from django.db import models
from django.db.models import Q

from catalog.models import Product


class InventoryAsset(models.Model):
    STATUS_AVAILABLE = 'available'
    STATUS_RESERVED = 'reserved'
    STATUS_DELIVERING = 'delivering'
    STATUS_SOLD = 'sold'
    STATUS_UNAVAILABLE = 'unavailable'
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, 'Available'),
        (STATUS_RESERVED, 'Reserved'),
        (STATUS_DELIVERING, 'Delivering'),
        (STATUS_SOLD, 'Sold'),
        (STATUS_UNAVAILABLE, 'Unavailable'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_assets')
    reserved_for = models.ForeignKey(
        'orders.OrderItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reserved_assets',
    )
    external_id = models.CharField(max_length=120, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'external_id'],
                condition=~Q(external_id=''),
                name='unique_product_external_asset_id',
            ),
        ]

    def __str__(self):
        return f'{self.product.name} [{self.status}]'
