"""
Model database SQLAlchemy (Async) untuk Economy Adventure Bot.
Semua tabel yang dibutuhkan game economy multiplayer didefinisikan di sini.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    coin: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    bank: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    job: Mapped[str | None] = mapped_column(String(100), nullable=True)

    house: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vehicle: Mapped[str | None] = mapped_column(String(100), nullable=True)

    total_work: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_fight: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_login: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    inventory_items: Mapped[list["Inventory"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    pets: Mapped[list["Pet"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="inventory_items")


class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pet_type: Mapped[str] = mapped_column(String(100), nullable=False)
    pet_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    bonus: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="pets")


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # deposit / withdraw
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Market(Base):
    __tablename__ = "market"
    __table_args__ = (
        # Query utama _list_market memfilter status='open' lalu order by created_at desc.
        # Index komposit ini membuat query tersebut index-only-scan, bukan seq scan + sort.
        Index("ix_market_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)  # open / sold / cancelled

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Cooldown(Base):
    __tablename__ = "cooldown"
    __table_args__ = (
        # Satu baris cooldown per (user, command). Mencegah row duplikat saat dua request
        # untuk command yang sama diproses bersamaan (race condition), dan mempercepat
        # check_cooldown/set_cooldown menjadi index lookup langsung.
        UniqueConstraint("user_id", "command", name="uq_cooldown_user_command"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    command: Mapped[str] = mapped_column(String(50), nullable=False)
    last_used: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Farming(Base):
    __tablename__ = "farming"
    __table_args__ = (
        # _get_active_farm selalu memfilter user_id + status IN (...). Index komposit ini
        # menghindari scan seluruh riwayat farming (termasuk yang sudah 'harvested') milik user.
        Index("ix_farming_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plant: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    plant_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    harvest_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="growing", nullable=False)  # growing / ready / harvested


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (
        # Satu baris achievement per (user, achievement) - mencegah duplikat saat _sync_achievements
        # dipanggil bersamaan (mis. /achievement ditekan dua kali dengan cepat).
        UniqueConstraint("user_id", "achievement", name="uq_achievement_user_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement: Mapped[str] = mapped_column(String(100), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Couple(Base):
    """
    Relasi pasangan yang sedang aktif (atau riwayat pasangan yang sudah berakhir).
    Satu baris merepresentasikan satu hubungan antara user_id <-> partner_id.

    Anti-exploit di level database (bukan hanya Python):
    - ck_couples_not_self: user tidak bisa menjadi pasangan dirinya sendiri.
    - uq_couples_user_active / uq_couples_partner_active: partial unique index yang
      memastikan satu user_id (di kolom manapun) hanya boleh muncul di MAKSIMAL satu
      baris couples berstatus 'active' sekaligus -> mencegah double marriage.
    """

    __tablename__ = "couples"
    __table_args__ = (
        CheckConstraint("user_id != partner_id", name="ck_couples_not_self"),
        Index(
            "uq_couples_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_couples_partner_active",
            "partner_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    love_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active / ended

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CoupleProposal(Base):
    """
    Lamaran pasangan yang tertunda (pending) / sudah diproses.
    expires_at membuat proposal otomatis tidak valid setelah beberapa waktu
    walau tombol lama di chat masih bisa ditekan.
    """

    __tablename__ = "couple_proposals"
    __table_args__ = (
        CheckConstraint("sender_id != receiver_id", name="ck_couple_proposals_not_self"),
        # Query utama: cari proposal pending milik sender/receiver tertentu.
        Index("ix_couple_proposals_receiver_status", "receiver_id", "status"),
        Index("ix_couple_proposals_sender_status", "sender_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending/accepted/rejected/expired
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
