# Spesifikasi Teknis & Desain Sistem

**ALUR Logistik (LajuLogistik)** · Versi 1.1.0 · Oktober 2026 · Revisi dari v1.0.0

---

## 1. Ringkasan Sistem

ALUR Logistik adalah sistem manajemen pengiriman dan pelacakan paket berbasis status, dengan penekanan pada pencatatan riwayat status di setiap tahap. Antarmuka dibagi menjadi dua:

- PWA mobile-first untuk Customer dan Kurir.
- Dashboard web desktop untuk Admin.

### 1.1 Tech Stack

| Lapisan | Teknologi |
|---|---|
| Frontend Customer & Kurir | Vue 3, Vite, Tailwind CSS, vite-plugin-pwa |
| Frontend Admin | Vue 3, PrimeVue + Tailwind CSS |
| Backend API | FastAPI (Python 3.11+), SQLAlchemy 2.0 async, Pydantic v2 |
| Database | PostgreSQL 13+ |
| Scheduler | APScheduler (di dalam event loop FastAPI) |
| Autentikasi | OAuth2 + JWT Bearer, Role-Based Access Control (RBAC) |

---

## 2. Pemetaan Kebutuhan Tugas ke Sistem

| Kebutuhan | Implementasi | Catatan |
|---|---|---|
| Customer membuat delivery request (alamat asal-tujuan, detail paket) | `POST /shipments` | Sudah ada |
| Admin menugaskan kurir ke tiap pengiriman | `PUT /admin/shipments/{id}/assign` | Sudah ada |
| Kurir update status: Placed → Picked Up → In Transit → Delivered | `PUT /courier/shipments/{id}/status` | "Placed" = status `PENDING` |
| Halaman tracking untuk customer dengan riwayat lengkap + timestamp | `GET /shipments/{tracking_number}/track` | Sudah ada |
| Riwayat pengiriman customer | `GET /shipments/me` | Baru (belum ada di v1.0.0) |
| Dashboard admin: daftar pengiriman aktif | `GET /admin/shipments` | Baru |
| Dashboard admin: manajemen data kurir | `/admin/couriers` (CRUD) | Baru (hanya ada di matriks, belum ada endpoint) |
| Dashboard admin: grafik ringkasan volume pengiriman | `GET /admin/dashboard/summary` | Baru (belum ada di v1.0.0) |

---

## 3. Peran & Hak Akses (RBAC)

| Modul / Fitur | Customer (PWA) | Courier (PWA) | Admin (Desktop) |
|---|:---:|:---:|:---:|
| Self-registration akun | ✔ | – | – |
| Buat Delivery Request (DR) | ✔ | – | – |
| Lihat riwayat pengiriman sendiri | ✔ | – | – |
| Lihat tracking history paket sendiri | ✔ | – | – |
| Konfirmasi pesanan selesai | ✔ | – | – |
| Lihat daftar tugas yang ditugaskan | – | ✔ | – |
| Update status (Picked Up, In Transit, Delivered) | – | ✔ | – |
| Upload foto bukti pengiriman | – | ✔ | – |
| Lihat semua pengiriman + filter | – | – | ✔ |
| Assign kurir ke DR | – | – | ✔ |
| Reject DR (+ alasan) | – | – | ✔ |
| CRUD akun kurir | – | – | ✔ |
| Lihat grafik ringkasan volume pengiriman | – | – | ✔ |
| Kelola pengaturan sistem | – | – | ✔ |

Halaman tracking publik (berdasarkan nomor resi) dapat diakses tanpa login.

---

## 4. Lifecycle Status Pengiriman

```
PENDING ──┬──► REJECTED (Admin reject + alasan)
          │
          └──► ASSIGNED (Admin assign kurir)
                  │
                  ▼
              PICKED_UP (Kurir)
                  │
                  ▼
              IN_TRANSIT (Kurir)
                  │
                  ▼
              DELIVERED (Kurir + foto bukti)
                  │
                  ├──► COMPLETED (Konfirmasi Customer)
                  └──► COMPLETED (Cron Job otomatis setelah 3 hari)
```

### 4.1 Tabel Transisi yang Diizinkan

| Dari | Ke | Aktor | Syarat |
|---|---|---|---|
| PENDING | ASSIGNED | Admin | `courier_id` valid, role `COURIER`, `is_active = true` |
| PENDING | REJECTED | Admin | `rejection_reason` wajib diisi |
| ASSIGNED | PICKED_UP | Kurir | Hanya kurir yang ditugaskan |
| PICKED_UP | IN_TRANSIT | Kurir | Hanya kurir yang ditugaskan |
| IN_TRANSIT | DELIVERED | Kurir | `proof_image_url` wajib; `delivered_at` diisi |
| DELIVERED | COMPLETED | Customer | Hanya pemilik shipment |
| DELIVERED | COMPLETED | Sistem (cron) | `delivered_at <= NOW() - auto_complete_days` |

Transisi di luar tabel ini ditolak dengan `409 Conflict`. Status tidak boleh dilompati atau mundur.

---

## 5. Aturan Bisnis

### 5.1 Visual Alert di Dashboard Admin

- **Pemicu:** `status = PENDING`.
- **Kondisi:** `NOW() - created_at >= pending_alert_timeout_minutes` (default 30 menit).
- **Efek UI:** baris tabel berlatar merah dan diurutkan ke posisi paling atas.

### 5.2 Auto-Complete (BackgroundTask)

- **Jadwal:** setiap 1 jam (APScheduler).
- **Query:** `status = 'DELIVERED' AND delivered_at <= NOW() - INTERVAL '<auto_complete_days> days'`.
- **Efek:** status menjadi `COMPLETED` dan dicatat di `tracking_histories` dengan `created_by = NULL`.
- **Ketahanan:** wajib ada retry logic bila koneksi database terputus saat eksekusi.
- Nilai interval dibaca dari `system_settings.auto_complete_days`, bukan di-hardcode.

### 5.3 Audit Trail

Setiap perubahan status, termasuk saat DR pertama dibuat (`PENDING`), wajib menambah satu baris di `tracking_histories` dalam transaksi database yang sama dengan update `shipments`.

### 5.4 Format Nomor Resi

`TRX-YYYYMMDD-NNNN`, contoh `TRX-20260925-0001`. Nomor urut (`NNNN`) di-reset setiap hari.

> v1.0.0 menulis `TRX-YYYYMMDDXXXX` pada kamus data tetapi memakai tanda hubung pada contoh; kini diseragamkan.

---

## 6. Model Data

### 6.1 Relasi Antar Tabel

```
users (1) ──< shipments.customer_id (ON DELETE RESTRICT)
users (1) ──< shipments.courier_id (ON DELETE SET NULL)
shipments (1) ──< tracking_histories (ON DELETE CASCADE)
users (1) ──< tracking_histories.created_by (ON DELETE SET NULL)
system_settings (berdiri sendiri)
```

### 6.2 Tabel `users`

| Kolom | Tipe | Constraint | Deskripsi |
|---|---|---|---|
| `id` | BIGSERIAL | PK | Identitas user |
| `name` | VARCHAR(100) | NOT NULL | Nama lengkap |
| `email` | VARCHAR(150) | UNIQUE, NOT NULL | Email untuk login |
| `phone` | VARCHAR(20) | UNIQUE, NOT NULL | Nomor telepon / WhatsApp |
| `password_hash` | VARCHAR(255) | NOT NULL | Hash Bcrypt (cost 12) |
| `role` | ENUM `user_role` | NOT NULL | ADMIN, COURIER, CUSTOMER |
| `is_active` | BOOLEAN | DEFAULT TRUE | Status keaktifan akun |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Waktu registrasi |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Diperbarui otomatis oleh trigger |

### 6.3 Tabel `shipments`

| Kolom | Tipe | Constraint | Deskripsi |
|---|---|---|---|
| `id` | BIGSERIAL | PK | Identitas shipment |
| `tracking_number` | VARCHAR(50) | UNIQUE, NOT NULL | Nomor resi |
| `customer_id` | BIGINT | FK `users.id`, NOT NULL | Pembuat request |
| `courier_id` | BIGINT | FK `users.id`, NULLABLE | Kurir yang ditugaskan |
| `sender_name` / `sender_phone` | VARCHAR(100) / VARCHAR(20) | NOT NULL | Data pengirim |
| `origin_address` | TEXT | NOT NULL | Alamat penjemputan |
| `recipient_name` / `recipient_phone` | VARCHAR(100) / VARCHAR(20) | NOT NULL | Data penerima |
| `destination_address` | TEXT | NOT NULL | Alamat tujuan |
| `package_description` | TEXT | NOT NULL | Deskripsi isi paket |
| `weight_kg` | NUMERIC(6,2) | NOT NULL, CHECK > 0 | Berat paket (kg) |
| `status` | ENUM `shipment_status` | DEFAULT 'PENDING' | Status terkini |
| `rejection_reason` | TEXT | NULLABLE | Alasan jika ditolak |
| `proof_image_url` | VARCHAR(255) | NULLABLE | URL foto bukti |
| `delivered_at` | TIMESTAMPTZ | NULLABLE | Waktu status DELIVERED |
| `created_at` / `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Waktu pengajuan / pembaruan |

### 6.4 Tabel `tracking_histories`

| Kolom | Tipe | Constraint | Deskripsi |
|---|---|---|---|
| `id` | BIGSERIAL | PK | Identitas log |
| `shipment_id` | BIGINT | FK `shipments.id`, NOT NULL | Shipment terkait |
| `status` | ENUM `shipment_status` | NOT NULL | Status pada tahap tersebut |
| `notes` | TEXT | NOT NULL | Keterangan log |
| `created_by` | BIGINT | FK `users.id`, NULLABLE | Aktor; NULL jika sistem/cron |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Waktu log dicatat |

### 6.5 Tabel `system_settings`

| Kolom | Tipe | Constraint | Deskripsi |
|---|---|---|---|
| `key` | VARCHAR(50) | PK | Kunci konfigurasi |
| `value` | VARCHAR(255) | NOT NULL | Nilai konfigurasi |
| `description` | TEXT | NULLABLE | Penjelasan parameter |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Waktu pembaruan |

Nilai awal: `pending_alert_timeout_minutes = 30`, `auto_complete_days = 3`.

### 6.6 Index

| Index | Tujuan |
|---|---|
| `idx_shipments_tracking_number` | Pencarian berdasarkan resi |
| `idx_shipments_customer_id`, `idx_shipments_courier_id` | Daftar paket per customer / kurir |
| `idx_shipments_status` | Filter status di dashboard admin |
| `idx_shipments_pending_alert` (parsial: PENDING) | Deteksi baris merah |
| `idx_shipments_auto_complete` (parsial: DELIVERED) | Query cron auto-complete |
| `idx_tracking_histories_shipment_id` | Riwayat per shipment |

---

## 7. Kontrak REST API

Base URL: `/api/v1`. Semua endpoint selain yang bertanda **Public** memerlukan header `Authorization: Bearer <token>`.

### 7.1 Ringkasan Endpoint

| Modul | Method & Path | Akses | Status |
|---|---|---|---|
| Auth | `POST /auth/register` | Public | Ada |
| Auth | `POST /auth/login` | Public | Ada |
| Shipment | `POST /shipments` | Customer | Ada |
| Shipment | `GET /shipments/me` | Customer | Baru |
| Shipment | `GET /shipments/{tracking_number}/track` | Public | Ada |
| Shipment | `PUT /shipments/{id}/confirm` | Customer | Baru |
| Kurir | `GET /courier/shipments` | Courier | Baru |
| Kurir | `PUT /courier/shipments/{id}/status` | Courier | Ada |
| Upload | `POST /uploads/proof` | Courier | Baru |
| Admin | `GET /admin/shipments` | Admin | Baru |
| Admin | `PUT /admin/shipments/{id}/assign` | Admin | Ada |
| Admin | `PUT /admin/shipments/{id}/reject` | Admin | Ada |
| Admin | `GET /admin/dashboard/summary` | Admin | Baru |
| Admin | `GET /admin/couriers`, `POST`, `PUT /{id}`, `PATCH /{id}/deactivate` | Admin | Baru |
| Admin | `GET /admin/settings`, `PUT /admin/settings` | Admin | PUT ada, GET baru |

### 7.2 Autentikasi

**`POST /auth/register`** — Request:

```json
{ "name": "Eko Customer", "email": "eko@gmail.com", "phone": "081234567892", "password": "Password123!" }
```

Response `201`:

```json
{ "message": "Registrasi berhasil", "user_id": 3 }
```

**`POST /auth/login`** — Request:

```json
{ "email": "admin@alur.com", "password": "Password123!" }
```

Response `200`:

```json
{ "access_token": "eyJhbGciOiJKV1QiLC...", "token_type": "bearer", "role": "ADMIN", "name": "Super Admin" }
```

### 7.3 Shipment (Customer)

**`POST /shipments`** — Request:

```json
{
  "sender_name": "Eko Customer",
  "sender_phone": "081234567892",
  "origin_address": "Jl. Kemang Raya No. 10, Jakarta Selatan",
  "recipient_name": "Budi Santoso",
  "recipient_phone": "089876543210",
  "destination_address": "Jl. Asia Afrika No. 5, Bandung",
  "package_description": "Dokumen Kontrak Kerja",
  "weight_kg": 0.5
}
```

Response `201`:

```json
{ "id": 101, "tracking_number": "TRX-20260925-0001", "status": "PENDING", "created_at": "2026-09-25T10:00:00Z" }
```

**`GET /shipments/me?status=&page=1&limit=20`** — daftar riwayat pengiriman milik customer yang login, terbaru lebih dulu.

**`GET /shipments/{tracking_number}/track`** — Public. Response `200`:

```json
{
  "tracking_number": "TRX-20260925-0001",
  "status": "PICKED_UP",
  "sender_name": "Eko Customer",
  "recipient_name": "Budi Santoso",
  "destination_address": "Jl. Asia Afrika No. 5, Bandung",
  "history": [
    { "status": "PENDING", "notes": "Delivery request berhasil dibuat oleh Customer.", "created_at": "2026-09-25T10:00:00Z" },
    { "status": "ASSIGNED", "notes": "Pesanan disetujui Admin dan ditugaskan ke Kurir Budi.", "created_at": "2026-09-25T10:15:00Z" },
    { "status": "PICKED_UP", "notes": "Paket telah diambil oleh kurir dari lokasi pengirim.", "created_at": "2026-09-25T11:00:00Z" }
  ]
}
```

> **Catatan privasi:** untuk pengakses tanpa login, nama dan alamat sebaiknya disamarkan sebagian (contoh: "Budi S.", alamat hanya kota/kecamatan). Detail lengkap hanya untuk pemilik shipment.

**`PUT /shipments/{id}/confirm`** — Customer pemilik mengonfirmasi paket diterima. Syarat: status `DELIVERED`. Response `200`:

```json
{ "message": "Pesanan dikonfirmasi selesai", "current_status": "COMPLETED" }
```

### 7.4 Aksi Kurir

**`GET /courier/shipments?status=`** — daftar tugas milik kurir yang login.

**`POST /uploads/proof`** — `multipart/form-data` (field `file`, JPG/PNG, maks 5 MB). Response `201`:

```json
{ "url": "https://storage.alur.com/proofs/trx-0001.jpg" }
```

URL ini dipakai pada update status DELIVERED.

**`PUT /courier/shipments/{id}/status`** — Update biasa:

```json
{ "status": "IN_TRANSIT", "notes": "Paket dalam perjalanan via jalur darat" }
```

Saat DELIVERED:

```json
{
  "status": "DELIVERED",
  "notes": "Diterima oleh yang bersangkutan",
  "proof_image_url": "https://storage.alur.com/proofs/trx-0001.jpg"
}
```

Response `200`:

```json
{ "message": "Status berhasil diperbarui", "current_status": "DELIVERED" }
```

### 7.5 Manajemen Admin

**`GET /admin/shipments?status=&courier_id=&date_from=&date_to=&q=&page=&limit=`** — daftar semua pengiriman. Setiap item memuat flag `is_overdue_pending` (true bila memenuhi aturan 5.1). Urutan default: overdue PENDING di atas, lalu `created_at` terbaru.

**`PUT /admin/shipments/{id}/assign`**

```json
{ "courier_id": 2 }
```

→

```json
{ "message": "Kurir berhasil ditugaskan", "shipment_id": 101, "status": "ASSIGNED" }
```

**`PUT /admin/shipments/{id}/reject`**

```json
{ "rejection_reason": "Alamat pengirim tidak terjangkau layanan operasional." }
```

→

```json
{ "message": "Delivery request ditolak", "shipment_id": 101, "status": "REJECTED" }
```

**`GET /admin/dashboard/summary?period=7d|30d|12m`** — Response `200`:

```json
{
  "totals": { "active": 42, "pending": 5, "delivered_today": 12, "completed": 310 },
  "volume_per_day": [ { "date": "2026-09-24", "count": 18 }, { "date": "2026-09-25", "count": 23 } ],
  "by_status": { "PENDING": 5, "ASSIGNED": 8, "PICKED_UP": 6, "IN_TRANSIT": 23, "DELIVERED": 12 }
}
```

**`/admin/couriers`** — `GET` (daftar), `POST` (buat akun kurir: name, email, phone, password), `PUT /{id}` (ubah data), `PATCH /{id}/deactivate` (set `is_active = false`; akun tidak dihapus agar riwayat tetap utuh).

**`PUT /admin/settings`**

```json
{ "pending_alert_timeout_minutes": "45", "auto_complete_days": "3" }
```

→

```json
{ "message": "Pengaturan sistem berhasil disimpan" }
```

### 7.6 Format Error Standar

```json
{ "detail": "Pesan error yang dapat dibaca", "code": "INVALID_STATUS_TRANSITION" }
```

| HTTP | Penggunaan |
|---|---|
| 400 / 422 | Payload tidak valid |
| 401 | Token tidak ada / kedaluwarsa |
| 403 | Role tidak berhak, atau bukan pemilik / kurir yang ditugaskan |
| 404 | Data tidak ditemukan |
| 409 | Transisi status tidak valid |

---

## 8. Rancangan Antarmuka

### 8.1 PWA Customer

| Halaman | Isi utama |
|---|---|
| Login / Registrasi | Form autentikasi |
| Beranda | Ringkasan paket aktif, tombol Buat Pengiriman, kolom cari resi |
| Buat Delivery Request | Form pengirim, penerima, alamat, deskripsi, berat |
| Riwayat Pengiriman | Daftar paket + filter status |
| Detail & Tracking | Timeline status vertikal dengan timestamp, tombol Konfirmasi Selesai saat DELIVERED |

### 8.2 PWA Kurir

| Halaman | Isi utama |
|---|---|
| Daftar Tugas | Paket ASSIGNED / PICKED_UP / IN_TRANSIT milik kurir |
| Detail Tugas | Alamat jemput & tujuan, kontak, tombol aksi status berikutnya |
| Bukti Pengiriman | Ambil foto dengan kamera, unggah, lalu tandai DELIVERED |

### 8.3 Dashboard Admin (Desktop)

| Halaman | Isi utama |
|---|---|
| Ringkasan | Kartu total + grafik volume pengiriman per hari + distribusi status |
| Daftar Pengiriman | Tabel semua pengiriman, filter, baris merah untuk PENDING terlambat, aksi Assign / Reject |
| Manajemen Kurir | Tabel kurir, tambah / ubah / nonaktifkan |
| Pengaturan Sistem | Form timeout alert dan hari auto-complete |

### 8.4 Warna Badge Status

| Status | Warna | Arti |
|---|---|---|
| PENDING | Kuning | Menunggu Admin |
| REJECTED | Merah | Ditolak |
| ASSIGNED | Biru | Kurir ditugaskan |
| PICKED_UP | Indigo | Paket diambil |
| IN_TRANSIT | Ungu | Dalam perjalanan |
| DELIVERED | Hijau muda | Telah sampai |
| COMPLETED | Hijau tua | Selesai |

Baris merah pada tabel admin (alert PENDING terlambat) dibuat berbeda dari badge REJECTED, misalnya dengan latar baris merah muda penuh dan ikon peringatan, agar tidak membingungkan.

---

## 9. Persyaratan Non-Fungsional

| Aspek | Persyaratan |
|---|---|
| Performa | Respons REST API standar ≤ 200 ms pada beban normal |
| PWA | Dapat di-install (Add to Home Screen), mendukung Web Push untuk update status, kamera native untuk foto bukti |
| Keamanan | HTTPS/TLS 1.3, Bcrypt cost 12, JWT Bearer berumur 24 jam, validasi RBAC di setiap endpoint |
| Ketersediaan scheduler | Retry logic bila koneksi database terputus saat auto-complete |
| Integritas data | Update `shipments` dan insert `tracking_histories` dalam satu transaksi |

