# SmartHelp — IT xizmat va texnik murojaatlarni boshqarish

SmartHelp — universitet yoki tashkilotdagi kompyuter, printer, tarmoq va dasturiy ta'minot muammolarini ro'yxatga olish, mas'ulga biriktirish va hal etilishini kuzatish uchun o'quv veb-ilovasi.

## Funksiyalar

- Ro'yxatdan o'tish va tizimga kirish (parollar hash ko'rinishida saqlanadi)
- Rollar: foydalanuvchi, IT mutaxassisi, administrator
- Murojaat yaratish, qidirish va filtrlash
- Ta'sir va jiddiylik ballari orqali ustuvorlikni hisoblash
- Murojaatni mutaxassisga biriktirish, holat va yechimni yangilash
- O'zgarishlar tarixi
- Qurilmalar inventari
- Dashboard statistikasi
- SQLite bilan tez ishga tushirish, PostgreSQL uchun konfiguratsiya imkoniyati

## Talablar

- Python 3.10 yoki undan yangi
- VS Code tavsiya etiladi
- PostgreSQL faqat PostgreSQL rejimida kerak

## Windows'da ishga tushirish (PowerShell)

Loyiha papkasini VS Code'da ochib, Terminal → New Terminal ni tanlang.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
flask --app app init-db
python app.py
```

Agar PowerShell virtual muhitni faollashtirishga ruxsat bermasa, shu terminal oynasida:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Brauzerda `http://127.0.0.1:5000` ni oching.

## Demo hisoblar

Baza `flask --app app init-db` bilan birinchi marta tayyorlanganda quyidagi demo hisoblar yaratiladi:

| Rol | Email | Standart demo parol |
|---|---|---|
| Administrator | `admin@smarthelp.local` | `Admin123!` |
| IT mutaxassisi | `tech@smarthelp.local` | `Tech12345!` |
| Foydalanuvchi | `user@smarthelp.local` | `User12345!` |

Bu faqat mahalliy namoyish uchun. Haqiqiy foydalanishdan oldin `.env` ichidagi parollar va `SECRET_KEY` ni o'zgartiring. Demo hisoblar mavjud bo'lsa, init-db ularning parolini qayta o'zgartirmaydi.

## PostgreSQL'ga ulash

1. PostgreSQL'da `smarthelp` nomli baza yarating.
2. `.env` faylini oching va `DATABASE_URL` qatorini qo'shing. Misol:

```dotenv
DATABASE_URL=postgresql+psycopg://smarthelp_user:YOUR_PASSWORD@localhost:5432/smarthelp
SECRET_KEY=change-this-to-a-long-random-secret
FLASK_DEBUG=1
```

`smarthelp_user` va `YOUR_PASSWORD` o'rniga o'zingiz yaratgan PostgreSQL foydalanuvchisi va parolini kiriting. Bu foydalanuvchiga bazada jadval yaratish huquqi kerak.

3. Ishga tushiring:

```powershell
flask --app app init-db
python app.py
```

Standart holatda loyiha SQLite'dan foydalanadi, shuning uchun PostgreSQL sozlanmagan bo'lsa ham dastur sinab ko'rilishi mumkin. SQLite bazasi `instance/smarthelp.db` ichida yaratiladi.

## Asosiy sahifalar

- `/` — kirish sahifasi
- `/register` — ro'yxatdan o'tish
- `/login` — tizimga kirish
- `/dashboard` — statistika
- `/tickets` — murojaatlar
- `/tickets/new` — murojaat yaratish
- `/devices` — qurilmalar
- `/admin/users` — rollarni boshqarish (administrator)
- `/api/health` — server holati JSON

## To'rtta fan bilan bog'lanishi

1. **FrontEnd da ilovalar yaratish:** HTML, CSS, JavaScript, responsiv dizayn, formalar, jadvallar, filtrlar.
2. **Dasturiy injeneringga kirish:** rollar, modullar, talablar, README, sinov ssenariylari, arxitektura.
3. **Algoritmlarni loyihalash:** `calculate_priority()` funksiyasi, ball berish qoidasi, saralash va qidirish.
4. **Kompyuter qurilmalari va tarmoqlariga xizmat ko'rsatish:** qurilmalar inventari, muammolar kategoriyalari, diagnostika tavsiyalari va xizmat tarixi.

## Muhim eslatmalar

Bu semestr uchun o'quv prototipi. Internetga ochiq ishlab chiqarish muhitiga joylashdan oldin CSRF himoyasi, login urinishlari chegarasi, audit, ma'lumotlarni zaxiralash, konfiguratsiya va xavfsizlik tekshiruvi qo'shilishi kerak. `debug=True` bilan production'da ishlatmang.
