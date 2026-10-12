# Aturan Pengembangan Backend: ALUR Logistik (LajuLogistik)

Versi 1.1.0 · Acuan: Spesifikasi Teknis v1.1.0 dan `database-logistic.sql`

Stack: FastAPI (Python 3.11+), SQLAlchemy 2.0 async, Pydantic v2, PostgreSQL 13+, APScheduler.

---

## 1. Struktur Proyek

```
app/
├── main.py                 # inisialisasi FastAPI, router, lifespan (start/stop scheduler)
├── core/
│   ├── config.py           # settings dari environment (pydantic-settings)
│   ├── security.py         # hash Bcrypt, buat/verifikasi JWT
│   └── deps.py             # dependency: get_db, get_current_user, require_role
├── db/
│   ├── session.py          # async engine + sessionmaker
│   └── models/             # user.py, shipment.py, tracking_history.py, system_setting.py
├── schemas/                # Pydantic request/response per modul
├── routers/                # auth.py, shipments.py, courier.py, admin.py, uploads.py
├── services/               # logika bisnis (shipment_service.py, dashboard_service.py, ...)
├── repositories/           # query database (opsional, jika service mulai gemuk)
├── jobs/
│   └── auto_complete.py    # job APScheduler
└── tests/
```

Pemisahan tanggung jawab:

- **Router**: hanya menerima request, validasi lewat schema, memanggil service, mengembalikan response. Tidak ada logika bisnis dan tidak ada query langsung.
- **Service**: seluruh aturan bisnis (transisi status, pengecekan kepemilikan, pembuatan resi).
- **Model**: definisi tabel saja.

---

## 2. Konvensi Umum

1. Semua fungsi akses database memakai `async/await`. Dilarang memakai driver atau call yang blocking di dalam event loop.
2. Satu request = satu `AsyncSession` (lewat dependency `get_db`). Commit dilakukan di service, bukan di router.
3. Semua waktu disimpan sebagai `TIMESTAMPTZ` (UTC) dan dikirim ke klien dalam format ISO 8601 dengan akhiran `Z`.
4. Semua endpoint berada di bawah prefix `/api/v1`.
5. Nama field JSON memakai `snake_case`, sama persis dengan nama kolom pada kontrak API.
6. Gunakan type hint pada semua fungsi. Format kode dengan `ruff` dan `black`.
7. Dilarang meng-hardcode nilai konfigurasi (secret, URL, interval). Ambil dari environment atau tabel `system_settings`.

---

## 3. Autentikasi & Otorisasi

### 3.1 Autentikasi

- Password di-hash dengan **Bcrypt cost factor 12**. Password asli tidak boleh pernah disimpan atau dicatat di log.
- Login memakai email dan password. Respons berisi `access_token`, `token_type`, `role`, dan `name`.
- JWT berisi minimal `sub` (user id), `role`, dan `exp`. Masa berlaku **24 jam**.
- Akun dengan `is_active = false` ditolak saat login dan pada setiap request ber-token (`401`).
- Registrasi publik **hanya** membuat user dengan role `CUSTOMER`. Role tidak boleh diterima dari payload.
- Akun `COURIER` hanya dibuat oleh Admin. Akun `ADMIN` dibuat lewat seed atau skrip internal.

### 3.2 RBAC

Gunakan dependency `require_role(...)` pada setiap router, bukan pengecekan manual di tiap fungsi.

| Prefix / endpoint | Role yang diizinkan |
|---|---|
| `/auth/register`, `/auth/login` | Public |
| `GET /shipments/{tracking_number}/track` | Public |
| `POST /shipments`, `GET /shipments/me`, `PUT /shipments/{id}/confirm` | CUSTOMER |
| `/courier/*`, `POST /uploads/proof` | COURIER |
| `/admin/*` | ADMIN |

Aturan kepemilikan (selain cek role):

- Customer hanya boleh mengakses shipment dengan `customer_id` miliknya (`403` jika bukan).
- Kurir hanya boleh mengubah shipment dengan `courier_id` miliknya (`403` jika bukan).

---

## 4. Aturan Status Pengiriman (State Machine)

Seluruh perubahan status **wajib** lewat satu fungsi pusat di service (contoh: `change_status(...)`). Dilarang meng-update kolom `status` dari tempat lain.

### 4.1 Transisi yang diizinkan

| Dari | Ke | Aktor | Syarat |
|---|---|---|---|
| PENDING | ASSIGNED | Admin | `courier_id` ada, role COURIER, `is_active = true` |
| PENDING | REJECTED | Admin | `rejection_reason` wajib dan tidak kosong |
| ASSIGNED | PICKED_UP | Kurir | Kurir yang ditugaskan |
| PICKED_UP | IN_TRANSIT | Kurir | Kurir yang ditugaskan |
| IN_TRANSIT | DELIVERED | Kurir | `proof_image_url` wajib, `delivered_at` diisi `NOW()` |
| DELIVERED | COMPLETED | Customer | Pemilik shipment |
| DELIVERED | COMPLETED | Sistem (cron) | `delivered_at <= NOW() - auto_complete_days` |

- Transisi di luar tabel ini ditolak dengan `409 Conflict` (`code: INVALID_STATUS_TRANSITION`).
- Status tidak boleh dilompati atau mundur.
- Customer **tidak** dapat membatalkan DR. Pembatalan hanya dilakukan Admin melalui endpoint reject (status PENDING).
- Tidak ada batas jumlah tugas aktif per kurir.

### 4.2 Audit trail

- Setiap perubahan status, termasuk pembuatan DR pertama (`PENDING`), menambah satu baris di `tracking_histories`.
- Update `shipments` dan insert `tracking_histories` terjadi dalam **satu transaksi**. Jika salah satu gagal, keduanya di-rollback.
- `created_by` diisi id aktor. Untuk perubahan oleh cron, `created_by = NULL`.
- Kolom `notes` wajib diisi. Jika klien tidak mengirim catatan, service membuat catatan default yang bermakna (contoh: "Paket telah diambil oleh kurir dari lokasi pengirim.").
- Riwayat bersifat append-only: tidak ada endpoint untuk mengubah atau menghapus `tracking_histories`.

---

## 5. Nomor Resi

- Format: `TRX-YYYYMMDD-NNNN`, contoh `TRX-20260925-0001`.
- `NNNN` adalah nomor urut harian, di-reset setiap hari (zona waktu bisnis disepakati satu, contoh WIB).
- Pembuatan nomor harus aman terhadap request bersamaan (concurrent). Gunakan lock atau sequence per hari, dan tangani bentrok `UNIQUE` dengan retry.

---

## 6. Aturan Validasi Input

| Field | Aturan |
|---|---|
| `email` | Format email valid, unik |
| `phone` | Hanya angka (boleh diawali `+`), 8-20 karakter, unik pada `users` |
| `password` | Minimal 8 karakter, memuat huruf dan angka |
| `weight_kg` | Lebih dari 0, maksimal sesuai `NUMERIC(6,2)` |
| `origin_address`, `destination_address`, `package_description` | Tidak boleh kosong, di-trim |
| `rejection_reason` | Tidak boleh kosong |
| `proof_image_url` | Wajib saat DELIVERED, URL dari hasil `POST /uploads/proof` |
| Pengaturan sistem | `pending_alert_timeout_minutes` dan `auto_complete_days` berupa integer positif |

Validasi dilakukan di schema Pydantic. Aturan yang butuh data (keunikan, kepemilikan, status) dilakukan di service.

---

## 7. Aturan per Modul

### 7.1 Shipments (Customer)

- `POST /shipments` membuat shipment `PENDING` + riwayat awal, mengembalikan `id`, `tracking_number`, `status`, `created_at`.
- `GET /shipments/me` mendukung filter `status` dan paginasi (`page`, `limit`), urut `created_at` terbaru.
- `GET /shipments/{tracking_number}/track` bersifat publik dan menampilkan data sesuai kontrak (tanpa penyamaran). Riwayat diurutkan dari yang terlama.
- `PUT /shipments/{id}/confirm` hanya untuk pemilik dan hanya saat status `DELIVERED`.

### 7.2 Kurir

- `GET /courier/shipments` hanya mengembalikan shipment dengan `courier_id` kurir yang login.
- `POST /uploads/proof`: terima `multipart/form-data`, hanya JPG/PNG, maksimal 5 MB. Validasi tipe berdasarkan isi file, bukan hanya ekstensi. Nama file di-generate server (dilarang memakai nama asli dari klien).

### 7.3 Admin

- `GET /admin/shipments` mendukung filter `status`, `courier_id`, `date_from`, `date_to`, `q` (resi/nama), dan paginasi.
- Setiap item memuat `is_overdue_pending` (lihat bagian 8). Urutan default: PENDING terlambat di paling atas, lalu `created_at` terbaru.
- `GET /admin/dashboard/summary` mengembalikan `totals`, `volume_per_day`, dan `by_status` untuk periode `7d`, `30d`, atau `12m`. Hari tanpa data tetap dikembalikan dengan `count: 0` agar grafik tidak bolong.
- CRUD kurir: `POST` membuat user role COURIER. Penghapusan dilakukan dengan **nonaktifkan** (`is_active = false`), bukan `DELETE`, agar riwayat tetap utuh.
- Admin tidak dapat menugaskan kurir yang nonaktif.

---

## 8. Aturan Bisnis Otomatis

### 8.1 Visual alert (PENDING terlambat)

`is_overdue_pending = status == 'PENDING' AND NOW() - created_at >= pending_alert_timeout_minutes`

Nilai timeout dibaca dari `system_settings` (default 30). Perhitungan dilakukan di backend agar konsisten, frontend hanya menampilkan.

### 8.2 Auto-complete (APScheduler)

- Dijalankan di dalam event loop FastAPI, dimulai dan dihentikan pada lifespan aplikasi.
- Interval: setiap 1 jam.
- Query: `status = 'DELIVERED' AND delivered_at <= NOW() - INTERVAL '<auto_complete_days> days'`, dengan `auto_complete_days` dari `system_settings`.
- Setiap shipment yang diubah mendapat riwayat `COMPLETED` dengan `created_by = NULL` dalam transaksi yang sama.
- **Retry logic**: jika koneksi database terputus, ulangi dengan backoff (contoh: 3 kali, jeda 5 s, 15 s, 45 s). Gagal total dicatat sebagai error di log dan job berjalan lagi pada jadwal berikutnya.
- Job harus idempotent: menjalankannya dua kali tidak boleh menghasilkan riwayat ganda.

---

## 9. Format Error

Semua error memakai format:

```json
{ "detail": "Pesan yang dapat dibaca", "code": "KODE_ERROR" }
```

| HTTP | Penggunaan | Contoh `code` |
|---|---|---|
| 400 / 422 | Payload tidak valid | `VALIDATION_ERROR` |
| 401 | Token tidak ada, kedaluwarsa, atau akun nonaktif | `UNAUTHORIZED` |
| 403 | Role tidak berhak, atau bukan pemilik / kurir yang ditugaskan | `FORBIDDEN` |
| 404 | Data tidak ditemukan | `NOT_FOUND` |
| 409 | Transisi status tidak valid, data duplikat | `INVALID_STATUS_TRANSITION`, `DUPLICATE` |
| 500 | Kesalahan server | `INTERNAL_ERROR` |

Pesan error ke klien tidak boleh membocorkan detail internal (stack trace, query SQL).

---

## 10. Database

- Skema mengikuti `database-logistic.sql` sebagai sumber kebenaran. Perubahan skema lewat migrasi (Alembic), bukan edit manual.
- Trigger `update_timestamp_column` mengurus `updated_at`, jangan di-set manual dari aplikasi.
- Foreign key: `customer_id` `RESTRICT`, `courier_id` dan `created_by` `SET NULL`, `tracking_histories.shipment_id` `CASCADE`.
- Gunakan index yang sudah didefinisikan. Query list wajib memakai paginasi, tanpa `SELECT *` tanpa batas.
- Hindari query N+1: gunakan `selectinload` atau `joinedload` saat memuat relasi.

---

## 11. Keamanan

1. Seluruh komunikasi lewat HTTPS/TLS 1.3 (diatur di reverse proxy).
2. CORS hanya mengizinkan origin frontend yang terdaftar.
3. Rate limiting pada `/auth/login` dan `/auth/register` untuk mencegah brute force.
4. Secret (JWT secret, kredensial DB, storage) hanya di environment, tidak di repository.
5. Semua query lewat ORM atau parameter binding, dilarang menyusun SQL dari string input.
6. Log tidak boleh memuat password, hash, atau token.

---

## 12. Performa & Observabilitas

- Target respons REST API standar **≤ 200 ms** pada beban normal.
- Log terstruktur (JSON) dengan `request_id`. Job scheduler mencatat jumlah shipment yang diproses.
- Sediakan endpoint `GET /health` untuk pengecekan koneksi aplikasi dan database.

---

## 13. Testing

| Jenis | Cakupan minimal |
|---|---|
| Unit (service) | Semua transisi status valid dan tidak valid, pembuatan resi, perhitungan `is_overdue_pending` |
| Integrasi (API + DB test) | Alur lengkap: registrasi → buat DR → assign → picked up → in transit → delivered → confirm |
| RBAC | Setiap endpoint ditolak (`401`/`403`) untuk role yang tidak berhak |
| Scheduler | Auto-complete memproses data yang memenuhi syarat, mengabaikan yang belum, dan idempotent |

Pull request tidak digabung jika test gagal.
