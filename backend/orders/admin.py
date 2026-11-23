from django.contrib import admin, messages

from .models import Coupon, Order, OrderItem, Review, SupportTicket
from .services import cancel_order


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['name', 'price', 'quantity', 'currency', 'provider_id', 'item_snapshot']
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'user', 'status', 'total_amount', 'currency', 'created_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['order_number', 'user__username', 'provider_order_id']
    readonly_fields = ['order_number', 'idempotency_key', 'request_fingerprint', 'total_amount', 'discount_amount', 'coupon_code', 'currency', 'paid_at', 'snapshot', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'
    actions = ['cancel_unpaid_orders']

    @admin.action(description='Cancel selected unpaid orders (releases reserved stock)')
    def cancel_unpaid_orders(self, request, queryset):
        cancelled = sum(1 for order in queryset if cancel_order(order, reason='cancelled by staff', actor=request.user.get_username()))
        self.message_user(request, f'{cancelled} order(s) cancelled.', messages.SUCCESS)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'percent_off', 'max_discount', 'used_count', 'usage_limit', 'valid_until', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['product__name', 'user__username', 'comment']


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'user__username', 'message']
    readonly_fields = ['user', 'title', 'message', 'created_at', 'updated_at']
