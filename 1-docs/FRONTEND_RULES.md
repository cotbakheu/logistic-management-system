# Aturan Frontend: ALUR Logistik (LajuLogistik)

Versi sederhana. Tujuannya: kode rapi, mudah dibaca, dan mudah dikerjakan tanpa arsitektur yang rumit.

---

## 1. Gambaran

Frontend dibuat dalam **satu project** (satu source code) untuk tiga peran: Customer, Kurir, dan Admin.

- **Customer & Kurir**: tampilan mobile, berbentuk PWA.
- **Admin**: tampilan desktop (tabel, grafik, form).
- Setiap peran punya halaman dan layout sendiri, tetapi berbagi komponen, API, dan login yang sama.

**Teknologi:** Vue 3 (`<script setup>`), Vite, Tailwind CSS, Vue Router, Pinia, axios, vite-plugin-pwa. PrimeVue dipakai hanya untuk komponen admin yang rumit (tabel dan dialog). Bahasa kode boleh JavaScript biasa; TypeScript opsional.

---

## 2. Struktur Folder

```
src/
├── main.js
├── App.vue
├── router/
│   └── index.js          # semua route + pengecekan login/role
├── stores/
│   └── auth.js           # simpan token, role, nama (satu-satunya store)
├── api/
│   ├── http.js           # axios + token + penanganan error
│   └── index.js          # fungsi API: login, getMyShipments, assignCourier, dst
├── layouts/
│   ├── MobileLayout.vue  # dipakai Customer & Kurir (bottom nav)
│   └── AdminLayout.vue   # dipakai Admin (sidebar + header)
├── components/           # komponen yang dipakai di banyak halaman
│   ├── StatusBadge.vue
│   ├── TrackingTimeline.vue
│   ├── LoadingState.vue
│   └── EmptyState.vue
├── views/
│   ├── auth/             # LoginView, RegisterView
│   ├── public/           # TrackView
│   ├── customer/         # Home, CreateShipment, History, ShipmentDetail
│   ├── courier/          # TaskList, TaskDetail
│   └── admin/            # Dashboard, Shipments, Couriers, Settings
└── utils/
    └── format.js         # format tanggal, label status
```

Tidak perlu folder tambahan (repositories, use-cases, dan sejenisnya). Kalau satu file terasa terlalu panjang, pecah menjadi komponen kecil di `components/`.

---

## 3. Aturan Dasar Kode

1. Gunakan `<script setup>`. Satu halaman = satu file di `views/`.
2. Penamaan: komponen dan halaman `PascalCase.vue` (contoh `StatusBadge.vue`), fungsi dan variabel `camelCase`.
3. Komponen yang dipakai di lebih dari satu halaman dipindah ke `components/`. Kalau hanya dipakai satu halaman, biarkan di file halaman itu.
4. Data dari server cukup disimpan di halaman (`ref`) lalu dimuat saat halaman dibuka. Tidak perlu store untuk setiap data.
5. Jangan menulis URL API atau token langsung di komponen. Selalu lewat `api/`.
6. Teks antarmuka memakai **Bahasa Indonesia**. Format tanggal `DD MMM YYYY, HH:mm`.
7. Hapus `console.log` dan kode yang dikomentari sebelum commit.

---

## 4. Login & Hak Akses Halaman

1. Setelah login, simpan `access_token`, `role`, dan `name` di store `auth` dan di localStorage, supaya tidak logout saat halaman di-refresh.
2. Arahkan ke halaman awal sesuai role:

| Role | Halaman awal |
|---|---|
| CUSTOMER | `/customer` |
| COURIER | `/courier` |
| ADMIN | `/admin` |

3. Setiap route diberi `meta: { roles: [...] }`. Pengecekan di `router.beforeEach`:
   - belum login → ke `/login`;
   - role tidak cocok → ke halaman awal role-nya.
4. Halaman `/login`, `/register`, dan `/track/:trackingNumber` bisa dibuka tanpa login.
5. Logout: hapus token dari store dan localStorage, lalu ke `/login`.

> Pengecekan di frontend hanya untuk kenyamanan pengguna. Keamanan yang sebenarnya dijaga oleh backend.

---

## 5. Memanggil API

1. Semua request lewat satu instance axios di `api/http.js`.
2. Base URL dari `.env` (`VITE_API_BASE_URL`), diarahkan ke `/api/v1`.
3. Token otomatis ditambahkan ke header `Authorization: Bearer <token>`.
4. Penanganan error di satu tempat (interceptor):
   - `401` → logout dan ke `/login`
   - `403` → tampilkan "Anda tidak memiliki akses"
   - `409` / `422` → tampilkan pesan dari `detail`
   - gagal koneksi → tampilkan "Koneksi bermasalah, coba lagi"
5. Waktu dari server (UTC) hanya diubah ke waktu lokal saat ditampilkan, memakai `utils/format.js`.

---

## 6. Status Pengiriman

### 6.1 Satu komponen badge

Pakai `StatusBadge.vue` di semua tempat. Jangan membuat badge sendiri di halaman.

| Status | Label | Warna |
|---|---|---|
| PENDING | Menunggu | Kuning |
| REJECTED | Ditolak | Merah |
| ASSIGNED | Ditugaskan | Biru |
| PICKED_UP | Dijemput | Indigo |
| IN_TRANSIT | Dalam Perjalanan | Ungu |
| DELIVERED | Terkirim | Hijau muda |
| COMPLETED | Selesai | Hijau tua |

Selalu tampilkan teks label, jangan hanya warna.

### 6.2 Tombol aksi per status

| Peran | Status saat ini | Tombol yang muncul |
|---|---|---|
| Admin | PENDING | **Assign Kurir**, **Tolak** (alasan wajib) |
| Kurir | ASSIGNED | **Sudah Dijemput** |
| Kurir | PICKED_UP | **Dalam Perjalanan** |
| Kurir | IN_TRANSIT | **Terkirim** (wajib foto bukti) |
| Customer | DELIVERED | **Konfirmasi Selesai** |
| Semua | Status lain | Tidak ada tombol |

- Customer **tidak punya** tombol batal. Pembatalan hanya lewat tombol **Tolak** dari Admin.
- Setelah aksi berhasil, muat ulang data dari server.

### 6.3 Timeline tracking

`TrackingTimeline.vue` menampilkan riwayat secara vertikal: badge status, catatan, dan tanggal-jam. Dipakai di halaman tracking publik dan detail customer. Jika status `REJECTED`, tampilkan juga alasan penolakan.

---

## 7. Halaman per Peran

### Customer (mobile)

| Halaman | Isi |
|---|---|
| Beranda | Paket aktif, tombol **Buat Pengiriman**, kolom cari nomor resi |
| Buat Pengiriman | Form pengirim, penerima, alamat asal/tujuan, deskripsi, berat. Setelah sukses, tampilkan nomor resi |
| Riwayat | Daftar paket + filter status |
| Detail | Timeline tracking, tombol **Konfirmasi Selesai** saat `DELIVERED` |

### Kurir (mobile)

| Halaman | Isi |
|---|---|
| Daftar Tugas | Paket milik kurir tersebut |
| Detail Tugas | Alamat, kontak, tombol aksi status berikutnya. Untuk **Terkirim**: ambil foto, unggah, lalu kirim |

### Admin (desktop)

| Halaman | Isi |
|---|---|
| Dashboard | Kartu total, grafik volume pengiriman per hari, grafik jumlah per status |
| Pengiriman | Tabel semua pengiriman + filter, tombol Assign dan Tolak |
| Kurir | Tabel kurir: tambah, ubah, nonaktifkan (tanpa hapus permanen) |
| Pengaturan | Form timeout alert PENDING dan hari auto-complete |

### Tabel admin: baris merah

- Baris ditandai merah **hanya jika** `is_overdue_pending` bernilai `true` dari API. Frontend tidak menghitung sendiri.
- Urutan sudah diatur backend, jangan diubah.
- Tambahkan ikon peringatan agar berbeda dari badge `REJECTED`.

---

## 8. Foto Bukti Pengiriman (Kurir)

1. Pakai `<input type="file" accept="image/*" capture="environment">` untuk membuka kamera.
2. Tampilkan pratinjau foto sebelum dikirim.
3. Unggah ke `POST /uploads/proof`, lalu kirim `proof_image_url` bersama catatan ke endpoint update status.
4. Tombol dinonaktifkan selama proses unggah.
5. Jika unggah gagal, status jangan diubah dan tampilkan pesan agar mencoba lagi.

---

## 9. Form

1. Validasi dasar sebelum kirim, mengikuti aturan backend:

| Field | Aturan |
|---|---|
| Email | Format valid |
| Telepon | Angka, 8-20 karakter |
| Password | Minimal 8 karakter, ada huruf dan angka |
| Berat (kg) | Lebih dari 0 |
| Alamat, deskripsi, alasan tolak | Tidak boleh kosong |

2. Pesan error muncul tepat di bawah field, dalam Bahasa Indonesia.
3. Tombol kirim dinonaktifkan saat request berjalan (cegah klik dua kali).
4. Backend tetap menjadi penentu akhir. Kalau backend menolak, tampilkan pesannya.

---

## 10. Tiga Keadaan Layar

Setiap halaman yang mengambil data harus menangani:

| Keadaan | Tampilan |
|---|---|
| Memuat | `LoadingState` (spinner atau skeleton) |
| Kosong | `EmptyState` dengan kalimat penjelas, contoh "Belum ada pengiriman" |
| Gagal | Pesan error + tombol **Coba Lagi** |

---

## 11. Tampilan

1. Gunakan Tailwind. Atur warna utama dan font di `tailwind.config.js` agar seragam.
2. Customer & Kurir: rancang untuk layar HP dulu (lebar sekitar 360-430 px). Tombol minimal 44 × 44 px, menu utama di navigasi bawah.
3. Admin: layout sidebar + konten, nyaman di layar laptop (≥ 1024 px).
4. Teks isi minimal 14 px (di HP 16 px). Kontras teks harus jelas terbaca.
5. Semua input punya label.

---

## 12. PWA

1. Siapkan `manifest` (nama, ikon 192 dan 512 px, `display: standalone`) lewat vite-plugin-pwa agar bisa di-"Add to Home Screen".
2. Service worker hanya menyimpan file statis (JS, CSS, gambar). **Data API jangan di-cache**, supaya status selalu terbaru.
3. Web Push: minta izin notifikasi setelah pengguna melakukan aksi pertama (contoh: setelah membuat pengiriman), bukan saat aplikasi pertama dibuka.
4. Saat offline, tampilkan pesan "Anda sedang offline" dan nonaktifkan tombol yang mengubah data.

---

## 13. Keamanan Dasar

1. Jangan simpan password di browser, hanya token.
2. Jangan pakai `v-html` untuk teks dari pengguna.
3. Jangan taruh secret di kode. Semua variabel `VITE_*` bisa dilihat publik.

---

## 14. Checklist Sebelum Commit

- [ ] Aplikasi berjalan tanpa error di console.
- [ ] Halaman sudah menangani loading, kosong, dan gagal.
- [ ] Status memakai `StatusBadge`, bukan badge buatan sendiri.
- [ ] Pemanggilan API lewat folder `api/`.
- [ ] Sudah dicoba di tampilan HP (Customer & Kurir) atau desktop (Admin).
- [ ] Tidak ada `console.log` atau kode komentar yang tertinggal.
