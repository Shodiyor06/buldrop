from rest_framework import serializers
from .models import Product, ProductVariant, Supplier


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'slug', 'code', 'provider_type', 'is_active', 'api_url']


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ['id', 'name', 'sku', 'price', 'currency', 'track_stock', 'stock', 'is_active']


class ProductSerializer(serializers.ModelSerializer):
    variants = serializers.SerializerMethodField()
    supplier = SupplierSerializer(read_only=True)
    game_slug = serializers.CharField(source='game.slug', read_only=True)
    rating_average = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'game', 'game_slug', 'supplier', 'name', 'slug', 'description', 'image_url', 'price', 'currency',
            'fulfillment_type', 'is_skin', 'coin_price', 'is_active', 'variants', 'rating_average', 'review_count', 'available',
        ]

    def get_variants(self, product):
        variants = [variant for variant in product.variants.all() if variant.is_active]
        return ProductVariantSerializer(variants, many=True).data

    def get_rating_average(self, product):
        value = getattr(product, 'rating_average', None)
        return round(float(value), 2) if value is not None else None

    def get_review_count(self, product):
        return getattr(product, 'review_count', 0)

    def get_available(self, product):
        """Whether the product can currently be bought (stock/inventory permitting)."""
        if product.fulfillment_type == Product.FULFILLMENT_INVENTORY:
            return product.inventory_assets.filter(status='available').exists()
        variants = [variant for variant in product.variants.all() if variant.is_active]
        if variants:
            return any(not variant.track_stock or variant.stock > 0 for variant in variants)
        return product.price > 0


class ValidateGameAccountSerializer(serializers.Serializer):
    player_id = serializers.CharField(max_length=160)
    game_slug = serializers.SlugField()


class GameAccountValidationResultSerializer(serializers.Serializer):
    valid = serializers.BooleanField(allow_null=True)
    verification = serializers.CharField()
    player_id = serializers.CharField()
    game_slug = serializers.CharField()
    detail = serializers.CharField()
