'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';
import { api, Paginated, Skin, unwrap, WalletInfo, Withdrawal } from '../lib/api';
import { coins, withdrawalLabel } from '../lib/format';

type SteamProfile = { steam_id: string; steam_trade_url: string };

const input = 'mt-2 w-full rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm outline-none focus:border-violet-400';
const btn = 'rounded-xl px-4 py-2 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-50';

export default function Inventory() {
  const [skins, setSkins] = useState<Skin[]>([]);
  const [wallet, setWallet] = useState<WalletInfo | null>(null);
  const [history, setHistory] = useState<Withdrawal[]>([]);
  const [tradeUrl, setTradeUrl] = useState('');
  const [savedUrl, setSavedUrl] = useState('');
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    try {
      const [skinData, walletData, steam, withdrawals] = await Promise.all([
        api<Paginated<Skin> | Skin[]>('/skins/'),
        api<WalletInfo>('/wallet/'),
        api<SteamProfile>('/me/steam/'),
        api<Paginated<Withdrawal> | Withdrawal[]>('/skins/withdrawals/'),
      ]);
      setSkins(unwrap(skinData));
      setWallet(walletData);
      setTradeUrl(steam.steam_trade_url);
      setSavedUrl(steam.steam_trade_url);
      setHistory(unwrap(withdrawals));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Inventarni yuklab bo‘lmadi.');
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  // While a withdrawal is waiting for Steam, refresh so the user sees the result.
  const waiting = skins.some((skin) => skin.status === 'withdrawing');
  useEffect(() => {
    if (!waiting) return;
    const timer = window.setInterval(() => { void load(); }, 15000);
    return () => window.clearInterval(timer);
  }, [waiting, load]);

  const run = async (skin: Skin, action: () => Promise<unknown>, done: string) => {
    setBusyId(skin.id);
    setError('');
    setNotice('');
    try {
      await action();
      setNotice(done);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Amal bajarilmadi.');
    } finally {
      await load();
      setBusyId(null);
    }
  };

  const sell = (skin: Skin) => {
    if (!skin.sell_price) return;
    if (!window.confirm(`${skin.name} skinini ${coins(skin.sell_price)} evaziga sotasizmi?`)) return;
    void run(skin, () => api(`/skins/${skin.id}/sell/`, { method: 'POST' }), `${skin.name} sotildi: +${coins(skin.sell_price)}.`);
  };

  const withdraw = (skin: Skin) => {
    if (!savedUrl) { setError('Avval Steam trade havolangizni saqlang.'); return; }
    if (!window.confirm(`${skin.name} skinini Steam hisobingizga chiqarasizmi?`)) return;
    void run(skin, () => api(`/skins/${skin.id}/withdraw/`, { method: 'POST' }), 'So‘rov yuborildi. Steam’da trade taklifini qabul qiling.');
  };

  const cancel = (skin: Skin) => {
    if (!skin.withdrawal) return;
    void run(skin, () => api(`/skins/withdrawals/${skin.withdrawal!.id}/cancel/`, { method: 'POST' }), 'Chiqarish bekor qilindi.');
  };

  const saveUrl = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setNotice('');
    try {
      const saved = await api<SteamProfile>('/me/steam/', { method: 'PATCH', body: JSON.stringify({ steam_trade_url: tradeUrl }) });
      setSavedUrl(saved.steam_trade_url);
      setNotice('Steam trade havola saqlandi.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Saqlab bo‘lmadi.');
    }
  };

  return (
    <section id="inventory" className="mx-auto max-w-7xl scroll-mt-24 px-5 py-16 lg:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-violet-300">Inventar</p>
          <h2 className="mt-2 text-3xl font-black">Mening skinlarim</h2>
        </div>
        <div className="rounded-2xl border border-emerald-400/30 bg-emerald-400/10 px-5 py-3 text-right">
          <p className="text-xs text-emerald-200">Balans</p>
          <p className="text-xl font-black text-emerald-100">{wallet ? coins(wallet.balance) : '…'}</p>
        </div>
      </div>

      {error && <p role="alert" className="mt-4 rounded-xl border border-rose-400/30 bg-rose-400/10 px-4 py-3 text-sm text-rose-200">{error}</p>}
      {notice && <p role="status" className="mt-4 rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200">{notice}</p>}

      <form onSubmit={saveUrl} className="mt-6 rounded-2xl border border-white/10 bg-zinc-900/60 p-5">
        <label className="text-sm font-semibold" htmlFor="trade-url">Steam trade havolasi</label>
        <p className="mt-1 text-xs text-zinc-400">Steam → Inventar → Trade takliflari → “Menga kim trade yubora oladi?” bo‘limidan nusxa oling. Inventaringiz ochiq (public) bo‘lishi kerak.</p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input id="trade-url" className={input} placeholder="https://steamcommunity.com/tradeoffer/new/?partner=…&token=…" value={tradeUrl} onChange={(e) => setTradeUrl(e.target.value)} />
          <button className={`${btn} mt-2 bg-violet-500 text-white hover:bg-violet-400`} type="submit">Saqlash</button>
        </div>
      </form>

      {skins.length === 0 ? (
        <p className="mt-8 rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm text-zinc-400">Inventaringiz bo‘sh. Skin sotib olganingizda u shu yerga tushadi.</p>
      ) : (
        <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {skins.map((skin) => (
            <li key={skin.id} className="rounded-2xl border border-white/10 bg-zinc-900/60 p-4">
              {skin.image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={skin.image_url} alt={skin.name} className="h-36 w-full rounded-xl object-contain" />
              )}
              <h3 className="mt-3 font-bold">{skin.name}</h3>
              <p className="mt-1 text-sm text-zinc-400">
                {skin.sell_price ? `Sotish narxi: ${coins(skin.sell_price)}` : 'Tangaga sotib bo‘lmaydi'}
              </p>
              {skin.status === 'withdrawing' && skin.withdrawal ? (
                <div className="mt-3 space-y-2">
                  <p className="text-sm text-sky-200">{withdrawalLabel[skin.withdrawal.status]}</p>
                  {skin.withdrawal.status === 'pending' && (
                    <button className={`${btn} border border-zinc-600 text-zinc-200 hover:bg-zinc-800`} disabled={busyId === skin.id} onClick={() => cancel(skin)}>Bekor qilish</button>
                  )}
                </div>
              ) : (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className={`${btn} bg-emerald-500 text-black hover:bg-emerald-400`} disabled={busyId === skin.id || !skin.sell_price} onClick={() => sell(skin)}>Tangaga sotish</button>
                  <button className={`${btn} bg-violet-500 text-white hover:bg-violet-400`} disabled={busyId === skin.id} onClick={() => withdraw(skin)}>Steam’ga chiqarish</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {history.length > 0 && (
        <div className="mt-10">
          <h3 className="text-lg font-bold">Chiqarishlar tarixi</h3>
          <ul className="mt-3 divide-y divide-white/5 rounded-2xl border border-white/10 text-sm">
            {history.map((item) => (
              <li key={item.id} className="flex flex-wrap justify-between gap-2 px-4 py-3">
                <span>{item.skin_name}</span>
                <span className="text-zinc-400">{withdrawalLabel[item.status]}{item.error ? ` — ${item.error}` : ''}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {wallet && wallet.transactions.length > 0 && (
        <div className="mt-10">
          <h3 className="text-lg font-bold">Balans tarixi</h3>
          <ul className="mt-3 divide-y divide-white/5 rounded-2xl border border-white/10 text-sm">
            {wallet.transactions.map((tx) => (
              <li key={tx.id} className="flex justify-between gap-2 px-4 py-3">
                <span>{tx.description || tx.kind}</span>
                <span className={Number(tx.amount) >= 0 ? 'text-emerald-300' : 'text-rose-300'}>{Number(tx.amount) >= 0 ? '+' : ''}{coins(tx.amount)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
