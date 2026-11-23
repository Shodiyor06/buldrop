"""Steam helpers: trade-URL parsing and the HTTP client for the Steam bot service."""
import re

import requests
from django.conf import settings

TRADE_URL_RE = re.compile(
    r'^https://steamcommunity\.com/tradeoffer/new/\?partner=(?P<partner>\d{1,12})&token=(?P<token>[A-Za-z0-9_-]{4,20})$'
)
STEAM_ID64_BASE = 76561197960265728
DEFAULT_APPID = 730      # CS2
DEFAULT_CONTEXTID = '2'


class BotError(Exception):
    pass


class TransientBotError(BotError):
    """Network problem or 5xx from the bot: worth retrying."""


class PermanentBotError(BotError):
    """The bot rejected the request: retrying will not help."""


def parse_trade_url(url):
    """Return (partner_id, token, steam_id64) or raise ValueError."""
    match = TRADE_URL_RE.match((url or '').strip())
    if not match:
        raise ValueError('Invalid Steam trade URL. Copy it from Steam > Inventory > Trade Offers > "Who can send me trade offers?".')
    partner = int(match.group('partner'))
    if partner <= 0:
        raise ValueError('Invalid Steam trade URL.')
    return partner, match.group('token'), str(STEAM_ID64_BASE + partner)


def item_descriptor(asset):
    meta = asset.metadata or {}
    return {
        'appid': int(meta.get('appid') or DEFAULT_APPID),
        'contextid': str(meta.get('contextid') or DEFAULT_CONTEXTID),
        'assetid': str(asset.external_id),
    }


def send_offer(withdrawal):
    """Ask the bot service to send the trade offer. Returns the Steam trade offer id ('' if not known yet)."""
    if not settings.STEAM_BOT_URL or not settings.STEAM_BOT_API_KEY:
        raise PermanentBotError('Steam bot is not configured (STEAM_BOT_URL / STEAM_BOT_API_KEY).')
    asset = withdrawal.skin.asset
    if not asset.external_id:
        raise PermanentBotError('The inventory asset has no Steam asset id.')
    payload = {
        'withdrawal_id': withdrawal.pk,
        'trade_url': withdrawal.trade_url,
        'items': [item_descriptor(asset)],
        'message': f'BulDrop withdrawal #{withdrawal.pk}',
    }
    try:
        response = requests.post(
            f'{settings.STEAM_BOT_URL}/trade-offers',
            json=payload,
            headers={'X-Api-Key': settings.STEAM_BOT_API_KEY},
            timeout=settings.STEAM_BOT_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise TransientBotError(str(exc)) from exc
    if response.status_code >= 500 or response.status_code == 429:
        raise TransientBotError(f'Bot answered {response.status_code}.')
    if response.status_code >= 400:
        try:
            detail = response.json().get('error', '')
        except ValueError:
            detail = ''
        raise PermanentBotError(detail or f'Bot rejected the request ({response.status_code}).')
    try:
        return str(response.json().get('offer_id') or '')
    except ValueError as exc:
        raise TransientBotError('Bot returned invalid JSON.') from exc
