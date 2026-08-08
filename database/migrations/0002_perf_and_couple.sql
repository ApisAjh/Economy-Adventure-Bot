-- =====================================================================
-- Migration 0002 — Performance indexes/constraints + Couple System
-- =====================================================================
-- Jalankan file ini di Supabase SQL Editor jika project kamu SUDAH PERNAH
-- menjalankan database/schema.sql versi lama (sebelum fitur pasangan &
-- optimasi performance ini ada).
--
-- Aman dijalankan berkali-kali (idempotent):
--   - CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS untuk objek baru.
--   - Constraint pada tabel LAMA (cooldown, achievements) ditambahkan lewat
--     DO $$ ... $$ block yang mengecek pg_constraint dulu, supaya tidak error
--     kalau constraint-nya sudah pernah ditambahkan.
--
-- TIDAK menghapus/mengubah data yang sudah ada. Jika sebelumnya sudah ada
-- baris duplikat di tabel `cooldown` (user_id, command sama) atau
-- `achievements` (user_id, achievement sama), constraint UNIQUE di bawah
-- akan GAGAL ditambahkan — lihat catatan di masing-masing bagian untuk
-- cara membersihkannya terlebih dahulu.
-- =====================================================================


-- =====================================================================
-- 1) PERF INDEX: market (status, created_at)
-- =====================================================================
CREATE INDEX IF NOT EXISTS ix_market_status_created ON market (status, created_at DESC);


-- =====================================================================
-- 2) PERF INDEX: farming (user_id, status)
-- =====================================================================
CREATE INDEX IF NOT EXISTS ix_farming_user_status ON farming (user_id, status);


-- =====================================================================
-- 3) UNIQUE CONSTRAINT: cooldown (user_id, command)
-- Dibutuhkan oleh set_cooldown() yang sekarang memakai INSERT ... ON CONFLICT.
--
-- Jika langkah ini gagal dengan error "could not create unique index" karena
-- ada baris duplikat, jalankan dulu query pembersihan berikut (opsional,
-- hanya jika error muncul), lalu ulangi ALTER TABLE di bawah:
--
--   DELETE FROM cooldown a USING cooldown b
--   WHERE a.id < b.id
--     AND a.user_id = b.user_id
--     AND a.command = b.command;
-- =====================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_cooldown_user_command'
    ) THEN
        ALTER TABLE cooldown
            ADD CONSTRAINT uq_cooldown_user_command UNIQUE (user_id, command);
    END IF;
END $$;


-- =====================================================================
-- 4) UNIQUE CONSTRAINT: achievements (user_id, achievement)
-- Mencegah baris achievement duplikat untuk user+achievement yang sama.
--
-- Jika gagal karena duplikat, bersihkan dulu dengan:
--
--   DELETE FROM achievements a USING achievements b
--   WHERE a.id < b.id
--     AND a.user_id = b.user_id
--     AND a.achievement = b.achievement;
-- =====================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_achievement_user_name'
    ) THEN
        ALTER TABLE achievements
            ADD CONSTRAINT uq_achievement_user_name UNIQUE (user_id, achievement);
    END IF;
END $$;


-- =====================================================================
-- 5) TABEL BARU: couples
-- =====================================================================
CREATE TABLE IF NOT EXISTS couples (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    partner_id      INTEGER NOT NULL,
    love_level      INTEGER NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,

    CONSTRAINT fk_couples_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_couples_partner
        FOREIGN KEY (partner_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_couples_not_self CHECK (user_id != partner_id)
);

CREATE INDEX IF NOT EXISTS ix_couples_user_id ON couples (user_id);
CREATE INDEX IF NOT EXISTS ix_couples_partner_id ON couples (partner_id);

-- Anti double-marriage: satu user_id (di kolom manapun) maksimal 1 baris 'active'.
CREATE UNIQUE INDEX IF NOT EXISTS uq_couples_user_active
    ON couples (user_id) WHERE (status = 'active');
CREATE UNIQUE INDEX IF NOT EXISTS uq_couples_partner_active
    ON couples (partner_id) WHERE (status = 'active');


-- =====================================================================
-- 6) TABEL BARU: couple_proposals
-- =====================================================================
CREATE TABLE IF NOT EXISTS couple_proposals (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sender_id       INTEGER NOT NULL,
    receiver_id     INTEGER NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_couple_proposals_sender
        FOREIGN KEY (sender_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_couple_proposals_receiver
        FOREIGN KEY (receiver_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_couple_proposals_not_self CHECK (sender_id != receiver_id),
    CONSTRAINT ck_couple_proposals_status_valid
        CHECK (status IN ('pending', 'accepted', 'rejected', 'expired'))
);

CREATE INDEX IF NOT EXISTS ix_couple_proposals_receiver_status ON couple_proposals (receiver_id, status);
CREATE INDEX IF NOT EXISTS ix_couple_proposals_sender_status ON couple_proposals (sender_id, status);


-- =====================================================================
-- SELESAI — migration 0002 selesai dijalankan.
-- =====================================================================
