'use client';

import { useEffect, useState } from 'react';
import { API_BASE, api, getAccessToken } from '../lib/api';

type Stats = {
  orders: number;
  payments: number;
  tickets: number;
  games: number;
  products: number;
  customers: number;
  paid_orders: number;
  processing_orders: number;
  simulated_orders: number;
  revenue_by_currency: Record<string, string>;
};

const labels: [Exclude<keyof Stats, 'revenue_by_currency'>, string][] = [
  ['orders', 'Buyurtmalar'],
  ['payments', 'To‘lovlar'],
  ['tickets', 'Support murojaatlari'],
  ['games', 'Faol o‘yinlar'],
  ['products', 'Faol mahsulotlar'],
  ['customers', 'Mijozlar'],
  ['paid_orders', 'Yakunlangan buyurtmalar'],
  ['processing_orders', 'Operator kutayotgan buyurtmalar'],
  ['simulated_orders', 'Test simulyatsiyalari'],
];

export default function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const adminUrl = `${API_BASE.replace(/\/api\/v1\/?$/, '')}/admin/`;

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setError('Dashboard uchun admin akkaunt bilan tizimga kiring.');
      setLoading(false);
      return;
    }
    void api<Stats>('/admin/stats/')
      .then(setStats)
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : 'Statistikani yuklab bo‘lmadi.');
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-[#080910] px-5 py-10 text-zinc-100 md:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <a href="/" className="text-sm text-violet-300 hover:text-white">← Do‘konga qaytish</a>
            <h1 className="mt-3 text-3xl font-black">Admin dashboard</h1>
            <p className="mt-2 text-sm text-zinc-400">Ko‘rsatkichlar real database yozuvlaridan olinadi.</p>
          </div>
          <a href={adminUrl} className="rounded-xl border border-zinc-700 px-4 py-3 text-sm font-semibold hover:border-violet-400" target="_blank" rel="noreferrer">
            Katalog va buyurtmalarni boshqarish ↗
          </a>
        </div>

        {loading && <p className="mt-10 animate-pulse text-zinc-400">Ma’lumotlar yuklanmoqda...</p>}
        {error && (
          <div role="alert" className="mt-8 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-rose-200">
            {error}
            <a href="/#account" className="ml-2 underline">Kirish sahifasiga o‘tish</a>
          </div>
        )}
        {stats && (
          <>
            <div className="mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {labels.map(([key, label]) => (
                <article key={key} className="rounded-2xl border border-white/10 bg-zinc-900/70 p-5">
                  <p className="text-sm text-zinc-400">{label}</p>
                  <p className="mt-3 text-3xl font-black">{stats[key]}</p>
                </article>
              ))}
            </div>
            <article className="mt-4 rounded-2xl border border-white/10 bg-zinc-900/70 p-5">
              <p className="text-sm text-zinc-400">Tasdiqlangan provider to‘lovlaridan tushum</p>
              {Object.keys(stats.revenue_by_currency).length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-3">
                  {Object.entries(stats.revenue_by_currency).map(([currency, amount]) => (
                    <p key={currency} className="text-2xl font-black">{amount} {currency}</p>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-lg font-semibold text-zinc-300">Hozircha qayd etilmagan</p>
              )}
              <p className="mt-2 text-xs leading-5 text-zinc-500">
                Test to‘lovlari tushumga kiritilmaydi. Faqat Click/Payme orqali tasdiqlangan to‘lovlar hisoblanadi.
              </p>
            </article>
          </>
        )}
      </div>
    </main>
  );
}
