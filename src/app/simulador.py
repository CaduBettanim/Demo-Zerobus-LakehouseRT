"""Simulador de alunos: gera logins e respostas do simulado ao vivo e envia via Zerobus."""
import logging
import os
import threading
import time

import numpy as np
from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties
from zerobus.sdk.sync import ZerobusSdk

log = logging.getLogger("simulador")

LETRAS = np.array(list("ABCDE"))
N_QUESTOES = 120
# Questão com erro no gabarito oficial: a resposta tecnicamente correta é B (cadastrada como C)
CORRETA_REAL = {47: "B"}


class Simulador:
    def __init__(self, catalog: str, schema: str):
        self.workspace = os.environ.get("DATABRICKS_HOST", "")
        if not self.workspace.startswith("http"):
            self.workspace = "https://" + self.workspace
        # Por padrão usa o service principal do próprio app (injetado pelo Databricks Apps)
        self.client_id = os.environ.get("ZEROBUS_CLIENT_ID") or os.environ.get("DATABRICKS_CLIENT_ID")
        self.client_secret = os.environ.get("ZEROBUS_CLIENT_SECRET") or os.environ.get("DATABRICKS_CLIENT_SECRET")
        self.endpoint = os.environ.get("ZEROBUS_ENDPOINT") or None  # descoberto na 1ª abertura de prova
        self.t_resp = f"{catalog}.{schema}.respostas"
        self.t_sess = f"{catalog}.{schema}.sessoes"
        self.lock = threading.Lock()
        self.thread = None
        self.rodando = False
        self.pausado = False
        self.taxa = 3000
        self.simulado_id = 25
        self.rodada = 0
        self.enviadas = 0
        self.sessoes_enviadas = 0
        self.erro = None
        self.inicio = None
        self.hist = []  # (ts, enviadas) para calcular taxa real
        self.ids = np.array([], dtype=np.int32)
        self.progresso = np.array([], dtype=np.int16)

    # ---------- controle ----------
    def abrir(self, rodada: int, alunos: list, questoes: list, participantes: int, taxa: int):
        self.encerrar()
        rng = np.random.default_rng(rodada)
        alunos = alunos if participantes >= len(alunos) else [alunos[i] for i in rng.choice(len(alunos), participantes, replace=False)]
        self.ids = np.array([a["aluno_id"] for a in alunos], dtype=np.int32)
        self.hab = np.array([a["habilidade"] for a in alunos], dtype=np.float32)
        self.progresso = np.zeros(len(alunos), dtype=np.int16)
        # cada aluno começa a prova por um bloco diferente (como na vida real)
        self.offset = rng.integers(0, N_QUESTOES, len(alunos)).astype(np.int32)
        # login escalonado: todos entram nos primeiros ~25 s
        self.login_em = time.time() + rng.uniform(0, 25, len(alunos))
        self.logado = np.zeros(len(alunos), dtype=bool)
        self.finalizado = np.zeros(len(alunos), dtype=bool)
        self.dispositivo = np.where(rng.random(len(alunos)) < 0.7, "app", "web")
        q = sorted(questoes, key=lambda x: x["numero"])
        self.dif = np.array([x["dificuldade"] for x in q], dtype=np.float32)
        self.correta = np.array([CORRETA_REAL.get(x["numero"], x["gabarito"]) for x in q])
        self.rodada, self.taxa = rodada, taxa
        self.enviadas = self.sessoes_enviadas = 0
        self.erro, self.pausado, self.rodando = None, False, True
        self.inicio = time.time()
        self.hist = []
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def encerrar(self):
        self.rodando = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=15)
        self.thread = None

    def estado(self):
        agora = time.time()
        taxa_real = 0.0
        with self.lock:
            h = [x for x in self.hist if agora - x[0] <= 5]
        if len(h) >= 2 and h[-1][0] > h[0][0]:
            taxa_real = (h[-1][1] - h[0][1]) / (h[-1][0] - h[0][0])
        n = len(self.ids)
        return {
            "rodando": self.rodando, "pausado": self.pausado, "taxa_alvo": self.taxa,
            "taxa_real": round(taxa_real), "rodada": self.rodada, "enviadas": self.enviadas,
            "sessoes_enviadas": self.sessoes_enviadas, "participantes": n,
            "logados": int(self.logado.sum()) if n else 0,
            "finalizados": int(self.finalizado.sum()) if n else 0,
            "erro": self.erro,
            "segundos": round(agora - self.inicio) if self.inicio else 0,
        }

    def alunos_ativos(self, k=1):
        """Alguns alunos que já responderam questões (para o painel do aluno)."""
        if not len(self.ids):
            return []
        idx = np.flatnonzero(self.progresso > 10)
        if not len(idx):
            idx = np.arange(len(self.ids))
        return [int(self.ids[i]) for i in np.random.choice(idx, min(k, len(idx)), replace=False)]

    def _descobrir_endpoint(self):
        """<workspace-id>.zerobus.<região>.<domínio da nuvem> (AWS/Azure)."""
        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient()
        wid = w.get_workspace_id()
        regiao = w.metastores.summary().region
        dominio = "azuredatabricks.net" if "azuredatabricks.net" in self.workspace else "cloud.databricks.com"
        return f"{wid}.zerobus.{regiao}.{dominio}"

    # ---------- geração ----------
    def _stream(self, tabela):
        sdk = ZerobusSdk(self.endpoint, self.workspace)
        opts = StreamConfigurationOptions(record_type=RecordType.JSON)
        return sdk.create_stream(self.client_id, self.client_secret, TableProperties(tabela), opts)

    def _loop(self):
        try:
            if not self.endpoint:
                self.endpoint = self._descobrir_endpoint()
                log.info("Zerobus endpoint: %s", self.endpoint)
            s_resp, s_sess = self._stream(self.t_resp), self._stream(self.t_sess)
        except Exception as e:  # noqa: BLE001
            log.exception("falha abrindo streams")
            self.erro, self.rodando = f"Zerobus: {e}", False
            return
        rng = np.random.default_rng()
        tick = 0.25
        try:
            while self.rodando:
                t0 = time.time()
                if not self.pausado:
                    self._passo(rng, tick, s_resp, s_sess)
                with self.lock:
                    self.hist.append((time.time(), self.enviadas))
                    self.hist = self.hist[-200:]
                if self.finalizado.all():
                    self.rodando = False
                time.sleep(max(0.0, tick - (time.time() - t0)))
        except Exception as e:  # noqa: BLE001
            log.exception("erro no simulador")
            self.erro = str(e)
            self.rodando = False
        finally:
            for s in (s_resp, s_sess):
                try:
                    s.flush()
                    s.close()
                except Exception:  # noqa: BLE001
                    pass

    def _passo(self, rng, tick, s_resp, s_sess):
        agora = time.time()
        ts = int(agora * 1_000_000)
        sess = []
        # logins
        novos = np.flatnonzero(~self.logado & (self.login_em <= agora))
        for i in novos:
            for ev in ("login", "inicio"):
                sess.append({"simulado_id": self.simulado_id, "rodada": self.rodada, "aluno_id": int(self.ids[i]),
                             "evento": ev, "dispositivo": str(self.dispositivo[i]), "ocorrido_em": ts})
        self.logado[novos] = True
        # respostas
        ativos = np.flatnonzero(self.logado & ~self.finalizado)
        n = min(int(self.taxa * tick), len(ativos))
        recs = []
        if n > 0:
            esc = rng.choice(ativos, n, replace=False)
            num = (self.progresso[esc].astype(np.int32) + self.offset[esc]) % N_QUESTOES  # índice 0..119
            logit = 1.3 * self.hab[esc] + 0.25 - self.dif[num]
            p = 0.2 + 0.8 / (1 + np.exp(-logit))
            acerta = rng.random(n) < p
            corretas = self.correta[num]
            k = rng.integers(0, 4, n)
            for j in range(n):
                c = corretas[j]
                if acerta[j]:
                    alt = c
                else:
                    outras = [x for x in "ABCDE" if x != c]
                    alt = outras[k[j]]
                recs.append({"simulado_id": self.simulado_id, "rodada": self.rodada, "aluno_id": int(self.ids[esc[j]]),
                             "numero": int(num[j]) + 1, "alternativa": alt,
                             "tempo_resposta_s": int(rng.integers(20, 220)),
                             "dispositivo": str(self.dispositivo[esc[j]]), "respondido_em": ts})
            self.progresso[esc] += 1
            fim = esc[self.progresso[esc] >= N_QUESTOES]
            for i in fim:
                sess.append({"simulado_id": self.simulado_id, "rodada": self.rodada, "aluno_id": int(self.ids[i]),
                             "evento": "fim", "dispositivo": str(self.dispositivo[i]), "ocorrido_em": ts})
            self.finalizado[fim] = True
        for i in range(0, len(recs), 2000):
            s_resp.ingest_records_offset(recs[i:i + 2000])
        if sess:
            for i in range(0, len(sess), 2000):
                s_sess.ingest_records_offset(sess[i:i + 2000])
        self.enviadas += len(recs)
        self.sessoes_enviadas += len(sess)
