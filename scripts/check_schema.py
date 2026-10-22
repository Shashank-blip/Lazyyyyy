from dotenv import load_dotenv

load_dotenv()

from app.db import connect, ensure_schema, uses_bm25

with connect() as conn:
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_textsearch') ORDER BY 1"
    ).fetchall()
    indexes = conn.execute(
        """
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'lazyyyyy' AND tablename = 'pile_items'
        ORDER BY 1
        """
    ).fetchall()

print("extensions", [row["extname"] for row in rows])
print("bm25", uses_bm25())
print("indexes", [row["indexname"] for row in indexes])
