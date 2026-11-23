import base64
import json
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from orders.models import Order

from . import click, payme
from .models import Payment
from .serializers import (
    PaymentInitializeRequestSerializer,
    PaymentInitializeResultSerializer,
    PaymentMethodsSerializer,
    ProviderCallbackUnavailableSerializer,
    TestPaymentFinishRequestSerializer,
    TestPaymentFinishResultSerializer,
)
from .services import fail_test_payment, order_is_payable, settle_payment


def _return_url(order):
    return f'{settings.FRONTEND_URL}/?order={order.pk}'


def click_checkout_url(order):
    params = {
        'service_id': settings.CLICK_SERVICE_ID,
        'merchant_id': settings.CLICK_MERCHANT_ID,
        'amount': f'{order.total_amount:.2f}',
        'transaction_param': str(order.pk),
        'return_url': _return_url(order),
    }
    if settings.CLICK_MERCHANT_USER_ID:
        params['merchant_user_id'] = settings.CLICK_MERCHANT_USER_ID
    return f'{settings.CLICK_CHECKOUT_URL}?{urlencode(params)}'


def payme_checkout_url(order):
    tiyin = payme.to_tiyin(order.total_amount)
    raw = f'm={settings.PAYME_MERCHANT_KEY};ac.order_id={order.pk};a={tiyin};l=uz;cr=UZS;c={_return_url(order)}'
    return f'{settings.PAYME_CHECKOUT_URL.rstrip("/")}/{base64.b64encode(raw.encode()).decode()}'


class PaymentMethodsView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=PaymentMethodsSerializer)
    def get(self, request):
        return Response({
            'test': settings.TEST_PAYMENT_ENABLED,
            'click': settings.CLICK_ENABLED,
            'payme': settings.PAYME_ENABLED,
            'provider_currency': settings.PROVIDER_CURRENCY,
        })


class PaymentInitializeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=PaymentInitializeRequestSerializer,
        responses={201: PaymentInitializeResultSerializer},
    )
    def post(self, request):
        input_serializer = PaymentInitializeRequestSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        method = input_serializer.validated_data['method']

        enabled = {
            Payment.METHOD_TEST: settings.TEST_PAYMENT_ENABLED,
            Payment.METHOD_CLICK: settings.CLICK_ENABLED,
            Payment.METHOD_PAYME: settings.PAYME_ENABLED,
        }[method]
        if not enabled:
            detail = (
                'Payment providers are not configured. Test payments are disabled.'
                if method == Payment.METHOD_TEST
                else f'{method.title()} is not configured on this server.'
            )
            return Response({'detail': detail}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        order = Order.objects.filter(pk=input_serializer.validated_data['order_id'], user=request.user).first()
        if not order:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not order_is_payable(order):
            return Response({'detail': 'This order cannot accept another payment.'}, status=status.HTTP_409_CONFLICT)
        if method != Payment.METHOD_TEST and order.currency != settings.PROVIDER_CURRENCY:
            return Response(
                {'detail': f'{method.title()} accepts {settings.PROVIDER_CURRENCY} orders only.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = Payment.objects.filter(
            user=request.user,
            order_id=str(order.pk),
            method=method,
            status=Payment.STATUS_PENDING,
        ).first()
        if payment is None:
            payment = Payment.objects.create(
                user=request.user,
                order_id=str(order.pk),
                method=method,
                amount=order.total_amount,
                currency=order.currency,
            )
            AuditLog.objects.create(
                actor=str(request.user.pk),
                action=f'payment.{method}_initialized',
                payload={'payment_id': payment.pk, 'order_id': order.pk},
            )

        body = {
            'payment_id': payment.pk,
            'order_id': order.pk,
            'status': payment.status,
            'amount': str(payment.amount),
            'currency': payment.currency,
            'mode': 'test' if method == Payment.METHOD_TEST else 'live',
            'method': method,
        }
        if method == Payment.METHOD_TEST:
            body['message'] = 'No money will be charged. Confirm or fail this payment in the test flow.'
        else:
            body['checkout_url'] = click_checkout_url(order) if method == Payment.METHOD_CLICK else payme_checkout_url(order)
            body['message'] = 'Redirect the customer to checkout_url to complete the payment.'
        return Response(body, status=status.HTTP_201_CREATED)


class TestPaymentFinishView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=TestPaymentFinishRequestSerializer,
        responses={200: TestPaymentFinishResultSerializer},
    )
    def post(self, request, pk):
        if not settings.TEST_PAYMENT_ENABLED:
            return Response(
                {'detail': 'Test payment actions are disabled.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        input_serializer = TestPaymentFinishRequestSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        outcome = input_serializer.validated_data.get('outcome', 'paid')

        with transaction.atomic():
            payment = Payment.objects.select_for_update().filter(
                pk=pk,
                user=request.user,
                method=Payment.METHOD_TEST,
            ).first()
            if payment is None:
                return Response({'detail': 'Test payment not found.'}, status=status.HTTP_404_NOT_FOUND)
            order = Order.objects.select_for_update().filter(pk=payment.order_id, user=request.user).first()
            if order is None:
                return Response({'detail': 'The payment order no longer exists.'}, status=status.HTTP_404_NOT_FOUND)

            if payment.status == Payment.STATUS_PAID:
                return Response({
                    'payment_id': payment.pk,
                    'payment_status': payment.status,
                    'order_id': order.pk,
                    'order_status': order.status,
                })
            if payment.status != Payment.STATUS_PENDING or not order_is_payable(order):
                return Response({'detail': 'This payment is no longer pending.'}, status=status.HTTP_409_CONFLICT)
            if payment.amount != order.total_amount or payment.currency != order.currency:
                return Response({'detail': 'Payment amount does not match the order.'}, status=status.HTTP_409_CONFLICT)

            if outcome == 'paid':
                settle_payment(payment, order, actor=str(request.user.pk))
            else:
                fail_test_payment(payment, order, actor=str(request.user.pk))

        return Response({
            'payment_id': payment.pk,
            'payment_status': payment.status,
            'order_id': order.pk,
            'order_status': order.status,
            'mode': 'test',
        })


class ProviderCallbackNotConfiguredView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(request=None, responses={503: ProviderCallbackUnavailableSerializer})
    def post(self, request):
        return Response(
            {'detail': 'This payment provider callback is disabled until its merchant credentials are configured.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class ClickCallbackView(ProviderCallbackNotConfiguredView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses={200: OpenApiTypes.OBJECT, 503: ProviderCallbackUnavailableSerializer})
    def post(self, request):
        if not settings.CLICK_ENABLED:
            return super().post(request)
        return Response(click.handle(request.data))


class PaymeCallbackView(ProviderCallbackNotConfiguredView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses={200: OpenApiTypes.OBJECT, 503: ProviderCallbackUnavailableSerializer})
    def post(self, request):
        if not settings.PAYME_ENABLED:
            return super().post(request)
        try:
            payload = json.loads(request.body.decode('utf-8') or 'null')
        except (ValueError, UnicodeDecodeError):
            return Response(payme.error_body(None, payme.ERR_PARSE))
        return Response(payme.handle(payload, request.headers.get('Authorization', '')))
