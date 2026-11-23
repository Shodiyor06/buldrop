from django.contrib import admin

from .models import InventoryAsset


@admin.register(InventoryAsset)
class InventoryAssetAdmin(admin.ModelAdmin):
    list_display = ['product', 'external_id', 'status', 'reserved_for', 'updated_at']
    list_filter = ['status', 'product__game', 'product']
    search_fields = ['product__name', 'external_id']
    readonly_fields = ['created_at', 'updated_at']
    # metadata holds the secret delivered to the buyer, e.g. {"code": "XXXX-XXXX", "instructions": "..."}
    list_select_related = ['product', 'reserved_for']
