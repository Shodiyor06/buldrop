from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class MarketplaceUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Marketplace profile', {'fields': ('role', 'phone', 'avatar_url', 'created_at', 'updated_at')}),
    )
    readonly_fields = ['created_at', 'updated_at']
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Marketplace profile', {'fields': ('email', 'role', 'phone')}),
    )
