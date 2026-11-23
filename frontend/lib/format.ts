export const money = (value: string | number, currency: string) => {
  const amount = Number(value);
  const digits = currency === 'UZS' ? 0 : 2;
  return `${amount.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).replace(/,/g, ' ')} ${currency === 'UZS' ? 'so‘m' : currency}`;
};

export const statusLabel: Record<string, string> = {
  pending_payment: 'To‘lov kutilmoqda',
  paid: 'To‘langan',
  processing: 'Jarayonda',
  simulated: 'Test simulyatsiyasi',
  completed: 'Bajarildi',
  failed: 'Xatolik',
  cancelled: 'Bekor qilingan',
  refund_pending: 'Qaytarish kutilmoqda',
  refunded: 'Qaytarilgan',
};

export const statusTone: Record<string, string> = {
  pending_payment: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
  processing: 'border-sky-400/30 bg-sky-400/10 text-sky-200',
  completed: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
  simulated: 'border-violet-400/30 bg-violet-400/10 text-violet-200',
  failed: 'border-rose-400/30 bg-rose-400/10 text-rose-200',
  cancelled: 'border-zinc-500/30 bg-zinc-500/10 text-zinc-300',
  refunded: 'border-zinc-500/30 bg-zinc-500/10 text-zinc-300',
  refund_pending: 'border-rose-400/30 bg-rose-400/10 text-rose-200',
};

export const ticketStatusLabel: Record<string, string> = {
  open: 'Ochiq',
  answered: 'Javob berildi',
  closed: 'Yopilgan',
};

export const paymentLabel: Record<string, string> = {
  test: 'Test to‘lov',
  click: 'Click',
  payme: 'Payme',
};

export const fulfillmentLabel: Record<string, string> = {
  topup: 'Top-up',
  inventory: 'Raqamli kod',
  manual: 'Operator orqali',
};

export const coins = (value: string | number) =>
  `${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).replace(/,/g, ' ')} tanga`;

export const withdrawalLabel: Record<string, string> = {
  pending: 'Navbatda',
  sent: 'Steam’da taklif yuborildi — qabul qiling',
  accepted: 'Steam’ga o‘tkazildi',
  declined: 'Rad etildi / muddati tugadi',
  cancelled: 'Bekor qilindi',
  failed: 'Xatolik',
};
