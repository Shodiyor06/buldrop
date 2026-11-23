from rest_framework import serializers

from inventory.models import InventoryAsset

from .models import Order, OrderItem, Review, SupportTicket


class OrderItemSerializer(serializers.ModelSerializer):
    delivered_codes = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'name', 'price', 'quantity', 'currency', 'provider_id', 'item_snapshot', 'delivered_codes']
        read_only_fields = fields

    def get_delivered_codes(self, item):
        """Secrets are shown only to the owner, and only after a real payment released them."""
        delivery = getattr(item.order, 'delivery', None)
        if not delivery or not delivery.details.get('codes_released'):
            return []
        if item.product.is_skin:
            return []  # skins land in the buyer's inventory, they are not shown as codes
        return [
            {
                'external_id': asset.external_id,
                'code': asset.metadata.get('code', ''),
                'instructions': asset.metadata.get('instructions', ''),
            }
            for asset in item.reserved_assets.filter(status=InventoryAsset.STATUS_SOLD)
        ]


class OrderPaymentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    method = serializers.CharField()
    status = serializers.CharField()


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    delivery_status = serializers.SerializerMethodField()
    delivery_message = serializers.SerializerMethodField()
    payments = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'status',
            'total_amount',
            'discount_amount',
            'coupon_code',
            'currency',
            'provider_order_id',
            'notes',
            'snapshot',
            'items',
            'delivery_status',
            'delivery_message',
            'payments',
            'paid_at',
            'created_at',
        ]
        read_only_fields = fields

    def _delivery(self, order):
        return getattr(order, 'delivery', None)

    def get_delivery_status(self, order):
        delivery = self._delivery(order)
        return delivery.status if delivery else None

    def get_delivery_message(self, order):
        delivery = self._delivery(order)
        return delivery.details.get('message', '') if delivery else ''

    def get_payments(self, order):
        from payments.models import Payment

        return OrderPaymentSerializer(
            Payment.objects.filter(order_id=str(order.pk)).order_by('-id'), many=True
        ).data


class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    variant_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, max_value=100)
    game_account = serializers.DictField(required=False, allow_empty=True)

    def validate_game_account(self, value):
        player_id = value.get('player_id')
        if player_id is not None and (not isinstance(player_id, (str, int)) or not str(player_id).strip()):
            raise serializers.ValidationError('player_id must be a non-empty string or integer.')
        return value


class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemCreateSerializer(many=True, allow_empty=False)
    coupon_code = serializers.CharField(max_length=40, required=False, allow_blank=True, default='')

    def validate_items(self, items):
        if len(items) > 20:
            raise serializers.ValidationError('An order can contain at most 20 line items.')
        return items


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ['id', 'title', 'message', 'status', 'admin_reply', 'created_at']
        read_only_fields = ['id', 'status', 'admin_reply', 'created_at']


class StaffSupportTicketSerializer(SupportTicketSerializer):
    class Meta(SupportTicketSerializer.Meta):
        read_only_fields = ['id', 'title', 'message', 'created_at']


class ReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'username', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'username', 'created_at']

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value
