import os
import sys
import traceback

# Add parent directory to sys.path so app.main can be resolved on Vercel
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from app.main import app
except BaseException:
    err_tb = traceback.format_exc()
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="Wholesale Desk API - Startup Diagnostic", docs_url=None, redoc_url=None)

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    async def fallback_any(full_path: str = ""):
        return HTMLResponse(
            f"<!DOCTYPE html><html><head><title>Startup Diagnostic</title>"
            f"<style>body{{font-family:system-ui,sans-serif;padding:32px;background:#0f172a;color:#f8fafc;}}"
            f"pre{{background:#1e293b;padding:20px;border-radius:10px;overflow-x:auto;color:#38bdf8;border:1px solid #334155;}}"
            f"h2{{color:#f43f5e;}}</style></head><body>"
            f"<h2>Wholesale Desk API - Startup Diagnostic</h2>"
            f"<p>FastAPI failed to initialize on Vercel. Full traceback below:</p>"
            f"<pre>{err_tb}</pre>"
            f"</body></html>",
            status_code=500,
        )

    @app.get("/")
    async def fallback_root():
        return await fallback_any("")
