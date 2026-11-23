'use client';

import { FormEvent, useState } from 'react';
import { api, Order, PaymentMethods } from '../lib/api';
import { money, paymentLabel, statusLabel, statusTone } from '../lib/format';

type Props = {
  order: Order;
  methods: PaymentMethods | null;
  busy: boolean;
  onCancel: (order: Order) => void;
  onPay: (order: Order, method: 'test' | 'click' | 'payme') => void;
  onMessage: (text: string, isError?: boolean) => void;
};

export default function OrderCard({ order, methods, busy, onCancel, onPay, onMessage }: Props) {
  const [open, setOpen] = useState(order.status === 'pending_payment' || order.items.some((item) => item.delivered_codes.length > 0));
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const [reviewing, setReviewing] = useState<string | null>(null);

  const available = (['click', 'payme', 'test'] as const).filter((method) => {
    if (!methods || !methods[method]) return false;
    return method === 'test' || order.currency === methods.provider_currency;
  });

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      onMessage('Kod nusxalandi.');
    } catch {
      onMessage('Nusxalab bo‘lmadi — kodni qo‘lda belgilab oling.', true);
    }
  };

  const submitReview = async (event: FormEvent, slug: string) => {
    event.preventDefault();
    try {
      await api(`/products/${encodeURIComponent(slug)}/reviews/`, {
        method: 'POST',
        body: JSON.stringify({ rating, comment }),
      });
      setReviewing(null);
      setComment('');
      onMessage('Sharhingiz uchun rahmat!');
    } catch (caught) {
      onMessage(caught instanceof Error ? caught.message : 'Sharh yuborilmadi.', true);
    }
  };

  return (
    <div className="rounded-xl border border-white/10 bg-zinc-950 p-4 text-sm">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between gap-4 text-left">
        <div>
          <p className="font-semibold">{order.order_number}</p>
          <span className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-xs ${statusTone[order.status] ?? 'border-zinc-600 text-zinc-300'}`}>
            {statusLabel[order.status] ?? order.status}
          </span>
        </div>
        <span className="font-semibold">{money(order.total_amount, order.currency)}</span>
      </button>

      {open && (
        <div className="mt-4 space-y-3 border-t border-white/10 pt-4">
          {order.items.map((item) => (
            <div key={item.id}>
              <p className="text-zinc-200">
                {item.name} × {item.quantity}
                <span className="text-zinc-500"> · {money(item.price, item.currency)}</span>
              </p>
              {item.delivered_codes.map((entry) => (
                <div key={entry.external_id || entry.code} className="mt-2 flex items-center justify-between gap-3 rounded-lg border border-emerald-400/20 bg-emerald-400/5 px-3 py-2">
                  <div className="min-w-0">
                    <code className="break-all text-emerald-200">{entry.code}</code>
                    {entry.instructions && <p className="mt-1 text-xs text-zinc-400">{entry.instructions}</p>}
                  </div>
                  <button onClick={() => void copy(entry.code)} className="shrink-0 rounded-md border border-zinc-700 px-2 py-1 text-xs hover:border-emerald-400">
                    Nusxa
                  </button>
                </div>
              ))}
              {order.status === 'completed' && item.item_snapshot.product_slug && (
                reviewing === item.item_snapshot.product_slug ? (
                  <form onSubmit={(event) => void submitReview(event, item.item_snapshot.product_slug as string)} className="mt-2 flex flex-wrap items-center gap-2">
                    <select value={rating} onChange={(event) => setRating(Number(event.target.value))} aria-label="Baho" className="rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1">
                      {[5, 4, 3, 2, 1].map((value) => <option key={value} value={value}>{'★'.repeat(value)}</option>)}
                    </select>
                    <input value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Sharh (ixtiyoriy)" className="min-w-40 flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1" />
                    <button className="rounded-lg bg-violet-500 px-3 py-1 font-semibold">Yuborish</button>
                  </form>
                ) : (
                  <button onClick={() => setReviewing(item.item_snapshot.product_slug ?? null)} className="mt-1 text-xs text-violet-300 hover:text-white">
                    Baho berish
                  </button>
                )
              )}
            </div>
          ))}

          {Number(order.discount_amount) > 0 && (
            <p className="text-xs text-emerald-300">Kupon {order.coupon_code}: −{money(order.discount_amount, order.currency)}</p>
          )}
          {order.delivery_message && <p className="text-xs text-zinc-400">{order.delivery_message}</p>}
          {order.payments.length > 0 && (
            <p className="text-xs text-zinc-500">
              To‘lov: {order.payments.map((payment) => `${paymentLabel[payment.method] ?? payment.method} (${payment.status})`).join(', ')}
            </p>
          )}

          {order.status === 'pending_payment' && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {available.map((method) => (
                <button key={method} disabled={busy} onClick={() => onPay(order, method)} className="rounded-lg bg-violet-500 px-3 py-2 text-xs font-semibold hover:bg-violet-400 disabled:opacity-50">
                  {paymentLabel[method]} bilan to‘lash
                </button>
              ))}
              <button disabled={busy} onClick={() => onCancel(order)} className="rounded-lg border border-zinc-700 px-3 py-2 text-xs hover:border-rose-400 disabled:opacity-50">
                Bekor qilish
              </button>
              {available.length === 0 && <span className="text-xs text-amber-300">Bu buyurtma uchun to‘lov usuli mavjud emas.</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
