from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q


class Wallet(models.Model):
    """Site coin balance. Only changed through skins.services (row-locked, with a ledger entry)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(balance__gte=0), name='wallet_balance_non_negative')]

    def __str__(self):
        return f'{self.user} - {self.balance}'


class WalletTransaction(models.Model):
    KIND_SKIN_SALE = 'skin_sale'
    KIND_ADJUSTMENT = 'adjustment'
    KIND_CHOICES = [(KIND_SKIN_SALE, 'Skin sold for coins'), (KIND_ADJUSTMENT, 'Manual adjustment')]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2, help_text='Signed: positive credits, negative debits.')
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=200, blank=True, default='')
    skin = models.ForeignKey('UserSkin', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']


class UserSkin(models.Model):
    STATUS_IN_INVENTORY = 'in_inventory'
    STATUS_WITHDRAWING = 'withdrawing'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_SOLD = 'sold'
    STATUS_CHOICES = [
        (STATUS_IN_INVENTORY, 'In inventory'),
        (STATUS_WITHDRAWING, 'Withdrawal in progress'),
        (STATUS_WITHDRAWN, 'Withdrawn to Steam'),
        (STATUS_SOLD, 'Sold for coins'),
    ]
    ACTIVE_STATUSES = (STATUS_IN_INVENTORY, STATUS_WITHDRAWING)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='skins')
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='user_skins')
    asset = models.ForeignKey('inventory.InventoryAsset', on_delete=models.PROTECT, related_name='user_skins')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='user_skins')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_INVENTORY, db_index=True)
    sold_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sold_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            # A physical Steam item can belong to one user at a time.
            models.UniqueConstraint(
                fields=['asset'],
                condition=Q(status__in=['in_inventory', 'withdrawing']),
                name='unique_active_skin_per_asset',
            ),
        ]

    def __str__(self):
        return f'{self.product.name} ({self.user})'


class SteamWithdrawal(models.Model):
    STATUS_PENDING = 'pending'      # waiting to be sent (queued / waiting for an operator)
    STATUS_SENT = 'sent'            # trade offer is out, waiting for the user to accept it on Steam
    STATUS_ACCEPTED = 'accepted'
    STATUS_DECLINED = 'declined'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENT, 'Trade offer sent'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_DECLINED, 'Declined / expired'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_FAILED, 'Failed'),
    ]
    OPEN_STATUSES = (STATUS_PENDING, STATUS_SENT)

    skin = models.ForeignKey(UserSkin, on_delete=models.CASCADE, related_name='withdrawals')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='steam_withdrawals')
    trade_url = models.URLField(max_length=300)
    steam_id = models.CharField(max_length=20, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    trade_offer_id = models.CharField(max_length=40, blank=True, default='')
    error = models.CharField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['skin'],
                condition=Q(status__in=['pending', 'sent']),
                name='one_open_withdrawal_per_skin',
            ),
        ]

    def __str__(self):
        return f'Withdrawal #{self.pk} ({self.status})'
