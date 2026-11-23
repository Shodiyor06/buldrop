from django.contrib import admin

from .models import Product, ProductVariant, Supplier


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'provider_type', 'is_active']
    list_filter = ['provider_type', 'is_active']
    search_fields = ['name', 'code', 'slug']
    fields = ['name', 'slug', 'code', 'provider_type', 'api_url', 'credential_env', 'is_active']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'game', 'price', 'currency', 'fulfillment_type', 'is_active']
    list_filter = ['game', 'fulfillment_type', 'is_active', 'currency']
    search_fields = ['name', 'slug', 'game__name']
    prepopulated_fields = {'slug': ['name']}
    list_select_related = ['game', 'supplier']
    inlines = [ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['name', 'product', 'sku', 'price', 'currency', 'track_stock', 'stock', 'is_active']
    list_filter = ['currency', 'is_active']
    search_fields = ['name', 'sku', 'product__name']
