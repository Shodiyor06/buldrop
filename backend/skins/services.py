from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, ValidationError

from audit.models import AuditLog
from inventory.models import InventoryAsset

from . import steam
from .models import SteamWithdrawal, UserSkin, Wallet, WalletTransaction


class Conflict(APIException):
    status_code = 409
    default_detail = 'The request conflicts with the current state.'
    default_code = 'conflict'


def get_locked_wallet(user):
    Wallet.objects.get_or_create(user=user)
    return Wallet.objects.select_for_update().get(user=user)


def credit_wallet(user, amount, *, kind, description='', skin=None):
    """Add coins to a wallet and write the ledger row. Must run inside transaction.atomic()."""
    amount = Decimal(amount)
    if amount <= 0:
        raise ValueError('Credit amount must be positive.')
    wallet = get_locked_wallet(user)
    wallet.balance += amount
    wallet.save(update_fields=['balance', 'updated_at'])
    WalletTransaction.objects.create(
        wallet=wallet, kind=kind, amount=amount, balance_after=wallet.balance, description=description, skin=skin,
    )
    return wallet


@transaction.atomic
def grant_skin(*, user, asset, order_item=None):
    """Put a physical asset into a user's inventory."""
    if not asset.product.is_skin:
        raise ValueError('Only skin products can be granted to an inventory.')
    skin = UserSkin.objects.create(user=user, product=asset.product, asset=asset, order_item=order_item)
    AuditLog.objects.create(actor=str(user.pk), action='skin.granted', payload={'skin_id': skin.pk, 'asset_id': asset.pk})
    return skin


def _locked_skin(user, skin_id):
    skin = (
        UserSkin.objects.select_for_update()
        .select_related('product', 'asset')
        .filter(pk=skin_id, user=user)
        .first()
    )
    if skin is None:
        raise NotFound('Skin not found.')
    return skin


@transaction.atomic
def sell_skin(*, user, skin_id):
    """Sell a skin back to the shop for its fixed coin price. Returns (skin, wallet)."""
    skin = _locked_skin(user, skin_id)
    if skin.status != UserSkin.STATUS_IN_INVENTORY:
        raise Conflict('This skin is no longer in your inventory.')
    price = skin.product.coin_price
    if price is None or price <= 0:
        raise ValidationError({'detail': 'This skin cannot be sold for coins right now.'})

    skin.status = UserSkin.STATUS_SOLD
    skin.sold_price = price
    skin.sold_at = timezone.now()
    skin.save(update_fields=['status', 'sold_price', 'sold_at', 'updated_at'])
    # The shop owns the item again: it goes back on the shelf.
    InventoryAsset.objects.filter(pk=skin.asset_id).update(status=InventoryAsset.STATUS_AVAILABLE, reserved_for=None)
    wallet = credit_wallet(
        user, price, kind=WalletTransaction.KIND_SKIN_SALE, description=f'Sold {skin.product.name}', skin=skin,
    )
    AuditLog.objects.create(
        actor=str(user.pk), action='skin.sold', payload={'skin_id': skin.pk, 'coins': str(price)},
    )
    return skin, wallet


@transaction.atomic
def request_withdrawal(*, user, skin_id):
    """Start a withdrawal of a skin to the user's Steam account (trade offer)."""
    from .tasks import dispatch_withdrawal

    skin = _locked_skin(user, skin_id)
    if skin.status != UserSkin.STATUS_IN_INVENTORY:
        raise Conflict('This skin is no longer in your inventory.')
    if not user.steam_trade_url:
        raise ValidationError({'detail': 'Save your Steam trade URL first.'})
    try:
        _, _, steam_id = steam.parse_trade_url(user.steam_trade_url)
    except ValueError as exc:
        raise ValidationError({'detail': str(exc)}) from exc
    if settings.STEAM_TRADE_MODE == 'bot' and not skin.asset.external_id:
        raise ValidationError({'detail': 'This item cannot be withdrawn automatically. Contact support.'})

    withdrawal = SteamWithdrawal.objects.create(
        skin=skin, user=user, trade_url=user.steam_trade_url, steam_id=steam_id,
    )
    skin.status = UserSkin.STATUS_WITHDRAWING
    skin.save(update_fields=['status', 'updated_at'])
    AuditLog.objects.create(
        actor=str(user.pk), action='skin.withdrawal_requested', payload={'skin_id': skin.pk, 'withdrawal_id': withdrawal.pk},
    )
    transaction.on_commit(lambda: dispatch_withdrawal.delay(withdrawal.pk))
    return withdrawal


_FAILED_STATUSES = {
    SteamWithdrawal.STATUS_DECLINED,
    SteamWithdrawal.STATUS_CANCELLED,
    SteamWithdrawal.STATUS_FAILED,
}


@transaction.atomic
def apply_withdrawal_result(withdrawal_id, status, *, offer_id='', error='', actor='system'):
    """Move a withdrawal forward. Idempotent: finished withdrawals are never changed again."""
    withdrawal = SteamWithdrawal.objects.select_for_update().get(pk=withdrawal_id)
    if withdrawal.status not in SteamWithdrawal.OPEN_STATUSES:
        return withdrawal
    skin = UserSkin.objects.select_for_update().get(pk=withdrawal.skin_id)

    if offer_id:
        withdrawal.trade_offer_id = str(offer_id)[:40]
    if error:
        withdrawal.error = error[:300]

    if status == SteamWithdrawal.STATUS_SENT:
        withdrawal.status = SteamWithdrawal.STATUS_SENT
    elif status == SteamWithdrawal.STATUS_ACCEPTED:
        withdrawal.status = SteamWithdrawal.STATUS_ACCEPTED
        skin.status = UserSkin.STATUS_WITHDRAWN
        skin.save(update_fields=['status', 'updated_at'])
    elif status in _FAILED_STATUSES:
        withdrawal.status = status
        skin.status = UserSkin.STATUS_IN_INVENTORY  # the item never left: the user keeps it
        skin.save(update_fields=['status', 'updated_at'])
    else:
        raise ValueError(f'Unknown withdrawal status: {status}')
    withdrawal.save()
    AuditLog.objects.create(
        actor=actor, action=f'skin.withdrawal_{withdrawal.status}',
        payload={'withdrawal_id': withdrawal.pk, 'skin_id': skin.pk, 'offer_id': withdrawal.trade_offer_id},
    )
    return withdrawal


@transaction.atomic
def cancel_withdrawal(*, user, withdrawal_id):
    """The user cancels a withdrawal that has not been sent to Steam yet."""
    withdrawal = (
        SteamWithdrawal.objects.select_for_update().filter(pk=withdrawal_id, user=user).first()
    )
    if withdrawal is None:
        raise NotFound('Withdrawal not found.')
    if withdrawal.status != SteamWithdrawal.STATUS_PENDING:
        raise Conflict('Only withdrawals that have not been sent yet can be cancelled.')
    return apply_withdrawal_result(
        withdrawal.pk, SteamWithdrawal.STATUS_CANCELLED, error='Cancelled by the user.', actor=str(user.pk),
    )
