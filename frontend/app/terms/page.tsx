import PolicyPage from '../../components/policy-page';

export default function TermsPage() {
  return (
    <PolicyPage title="Foydalanish shartlari" updatedAt="2026-10-21">
      <section>
        <h2 className="text-xl font-bold text-white">Xizmat doirasi</h2>
        <p>BulDrop do‘kon administratori boshqaradigan raqamli o‘yin mahsulotlari katalogidir. Mahsulotlar faqat huquqiy va provayder talablari tasdiqlanganidan keyin sotuvga chiqarilishi kerak.</p>
      </section>
      <section>
        <h2 className="text-xl font-bold text-white">Buyurtma va narx</h2>
        <p>Buyurtma narxi serverdagi katalog narxidan hisoblanadi. Buyurtma tasdiqlanishidan oldin mahsulot, narx va mavjudlik qayta tekshiriladi. Mijoz yuborgan narx buyurtma summasini o‘zgartirmaydi.</p>
      </section>
      <section>
        <h2 className="text-xl font-bold text-white">Test rejimi va yetkazib berish</h2>
        <p>Hozirda test to‘lovi haqiqiy pul olmaydi, o‘yin hisobiga top-up yubormaydi va tashqi mahsulot yetkazmaydi. Test natijalari alohida simulyatsiya sifatida belgilanadi. Click, Payme, PlayPay va skin yetkazib berish yoqilmagan.</p>
      </section>
      <section>
        <h2 className="text-xl font-bold text-white">Foydalanuvchi javobgarligi</h2>
        <p>Foydalanuvchi taqdim etgan o‘yinchi ID va buyurtma ma’lumotlari to‘g‘ri ekanini tekshirishi lozim. Steam paroli yoki boshqa akkaunt parolini so‘ramang va hech qachon BulDrop orqali yubormang.</p>
      </section>
    </PolicyPage>
  );
}
