from django.db import models
from games.models import Game


class Supplier(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    code = models.CharField(max_length=50, unique=True)
    provider_type = models.CharField(max_length=50, default='mock')
    is_active = models.BooleanField(default=True)
    api_url = models.URLField(blank=True, default='')
    credential_env = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    FULFILLMENT_TOPUP = 'topup'
    FULFILLMENT_INVENTORY = 'inventory'
    FULFILLMENT_MANUAL = 'manual'
    FULFILLMENT_CHOICES = [
        (FULFILLMENT_TOPUP, 'Top-up'),
        (FULFILLMENT_INVENTORY, 'Inventory'),
        (FULFILLMENT_MANUAL, 'Manual review'),
    ]

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='products')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True, default='')
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default='USD')
    fulfillment_type = models.CharField(max_length=20, choices=FULFILLMENT_CHOICES, default=FULFILLMENT_MANUAL)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=80, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default='USD')
    stock = models.PositiveIntegerField(default=0)
    track_stock = models.BooleanField(
        default=False,
        help_text='When enabled, orders are limited by and decrement the stock counter.',
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['price', 'id']

    def __str__(self):
        return f'{self.product.name} - {self.name}'
