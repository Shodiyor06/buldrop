from rest_framework import generics, permissions

from .models import Delivery
from .serializers import DeliverySerializer


class DeliveryDetailView(generics.RetrieveAPIView):
    serializer_class = DeliverySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Delivery.objects.all()
        return Delivery.objects.filter(order__user=self.request.user)
