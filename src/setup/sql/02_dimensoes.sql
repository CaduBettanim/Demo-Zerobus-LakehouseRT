USE CATALOG `{catalog}`;
USE SCHEMA `{schema}`;

-- ============ Faculdades (fictícias) ============
CREATE OR REPLACE TABLE faculdades AS
SELECT
  CAST(id AS INT) AS faculdade_id,
  concat(element_at(array('Faculdade de Ciências Médicas Horizonte','Escola de Medicina Aurora','Faculdade de Medicina Vértice',
                          'Centro Universitário Atlântico','Faculdade de Medicina Serra Azul','Escola Médica Novo Rumo',
                          'Faculdade de Medicina Ipê','Centro Universitário Cerrado Vivo','Escola de Medicina Litoral',
                          'Faculdade de Ciências da Saúde Pampa'), CAST(((id - 1) % 10) + 1 AS INT)), ' – ', cidade) AS nome,
  cidade, uf, regiao
FROM VALUES
  (1,'São Paulo','SP','Sudeste'),(2,'Campinas','SP','Sudeste'),(3,'Ribeirão Preto','SP','Sudeste'),(4,'Rio de Janeiro','RJ','Sudeste'),
  (5,'Niterói','RJ','Sudeste'),(6,'Belo Horizonte','MG','Sudeste'),(7,'Juiz de Fora','MG','Sudeste'),(8,'Montes Claros','MG','Sudeste'),
  (9,'Vitória','ES','Sudeste'),(10,'Curitiba','PR','Sul'),(11,'Londrina','PR','Sul'),(12,'Porto Alegre','RS','Sul'),
  (13,'Florianópolis','SC','Sul'),(14,'Salvador','BA','Nordeste'),(15,'Vitória da Conquista','BA','Nordeste'),(16,'Recife','PE','Nordeste'),
  (17,'Fortaleza','CE','Nordeste'),(18,'Teresina','PI','Nordeste'),(19,'São Luís','MA','Nordeste'),(20,'Natal','RN','Nordeste'),
  (21,'João Pessoa','PB','Nordeste'),(22,'Maceió','AL','Nordeste'),(23,'Aracaju','SE','Nordeste'),(24,'Goiânia','GO','Centro-Oeste'),
  (25,'Brasília','DF','Centro-Oeste'),(26,'Cuiabá','MT','Centro-Oeste'),(27,'Campo Grande','MS','Centro-Oeste'),(28,'Manaus','AM','Norte'),
  (29,'Belém','PA','Norte'),(30,'Palmas','TO','Norte')
  AS t(id, cidade, uf, regiao);

-- ============ Alunos (50 mil) ============
CREATE OR REPLACE TABLE alunos CLUSTER BY (aluno_id) AS
WITH base AS (
  SELECT CAST(id AS INT) AS aluno_id,
         (pmod(hash(id, 'u1'), 1000000) + 1) / 1000001.0 AS u1,
         (pmod(hash(id, 'u2'), 1000000)) / 1000000.0 AS u2,
         pmod(hash(id, 'fac'), 1000) AS rf
  FROM range(1, 50001) AS r(id)
)
SELECT
  aluno_id,
  concat(
    element_at(array('Ana','Beatriz','Camila','Daniela','Eduarda','Fernanda','Gabriela','Helena','Isabela','Júlia','Larissa','Mariana',
                     'Natália','Patrícia','Rafaela','Sofia','Thaís','Vitória','Letícia','Carolina','Lucas','Gabriel','Pedro','Matheus',
                     'Rafael','Gustavo','Felipe','Bruno','Thiago','Rodrigo','Daniel','André','Leonardo','Vinícius','Henrique','João',
                     'Caio','Diego','Eduardo','Marcelo'), CAST(pmod(hash(aluno_id,'n'), 40) + 1 AS INT)), ' ',
    element_at(array('Silva','Santos','Oliveira','Souza','Rodrigues','Ferreira','Alves','Pereira','Lima','Gomes','Costa','Ribeiro',
                     'Martins','Carvalho','Almeida','Lopes','Soares','Fernandes','Vieira','Barbosa','Rocha','Dias','Nascimento',
                     'Andrade','Moreira','Nunes','Marques','Machado','Mendes','Freitas','Cardoso','Ramos','Gonçalves','Santana',
                     'Teixeira','Araújo','Pinto','Correia','Cavalcanti','Monteiro'), CAST(pmod(hash(aluno_id,'s1'), 40) + 1 AS INT)), ' ',
    element_at(array('Silva','Santos','Oliveira','Souza','Rodrigues','Ferreira','Alves','Pereira','Lima','Gomes','Costa','Ribeiro',
                     'Martins','Carvalho','Almeida','Lopes','Soares','Fernandes','Vieira','Barbosa'), CAST(pmod(hash(aluno_id,'s2'), 20) + 1 AS INT))
  ) AS nome,
  -- faculdades maiores (capitais do Sudeste) concentram mais alunos
  CAST(CASE WHEN rf < 300 THEN rf % 9 + 1 ELSE rf % 30 + 1 END AS INT) AS faculdade_id,
  element_at(array('Clínica Médica','Cirurgia Geral','Pediatria','Ginecologia e Obstetrícia','Medicina de Família',
                   'Anestesiologia','Ortopedia','Psiquiatria','Dermatologia','Cardiologia','Oftalmologia','Radiologia'),
             CAST(pmod(hash(aluno_id,'esp'), 12) + 1 AS INT)) AS especialidade_alvo,
  CAST(2025 + pmod(hash(aluno_id,'ano'), 3) AS INT) AS ano_formatura,
  -- habilidade latente ~ N(0,1) (Box-Muller), usada só pelo gerador
  sqrt(-2 * ln(u1)) * cos(2 * pi() * u2) AS habilidade
FROM base;

-- ============ Simulados ============
CREATE OR REPLACE TABLE simulados AS
SELECT CAST(id AS INT) AS simulado_id,
       CASE WHEN id = 25 THEN 'Simulado Nacional R1 – Outubro/2026 (AO VIVO)'
            ELSE concat('Simulado Nacional R1 – ', date_format(add_months(DATE'2024-10-19', CAST(id - 1 AS INT)), 'MM/yyyy')) END AS nome,
       CASE WHEN id = 25 THEN DATE'2026-10-18' ELSE add_months(DATE'2024-10-19', CAST(id - 1 AS INT)) END AS data_aplicacao,
       120 AS total_questoes
FROM range(1, 26) AS r(id);

-- ============ Questões (120 por simulado, 5 grandes áreas) ============
CREATE OR REPLACE TABLE questoes CLUSTER BY (simulado_id, numero) AS
WITH q AS (
  SELECT CAST(s.id AS INT) AS simulado_id, CAST(n.id AS INT) AS numero,
         CAST((n.id - 1) DIV 24 AS INT) AS area_idx
  FROM range(1, 26) AS s(id) CROSS JOIN range(1, 121) AS n(id)
)
SELECT
  simulado_id, numero,
  element_at(array('Clínica Médica','Cirurgia','Pediatria','Ginecologia e Obstetrícia','Medicina Preventiva'), area_idx + 1) AS area,
  element_at(element_at(array(
     array('Insuficiência cardíaca','Diabetes mellitus','Pneumonia comunitária','Sepse','Doença renal crônica','Hipertensão arterial','Anemias','Tireoidopatias'),
     array('Abdome agudo','Trauma (ATLS)','Hérnias','Colecistite','Apendicite','Queimaduras','Pré e pós-operatório','Obstrução intestinal'),
     array('Neonatologia','Imunizações','Bronquiolite','Desidratação','Puericultura','Doenças exantemáticas','Asma na infância','Desnutrição'),
     array('Pré-natal','Doença hipertensiva da gestação','Sangramentos da gestação','Rastreamento de câncer de colo','Planejamento familiar','Trabalho de parto','Climatério','Infecções genitais'),
     array('Epidemiologia','Vigilância em saúde','SUS e políticas de saúde','Bioestatística','Medicina baseada em evidências','Saúde do trabalhador','Atenção primária','Ética médica')
  ), area_idx + 1), CAST(pmod(hash(simulado_id, numero, 't'), 8) + 1 AS INT)) AS tema,
  -- gabarito oficial. Q47 do simulado ao vivo foi cadastrada com gabarito 'C' (erro proposital; a correta é 'B')
  CASE WHEN simulado_id = 25 AND numero = 47 THEN 'C'
       ELSE element_at(array('A','B','C','D','E'), CAST(pmod(hash(simulado_id, numero, 'g'), 5) + 1 AS INT)) END AS gabarito,
  -- dificuldade em escala logit (-1.6 .. 1.6)
  round(((pmod(hash(simulado_id, numero, 'd'), 1000)) / 1000.0 - 0.5) * 3.2, 3) AS dificuldade
FROM q;
