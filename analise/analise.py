"""Estatisticas e graficos dos testes de GET (Trabalho 1 de Redes).

Uso:  .venv/bin/python analise/analise.py  [get | put | comparar]   (padrao: get)

Le testes/<metodo>-<N>-clientes-<arquivo>-<link>/resultados.csv, descarta as
requisicoes com status != 0 e gera, em analise/:
  - estatisticas_<metodo>.csv  (uma linha por cenario x metrica)
  - graficos/<metodo>/*.png             (7 graficos, numerados pela ordem da analise)

Unidade amostral: a REPETICAO. Dentro de uma repeticao os clientes disputam o
mesmo enlace, entao nao sao independentes. Para cada repeticao tiramos a media
dos clientes; media, desvio padrao e IC 95% (t de Student, n-1 g.l.) saem
dessas medias. Mediana, minimo, maximo e p95 saem das requisicoes individuais,
porque descrevem a experiencia de cada cliente (cauda de latencia).
"""

import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

RAIZ = Path(__file__).resolve().parent.parent
TESTES = RAIZ / "testes"
SAIDA = RAIZ / "analise"
METODO = sys.argv[1].lower() if len(sys.argv) > 1 else "get"
GRAFICOS = SAIDA / "graficos" / METODO  # uma pasta por metodo (get, put, comparar)

PADRAO = re.compile(r"^(get|put)-(\d+)-clientes-(pagina_web|video)-(4G|fibra)$")

METRICAS = {
    "rtt_ms": "RTT do connect (ms)",
    "t_req_ms": "tempo de resposta (ms)",
    "t_dados_ms": "tempo de transferencia (ms)",
    "vazao_req_mbps": "vazao da requisicao (Mbps)",
    "vazao_dados_mbps": "vazao dos dados (Mbps)",
    "fracao_dados_pct": "tempo de transferencia / tempo total (%)",
}

# Capacidade do enlace de acesso (core/testes.md). GET trafega no sentido
# servidor -> cliente (download); PUT no sentido cliente -> servidor (upload).
CAPACIDADE = {"get": {"fibra": 400, "4G": 45}, "put": {"fibra": 200, "4G": 22}}

ARQUIVOS = ["pagina_web", "video"]
NOME_ARQUIVO = {"pagina_web": "Pagina web", "video": "Video (~8 MB)"}
LINKS = ["fibra", "4G"]
CLIENTES = [5, 10, 50]

# Paleta categorica validada (dataviz/validate_palette.js, modo claro: PASS)
COR = {"fibra": "#2a78d6", "4G": "#eb6834"}
MARCADOR = {"fibra": "o", "4G": "s"}  # codificacao secundaria (nao so cor)
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRADE = "#e4e3df"
FUNDO = "#fcfcfb"


# ----------------------------------------------------------------- dados

def carregar(metodo: str) -> pd.DataFrame:
    partes = []
    for csv in sorted(TESTES.glob(f"{metodo}-*/resultados.csv")):
        m = PADRAO.match(csv.parent.name)
        if not m:
            continue
        df = pd.read_csv(csv)
        df["clientes"] = int(m.group(2))
        df["arquivo"] = m.group(3)
        df["link"] = m.group(4)
        partes.append(df)
    if not partes:
        sys.exit(f"nenhum resultado de {metodo} em {TESTES}")
    df = pd.concat(partes, ignore_index=True)
    falhas = (df["status"] != 0).sum()
    print(f"{metodo}: {len(df)} requisicoes, {falhas} falhas descartadas")
    df = df[df["status"] == 0].copy()
    df["fracao_dados_pct"] = 100 * df["t_dados_ms"] / df["t_req_ms"]
    return df


CENARIO = ["arquivo", "link", "clientes"]


def por_repeticao(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por (cenario, repeticao): media dos clientes + vazao agregada."""
    g = df.groupby(CENARIO + ["repeticao"])
    rep = g[list(METRICAS)].mean()
    # Vazao agregada: todos os bits entregues na repeticao / tempo do cliente
    # mais lento. Como os clientes partem juntos, o mais lento aproxima o tempo
    # total da rodada (sem os instantes de inicio, e uma estimativa por baixo).
    rep["vazao_agregada_mbps"] = (
        g["bytes"].sum() * 8 / (g["t_req_ms"].max() / 1e3) / 1e6
    )
    return rep.reset_index()


def ic95(x: pd.Series) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    return stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / n**0.5


def estatisticas(df: pd.DataFrame, rep: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for chave, grupo_rep in rep.groupby(CENARIO):
        grupo_req = df.set_index(CENARIO).loc[chave]
        for met in list(METRICAS) + ["vazao_agregada_mbps"]:
            x = grupo_rep[met]
            linha = dict(zip(CENARIO, chave))
            linha.update(
                metrica=met,
                n_rep=len(x),
                media=x.mean(),
                dp=x.std(ddof=1),
                ic95=ic95(x),
            )
            if met in grupo_req:  # agregada nao existe por requisicao
                y = grupo_req[met]
                linha.update(
                    n_req=len(y),
                    mediana_req=y.median(),
                    min_req=y.min(),
                    max_req=y.max(),
                    p95_req=y.quantile(0.95),
                )
            linhas.append(linha)
    est = pd.DataFrame(linhas)
    est["cv_pct"] = 100 * est["dp"] / est["media"]
    return est


# ----------------------------------------------------------------- graficos

def estilo():
    plt.rcParams.update({
        "figure.facecolor": FUNDO,
        "axes.facecolor": FUNDO,
        "axes.edgecolor": GRADE,
        "axes.labelcolor": TEXTO_2,
        "axes.titlecolor": TEXTO,
        "axes.titlesize": 15,
        "axes.titleweight": "bold",
        "axes.titlepad": 14,
        "axes.labelpad": 8,
        "axes.labelsize": 11,
        "legend.fontsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.grid.axis": "y",
        "grid.color": GRADE,
        "grid.linewidth": 0.8,
        "xtick.color": TEXTO_2,
        "ytick.color": TEXTO_2,
        "font.size": 10,
        "legend.frameon": False,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    })


def moldura(fig, titulo, nota, handles, labels):
    """Titulo geral, legenda e nota em faixas fixas, sem encostar no grafico.

    De cima para baixo: titulo geral | titulo de cada grafico (o mais forte,
    via rcParams) | grafico | legenda | nota de leitura.
    """
    fig.subplots_adjust(top=0.78, bottom=0.31, wspace=0.28)
    if METODO in CAPACIDADE:
        titulo = f"{METODO.upper()}: {titulo}"
    fig.suptitle(titulo, x=0.5, y=0.985, ha="center", va="top",
                 color=TEXTO_2, fontsize=13, fontweight="bold")
    fig.legend(handles, labels, loc="lower center", ncol=len(labels),
               bbox_to_anchor=(0.5, 0.115))
    fig.text(0.5, 0.02, nota, ha="center", va="bottom",
             color=TEXTO_2, fontsize=9, linespacing=1.5)


def escala(arquivo: str, met: str):
    """Tempos do video em s; resto (pagina web, RTT, vazao) na unidade original."""
    if met in ("t_req_ms", "t_dados_ms") and arquivo == "video":
        return 1e-3, met.replace("_ms", "").replace("_", " ") + " (s)"
    return 1.0, None


def linhas_por_link(est, met, titulo, nome, ylabel):
    fig, eixos = plt.subplots(1, 2, figsize=(11, 5.4))
    x = range(len(CLIENTES))
    for ax, arq in zip(eixos, ARQUIVOS):
        fator, _ = escala(arq, met)
        unidade = "s" if fator != 1 else ylabel.split("(")[-1].rstrip(")")
        finais = {}
        for link in LINKS:
            d = (est[(est.metrica == met) & (est.arquivo == arq) & (est.link == link)]
                 .set_index("clientes").reindex(CLIENTES))
            ax.errorbar(x, d["media"] * fator, yerr=d["ic95"] * fator,
                        color=COR[link], marker=MARCADOR[link], markersize=7,
                        linewidth=2, capsize=4, label=link)
            finais[link] = d["media"].iloc[-1] * fator
        # rotulo direto no ultimo ponto: o maior sobe, o menor desce (sem colisao)
        alto = max(finais, key=finais.get)
        for link, y in finais.items():
            ax.annotate(link, (x[-1], y), xytext=(10, 7 if link == alto else -7),
                        textcoords="offset points", va="center", color=TEXTO_2)
        ax.set_xticks(list(x), [str(c) for c in CLIENTES])
        ax.set_xlim(-0.3, len(CLIENTES) - 0.4)
        ax.set_xlabel("clientes simultaneos")
        ax.set_ylabel(ylabel.rsplit("(", 1)[0] + f"({unidade})")
        ax.set_title(NOME_ARQUIVO[arq])
    h, l = eixos[0].get_legend_handles_labels()
    moldura(fig, titulo, "pontos: media das 11 repeticoes; barras: IC 95%", h, l)
    fig.savefig(GRAFICOS / nome)
    plt.close(fig)


# Cores por entidade (cada par validado no validate_palette.js, modo claro):
# link = azul/laranja (COR); metrica de vazao = verde-agua/amarelo; arquivo = rosa/verde
COR_MET = {"vazao_req_mbps": "#1baf7a", "vazao_dados_mbps": "#eda100"}
NOME_MET = {"vazao_req_mbps": "requisicao inteira", "vazao_dados_mbps": "so dados"}
COR_ARQ = {"pagina_web": "#e87ba4", "video": "#008300"}


def rotular_barras(ax, barras, fmt="{:.1f}"):
    for b in barras:
        ax.annotate(fmt.format(b.get_height()),
                    (b.get_x() + b.get_width() / 2, b.get_height()),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", color=TEXTO, fontsize=9)


def estabilidade_vazao(df):
    """Boxplot da vazao relativa (vazao / mediana do cenario), por requisicao.

    Dividir pela mediana do proprio cenario poe pagina web e video na mesma
    escala: 1,0 = requisicao tipica. Caixa estreita = vazao estavel. Os dois
    links entram juntos (cada requisicao normalizada pelo seu cenario).
    Outliers ficam de fora do desenho: na pagina web, 'so dados' chega a
    dezenas de vezes a mediana e esmagaria o eixo.
    """
    rel = df.copy()
    for met in COR_MET:
        rel[met] = rel[met] / rel.groupby(CENARIO)[met].transform("median")
    fig, eixos = plt.subplots(1, 2, figsize=(11, 5.4))
    for ax, met in zip(eixos, COR_MET):
        dados, pos, cores = [], [], []
        for i, c in enumerate(CLIENTES):
            for j, arq in enumerate(ARQUIVOS):
                dados.append(rel[(rel.arquivo == arq) & (rel.clientes == c)][met])
                pos.append(i * 3 + j)
                cores.append(COR_ARQ[arq])
        bp = ax.boxplot(dados, positions=pos, widths=0.8, patch_artist=True,
                        showfliers=False,
                        medianprops=dict(color=TEXTO, linewidth=1.5))
        for caixa, cor in zip(bp["boxes"], cores):
            caixa.set_facecolor(cor)
            caixa.set_edgecolor(cor)
        ax.axhline(1, color=TEXTO_2, linestyle="--", linewidth=1)
        ax.set_xticks([i * 3 + 0.5 for i in range(len(CLIENTES))],
                      [str(c) for c in CLIENTES])
        ax.set_xlabel("clientes simultaneos")
        ax.set_ylabel("vazao / mediana do cenario")
        ax.set_title("Vazao " + ("da " if met == "vazao_req_mbps" else "") + NOME_MET[met])
    handles = [plt.Rectangle((0, 0), 1, 1, color=COR_ARQ[a]) for a in ARQUIVOS]
    moldura(fig, "Estabilidade da vazao: pagina web x video",
            "cada caixa: todas as requisicoes (fibra + 4G), cada uma dividida pela "
            "mediana do seu cenario. 1,0 = requisicao tipica.\n"
            "caixa = 50% centrais; hastes = faixa sem outliers (nao desenhados). "
            "Quanto mais estreita a caixa, mais estavel.",
            handles, [NOME_ARQUIVO[a] for a in ARQUIVOS])
    fig.savefig(GRAFICOS / "3_estabilidade_vazao.png")
    plt.close(fig)


def variacao_vazao(df):
    """Mesma ideia do boxplot, em um numero so: coeficiente de variacao (CV).

    CV = desvio padrao / media, em %: quanto a vazao de uma requisicao costuma
    se afastar da media do cenario. 10% = requisicoes quase iguais; 300% =
    cada requisicao da um valor completamente diferente. Calculado entre as
    requisicoes de cada cenario; a barra e a media dos dois links.
    """
    cv = (df.groupby(CENARIO)[list(COR_MET)]
            .agg(lambda x: 100 * x.std(ddof=1) / x.mean())
            .groupby(["arquivo", "clientes"]).mean())
    fig, eixos = plt.subplots(1, 2, figsize=(11, 5.4))
    larg = 0.36
    for ax, met in zip(eixos, COR_MET):
        for j, arq in enumerate(ARQUIVOS):
            pos = [i + (j - 0.5) * (larg + 0.03) for i in range(len(CLIENTES))]
            barras = ax.bar(pos, cv.loc[arq][met].reindex(CLIENTES), width=larg,
                            color=COR_ARQ[arq], label=NOME_ARQUIVO[arq])
            rotular_barras(ax, barras, "{:.0f}%")
        ax.set_xticks(range(len(CLIENTES)), [str(c) for c in CLIENTES])
        ax.set_xlabel("clientes simultaneos")
        ax.set_ylabel("variacao em torno da media (%)")
        ax.set_title("Vazao " + ("da " if met == "vazao_req_mbps" else "") + NOME_MET[met])
        ax.margins(y=0.15)
    h, l = eixos[0].get_legend_handles_labels()
    moldura(fig, "Variacao da vazao entre requisicoes: pagina web x video",
            "barra = coeficiente de variacao (desvio padrao / media) entre as "
            "requisicoes do cenario, media de fibra e 4G.\n"
            "Quanto maior a barra, mais instavel a vazao. Atencao: os dois "
            "graficos tem escalas diferentes.", h, l)
    fig.savefig(GRAFICOS / "3b_variacao_vazao.png")
    plt.close(fig)


def vazao_comparada(est, clientes=5):
    """Vazao da requisicao inteira x so dos dados, com poucos clientes.

    A diferenca entre as duas e o tempo fora da transferencia: handshake e
    espera pela resposta (RTTs). Na pagina web (3 KB) isso domina; no video
    as duas barras ficam iguais. Sem barra de erro: a vazao 'so dados' da
    pagina web varia demais (ver grafico 3) e vale como ordem de grandeza.
    """
    fig, eixos = plt.subplots(1, 2, figsize=(11, 5.4))
    larg = 0.36
    for ax, arq in zip(eixos, ARQUIVOS):
        for j, met in enumerate(COR_MET):
            d = (est[(est.metrica == met) & (est.arquivo == arq)
                     & (est.clientes == clientes)].set_index("link").reindex(LINKS))
            pos = [i + (j - 0.5) * (larg + 0.03) for i in range(len(LINKS))]
            barras = ax.bar(pos, d["media"], width=larg, color=COR_MET[met],
                            label=NOME_MET[met])
            rotular_barras(ax, barras)
        ax.set_xticks(range(len(LINKS)), LINKS)
        ax.set_ylabel("vazao por cliente (Mbps)")
        ax.set_title(NOME_ARQUIVO[arq])
        ax.margins(y=0.15)
    h, l = eixos[0].get_legend_handles_labels()
    moldura(fig, f"Vazao: requisicao inteira x so dados ({clientes} clientes)",
            "requisicao inteira: bytes / tempo do connect ate o ultimo byte\n"
            "so dados: bytes / tempo de transferencia do arquivo", h, l)
    fig.savefig(GRAFICOS / "4a_vazao_requisicao_x_dados.png")
    plt.close(fig)


def fracao_dados(est):
    """% do tempo total da requisicao gasto transferindo o arquivo."""
    fig, eixos = plt.subplots(1, 2, figsize=(11, 5.4), sharey=True)
    larg = 0.36
    for ax, arq in zip(eixos, ARQUIVOS):
        for j, link in enumerate(LINKS):
            d = (est[(est.metrica == "fracao_dados_pct") & (est.arquivo == arq)
                     & (est.link == link)].set_index("clientes").reindex(CLIENTES))
            pos = [i + (j - 0.5) * (larg + 0.03) for i in range(len(CLIENTES))]
            barras = ax.bar(pos, d["media"], width=larg, color=COR[link], label=link)
            rotular_barras(ax, barras, "{:.0f}%")
        ax.set_xticks(range(len(CLIENTES)), [str(c) for c in CLIENTES])
        ax.set_xlabel("clientes simultaneos")
        ax.set_title(NOME_ARQUIVO[arq])
        ax.set_ylim(0, 112)
    eixos[0].set_ylabel("tempo transferindo dados (% do total)")
    h, l = eixos[0].get_legend_handles_labels()
    moldura(fig, "Quanto do tempo da requisicao e transferencia de dados",
            "t_dados / t_req por requisicao, media das 11 repeticoes.\n"
            "O resto e handshake (connect) + espera pela resposta do servidor.", h, l)
    fig.savefig(GRAFICOS / "4b_fracao_tempo_dados.png")
    plt.close(fig)


def ocupacao_link(est):
    """Vazao agregada (soma dos clientes) como % da capacidade do link, video."""
    fig, ax = plt.subplots(figsize=(7, 5.4))
    cap = CAPACIDADE[METODO]
    sentido = "download" if METODO == "get" else "upload"
    larg = 0.36
    for j, link in enumerate(LINKS):
        d = (est[(est.metrica == "vazao_agregada_mbps") & (est.arquivo == "video")
                 & (est.link == link)].set_index("clientes").reindex(CLIENTES))
        pct = 100 * d["media"] / cap[link]
        pos = [i + (j - 0.5) * (larg + 0.03) for i in range(len(CLIENTES))]
        barras = ax.bar(pos, pct, width=larg, color=COR[link],
                        label=f"{link} ({cap[link]} Mbps)")
        for b in barras:
            ax.annotate(f"{b.get_height():.0f}%",
                        (b.get_x() + b.get_width() / 2, b.get_height()),
                        xytext=(0, -14), textcoords="offset points",
                        ha="center", color="white", fontsize=10, fontweight="bold")
    ax.axhline(100, color=TEXTO_2, linestyle="--", linewidth=1)
    ax.annotate("100% = link cheio", (-0.45, 100), xytext=(0, 4),
                textcoords="offset points", ha="left", color=TEXTO_2, fontsize=8)
    ax.set_xticks(range(len(CLIENTES)), [str(c) for c in CLIENTES])
    ax.set_xlabel("clientes simultaneos")
    ax.set_ylabel("uso da capacidade do link (%)")
    ax.set_ylim(0, 118)
    ax.set_title(NOME_ARQUIVO["video"])
    h, l = ax.get_legend_handles_labels()
    moldura(fig, "Ocupacao do link", "soma da vazao de todos os clientes / "
            f"capacidade de {sentido} do link", h, l)
    fig.savefig(GRAFICOS / "6_ocupacao_link.png")
    plt.close(fig)


# ----------------------------------------------------------------- GET x PUT

def comparar_linhas(ests, met, titulo, nome, ylabel):
    """Mesmo grafico de linhas, com GET (cheia) e PUT (tracejada) juntos."""
    fig, eixos = plt.subplots(1, 2, figsize=(11, 5.4))
    x = list(range(len(CLIENTES)))
    tracos = {"get": ("-", True), "put": ("--", False)}
    for ax, arq in zip(eixos, ARQUIVOS):
        fator, _ = escala(arq, met)
        unidade = "s" if fator != 1 else ylabel.split("(")[-1].rstrip(")")
        for link in LINKS:
            for metodo, (ls, cheio) in tracos.items():
                est = ests[metodo]
                d = (est[(est.metrica == met) & (est.arquivo == arq)
                         & (est.link == link)].set_index("clientes").reindex(CLIENTES))
                ax.errorbar(x, d["media"] * fator, yerr=d["ic95"] * fator,
                            color=COR[link], marker=MARCADOR[link], markersize=7,
                            mfc=COR[link] if cheio else FUNDO, linewidth=2,
                            linestyle=ls, capsize=4,
                            label=f"{link}, {metodo.upper()}")
        ax.set_xticks(x, [str(c) for c in CLIENTES])
        ax.set_xlabel("clientes simultaneos")
        ax.set_ylabel(ylabel.rsplit("(", 1)[0] + f"({unidade})")
        ax.set_title(NOME_ARQUIVO[arq])
    h, l = eixos[0].get_legend_handles_labels()
    moldura(fig, "GET x PUT: " + titulo,
            "linha cheia: GET; tracejada: PUT. Pontos: media das 11 repeticoes; "
            "barras: IC 95%", h, l)
    fig.savefig(GRAFICOS / nome)
    plt.close(fig)


def comparar_ocupacao(ests):
    """Ocupacao do link no video: GET sobre o download, PUT sobre o upload."""
    fig, eixos = plt.subplots(1, 2, figsize=(11, 5.4), sharey=True)
    larg = 0.36
    for ax, link in zip(eixos, LINKS):
        for j, metodo in enumerate(["get", "put"]):
            est = ests[metodo]
            d = (est[(est.metrica == "vazao_agregada_mbps") & (est.arquivo == "video")
                     & (est.link == link)].set_index("clientes").reindex(CLIENTES))
            cap = CAPACIDADE[metodo][link]
            pos = [i + (j - 0.5) * (larg + 0.03) for i in range(len(CLIENTES))]
            barras = ax.bar(pos, 100 * d["media"] / cap, width=larg,
                            color=COR[link] if metodo == "get" else FUNDO,
                            edgecolor=COR[link], linewidth=1.5,
                            hatch=None if metodo == "get" else "///",
                            label=metodo.upper())
            rotular_barras(ax, barras, "{:.0f}%")
        ax.axhline(100, color=TEXTO_2, linestyle="--", linewidth=1)
        ax.set_xticks(range(len(CLIENTES)), [str(c) for c in CLIENTES])
        ax.set_xlabel("clientes simultaneos")
        ax.set_title(f"{link} ({CAPACIDADE['get'][link]} down / "
                     f"{CAPACIDADE['put'][link]} up Mbps)")
        ax.set_ylim(0, 118)
    eixos[0].set_ylabel("uso da capacidade do link (%)")
    h = [plt.Rectangle((0, 0), 1, 1, fc=TEXTO_2, ec=TEXTO_2),
         plt.Rectangle((0, 0), 1, 1, fc=FUNDO, ec=TEXTO_2, hatch="///")]
    moldura(fig, "GET x PUT: ocupacao do link no video",
            "soma da vazao de todos os clientes / capacidade do link no sentido "
            "da transferencia\n(GET: download; PUT: upload). 100% = link cheio.",
            h, ["GET", "PUT"])
    fig.savefig(GRAFICOS / "6_ocupacao_link.png")
    plt.close(fig)


def comparar():
    ests = {}
    for metodo in ("get", "put"):
        df = carregar(metodo)
        ests[metodo] = estatisticas(df, por_repeticao(df))
    comparar_linhas(ests, "t_req_ms", "tempo total da requisicao",
                    "1_tempo_requisicao.png", "tempo total (ms)")
    comparar_linhas(ests, "t_dados_ms", "tempo de transferencia dos dados",
                    "2_tempo_transferencia.png", "tempo de transferencia (ms)")
    comparar_linhas(ests, "vazao_req_mbps", "vazao por cliente (requisicao inteira)",
                    "4_vazao_por_cliente.png", "vazao por cliente (Mbps)")
    comparar_linhas(ests, "fracao_dados_pct",
                    "quanto do tempo e transferencia de dados",
                    "4b_fracao_tempo_dados.png", "tempo transferindo dados (%)")
    comparar_linhas(ests, "rtt_ms", "RTT do connect",
                    "5_rtt.png", "RTT (ms)")
    comparar_ocupacao(ests)
    print(f"\nsaida em {GRAFICOS}")


# ----------------------------------------------------------------- main

def resumo_terminal(est):
    cols = ["arquivo", "link", "clientes", "media", "ic95", "cv_pct", "p95_req"]
    for met in ["t_req_ms", "t_dados_ms", "rtt_ms", "vazao_req_mbps",
                "vazao_dados_mbps", "fracao_dados_pct", "vazao_agregada_mbps"]:
        print(f"\n== {met} ==")
        print(est[est.metrica == met][cols].round(2).to_string(index=False))


def main():
    GRAFICOS.mkdir(parents=True, exist_ok=True)
    estilo()
    if METODO == "comparar":
        return comparar()
    df = carregar(METODO)
    rep = por_repeticao(df)
    est = estatisticas(df, rep)
    est.to_csv(SAIDA / f"estatisticas_{METODO}.csv", index=False,
               float_format="%.3f")
    resumo_terminal(est)

    # 1. tempo total da requisicao x quantidade de clientes
    linhas_por_link(est, "t_req_ms",
                    "Tempo total da requisicao (connect ate o ultimo byte)",
                    "1_tempo_requisicao.png", "tempo total (ms)")
    # 2. tempo so da transferencia dos dados, por tecnologia e concorrencia
    linhas_por_link(est, "t_dados_ms", "Tempo de transferencia dos dados",
                    "2_tempo_transferencia.png", "tempo de transferencia (ms)")
    # 3. estabilidade da vazao: pagina web x video
    estabilidade_vazao(df)
    variacao_vazao(df)
    # 4. vazao da requisicao x so dados, e a fracao do tempo que e transferencia
    vazao_comparada(est)
    fracao_dados(est)
    # 5. RTT por concorrencia e tecnologia
    linhas_por_link(est, "rtt_ms", "RTT do connect x concorrencia",
                    "5_rtt.png", "RTT (ms)")
    # 6. ocupacao do link
    ocupacao_link(est)
    print(f"\nsaida em {SAIDA}")


if __name__ == "__main__":
    main()
