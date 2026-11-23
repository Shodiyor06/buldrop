from rest_framework import generics, permissions

from .models import Game, GameAccount
from .serializers import GameAccountSerializer, GameSerializer


class GameListView(generics.ListAPIView):
    queryset = Game.objects.filter(is_active=True)
    serializer_class = GameSerializer
    permission_classes = [permissions.AllowAny]


class GameDetailView(generics.RetrieveAPIView):
    queryset = Game.objects.filter(is_active=True)
    serializer_class = GameSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'


class GameAccountListCreateView(generics.ListCreateAPIView):
    """Saved player IDs so customers do not retype them at checkout."""

    serializer_class = GameAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return GameAccount.objects.filter(user=self.request.user).select_related('game')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class GameAccountDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = GameAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GameAccount.objects.filter(user=self.request.user).select_related('game')
