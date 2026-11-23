from django.contrib import admin, messages

from .models import SteamWithdrawal, UserSkin, Wallet, WalletTransaction
from .services import apply_withdrawal_result


class ReadOnlyTransactions(admin.TabularInline):
    model = WalletTransaction
    extra = 0
    can_delete = False
    readonly_fields = ['kind', 'amount', 'balance_after', 'description', 'skin', 'created_at']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    # Balances change only through the API/services so every change has a ledger row.
    list_display = ['user', 'balance', 'updated_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['user', 'balance', 'updated_at']
    inlines = [ReadOnlyTransactions]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserSkin)
class UserSkinAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'status', 'sold_price', 'created_at']
    list_filter = ['status', 'product__game']
    search_fields = ['user__username', 'product__name', 'asset__external_id']
    autocomplete_fields = ['user']
    raw_id_fields = ['asset', 'order_item']
    readonly_fields = ['sold_price', 'sold_at', 'created_at', 'updated_at']


@admin.register(SteamWithdrawal)
class SteamWithdrawalAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'skin', 'status', 'trade_offer_id', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'trade_offer_id', 'skin__product__name']
    readonly_fields = ['skin', 'user', 'trade_url', 'steam_id', 'created_at', 'updated_at']
    actions = ['mark_sent', 'mark_accepted', 'mark_failed']

    def _apply(self, request, queryset, new_status, label):
        done = 0
        for withdrawal in queryset:
            before = withdrawal.status
            result = apply_withdrawal_result(
                withdrawal.pk, new_status, actor=request.user.get_username(),
                error='Marked by an operator.' if new_status == SteamWithdrawal.STATUS_FAILED else '',
            )
            done += result.status != before
        self.message_user(request, f'{done} withdrawal(s) marked as {label}.', messages.SUCCESS)

    @admin.action(description='Mark selected as: trade offer sent')
    def mark_sent(self, request, queryset):
        self._apply(request, queryset, SteamWithdrawal.STATUS_SENT, 'sent')

    @admin.action(description='Mark selected as: accepted by the user (skin leaves the inventory)')
    def mark_accepted(self, request, queryset):
        self._apply(request, queryset, SteamWithdrawal.STATUS_ACCEPTED, 'accepted')

    @admin.action(description='Mark selected as: failed (skin returns to the user inventory)')
    def mark_failed(self, request, queryset):
        self._apply(request, queryset, SteamWithdrawal.STATUS_FAILED, 'failed')
