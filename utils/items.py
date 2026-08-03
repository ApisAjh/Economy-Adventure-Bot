"""
Definisi statis konten game: item toko, pekerjaan, ikan, hasil tambang,
tanaman, jenis pet, dan daftar achievement.
"""

# ---- Toko ----
SHOP_ITEMS: dict[str, dict] = {
    "Pancing": {"emoji": "🎣", "price": 1500, "category": "tool"},
    "Kapak": {"emoji": "🪓", "price": 1500, "category": "tool"},
    "Pickaxe": {"emoji": "⛏", "price": 1500, "category": "tool"},
    "Laptop": {"emoji": "💻", "price": 5000, "category": "tool"},
    "Motor": {"emoji": "🏍", "price": 25000, "category": "vehicle"},
    "Mobil": {"emoji": "🚗", "price": 100000, "category": "vehicle"},
    "Rumah": {"emoji": "🏠", "price": 250000, "category": "house"},
    "Pet": {"emoji": "🐶", "price": 15000, "category": "pet"},
    "Diamond": {"emoji": "💎", "price": 10000, "category": "resource"},
    "Lucky Box": {"emoji": "🎁", "price": 3000, "category": "box"},
}

# ---- Pekerjaan (/work) ----
JOBS: list[dict] = [
    {"name": "Barista", "emoji": "☕", "min_coin": 300, "max_coin": 700, "xp": 80},
    {"name": "Programmer", "emoji": "💻", "min_coin": 800, "max_coin": 1500, "xp": 150},
    {"name": "Dokter", "emoji": "🩺", "min_coin": 900, "max_coin": 1700, "xp": 160},
    {"name": "Polisi", "emoji": "👮", "min_coin": 600, "max_coin": 1100, "xp": 110},
    {"name": "Chef", "emoji": "👨‍🍳", "min_coin": 500, "max_coin": 1000, "xp": 100},
    {"name": "Pilot", "emoji": "✈️", "min_coin": 1000, "max_coin": 2000, "xp": 180},
    {"name": "Guru", "emoji": "🧑‍🏫", "min_coin": 400, "max_coin": 800, "xp": 90},
    {"name": "Petani", "emoji": "🌾", "min_coin": 300, "max_coin": 600, "xp": 70},
    {"name": "Nelayan", "emoji": "🎣", "min_coin": 350, "max_coin": 650, "xp": 75},
    {"name": "Kurir", "emoji": "📦", "min_coin": 250, "max_coin": 550, "xp": 60},
    {"name": "Teknisi", "emoji": "🔧", "min_coin": 500, "max_coin": 950, "xp": 100},
    {"name": "Mekanik", "emoji": "🛠", "min_coin": 500, "max_coin": 950, "xp": 100},
]

# ---- Ikan (/fish) ----
FISH_TYPES: list[dict] = [
    {"name": "Ikan Biasa", "emoji": "🐟", "rarity": "common", "weight": 70, "min_coin": 100, "max_coin": 300},
    {"name": "Rare Fish", "emoji": "🐠", "rarity": "rare", "weight": 25, "min_coin": 500, "max_coin": 1200},
    {"name": "Legendary Fish", "emoji": "🐡", "rarity": "legendary", "weight": 5, "min_coin": 2000, "max_coin": 5000},
]

# ---- Hasil Tambang (/mine) ----
ORE_TYPES: list[dict] = [
    {"name": "Batu", "emoji": "🪨", "weight": 55, "min_coin": 50, "max_coin": 150},
    {"name": "Besi", "emoji": "⛓", "weight": 30, "min_coin": 200, "max_coin": 500},
    {"name": "Emas", "emoji": "🥇", "weight": 12, "min_coin": 700, "max_coin": 1500},
    {"name": "Diamond", "emoji": "💎", "weight": 3, "min_coin": 3000, "max_coin": 6000},
]

# ---- Tanaman (/farm) ----
PLANTS: dict[str, dict] = {
    "Jagung": {"emoji": "🌽", "grow_seconds": 300, "yield_min": 3, "yield_max": 8, "sell_price": 150},
    "Gandum": {"emoji": "🌾", "grow_seconds": 600, "yield_min": 4, "yield_max": 10, "sell_price": 200},
    "Padi": {"emoji": "🍚", "grow_seconds": 900, "yield_min": 5, "yield_max": 12, "sell_price": 250},
}

# ---- Pet (/pet) ----
PET_TYPES: list[dict] = [
    {"name": "Kucing", "emoji": "🐱", "base_bonus": 0.02},
    {"name": "Anjing", "emoji": "🐶", "base_bonus": 0.03},
    {"name": "Naga", "emoji": "🐉", "base_bonus": 0.08},
    {"name": "Rubah", "emoji": "🦊", "base_bonus": 0.04},
    {"name": "Burung", "emoji": "🐦", "base_bonus": 0.025},
]

# ---- Lucky Box (isi random) ----
LUCKY_BOX_REWARDS: list[dict] = [
    {"type": "coin", "weight": 40, "min_coin": 500, "max_coin": 3000},
    {"type": "diamond", "weight": 25, "amount": 1},
    {"type": "item", "weight": 20, "item": "Pickaxe"},
    {"type": "pet", "weight": 10, "pet": "Rubah"},
    {"type": "jackpot", "weight": 5, "min_coin": 10000, "max_coin": 50000},
]

# ---- Achievement ----
ACHIEVEMENTS: dict[str, dict] = {
    "Worker": {"emoji": "🏆", "description": "Bekerja 100 kali", "check": "total_work", "target": 100},
    "Owner": {"emoji": "🏠", "description": "Memiliki rumah", "check": "house", "target": True},
    "Millionaire": {"emoji": "💰", "description": "Memiliki 1 juta Coin", "check": "coin", "target": 1_000_000},
    "Fighter": {"emoji": "⚔️", "description": "Menang duel 50 kali", "check": "total_fight", "target": 50},
    "Loyal Player": {"emoji": "📅", "description": "Login 30 kali", "check": "total_login", "target": 30},
}
