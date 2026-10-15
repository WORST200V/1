# SmartHelp — Texnik topshiriq (qisqa ТЗ)

## 1. Umumiy ma'lumot
Nomi: SmartHelp. Turi: brauzerda ishlaydigan mijoz-server veb-ilova. Maqsad: tashkilot ichidagi texnik murojaatlarni ro'yxatga olish va bajarilishini kuzatish.

## 2. Foydalanuvchi rollari
- Foydalanuvchi: murojaat yaratish, o'z murojaatlari va holatini ko'rish.
- IT mutaxassisi: tegishli murojaatlarni ko'rish, statusni yangilash, yechim kiritish.
- Administrator: qurilmalar va foydalanuvchi rollarini boshqarish.

## 3. Funksional talablar
- FR-01: foydalanuvchi ro'yxatdan o'tishi va tizimga kirishi.
- FR-02: tizim foydalanuvchining rolini tekshirishi.
- FR-03: murojaat sarlavha, tavsif, kategoriya va ta'sir/jiddiylik qiymatlari bilan yaratilishi.
- FR-04: ustuvorlik ballar asosida avtomatik hisoblanishi.
- FR-05: murojaatga qurilma va mutaxassis biriktirilishi mumkin.
- FR-06: murojaat holatlari tarixda saqlanishi.
- FR-07: murojaatlar qidirilishi va holat/kategoriya bo'yicha filtrlanishi.
- FR-08: qurilmalar inventar ro'yxatida saqlanishi.
- FR-09: dashboard asosiy sonli ko'rsatkichlarni ko'rsatishi.

## 4. Nofunksional talablar
- NFR-01: interfeys desktop va mobil o'lchamlarga moslashishi.
- NFR-02: parollar ochiq matnda saqlanmasligi.
- NFR-03: foydalanuvchi boshqa oddiy foydalanuvchining murojaatini ko'ra olmasligi.
- NFR-04: ma'lumotlar relyatsion bazada saqlanishi.
- NFR-05: asosiy jarayonlar qo'lda test ssenariylari bilan tekshirilishi.

## 5. Ustuvorlik algoritmi
score = impact + severity.
- score >= 5: Yuqori.
- score = 4: O'rta.
- aks holda: Past.

## 6. Qabul qilish mezonlari
- Yangi foydalanuvchi ro'yxatdan o'ta oladi.
- Foydalanuvchi murojaat yaratib, o'z murojaatini ko'ra oladi.
- IT mutaxassisi murojaat statusini o'zgartira oladi.
- Administrator qurilma qo'sha va foydalanuvchi rolini o'zgartira oladi.
- Dashboard va qidiruv/filtrlar ishlaydi.
- /api/health `status: ok` JSON javobini beradi.
