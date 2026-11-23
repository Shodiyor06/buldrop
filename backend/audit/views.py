from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsMarketplaceAdmin
from catalog.models import Product
from games.models import Game
from orders.models import Order, SupportTicket
from payments.models import Payment
from django.contrib.auth import get_user_model
from django.db.models import Sum
from rest_framework import serializers
from drf_spectacular.utils import extend_schema

User = get_user_model()


class AdminStatsSerializer(serializers.Serializer):
    orders = serializers.IntegerField()
    payments = serializers.IntegerField()
    tickets = serializers.IntegerField()
    games = serializers.IntegerField()
    products = serializers.IntegerField()
    customers = serializers.IntegerField()
    paid_orders = serializers.IntegerField()
    processing_orders = serializers.IntegerField()
    simulated_orders = serializers.IntegerField()
    revenue_by_currency = serializers.DictField(child=serializers.CharField())


class AdminStatsView(APIView):
    permission_classes = [IsMarketplaceAdmin]

    @extend_schema(responses=AdminStatsSerializer)
    def get(self, request):
        revenue_by_currency = {
            row['currency']: str(row['total'])
            for row in Payment.objects.filter(status=Payment.STATUS_PAID)
            .exclude(method=Payment.METHOD_TEST)
            .values('currency')
            .annotate(total=Sum('amount'))
        }
        return Response({
            'orders': Order.objects.count(),
            'payments': Payment.objects.count(),
            'tickets': SupportTicket.objects.count(),
            'games': Game.objects.filter(is_active=True).count(),
            'products': Product.objects.filter(is_active=True).count(),
            'customers': User.objects.filter(role=User.ROLE_CUSTOMER).count(),
            'paid_orders': Order.objects.filter(status=Order.STATUS_COMPLETED).count(),
            'processing_orders': Order.objects.filter(status=Order.STATUS_PROCESSING).count(),
            'simulated_orders': Order.objects.filter(status=Order.STATUS_SIMULATED).count(),
            'revenue_by_currency': revenue_by_currency,
        })
