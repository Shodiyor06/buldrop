'use client';

import { useState } from 'react';
import type { Product, Variant } from '../lib/api';
import { fulfillmentLabel, money } from '../lib/format';

export default function ProductCard({
  product,
  onAdd,
}: {
  product: Product;
  onAdd: (product: Product, variant: Variant | null) => void;
}) {
  const [variantId, setVariantId] = useState<number | null>(product.variants[0]?.id ?? null);
  const variant = product.variants.find((item) => item.id === variantId) ?? null;
  const price = variant?.price ?? product.price;
  const currency = variant?.currency ?? product.currency;
  const soldOut = !product.available || (variant?.track_stock === true && variant.stock <= 0);

  return (
    <article className="group overflow-hidden rounded-2xl border border-white/10 bg-zinc-900/60 transition hover:-translate-y-1 hover:border-violet-400/40">
      <div className="flex h-36 items-end justify-between bg-gradient-to-br from-violet-600/30 via-zinc-900 to-cyan-500/20 p-5">
        <span className="rounded-full border border-white/10 bg-black/30 px-3 py-1 text-xs text-zinc-200">
          {fulfillmentLabel[product.fulfillment_type] ?? product.fulfillment_type}
        </span>
        {product.review_count > 0 && product.rating_average !== null && (
          <span className="rounded-full border border-amber-300/20 bg-black/30 px-3 py-1 text-xs text-amber-200">
            ★ {product.rating_average.toFixed(1)} ({product.review_count})
          </span>
        )}
      </div>
      <div className="p-5">
        <h3 className="text-lg font-bold">{product.name}</h3>
        <p className="mt-2 min-h-10 text-sm text-zinc-400">
          {product.description || 'Do‘kon administratori kiritgan mahsulot.'}
        </p>
        {product.variants.length > 0 && (
          <select
            aria-label={`${product.name} variantini tanlang`}
            value={variantId ?? ''}
            onChange={(event) => setVariantId(Number(event.target.value))}
            className="mt-4 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-violet-400"
          >
            {product.variants.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} — {money(item.price, item.currency)}
                {item.track_stock && item.stock <= 0 ? ' (tugagan)' : ''}
              </option>
            ))}
          </select>
        )}
        <div className="mt-5 flex items-center justify-between gap-3">
          <span className="font-bold text-cyan-200">{money(price, currency)}</span>
          <button
            disabled={soldOut}
            onClick={() => onAdd(product, variant)}
            className="rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-white/10"
          >
            {soldOut ? 'Mavjud emas' : 'Savatga'}
          </button>
        </div>
      </div>
    </article>
  );
}
