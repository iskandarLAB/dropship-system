# Elrah Exclusive - HQ Dropship & Affiliate Management System

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2%20LTS-green.svg)](https://www.djangoproject.com/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-purple.svg)](https://getbootstrap.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

Sistem pengurusan dropship & affiliate busana moden berprestasi tinggi berjenama **Elrah Exclusive** ([elrahexclusive.my](https://elrahexclusive.my)). Dibina khas untuk menyelesaikan masalah pengurusan stok gudang harian, aliran tunai FPX tanpa risiko penipuan resit, serta pembayaran komisen mingguan secara automatik ke akaun bank ejen.

---

## 🌟 Ciri-Ciri Utama

### 1. Model Pemasaran Affiliate (Zero-Capital)
- **Kedai Affiliate Peribadi**: Setiap ejen mempunyai pautan butik sendiri (`/shop/<username>/`).
- **Pembayaran Terus ke HQ**: Pelanggan membayar harga runcit pakaian + pos terus ke akaun syarikat melalui **CHIP Collect (FPX)**.
- **Komisen 15% Automatik**: Komisen 15% dikira dan dikreditkan secara automatik setiap kali pesanan berjaya dibayar.

### 2. Pembayaran Komisen Mingguan (CHIP Send API)
- Ejen mendaftar nombor akaun bank tempatan (Maybank, CIMB, Bank Islam, dll.) di portal.
- Admin menyemak lejar baki komisen terkumpul di `/admin-panel/payouts/`.
- Pindahan dana secara pukal (*batch disbursement*) terus ke akaun bank ejen menggunakan **CHIP Send API** dengan pengesahan HMAC-SHA512 checksum.

### 3. Pengurusan Stok Gudang 24 Jam (HQ Stock Audit)
- **Bulk Edit Grid (`/hq/stock/`)**: Pihak gudang mengemas kini baki fizikal semua saiz (S-XXL) dan warna dalam satu skrin pantas.
- **24-Hour Freshness Alert**: Notifikasi automatik jika stok belum disemak dalam tempoh 24 jam.
- **Audit Log (`StockLog`)**: Rekod kekal setiap pergerakan stok keluar masuk berserta sebab (*HQ_UPDATE*, *ORDER*, *RESTORE*).

### 4. Pusat Pengeposan Gudang & Slip Pembungkusan
- Barisan giliran pesanan berbayar (`/orders/hq/`).
- Penetapan syarikat kurier (J&T Express, Pos Laju, Ninja Van) & nombor penjejakan (*tracking*).
- Cetakan rasmi **Packing Slip** berjenama Elrah Exclusive Fulfillment Hub.

### 5. Papan Pendahulu Jualan (Leaderboard)
- Kedudukan Top 10 dropshipper jualan tertinggi (*Bulan Ini* & *Sepanjang Masa*).
- Kad motivasi pintar yang mengira jurang jualan untuk memintas pesaing di atasnya.

---

## 🏗️ Struktur Aplikasi (Architecture)

```text
dropship/
├── accounts/    # Pengurusan pengguna, peranan (HQ/Admin/Dropshipper), KYC bank
├── catalog/     # Produk Elrah (Daytona, Modern Fit, Kurta), varian, stok, rate pos
├── orders/      # Tempahan pelanggan, tempahan stok, status fulfillment, packing slip
├── payments/    # Integrasi CHIP Collect FPX & offline simulator
├── payouts/     # Lejar komisen 15%, batching, integrasi CHIP Send disbursements
├── dashboard/   # Dashboard analitik Chart.js, KPI jualan & papan pendahulu
├── templates/   # UI Bootstrap 5 responsif bertemakan kemewahan hitam & emas
├── config/      # Konfigurasi Django & routing URLs
└── manage.py
```

---

## 🚀 Panduan Pemasangan Tempatan (Local Setup)

### 1. Klon Repositori & Sediakan Virtual Environment
```bash
git clone <repo-url>
cd dropship

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Tetapan Environment Variables (`.env`)
Salin templat fail konfigurasi:
```bash
cp .env.example .env
```

Sunting `.env` mengikut persekitaran anda:
```env
SECRET_KEY=your-secret-key-here
DEBUG=1
ALLOWED_HOSTS=localhost,127.0.0.1

# Payment Gateway
PAYMENT_GATEWAY=dummy
CHIP_SEND_SIMULATOR=1
```

### 3. Migrasi Pangkalan Data & Cipta Data Demo
```bash
python manage.py migrate
python manage.py seed_demo
```

### 4. Jalankan Pelayan Pembangunan
```bash
python manage.py runserver 127.0.0.1:8000
```

Lawati `http://127.0.0.1:8000/` di pelayar web anda.

---

## 🔑 Akaun Demo Sedia Ada (Kata Laluan: `password123`)

| Username | Peranan | Akses Utama |
|---|---|---|
| `admin` | Admin HQ | `/admin-panel/`, `/admin-panel/payouts/`, `/admin/` |
| `hq` | Pengurus Gudang | `/hq/`, `/hq/stock/`, `/orders/hq/` |
| `dropship1` | Ejen Affiliate | `/dashboard/`, `/shop/dropship1/`, `/payouts/` |
| `pending1` | Pemohon Baharu | Menunggu kelulusan Admin |

---

## 🧪 Menjalankan Ujian Automasi (Test Suite)

```bash
python manage.py test
```
*(Kesemua 23 unit & integration tests disahkan lulus)*

---

## 📄 Lesen
Hak Cipta Terpelihara © Elrah Exclusive HQ.
