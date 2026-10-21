from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    String, Integer, Boolean, DateTime, Date, ForeignKey, Numeric, Text,
    CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from .database import Base
from .embeddings import EMBEDDING_DIM

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unit: Mapped[str] = mapped_column(String(30), default="pcs")
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Vector embedding for semantic search (populated on create/update)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

class Party(Base):
    __tablename__ = "parties"
    id: Mapped[int] = mapped_column(primary_key=True)
    party_type: Mapped[str] = mapped_column(String(20), index=True)  # customer or supplier
    name: Mapped[str] = mapped_column(String(240), index=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(240), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Purchase(Base):
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("parties.id"))
    document_date: Mapped[date] = mapped_column(Date, default=date.today)
    tax_mode: Mapped[str] = mapped_column(String(10), default="gst")  # gst / non_gst
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    lines: Mapped[list["PurchaseLine"]] = relationship(back_populates="purchase", cascade="all, delete-orphan")
    supplier: Mapped["Party"] = relationship()

class PurchaseLine(Base):
    __tablename__ = "purchase_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    purchase: Mapped["Purchase"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()

class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"), nullable=True)
    invoice_date: Mapped[date] = mapped_column(Date, default=date.today)
    tax_mode: Mapped[str] = mapped_column(String(10), default="gst")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    lines: Mapped[list["SaleLine"]] = relationship(back_populates="sale", cascade="all, delete-orphan")
    customer: Mapped["Party | None"] = relationship()

class SaleLine(Base):
    __tablename__ = "sale_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    sale: Mapped["Sale"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()

class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    movement_type: Mapped[str] = mapped_column(String(30))  # opening, purchase, sale, return, adjustment
    quantity_change: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    picture: Mapped[str | None] = mapped_column(String(512), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="viewer")  # admin, manager, viewer
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

