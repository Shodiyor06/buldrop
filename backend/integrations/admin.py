from django.contrib import admin

from .models import IntegrationEvent


@admin.register(IntegrationEvent)
class IntegrationEventAdmin(admin.ModelAdmin):
    list_display = ['provider', 'event_type', 'external_id', 'status', 'created_at']
    list_filter = ['provider', 'status', 'event_type']
    search_fields = ['provider', 'event_type', 'external_id']
    readonly_fields = ['created_at', 'updated_at']
