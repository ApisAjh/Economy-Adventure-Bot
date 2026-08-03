# 🎮 Economy Adventure Bot

Game ekonomi multiplayer Telegram — ringan, cepat, dan menyenangkan.
Dibangun dengan **Python 3.12**, **python-telegram-bot v22+**, **FastAPI**, **SQLAlchemy Async (asyncpg)**,
berjalan sepenuhnya via **Webhook** di atas **Vercel Serverless**, dengan database **PostgreSQL (Supabase)**.

> ⚠️ Bot ini TIDAK menggunakan polling sama sekali, dan TIDAK menggunakan Supabase SDK.
> Koneksi ke database Supabase murni melalui `DATABASE_URL` (PostgreSQL connection string).

---

## 📁 Struktur Project

```
api/
    webhook.py          # Entry point FastAPI + webhook Telegram (untuk Vercel)
database/
    database.py         # Koneksi & session SQLAlchemy Async
    models.py            # Semua model tabel (User, Inventory, Pet, dst)
    migrations.py         # Script pembuatan tabel
handlers/
    start.py, work.py, daily.py, profile.py, shop.py, inventory.py,
    bank.py, market.py, farming.py, fishing.py, mining.py, pet.py,
    duel.py, ranking.py, achievement.py, event.py, admin.py
utils/
    economy.py, items.py, cooldown.py, security.py, logger.py
config/
    settings.py          # Loader environment variables
requirements.txt
vercel.json
README.md
.env.example
```

---

## 🚀 1. Instalasi Lokal

```bash
git clone <repo-anda>
cd economy_adventure_bot

python3.12 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Salin file environment:

```bash
cp .env.example .env
```

Isi `.env` sesuai kebutuhan (lihat bagian **Environment Variables** di bawah).

---

## 🐘 2. Membuat PostgreSQL di Supabase

1. Buka [https://supabase.com](https://supabase.com) dan login/daftar.
2. Klik **New Project**, isi nama project, password database, dan pilih region terdekat.
3. Tunggu hingga project selesai di-provision (biasanya 1-2 menit).
4. Masuk ke menu **Project Settings → Database**.
5. Cari bagian **Connection string → URI**. Salin URL dengan format:

```
postgresql://postgres:[YOUR-PASSWORD]@[HOST]:5432/postgres
```

6. Ganti `[YOUR-PASSWORD]` dengan password database yang kamu buat di langkah 2.

> 💡 Tips: Gunakan mode **Connection Pooling (Transaction mode / port 6543)** dari Supabase
> jika ingin koneksi lebih stabil di lingkungan serverless seperti Vercel. Salin URL versi pooling
> tersebut sebagai `DATABASE_URL`.

Bot ini **tidak** memakai Supabase SDK — hanya menyambung ke Postgres murni via SQLAlchemy + asyncpg.

---

## 🔑 3. Mendapatkan ADMIN_ID (Telegram User ID)

1. Buka Telegram, cari bot **@userinfobot** atau **@RawDataBot**.
2. Kirim pesan apa saja ke bot tersebut.
3. Bot akan membalas dengan `id` milikmu — itulah `ADMIN_ID` kamu.

---

## ⚙️ 4. Environment Variables

Isi file `.env` (atau Environment Variables di dashboard Vercel):

```env
BOT_TOKEN=isi_token_dari_botfather

WEBHOOK_URL=https://nama-project-anda.vercel.app

ADMIN_ID=123456789

DATABASE_URL=postgresql://postgres:password@host:5432/postgres

BOT_VERSION=1.0.0
```

| Variabel      | Keterangan                                                        |
|---------------|--------------------------------------------------------------------|
| `BOT_TOKEN`   | Token bot dari [@BotFather](https://t.me/BotFather)                |
| `WEBHOOK_URL` | URL hasil deploy Vercel (tanpa trailing slash)                     |
| `ADMIN_ID`    | Telegram User ID pemilik/admin bot                                 |
| `DATABASE_URL`| Connection string PostgreSQL dari Supabase                         |
| `BOT_VERSION` | Versi bot, ditampilkan di statistik admin                          |

---

## 🗄️ 5. Migrasi Database

Setelah `.env` terisi (khususnya `DATABASE_URL`), jalankan migrasi untuk membuat semua tabel:

```bash
python -m database.migrations
```

Script ini akan membuat tabel: `users`, `inventory`, `pets`, `bank_transactions`,
`market`, `cooldown`, `farming`, `achievements`, `events` — otomatis, jika belum ada.

> Jalankan ulang perintah ini kapan pun kamu menambah model baru di `database/models.py`.

---

## ☁️ 6. Deploy ke Vercel

1. Install Vercel CLI (opsional, bisa juga lewat dashboard web):

```bash
npm install -g vercel
```

2. Login dan deploy:

```bash
vercel login
vercel --prod
```

3. Di dashboard Vercel, buka **Project → Settings → Environment Variables**, lalu masukkan
   semua variabel dari `.env.example` (`BOT_TOKEN`, `WEBHOOK_URL`, `ADMIN_ID`, `DATABASE_URL`, `BOT_VERSION`).

4. Setelah deploy sukses, `WEBHOOK_URL` kamu adalah domain yang diberikan Vercel, contoh:
   `https://economy-adventure-bot.vercel.app`

5. Redeploy sekali lagi setelah environment variables diisi agar terbaca oleh aplikasi:

```bash
vercel --prod
```

---

## 🔗 7. Set Webhook Telegram

Setelah bot live di Vercel, daftarkan webhook ke Telegram Bot API dengan memanggil URL berikut
di browser atau menggunakan `curl`:

```bash
curl -F "url=https://nama-project-anda.vercel.app/api/webhook" \
     https://api.telegram.org/bot<BOT_TOKEN>/setWebhook
```

Jika berhasil, responsnya:

```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

Untuk mengecek status webhook:

```bash
curl https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo
```

Untuk menghapus webhook (misalnya sebelum testing lokal dengan polling manual):

```bash
curl https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook
```

---

## 🕹️ 8. Daftar Command

| Command             | Keterangan                                            |
|---------------------|--------------------------------------------------------|
| `/start`             | Membuat akun & menampilkan menu utama                 |
| `/profile`           | Melihat profil lengkap                                 |
| `/work`              | Bekerja untuk coin & xp (cooldown 10 menit)             |
| `/daily`             | Klaim reward harian (cooldown 24 jam)                   |
| `/shop`              | Membuka toko item                                       |
| `/inventory`         | Melihat semua barang                                     |
| `/deposit <jumlah>`  | Menabung coin ke bank                                    |
| `/withdraw <jumlah>` | Menarik coin dari bank                                   |
| `/bank`              | Melihat saldo & riwayat transaksi bank                    |
| `/market`            | Melihat listing marketplace antar pemain                  |
| `/market sell <item> <qty> <harga>` | Menjual item ke marketplace           |
| `/market buy <id>`   | Membeli listing marketplace                                |
| `/market cancel <id>`| Membatalkan listing milik sendiri                          |
| `/farm plant <tanaman>` | Menanam (Jagung/Gandum/Padi)                            |
| `/farm harvest`      | Memanen tanaman yang sudah siap                             |
| `/farm status`       | Melihat status tanaman aktif                                |
| `/fish`              | Memancing ikan (butuh 🎣 Pancing)                            |
| `/mine`              | Menambang (butuh ⛏ Pickaxe)                                  |
| `/pet`               | Melihat pet yang dimiliki                                     |
| `/pet train <id>`    | Melatih pet agar naik level                                    |
| `/duel`              | Balas pesan pemain lain dengan command ini untuk PvP             |
| `/ranking`           | Top 10 pemain terkaya                                            |
| `/achievement`       | Melihat progress achievement                                      |
| `/event`             | Melihat event yang sedang aktif                                    |
| `/admin`             | Panel admin (hanya untuk `ADMIN_ID`)                                |

---

## 🛠️ 9. Fitur Admin

Akses `/admin` (hanya `ADMIN_ID`) untuk membuka panel dengan tombol:

- 📊 Statistik Bot (total user, user aktif hari ini, total coin beredar, dll)
- 👥 Total User
- 💰 Tambah Coin / 💸 Kurangi Coin
- 🎁 Berikan Item
- 🚫 Ban User / ✅ Unban User
- 📢 Broadcast pesan ke semua user
- 🎉 Aktifkan Event (dengan multiplier & durasi)
- ⏸ Maintenance Mode ON/OFF
- 🔄 Reset Cooldown user tertentu
- 🗑 Hapus Akun (permanen)
- 📦 Backup Database (dikirim sebagai file `.json`)

Setelah menekan tombol yang membutuhkan input (misalnya Tambah Coin), admin cukup
mengirim pesan teks sesuai format yang diminta bot. Ketik `/cancel` untuk membatalkan.

---

## 💾 10. Cara Backup & Migrasi Database

**Backup** — gunakan tombol **📦 Backup Database** di `/admin`. Bot akan mengirim file
`.json` berisi seluruh data dari tabel utama (users, inventory, pets, transaksi, market,
farming, achievements, events) langsung ke chat admin.

**Migrasi** — jalankan ulang:

```bash
python -m database.migrations
```

Perintah ini bersifat idempotent (aman dijalankan berkali-kali), hanya membuat tabel yang
belum ada tanpa menghapus data yang sudah ada.

---

## 🔒 11. Keamanan

- Semua command memiliki cooldown untuk mencegah spam.
- Validasi input di setiap handler (jumlah harus positif, item harus valid, dll).
- Coin tidak pernah bisa menjadi negatif.
- Item di inventory otomatis terakumulasi (tidak membuat duplikasi entri).
- Query database 100% menggunakan SQLAlchemy ORM (parameterized), sehingga terlindungi dari SQL Injection.
- Semua exception ditangani oleh error handler global dan dicatat lewat logger.
- Admin panel hanya bisa diakses oleh `ADMIN_ID`.

---

## 🧱 12. Teknologi yang Digunakan

- Python 3.12
- python-telegram-bot v22+
- FastAPI (webhook endpoint)
- SQLAlchemy Async + asyncpg
- PostgreSQL (hosting: Supabase, tanpa Supabase SDK)
- python-dotenv
- Vercel Serverless Functions

---

## 📌 Catatan

- Maintenance Mode disimpan di memori proses (`bot_data`) — cocok untuk penggunaan
  jangka pendek. Untuk kebutuhan produksi skala besar, pertimbangkan menyimpan flag
  ini di tabel database agar konsisten di semua instance serverless.
- Project ini dirancang modular sehingga mudah dikembangkan lebih lanjut — misalnya
  menambahkan clan/guild, quest harian, atau sistem crafting.
