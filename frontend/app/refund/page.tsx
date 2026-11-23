import PolicyPage from '../../components/policy-page';

export default function RefundPage() {
  return (
    <PolicyPage title="Qaytarish siyosati" updatedAt="2026-10-21">
      <section>
        <h2 className="text-xl font-bold text-white">Test xaridlari</h2>
        <p>Test to‘lovi haqiqiy pul olmaydi. Test rejimidagi simulyatsiya real xarid yoki real yetkazib berish hisoblanmaydi va qaytariladigan to‘lov yaratmaydi.</p>
      </section>
      <section>
        <h2 className="text-xl font-bold text-white">Haqiqiy to‘lovlar</h2>
        <p>Click va Payme merchant integratsiyalari hozircha yoqilmagan. Haqiqiy to‘lovlarni qabul qilishdan oldin qaytarish shartlari provayder qoidalari, mahsulot turi va amaldagi qonunlarga mos ravishda tasdiqlanishi zarur.</p>
      </section>
      <section>
        <h2 className="text-xl font-bold text-white">Yordam so‘rash</h2>
        <p>Buyurtma bo‘yicha savol bo‘lsa, akkauntga kirib support murojaati yuboring va buyurtma raqamini ko‘rsating. Parol yoki to‘lov kartasi ma’lumotlarini xabarda yubormang.</p>
      </section>
    </PolicyPage>
  );
}
