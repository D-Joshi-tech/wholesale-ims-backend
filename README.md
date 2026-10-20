# Wholesale Desk — Backend API

High-performance Wholesale Inventory Management & Billing API built with **FastAPI**, **SQLAlchemy 2.0 (asyncpg)**, **PostgreSQL**, and **pgvector**.

---

## 🚀 Local Development

### 1. Requirements
* Python 3.11+
* PostgreSQL with `pgvector` extension enabled

### 2. Setup Virtual Environment
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env`:
```env
DATABASE_URL=postgresql+asyncpg://wholesale_user:change_this_password@localhost:5432/wholesale_db
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
PORT=8000
```

### 4. Run the Server
```bash
uvicorn app.main:app --reload --port 8000
```
* **API root**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Interactive Docs (Swagger)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## ☁️ Cloud Deployment (Render / Railway / Supabase / Fly.io / VPS)

### Database:
Use any PostgreSQL database with `pgvector` enabled (e.g. [Supabase](https://supabase.com), [Neon](https://neon.tech), [Render Postgres](https://render.com)).
Set your connection string as `DATABASE_URL`. The app automatically normalizes `postgres://` and `postgresql://` schemes to `postgresql+asyncpg://`.

### Deploying on Render (Free/Standard):
1. Create a new **Web Service** on [render.com](https://render.com).
2. Connect your `wholesale-ims-backend` GitHub repository.
3. Choose **Docker** or Python environment:
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Under **Environment Variables**, set:
   * `DATABASE_URL`: Your cloud Postgres connection URL.
   * `CORS_ORIGINS`: Comma-separated domains (e.g. `https://your-app.vercel.app,http://localhost:3000`).
   *(Note: Any `*.vercel.app` domain is automatically permitted by default).*

### Deploying with Docker:
```bash
docker build -t wholesale-backend .
docker run -p 8000:8000 -e DATABASE_URL="your_db_url" wholesale-backend
```

---

## 🛠 Tech Stack
* **Framework**: FastAPI
* **ORM & DB**: SQLAlchemy 2 (asyncio), asyncpg, pgvector
* **Semantic Search**: fastembed (`BAAI/bge-small-en-v1.5`, 384 dimensions)
* **Validation**: Pydantic v2
