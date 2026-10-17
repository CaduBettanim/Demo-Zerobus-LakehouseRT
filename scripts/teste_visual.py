"""Teste visual ponta a ponta do app (Playwright + Chrome local).

Uso: python scripts/teste_visual.py <url-do-app> <pasta-de-saida>
Token: variável DATABRICKS_TOKEN ou `databricks auth token -p <profile>` salvo em /tmp/apptok.
Abre a prova, percorre todas as abas, anula a Q47, roda escala e comparativo e encerra com limpeza.
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

URL = sys.argv[1].rstrip("/")
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/shots"
TOKEN = os.environ.get("DATABRICKS_TOKEN") or open("/tmp/apptok").read().strip()
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page(viewport={"width": 1600, "height": 1000}, extra_http_headers={"Authorization": f"Bearer {TOKEN}"})
    erros = []
    pg.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
    pg.on("console", lambda m: erros.append(f"console.{m.type}: {m.text}") if m.type == "error" and "favicon" not in m.text else None)
    pg.on("response", lambda r: erros.append(f"HTTP {r.status} {r.url}") if r.status >= 400 and "favicon" not in r.url else None)
    pg.on("dialog", lambda d: d.accept())  # confirmação do ■

    def foto(nome):
        pg.screenshot(path=f"{OUT}/{nome}.png", full_page=True)
        print("ok", nome)

    pg.goto(URL)
    time.sleep(4)
    if pg.locator("#pill.on").count() == 0:
        pg.click("#btn-abrir")
    time.sleep(35)
    foto("vivo")

    pg.click("[data-aba=aluno]")
    pg.click("#btn-aleatorio")
    pg.wait_for_selector("#aluno-painel:not(.hidden)", timeout=30000)
    time.sleep(2)
    foto("aluno")

    pg.click("[data-aba=questoes]")
    pg.wait_for_selector("#btn-anular", timeout=120000)
    time.sleep(1)
    foto("questoes")
    pg.click("#btn-anular")
    pg.wait_for_selector("#modal:not(.hidden)", timeout=60000)
    time.sleep(1)
    foto("anular")
    pg.click("#modal-box .btn")

    pg.click("[data-aba=escala]")
    pg.click("#btn-escala")
    pg.wait_for_selector("#esc-srv:not(.hidden)", timeout=120000)
    time.sleep(6)
    foto("escala")

    pg.click("[data-aba=comparar]")
    pg.click("[data-cmp=posicao]")
    pg.wait_for_selector(".box.rt", timeout=120000)
    time.sleep(1)
    foto("comparar")

    pg.click("[data-aba=arq]")
    time.sleep(2)
    foto("arq")

    pg.click("[data-aba=vivo]")
    pg.click("#btn-encerrar")
    pg.wait_for_selector(".toast:has-text('Prova encerrada')", timeout=120000)
    time.sleep(1)
    foto("encerrado")
    print("toast:", pg.locator(".toast:has-text('Prova encerrada')").first.inner_text())

    print("\n".join(erros) or "sem erros de console/HTTP")
    b.close()
