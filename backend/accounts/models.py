from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CUSTOMER = 'customer'
    ROLE_ADMIN = 'admin'
    ROLE_SUPPORT = 'support'
    ROLE_CHOICES = [
        (ROLE_CUSTOMER, 'Customer'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_SUPPORT, 'Support Operator'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CUSTOMER)
    phone = models.CharField(max_length=32, blank=True, default='')
    avatar_url = models.URLField(blank=True, default='')
    steam_id = models.CharField(max_length=20, blank=True, default='')
    steam_trade_url = models.URLField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.ROLE_ADMIN
        if self.role in {self.ROLE_ADMIN, self.ROLE_SUPPORT}:
            self.is_staff = True
        elif not self.is_superuser:
            self.is_staff = False
        super().save(*args, **kwargs)
