'use client';

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  API_BASE,
  api,
  clearSession,
  Game,
  getAccessToken,
  LOGOUT_EVENT,
  newKey,
  Order,
  Paginated,
  PaymentMethods,
  Product,
  saveSession,
  SavedAccount,
  Ticket,
  unwrap,
  Variant,
} from '../lib/api';
import { money, paymentLabel, statusLabel, ticketStatusLabel } from '../lib/format';
import Inventory from './inventory';
import OrderCard from './order-card';
import ProductCard from './product-card';

type CartLine = { key: string; product: Product; variant: Variant | null; quantity: number };
type AuthMode = 'login' | 'register';
type CurrentUser = { username: string; email: string; role: string };
type Method = 'test' | 'click' | 'payme';
type PaymentInit = { payment_id: number; checkout_url?: string; mode: string };

const CART_KEY = 'buldrop_cart';
const unitPrice = (line: CartLine) => Number(line.variant?.price ?? line.product.price);
const unitCurrency = (line: CartLine) => line.variant?.currency ?? line.product.currency;
const input = 'mt-2 w-full rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 outline-none focus:border-violet-400';

export default function Storefront() {
  const [games, setGames] = useState<Game[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [methods, setMethods] = useState<PaymentMethods | null>(null);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [cartLoaded, setCartLoaded] = useState(false);
  const [orders, setOrders] = useState<Order[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [saved, setSaved] = useState<SavedAccount[]>([]);
  const [query, setQuery] = useState('');
  const [selectedGame, setSelectedGame] = useState('');
  const [playerId, setPlayerId] = useState('');
  const [coupon, setCoupon] = useState('');
  const [method, setMethod] = useState<Method | ''>('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authMode, setAuthMode] = useState<AuthMode>('login');
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [ticketTitle, setTicketTitle] = useState('');
  const [ticketMessage, setTicketMessage] = useState('');
  const checkoutKey = useRef<string | null>(null);
  const returnOrder = useRef<number | null>(null);

  const adminUrl = useMemo(() => `${API_BASE.replace(/\/api\/v1\/?$/, '')}/admin/`, []);
  const say = useCallback((text: string, isError = false) => {
    if (isError) { setError(text); setNotice(''); } else { setNotice(text); setError(''); }
  }, []);

  /* ---------- data loading ---------- */
  const loadCatalog = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (query) params.set('q', query);
      if (selectedGame) params.set('game', selectedGame);
      const [gameData, productData] = await Promise.all([
        api<Paginated<Game> | Game[]>('/games/'),
        api<Paginated<Product> | Product[]>(`/products/?${params.toString()}`),
      ]);
      setGames(unwrap(gameData));
      setProducts(unwrap(productData));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Katalogni yuklab bo‘lmadi.');
    } finally {
      setLoading(false);
    }
  }, [query, selectedGame]);

  const loadOrders = useCallback(async () => {
    setOrders(unwrap(await api<Paginated<Order> | Order[]>('/orders/')));
  }, []);

  const loadAccountData = useCallback(async () => {
    const [, ticketData, accountData] = await Promise.all([
      loadOrders(),
      api<Paginated<Ticket> | Ticket[]>('/support/tickets/'),
      api<SavedAccount[]>('/game-accounts/'),
    ]);
    setTickets(unwrap(ticketData));
    setSaved(accountData);
  }, [loadOrders]);

  useEffect(() => { void loadCatalog(); }, [loadCatalog]);

  useEffect(() => {
    api<PaymentMethods>('/payments/methods/')
      .then((data) => {
        setMethods(data);
        setMethod(data.click ? 'click' : data.payme ? 'payme' : data.test ? 'test' : '');
      })
      .catch(() => setMethods({ test: false, click: false, payme: false, provider_currency: 'UZS' }));
  }, []);

  // Cart persistence
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(CART_KEY);
      if (raw) setCart(JSON.parse(raw) as CartLine[]);
    } catch { /* ignore corrupt cart */ }
    setCartLoaded(true);
    const returned = new URLSearchParams(window.location.search).get('order');
    if (returned && /^\d+$/.test(returned)) returnOrder.current = Number(returned);
  }, []);
  useEffect(() => {
    if (cartLoaded) window.localStorage.setItem(CART_KEY, JSON.stringify(cart));
  }, [cart, cartLoaded]);

  // Session restore + forced logout
  useEffect(() => {
    const onLogout = () => { setUser(null); setOrders([]); setTickets([]); setSaved([]); };
    window.addEventListener(LOGOUT_EVENT, onLogout);
    if (getAccessToken()) {
      api<CurrentUser>('/me/')
        .then(async (current) => { setUser(current); await loadAccountData(); })
        .catch(() => undefined);
    }
    return () => window.removeEventListener(LOGOUT_EVENT, onLogout);
  }, [loadAccountData]);

  // Back from Click/Payme: poll the order until it leaves the pending states
  useEffect(() => {
    const id = returnOrder.current;
    if (!user || !id) return;
    returnOrder.current = null;
    window.history.replaceState(null, '', window.location.pathname + '#account');
    let attempts = 0;
    const timer = window.setInterval(async () => {
      attempts += 1;
      try {
        const order = await api<Order>(`/orders/${id}/`);
        if (order.status !== 'pending_payment' || attempts >= 20) {
          window.clearInterval(timer);
          await loadOrders();
          say(
            order.status === 'pending_payment'
              ? `Buyurtma ${order.order_number} uchun to‘lov hali tasdiqlanmadi. Biroz kutib, ro‘yxatni yangilang.`
              : `Buyurtma ${order.order_number}: ${statusLabel[order.status] ?? order.status}.`,
          );
        }
      } catch {
        window.clearInterval(timer);
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [user, loadOrders, say]);

  /* ---------- cart ---------- */
  const addToCart = (product: Product, variant: Variant | null) => {
    checkoutKey.current = null;
    const key = `${product.id}:${variant?.id ?? 0}`;
    setCart((current) => {
      const existing = current.find((line) => line.key === key);
      if (existing) return current.map((line) => (line.key === key ? { ...line, quantity: Math.min(100, line.quantity + 1) } : line));
      return [...current, { key, product, variant, quantity: 1 }];
    });
    say(`${product.name}${variant ? ` — ${variant.name}` : ''} savatga qo‘shildi.`);
  };

  const changeQuantity = (key: string, delta: number) => {
    checkoutKey.current = null;
    setCart((current) =>
      current.map((line) => (line.key === key ? { ...line, quantity: Math.min(100, Math.max(0, line.quantity + delta)) } : line)).filter((line) => line.quantity > 0),
    );
  };

  const total = cart.reduce((sum, line) => sum + unitPrice(line) * line.quantity, 0);
  const currency = cart[0] ? unitCurrency(cart[0]) : 'UZS';
  const mixedCurrency = cart.some((line) => unitCurrency(line) !== currency);
  const needsPlayerId = cart.some((line) => line.product.fulfillment_type === 'topup');
  const liveMethods = (['click', 'payme', 'test'] as Method[]).filter((item) => {
    if (!methods || !methods[item]) return false;
    return item === 'test' || currency === methods.provider_currency;
  });
  const activeMethod: Method | '' = method && liveMethods.includes(method) ? method : liveMethods[0] ?? '';

  /* ---------- payments ---------- */
  const startPayment = async (order: Order, chosen: Method) => {
    const payment = await api<PaymentInit>('/payments/initialize/', {
      method: 'POST',
      body: JSON.stringify({ order_id: order.id, method: chosen }),
    });
    if (chosen === 'test') {
      const result = await api<{ order_status: string }>(`/payments/test/finish/${payment.payment_id}/`, {
        method: 'POST',
        body: JSON.stringify({ outcome: 'paid' }),
      });
      say(`Buyurtma ${order.order_number}: ${statusLabel[result.order_status] ?? result.order_status}. Bu faqat test simulyatsiyasi — haqiqiy to‘lov yoki yetkazib berish emas.`);
      await loadOrders();
      return;
    }
    if (!payment.checkout_url) throw new Error('To‘lov havolasi olinmadi.');
    window.location.href = payment.checkout_url;
  };

  const checkout = async () => {
    if (!user) return say('Buyurtma berish uchun avval tizimga kiring.', true);
    if (needsPlayerId && !playerId.trim()) return say('Top-up uchun o‘yinchi ID sini kiriting.', true);
    if (mixedCurrency) return say('Savatdagi mahsulotlar turli valyutada — alohida buyurtma bering.', true);
    if (!activeMethod) return say('Bu valyuta uchun hozircha to‘lov usuli mavjud emas.', true);
    setBusy(true);
    try {
      checkoutKey.current ??= newKey();
      const order = await api<Order>('/orders/', {
        method: 'POST',
        headers: { 'Idempotency-Key': checkoutKey.current },
        body: JSON.stringify({
          coupon_code: coupon.trim(),
          items: cart.map((line) => ({
            product_id: line.product.id,
            ...(line.variant ? { variant_id: line.variant.id } : {}),
            quantity: line.quantity,
            ...(line.product.fulfillment_type === 'topup' ? { game_account: { player_id: playerId.trim() } } : {}),
          })),
        }),
      });
      setCart([]);
      setCoupon('');
      checkoutKey.current = null;
      await loadOrders();
      try {
        await startPayment(order, activeMethod);
      } catch (caught) {
        say(`Buyurtma ${order.order_number} yaratildi, lekin to‘lov boshlanmadi: ${caught instanceof Error ? caught.message : ''} Buyurtmalar ro‘yxatidan qayta urinib ko‘ring.`, true);
      }
    } catch (caught) {
      say(caught instanceof Error ? caught.message : 'Buyurtma bajarilmadi.', true);
    } finally {
      setBusy(false);
    }
  };

  const payExisting = async (order: Order, chosen: Method) => {
    setBusy(true);
    try { await startPayment(order, chosen); } catch (caught) {
      say(caught instanceof Error ? caught.message : 'To‘lov boshlanmadi.', true);
    } finally { setBusy(false); }
  };

  const cancelOrder = async (order: Order) => {
    setBusy(true);
    try {
      await api(`/orders/${order.id}/cancel/`, { method: 'POST' });
      await loadOrders();
      await loadCatalog();
      say(`Buyurtma ${order.order_number} bekor qilindi.`);
    } catch (caught) {
      say(caught instanceof Error ? caught.message : 'Bekor qilib bo‘lmadi.', true);
    } finally { setBusy(false); }
  };

  /* ---------- account ---------- */
  const handleAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    try {
      if (authMode === 'register') {
        await api('/auth/register/', { method: 'POST', body: JSON.stringify({ username, email, password }) });
      }
      const login = await api<{ access: string; refresh: string }>('/auth/login/', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      saveSession(login.access, login.refresh);
      const current = await api<CurrentUser>('/me/');
      setUser(current);
      await loadAccountData();
      say(`Xush kelibsiz, ${current.username}.`);
      setPassword('');
    } catch (caught) {
      say(caught instanceof Error ? caught.message : 'Kirish amalga oshmadi.', true);
    } finally { setBusy(false); }
  };

  const logout = () => {
    clearSession();
    setUser(null); setOrders([]); setTickets([]); setSaved([]);
    say('Tizimdan chiqdingiz.');
  };

  const saveAccount = async (game: string) => {
    if (!playerId.trim()) return;
    try {
      await api('/game-accounts/', { method: 'POST', body: JSON.stringify({ game_slug: game, player_id: playerId.trim() }) });
      setSaved(await api<SavedAccount[]>('/game-accounts/'));
      say('ID saqlandi.');
    } catch (caught) { say(caught instanceof Error ? caught.message : 'Saqlab bo‘lmadi.', true); }
  };

  const removeAccount = async (id: number) => {
    await api(`/game-accounts/${id}/`, { method: 'DELETE' }).catch(() => undefined);
    setSaved((current) => current.filter((item) => item.id !== id));
  };

  const submitSupportTicket = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user) return say('Support murojaati yuborish uchun tizimga kiring.', true);
    setBusy(true);
    try {
      await api('/support/tickets/', { method: 'POST', body: JSON.stringify({ title: ticketTitle, message: ticketMessage }) });
      setTicketTitle(''); setTicketMessage('');
      setTickets(unwrap(await api<Paginated<Ticket> | Ticket[]>('/support/tickets/')));
      say('Murojaatingiz qabul qilindi.');
    } catch (caught) {
      say(caught instanceof Error ? caught.message : 'Murojaat yuborilmadi.', true);
    } finally { setBusy(false); }
  };

  const firstTopupGame = cart.find((line) => line.product.fulfillment_type === 'topup')?.product.game_slug ?? '';
  const isStaff = user?.role === 'admin' || user?.role === 'support';
  const testOnly = methods?.test && !methods.click && !methods.payme;

  return (
    <main className="min-h-screen bg-[#080910] text-zinc-100">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-[#080910]/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 lg:px-8">
          <a href="#" className="flex items-center gap-3 font-black tracking-tight">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-400 text-lg">B</span>
            <span className="text-xl">BulDrop</span>
          </a>
          <nav className="hidden items-center gap-7 text-sm text-zinc-300 md:flex">
            <a href="#catalog" className="hover:text-white">Katalog</a>
            <a href="#how-it-works" className="hover:text-white">Qanday ishlaydi</a>
            <a href="#faq" className="hover:text-white">Yordam</a>
            {isStaff && <a href="/dashboard" className="hover:text-white">Dashboard</a>}
            {isStaff && <a href={adminUrl} target="_blank" rel="noreferrer" className="hover:text-white">Admin</a>}
          </nav>
          <a href="#account" className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-semibold hover:border-violet-400">
            {user ? user.username : 'Kirish'}
            {cart.length > 0 && <span className="ml-2 rounded-full bg-violet-500 px-2 py-0.5 text-xs">{cart.reduce((n, line) => n + line.quantity, 0)}</span>}
          </a>
        </div>
      </header>

      <section className="relative overflow-hidden border-b border-white/5">
        <div className="pointer-events-none absolute -left-32 top-0 h-96 w-96 rounded-full bg-violet-600/20 blur-[110px]" />
        <div className="pointer-events-none absolute right-0 top-16 h-80 w-80 rounded-full bg-cyan-500/10 blur-[100px]" />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-5 py-16 md:py-24 lg:grid-cols-[1.2fr_0.8fr] lg:px-8">
          <div className="flex flex-col justify-center">
            <p className="mb-5 w-fit rounded-full border border-violet-400/30 bg-violet-400/10 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.2em] text-violet-200">Gaming goods marketplace</p>
            <h1 className="max-w-3xl text-5xl font-black leading-[1.04] tracking-tight md:text-7xl">
              O‘yinlaringiz uchun <span className="bg-gradient-to-r from-violet-300 to-cyan-300 bg-clip-text text-transparent">kerakli mahsulotlar.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-8 text-zinc-400">O‘yin mahsulotlarini toping, savatga qo‘shing, Click yoki Payme orqali to‘lang va buyurtmangizni kuzating. Narx va mavjudlik do‘kon bazasidan olinadi.</p>
            <a href="#catalog" className="mt-8 w-fit rounded-xl bg-gradient-to-r from-violet-500 to-cyan-400 px-6 py-3.5 font-bold shadow-lg shadow-violet-500/20 transition hover:-translate-y-0.5">Katalogni ko‘rish</a>
            {testOnly && <p className="mt-4 text-xs text-amber-300">Test rejimi: hech qanday haqiqiy to‘lov yoki yetkazib berish amalga oshmaydi.</p>}
          </div>
          <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-zinc-900/90 to-[#10111b] p-6 shadow-2xl shadow-violet-900/10 md:p-8">
            <div className="flex items-center justify-between">
              <div><p className="text-sm text-zinc-400">O‘yinlar</p><h2 className="mt-1 text-2xl font-bold">Mashhur katalog</h2></div>
              <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">{games.length} ta</span>
            </div>
            <div className="mt-6 grid grid-cols-2 gap-3">
              {games.slice(0, 6).map((game, index) => (
                <button
                  key={game.id}
                  onClick={() => { setSelectedGame(game.slug); document.getElementById('catalog')?.scrollIntoView({ behavior: 'smooth' }); }}
                  className={`rounded-2xl border p-4 text-left transition hover:-translate-y-1 hover:border-violet-400/50 ${['from-violet-500/20', 'from-cyan-500/15', 'from-rose-500/15', 'from-amber-500/15'][index % 4]} bg-gradient-to-br to-zinc-950 border-white/10`}
                >
                  <span className="text-sm font-semibold">{game.name}</span>
                  <span className="mt-3 block text-xs text-zinc-400">Katalogni ko‘rish ↗</span>
                </button>
              ))}
              {games.length === 0 && !loading && <p className="col-span-2 rounded-xl border border-dashed border-zinc-700 p-5 text-sm text-zinc-400">Hozircha o‘yinlar yo‘q.</p>}
            </div>
          </div>
        </div>
      </section>

      <section id="catalog" className="mx-auto max-w-7xl scroll-mt-24 px-5 py-16 lg:px-8">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div>
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-violet-300">Do‘kon</p>
            <h2 className="mt-2 text-3xl font-black md:text-4xl">Mahsulotlar katalogi</h2>
            <p className="mt-2 text-zinc-400">Narx va mavjudlik serverdan tekshiriladi.</p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <label className="sr-only" htmlFor="catalog-search">Mahsulot qidirish</label>
            <input id="catalog-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Mahsulot qidirish..." className="min-w-64 rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm outline-none focus:border-violet-400" />
            <select aria-label="O‘yin bo‘yicha filter" value={selectedGame} onChange={(event) => setSelectedGame(event.target.value)} className="rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm outline-none focus:border-violet-400">
              <option value="">Barcha o‘yinlar</option>
              {games.map((game) => <option key={game.id} value={game.slug}>{game.name}</option>)}
            </select>
          </div>
        </div>

        {error && <div role="alert" className="mt-6 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">{error}</div>}
        {notice && <div role="status" className="mt-6 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-200">{notice}</div>}

        {loading ? (
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((item) => <div key={item} className="h-56 animate-pulse rounded-2xl bg-zinc-900" />)}</div>
        ) : products.length > 0 ? (
          <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {products.map((product) => <ProductCard key={product.id} product={product} onAdd={addToCart} />)}
          </div>
        ) : (
          <div className="mt-8 rounded-2xl border border-dashed border-zinc-700 bg-zinc-900/30 px-6 py-14 text-center">
            <h3 className="text-lg font-bold">Hech narsa topilmadi</h3>
            <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-zinc-400">
              {query || selectedGame ? 'Qidiruv yoki filterni o‘zgartirib ko‘ring.' : 'Katalog hozircha bo‘sh. Administrator mahsulot qo‘shgach shu yerda ko‘rinadi.'}
            </p>
            {(query || selectedGame) && <button onClick={() => { setQuery(''); setSelectedGame(''); }} className="mt-5 rounded-lg border border-zinc-700 px-4 py-2 text-sm hover:border-violet-400">Filterni tozalash</button>}
          </div>
        )}
      </section>

      <section className="border-y border-white/5 bg-zinc-950/50">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-14 md:grid-cols-3 lg:px-8">
          <div id="how-it-works">
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-cyan-300">Jarayon</p>
            <h2 className="mt-2 text-2xl font-black">Buyurtma qanday ishlaydi</h2>
          </div>
          {[
            ['01', 'Mahsulot tanlang', 'Variantni tanlang va savatga qo‘shing; savat sahifa yangilansa ham saqlanadi.'],
            ['02', 'To‘lang', 'Server narx va mavjudlikni tekshiradi. Click yoki Payme sahifasida to‘lov amalga oshadi.'],
            ['03', 'Qabul qiling', 'Raqamli kodlar to‘lovdan so‘ng darhol buyurtmangizda ko‘rinadi; top-up operator tomonidan bajariladi.'],
          ].map(([number, title, body]) => (
            <div key={number} className="rounded-2xl border border-white/10 bg-zinc-900/50 p-5">
              <p className="text-sm font-bold text-violet-300">{number}</p>
              <h3 className="mt-3 font-bold">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-zinc-400">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="account" className="mx-auto grid max-w-7xl scroll-mt-24 gap-8 px-5 py-16 lg:grid-cols-2 lg:px-8">
        <div className="rounded-2xl border border-white/10 bg-zinc-900/50 p-6 md:p-8">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-bold uppercase tracking-[0.18em] text-violet-300">Akkaunt</p>
              <h2 className="mt-2 text-2xl font-black">{user ? `Salom, ${user.username}` : authMode === 'login' ? 'Tizimga kirish' : 'Ro‘yxatdan o‘tish'}</h2>
            </div>
            {user && <button onClick={logout} className="text-sm text-zinc-400 hover:text-white">Chiqish</button>}
          </div>
          {!user ? (
            <form onSubmit={handleAuth} className="mt-6 space-y-4">
              <label className="block text-sm text-zinc-300">Foydalanuvchi nomi
                <input value={username} onChange={(event) => setUsername(event.target.value)} required autoComplete="username" className={input} />
              </label>
              {authMode === 'register' && (
                <label className="block text-sm text-zinc-300">Email
                  <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" className={input} />
                </label>
              )}
              <label className="block text-sm text-zinc-300">Parol
                <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} autoComplete={authMode === 'login' ? 'current-password' : 'new-password'} className={input} />
              </label>
              <button disabled={busy} className="w-full rounded-xl bg-violet-500 px-4 py-3 font-bold transition hover:bg-violet-400 disabled:opacity-50">{busy ? 'Kuting...' : authMode === 'login' ? 'Kirish' : 'Akkaunt yaratish'}</button>
              <button type="button" onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')} className="w-full text-sm text-zinc-400 hover:text-white">{authMode === 'login' ? 'Yangi akkaunt yaratish' : 'Akkauntingiz bormi? Kirish'}</button>
            </form>
          ) : (
            <div className="mt-6">
              <div className="flex items-center justify-between">
                <p className="text-sm text-zinc-400">{user.email || user.username}</p>
                <button onClick={() => void loadOrders()} className="rounded-lg border border-zinc-700 px-4 py-2 text-sm hover:border-violet-400">Yangilash</button>
              </div>
              {saved.length > 0 && (
                <div className="mt-5">
                  <p className="text-xs font-bold uppercase tracking-wider text-zinc-500">Saqlangan ID lar</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {saved.map((item) => (
                      <span key={item.id} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-zinc-950 px-3 py-1 text-xs">
                        {item.game_name}: {item.player_id}
                        <button aria-label="O‘chirish" onClick={() => void removeAccount(item.id)} className="text-zinc-500 hover:text-rose-300">×</button>
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <div className="mt-5 space-y-3">
                {orders.map((order) => (
                  <OrderCard key={order.id} order={order} methods={methods} busy={busy} onCancel={(item) => void cancelOrder(item)} onPay={(item, chosen) => void payExisting(item, chosen)} onMessage={say} />
                ))}
                {orders.length === 0 && <p className="text-sm text-zinc-500">Hozircha buyurtmalar yo‘q.</p>}
              </div>
            </div>
          )}
        </div>

        <aside className="rounded-2xl border border-white/10 bg-zinc-900/50 p-6 md:p-8">
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-cyan-300">Savat</p>
          <div className="mt-2 flex items-center justify-between">
            <h2 className="text-2xl font-black">Checkout</h2>
            <span className="rounded-full bg-zinc-800 px-3 py-1 text-xs">{cart.reduce((n, line) => n + line.quantity, 0)} ta</span>
          </div>
          <div className="mt-6 space-y-3">
            {cart.map((line) => (
              <div key={line.key} className="flex items-center justify-between gap-3 border-b border-white/10 pb-3">
                <div>
                  <p className="text-sm font-semibold">{line.product.name}{line.variant ? ` — ${line.variant.name}` : ''}</p>
                  <p className="mt-1 text-xs text-zinc-400">{money(unitPrice(line), unitCurrency(line))} × {line.quantity}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button aria-label={`${line.product.name} miqdorini kamaytirish`} onClick={() => changeQuantity(line.key, -1)} className="h-7 w-7 rounded-md bg-zinc-800">−</button>
                  <span className="w-6 text-center text-sm">{line.quantity}</span>
                  <button aria-label={`${line.product.name} miqdorini oshirish`} onClick={() => changeQuantity(line.key, 1)} className="h-7 w-7 rounded-md bg-zinc-800">+</button>
                </div>
              </div>
            ))}
            {cart.length === 0 && <p className="rounded-xl border border-dashed border-zinc-700 p-5 text-sm text-zinc-400">Savat bo‘sh. Katalogdan mahsulot tanlang.</p>}
          </div>

          {needsPlayerId && (
            <div className="mt-5 text-sm text-zinc-300">
              <label>O‘yinchi ID
                <input value={playerId} onChange={(event) => { checkoutKey.current = null; setPlayerId(event.target.value); }} placeholder="Player ID" className={input} />
              </label>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                {saved.map((item) => (
                  <button key={item.id} onClick={() => { checkoutKey.current = null; setPlayerId(item.player_id); }} className="rounded-full border border-white/10 px-3 py-1 hover:border-violet-400">{item.player_id}</button>
                ))}
                {user && playerId.trim() && !saved.some((item) => item.player_id === playerId.trim()) && firstTopupGame && (
                  <button onClick={() => void saveAccount(firstTopupGame)} className="text-violet-300 hover:text-white">ID ni saqlash</button>
                )}
              </div>
              <span className="mt-2 block text-xs text-amber-300">ID ni to‘g‘ri kiriting: top-up aynan shu ID ga yuboriladi, ID avtomatik tekshirilmaydi.</span>
            </div>
          )}

          {cart.length > 0 && (
            <>
              <label className="mt-5 block text-sm text-zinc-300">Kupon (ixtiyoriy)
                <input value={coupon} onChange={(event) => { checkoutKey.current = null; setCoupon(event.target.value); }} placeholder="KUPON" className={input} />
              </label>
              <fieldset className="mt-5">
                <legend className="text-sm text-zinc-300">To‘lov usuli</legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {liveMethods.map((item) => (
                    <label key={item} className={`cursor-pointer rounded-xl border px-4 py-2 text-sm ${activeMethod === item ? 'border-violet-400 bg-violet-500/10' : 'border-zinc-700'}`}>
                      <input type="radio" name="method" value={item} checked={activeMethod === item} onChange={() => setMethod(item)} className="sr-only" />
                      {paymentLabel[item]}
                    </label>
                  ))}
                </div>
                {liveMethods.length === 0 && <p className="mt-2 text-xs text-amber-300">{mixedCurrency ? 'Savatda turli valyutalar bor.' : `Hozircha ${currency} valyutasi uchun to‘lov usuli yoqilmagan.`}</p>}
              </fieldset>
            </>
          )}

          <div className="mt-6 flex justify-between border-t border-white/10 pt-4">
            <span className="text-zinc-400">Jami</span>
            <span className="text-xl font-black">{money(total, currency)}</span>
          </div>
          <button disabled={busy || cart.length === 0 || !activeMethod} onClick={() => void checkout()} className="mt-5 w-full rounded-xl bg-gradient-to-r from-violet-500 to-cyan-400 px-4 py-3 font-bold disabled:cursor-not-allowed disabled:opacity-40">
            {busy ? 'Buyurtma tekshirilmoqda...' : activeMethod === 'test' ? 'Test rejimida buyurtma berish' : 'Buyurtma berish va to‘lash'}
          </button>
          <p className="mt-3 text-center text-xs leading-5 text-zinc-500">
            {activeMethod === 'test' ? 'Faqat lokal test rejimi: haqiqiy pul yechilmaydi.' : 'Chegirma (kupon) yakuniy narxga server tomonida qo‘llanadi. To‘lov Click/Payme sahifasida amalga oshadi.'}
          </p>
        </aside>
      </section>

      {user && <Inventory />}

      <section id="faq" className="border-t border-white/5 bg-zinc-950/40">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-12 md:grid-cols-2 lg:px-8">
          <div>
            <h2 className="text-2xl font-black">Yordam va muhim ma’lumot</h2>
            <p className="mt-3 max-w-xl text-sm leading-6 text-zinc-400">To‘lanmagan buyurtmalar bir soatdan so‘ng avtomatik bekor qilinadi va zaxira bo‘shatiladi. Muammo bo‘lsa pastdagi forma orqali yozing.</p>
          </div>
          <div className="grid gap-3 text-sm text-zinc-300">
            <p className="rounded-xl border border-white/10 p-4">Raqamli kodlar to‘lov tasdiqlangach buyurtma kartasida ko‘rinadi.</p>
            <p className="rounded-xl border border-white/10 p-4">Top-up buyurtmalarini operator qo‘lda bajaradi; holat “Jarayonda” bo‘lib turadi.</p>
          </div>
        </div>
        <form onSubmit={submitSupportTicket} className="mx-auto max-w-7xl px-5 pb-6 lg:px-8">
          <h3 className="text-lg font-bold">Supportga murojaat</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_2fr_auto]">
            <input value={ticketTitle} onChange={(event) => setTicketTitle(event.target.value)} required maxLength={180} placeholder="Mavzu" className="rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm outline-none focus:border-violet-400" />
            <textarea value={ticketMessage} onChange={(event) => setTicketMessage(event.target.value)} required rows={1} placeholder="Xabaringiz" className="resize-y rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm outline-none focus:border-violet-400" />
            <button disabled={busy} className="rounded-xl border border-zinc-700 px-5 py-3 text-sm font-semibold hover:border-violet-400 disabled:opacity-50">Yuborish</button>
          </div>
          {!user && <p className="mt-2 text-xs text-zinc-500">Yuborish uchun akkauntga kiring.</p>}
        </form>
        {tickets.length > 0 && (
          <div className="mx-auto max-w-7xl space-y-3 px-5 pb-12 lg:px-8">
            {tickets.map((ticket) => (
              <div key={ticket.id} className="rounded-xl border border-white/10 p-4 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-semibold">{ticket.title}</p>
                  <span className="text-xs text-zinc-400">{ticketStatusLabel[ticket.status] ?? ticket.status}</span>
                </div>
                <p className="mt-1 text-zinc-400">{ticket.message}</p>
                {ticket.admin_reply && <p className="mt-2 rounded-lg border border-emerald-400/20 bg-emerald-400/5 p-3 text-emerald-100">Javob: {ticket.admin_reply}</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      <footer className="border-t border-white/5 px-5 py-7 text-center text-xs text-zinc-500">
        <div className="flex flex-wrap justify-center gap-x-5 gap-y-2">
          <span>© BulDrop</span>
          <a className="hover:text-zinc-300" href="/terms">Foydalanish shartlari</a>
          <a className="hover:text-zinc-300" href="/privacy">Maxfiylik</a>
          <a className="hover:text-zinc-300" href="/refund">Qaytarish siyosati</a>
        </div>
      </footer>
    </main>
  );
}
