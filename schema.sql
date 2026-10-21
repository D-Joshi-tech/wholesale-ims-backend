-- Wholesale IMS Schema for PostgreSQL with pgvector
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(80) UNIQUE NOT NULL,
    name VARCHAR(240) NOT NULL,
    category VARCHAR(120),
    unit VARCHAR(30) DEFAULT 'pcs',
    purchase_price NUMERIC(12, 2) DEFAULT 0,
    selling_price NUMERIC(12, 2) DEFAULT 0,
    gst_rate NUMERIC(5, 2) DEFAULT 0,
    stock_quantity NUMERIC(14, 3) DEFAULT 0,
    reorder_level NUMERIC(14, 3) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    embedding vector(384)
);

CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS products_embedding_hnsw_idx ON products USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS parties (
    id SERIAL PRIMARY KEY,
    party_type VARCHAR(20) NOT NULL,
    name VARCHAR(240) NOT NULL,
    phone VARCHAR(40),
    email VARCHAR(240),
    gstin VARCHAR(15),
    address TEXT,
    state_code VARCHAR(2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_parties_type ON parties(party_type);
CREATE INDEX IF NOT EXISTS idx_parties_name ON parties(name);

CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    document_number VARCHAR(50) UNIQUE NOT NULL,
    supplier_id INTEGER NOT NULL REFERENCES parties(id),
    document_date DATE DEFAULT CURRENT_DATE,
    tax_mode VARCHAR(10) DEFAULT 'gst',
    subtotal NUMERIC(14, 2) DEFAULT 0,
    tax_total NUMERIC(14, 2) DEFAULT 0,
    grand_total NUMERIC(14, 2) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_purchases_doc_num ON purchases(document_number);

CREATE TABLE IF NOT EXISTS purchase_lines (
    id SERIAL PRIMARY KEY,
    purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity NUMERIC(14, 3) NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    gst_rate NUMERIC(5, 2) DEFAULT 0,
    line_total NUMERIC(14, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES parties(id),
    invoice_date DATE DEFAULT CURRENT_DATE,
    tax_mode VARCHAR(10) DEFAULT 'gst',
    subtotal NUMERIC(14, 2) DEFAULT 0,
    tax_total NUMERIC(14, 2) DEFAULT 0,
    grand_total NUMERIC(14, 2) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sales_inv_num ON sales(invoice_number);

CREATE TABLE IF NOT EXISTS sale_lines (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity NUMERIC(14, 3) NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    gst_rate NUMERIC(5, 2) DEFAULT 0,
    line_total NUMERIC(14, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    movement_type VARCHAR(30) NOT NULL,
    quantity_change NUMERIC(14, 3) NOT NULL,
    reference VARCHAR(80),
    note TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id ON stock_movements(product_id);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    picture VARCHAR(512),
    role VARCHAR(50) DEFAULT 'viewer',
    is_allowed BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITHOUT TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Ensure initial admin user exists
INSERT INTO users (email, name, role, is_allowed)
VALUES ('dhyeyjoshi007@gmail.com', 'Dhyey Joshi', 'admin', TRUE)
ON CONFLICT (email) DO UPDATE SET role = 'admin', is_allowed = TRUE;

-- Ensure ims_user owns and has full access
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ims_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ims_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ims_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ims_user;

