-- =====================================================================
-- Economy Adventure Bot — Database Schema (PostgreSQL / Supabase)
-- =====================================================================
-- File ini adalah representasi SQL murni dari seluruh model yang
-- didefinisikan di "database/models.py" (SQLAlchemy).
--
-- Cara pakai:
--   1. Buka Supabase Dashboard → SQL Editor → New Query.
--   2. Salin seluruh isi file ini.
--   3. Tempel ke SQL Editor, lalu klik "Run".
--
-- Aman dijalankan berkali-kali (idempotent) karena menggunakan
-- "CREATE TABLE IF NOT EXISTS" dan "CREATE INDEX IF NOT EXISTS".
--
-- Urutan tabel mengikuti urutan dependensi Foreign Key:
--   users -> inventory, pets, bank_transactions, market, cooldown,
--            farming, achievements, couples, couple_proposals
--   events (berdiri sendiri, tanpa Foreign Key)
-- =====================================================================


-- =====================================================================
-- TABEL: users
-- Menyimpan data utama setiap pemain.
-- =====================================================================
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    telegram_id     BIGINT NOT NULL,
    username        VARCHAR(255),
    full_name       VARCHAR(255),

    coin            BIGINT NOT NULL DEFAULT 0,
    bank            BIGINT NOT NULL DEFAULT 0,

    level           INTEGER NOT NULL DEFAULT 1,
    xp              BIGINT NOT NULL DEFAULT 0,

    job             VARCHAR(100),

    house           VARCHAR(100),
    vehicle         VARCHAR(100),

    total_work      INTEGER NOT NULL DEFAULT 0,
    total_fight     INTEGER NOT NULL DEFAULT 0,
    total_login     INTEGER NOT NULL DEFAULT 0,

    last_login      TIMESTAMPTZ,

    is_banned       BOOLEAN NOT NULL DEFAULT FALSE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_users_telegram_id UNIQUE (telegram_id),
    CONSTRAINT ck_users_coin_non_negative CHECK (coin >= 0),
    CONSTRAINT ck_users_bank_non_negative CHECK (bank >= 0),
    CONSTRAINT ck_users_level_positive CHECK (level >= 1),
    CONSTRAINT ck_users_xp_non_negative CHECK (xp >= 0),
    CONSTRAINT ck_users_total_work_non_negative CHECK (total_work >= 0),
    CONSTRAINT ck_users_total_fight_non_negative CHECK (total_fight >= 0),
    CONSTRAINT ck_users_total_login_non_negative CHECK (total_login >= 0)
);

-- index=True pada kolom telegram_id (selain UNIQUE constraint di atas)
CREATE INDEX IF NOT EXISTS ix_users_telegram_id ON users (telegram_id);

-- Trigger agar kolom updated_at otomatis mengikuti perilaku onupdate=func.now()
-- yang didefinisikan di model SQLAlchemy (User.updated_at).
CREATE OR REPLACE FUNCTION set_updated_at_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_set_updated_at ON users;
CREATE TRIGGER trg_users_set_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();


-- =====================================================================
-- TABEL: inventory
-- Menyimpan barang yang dimiliki setiap pemain.
-- =====================================================================
CREATE TABLE IF NOT EXISTS inventory (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    item_name       VARCHAR(100) NOT NULL,
    quantity        INTEGER NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_inventory_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_inventory_quantity_non_negative CHECK (quantity >= 0)
);

CREATE INDEX IF NOT EXISTS ix_inventory_user_id ON inventory (user_id);


-- =====================================================================
-- TABEL: pets
-- Menyimpan pet yang dimiliki setiap pemain.
-- =====================================================================
CREATE TABLE IF NOT EXISTS pets (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    pet_type        VARCHAR(100) NOT NULL,
    pet_level       INTEGER NOT NULL DEFAULT 1,
    bonus           DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_pets_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_pets_level_positive CHECK (pet_level >= 1),
    CONSTRAINT ck_pets_bonus_non_negative CHECK (bonus >= 0)
);

CREATE INDEX IF NOT EXISTS ix_pets_user_id ON pets (user_id);


-- =====================================================================
-- TABEL: bank_transactions
-- Mencatat riwayat setiap deposit/withdraw pemain.
-- =====================================================================
CREATE TABLE IF NOT EXISTS bank_transactions (
    id                  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             INTEGER NOT NULL,
    transaction_type    VARCHAR(50) NOT NULL,
    amount              BIGINT NOT NULL,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_bank_transactions_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_bank_transactions_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_bank_transactions_type_valid
        CHECK (transaction_type IN ('deposit', 'withdraw'))
);

CREATE INDEX IF NOT EXISTS ix_bank_transactions_user_id ON bank_transactions (user_id);


-- =====================================================================
-- TABEL: market
-- Marketplace jual-beli item antar pemain.
-- =====================================================================
CREATE TABLE IF NOT EXISTS market (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    seller_id       INTEGER NOT NULL,
    item_name       VARCHAR(100) NOT NULL,
    quantity        INTEGER NOT NULL,
    price           BIGINT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'open',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_market_seller
        FOREIGN KEY (seller_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_market_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_market_price_positive CHECK (price > 0),
    CONSTRAINT ck_market_status_valid
        CHECK (status IN ('open', 'sold', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS ix_market_seller_id ON market (seller_id);

-- PERF: _list_market selalu memfilter status='open' lalu ORDER BY created_at DESC.
-- Index komposit ini membuat query tersebut memakai index scan yang sudah terurut,
-- bukan seq scan + sort terpisah.
CREATE INDEX IF NOT EXISTS ix_market_status_created ON market (status, created_at DESC);


-- =====================================================================
-- TABEL: cooldown
-- Menyimpan waktu terakhir setiap command dijalankan per user.
-- =====================================================================
CREATE TABLE IF NOT EXISTS cooldown (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    command         VARCHAR(50) NOT NULL,
    last_used       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_cooldown_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,

    -- PERF/SAFETY: satu baris cooldown per (user, command). Dipakai oleh set_cooldown()
    -- untuk melakukan upsert (INSERT ... ON CONFLICT) dalam 1 query, dan mencegah baris
    -- duplikat jika dua request command yang sama diproses hampir bersamaan.
    CONSTRAINT uq_cooldown_user_command UNIQUE (user_id, command)
);

CREATE INDEX IF NOT EXISTS ix_cooldown_user_id ON cooldown (user_id);


-- =====================================================================
-- TABEL: farming
-- Menyimpan status tanam/panen pemain.
-- =====================================================================
CREATE TABLE IF NOT EXISTS farming (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    plant           VARCHAR(100) NOT NULL,
    amount          INTEGER NOT NULL,
    plant_time      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    harvest_time    TIMESTAMPTZ NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'growing',

    CONSTRAINT fk_farming_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_farming_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_farming_status_valid
        CHECK (status IN ('growing', 'ready', 'harvested'))
);

CREATE INDEX IF NOT EXISTS ix_farming_user_id ON farming (user_id);

-- PERF: _get_active_farm selalu memfilter user_id + status IN ('growing','ready').
-- Index komposit menghindari scan seluruh riwayat farming user (termasuk yang 'harvested').
CREATE INDEX IF NOT EXISTS ix_farming_user_status ON farming (user_id, status);


-- =====================================================================
-- TABEL: achievements
-- Menyimpan progress achievement setiap pemain.
-- =====================================================================
CREATE TABLE IF NOT EXISTS achievements (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    achievement     VARCHAR(100) NOT NULL,
    completed       BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at    TIMESTAMPTZ,

    CONSTRAINT fk_achievements_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,

    -- Mencegah baris achievement duplikat untuk user+achievement yang sama.
    CONSTRAINT uq_achievement_user_name UNIQUE (user_id, achievement)
);

CREATE INDEX IF NOT EXISTS ix_achievements_user_id ON achievements (user_id);


-- =====================================================================
-- TABEL: couples
-- Relasi pasangan (aktif maupun sudah berakhir) antar dua pemain.
-- =====================================================================
CREATE TABLE IF NOT EXISTS couples (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    partner_id      INTEGER NOT NULL,
    love_level      INTEGER NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',   -- active / ended

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

-- ANTI-EXPLOIT (double marriage): partial unique index memastikan satu user_id hanya
-- boleh muncul di MAKSIMAL satu baris couples berstatus 'active', baik dia tercatat
-- sebagai user_id ATAUPUN partner_id di baris tersebut.
CREATE UNIQUE INDEX IF NOT EXISTS uq_couples_user_active
    ON couples (user_id) WHERE (status = 'active');
CREATE UNIQUE INDEX IF NOT EXISTS uq_couples_partner_active
    ON couples (partner_id) WHERE (status = 'active');


-- =====================================================================
-- TABEL: couple_proposals
-- Lamaran pasangan (pending/accepted/rejected/expired), punya masa berlaku.
-- =====================================================================
CREATE TABLE IF NOT EXISTS couple_proposals (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sender_id       INTEGER NOT NULL,
    receiver_id     INTEGER NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending/accepted/rejected/expired
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
-- TABEL: events
-- Event global yang dikelola admin (tidak terhubung ke tabel manapun).
-- =====================================================================
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_name      VARCHAR(100) NOT NULL,
    description     TEXT,
    multiplier      DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    active          BOOLEAN NOT NULL DEFAULT FALSE,
    start_time      TIMESTAMPTZ,
    end_time        TIMESTAMPTZ,

    CONSTRAINT ck_events_multiplier_positive CHECK (multiplier > 0)
);

-- =====================================================================
-- SELESAI
-- Setelah script ini dijalankan, seluruh tabel yang dibutuhkan
-- Economy Adventure Bot sudah siap digunakan.
-- =====================================================================
