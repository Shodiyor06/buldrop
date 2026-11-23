import type { ReactNode } from 'react';

export default function PolicyPage({
  title,
  updatedAt,
  children,
}: {
  title: string;
  updatedAt: string;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen bg-[#080910] px-5 py-12 text-zinc-100">
      <article className="mx-auto max-w-3xl">
        <a href="/" className="text-sm text-violet-300 hover:text-white">← Do‘konga qaytish</a>
        <h1 className="mt-5 text-4xl font-black">{title}</h1>
        <p className="mt-2 text-xs text-zinc-500">Loyiha matni · yangilangan: {updatedAt}</p>
        <div className="mt-8 rounded-2xl border border-amber-400/20 bg-amber-400/5 p-4 text-sm leading-6 text-amber-100">
          Bu dastlabki loyiha matni bo‘lib, yuridik maslahat emas. Saytni ommaga ochishdan oldin yurist va amaldagi provayder shartlariga muvofiq tekshiring.
        </div>
        <div className="mt-8 max-w-none space-y-6 leading-7 text-zinc-300">
          {children}
        </div>
      </article>
    </main>
  );
}
