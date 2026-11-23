from django.contrib import admin, messages

from .models import Delivery, DeliveryAttempt
from .services import complete_manual_delivery


class DeliveryAttemptInline(admin.TabularInline):
    model = DeliveryAttempt
    extra = 0
    can_delete = False
    readonly_fields = ['status', 'result', 'created_at']


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'status', 'provider', 'updated_at']
    list_filter = ['status', 'provider']
    search_fields = ['order__order_number', 'order__user__username']
    readonly_fields = ['order', 'provider', 'details', 'created_at', 'updated_at']
    inlines = [DeliveryAttemptInline]
    actions = ['mark_delivered']

    @admin.action(description='Mark selected manual orders as delivered')
    def mark_delivered(self, request, queryset):
        done = sum(1 for delivery in queryset if complete_manual_delivery(delivery, actor=request.user.get_username()))
        skipped = queryset.count() - done
        if done:
            self.message_user(request, f'{done} order(s) marked as delivered.', messages.SUCCESS)
        if skipped:
            self.message_user(request, f'{skipped} delivery(ies) were not awaiting manual delivery.', messages.WARNING)


@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(admin.ModelAdmin):
    list_display = ['id', 'delivery', 'status', 'created_at']
    list_filter = ['status']
    readonly_fields = ['delivery', 'status', 'result', 'created_at']
