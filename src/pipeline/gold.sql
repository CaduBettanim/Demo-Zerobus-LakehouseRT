-- Camada gold: desempenho histórico (simulados anteriores), servida pelo Lakehouse//RT

CREATE OR REFRESH MATERIALIZED VIEW desempenho_aluno
CLUSTER BY (aluno_id, simulado_id)
COMMENT 'Nota por aluno e simulado (histórico), com acertos por grande área'
AS SELECT
  r.simulado_id, r.aluno_id, a.faculdade_id, f.uf,
  count(*) AS respondidas,
  sum(CASE WHEN r.alternativa = q.gabarito THEN 1 ELSE 0 END) AS acertos,
  round(100.0 * sum(CASE WHEN r.alternativa = q.gabarito THEN 1 ELSE 0 END) / 120, 1) AS nota,
  sum(CASE WHEN q.area = 'Clínica Médica' AND r.alternativa = q.gabarito THEN 1 ELSE 0 END) AS ac_clinica,
  sum(CASE WHEN q.area = 'Cirurgia' AND r.alternativa = q.gabarito THEN 1 ELSE 0 END) AS ac_cirurgia,
  sum(CASE WHEN q.area = 'Pediatria' AND r.alternativa = q.gabarito THEN 1 ELSE 0 END) AS ac_pediatria,
  sum(CASE WHEN q.area = 'Ginecologia e Obstetrícia' AND r.alternativa = q.gabarito THEN 1 ELSE 0 END) AS ac_go,
  sum(CASE WHEN q.area = 'Medicina Preventiva' AND r.alternativa = q.gabarito THEN 1 ELSE 0 END) AS ac_preventiva
FROM respostas r
JOIN questoes q ON q.simulado_id = r.simulado_id AND q.numero = r.numero
JOIN alunos a ON a.aluno_id = r.aluno_id
JOIN faculdades f ON f.faculdade_id = a.faculdade_id
WHERE r.rodada = 0
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW desempenho_faculdade
COMMENT 'Nota média por faculdade e simulado (histórico)'
AS SELECT simulado_id, faculdade_id, uf, count(*) AS participantes, round(avg(nota), 2) AS nota_media,
          round(percentile_approx(nota, 0.9), 1) AS nota_p90
FROM desempenho_aluno GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW estatisticas_questoes
COMMENT 'Percentual de acerto histórico por questão'
AS SELECT r.simulado_id, r.numero, q.area, q.tema, count(*) AS respostas,
          round(100.0 * avg(CASE WHEN r.alternativa = q.gabarito THEN 1 ELSE 0 END), 1) AS pct_acerto
FROM respostas r JOIN questoes q ON q.simulado_id = r.simulado_id AND q.numero = r.numero
WHERE r.rodada = 0
GROUP BY ALL;
