from rest_framework import serializers
from .models import Game, GameAccount


class GameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = ['id', 'name', 'slug', 'description', 'logo_url', 'banner_url', 'is_active', 'category']


class GameAccountSerializer(serializers.ModelSerializer):
    game_slug = serializers.SlugRelatedField(
        source='game', slug_field='slug', queryset=Game.objects.filter(is_active=True), write_only=True
    )
    game_name = serializers.CharField(source='game.name', read_only=True)

    class Meta:
        model = GameAccount
        fields = ['id', 'game_slug', 'game_name', 'label', 'player_id', 'created_at']
        read_only_fields = ['id', 'game_name', 'created_at']

    def validate_player_id(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('player_id is required.')
        return value
