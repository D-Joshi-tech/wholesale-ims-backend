from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=240)
    category: str | None = None
    unit: str = "pcs"
    purchase_price: Decimal = Field(default=0, ge=0)
    selling_price: Decimal = Field(default=0, ge=0)
    gst_rate: Decimal = Field(default=0, ge=0, le=100)
    opening_stock: Decimal = Field(default=0, ge=0)
    reorder_level: Decimal = Field(default=0, ge=0)

class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku: str
    name: str
    category: str | None
    unit: str
    purchase_price: Decimal
    selling_price: Decimal
    gst_rate: Decimal
    stock_quantity: Decimal
    reorder_level: Decimal
    is_active: bool

class PartyCreate(BaseModel):
    party_type: Literal["customer", "supplier"]
    name: str
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    address: str | None = None
    state_code: str | None = None

class PartyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    party_type: str
    name: str
    phone: str | None
    email: str | None
    gstin: str | None
    address: str | None
    state_code: str | None
    is_active: bool

class LineInput(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    gst_rate: Decimal = Field(default=0, ge=0, le=100)

class PurchaseCreate(BaseModel):
    document_number: str
    supplier_id: int
    document_date: date = Field(default_factory=date.today)
    tax_mode: Literal["gst", "non_gst"] = "gst"
    lines: list[LineInput] = Field(min_length=1)
    notes: str | None = None

class SaleCreate(BaseModel):
    invoice_number: str
    customer_id: int | None = None
    invoice_date: date = Field(default_factory=date.today)
    tax_mode: Literal["gst", "non_gst"] = "gst"
    lines: list[LineInput] = Field(min_length=1)
    notes: str | None = None

class GoogleAuthRequest(BaseModel):
    credential: str  # Google ID token credential
    client_id: str | None = None

class DevLoginRequest(BaseModel):
    email: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserRead"

class UserCreate(BaseModel):
    email: str
    name: str | None = None
    role: Literal["admin", "manager", "viewer"] = "viewer"
    is_allowed: bool = True

class UserUpdate(BaseModel):
    name: str | None = None
    role: Literal["admin", "manager", "viewer"] | None = None
    is_allowed: bool | None = None

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str | None
    picture: str | None
    role: str
    is_allowed: bool
    created_at: datetime | None = None
    last_login: datetime | None = None

