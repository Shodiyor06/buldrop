from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order_id', 'user', 'method', 'amount', 'currency', 'status', 'created_at']
    list_filter = ['method', 'status', 'currency', 'created_at']
    search_fields = ['order_id', 'provider_payment_id', 'user__username']
    readonly_fields = [
        'user', 'order_id', 'method', 'provider_payment_id', 'amount', 'currency', 'status', 'callback_payload',
        'provider_state', 'provider_reason', 'provider_create_time', 'provider_perform_time',
        'provider_cancel_time', 'provider_time', 'created_at', 'updated_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
