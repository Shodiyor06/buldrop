from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.views import MeView, RegisterView
from audit.views import AdminStatsView
from catalog.views import ProductDetailView, ProductListView, ValidateGameAccountView
from delivery.views import DeliveryDetailView
from games.views import GameAccountDetailView, GameAccountListCreateView, GameDetailView, GameListView
from orders.views import (
    OrderCancelView,
    OrderDetailView,
    OrderListCreateView,
    ProductReviewListView,
    SupportTicketDetailView,
    SupportTicketListView,
)
from payments.views import (
    ClickCallbackView,
    PaymeCallbackView,
    PaymentInitializeView,
    PaymentMethodsView,
    TestPaymentFinishView,
)

urlpatterns = [
    path('', include('skins.urls')),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('games/', GameListView.as_view(), name='games'),
    path('games/<slug:slug>/', GameDetailView.as_view(), name='game-detail'),
    path('products/', ProductListView.as_view(), name='products'),
    path('products/<slug:slug>/', ProductDetailView.as_view(), name='product-detail'),
    path('products/<slug:slug>/reviews/', ProductReviewListView.as_view(), name='product-reviews'),
    path('game-accounts/', GameAccountListCreateView.as_view(), name='game-accounts'),
    path('game-accounts/validate/', ValidateGameAccountView.as_view(), name='validate-game-account'),
    path('game-accounts/<int:pk>/', GameAccountDetailView.as_view(), name='game-account-detail'),
    path('orders/', OrderListCreateView.as_view(), name='orders'),
    path('orders/<int:pk>/', OrderDetailView.as_view(), name='order-detail'),
    path('orders/<int:pk>/cancel/', OrderCancelView.as_view(), name='order-cancel'),
    path('payments/methods/', PaymentMethodsView.as_view(), name='payment-methods'),
    path('payments/initialize/', PaymentInitializeView.as_view(), name='payment-initialize'),
    path('payments/test/finish/<int:pk>/', TestPaymentFinishView.as_view(), name='test-payment-finish'),
    path('payments/callback/click/', ClickCallbackView.as_view(), name='click-callback'),
    path('payments/callback/payme/', PaymeCallbackView.as_view(), name='payme-callback'),
    path('deliveries/<int:pk>/', DeliveryDetailView.as_view(), name='delivery-detail'),
    path('support/tickets/', SupportTicketListView.as_view(), name='ticket-list'),
    path('support/tickets/<int:pk>/', SupportTicketDetailView.as_view(), name='ticket-detail'),
    path('admin/stats/', AdminStatsView.as_view(), name='admin-stats'),
]
