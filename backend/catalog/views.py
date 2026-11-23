from decimal import Decimal, InvalidOperation

from django.db.models import Avg, Count, Q
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .models import Product
from .serializers import GameAccountValidationResultSerializer, ProductSerializer, ValidateGameAccountSerializer


def _with_ratings(queryset):
    # Aggregation drops Meta.ordering, so order explicitly to keep pagination stable.
    return queryset.annotate(
        rating_average=Avg('reviews__rating'),
        review_count=Count('reviews', distinct=True),
    ).order_by('name', 'id')


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = _with_ratings(Product.objects.filter(is_active=True, game__is_active=True).select_related('game', 'supplier').prefetch_related('variants'))
        query = self.request.query_params.get('q')
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(description__icontains=query))
        game_slug = self.request.query_params.get('game')
        if game_slug:
            queryset = queryset.filter(game__slug=game_slug)
        category_slug = self.request.query_params.get('category')
        if category_slug:
            queryset = queryset.filter(game__category__slug=category_slug)
        minimum = self.request.query_params.get('min_price')
        maximum = self.request.query_params.get('max_price')
        try:
            minimum_value = Decimal(minimum) if minimum is not None else None
            maximum_value = Decimal(maximum) if maximum is not None else None
        except InvalidOperation:
            raise serializers.ValidationError({'price': 'Price filters must be valid decimal numbers.'})
        if any(value is not None and (not value.is_finite() or value < 0) for value in (minimum_value, maximum_value)):
            raise serializers.ValidationError({'price': 'Price filters must be finite, non-negative numbers.'})
        if minimum_value is not None and maximum_value is not None and minimum_value > maximum_value:
            raise serializers.ValidationError({'price': 'min_price cannot be greater than max_price.'})
        if minimum_value is not None:
            queryset = queryset.filter(price__gte=minimum_value)
        if maximum_value is not None:
            queryset = queryset.filter(price__lte=maximum_value)
        queryset = queryset.filter(Q(supplier__isnull=True) | Q(supplier__is_active=True))
        return queryset


class ProductDetailView(generics.RetrieveAPIView):
    queryset = _with_ratings(Product.objects.filter(
        is_active=True,
        game__is_active=True,
    ).filter(
        Q(supplier__isnull=True) | Q(supplier__is_active=True)
    ).select_related('game', 'supplier').prefetch_related('variants'))
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'


class ValidateGameAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=ValidateGameAccountSerializer,
        responses={503: GameAccountValidationResultSerializer},
    )
    def post(self, request):
        input_serializer = ValidateGameAccountSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        player_id = input_serializer.validated_data['player_id']
        game_slug = input_serializer.validated_data['game_slug']
        return Response({
            'valid': None,
            'verification': 'unavailable',
            'player_id': str(player_id),
            'game_slug': game_slug,
            'detail': 'No live game-account validation provider is configured. The identifier was not verified.',
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
