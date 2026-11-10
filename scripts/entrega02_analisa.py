#!/usr/bin/env python3
"""Analisa os resultados da Entrega 2 e gera as peças do relatório.

Lê results/entrega02/execucoes.json e os CSVs de cada cenário e escreve:

    report/gerado/resumo_entrega02.csv     métricas de todos os cenários
    report/gerado/tabela_comparativa.tex   tabela obrigatória (throughput,
                                           retransmissões e tempo total)
    report/gerado/tabela_md5.tex           MD5 e DONE de cada execução
    report/gerado/analise.tex              respostas (a), (b) e (c) com os números
    report/figuras/e2_janela_sem_perda.png throughput x janela, sem perda
    report/figuras/e2_segmentos_w16_p10.png GBN x SR, janela 16, 10% de perda

Uso (na raiz do repositório):
    python scripts/entrega02_analisa.py [--results results/entrega02]
"""

import argparse
import csv
import json
import os
import statistics
import sys
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIGS = [("saw", 1), ("gbn", 4), ("gbn", 8), ("gbn", 16),
           ("sr", 4), ("sr", 8), ("sr", 16)]
LOSSES = [0.0, 0.05, 0.10]
NOME = {"saw": "SAW", "gbn": "GBN", "sr": "SR"}

# Paleta validada para daltonismo (mesma da Entrega 1).
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COR = {"saw": AQUA, "gbn": BLUE, "sr": ORANGE}


# ---------------------------------------------------------------------------
# Leitura e métricas
# ---------------------------------------------------------------------------

def name(protocol, window, loss):
    return f"{protocol}_w{window}_p{round(loss * 100):02d}"


def read_csv(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "seq": int(r["segment"]),
                "ts": datetime.fromisoformat(r["timestamp"]).timestamp(),
                "size": int(r["size_bytes"]),
                "rtt": float(r["rtt_ms"]) if r["rtt_ms"] else None,
                "thr": float(r["throughput_kbps"]) if r["throughput_kbps"] else None,
                "retx": int(r["retransmissions"]),
                "timeout": r["timeout_occurred"].strip() == "1",
                "lost": r["loss_simulated"].strip() == "1",
                "elapsed": None,
            })
    rows.sort(key=lambda r: r["seq"])
    for r in rows:
        # throughput_kbps = size*8/elapsed  ->  elapsed (ms) desde o 1º REQ
        r["elapsed"] = r["size"] * 8 / r["thr"] if r["thr"] else r["rtt"]
    return rows


def gbn_eventos(rows, window):
    """Estima quantos timeouts o GBN teve a partir da coluna retransmissions.

    Cada timeout da base reenvia um bloco contíguo de no máximo `window`
    segmentos (+1 em cada). Percorrendo em ordem de seq, mantemos os blocos
    ativos (que duram até `window` segmentos); quando a contagem do segmento
    excede os blocos ativos, começam novos blocos (novos timeouts).
    """
    ativos, eventos = [], 0
    for i, r in enumerate(rows):
        ativos = [s for s in ativos if i - s < window]
        falta = r["retx"] - len(ativos)
        if falta > 0:
            ativos += [i] * falta
            eventos += falta
        elif falta < 0:
            ativos = ativos[-falta:]
    return eventos


def exemplo_gbn(rows, window):
    """Primeiro timeout do GBN: (seq da base, nº de segmentos do bloco reenviado).

    O bloco é limitado à janela: timeouts seguintes podem emendar outros blocos.
    """
    for i, r in enumerate(rows):
        if r["retx"] > 0:
            j = i
            while (j + 1 < len(rows) and rows[j + 1]["retx"] > 0
                   and j + 1 - i < window):
                j += 1
            return r["seq"], j - i + 1
    return None


def exemplo_sr(rows):
    """Primeiro segmento retransmitido no SR e quantos vizinhos também foram."""
    for i, r in enumerate(rows):
        if r["retx"] > 0:
            viz = rows[max(0, i - 3):i] + rows[i + 1:i + 4]
            return r["seq"], sum(v["retx"] > 0 for v in viz)
    return None


def metrics(rows, protocol, window=1):
    start = min(r["ts"] - r["elapsed"] / 1000 for r in rows)
    end = max(r["ts"] for r in rows)
    duration = end - start
    total_bytes = sum(r["size"] for r in rows)
    retx = sum(r["retx"] for r in rows)
    erros = sum(r["lost"] for r in rows)
    # Eventos de timeout. SR: cada retransmissão é um timeout de 1 segmento.
    # GBN: um timeout reenvia a janela inteira a partir da base, somando +1 em
    # segmentos consecutivos; cada "degrau de subida" em seq marca um evento.
    eventos = gbn_eventos(rows, window) if protocol == "gbn" else retx
    clean = [r["rtt"] for r in rows if r["retx"] == 0]
    return {
        "segmentos": len(rows),
        "bytes": total_bytes,
        "tempo_s": duration,
        "throughput_kbps": total_bytes * 8 / duration / 1000,
        "retransmissoes": retx,
        "segmentos_com_retx": sum(r["retx"] > 0 for r in rows),
        "erros_simulados": erros,
        "eventos_timeout": eventos,
        "retx_por_erro": retx / erros if erros else None,
        "retx_por_timeout": retx / eventos if eventos else None,
        "rtt_mediano_ms": statistics.median(clean) if clean else None,
    }


def load(results_dir):
    with open(os.path.join(results_dir, "execucoes.json"), encoding="utf-8") as f:
        runs = {r["cenario"]: r for r in json.load(f)}
    data = {}
    for p, w in CONFIGS:
        for loss in LOSSES:
            n = name(p, w, loss)
            run = runs.get(n)
            if not run or not run.get("csv"):
                print(f"aviso: cenário {n} sem resultado", file=sys.stderr)
                continue
            rows = read_csv(os.path.join(ROOT, run["csv"]))
            data[n] = {"run": run, "rows": rows, **metrics(rows, p, w)}
    return data


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

def br(x, d=1):
    if x is None:
        return "---"
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", "\\,")


def pct(x, d=0):
    return br(100 * x, d) + "\\%"


def get(data, p, w, loss, key):
    item = data.get(name(p, w, loss))
    return item[key] if item else None


# ---------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------

def tabela_comparativa(data):
    linhas = [
        r"\begin{table}[H]", r"\centering", r"\footnotesize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{llrrrrrrrrr}", r"\toprule",
        r" & & \multicolumn{3}{c}{Sem perda} & \multicolumn{3}{c}{5\% de perda}"
        r" & \multicolumn{3}{c}{10\% de perda} \\",
        r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}\cmidrule(lr){9-11}",
        r"Protocolo & Janela & kbit/s & Retx. & Tempo (s) & kbit/s & Retx."
        r" & Tempo (s) & kbit/s & Retx. & Tempo (s) \\", r"\midrule",
    ]
    for p, w in CONFIGS:
        cells = [NOME[p], str(w)]
        for loss in LOSSES:
            cells += [br(get(data, p, w, loss, "throughput_kbps")),
                      br(get(data, p, w, loss, "retransmissoes"), 0),
                      br(get(data, p, w, loss, "tempo_s"), 1)]
        linhas.append(" & ".join(cells) + r" \\")
        if (p, w) in (("saw", 1), ("gbn", 16)):
            linhas.append(r"\midrule")
    arquivo = next(iter(data.values()))["run"]["arquivo"] if data else "small"
    linhas += [r"\bottomrule", r"\end{tabular}",
               r"\caption{Throughput médio (bytes recebidos $\times 8$ / tempo "
               r"total), total de retransmissões de \texttt{REQ} e tempo total "
               rf"da transferência do arquivo \texttt{{{arquivo}}} em cada cenário.}}",
               r"\label{tab:comparativa}", r"\end{table}"]
    return "\n".join(linhas) + "\n"


def tabela_md5(data):
    md5s = {d["run"].get("md5") for d in data.values()} - {None}
    esperado = {d["run"].get("md5_expected") for d in data.values()}
    sem_log = sum(d["run"].get("md5") is None for d in data.values())
    linhas = [
        r"\begin{table}[H]", r"\centering", r"\footnotesize",
        r"\begin{tabular}{llccc}", r"\toprule",
        r"Protocolo & Janela & Sem perda & 5\% & 10\% \\", r"\midrule",
    ]
    for p, w in CONFIGS:
        cells = [NOME[p], str(w)]
        for loss in LOSSES:
            d = data.get(name(p, w, loss))
            if not d:
                cells.append("---")
                continue
            run = d["run"]
            if run.get("md5") is None:
                cells.append(rf"completo$^*$ ({d['segmentos']} seg.)")
                continue
            ok = run.get("md5") == run.get("md5_expected")
            cells.append(("MD5 ok" if ok else "MD5 \\textbf{difere}")
                         + f", \\texttt{{DONE ok={run.get('done_ok')}}}")
        linhas.append(" & ".join(cells) + r" \\")
    unico = md5s.pop() if len(md5s) == 1 else None
    legenda = (rf"Todas as execuções com log preservado produziram o MD5 "
               rf"\texttt{{{unico}}}, igual ao \texttt{{checksum}} informado no \texttt{{OK}}"
               if unico and esperado == {unico}
               else r"MD5 calculado pelo cliente comparado ao \texttt{checksum} do \texttt{OK}")
    linhas += [r"\bottomrule", r"\end{tabular}",
               rf"\caption{{Integridade dos arquivos recebidos. {legenda}."
               + (rf" $^*$Em {sem_log} cenários a saída do cliente (com o MD5) foi "
                  r"sobrescrita por uma reexecução posterior; o CSV registra o "
                  r"download completo de todos os segmentos." if sem_log else "")
               + "}",
               r"\label{tab:md5}", r"\end{table}"]
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------

def style(ax, ylabel):
    ax.set_facecolor(SURFACE)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0, labelsize=8)


def fig_janela(data, path):
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    saw = get(data, "saw", 1, 0.0, "throughput_kbps")
    rtt = get(data, "saw", 1, 0.0, "rtt_mediano_ms")
    xs = [1, 4, 8, 16]
    if rtt:
        ax.plot(xs, [w * 512 * 8 / rtt for w in xs], color=MUTED,
                linestyle=(0, (4, 3)), linewidth=1.2,
                label=r"ideal $N \times L / \mathrm{RTT}$ (RTT mediano do SAW)")
    estilo = {"gbn": dict(marker="o", markersize=7, linewidth=2.2),
              "sr": dict(marker="s", markersize=5, linewidth=1.4,
                         linestyle=(0, (5, 2)), markerfacecolor=SURFACE)}
    for p in ("gbn", "sr"):
        ys = [saw] + [get(data, p, w, 0.0, "throughput_kbps") for w in xs[1:]]
        ax.plot(xs, ys, color=COR[p], label=NOME[p], **estilo[p])
        for x, y in zip(xs[1:], ys[1:]):
            if y:
                ax.annotate(br(y, 0).replace("\\,", "."), (x, y),
                            textcoords="offset points",
                            xytext=(6, -12) if p == "sr" else (-8, 8),
                            ha="left" if p == "sr" else "right",
                            fontsize=7, color=COR[p])
    ax.set_xscale("log", base=2)
    ax.set_xticks(xs)
    ax.set_xticklabels(["1 (SAW)", "4", "8", "16"])
    ax.set_xlabel("tamanho da janela $N$", color=MUTED, fontsize=9)
    style(ax, "throughput (kbit/s)")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def vazao_movel(rows, k=16):
    """Média móvel (k segmentos) da coluna throughput_kbps do CSV, isto é,
    size_bytes*8 / tempo do 1º REQ até o DATA de cada segmento."""
    vals = [r["thr"] or 0.0 for r in rows]
    xs, ys = [], []
    for i in range(k - 1, len(rows)):
        xs.append(rows[i]["seq"])
        ys.append(sum(vals[i - k + 1:i + 1]) / k)
    return xs, ys


def fig_segmentos(data, path, w=16, loss=0.10):
    fig, axes = plt.subplots(3, 1, figsize=(8, 6.2), dpi=160, sharex=True,
                             gridspec_kw={"height_ratios": [1.6, 1, 1]})
    fig.patch.set_facecolor(SURFACE)
    for p in ("gbn", "sr"):
        d = data.get(name(p, w, loss))
        if not d:
            continue
        xs, ys = vazao_movel(d["rows"])
        axes[0].plot(xs, ys, color=COR[p], linewidth=1.4,
                     label=f"{NOME[p]} (vazão da sessão: "
                           f"{br(d['throughput_kbps'], 1).replace(chr(92) + ',', '.')} kbit/s)")
    style(axes[0], "throughput por segmento\n(kbit/s, média de 16)")
    axes[0].set_ylim(bottom=0)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK, loc="lower left",
                   bbox_to_anchor=(0, 1.0), ncol=2)
    for ax, p in zip(axes[1:], ("gbn", "sr")):
        d = data.get(name(p, w, loss))
        if not d:
            continue
        seqs = [r["seq"] for r in d["rows"]]
        ax.bar(seqs, [r["retx"] for r in d["rows"]], width=1.0, color=COR[p])
        lost = [r["seq"] for r in d["rows"] if r["lost"]]
        ax.scatter(lost, [-0.4] * len(lost), marker="|", s=18, color=INK,
                   linewidths=0.6, label="perda simulada")
        style(ax, f"retransmissões\n{NOME[p]} (total {d['retransmissoes']})")
        ax.yaxis.get_major_locator().set_params(integer=True)
        ax.legend(frameon=False, fontsize=7, labelcolor=MUTED, loc="upper right")
    axes[2].set_xlabel("segmento", color=MUTED, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Texto da análise
# ---------------------------------------------------------------------------

def analise(data):
    t = lambda p, w, l: get(data, p, w, l, "throughput_kbps")  # noqa: E731
    saw0 = t("saw", 1, 0.0)
    rtt = get(data, "saw", 1, 0.0, "rtt_mediano_ms") or 25.0
    out = []

    # (a) janela sem perda
    out.append(r"\subsection*{(a) Impacto do tamanho da janela sem perda}")
    frases = []
    estab = {}
    for p in ("gbn", "sr"):
        v4, v8, v16 = (t(p, 4, 0.0), t(p, 8, 0.0), t(p, 16, 0.0))
        if None in (v4, v8, v16, saw0):
            continue
        g48, g816 = v8 / v4 - 1, v16 / v8 - 1
        estab[p] = 8 if g816 < 0.15 else (16 if g816 < 0.5 else None)
        if g48 < 0.15:
            estab[p] = 4
        frases.append(
            rf"No {NOME[p]}, o throughput passou de {br(saw0)}\,kbit/s (SAW, $N=1$) "
            rf"para {br(v4)}, {br(v8)} e {br(v16)}\,kbit/s com $N = 4$, 8 e 16 "
            rf"({br(v4 / saw0, 1)}$\times$, {br(v8 / saw0, 1)}$\times$ e "
            rf"{br(v16 / saw0, 1)}$\times$ o SAW). De 4 para 8 o ganho foi de "
            rf"{pct(g48)} e de 8 para 16, de {pct(g816)}.")
    out.append(" ".join(frases))
    ideal16 = 16 * 512 * 8 / rtt
    vmax = max(filter(None, [t(p, 16, 0.0) for p in ("gbn", "sr")]), default=None)
    out.append(
        r"\par Sem perda, GBN e SR executam o mesmo caminho (pedem, recebem em ordem "
        r"e confirmam, sem retransmissões), então diferenças entre eles nessa coluna "
        r"vêm das condições da rede em cada execução, e não do protocolo. Com $N$ "
        r"segmentos em trânsito, chegam até $N$ segmentos por RTT, e o teto ideal é "
        rf"$N \times L/\mathrm{{RTT}}$ (com RTT mediano de {br(rtt, 2)}\,ms, "
        rf"{br(4 * 4096 / rtt, 0)}, {br(8 * 4096 / rtt, 0)} e {br(ideal16, 0)}\,kbit/s "
        r"para $N = 4$, 8 e 16). Esse crescimento linear vale enquanto a janela é "
        r"menor que o produto banda $\times$ atraso do caminho. Quando "
        r"$N \times L$ passa a cobrir todo o RTT, o canal fica sempre ocupado e o "
        r"limite passa a ser o gargalo (a banda do enlace ou a taxa de resposta do "
        r"servidor e do cliente), não mais a janela.")
    if vmax:
        bdp = vmax * rtt / (512 * 8)
        if any(v == 8 for v in estab.values()):
            concl = (r"Nos dados, o throughput \textbf{se estabiliza a partir de "
                     r"$N = 8$}: dobrar a janela para 16 quase não muda a vazão.")
        elif any(v == 4 for v in estab.values()):
            concl = (r"Nos dados, o throughput \textbf{já se estabiliza em "
                     r"$N = 4$}.")
        elif any(v == 16 for v in estab.values()):
            concl = (r"Nos dados, o ganho começa a diminuir entre 8 e 16, sinal de "
                     r"que a vazão \textbf{se aproxima da estabilização em "
                     r"$N \approx 16$}.")
        else:
            concl = (r"Nos dados, o throughput \textbf{não se estabilizou até "
                     r"$N = 16$}: cada vez que a janela dobrou, a vazão ainda subiu "
                     r"de forma expressiva, sinal de que o produto banda $\times$ "
                     r"atraso do caminho não foi atingido. A estabilização só "
                     r"ocorreria com janelas maiores.")
        if any(estab.values()):
            extra = (rf"A maior vazão medida ({br(vmax)}\,kbit/s) equivale a "
                     rf"$\approx {br(bdp, 1)}$ segmentos entregues por RTT "
                     r"(vazão $\times$ RTT$/L$): é o produto banda $\times$ atraso do "
                     r"caminho, e janelas maiores que isso só acumulam pedidos "
                     r"esperando na fila.")
        else:
            extra = (rf"A maior vazão medida ({br(vmax)}\,kbit/s) equivale a "
                     rf"$\approx {br(bdp, 1)}$ segmentos entregues por RTT mediano, "
                     r"abaixo dos 16 da janela, porque parte do tempo a janela fica "
                     r"parada esperando o \texttt{DATA} mais lento. A estabilização "
                     r"ocorreria na janela em que $N \times L/\mathrm{RTT}$ alcançasse "
                     r"a banda disponível.")
        out.append(rf"\par {concl} {extra} Ver Figura~\ref{{fig:janela}}.")
        out.append(ruido_sem_perda(data))

    # (b) retransmissões por erro, janela 16 e 10%
    out.append(r"\subsection*{(b) Retransmissões por erro com 10\% de perda e "
               r"janela 16}")
    g = data.get(name("gbn", 16, 0.10))
    s = data.get(name("sr", 16, 0.10))
    if g and s:
        out.append(
            r"No GBN, cada timeout da base reenvia a janela inteira, somando $+1$ na "
            r"coluna \texttt{retransmissions} de até 16 segmentos consecutivos. "
            rf"Separando esses blocos no CSV, houve {g['eventos_timeout']} timeouts e "
            rf"{g['retransmissoes']} \texttt{{REQ}}s reenviados: "
            rf"\textbf{{{br(g['retx_por_timeout'], 1)} segmentos retransmitidos por "
            r"erro}, praticamente a janela inteira. No SR, cada timeout reenvia um "
            rf"único \texttt{{REQ}}: houve {s['retransmissoes']} retransmissões para "
            rf"{s['erros_simulados']} segmentos com \texttt{{loss\_simulated}}$=1$, ou "
            rf"\textbf{{{br(s['retx_por_erro'], 2)} por erro}}. O valor fica um pouco "
            r"acima de 1 porque o próprio reenvio também pode ser descartado. "
            rf"No total, o GBN reenviou "
            rf"\textbf{{{br(g['retransmissoes'] / max(s['retransmissoes'], 1), 1)}$\times$}} "
            r"mais \texttt{REQ}s que o SR. O GBN também marcou mais segmentos com "
            rf"perda simulada ({g['erros_simulados']} contra {s['erros_simulados']}), "
            r"porque recebe muito mais \texttt{DATA}s, e cada reenvio da janela é "
            r"exposto de novo aos 10\% de descarte (Figura~\ref{fig:segmentos}).")
        eg, es = exemplo_gbn(g["rows"], 16), exemplo_sr(s["rows"])
        if eg and es:
            out.append(
                rf"\par Um exemplo do CSV: no GBN, o primeiro timeout ocorreu na base "
                rf"\texttt{{seq={eg[0]}}}, e as linhas {eg[0]} a {eg[0] + eg[1] - 1} "
                rf"(o bloco de {eg[1]} segmentos daquela janela) passaram a ter "
                r"\texttt{retransmissions}$\geq1$, todos reenviados por causa de um único "
                r"\texttt{DATA} perdido. No SR, o primeiro segmento "
                rf"retransmitido foi o \texttt{{seq={es[0]}}}, e "
                + (r"nenhum dos três vizinhos de cada lado foi reenviado."
                   if es[1] == 0 else
                   rf"só {es[1]} dos seis vizinhos mais próximos também foi reenviado, "
                   r"por perdas próprias."))

    # (c) por que GBN sofre mais
    out.append(r"\subsection*{(c) Por que o GBN sofre mais que o SR com alta perda}")
    linhas = []
    for w in (4, 8, 16):
        tg, ts_ = t("gbn", w, 0.10), t("sr", w, 0.10)
        rg = get(data, "gbn", w, 0.10, "retransmissoes")
        rs = get(data, "sr", w, 0.10, "retransmissoes")
        dg = get(data, "gbn", w, 0.10, "tempo_s")
        ds = get(data, "sr", w, 0.10, "tempo_s")
        if None in (tg, ts_, rg, rs, dg, ds):
            continue
        linhas.append(
            rf"com $N={w}$, o GBN fez {br(rg, 0)} retransmissões e levou {br(dg)}\,s "
            rf"({br(tg)}\,kbit/s), contra {br(rs, 0)} retransmissões e {br(ds)}\,s "
            rf"({br(ts_)}\,kbit/s) do SR")
    if linhas:
        out.append(r"Com 10\% de perda (Tabela~\ref{tab:comparativa}), " +
                   "; ".join(linhas) + ".")
    g4, g16 = t("gbn", 4, 0.10), t("gbn", 16, 0.10)
    s4, s16 = t("sr", 4, 0.10), t("sr", 16, 0.10)
    gbn_piora = False
    if None not in (g4, g16, s4, s16):
        dg, ds = g16 / g4 - 1, s16 / s4 - 1
        gbn_piora = dg < 0.10
        out.append(
            rf"Com 10\% de perda, aumentar a janela de 4 para 16 mudou o throughput "
            rf"do GBN em {'+' if dg >= 0 else ''}{pct(dg)} e o do SR em "
            rf"{'+' if ds >= 0 else ''}{pct(ds)}.")
    out.append(
        r"\par A diferença vem do receptor. O GBN não guarda segmentos fora de "
        r"ordem: quando o \texttt{DATA} da base se perde, os $N-1$ \texttt{DATA}s "
        r"seguintes, que chegaram corretamente, são descartados, e todos são "
        r"pedidos de novo após o timeout. Com perda $p$, a chance de uma janela de "
        r"$N$ segmentos passar sem nenhum erro é $(1-p)^N$, que vale "
        rf"{pct(0.9 ** 16)} para $p=10\%$ e $N=16$. Quase toda janela tem um erro, e "
        r"cada erro custa até $N$ reenvios. "
        + (r"Por isso, nos dados, janelas maiores \textbf{não melhoram} o GBN "
           r"sob perda alta: o trabalho ganho com o paralelismo é jogado fora a "
           r"cada erro, e o próprio reenvio de $N$ segmentos volta a sofrer perdas "
           r"(com $N=16$, há 81\% de chance de pelo menos mais um erro no reenvio). "
           if gbn_piora else
           r"Quanto maior a janela, mais trabalho já feito é jogado fora a cada "
           r"erro. ")
        + r"O SR guarda os segmentos "
        r"fora de ordem no buffer e reenvia só o que faltou: o custo de um erro é um "
        r"\texttt{REQ}, independentemente de $N$. Enquanto espera o timeout do "
        r"segmento perdido, ele continua recebendo o resto da janela, e por isso "
        r"janelas maiores continuam ajudando o SR mesmo com perda.")
    return "\n\n".join(out) + "\n"


def ruido_sem_perda(data):
    """Parágrafo sobre RTT por execução e perdas naturais nos cenários sem perda."""
    itens, rtts, naturais = [], [], []
    for p, w in CONFIGS:
        d = data.get(name(p, w, 0.0))
        if not d or not d["rtt_mediano_ms"]:
            continue
        ideal = w * 512 * 8 / d["rtt_mediano_ms"]
        rtts.append(d["rtt_mediano_ms"])
        itens.append(d["throughput_kbps"] / ideal)
        if d["retransmissoes"]:
            sem = d["tempo_s"] - d["eventos_timeout"] * d["run"]["timeout_ms"] / 1000
            plural = d["eventos_timeout"] > 1
            naturais.append(
                rf"no {NOME[p]} com $N={w}$, {d['eventos_timeout']} "
                rf"timeout{'s' if plural else ''} "
                rf"({d['retransmissoes']} \texttt{{REQ}}s reenviados) "
                rf"{'custaram' if plural else 'custou'} "
                rf"$\approx {br(d['eventos_timeout'] * d['run']['timeout_ms'] / 1000, 0)}$\,s "
                rf"de {br(d['tempo_s'])}\,s; sem {'eles' if plural else 'ele'}, a vazão seria "
                rf"$\approx {br(d['bytes'] * 8 / sem / 1000, 0)}$\,kbit/s")
    if not itens:
        return ""
    txt = (rf"\par Dois cuidados na leitura desses números. Primeiro, cada cenário "
           rf"foi executado uma vez, e o RTT mediano variou de {br(min(rtts), 1)} a "
           rf"{br(max(rtts), 1)}\,ms entre as execuções. Medida contra o ideal "
           rf"$N \times L/\mathrm{{RTT}}$ da própria execução, a eficiência ficou "
           rf"entre {pct(min(itens))} e {pct(max(itens))}, porque os picos de RTT "
           r"seguram a janela e o \texttt{DATA} mais lento atrasa o deslizamento.")
    if naturais:
        txt += (r" Segundo, mesmo sem perda simulada houve \textbf{perda natural} na "
                r"rede (retransmissões com \texttt{loss\_simulated}$=0$): "
                + "; ".join(naturais)
                + r". Numa transferência de poucos segundos, um único timeout de 1\,s "
                  r"pesa muito na média.")
    return txt


def conclusao(data):
    t = lambda p, w, l: get(data, p, w, l, "throughput_kbps")  # noqa: E731
    partes = []
    saw0, g16, s16 = t("saw", 1, 0.0), t("gbn", 16, 0.0), t("sr", 16, 0.0)
    if None not in (saw0, g16, s16):
        partes.append(
            rf"Sem perda, a janela deslizante eliminou o limite de um segmento por RTT "
            rf"do SAW: com $N=16$, GBN e SR chegaram a {br(g16)} e {br(s16)}\,kbit/s, "
            rf"{br(g16 / saw0, 1)}$\times$ e {br(s16 / saw0, 1)}$\times$ o SAW"
            + (r", com desempenho equivalente entre si."
               if abs(g16 / s16 - 1) < 0.15 else
               r". A diferença entre os dois sem perda veio das condições da rede "
               r"em cada execução (perda natural e variação do RTT), e não do "
               r"protocolo."))
    g10, s10 = t("gbn", 16, 0.10), t("sr", 16, 0.10)
    rg = get(data, "gbn", 16, 0.10, "retransmissoes")
    rs = get(data, "sr", 16, 0.10, "retransmissoes")
    if None not in (g10, s10, rg, rs):
        melhor = "SR" if s10 > g10 else "GBN"
        partes.append(
            rf"Com 10\% de perda e $N=16$, o GBN fez {br(rg, 0)} retransmissões contra {br(rs, 0)} "
            rf"do SR, e o {melhor} teve a maior vazão ({br(max(g10, s10))} contra "
            rf"{br(min(g10, s10))}\,kbit/s): cada erro custa até $N$ reenvios no "
            r"GBN e um único reenvio no SR.")
    partes.append(
        r"Em todos os protocolos, o timeout fixo de \eTimeout\,ms ainda é o maior "
        r"custo de cada perda, dezenas de vezes o RTT. Isso motiva o timeout "
        r"adaptativo por EWMA da próxima entrega.")
    return " ".join(partes) + "\n"


def macros(data):
    """Valores usados no texto fixo do relatório (metodologia)."""
    runs = [d["run"] for d in data.values()]
    inicio = min(r["inicio"] for r in runs)
    fim = max(r["inicio"] for r in runs)
    d0 = datetime.fromisoformat(inicio)
    d1 = datetime.fromisoformat(fim)
    quando = (f"{d0:%d/%m/%Y}, entre {d0:%H:%M} e {d1:%H:%M}"
              if d0.date() == d1.date()
              else f"de {d0:%d/%m/%Y %H:%M} a {d1:%d/%m/%Y %H:%M}")
    r0 = runs[0]
    seg = next(iter(data.values()))["segmentos"]
    ok = sum(1 for r in runs if r.get("md5") and r.get("md5") == r.get("md5_expected")
             and r.get("done_ok") == 1)
    return "\n".join([
        rf"\newcommand{{\eArquivo}}{{\texttt{{{r0['arquivo']}}}}}",
        rf"\newcommand{{\eSegmentos}}{{{br(seg, 0)}}}",
        rf"\newcommand{{\eTimeout}}{{{br(r0['timeout_ms'], 0)}}}",
        rf"\newcommand{{\eSeed}}{{{r0['seed']}}}",
        rf"\newcommand{{\eQuando}}{{{quando}}}",
        rf"\newcommand{{\eExecucoes}}{{{len(runs)}}}",
        rf"\newcommand{{\eExecucoesOk}}{{{ok}}}",
        rf"\newcommand{{\eRttMediano}}{{{br(get(data, 'saw', 1, 0.0, 'rtt_mediano_ms') or 0, 2)}}}",
    ]) + "\n"


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--results", default=os.path.join("results", "entrega02"))
    parser.add_argument("--report", default="report")
    args = parser.parse_args()

    data = load(os.path.join(ROOT, args.results))
    if not data:
        print("nenhum resultado encontrado", file=sys.stderr)
        return 1
    gen = os.path.join(ROOT, args.report, "gerado")
    figs = os.path.join(ROOT, args.report, "figuras")
    os.makedirs(gen, exist_ok=True)
    os.makedirs(figs, exist_ok=True)

    campos = ["cenario", "protocolo", "janela", "perda", "segmentos", "bytes",
              "tempo_s", "throughput_kbps", "retransmissoes",
              "segmentos_com_retx", "erros_simulados", "eventos_timeout",
              "retx_por_erro", "retx_por_timeout", "rtt_mediano_ms", "md5",
              "done_ok"]
    with open(os.path.join(gen, "resumo_entrega02.csv"), "w", newline="",
              encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=campos)
        wr.writeheader()
        for n, d in sorted(data.items()):
            run = d["run"]
            wr.writerow({"cenario": n, "protocolo": run["protocolo"],
                         "janela": run["janela"], "perda": run["perda"],
                         "md5": run.get("md5"), "done_ok": run.get("done_ok"),
                         **{k: (round(d[k], 4) if isinstance(d[k], float) else d[k])
                            for k in campos if k in d}})

    with open(os.path.join(gen, "tabela_comparativa.tex"), "w", encoding="utf-8") as f:
        f.write(tabela_comparativa(data))
    with open(os.path.join(gen, "tabela_md5.tex"), "w", encoding="utf-8") as f:
        f.write(tabela_md5(data))
    with open(os.path.join(gen, "analise.tex"), "w", encoding="utf-8") as f:
        f.write(analise(data))
    with open(os.path.join(gen, "conclusao.tex"), "w", encoding="utf-8") as f:
        f.write(conclusao(data))
    with open(os.path.join(gen, "dados.tex"), "w", encoding="utf-8") as f:
        f.write(macros(data))
    fig_janela(data, os.path.join(figs, "e2_janela_sem_perda.png"))
    fig_segmentos(data, os.path.join(figs, "e2_segmentos_w16_p10.png"))

    print(f"{len(data)}/21 cenários analisados")
    for n, d in sorted(data.items()):
        print(f"  {n:13s} {d['throughput_kbps']:9.1f} kbit/s  retx={d['retransmissoes']:5d}"
              f"  tempo={d['tempo_s']:7.1f} s  erros={d['erros_simulados']}")
    print(f"peças geradas em {os.path.relpath(gen, ROOT)} e "
          f"{os.path.relpath(figs, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
