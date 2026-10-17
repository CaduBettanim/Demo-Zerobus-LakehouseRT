// MedPrime Residência · Simulado Nacional ao vivo (Lakehouse//RT + Zerobus)
const $ = (s) => document.querySelector(s);
const fmt = (n) => (n == null ? "–" : Number(n).toLocaleString("pt-BR"));
const pct = (n) => (n == null ? "–" : `${Number(n).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`);
let abaAtual = "vivo";
let alunoAtual = null;
let qSel = null;
let ultimoTop = {};

async function api(url, opts = {}) {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return r.json();
}
const post = (url, body = {}) => api(url, { method: "POST", body: JSON.stringify(body) });
function toast(msg, ms = 4000) {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = msg; document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}
function setLat(id, ms) { const el = $(`#lat-${id}`); if (el) el.textContent = ms == null ? "" : `⚡ Lakehouse//RT · ${fmt(ms)} ms`; }

// ---------- gráficos SVG ----------
function barras(el, vals, { cor = "#0e7490", rotulos = [] } = {}) {
  const W = el.clientWidth || 400, H = el.clientHeight || 200, n = Math.max(vals.length, 1);
  const max = Math.max(1, ...vals), bw = W / n;
  let s = `<svg viewBox="0 0 ${W} ${H}">`;
  vals.forEach((v, i) => {
    const h = (v / max) * (H - 34);
    s += `<rect x="${i * bw + 1}" y="${H - 18 - h}" width="${Math.max(1, bw - 2)}" height="${h}" rx="2" fill="${cor}"><title>${fmt(v)}</title></rect>`;
  });
  if (vals.some((v) => v > 0)) s += `<text x="${W}" y="10" font-size="11" fill="#64748b" text-anchor="end">pico ${fmt(max)}/s</text>`;
  if (rotulos.length) { s += `<text x="0" y="${H - 3}" font-size="10" fill="#94a3b8">${rotulos[0]}</text><text x="${W}" y="${H - 3}" font-size="10" fill="#94a3b8" text-anchor="end">${rotulos[rotulos.length - 1]}</text>`; }
  el.innerHTML = s + "</svg>";
}
function linhas(el, series, { rotulos = [], yMax = null, sufixo = "" } = {}) {
  const W = el.clientWidth || 400, H = el.clientHeight || 200, P = 30;
  const all = series.flatMap((s) => s.vals.filter((v) => v != null));
  const max = yMax || Math.max(1, ...all) * 1.1, min = 0;
  const n = Math.max(...series.map((s) => s.vals.length), 2);
  const x = (i) => P + (i / (n - 1)) * (W - P - 6), y = (v) => H - 18 - ((v - min) / (max - min)) * (H - 30);
  let s = `<svg viewBox="0 0 ${W} ${H}">`;
  for (let k = 0; k <= 4; k++) {
    const v = min + ((max - min) * k) / 4;
    s += `<line x1="${P}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="#f1f5f9"/><text x="${P - 4}" y="${y(v) + 4}" font-size="10" fill="#94a3b8" text-anchor="end">${Math.round(v)}${sufixo}</text>`;
  }
  series.forEach((se) => {
    const pts = se.vals.map((v, i) => (v == null ? null : `${x(i)},${y(v)}`)).filter(Boolean);
    s += `<polyline fill="none" stroke="${se.cor}" stroke-width="${se.w || 2.5}" points="${pts.join(" ")}" ${se.dash ? 'stroke-dasharray="5 4"' : ""}/>`;
    se.vals.forEach((v, i) => { if (v != null && se.pontos) s += `<circle cx="${x(i)}" cy="${y(v)}" r="3" fill="${se.cor}"><title>${rotulos[i] || ""}: ${v}${sufixo}</title></circle>`; });
  });
  if (rotulos.length) { s += `<text x="${P}" y="${H - 3}" font-size="10" fill="#94a3b8">${rotulos[0]}</text><text x="${W}" y="${H - 3}" font-size="10" fill="#94a3b8" text-anchor="end">${rotulos[rotulos.length - 1]}</text>`; }
  el.innerHTML = s + "</svg>";
}
function corEscala(v, lo = 45, hi = 75) {
  const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
  const stops = [[253, 230, 138], [20, 184, 166], [14, 116, 144]];
  const a = t < 0.5 ? stops[0] : stops[1], b = t < 0.5 ? stops[1] : stops[2], u = t < 0.5 ? t * 2 : (t - 0.5) * 2;
  return `rgb(${a.map((c, i) => Math.round(c + (b[i] - c) * u)).join(",")})`;
}

// ---------- abas ----------
document.querySelectorAll(".abas button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".abas button").forEach((x) => x.classList.toggle("ativa", x === b));
  document.querySelectorAll(".aba").forEach((x) => x.classList.toggle("ativa", x.id === `aba-${b.dataset.aba}`));
  abaAtual = b.dataset.aba;
  if (abaAtual === "vivo") carregarVivo();
  if (abaAtual === "questoes") carregarQuestoes();
  if (abaAtual === "aluno" && alunoAtual) carregarAluno(alunoAtual);
}));

// ---------- controle do simulador ----------
$("#btn-abrir").onclick = async () => {
  $("#btn-abrir").disabled = true;
  try {
    await post("/api/simulador/abrir", { participantes: +$("#sel-part").value, taxa: +$("#sel-taxa").value });
    alunoAtual = null; qSel = null; ultimoTop = {};
    $("#aluno-painel").classList.add("hidden"); $("#aluno-vazio").classList.remove("hidden");
    toast("Prova aberta! Alunos entrando e respondendo via Zerobus…");
  } catch (e) { toast("Erro ao abrir prova: " + e.message, 8000); }
  $("#btn-abrir").disabled = false;
};
$("#sel-taxa").onchange = () => post("/api/simulador/taxa", { taxa: +$("#sel-taxa").value });
$("#btn-pausar").onclick = () => post("/api/simulador/pausar");
$("#btn-encerrar").title = "Encerrar e limpar dados"; $("#btn-encerrar").onclick = async () => {
  if (!confirm("Encerrar a prova e apagar os dados ao vivo desta demo?\n\nO histórico (115 mi de respostas), as dimensões e a gold são mantidos.")) return;
  $("#btn-encerrar").disabled = true;
  toast("Encerrando a prova: aguardando o Zerobus materializar os últimos registros e limpando os dados ao vivo…", 12000);
  try {
    const r = await post("/api/simulador/encerrar");
    const l = r.limpeza;
    toast(`Prova encerrada. Removidos: ${fmt(l.respostas)} respostas, ${fmt(l.sessoes)} eventos de sessão e ${fmt(l.anulacoes)} anulações (${fmt(l.ms)} ms). Lembrete: o app continua ligado; pare com "databricks apps stop" se não for usar.`, 10000);
    alunoAtual = null; qSel = null; ultimoTop = {};
    $("#aluno-painel").classList.add("hidden"); $("#aluno-vazio").classList.remove("hidden");
    $("#badge-susp").classList.add("hidden"); questoesCache = [];
    // o RT enxerga o DELETE em ~1–2 s (mesmo atraso de qualquer commit): recarrega em seguida
    [500, 3000, 7000].forEach((ms) => setTimeout(() => { pollVolume(); carregarVivo(); if (abaAtual === "questoes") carregarQuestoes(); }, ms));
  } catch (e) { toast("Erro ao encerrar: " + e.message, 8000); }
  $("#btn-encerrar").disabled = false;
};

async function pollEstado() {
  try {
    const e = await api("/api/estado");
    const pill = $("#pill");
    if (e.rodando && !e.pausado) { pill.className = "pill on"; pill.textContent = "● AO VIVO"; }
    else if (e.rodando) { pill.className = "pill pause"; pill.textContent = "❚❚ PAUSADO"; }
    else { pill.className = "pill off"; pill.textContent = e.enviadas ? "■ ENCERRADO" : "● AGUARDANDO"; }
    $("#st-taxa").textContent = fmt(e.taxa_real);
    if (e.rodando && document.activeElement !== $("#sel-taxa")) $("#sel-taxa").value = String(e.taxa_alvo);
    $("#st-env").textContent = fmt(e.enviadas);
    if (e.erro) toast("Simulador: " + e.erro, 8000);
  } catch (_) {}
}
async function pollVolume() {
  try { const v = await api("/api/volume"); $("#st-vol").textContent = (v.linhas / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mi"; } catch (_) {}
}

// ---------- Coordenação ao vivo ----------
const MAPA = { RR: [2, 0], AP: [4, 0], AM: [1, 1], PA: [3, 1], MA: [4, 1], CE: [5, 1], RN: [6, 1], AC: [0, 2], RO: [1, 2], MT: [2, 2], TO: [3, 2], PI: [4, 2], PB: [6, 2], PE: [5, 2],
  MS: [2, 3], GO: [3, 3], BA: [4, 3], AL: [6, 3], SE: [5, 3], DF: [3, 4], MG: [4, 4], ES: [5, 4], SP: [3, 5], RJ: [4, 5], PR: [2, 5], SC: [2, 6], RS: [2, 7] };
let carregandoVivo = false;
async function carregarVivo() {
  if (carregandoVivo) return; carregandoVivo = true;
  try {
    const r = await api("/api/ao-vivo");
    const d = r.dados, k = d.kpis[0] || {}, s = d.sessoes[0] || {};
    Object.entries(r.ms).forEach(([n, ms]) => setLat(n, ms));
    const online = (s.logins || 0) - (s.finalizados || 0);
    $("#k-online").textContent = fmt(online);
    $("#k-online-s").textContent = s.logins ? `${fmt(s.logins)} logins · ${Math.round((100 * s.via_app) / s.logins)}% pelo app` : "";
    $("#k-resp").textContent = fmt(k.respostas);
    $("#k-resp-s").textContent = k.alunos_respondendo ? `${fmt(k.alunos_respondendo)} alunos já responderam` : "";
    // taxa: média dos últimos 10 s já materializados no Delta (ignora o lote ainda não commitado)
    $("#k-fim").textContent = fmt(s.finalizados || 0);
    $("#k-fim-s").textContent = s.logins ? pct((100 * (s.finalizados || 0)) / s.logins) + " dos inscritos" : "";
    if (k.ultima && k.agora) {
      const idade = (new Date(k.agora.replace(" ", "T") + "Z") - new Date(k.ultima.replace(" ", "T") + "Z")) / 1000;
      $("#k-fresh").textContent = idade < 120 ? `${Math.max(0, idade).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s` : "–";
    } else $("#k-fresh").textContent = "–";
    const ufs = d.por_uf; let totAc = 0, totN = 0;
    ufs.forEach((u) => { totAc += u.aproveitamento * u.alunos; totN += u.alunos; });
    $("#k-aprov").textContent = totN ? pct(totAc / totN) : "–";
    // gráfico por segundo (preenche lacunas)
    const mapaSeg = Object.fromEntries(d.por_segundo.map((x) => [x.seg.slice(0, 19), x.n]));
    const agora = k.agora ? new Date(k.agora.replace(" ", "T") + "Z") : new Date();
    const vals = [], rot = [];
    for (let i = 59; i >= 1; i--) {
      const t = new Date(agora.getTime() - i * 1000); const key = t.toISOString().slice(0, 19).replace("T", " ");
      vals.push(mapaSeg[key] || 0); rot.push(i === 59 ? "-60 s" : i === 1 ? "agora" : "");
    }
    barras($("#ch-seg"), vals, { cor: "#ff3621", rotulos: ["-60 s", "agora"] });
    let fimIdx = vals.length; while (fimIdx > 0 && !vals[fimIdx - 1]) fimIdx--;
    const janela = vals.slice(Math.max(0, fimIdx - 10), fimIdx);
    $("#k-taxa").textContent = janela.length ? fmt(Math.round(janela.reduce((a, b) => a + b, 0) / janela.length)) : "0";
    // mapa
    const byUf = Object.fromEntries(ufs.map((u) => [u.uf, u]));
    $("#mapa").innerHTML = Object.entries(MAPA).map(([uf, [c, l]]) => {
      const u = byUf[uf];
      return `<div class="uf ${u ? "" : "sem"}" style="grid-column:${c + 1};grid-row:${l + 1};${u ? `background:${corEscala(u.aproveitamento)}` : ""}" title="${uf}${u ? ` · ${fmt(u.alunos)} alunos · ${pct(u.aproveitamento)}` : ""}">${uf}${u ? `<small>${pct(u.aproveitamento)}</small>` : ""}</div>`;
    }).join("");
    // top 10
    const novoTop = {};
    const linhasTop = d.top10.map((a, i) => {
      novoTop[a.aluno_id] = i; const mudou = ultimoTop[a.aluno_id] !== i;
      return `<tr class="${mudou ? "flash" : ""}"><td class="pos">${i + 1}º</td><td>${a.nome}<div class="sub">${a.faculdade}</div></td><td>${a.uf}</td><td class="num">${a.acertos}/${a.respondidas}</td><td class="num">${pct(a.aproveitamento)}</td></tr>`;
    }).join("");
    $("#tb-top").innerHTML = "<tr><th>#</th><th>Aluno</th><th>UF</th><th class='num'>Acertos</th><th class='num'>Aprov.</th></tr>" +
      (linhasTop || "<tr><td colspan=5 class='sub'>Aguardando respostas… clique em ▶ Abrir prova.</td></tr>");
    ultimoTop = novoTop;
    $("#tb-fac").innerHTML = d.faculdades.map((f, i) => `<tr><td class="pos">${i + 1}º</td><td>${f.faculdade}<div class="sub">${fmt(f.alunos)} alunos</div></td><td class="num">${pct(f.aproveitamento)}</td></tr>`).join("") || "<tr><td class='sub'>–</td></tr>";
  } catch (e) { console.error(e); }
  carregandoVivo = false;
}

// ---------- Painel do aluno ----------
let tBusca;
$("#busca").addEventListener("input", (ev) => {
  clearTimeout(tBusca);
  const q = ev.target.value.trim();
  if (q.length < 3) { $("#busca-res").classList.add("hidden"); return; }
  tBusca = setTimeout(async () => {
    const r = await api(`/api/aluno/busca?q=${encodeURIComponent(q)}`);
    $("#busca-res").innerHTML = r.dados.map((a) => `<div data-id="${a.aluno_id}"><b>${a.nome}</b> · <span class="sub">${a.faculdade}</span></div>`).join("") || "<div>nenhum aluno</div>";
    $("#busca-res").classList.remove("hidden");
    $("#busca-res").querySelectorAll("[data-id]").forEach((d) => (d.onclick = () => { $("#busca-res").classList.add("hidden"); $("#busca").value = ""; carregarAluno(+d.dataset.id); }));
  }, 250);
});
$("#btn-aleatorio").onclick = async () => { const r = await api("/api/aluno/aleatorio"); carregarAluno(r.aluno_id); };
async function carregarAluno(id) {
  alunoAtual = id;
  try {
    const r = await api(`/api/aluno/${id}`);
    const d = r.dados, p = d.posicao[0];
    const total = Object.values(r.ms).reduce((a, b) => Math.max(a, b), 0);
    $("#lat-aluno").textContent = `⚡ Lakehouse//RT · posição ${fmt(r.ms.posicao)} ms · desempenho ${fmt(r.ms.meu)} ms · histórico ${fmt(r.ms.historico)} ms`;
    if (!p) { $("#aluno-vazio").innerHTML = "Esse aluno ainda não respondeu nenhuma questão nesta prova."; $("#aluno-vazio").classList.remove("hidden"); $("#aluno-painel").classList.add("hidden"); return; }
    $("#aluno-vazio").classList.add("hidden"); $("#aluno-painel").classList.remove("hidden");
    $("#al-nome").textContent = p.nome;
    $("#al-sub").textContent = `${p.faculdade} · ${p.uf} · quer ${p.especialidade_alvo}`;
    $("#al-pos").textContent = `${fmt(p.posicao)}º`;
    $("#al-total").textContent = `de ${fmt(p.total)} alunos`;
    $("#al-posfac").textContent = `${fmt(p.posicao_faculdade)}º / ${fmt(p.total_faculdade)}`;
    $("#al-pct").textContent = `top ${Math.max(1, Math.ceil((100 * p.posicao) / p.total))}%`;
    $("#al-ac").textContent = fmt(p.acertos);
    $("#al-resp").textContent = `${p.respondidas}/120`;
    $("#al-bar").style.width = `${(100 * p.respondidas) / 120}%`;
    const meu = Object.fromEntries(d.meu.map((m) => [m.area, m]));
    $("#ch-areas").innerHTML = d.areas.sort((a, b) => a.area.localeCompare(b.area)).map((a) => {
      const m = meu[a.area]; const al = m && m.respondidas ? (100 * m.acertos) / m.respondidas : null;
      return `<div class="area-row"><div class="nm">${a.area} ${m ? `<span class="sub">(${m.acertos}/${m.respondidas})</span>` : ""}</div><div class="bars">
        <div style="width:calc(${al || 0}% * .85);background:var(--rt)"><span>${al == null ? "–" : pct(al)}</span></div>
        <div style="width:calc(${a.faculdade || 0}% * .85);background:var(--acc)"><span>${pct(a.faculdade)}</span></div>
        <div style="width:calc(${a.nacional || 0}% * .85);background:#94a3b8"><span>${pct(a.nacional)}</span></div></div></div>`;
    }).join("");
    const h = d.historico;
    linhas($("#ch-hist"), [{ vals: h.map((x) => x.nota), cor: "#ff3621", pontos: true }, { vals: h.map((x) => x.nota_nacional), cor: "#94a3b8", dash: true }],
      { rotulos: h.map((x) => x.nome.replace("Simulado Nacional R1 – ", "")), yMax: 100 });
  } catch (e) { console.error(e); toast("Erro: " + e.message); }
}

// ---------- Questões ----------
let carregandoQ = false, questoesCache = [];
async function carregarQuestoes() {
  if (carregandoQ) return; carregandoQ = true;
  try {
    const r = await api("/api/questoes");
    setLat("questoes", r.ms);
    questoesCache = r.dados;
    const susp = r.dados.filter((q) => q.suspeita);
    $("#badge-susp").classList.toggle("hidden", !susp.length);
    $("#q-grid").innerHTML = r.dados.map((q) => {
      const cls = ["q", q.suspeita ? "susp" : "", q.anulada ? "anul" : "", qSel === q.numero ? "sel" : ""].join(" ");
      const bg = q.pct_acerto == null ? "" : `background:${corEscala(q.pct_acerto, 20, 85)}`;
      return `<div class="${cls}" style="${bg}" data-n="${q.numero}" title="Q${q.numero} · ${q.area} · ${q.tema} · ${q.pct_acerto == null ? "sem respostas" : pct(q.pct_acerto)}">${q.suspeita ? "⚠" : q.numero}</div>`;
    }).join("");
    $("#q-grid").querySelectorAll(".q").forEach((el) => (el.onclick = () => { qSel = +el.dataset.n; detalheQuestao(); carregarQuestoes(); }));
    if (qSel == null && susp.length) qSel = susp[0].numero;
    detalheQuestao();
  } catch (e) { console.error(e); }
  carregandoQ = false;
}
function detalheQuestao() {
  const q = questoesCache.find((x) => x.numero === qSel);
  if (!q) return;
  const n = q.n || 0;
  const alts = "ABCDE".split("").map((L) => {
    const v = q[L.toLowerCase()] || 0, p = n ? (100 * v) / n : 0;
    return `<div class="alt ${L === q.gabarito ? "gab" : ""} ${L === q.mais_marcada ? "top" : ""}"><b>${L}</b><div class="trilho"><i style="width:${p}%"></i></div><span>${pct(p)}</span></div>`;
  }).join("");
  $("#q-det").innerHTML = `<div class="card-h"><h3>Questão ${q.numero} · ${q.area}</h3><span class="lat">${fmt(n)} respostas</span></div>
    <div class="sub">Tema: <b>${q.tema}</b> · gabarito oficial: <b>${q.gabarito}</b></div>
    ${alts}
    <div class="sub">Acerto ao vivo: <b>${pct(q.pct_acerto)}</b> · média histórica do tema: <b>${pct(q.pct_hist)}</b></div>
    ${q.anulada ? `<div class="info">✅ Questão anulada. O ponto foi atribuído a todos os alunos e o ranking nacional já foi recalculado.</div>` : ""}
    ${q.suspeita ? `<div class="alerta">⚠ <b>Padrão suspeito:</b> ${pct((100 * q[q.mais_marcada.toLowerCase()]) / n)} dos alunos marcaram <b>${q.mais_marcada}</b>, mas o gabarito oficial é <b>${q.gabarito}</b>. O acerto (${pct(q.pct_acerto)}) está muito abaixo da média histórica do tema (${pct(q.pct_hist)}). Pode ser erro de gabarito.</div>
      <button class="btn prim" id="btn-anular">Anular questão ${q.numero} e recalcular ranking</button>` : ""}`;
  const b = $("#btn-anular");
  if (b) b.onclick = () => anular(q.numero);
}
async function anular(numero) {
  $("#btn-anular").disabled = true;
  try {
    const r = await post(`/api/questoes/${numero}/anular`, {});
    const antes = Object.fromEntries(r.top_antes.map((a, i) => [a.aluno_id, i + 1]));
    $("#modal-box").innerHTML = `<h2>Questão ${numero} anulada</h2>
      <p>Escrita da anulação via <b>DBSQL</b>: <b>${fmt(r.ms_escrita_dbsql)} ms</b> · ranking de todos os alunos recalculado no <b style="color:var(--rt)">Lakehouse//RT</b>: <b>${fmt(r.ms_ranking_rt)} ms</b></p>
      <div class="cols2"><div><h3>Antes</h3><table class="tab">${r.top_antes.map((a, i) => `<tr><td class="pos">${i + 1}º</td><td>${a.nome}</td><td class="num">${a.acertos}</td></tr>`).join("")}</table></div>
      <div><h3>Depois</h3><table class="tab">${r.top_depois.map((a, i) => { const ant = antes[a.aluno_id]; const tag = !ant ? '<span class="sobe">novo</span>' : ant > i + 1 ? `<span class="sobe">▲${ant - i - 1}</span>` : ant < i + 1 ? `<span class="desce">▼${i + 1 - ant}</span>` : ""; return `<tr><td class="pos">${i + 1}º</td><td>${a.nome} ${tag}</td><td class="num">${a.acertos}</td></tr>`; }).join("")}</table></div></div>
      <p style="text-align:right"><button class="btn prim" onclick="document.getElementById('modal').classList.add('hidden')">Fechar</button></p>`;
    $("#modal").classList.remove("hidden");
    carregarQuestoes();
  } catch (e) { toast("Erro: " + e.message); }
}

// ---------- Escala ----------
let pollEsc = null;
$("#btn-escala").onclick = async () => {
  $("#esc-srv").classList.add("hidden");
  const e = await post("/api/escala/iniciar", { usuarios: +$("#esc-u").value, duracao: +$("#esc-d").value });
  $("#btn-escala").disabled = true;
  clearInterval(pollEsc); pollEsc = setInterval(atualizarEscala, 1000);
};
async function atualizarEscala() {
  const e = await api("/api/escala/estado");
  $("#e-u").textContent = fmt(e.usuarios);
  $("#e-qps").textContent = fmt(Math.round(e.atual.qps));
  $("#e-p50").textContent = e.atual.p50 == null ? "–" : `${fmt(e.atual.p50)} ms`;
  $("#e-p95").textContent = e.atual.p95 == null ? "–" : `${fmt(e.atual.p95)} ms`;
  $("#e-ok").textContent = fmt(e.ok); $("#e-err").textContent = fmt(e.erros);
  const s = e.serie;
  linhas($("#ch-qps"), [{ vals: s.map((x) => x.qps), cor: "#0e7490" }, { vals: s.map((x) => x.usuarios), cor: "#cbd5e1", dash: true, w: 1.5 }], { rotulos: s.map((x) => `${x.t}s`) });
  linhas($("#ch-lat"), [{ vals: s.map((x) => x.p50), cor: "#ff3621" }, { vals: s.map((x) => x.p95), cor: "#f59e0b" }], { rotulos: s.map((x) => `${x.t}s`), sufixo: "" });
  if (!e.rodando) {
    clearInterval(pollEsc); $("#btn-escala").disabled = false;
    if (e.ok) {
      $("#esc-srv").innerHTML = `<b>Teste concluído:</b> ${fmt(e.ok)} consultas · ponta a ponta (app → API → RT → app) p50 <b>${fmt(e.p50_total)} ms</b> · p95 <b>${fmt(e.p95_total)} ms</b> · ${fmt(e.erros)} erros<br><span class="sub">medindo o tempo dentro do motor Lakehouse//RT…</span>`;
      $("#esc-srv").classList.remove("hidden");
      setTimeout(async () => {
        try {
          const s = await api("/api/escala/servidor");
          if (s.n) $("#esc-srv").innerHTML = `<b>Teste concluído:</b> ${fmt(e.ok)} consultas · ${fmt(e.erros)} erros<br>Ponta a ponta (app → API → RT → app): p50 <b>${fmt(e.p50_total)} ms</b> · p95 <b>${fmt(e.p95_total)} ms</b><br>Dentro do motor <b style="color:var(--rt)">Lakehouse//RT</b> (${fmt(s.n)} consultas no query history): p50 <b>${fmt(s.p50)} ms</b> · p95 <b>${fmt(s.p95)} ms</b> · p99 <b>${fmt(s.p99)} ms</b>`;
        } catch (_) {}
      }, 4000);
    }
  }
}

// ---------- RT vs DBSQL ----------
document.querySelectorAll("[data-cmp]").forEach((b) => (b.onclick = async () => {
  document.querySelectorAll("[data-cmp]").forEach((x) => (x.disabled = true));
  $("#cmp-res").innerHTML = '<div class="vazio">Executando a mesma consulta nos dois warehouses…</div>'; $("#cmp-sql").textContent = "";
  try {
    const r = await api(`/api/comparar?tipo=${b.dataset.cmp}&n=${b.dataset.cmp === "aluno" ? 5 : 3}`);
    linhas($("#cmp-ch"), [{ vals: r.rt, cor: "#ff3621", pontos: true }, { vals: r.dbsql, cor: "#334155", pontos: true }], { rotulos: r.rt.map((_, i) => `exec ${i + 1}`) });
    const x = r.mediana_dbsql / Math.max(1, r.mediana_rt);
    $("#cmp-res").innerHTML = `<div class="box rt">Lakehouse//RT<b>${fmt(Math.round(r.mediana_rt))} ms</b></div><div class="x">${x.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}×</div><div class="box db">DBSQL Serverless<b>${fmt(Math.round(r.mediana_dbsql))} ms</b></div>`;
    $("#cmp-sql").textContent = r.sql.replace(/\b\w+\.\w+\.(?=\w)/g, "");
  } catch (e) { $("#cmp-res").innerHTML = `<div class="alerta">${e.message}</div>`; }
  document.querySelectorAll("[data-cmp]").forEach((x) => (x.disabled = false));
}));

$("#esc-sql").textContent = `-- consulta executada por cada usuário simulado (aluno aleatório a cada chamada)
SELECT q.area, count(*) AS respondidas,
       sum(CASE WHEN r.alternativa = q.gabarito THEN 1 ELSE 0 END) AS acertos
FROM respostas r JOIN questoes q ON q.simulado_id = r.simulado_id AND q.numero = r.numero
WHERE r.simulado_id = :sim AND r.rodada = :rodada AND r.aluno_id = :aluno
GROUP BY q.area`;

// ---------- loops ----------
setInterval(pollEstado, 1000);
setInterval(() => { if (abaAtual === "vivo") carregarVivo(); }, 2000);
setInterval(() => { if (abaAtual === "questoes") carregarQuestoes(); }, 3000);
setInterval(() => { if (abaAtual === "aluno" && alunoAtual && $("#auto-aluno").checked) carregarAluno(alunoAtual); }, 3000);
setInterval(pollVolume, 10000);
pollEstado(); pollVolume(); carregarVivo();
