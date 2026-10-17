"""MedPrime Residência — Simulado Nacional ao vivo. Demo de Lakehouse//RT + Zerobus."""
import asyncio
import logging
import os
import random
import statistics
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import consultas as Q
from simulador import Simulador
from sql_client import SqlError, query

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

RT = os.environ["RT_WAREHOUSE_ID"]
DBSQL = os.environ["DBSQL_WAREHOUSE_ID"]
SIM = 25

app = FastAPI(title="MedPrime Residência – Simulado ao vivo")
sim = Simulador(Q.C, Q.S)
estado = {"rodada": 0}
_cache = {}


async def rt(sql, **p):
    return await query(RT, sql, {"sim": SIM, "rod": estado["rodada"], **p})


async def db(sql, **p):
    return await query(DBSQL, sql, {"sim": SIM, "rod": estado["rodada"], **p})


@app.on_event("startup")
async def _startup():
    try:
        rows, _ = await db(Q.ULTIMA_RODADA)
        estado["rodada"] = rows[0]["rodada"]
    except Exception:  # noqa: BLE001
        log.exception("não consegui ler a última rodada")


def _erro(e):
    log.exception("erro")
    raise HTTPException(500, str(e))


# ---------------- Simulador ----------------
class Abrir(BaseModel):
    participantes: int = 50000
    taxa: int = 3000


@app.post("/api/simulador/abrir")
async def abrir(a: Abrir):
    try:
        if "alunos" not in _cache:
            (_cache["alunos"], _), (_cache["questoes"], _) = await asyncio.gather(db(Q.ALUNOS_SIM), db(Q.QUESTOES_SIM))
        nova = estado["rodada"] + 1
        await query(DBSQL, Q.NOVA_RODADA, {"sim": SIM, "rod": nova, "part": a.participantes})
        estado["rodada"] = nova
        sim.abrir(nova, _cache["alunos"], _cache["questoes"], a.participantes, a.taxa)
        return sim.estado()
    except Exception as e:  # noqa: BLE001
        _erro(e)


class Taxa(BaseModel):
    taxa: int


@app.post("/api/simulador/taxa")
async def taxa(t: Taxa):
    sim.taxa = max(100, min(t.taxa, 12000))
    return sim.estado()


@app.post("/api/simulador/pausar")
async def pausar():
    sim.pausado = not sim.pausado
    return sim.estado()


@app.post("/api/simulador/encerrar")
async def encerrar():
    """Para o simulador (flush + close dos streams Zerobus) e apaga os dados ao vivo das provas."""
    await asyncio.to_thread(sim.encerrar)
    t0 = time.perf_counter()
    # O ack do Zerobus garante durabilidade, mas a materialização no Delta chega em lotes de ~5 s.
    # Espera a tabela conter tudo o que foi enviado antes de apagar (senão registros chegam depois do DELETE).
    esperado_r, esperado_s = sim.enviadas, sim.sessoes_enviadas
    while time.perf_counter() - t0 < 45:
        try:
            rows, _ = await db(Q.CONTAGEM_RODADA)
            if rows[0]["respostas"] >= esperado_r and rows[0]["sessoes"] >= esperado_s:
                break
        except Exception:  # noqa: BLE001
            log.exception("contagem da rodada")
        await asyncio.sleep(2)
    try:
        res = await asyncio.gather(*(query(DBSQL, sql) for sql in Q.LIMPEZA))
    except Exception as e:  # noqa: BLE001
        _erro(e)
    removidas = [r[0][0].get("num_affected_rows", 0) if r[0] else 0 for r in res]
    return {**sim.estado(), "limpeza": {"respostas": removidas[0], "sessoes": removidas[1], "anulacoes": removidas[2],
                                        "ms": round((time.perf_counter() - t0) * 1000)}}


@app.get("/api/estado")
async def get_estado():
    return {**sim.estado(), "rodada": estado["rodada"]}


# ---------------- Coordenação ao vivo ----------------
async def _timed(name, coro, out, ms):
    rows, t = await coro
    out[name] = rows
    ms[name] = t


@app.get("/api/ao-vivo")
async def ao_vivo():
    out, ms = {}, {}
    try:
        await asyncio.gather(
            _timed("kpis", rt(Q.KPIS), out, ms),
            _timed("sessoes", rt(Q.SESSOES), out, ms),
            _timed("por_segundo", rt(Q.POR_SEGUNDO), out, ms),
            _timed("por_uf", rt(Q.POR_UF), out, ms),
            _timed("top10", rt(Q.TOP10), out, ms),
            _timed("faculdades", rt(Q.TOP_FACULDADES), out, ms),
        )
    except Exception as e:  # noqa: BLE001
        _erro(e)
    return {"dados": out, "ms": ms, "rodada": estado["rodada"], "simulador": sim.estado()}


# ---------------- Painel do aluno ----------------
@app.get("/api/aluno/aleatorio")
async def aluno_aleatorio():
    ids = sim.alunos_ativos(1)
    if not ids:
        return {"aluno_id": random.randint(1, 50000)}
    return {"aluno_id": ids[0]}


@app.get("/api/aluno/busca")
async def busca(q: str):
    rows, ms = await query(RT, Q.BUSCA_ALUNO, {"termo": f"%{q}%"})
    return {"dados": rows, "ms": ms}


@app.get("/api/aluno/{aluno_id}")
async def aluno(aluno_id: int):
    out, ms = {}, {}
    try:
        await asyncio.gather(
            _timed("posicao", rt(Q.POSICAO, aluno=aluno_id), out, ms),
            _timed("meu", rt(Q.MEU_DESEMPENHO, aluno=aluno_id), out, ms),
            _timed("historico", query(RT, Q.HISTORICO_ALUNO, {"aluno": aluno_id}), out, ms),
        )
        fac = out["posicao"][0]["faculdade_id"] if out["posicao"] else 0
        await _timed("areas", rt(Q.AREAS_NACIONAL, fac=fac), out, ms)
    except Exception as e:  # noqa: BLE001
        _erro(e)
    return {"dados": out, "ms": ms}


# ---------------- Raio-X das questões ----------------
@app.get("/api/questoes")
async def questoes():
    try:
        rows, ms = await rt(Q.QUESTOES)
    except Exception as e:  # noqa: BLE001
        _erro(e)
    for r in rows:
        dist = {k: r[k.lower()] for k in "ABCDE"}
        n = r["n"] or 0
        top = max(dist, key=dist.get) if n else None
        r["mais_marcada"] = top
        r["pct_acerto"] = round(100 * dist[r["gabarito"]] / n, 1) if n else None
        r["suspeita"] = bool(n >= 200 and top != r["gabarito"] and dist[top] / n > 0.4 and not r["anulada"])
    return {"dados": rows, "ms": ms}


class Anular(BaseModel):
    motivo: str = "Gabarito divergente da alternativa tecnicamente correta"


@app.post("/api/questoes/{numero}/anular")
async def anular(numero: int, a: Anular):
    try:
        top_antes, _ = await rt(Q.TOP10)
        _, ms_write = await db(Q.ANULAR, num=numero, motivo=a.motivo)
        t0 = time.perf_counter()
        top_depois, ms_rt = await rt(Q.TOP10)
        return {"ms_escrita_dbsql": ms_write, "ms_ranking_rt": ms_rt,
                "top_antes": top_antes, "top_depois": top_depois,
                "total_ms": round((time.perf_counter() - t0) * 1000) + ms_write}
    except Exception as e:  # noqa: BLE001
        _erro(e)


# ---------------- Teste de escala ----------------
escala = {"rodando": False, "usuarios": 0, "lat": [], "ok": 0, "erros": 0, "inicio": 0, "serie": [], "ultimo_erro": None}


async def _usuario(fim):
    while escala["rodando"] and time.time() < fim:
        ids = sim.alunos_ativos(1) or [random.randint(1, 50000)]
        try:
            _, ms = await rt(Q.MEU_DESEMPENHO, aluno=ids[0])
            escala["lat"].append((time.time(), ms))
            escala["ok"] += 1
        except Exception as e:  # noqa: BLE001
            escala["erros"] += 1
            escala["ultimo_erro"] = str(e)[:200]
            await asyncio.sleep(0.5)


async def _rodar_escala(usuarios, duracao):
    fim = time.time() + duracao
    # rampa: adiciona usuários em 5 degraus
    tasks = []
    for passo in range(5):
        if not escala["rodando"]:
            break
        alvo = usuarios * (passo + 1) // 5
        while len(tasks) < alvo:
            tasks.append(asyncio.create_task(_usuario(fim)))
        escala["usuarios"] = len(tasks)
        await asyncio.sleep(min(4, duracao / 6))
    await asyncio.gather(*tasks, return_exceptions=True)
    escala["rodando"] = False
    escala["fim"] = time.time()


class Escala(BaseModel):
    usuarios: int = 100
    duracao: int = 60


@app.post("/api/escala/iniciar")
async def escala_iniciar(e: Escala):
    if escala["rodando"]:
        return escala_estado()
    escala.update(rodando=True, fim=None, usuarios=0, lat=[], ok=0, erros=0, inicio=time.time(), serie=[], ultimo_erro=None)
    asyncio.create_task(_rodar_escala(max(1, min(e.usuarios, 100)), max(10, min(e.duracao, 180))))
    return escala_estado()


@app.post("/api/escala/parar")
async def escala_parar():
    escala["rodando"] = False
    return escala_estado()


@app.get("/api/escala/servidor")
async def escala_servidor():
    """Latência medida dentro do motor Lakehouse//RT (query history) durante o último teste."""
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import QueryFilter, TimeRange

    def _coletar():
        w = WorkspaceClient()
        ini = int(escala["inicio"] * 1000)
        fim = int((escala.get("fim") or time.time()) * 1000) + 2000
        filtro = QueryFilter(warehouse_ids=[RT], query_start_time_range=TimeRange(start_time_ms=ini, end_time_ms=fim))
        durs, tok = [], None
        for _ in range(20):
            res = w.query_history.list(filter_by=filtro, max_results=1000, page_token=tok)
            durs += [q.duration for q in (res.res or []) if q.duration is not None]
            tok = res.next_page_token
            if not res.has_next_page:
                break
        return sorted(durs)

    if not escala["inicio"]:
        return {"n": 0}
    durs = await asyncio.to_thread(_coletar)
    n = len(durs)
    if not n:
        return {"n": 0}
    return {"n": n, "p50": durs[n // 2], "p95": durs[int(n * 0.95)], "p99": durs[min(n - 1, int(n * 0.99))]}


@app.get("/api/escala/estado")
def escala_estado():
    agora = time.time()
    janela = [ms for t, ms in escala["lat"] if agora - t <= 5]
    qps = len([1 for t, _ in escala["lat"] if agora - t <= 3]) / 3
    def pct(xs, p):
        if not xs:
            return None
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(p * len(xs)))]
    ponto = {"t": round(agora - escala["inicio"], 1), "qps": round(qps, 1), "p50": pct(janela, 0.5),
             "p95": pct(janela, 0.95), "usuarios": escala["usuarios"]}
    if escala["rodando"] or (escala["serie"] and escala["serie"][-1]["t"] != ponto["t"]):
        if escala["rodando"]:
            escala["serie"].append(ponto)
            escala["serie"] = escala["serie"][-300:]
    todas = [ms for _, ms in escala["lat"]]
    return {"rodando": escala["rodando"], "usuarios": escala["usuarios"], "ok": escala["ok"], "erros": escala["erros"],
            "atual": ponto, "serie": escala["serie"], "ultimo_erro": escala["ultimo_erro"],
            "p50_total": pct(todas, 0.5), "p95_total": pct(todas, 0.95), "p99_total": pct(todas, 0.99)}


# ---------------- RT vs DBSQL ----------------
@app.get("/api/comparar")
async def comparar(tipo: str = "aluno", n: int = 5):
    n = max(1, min(n, 10))
    res = {"rt": [], "dbsql": []}
    try:
        for _ in range(n):
            aluno = (sim.alunos_ativos(1) or [random.randint(1, 50000)])[0]
            sql = Q.MEU_DESEMPENHO if tipo == "aluno" else Q.POSICAO
            p = {"sim": SIM, "rod": estado["rodada"], "aluno": aluno}
            (_, ms_rt), (_, ms_db) = await asyncio.gather(query(RT, sql, p), query(DBSQL, sql, p))
            res["rt"].append(ms_rt)
            res["dbsql"].append(ms_db)
    except Exception as e:  # noqa: BLE001
        _erro(e)
    return {"tipo": tipo, **res, "mediana_rt": statistics.median(res["rt"]), "mediana_dbsql": statistics.median(res["dbsql"]),
            "sql": (Q.MEU_DESEMPENHO if tipo == "aluno" else Q.POSICAO).strip()}


@app.get("/api/config")
async def config():
    return {"catalog": Q.C, "schema": Q.S, "rt_warehouse_id": RT, "dbsql_warehouse_id": DBSQL,
            "zerobus_endpoint": sim.endpoint}


@app.get("/api/volume")
async def volume():
    rows, ms = await query(RT, Q.VOLUME)
    return {"linhas": rows[0]["linhas"], "ms": ms}


@app.exception_handler(SqlError)
async def _sql_err(_, e):
    raise HTTPException(500, str(e))


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
