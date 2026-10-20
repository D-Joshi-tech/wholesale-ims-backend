import os
from contextlib import asynccontextmanager
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import parse_qs, urlencode
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from .database import Base, get_db, get_engine
from .models import Product, Party, Purchase, PurchaseLine, Sale, SaleLine, StockMovement
from .schemas import ProductCreate, ProductRead, PartyCreate, PartyRead, PurchaseCreate, SaleCreate
from .embeddings import embed_text, product_text, preload_model

# -------------------------------------------------------------------
# Lifespan: creates all tables on startup (required for async engine)
# -------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize Database Tables & pgvector Extension
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS products_embedding_hnsw_idx
                ON products USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """))
    except Exception as e:
        print(f"Database connection/startup note (ensure cloud DB is configured): {e}")

    # 2. Preload embedding model
    try:
        import asyncio
        await asyncio.get_event_loop().run_in_executor(None, preload_model)
    except Exception as e:
        print(f"Model preloading note: {e}")

    yield

cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

class VercelPathCorrectionMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            query_string = scope.get("query_string", b"").decode("utf-8")
            path = scope.get("path", "")
            if "path=" in query_string:
                params = parse_qs(query_string)
                if "path" in params and params["path"]:
                    target_path = "/" + params["path"][0].lstrip("/")
                    del params["path"]
                    new_query = urlencode(params, doseq=True)
                    scope["path"] = target_path
                    scope["raw_path"] = target_path.encode("utf-8")
                    scope["query_string"] = new_query.encode("utf-8")
            elif path in ("/api/index.py", "/api/index", "/api", "/api/"):
                headers = dict(scope.get("headers", []))
                matched = (
                    headers.get(b"x-matched-path")
                    or headers.get(b"x-forwarded-uri")
                    or headers.get(b"x-invoke-path")
                )
                if matched:
                    decoded = matched.decode("utf-8")
                    if decoded not in ("/api/index.py", "/api/index", "/api", "/api/"):
                        scope["path"] = decoded
                        scope["raw_path"] = decoded.encode("utf-8")
        await self.app(scope, receive, send)

app = FastAPI(
    title="Wholesale Management API",
    version="0.1.0",
    lifespan=lifespan if not os.getenv("VERCEL") else None,
)
app.add_middleware(VercelPathCorrectionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CENT = Decimal("0.01")
def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)

# -------------------------------------------------------------------
# Root & Health & Vercel Endpoints
# -------------------------------------------------------------------
@app.get("/")
@app.get("/api")
@app.get("/api/")
@app.get("/api/index.py")
@app.get("/api/index")
async def root():
    return {
        "app": "Wholesale Desk API",
        "status": "online",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/api/docs")
async def api_docs():
    return RedirectResponse(url="/docs")

# -------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------
@app.get("/api/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db)):
    product_count = await db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True))) or 0
    low_stock = await db.scalar(select(func.count(Product.id)).where(
        Product.is_active.is_(True), Product.stock_quantity <= Product.reorder_level
    )) or 0
    sales_total = await db.scalar(select(func.coalesce(func.sum(Sale.grand_total), 0))) or 0
    purchase_total = await db.scalar(select(func.coalesce(func.sum(Purchase.grand_total), 0))) or 0
    return {
        "product_count": product_count,
        "low_stock_count": low_stock,
        "sales_total": float(sales_total),
        "purchase_total": float(purchase_total),
    }

# -------------------------------------------------------------------
# Products
# -------------------------------------------------------------------
@app.get("/api/products", response_model=list[ProductRead])
async def list_products(search: str = "", db: AsyncSession = Depends(get_db)):
    stmt = select(Product).where(Product.is_active.is_(True))
    if search:
        stmt = stmt.where((Product.name.ilike(f"%{search}%")) | (Product.sku.ilike(f"%{search}%")))
    result = await db.execute(stmt.order_by(Product.name).limit(500))
    return result.scalars().all()

@app.post("/api/products", response_model=ProductRead, status_code=201)
async def create_product(payload: ProductCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(Product.id).where(Product.sku == payload.sku))
    if existing:
        raise HTTPException(409, "SKU already exists")
    product = Product(
        sku=payload.sku.strip(), name=payload.name.strip(), category=payload.category,
        unit=payload.unit, purchase_price=payload.purchase_price,
        selling_price=payload.selling_price, gst_rate=payload.gst_rate,
        stock_quantity=payload.opening_stock, reorder_level=payload.reorder_level,
    )
    db.add(product)
    await db.flush()
    if payload.opening_stock:
        db.add(StockMovement(product_id=product.id, movement_type="opening",
                             quantity_change=payload.opening_stock, reference="OPENING"))
    await db.commit()
    await db.refresh(product)
    # Generate and save embedding (if embedding model is available)
    vector = await embed_text(product_text(product.name, product.category, product.unit))
    if vector is not None:
        product.embedding = vector
        await db.commit()
        await db.refresh(product)
    return product


@app.get("/api/products/search", response_model=list[ProductRead])
async def semantic_search(
    q: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic product search using pgvector cosine similarity.
    Gracefully falls back to standard keyword search if vector model is unavailable.
    """
    if not q.strip():
        raise HTTPException(400, "Query cannot be empty")
    query_vector = await embed_text(q.strip())
    if query_vector is not None:
        try:
            result = await db.execute(
                select(Product)
                .where(Product.is_active.is_(True))
                .where(Product.embedding.isnot(None))
                .order_by(Product.embedding.cosine_distance(query_vector))
                .limit(limit)
            )
            matches = result.scalars().all()
            if matches:
                return matches
        except Exception:
            pass

    # Keyword search fallback
    stmt = select(Product).where(
        Product.is_active.is_(True),
        (Product.name.ilike(f"%{q.strip()}%")) | (Product.sku.ilike(f"%{q.strip()}%"))
    ).limit(limit)
    fallback_result = await db.execute(stmt)
    return fallback_result.scalars().all()

# -------------------------------------------------------------------
# Parties (Suppliers & Customers)
# -------------------------------------------------------------------
@app.get("/api/parties", response_model=list[PartyRead])
async def list_parties(party_type: str | None = None, search: str = "", db: AsyncSession = Depends(get_db)):
    stmt = select(Party).where(Party.is_active.is_(True))
    if party_type:
        if party_type not in {"customer", "supplier"}:
            raise HTTPException(400, "party_type must be customer or supplier")
        stmt = stmt.where(Party.party_type == party_type)
    if search:
        stmt = stmt.where(Party.name.ilike(f"%{search}%"))
    result = await db.execute(stmt.order_by(Party.name).limit(500))
    return result.scalars().all()

@app.post("/api/parties", response_model=PartyRead, status_code=201)
async def create_party(payload: PartyCreate, db: AsyncSession = Depends(get_db)):
    party = Party(**payload.model_dump())
    db.add(party)
    await db.commit()
    await db.refresh(party)
    return party

# -------------------------------------------------------------------
# Purchases
# -------------------------------------------------------------------
@app.get("/api/purchases")
async def list_purchases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Purchase).options(joinedload(Purchase.supplier)).order_by(Purchase.id.desc()).limit(100)
    )
    rows = result.unique().scalars().all()
    return [{
        "id": x.id, "document_number": x.document_number, "supplier": x.supplier.name,
        "document_date": x.document_date.isoformat(), "tax_mode": x.tax_mode,
        "subtotal": float(x.subtotal), "tax_total": float(x.tax_total), "grand_total": float(x.grand_total)
    } for x in rows]

@app.post("/api/purchases", status_code=201)
async def create_purchase(payload: PurchaseCreate, db: AsyncSession = Depends(get_db)):
    try:
        supplier = await db.get(Party, payload.supplier_id)
        if not supplier or supplier.party_type != "supplier":
            raise HTTPException(400, "Valid supplier required")
        purchase = Purchase(
            document_number=payload.document_number, supplier_id=payload.supplier_id,
            document_date=payload.document_date, tax_mode=payload.tax_mode, notes=payload.notes,
        )
        subtotal = Decimal("0")
        tax_total = Decimal("0")
        db.add(purchase)
        await db.flush()
        for line in payload.lines:
            result = await db.execute(
                select(Product).where(Product.id == line.product_id).with_for_update()
            )
            product = result.scalar_one_or_none()
            if not product:
                raise HTTPException(404, f"Product {line.product_id} not found")
            base = money(line.quantity * line.unit_price)
            tax = money(base * line.gst_rate / Decimal("100")) if payload.tax_mode == "gst" else Decimal("0.00")
            subtotal += base
            tax_total += tax
            db.add(PurchaseLine(
                purchase_id=purchase.id, product_id=product.id, quantity=line.quantity,
                unit_price=line.unit_price,
                gst_rate=line.gst_rate if payload.tax_mode == "gst" else 0,
                line_total=base + tax,
            ))
            product.stock_quantity += line.quantity
            product.purchase_price = line.unit_price
            db.add(StockMovement(product_id=product.id, movement_type="purchase",
                                 quantity_change=line.quantity, reference=payload.document_number))
        purchase.subtotal = subtotal
        purchase.tax_total = tax_total
        purchase.grand_total = subtotal + tax_total
        await db.commit()
        return {
            "id": purchase.id, "document_number": purchase.document_number,
            "subtotal": float(subtotal), "tax_total": float(tax_total),
            "grand_total": float(subtotal + tax_total), "tax_mode": payload.tax_mode,
        }
    except Exception:
        await db.rollback()
        raise

# -------------------------------------------------------------------
# Sales
# -------------------------------------------------------------------
@app.get("/api/sales")
async def list_sales(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Sale).options(joinedload(Sale.customer)).order_by(Sale.id.desc()).limit(100)
    )
    rows = result.unique().scalars().all()
    return [{
        "id": x.id, "invoice_number": x.invoice_number,
        "customer": x.customer.name if x.customer else "Walk-in",
        "invoice_date": x.invoice_date.isoformat(), "tax_mode": x.tax_mode,
        "subtotal": float(x.subtotal), "tax_total": float(x.tax_total), "grand_total": float(x.grand_total)
    } for x in rows]

@app.post("/api/sales", status_code=201)
async def create_sale(payload: SaleCreate, db: AsyncSession = Depends(get_db)):
    try:
        if payload.customer_id:
            customer = await db.get(Party, payload.customer_id)
            if not customer or customer.party_type != "customer":
                raise HTTPException(400, "Valid customer required")
        sale = Sale(
            invoice_number=payload.invoice_number, customer_id=payload.customer_id,
            invoice_date=payload.invoice_date, tax_mode=payload.tax_mode, notes=payload.notes,
        )
        subtotal = Decimal("0")
        tax_total = Decimal("0")
        db.add(sale)
        await db.flush()
        for line in payload.lines:
            result = await db.execute(
                select(Product).where(Product.id == line.product_id).with_for_update()
            )
            product = result.scalar_one_or_none()
            if not product:
                raise HTTPException(404, f"Product {line.product_id} not found")
            if product.stock_quantity < line.quantity:
                raise HTTPException(400, f"Insufficient stock for {product.name}; available: {product.stock_quantity}")
            base = money(line.quantity * line.unit_price)
            tax = money(base * line.gst_rate / Decimal("100")) if payload.tax_mode == "gst" else Decimal("0.00")
            subtotal += base
            tax_total += tax
            db.add(SaleLine(
                sale_id=sale.id, product_id=product.id, quantity=line.quantity,
                unit_price=line.unit_price,
                gst_rate=line.gst_rate if payload.tax_mode == "gst" else 0,
                line_total=base + tax,
            ))
            product.stock_quantity -= line.quantity
            db.add(StockMovement(product_id=product.id, movement_type="sale",
                                 quantity_change=-line.quantity, reference=payload.invoice_number))
        sale.subtotal = subtotal
        sale.tax_total = tax_total
        sale.grand_total = subtotal + tax_total
        await db.commit()
        return {
            "id": sale.id, "invoice_number": sale.invoice_number,
            "subtotal": float(subtotal), "tax_total": float(tax_total),
            "grand_total": float(subtotal + tax_total), "tax_mode": payload.tax_mode,
        }
    except Exception:
        await db.rollback()
        raise

# -------------------------------------------------------------------
# Inventory movements
# -------------------------------------------------------------------
@app.get("/api/inventory/movements")
async def inventory_movements(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StockMovement).options(joinedload(StockMovement.product))
        .order_by(StockMovement.id.desc()).limit(200)
    )
    rows = result.unique().scalars().all()
    return [{
        "id": x.id, "product": x.product.name, "sku": x.product.sku,
        "movement_type": x.movement_type, "quantity_change": float(x.quantity_change),
        "reference": x.reference, "created_at": x.created_at.isoformat()
    } for x in rows]


