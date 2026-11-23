from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order_id', 'method', 'provider_payment_id', 'amount', 'currency', 'status', 'created_at']
        read_only_fields = fields


class PaymentInitializeRequestSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    method = serializers.ChoiceField(choices=['test', 'click', 'payme'], required=False, default='test')


class PaymentMethodsSerializer(serializers.Serializer):
    test = serializers.BooleanField()
    click = serializers.BooleanField()
    payme = serializers.BooleanField()
    provider_currency = serializers.CharField()


class PaymentInitializeResultSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    order_id = serializers.IntegerField()
    status = serializers.CharField()
    amount = serializers.CharField()
    currency = serializers.CharField()
    mode = serializers.CharField()
    method = serializers.CharField()
    message = serializers.CharField()
    checkout_url = serializers.CharField(required=False)


class TestPaymentFinishRequestSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=['paid', 'failed'], required=False, default='paid')


class TestPaymentFinishResultSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    payment_status = serializers.CharField()
    order_id = serializers.IntegerField()
    order_status = serializers.CharField()
    mode = serializers.CharField(required=False)


class ProviderCallbackUnavailableSerializer(serializers.Serializer):
    detail = serializers.CharField()
