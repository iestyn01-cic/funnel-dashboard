# Patch psycopg2.connect to return None on failure instead of raising
# This allows the app to fall back to file-based storage when DB is unreachable
try:
    import psycopg2
    _orig_connect = psycopg2.connect
    def _safe_connect(*args, **kwargs):
        try:
            return _orig_connect(*args, **kwargs)
        except Exception:
            return None
    psycopg2.connect = _safe_connect
except Exception:
    pass
