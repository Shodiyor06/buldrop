import hashlib
import hmac
import json

from django.conf import settings
from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import steam
from .models import SteamWithdrawal, UserSkin, Wallet
from .serializers import SteamProfileSerializer, UserSkinSerializer, WalletSerializer, WithdrawalSerializer
from .services import apply_withdrawal_result, cancel_withdrawal, request_withdrawal, sell_skin

WEBHOOK_STATUS_MAP = {
    'sent': SteamWithdrawal.STATUS_SENT,
    'accepted': SteamWithdrawal.STATUS_ACCEPTED,
    'declined': SteamWithdrawal.STATUS_DECLINED,
    'expired': SteamWithdrawal.STATUS_DECLINED,
    'cancelled': SteamWithdrawal.STATUS_CANCELLED,
    'canceled': SteamWithdrawal.STATUS_CANCELLED,
    'failed': SteamWithdrawal.STATUS_FAILED,
}


def _skins_for(user):
    return (
        UserSkin.objects.filter(user=user)
        .select_related('product', 'product__game')
        .prefetch_related(Prefetch('withdrawals', queryset=SteamWithdrawal.objects.order_by('-created_at', '-id')))
    )


class SkinListView(generics.ListAPIView):
    """The user's skins. Defaults to the active ones; use ?status=sold|withdrawn|all for history."""

    serializer_class = UserSkinSerializer

    def get_queryset(self):
        queryset = _skins_for(self.request.user)
        wanted = self.request.query_params.get('status', 'active')
        if wanted == 'active':
            return queryset.filter(status__in=UserSkin.ACTIVE_STATUSES)
        if wanted == 'all':
            return queryset
        return queryset.filter(status=wanted)


class SkinSellView(APIView):
    @extend_schema(request=None, responses={200: UserSkinSerializer})
    def post(self, request, pk):
        sell_skin(user=request.user, skin_id=pk)
        skin = _skins_for(request.user).get(pk=pk)
        wallet = Wallet.objects.get(user=request.user)
        return Response({'skin': UserSkinSerializer(skin).data, 'balance': str(wallet.balance)})


class SkinWithdrawView(APIView):
    @extend_schema(request=None, responses={201: WithdrawalSerializer})
    def post(self, request, pk):
        withdrawal = request_withdrawal(user=request.user, skin_id=pk)
        withdrawal.refresh_from_db()
        return Response(WithdrawalSerializer(withdrawal).data, status=status.HTTP_201_CREATED)


class WithdrawalListView(generics.ListAPIView):
    serializer_class = WithdrawalSerializer

    def get_queryset(self):
        return SteamWithdrawal.objects.filter(user=self.request.user).select_related('skin__product')


class WithdrawalCancelView(APIView):
    @extend_schema(request=None, responses={200: WithdrawalSerializer})
    def post(self, request, pk):
        withdrawal = cancel_withdrawal(user=request.user, withdrawal_id=pk)
        return Response(WithdrawalSerializer(withdrawal).data)


class WalletView(APIView):
    @extend_schema(responses=WalletSerializer)
    def get(self, request):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        return Response(WalletSerializer(wallet).data)


class SteamProfileView(APIView):
    """GET/PATCH the Steam trade URL that withdrawals are sent to."""

    def _payload(self, user):
        return {'steam_id': user.steam_id, 'steam_trade_url': user.steam_trade_url}

    @extend_schema(responses=SteamProfileSerializer)
    def get(self, request):
        return Response(self._payload(request.user))

    @extend_schema(request=SteamProfileSerializer, responses=SteamProfileSerializer)
    def patch(self, request):
        serializer = SteamProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        url = serializer.validated_data['steam_trade_url']
        user = request.user
        user.steam_trade_url = url
        user.steam_id = steam.parse_trade_url(url)[2] if url else ''
        user.save(update_fields=['steam_trade_url', 'steam_id', 'updated_at'])
        return Response(self._payload(user))


class SteamWebhookView(APIView):
    """The Steam bot reports trade-offer results here. The body is signed with HMAC-SHA256 (X-Signature)."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(exclude=True)
    def post(self, request):
        secret = settings.STEAM_BOT_WEBHOOK_SECRET
        if not secret:
            return Response({'detail': 'Steam webhook is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, request.headers.get('X-Signature', '')):
            return Response({'detail': 'Invalid signature.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            data = json.loads(request.body)
            withdrawal_id = int(data['withdrawal_id'])
            new_status = WEBHOOK_STATUS_MAP[str(data['status']).lower()]
        except (ValueError, KeyError, TypeError):
            return Response({'detail': 'Invalid payload.'}, status=status.HTTP_400_BAD_REQUEST)
        if not SteamWithdrawal.objects.filter(pk=withdrawal_id).exists():
            return Response({'detail': 'Unknown withdrawal.'}, status=status.HTTP_404_NOT_FOUND)
        withdrawal = apply_withdrawal_result(
            withdrawal_id, new_status,
            offer_id=str(data.get('offer_id') or ''), error=str(data.get('error') or ''), actor='steam-bot',
        )
        return Response({'status': withdrawal.status})
