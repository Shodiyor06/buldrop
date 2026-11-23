from django.urls import path

from .views import (
    SkinListView,
    SkinSellView,
    SkinWithdrawView,
    SteamProfileView,
    SteamWebhookView,
    WalletView,
    WithdrawalCancelView,
    WithdrawalListView,
)

urlpatterns = [
    path('skins/', SkinListView.as_view(), name='skins'),
    path('skins/<int:pk>/sell/', SkinSellView.as_view(), name='skin-sell'),
    path('skins/<int:pk>/withdraw/', SkinWithdrawView.as_view(), name='skin-withdraw'),
    path('skins/withdrawals/', WithdrawalListView.as_view(), name='withdrawals'),
    path('skins/withdrawals/<int:pk>/cancel/', WithdrawalCancelView.as_view(), name='withdrawal-cancel'),
    path('wallet/', WalletView.as_view(), name='wallet'),
    path('me/steam/', SteamProfileView.as_view(), name='steam-profile'),
    path('steam/webhook/', SteamWebhookView.as_view(), name='steam-webhook'),
]
