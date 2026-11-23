from django.contrib import admin

from .models import Category, Game, GameAccount


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'category', 'is_active']
    list_filter = ['is_active', 'category']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}


@admin.register(GameAccount)
class GameAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'game', 'player_id', 'label', 'created_at']
    list_filter = ['game']
    search_fields = ['user__username', 'game__name', 'player_id']
    readonly_fields = ['created_at']
