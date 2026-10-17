"""SQL servido pelo Lakehouse//RT. Todas as consultas leem direto as tabelas Delta do Unity Catalog."""
import os

C = os.environ["DEMO_CATALOG"]
S = os.environ.get("DEMO_SCHEMA", "rt_simulado")
T = f"{C}.{S}"

# Notas ao vivo de cada aluno na rodada (questões anuladas contam ponto para todos)
_NOTAS = f"""
notas AS (
  SELECT r.aluno_id,
         count(*) AS respondidas,
         sum(CASE WHEN an.numero IS NOT NULL OR r.alternativa = q.gabarito THEN 1 ELSE 0 END) AS acertos
  FROM {T}.respostas r
  JOIN {T}.questoes q ON q.simulado_id = r.simulado_id AND q.numero = r.numero
  LEFT JOIN (SELECT DISTINCT numero FROM {T}.anulacoes WHERE simulado_id = :sim AND rodada = :rod) an ON an.numero = r.numero
  WHERE r.simulado_id = :sim AND r.rodada = :rod
  GROUP BY r.aluno_id
)"""

KPIS = f"""
SELECT count(*) AS respostas,
       count(DISTINCT aluno_id) AS alunos_respondendo,
       sum(CASE WHEN respondido_em > current_timestamp() - INTERVAL 10 SECONDS THEN 1 ELSE 0 END) / 10.0 AS taxa_10s,
       CAST(max(respondido_em) AS STRING) AS ultima,
       CAST(current_timestamp() AS STRING) AS agora
FROM {T}.respostas WHERE simulado_id = :sim AND rodada = :rod"""

SESSOES = f"""
SELECT sum(CASE WHEN evento = 'login' THEN 1 ELSE 0 END) AS logins,
       sum(CASE WHEN evento = 'fim' THEN 1 ELSE 0 END) AS finalizados,
       sum(CASE WHEN evento = 'login' AND dispositivo = 'app' THEN 1 ELSE 0 END) AS via_app
FROM {T}.sessoes WHERE simulado_id = :sim AND rodada = :rod"""

POR_SEGUNDO = f"""
SELECT CAST(date_trunc('SECOND', respondido_em) AS STRING) AS seg, count(*) AS n
FROM {T}.respostas
WHERE simulado_id = :sim AND rodada = :rod AND respondido_em > current_timestamp() - INTERVAL 60 SECONDS
GROUP BY 1 ORDER BY 1"""

POR_UF = f"""
WITH {_NOTAS}
SELECT f.uf, f.regiao, count(*) AS alunos, round(100.0 * sum(n.acertos) / sum(n.respondidas), 1) AS aproveitamento
FROM notas n JOIN {T}.alunos a ON a.aluno_id = n.aluno_id JOIN {T}.faculdades f ON f.faculdade_id = a.faculdade_id
GROUP BY f.uf, f.regiao"""

TOP10 = f"""
WITH {_NOTAS}
SELECT n.aluno_id, a.nome, f.nome AS faculdade, f.uf, n.acertos, n.respondidas,
       round(100.0 * n.acertos / n.respondidas, 1) AS aproveitamento
FROM notas n JOIN {T}.alunos a ON a.aluno_id = n.aluno_id JOIN {T}.faculdades f ON f.faculdade_id = a.faculdade_id
ORDER BY n.acertos DESC, n.respondidas ASC, n.aluno_id
LIMIT 10"""

TOP_FACULDADES = f"""
WITH {_NOTAS}
SELECT f.nome AS faculdade, f.uf, count(*) AS alunos, round(100.0 * sum(n.acertos) / sum(n.respondidas), 1) AS aproveitamento
FROM notas n JOIN {T}.alunos a ON a.aluno_id = n.aluno_id JOIN {T}.faculdades f ON f.faculdade_id = a.faculdade_id
GROUP BY f.nome, f.uf HAVING count(*) >= 50
ORDER BY aproveitamento DESC LIMIT 8"""

# ---------- Painel do aluno ----------
POSICAO = f"""
WITH {_NOTAS},
eu AS (SELECT * FROM notas WHERE aluno_id = :aluno)
SELECT a.aluno_id, a.nome, a.especialidade_alvo, f.nome AS faculdade, f.uf, f.faculdade_id,
       eu.acertos, eu.respondidas,
       (SELECT count(*) FROM notas n WHERE n.acertos > eu.acertos) + 1 AS posicao,
       (SELECT count(*) FROM notas) AS total,
       (SELECT count(*) FROM notas n JOIN {T}.alunos a2 ON a2.aluno_id = n.aluno_id
         WHERE a2.faculdade_id = a.faculdade_id AND n.acertos > eu.acertos) + 1 AS posicao_faculdade,
       (SELECT count(*) FROM notas n JOIN {T}.alunos a2 ON a2.aluno_id = n.aluno_id
         WHERE a2.faculdade_id = a.faculdade_id) AS total_faculdade
FROM eu JOIN {T}.alunos a ON a.aluno_id = eu.aluno_id JOIN {T}.faculdades f ON f.faculdade_id = a.faculdade_id"""

# Consulta "leve" típica do app do aluno: o próprio desempenho por área (lookup seletivo)
MEU_DESEMPENHO = f"""
SELECT q.area, count(*) AS respondidas,
       sum(CASE WHEN r.alternativa = q.gabarito THEN 1 ELSE 0 END) AS acertos
FROM {T}.respostas r JOIN {T}.questoes q ON q.simulado_id = r.simulado_id AND q.numero = r.numero
WHERE r.simulado_id = :sim AND r.rodada = :rod AND r.aluno_id = :aluno
GROUP BY q.area"""

AREAS_NACIONAL = f"""
SELECT q.area,
       round(100.0 * avg(CASE WHEN r.alternativa = q.gabarito THEN 1 ELSE 0 END), 1) AS nacional,
       round(100.0 * avg(CASE WHEN a.faculdade_id = :fac THEN CASE WHEN r.alternativa = q.gabarito THEN 1 ELSE 0 END END), 1) AS faculdade
FROM {T}.respostas r JOIN {T}.questoes q ON q.simulado_id = r.simulado_id AND q.numero = r.numero
JOIN {T}.alunos a ON a.aluno_id = r.aluno_id
WHERE r.simulado_id = :sim AND r.rodada = :rod
GROUP BY q.area"""

HISTORICO_ALUNO = f"""
SELECT d.simulado_id, s.nome, d.nota, n.nota_nacional
FROM {T}.desempenho_aluno d
JOIN {T}.simulados s ON s.simulado_id = d.simulado_id
JOIN (SELECT simulado_id, round(sum(nota_media * participantes) / sum(participantes), 1) AS nota_nacional
      FROM {T}.desempenho_faculdade GROUP BY simulado_id) n ON n.simulado_id = d.simulado_id
WHERE d.aluno_id = :aluno
ORDER BY d.simulado_id"""

BUSCA_ALUNO = f"""
SELECT a.aluno_id, a.nome, f.nome AS faculdade, f.uf FROM {T}.alunos a JOIN {T}.faculdades f ON f.faculdade_id = a.faculdade_id
WHERE lower(a.nome) LIKE lower(:termo) ORDER BY a.nome LIMIT 8"""

# ---------- Raio-X das questões ----------
QUESTOES = f"""
WITH agg AS (
  SELECT numero, count(*) AS n,
         sum(CASE WHEN alternativa = 'A' THEN 1 ELSE 0 END) AS a,
         sum(CASE WHEN alternativa = 'B' THEN 1 ELSE 0 END) AS b,
         sum(CASE WHEN alternativa = 'C' THEN 1 ELSE 0 END) AS c,
         sum(CASE WHEN alternativa = 'D' THEN 1 ELSE 0 END) AS d,
         sum(CASE WHEN alternativa = 'E' THEN 1 ELSE 0 END) AS e
  FROM {T}.respostas WHERE simulado_id = :sim AND rodada = :rod
  GROUP BY numero
)
SELECT q.numero, q.area, q.tema, q.gabarito,
       coalesce(agg.n, 0) AS n, coalesce(agg.a, 0) AS a, coalesce(agg.b, 0) AS b, coalesce(agg.c, 0) AS c,
       coalesce(agg.d, 0) AS d, coalesce(agg.e, 0) AS e,
       CASE WHEN an.numero IS NOT NULL THEN 1 ELSE 0 END AS anulada,
       h.pct_hist
FROM {T}.questoes q
LEFT JOIN agg ON agg.numero = q.numero
LEFT JOIN (SELECT DISTINCT numero FROM {T}.anulacoes WHERE simulado_id = :sim AND rodada = :rod) an ON an.numero = q.numero
LEFT JOIN (SELECT area, tema, round(avg(pct_acerto), 1) AS pct_hist FROM {T}.estatisticas_questoes GROUP BY area, tema) h
       ON h.area = q.area AND h.tema = q.tema
WHERE q.simulado_id = :sim
ORDER BY q.numero"""

# Escritas vão pelo DBSQL (o Lakehouse//RT é somente leitura)
ANULAR = f"INSERT INTO {T}.anulacoes VALUES (:sim, :rod, :num, :motivo, current_timestamp())"
NOVA_RODADA = f"INSERT INTO {T}.rodadas VALUES (:sim, :rod, current_timestamp(), :part)"
ULTIMA_RODADA = f"SELECT coalesce(max(rodada), 0) AS rodada FROM {T}.rodadas WHERE simulado_id = :sim"
ALUNOS_SIM = f"SELECT aluno_id, habilidade FROM {T}.alunos"
QUESTOES_SIM = f"SELECT numero, gabarito, dificuldade FROM {T}.questoes WHERE simulado_id = :sim"
VOLUME = f"SELECT count(*) AS linhas FROM {T}.respostas"
# Limpeza ao encerrar: remove tudo que é ao vivo e mantém o histórico (rodada 0), dimensões e gold.
# A tabela `rodadas` fica, para a numeração seguir crescente (o Zerobus é at-least-once).
CONTAGEM_RODADA = f"""
SELECT (SELECT count(*) FROM {T}.respostas WHERE simulado_id = :sim AND rodada = :rod) AS respostas,
       (SELECT count(*) FROM {T}.sessoes WHERE simulado_id = :sim AND rodada = :rod) AS sessoes"""
LIMPEZA = [
    f"DELETE FROM {T}.respostas WHERE rodada > 0",
    f"DELETE FROM {T}.sessoes WHERE rodada > 0",
    f"DELETE FROM {T}.anulacoes",
]
