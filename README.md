# BulDrop

BulDrop is a Django REST Framework and Next.js storefront for an administrator-managed gaming goods shop. It includes user accounts, server-priced orders, inventory reservation, a clearly labelled local test-payment flow, and admin-managed game/product records.

## What works

- Accounts (JWT), catalog with **variants** (e.g. 60 UC / 325 UC), search/filter, ratings and reviews, saved player IDs, coupons, support tickets with staff replies.
- Server-priced orders with idempotency, inventory reservation, optional per-variant stock, 60-minute expiry of unpaid orders, customer cancel.
- **Click** (SHOP API Prepare/Complete) and **Payme** (Merchant API JSON-RPC) payments with signature/Basic-auth checks, idempotent callbacks and refunds. They activate only when their credentials are set.
- Local **test payment** (DEBUG + `PAYMENT_MODE=test`): simulates the order flow, never charges, never reveals or consumes real stock.
- Fulfilment after a real payment: **inventory** products (digital codes) are delivered instantly and shown on the order; **top-up/manual** products wait in the operator queue and you finish them in Django admin (Deliveries -> "Mark selected manual orders as delivered").

## Not implemented (needs things only you can provide)

- **PlayPay / automatic top-ups**: no supplier API documentation or credentials were available, so nothing is faked. Top-ups are fulfilled by an operator. `game-accounts/validate/` still reports "unverified".
- Click/Payme could not be tested against the real providers here (tests simulate their protocols). Run each provider's sandbox/test cabinet before taking real money.

## Skins, coins and Steam withdrawals

- A product with `is_skin=True` and a `coin_price` (admin) is a Steam skin. Its `InventoryAsset.external_id` is the Steam **asset id** in the shop bot's inventory (`metadata`: `{"appid": 730, "contextid": "2"}`).
- After a **real** payment the skin lands in the buyer's inventory (`/api/v1/skins/`). Test payments grant nothing.
- **Sell for coins**: `POST /api/v1/skins/<id>/sell/` credits exactly the product's `coin_price` to the wallet (`GET /api/v1/wallet/`) and puts the item back on the shop shelf. Every change has a ledger row.
- **Withdraw to Steam**: the user saves a trade URL (`PATCH /api/v1/me/steam/`), then `POST /api/v1/skins/<id>/withdraw/`. The skin is locked (cannot be sold twice) until the trade is accepted (skin leaves) or fails/declines (skin returns).
  - `STEAM_TRADE_MODE=manual` (default): an operator sends the trade by hand and uses the actions in admin -> Steam withdrawals.
  - `STEAM_TRADE_MODE=bot`: Django calls the bot in `steam-bot/`, which sends the offer and reports back to `/api/v1/steam/webhook/` (HMAC `STEAM_BOT_WEBHOOK_SECRET`). The bot needs a dedicated Steam account with Steam Guard (shared/identity secrets) and **has not been tested against live Steam here** - try it with a cheap item first. Run it with `BOT_API_KEY`, `BACKEND_WEBHOOK_URL`, `WEBHOOK_SECRET`, `STEAM_USERNAME`, `STEAM_PASSWORD`, `STEAM_SHARED_SECRET`, `STEAM_IDENTITY_SECRET`.
- Give a user a skin for testing: `python manage.py grant_skin <username> <product-slug>`.

## Requirements

- Python 3.12+
- Node.js 22+
- Docker Compose (optional, recommended for PostgreSQL and Redis)

## Run locally

### 1. Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 127.0.0.1:8080
```

Use `.venv` with the leading dot exactly as shown. The commands above call that interpreter directly, so shell activation is optional.

The default local database is SQLite. The first migrations add CS2, PUBG Mobile, Free Fire, Roblox, and Dota 2 as games, without inventing products or prices.

Useful URLs:

- Store API: `http://localhost:8080/api/v1/`
- Django admin: `http://localhost:8080/admin/`
- Swagger UI: `http://localhost:8080/api/docs/`
- OpenAPI schema: `http://localhost:8080/api/schema/`

In admin, create a supplier/product and set a real server-side price. `fulfillment_type` supports top-up, inventory, and manual review. Inventory products require available `InventoryAsset` records.

### 2. Frontend

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. The frontend `.env.local` points to the local backend at port `8080`; restart Next.js after changing this value. If serving both apps over your LAN, add the frontend origin (for example `http://192.168.1.158:3000`) to `CORS_ALLOWED_ORIGINS` in the root `.env`.

### 3. Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

The development stack exposes the storefront through Nginx at `http://localhost:8080`, the backend at `http://localhost:8000`, and PostgreSQL/Redis on their default ports. Create the admin account with:

```bash
docker compose exec backend python manage.py createsuperuser
```

The Compose defaults are for local development only. Do not expose this stack publicly as-is.

## Go-live steps

1. `python manage.py seed_demo` (optional) creates clearly labelled DEMO products so you can try the shop. Replace them in admin with real products and prices. Use **UZS** for anything paid via Click/Payme.
2. Inventory codes: add `InventoryAsset` rows in admin (metadata `{"code": "...", "instructions": "..."}`) or bulk-load: `python manage.py import_inventory <product-slug> codes.txt`.
3. Fill the Click/Payme variables in `.env` (see `.env.example`) and register the callback URLs at the providers:
   - Click: `https://YOUR-DOMAIN/api/v1/payments/callback/click/`
   - Payme: `https://YOUR-DOMAIN/api/v1/payments/callback/payme/` (Basic auth login `Paycom`, password = `PAYME_SECRET_KEY`)
4. Set `DEBUG=False`, strong `SECRET_KEY`/`JWT_SIGNING_KEY`, `ALLOWED_HOSTS`, `FRONTEND_URL`, CORS/CSRF origins, HTTPS.
5. Run the Celery worker with beat (`celery -A config worker -B`) so unpaid orders expire; or schedule `python manage.py expire_pending_orders` with cron.

## Checkout behavior

1. Customer adds products/variants to the cart (persisted in the browser) and optionally enters a coupon.
2. `POST /api/v1/orders/` takes product/variant IDs and quantities only; the server prices everything, applies the coupon, reserves stock. `Idempotency-Key` prevents duplicates.
3. `POST /api/v1/payments/initialize/ {order_id, method}` with `method` = `click` | `payme` | `test`. Click/Payme return a `checkout_url` to redirect to; the provider then calls the callback URL and the order moves to `processing` -> `completed` (codes) or waits for an operator.
4. `GET /api/v1/payments/methods/` tells the frontend which methods are enabled.
5. `POST /api/v1/orders/<id>/cancel/` cancels an unpaid order and frees its reservation.

## Background tasks

For fast local development, `CELERY_TASK_ALWAYS_EAGER=True` executes the test delivery task synchronously without Redis. To exercise a worker queue, set `CELERY_TASK_ALWAYS_EAGER=False`, keep Redis running, and start:

```bash
cd backend
celery -A config worker --loglevel=info
```

## Tests and checks

```bash
cd backend
.venv/bin/python manage.py check
.venv/bin/python manage.py test
.venv/bin/python manage.py makemigrations --check --dry-run
cd ../frontend
npm run build
```

Tests use local/mock behavior only and do not send provider orders.

## Production checklist

- Set `DEBUG=False`, a generated high-entropy `SECRET_KEY`, explicit `ALLOWED_HOSTS`, CORS/CSRF origins, and strong database credentials.
- Set a separate high-entropy `JWT_SIGNING_KEY` as well. Both keys must be at least 50 characters when `DEBUG=False`.
- Provide TLS certificate/key files and enable the HTTPS server block from `deploy/nginx/https-server.example.conf`. Configure HTTP-to-HTTPS redirection at the edge.
- Use managed PostgreSQL and Redis with private network access, backups, restore drills, and monitored retention.
- Configure structured logging, error reporting, rate limits, and secret rotation. Never put provider credentials in source control or return them to clients.
- Replace development `runserver` with a production WSGI server and build/serve the frontend as a production Next.js deployment.
- Implement and test Click/Payme/PlayPay against their current official documentation and sandbox before accepting real payments or promising delivery.
