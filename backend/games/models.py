from django.conf import settings
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Game(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True, default='')
    banner_url = models.URLField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='games')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class GameAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='game_accounts')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='accounts')
    label = models.CharField(max_length=80, blank=True, default='')
    player_id = models.CharField(max_length=160)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.game.name}: {self.player_id}'
