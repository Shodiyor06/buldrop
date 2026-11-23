from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product

from .models import Order, OrderItem, Review, SupportTicket
from .serializers import (
    OrderCreateSerializer,
    OrderSerializer,
    ReviewSerializer,
    StaffSupportTicketSerializer,
    SupportTicketSerializer,
)
from .services import cancel_order, create_order


def _orders_for(user):
    return Order.objects.filter(user=user).select_related('delivery').prefetch_related('items__reserved_assets')


class OrderListCreateView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return _orders_for(self.request.user)

    @extend_schema(
        request=OrderCreateSerializer,
        responses={200: OrderSerializer, 201: OrderSerializer},
    )
    def post(self, request, *args, **kwargs):
        input_serializer = OrderCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        idempotency_key = request.headers.get('Idempotency-Key')
        if idempotency_key and len(idempotency_key) > 120:
            return Response({'detail': 'Idempotency-Key must be at most 120 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        order, created = create_order(
            user=request.user,
            items=input_serializer.validated_data['items'],
            idempotency_key=idempotency_key,
            coupon_code=input_serializer.validated_data.get('coupon_code', ''),
        )
        order = _orders_for(request.user).get(pk=order.pk)
        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return _orders_for(self.request.user)


class OrderCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=None, responses={200: OrderSerializer})
    def post(self, request, pk):
        order = _orders_for(request.user).filter(pk=pk).first()
        if order is None:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not cancel_order(order, reason='cancelled by customer', actor=str(request.user.pk)):
            return Response({'detail': 'Only unpaid orders can be cancelled.'}, status=status.HTTP_409_CONFLICT)
        return Response(OrderSerializer(_orders_for(request.user).get(pk=pk)).data)


class SupportTicketListView(generics.ListCreateAPIView):
    serializer_class = SupportTicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return SupportTicket.objects.all()
        return SupportTicket.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SupportTicketDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return StaffSupportTicketSerializer if self.request.user.is_staff else SupportTicketSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return SupportTicket.objects.all()
        return SupportTicket.objects.filter(user=self.request.user)

    def update(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({'detail': 'Only support staff can update tickets.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)


class ProductReviewListView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer

    def get_permissions(self):
        return [permissions.AllowAny()] if self.request.method == 'GET' else [permissions.IsAuthenticated()]

    def _product(self):
        return generics.get_object_or_404(Product, slug=self.kwargs['slug'], is_active=True)

    def get_queryset(self):
        return Review.objects.filter(product=self._product()).select_related('user')

    def create(self, request, *args, **kwargs):
        product = self._product()
        purchased = OrderItem.objects.filter(
            Q(order__status=Order.STATUS_COMPLETED),
            order__user=request.user,
            product=product,
        ).exists()
        if not purchased:
            return Response(
                {'detail': 'Only customers with a completed order for this product can leave a review.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review, created = Review.objects.update_or_create(
            user=request.user,
            product=product,
            defaults=serializer.validated_data,
        )
        return Response(
            ReviewSerializer(review).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
