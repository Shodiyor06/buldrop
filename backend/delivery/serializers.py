from rest_framework import serializers

from .models import Delivery, DeliveryAttempt


class DeliveryAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAttempt
        fields = ['id', 'status', 'result', 'created_at']


class DeliverySerializer(serializers.ModelSerializer):
    attempts = DeliveryAttemptSerializer(many=True, read_only=True)

    class Meta:
        model = Delivery
        fields = ['id', 'order', 'status', 'provider', 'details', 'attempts', 'created_at']
