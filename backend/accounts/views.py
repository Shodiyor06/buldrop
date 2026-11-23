from django.contrib.auth import get_user_model
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)
