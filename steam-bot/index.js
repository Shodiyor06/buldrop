// BulDrop Steam bot: sends trade offers for Django withdrawals and reports the outcome back.
// POST /trade-offers  (X-Api-Key)  -> { offer_id }
// Webhook to Django: POST $BACKEND_WEBHOOK_URL with X-Signature = HMAC-SHA256(body, WEBHOOK_SECRET)
const fs = require('fs');
const crypto = require('crypto');
const express = require('express');
const SteamUser = require('steam-user');
const SteamCommunity = require('steamcommunity');
const SteamTotp = require('steam-totp');
const TradeOfferManager = require('steam-tradeoffer-manager');

const env = (name) => {
  const value = process.env[name];
  if (!value) { console.error(`Missing env ${name}`); process.exit(1); }
  return value;
};
const API_KEY = env('BOT_API_KEY');
const WEBHOOK_URL = env('BACKEND_WEBHOOK_URL');
const WEBHOOK_SECRET = env('WEBHOOK_SECRET');
const STATE_FILE = process.env.STATE_FILE || './state.json';

// withdrawal_id -> offer_id (persisted so retries from Django never create a second offer)
let state = {};
try { state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')); } catch { /* first run */ }
const save = () => fs.writeFileSync(STATE_FILE, JSON.stringify(state));

const client = new SteamUser();
const community = new SteamCommunity();
const manager = new TradeOfferManager({ steam: client, community, language: 'en', pollInterval: 15000 });
let ready = false;

client.logOn({
  accountName: env('STEAM_USERNAME'),
  password: env('STEAM_PASSWORD'),
  twoFactorCode: SteamTotp.generateAuthCode(env('STEAM_SHARED_SECRET')),
});
client.on('webSession', (_sid, cookies) => {
  manager.setCookies(cookies, (err) => { if (err) { console.error(err); process.exit(1); } ready = true; console.log('Bot ready'); });
  community.setCookies(cookies);
  community.startConfirmationChecker(10000, env('STEAM_IDENTITY_SECRET'));
});
client.on('error', (err) => { console.error('Steam error', err); process.exit(1); });

async function notify(payload) {
  const body = JSON.stringify(payload);
  const signature = crypto.createHmac('sha256', WEBHOOK_SECRET).update(body).digest('hex');
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      const res = await fetch(WEBHOOK_URL, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Signature': signature }, body });
      if (res.ok || res.status < 500) return;
    } catch { /* retry */ }
    await new Promise((r) => setTimeout(r, 5000 * (attempt + 1)));
  }
  console.error('Webhook failed for', payload);
}

const STATE_MAP = {
  [TradeOfferManager.ETradeOfferState.Accepted]: 'accepted',
  [TradeOfferManager.ETradeOfferState.Declined]: 'declined',
  [TradeOfferManager.ETradeOfferState.Canceled]: 'cancelled',
  [TradeOfferManager.ETradeOfferState.Expired]: 'declined',
  [TradeOfferManager.ETradeOfferState.InvalidItems]: 'failed',
  [TradeOfferManager.ETradeOfferState.CanceledBySecondFactor]: 'cancelled',
};
manager.on('sentOfferChanged', (offer) => {
  const status = STATE_MAP[offer.state];
  const entry = Object.entries(state).find(([, id]) => id === offer.id);
  if (status && entry) void notify({ withdrawal_id: Number(entry[0]), status, offer_id: offer.id });
});

const app = express();
app.use(express.json());
app.get('/health', (_req, res) => res.json({ ready }));
app.post('/trade-offers', (req, res) => {
  if (req.get('X-Api-Key') !== API_KEY) return res.status(401).json({ error: 'unauthorized' });
  if (!ready) return res.status(503).json({ error: 'bot not ready' });
  const { withdrawal_id: id, trade_url: tradeUrl, items, message } = req.body || {};
  if (!id || !tradeUrl || !Array.isArray(items) || items.length === 0) return res.status(400).json({ error: 'invalid request' });
  if (state[id]) return res.json({ offer_id: state[id] });
  const offer = manager.createOffer(tradeUrl);
  items.forEach((item) => offer.addMyItem({ appid: Number(item.appid), contextid: String(item.contextid), assetid: String(item.assetid) }));
  offer.setMessage(message || 'BulDrop');
  offer.send((err) => {
    if (err) return res.status(400).json({ error: String(err.message || err) });
    state[id] = offer.id;
    save();
    res.json({ offer_id: offer.id });
  });
});
app.listen(Number(process.env.PORT || 3100), () => console.log('Steam bot API listening'));
