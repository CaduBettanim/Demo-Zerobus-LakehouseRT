USE CATALOG `{catalog}`;
USE SCHEMA `{schema}`;

-- Histórico: 24 simulados anteriores (~80% de participação, 120 questões cada)
INSERT INTO respostas
WITH part AS (
  SELECT s.simulado_id, s.data_aplicacao, a.aluno_id, a.habilidade
  FROM simulados s CROSS JOIN alunos a
  WHERE s.simulado_id <= 24 AND pmod(hash(s.simulado_id, a.aluno_id, 'p'), 100) < 80
),
resp AS (
  SELECT p.simulado_id, p.aluno_id, q.numero, q.gabarito, p.data_aplicacao,
         0.2 + 0.8 / (1 + exp(-(1.3 * (p.habilidade + 0.25 * (p.simulado_id - 12) / 12.0) - q.dificuldade))) AS p_acerto,
         (pmod(hash(p.simulado_id, p.aluno_id, q.numero, 'r'), 100000)) / 100000.0 AS u,
         pmod(hash(p.simulado_id, p.aluno_id, q.numero, 'w'), 4) AS k,
         pmod(hash(p.simulado_id, p.aluno_id, q.numero, 't'), 1000) AS rt
  FROM part p JOIN questoes q ON q.simulado_id = p.simulado_id
)
SELECT
  simulado_id, 0 AS rodada, aluno_id, numero,
  CASE WHEN u < p_acerto THEN gabarito
       ELSE element_at(array_except(array('A','B','C','D','E'), array(gabarito)), CAST(k + 1 AS INT)) END AS alternativa,
  CAST(25 + rt % 200 AS INT) AS tempo_resposta_s,
  CASE WHEN rt % 10 < 7 THEN 'app' ELSE 'web' END AS dispositivo,
  CAST(data_aplicacao AS TIMESTAMP) + make_interval(0, 0, 0, 0, 13, 0, numero * 100 + rt % 90) AS respondido_em
FROM resp;
