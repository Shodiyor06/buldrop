import PolicyPage from '../../components/policy-page';

export default function PrivacyPage() {
  return (
    <PolicyPage title="Maxfiylik siyosati" updatedAt="2026-10-21">
      <section>
        <h2 className="text-xl font-bold text-white">Qanday ma’lumotlar saqlanadi</h2>
        <p>Akkaunt profili, buyurtma tarixi, support murojaatlari va top-up buyurtmasi uchun mijoz kiritgan o‘yinchi identifikatori saqlanishi mumkin. To‘lov kartasi ma’lumotlari test ilovada yig‘ilmaydi.</p>
      </section>
      <section>
        <h2 className="text-xl font-bold text-white">Foydalanish va kirish</h2>
        <p>Ma’lumotlar akkauntni yuritish, buyurtmalarni ko‘rsatish va supportga javob berish uchun ishlatiladi. Foydalanuvchilar faqat o‘z buyurtmalarini ko‘radi; vakolatli xodimlar ish vazifasi doirasida admin paneldan foydalanadi.</p>
      </section>
      <section>
        <h2 className="text-xl font-bold text-white">Maxfiy ma’lumotlar</h2>
        <p>Provider kalitlari server muhitida saqlanishi kerak va mijoz interfeysiga yuborilmaydi. Steam login parollari so‘ralmaydi yoki saqlanmaydi. Ishlab chiqarishda ma’lumotlarni saqlash muddati va o‘chirish jarayonini alohida belgilang.</p>
      </section>
      <section>
        <h2 className="text-xl font-bold text-white">Murojaat</h2>
        <p>Ma’lumotlarni tuzatish yoki o‘chirish bo‘yicha so‘rovni support orqali yuboring. Yakuniy siyosat yurisdiksiya va amaldagi qonunlarga mos ravishda tasdiqlanishi kerak.</p>
      </section>
    </PolicyPage>
  );
}
