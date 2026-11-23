from celery import shared_task
from django.conf import settings

from . import steam
from .models import SteamWithdrawal
from .services import apply_withdrawal_result

MAX_RETRIES = 5


@shared_task(bind=True)
def dispatch_withdrawal(self, withdrawal_id):
    """Send a pending withdrawal to the Steam bot. In 'manual' mode an operator handles it in Django admin."""
    if settings.STEAM_TRADE_MODE != 'bot':
        return 'manual'
    withdrawal = (
        SteamWithdrawal.objects.select_related('skin__asset').filter(pk=withdrawal_id).first()
    )
    if withdrawal is None or withdrawal.status != SteamWithdrawal.STATUS_PENDING:
        return 'skipped'
    try:
        offer_id = steam.send_offer(withdrawal)
    except steam.PermanentBotError as exc:
        apply_withdrawal_result(withdrawal_id, SteamWithdrawal.STATUS_FAILED, error=str(exc))
        return 'failed'
    except steam.TransientBotError as exc:
        if self.request.retries >= MAX_RETRIES:
            apply_withdrawal_result(
                withdrawal_id, SteamWithdrawal.STATUS_FAILED, error=f'Steam bot unavailable: {exc}'
            )
            return 'failed'
        raise self.retry(exc=exc, countdown=30 * 2 ** self.request.retries, max_retries=MAX_RETRIES)
    apply_withdrawal_result(withdrawal_id, SteamWithdrawal.STATUS_SENT, offer_id=offer_id)
    return 'sent'
