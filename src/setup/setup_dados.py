# Databricks notebook source
# MAGIC %md
# MAGIC # Setup de dados · MedPrime Residência (Lakehouse//RT + Zerobus)
# MAGIC Cria schema, tabelas (alvos do Zerobus e controle), dimensões e ~115M respostas históricas.
# MAGIC É idempotente: só gera o que ainda não existe, a menos que `recriar = true`.

# COMMAND ----------

import os
import re

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("schema", "rt_simulado")
dbutils.widgets.dropdown("recriar", "false", ["false", "true"])

CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
RECRIAR = dbutils.widgets.get("recriar") == "true"
assert CATALOG and SCHEMA, "Informe os parâmetros catalog e schema"
T = f"`{CATALOG}`.`{SCHEMA}`"
SQL_DIR = os.path.join(os.getcwd(), "sql")
print(f"Destino: {CATALOG}.{SCHEMA} · recriar={RECRIAR}")

# COMMAND ----------


def executar(arquivo):
    texto = open(os.path.join(SQL_DIR, arquivo)).read().replace("{catalog}", CATALOG).replace("{schema}", SCHEMA)
    texto = "\n".join(l for l in texto.splitlines() if not l.strip().startswith("--"))
    for stmt in [s.strip() for s in re.split(r";\s*\n", texto + "\n") if s.strip()]:
        print(" ".join(stmt.split())[:110])
        spark.sql(stmt)


def existe(tabela):
    return spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{tabela}")


spark.sql(f"CREATE SCHEMA IF NOT EXISTS {T} COMMENT 'Demo Lakehouse//RT + Zerobus - MedPrime Residência (dados sintéticos)'")

# COMMAND ----------

# MAGIC %md ## 1. Tabelas (alvos do Zerobus e controle da demo)

# COMMAND ----------

if RECRIAR:
    for t in ("respostas", "sessoes", "rodadas", "anulacoes"):
        spark.sql(f"DROP TABLE IF EXISTS {T}.{t}")
executar("01_tabelas.sql")
spark.sql(f"ALTER TABLE {T}.respostas SET TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true')")

# COMMAND ----------

# MAGIC %md ## 2. Dimensões (faculdades, alunos, simulados, questões)

# COMMAND ----------

if RECRIAR or not all(existe(t) for t in ("faculdades", "alunos", "simulados", "questoes")):
    executar("02_dimensoes.sql")
else:
    print("Dimensões já existem, pulando.")

# COMMAND ----------

# MAGIC %md ## 3. Histórico (24 simulados anteriores, ~115M respostas)

# COMMAND ----------

hist = spark.sql(f"SELECT count(*) AS n FROM {T}.respostas WHERE rodada = 0").first()["n"]
if RECRIAR or hist == 0:
    executar("03_historico.sql")
    spark.sql(f"OPTIMIZE {T}.respostas")
    spark.sql(f"ANALYZE TABLE {T}.respostas COMPUTE STATISTICS FOR ALL COLUMNS")
else:
    print(f"Histórico já carregado ({hist:,} respostas), pulando.")

# COMMAND ----------

resumo = spark.sql(f"""
SELECT (SELECT count(*) FROM {T}.alunos) AS alunos,
       (SELECT count(*) FROM {T}.faculdades) AS faculdades,
       (SELECT count(*) FROM {T}.questoes) AS questoes,
       (SELECT count(*) FROM {T}.respostas WHERE rodada = 0) AS respostas_historicas""").first().asDict()
print(resumo)
assert resumo["alunos"] == 50000 and resumo["questoes"] == 3000 and resumo["respostas_historicas"] > 100_000_000
