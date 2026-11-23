from rest_framework import serializers

from . import steam
from .models import SteamWithdrawal, UserSkin, Wallet, WalletTransaction


class WithdrawalSerializer(serializers.ModelSerializer):
    skin_name = serializers.CharField(source='skin.product.name', read_only=True)

    class Meta:
        model = SteamWithdrawal
        fields = ['id', 'skin', 'skin_name', 'status', 'trade_offer_id', 'error', 'created_at', 'updated_at']
        read_only_fields = fields


class UserSkinSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='product.name', read_only=True)
    image_url = serializers.CharField(source='product.image_url', read_only=True)
    game_slug = serializers.CharField(source='product.game.slug', read_only=True)
    sell_price = serializers.SerializerMethodField()
    withdrawal = serializers.SerializerMethodField()

    class Meta:
        model = UserSkin
        fields = ['id', 'name', 'image_url', 'game_slug', 'status', 'sell_price', 'sold_price', 'withdrawal', 'created_at']
        read_only_fields = fields

    def get_sell_price(self, skin):
        if skin.status == UserSkin.STATUS_SOLD:
            return str(skin.sold_price)
        price = skin.product.coin_price
        return str(price) if price and price > 0 else None

    def get_withdrawal(self, skin):
        withdrawal = next(iter(skin.withdrawals.all()), None)  # prefetched, newest first
        return WithdrawalSerializer(withdrawal).data if withdrawal else None


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = ['id', 'kind', 'amount', 'balance_after', 'description', 'created_at']
        read_only_fields = fields


class WalletSerializer(serializers.ModelSerializer):
    transactions = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ['balance', 'transactions']
        read_only_fields = fields

    def get_transactions(self, wallet):
        return WalletTransactionSerializer(wallet.transactions.all()[:20], many=True).data


class SteamProfileSerializer(serializers.Serializer):
    steam_trade_url = serializers.CharField(max_length=300, allow_blank=True)

    def validate_steam_trade_url(self, value):
        value = value.strip()
        if not value:
            return ''
        try:
            steam.parse_trade_url(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value
