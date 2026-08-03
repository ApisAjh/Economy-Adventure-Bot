"""
Model database SQLAlchemy (Async) untuk Economy Adventure Bot.
Semua tabel yang dibutuhkan game economy multiplayer didefinisikan di sini.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)  # open / sold / cancelled

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Cooldown(Base):
    __tablename__ = "cooldown"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    command: Mapped[str] = mapped_column(String(50), nullable=False)
    last_used: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Farming(Base):
    __tablename__ = "farming"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plant: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    plant_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    harvest_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="growing", nullable=False)  # growing / ready / harvested


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement: Mapped[str] = mapped_column(String(100), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
