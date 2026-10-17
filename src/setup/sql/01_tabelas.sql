USE CATALOG `{catalog}`;
USE SCHEMA `{schema}`;

-- Alvo do Zerobus: respostas dos alunos (histórico + ao vivo)
CREATE TABLE IF NOT EXISTS respostas (
  simulado_id     INT,
  rodada          INT,
  aluno_id        INT,
  numero          INT,
  alternativa     STRING,
  tempo_resposta_s INT,
  dispositivo     STRING,
  respondido_em   TIMESTAMP
) CLUSTER BY (simulado_id, rodada, aluno_id)
COMMENT 'Respostas do simulado. Ao vivo chegam via Zerobus.'
TBLPROPERTIES ('delta.enableRowTracking' = 'true');

-- Alvo do Zerobus: eventos de sessão (login / início / fim)
CREATE TABLE IF NOT EXISTS sessoes (
  simulado_id INT,
  rodada      INT,
  aluno_id    INT,
  evento      STRING,
  dispositivo STRING,
  ocorrido_em TIMESTAMP
) CLUSTER BY (simulado_id, rodada, evento)
COMMENT 'Eventos de sessão dos alunos via Zerobus.';

-- Controle da demo (escrito pelo app via DBSQL; lido pelo RT)
CREATE TABLE IF NOT EXISTS rodadas (
  simulado_id INT, rodada INT, aberta_em TIMESTAMP, participantes INT
) COMMENT 'Cada abertura de prova ao vivo gera uma rodada.';

CREATE TABLE IF NOT EXISTS anulacoes (
  simulado_id INT, rodada INT, numero INT, motivo STRING, anulada_em TIMESTAMP
) COMMENT 'Questões anuladas pela coordenação.';
