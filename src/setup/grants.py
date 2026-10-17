# Databricks notebook source
# MAGIC %md
# MAGIC # Grants para o service principal do app
# MAGIC O app usa o **próprio service principal** (injetado pelo Databricks Apps) para consultar o
# MAGIC Lakehouse//RT, escrever via DBSQL e ingerir via **Zerobus**. O Zerobus exige `SELECT` e `MODIFY`
# MAGIC explícitos nas tabelas de destino.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("schema", "rt_simulado")
dbutils.widgets.text("app_name", "medprime-rt-simulado")

CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
APP = dbutils.widgets.get("app_name").strip()
T = f"`{CATALOG}`.`{SCHEMA}`"

sp = WorkspaceClient().apps.get(APP).service_principal_client_id
assert sp, f"App {APP} sem service principal"
print(f"App {APP} → service principal {sp}")

# COMMAND ----------

grants = [
    f"GRANT USE CATALOG ON CATALOG `{CATALOG}` TO `{sp}`",
    f"GRANT USE SCHEMA, SELECT ON SCHEMA {T} TO `{sp}`",
    # alvos do Zerobus (grant explícito na tabela é obrigatório)
    f"GRANT SELECT, MODIFY ON TABLE {T}.respostas TO `{sp}`",
    f"GRANT SELECT, MODIFY ON TABLE {T}.sessoes TO `{sp}`",
    # controle da demo (anulação, rodadas, limpeza ao encerrar)
    f"GRANT SELECT, MODIFY ON TABLE {T}.anulacoes TO `{sp}`",
    f"GRANT SELECT, MODIFY ON TABLE {T}.rodadas TO `{sp}`",
]
for g in grants:
    print(g)
    spark.sql(g)
