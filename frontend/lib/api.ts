export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080/api/v1';

export type Game = {
  id: number;
  name: string;
  slug: string;
  description: string;
  logo_url: string;
  banner_url: string;
};

export type Variant = {
  id: number;
  name: string;
  sku: string;
  price: string;
  currency: string;
  track_stock: boolean;
  stock: number;
};

export type Product = {
  id: number;
  game: number;
  game_slug: string;
  name: string;
  slug: string;
  description: string;
  image_url: string;
  price: string;
  currency: string;
  fulfillment_type: 'topup' | 'inventory' | 'manual';
  is_skin: boolean;
  coin_price: string | null;
  variants: Variant[];
  rating_average: number | null;
  review_count: number;
  available: boolean;
};

export type DeliveredCode = { external_id: string; code: string; instructions: string };

export type OrderItem = {
  id: number;
  name: string;
  price: string;
  quantity: number;
  currency: string;
  item_snapshot: { product_slug?: string; fulfillment_type?: string };
  delivered_codes: DeliveredCode[];
};

export type Order = {
  id: number;
  order_number: string;
  status: string;
  total_amount: string;
  discount_amount: string;
  coupon_code: string;
  currency: string;
  items: OrderItem[];
  delivery_status: string | null;
  delivery_message: string;
  payments: { id: number; method: string; status: string }[];
  created_at: string;
};

export type Ticket = {
  id: number;
  title: string;
  message: string;
  status: string;
  admin_reply: string;
  created_at: string;
};

export type SavedAccount = {
  id: number;
  game_name: string;
  label: string;
  player_id: string;
};

export type PaymentMethods = {
  test: boolean;
  click: boolean;
  payme: boolean;
  provider_currency: string;
};

export type Paginated<T> = { results: T[]; count: number };

export const unwrap = <T,>(data: Paginated<T> | T[]): T[] =>
  Array.isArray(data) ? data : data.results;

const ACCESS_KEY = 'buldrop_access';
const REFRESH_KEY = 'buldrop_refresh';
export const LOGOUT_EVENT = 'buldrop:logout';

export function getAccessToken() {
  return typeof window === 'undefined' ? null : window.sessionStorage.getItem(ACCESS_KEY);
}

export function saveSession(access: string, refresh: string) {
  window.sessionStorage.setItem(ACCESS_KEY, access);
  window.sessionStorage.setItem(REFRESH_KEY, refresh);
}

export function clearSession() {
  window.sessionStorage.removeItem(ACCESS_KEY);
  window.sessionStorage.removeItem(REFRESH_KEY);
}

function describeError(data: unknown, status: number): string {
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>;
    if (typeof record.detail === 'string') return record.detail;
    const parts = Object.entries(record).flatMap(([field, value]) => {
      const text = Array.isArray(value) ? value.map(String).join(' ') : typeof value === 'object' && value ? JSON.stringify(value) : String(value);
      return field === 'non_field_errors' ? [text] : [`${field}: ${text}`];
    });
    if (parts.length) return parts.join(' ');
  }
  return `So‘rov bajarilmadi (${status}).`;
}

async function send(path: string, options: RequestInit, token: string | null) {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(`${API_BASE}${path}`, { ...options, headers, cache: 'no-store' });
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = window.sessionStorage.getItem(REFRESH_KEY);
  if (!refresh) return null;
  const response = await fetch(`${API_BASE}/auth/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
    cache: 'no-store',
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || typeof data?.access !== 'string') return null;
  saveSession(data.access, typeof data.refresh === 'string' ? data.refresh : refresh);
  return data.access;
}

/**
 * JSON request helper. When a session exists the access token is attached automatically and refreshed once
 * on a 401; if refreshing fails the session is cleared and LOGOUT_EVENT is dispatched.
 */
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const browser = typeof window !== 'undefined';
  let token = browser ? getAccessToken() : null;
  let response = await send(path, options, token);

  if (response.status === 401 && token && browser) {
    token = await refreshAccessToken();
    if (token) {
      response = await send(path, options, token);
    } else {
      clearSession();
      window.dispatchEvent(new Event(LOGOUT_EVENT));
    }
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(describeError(data, response.status));
  return data as T;
}

/** Kept for existing callers: explicit-token variant. */
export async function apiRequest<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  if (token && typeof window !== 'undefined' && !getAccessToken()) {
    window.sessionStorage.setItem(ACCESS_KEY, token);
  }
  return api<T>(path, options);
}

export function newKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}

export type Withdrawal = {
  id: number;
  skin: number;
  skin_name: string;
  status: 'pending' | 'sent' | 'accepted' | 'declined' | 'cancelled' | 'failed';
  trade_offer_id: string;
  error: string;
  created_at: string;
};

export type Skin = {
  id: number;
  name: string;
  image_url: string;
  game_slug: string;
  status: 'in_inventory' | 'withdrawing' | 'withdrawn' | 'sold';
  sell_price: string | null;
  sold_price: string | null;
  withdrawal: Withdrawal | null;
  created_at: string;
};

export type WalletInfo = {
  balance: string;
  transactions: { id: number; kind: string; amount: string; balance_after: string; description: string; created_at: string }[];
};
