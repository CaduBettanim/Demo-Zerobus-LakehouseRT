"""Benchmark: Databricks SQL Connector (use_kernel=True) no Lakehouse//RT com N threads, cada uma com sua conexão.

Uso: DATABRICKS_CONFIG_PROFILE=<profile> RT_WAREHOUSE_ID=<id> DEMO_CATALOG=<catalogo> [DEMO_SCHEMA=rt_simulado] \
     python scripts/bench_kernel.py <threads> <segundos> <rodada>
"""
import statistics
import sys
import threading
import os
import time

from databricks import sql
from databricks.sdk import WorkspaceClient

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
DUR = int(sys.argv[2]) if len(sys.argv) > 2 else 20
ROD = int(sys.argv[3]) if len(sys.argv) > 3 else 4
w = WorkspaceClient()
tok = w.config.authenticate()["Authorization"].split(" ", 1)[1]
T = f"{os.environ['DEMO_CATALOG']}.{os.environ.get('DEMO_SCHEMA', 'rt_simulado')}"
Q = f"""SELECT q.area, count(*) AS respondidas, sum(CASE WHEN r.alternativa = q.gabarito THEN 1 ELSE 0 END) AS acertos
FROM {T}.respostas r JOIN {T}.questoes q ON q.simulado_id = r.simulado_id AND q.numero = r.numero
WHERE r.simulado_id = 25 AND r.rodada = :rod AND r.aluno_id = :aluno GROUP BY q.area"""
lat, erros = [], []


def worker(i):
    import random
    conn = sql.connect(server_hostname=w.config.host.replace("https://", "").rstrip("/"),
                       http_path=f"/sql/1.0/warehouses/{os.environ['RT_WAREHOUSE_ID']}", access_token=tok, use_kernel=True)
    cur = conn.cursor()
    fim = time.time() + DUR
    while time.time() < fim:
        t0 = time.perf_counter()
        try:
            cur.execute(Q, {"rod": ROD, "aluno": random.randint(1, 50000)})
            cur.fetchall()
            lat.append((time.perf_counter() - t0) * 1000)
        except Exception as e:  # noqa: BLE001
            erros.append(str(e)[:200])
    cur.close()
    conn.close()


ths = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
t0 = time.time()
[t.start() for t in ths]
[t.join() for t in ths]
dt = time.time() - t0
lat.sort()
n = len(lat)
print(f"threads={N} consultas={n} qps={n/dt:.1f} p50={lat[n//2]:.0f}ms p95={lat[int(n*.95)]:.0f}ms erros={len(erros)} {erros[:1]}")
