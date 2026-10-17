"""Cliente assíncrono da Statement Execution API (funciona no warehouse Lakehouse//RT e no DBSQL)."""
import asyncio
import time

import httpx
from databricks.sdk import WorkspaceClient

_w = WorkspaceClient()
_host = _w.config.host.rstrip("/")
_client = httpx.AsyncClient(
    timeout=httpx.Timeout(60.0),
    limits=httpx.Limits(max_connections=400, max_keepalive_connections=400),
)


def _headers() -> dict:
    return _w.config.authenticate()


class SqlError(Exception):
    pass


def _param(name, value):
    if isinstance(value, bool):
        return {"name": name, "value": str(value).lower(), "type": "BOOLEAN"}
    if isinstance(value, int):
        return {"name": name, "value": str(value), "type": "INT"}
    return {"name": name, "value": str(value), "type": "STRING"}


async def query(warehouse_id: str, sql: str, params: dict | None = None):
    """Executa SQL e retorna (linhas como dicts, ms medidos pelo cliente)."""
    body = {
        "statement": sql,
        "warehouse_id": warehouse_id,
        "wait_timeout": "30s",
        "format": "JSON_ARRAY",
        "disposition": "INLINE",
        "on_wait_timeout": "CONTINUE",
    }
    if params:
        body["parameters"] = [_param(k, v) for k, v in params.items()]
    t0 = time.perf_counter()
    r = await _client.post(f"{_host}/api/2.0/sql/statements", json=body, headers=_headers())
    r.raise_for_status()
    d = r.json()
    while d["status"]["state"] in ("PENDING", "RUNNING"):
        await asyncio.sleep(0.2)
        r = await _client.get(f"{_host}/api/2.0/sql/statements/{d['statement_id']}", headers=_headers())
        r.raise_for_status()
        d = r.json()
    ms = round((time.perf_counter() - t0) * 1000)
    if d["status"]["state"] != "SUCCEEDED":
        raise SqlError(d["status"].get("error", {}).get("message", d["status"]["state"]))
    cols = [c["name"] for c in d["manifest"]["schema"]["columns"]]
    types = [c["type_name"] for c in d["manifest"]["schema"]["columns"]]
    rows = []
    for row in (d.get("result") or {}).get("data_array") or []:
        rec = {}
        for c, t, v in zip(cols, types, row):
            if v is None:
                rec[c] = None
            elif t in ("INT", "LONG", "SHORT", "BYTE"):
                rec[c] = int(v)
            elif t in ("DOUBLE", "FLOAT", "DECIMAL"):
                rec[c] = float(v)
            elif t == "BOOLEAN":
                rec[c] = v in ("true", True)
            else:
                rec[c] = v
        rows.append(rec)
    return rows, ms
