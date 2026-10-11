-- ============================================================================
-- SYSTEM NAME : ALUR LOGISTIK (LajuLogistik)
-- DATABASE    : PostgreSQL 13+
-- DESCRIPTION : Complete Schema for Logistics Tracking & Management System
-- ============================================================================

-- Drop existing structures if re-running (Clean setup)
DROP TABLE IF EXISTS tracking_histories CASCADE;
DROP TABLE IF EXISTS shipments CASCADE;
DROP TABLE IF EXISTS system_settings CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TYPE IF EXISTS shipment_status CASCADE;
DROP TYPE IF EXISTS user_role CASCADE;

-- ----------------------------------------------------------------------------
-- 1. ENUM TYPES CREATION
-- ----------------------------------------------------------------------------
CREATE TYPE user_role AS ENUM (
    'ADMIN',
    'COURIER',
    'CUSTOMER'
);

CREATE TYPE shipment_status AS ENUM (
    'PENDING', 
    'REJECTED', 
    'ASSIGNED', 
    'PICKED_UP', 
    'IN_TRANSIT', 
    'DELIVERED', 
    'COMPLETED'
);

-- ----------------------------------------------------------------------------
-- 2. USERS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ----------------------------------------------------------------------------
-- 3. SHIPMENTS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE shipments (
    id BIGSERIAL PRIMARY KEY,
    tracking_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    courier_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    
    -- Origin / Pengirim
    sender_name VARCHAR(100) NOT NULL,
    sender_phone VARCHAR(20) NOT NULL,
    origin_address TEXT NOT NULL,
    
    -- Destination / Penerima
    recipient_name VARCHAR(100) NOT NULL,
    recipient_phone VARCHAR(20) NOT NULL,
    destination_address TEXT NOT NULL,
    
    -- Detail Paket
    package_description TEXT NOT NULL,
    weight_kg NUMERIC(6, 2) NOT NULL CONSTRAINT check_weight_positive CHECK (weight_kg > 0),
    
    -- Status & Metadata Lifecycle
    status shipment_status DEFAULT 'PENDING' NOT NULL,
    rejection_reason TEXT,
    proof_image_url VARCHAR(255),
    
    -- Timestamps
    delivered_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ----------------------------------------------------------------------------
-- 4. TRACKING_HISTORIES TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE tracking_histories (
    id BIGSERIAL PRIMARY KEY,
    shipment_id BIGINT NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
    status shipment_status NOT NULL,
    notes TEXT NOT NULL,
    created_by BIGINT REFERENCES users(id) ON DELETE SET NULL, -- NULL jika di-generated oleh sistem/cron
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ----------------------------------------------------------------------------
-- 5. SYSTEM_SETTINGS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE system_settings (
    key VARCHAR(50) PRIMARY KEY,
    value VARCHAR(255) NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ----------------------------------------------------------------------------
-- 6. INDEXES FOR PERFORMANCE OPTIMIZATION
-- ----------------------------------------------------------------------------
-- Index pencarian berdasar nomor resi
CREATE INDEX idx_shipments_tracking_number ON shipments(tracking_number);

-- Index query list paket per Customer & Kurir
CREATE INDEX idx_shipments_customer_id ON shipments(customer_id);
CREATE INDEX idx_shipments_courier_id ON shipments(courier_id);

-- Index khusus Admin Dashboard (Optimasi Filter Status & Sort Waktu)
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_pending_alert ON shipments(status, created_at) WHERE status = 'PENDING';

-- Index khusus Cron Job Auto-Complete (Meningkatkan kecepatan query 3 hari)
CREATE INDEX idx_shipments_auto_complete ON shipments(status, delivered_at) WHERE status = 'DELIVERED';

-- Index log tracking per shipment
CREATE INDEX idx_tracking_histories_shipment_id ON tracking_histories(shipment_id);

-- ----------------------------------------------------------------------------
-- 7. TRIGGER FOR AUTO-UPDATING 'updated_at' TIMESTAMP
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_timestamp_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_modtime
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_column();

CREATE TRIGGER update_shipments_modtime
    BEFORE UPDATE ON shipments
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_column();

CREATE TRIGGER update_system_settings_modtime
    BEFORE UPDATE ON system_settings
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_column();

-- ----------------------------------------------------------------------------
-- 8. INITIAL SEED DATA
-- ----------------------------------------------------------------------------
-- Password hash berikut mengacu pada string terenkripsi "Password123!" (Bcrypt)
INSERT INTO users (name, email, phone, password_hash, role) VALUES
('Super Admin', 'admin@alur.com', '081234567890', '$2b$12$e86R4/4.0LszI4u.hVptIuG68I9q1u0XQ8O2J40GvA621jR2oZ14G', 'ADMIN'),
('Budi Kurir', 'budi.courier@alur.com', '081234567891', '$2b$12$e86R4/4.0LszI4u.hVptIuG68I9q1u0XQ8O2J40GvA621jR2oZ14G', 'COURIER'),
('Eko Customer', 'eko.customer@gmail.com', '081234567892', '$2b$12$e86R4/4.0LszI4u.hVptIuG68I9q1u0XQ8O2J40GvA621jR2oZ14G', 'CUSTOMER');

-- Inisialisasi Pengaturan Konfigurasi Sistem
INSERT INTO system_settings (key, value, description) VALUES
('pending_alert_timeout_minutes', '30', 'Durasi menit status PENDING sebelum baris berwarna MERAH di Dashboard Admin'),
('auto_complete_days', '3', 'Durasi hari status DELIVERED sebelum otomatis diubah menjadi COMPLETED oleh Cron Job');