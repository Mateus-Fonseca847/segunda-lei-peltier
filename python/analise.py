"""
Análise dos ensaios — Segunda Lei com Peltier e Arduino

Lê os arquivos gravados pelo painel (ensaio0_*, ensaio1_*, ensaio2_*), calcula
as perdas para o ambiente, o calor que atravessa o Peltier, o trabalho elétrico,
as eficiências e a produção de entropia, e gera figuras e uma tabela de resultados.

Uso (dentro da pasta python/):
    python analise.py                         # usa os arquivos mais recentes de ../dados
    python analise.py --tamb 24.5             # temperatura ambiente medida (°C)
    python analise.py --massa-recipiente 0.06 --c-recipiente 460
    python analise.py --ensaio1 ../dados/meu_arquivo.csv
    python analise.py --pasta montagem_2  # dados em ../dados/montagem_2/

Saídas: ../figuras/*.png e ../resultados.md

Modelo (versão com banho de gelo, Tf = 0 °C):
  Ensaio 0  — as duas caixas com a mesma água quente: não passa calor pelo Peltier,
              então  perda(T) = C · (−dT/dt)  mede só a troca da caixa quente com o ar.
  Ensaios 1 e 2 —  Q̇q = C · (−dTq/dt) − perda(Tq)     (calor que atravessa o Peltier)
                   P  = V² / R                         (só no Ensaio 2, com carga)
                   Q̇f = Q̇q − P                         (calor entregue ao gelo)
                   Ṡ  = Q̇f / Tf − Q̇q / Tq ≥ 0          (produção de entropia)
  com C = m_água · c_água + m_recipiente · c_recipiente.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter

C_AGUA = 4190.0                 # J/(kg·K)
T_FRIO_C = 0.0                  # banho de gelo
K = 273.15

_BASE = Path(__file__).resolve().parent
RAIZ = _BASE.parent if _BASE.name == "python" else _BASE
DADOS = RAIZ / "dados"
FIGURAS = RAIZ / "figuras"
SAIDA = FIGURAS                          # muda com --pasta
RESULTADOS = RAIZ / "resultados.md"


# ----------------------------------------------------------------------------
# Leitura e preparação
# ----------------------------------------------------------------------------
def mais_recente(prefixo, pasta):
    candidatos = sorted(Path(pasta).glob(f"{prefixo}_*.csv"), key=lambda p: p.stat().st_mtime)
    return candidatos[-1] if candidatos else None


def carregar(caminho, janela):
    """Lê o CSV (+ .json), reamostra em 1 s e calcula temperatura suavizada e dT/dt."""
    caminho = Path(caminho)
    df = pd.read_csv(caminho).dropna()
    meta_path = caminho.with_suffix(".json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    t = df["t_s"].to_numpy(float)
    ordem = np.argsort(t)
    t, tq, v = t[ordem], df["Tq_C"].to_numpy(float)[ordem], df["V_V"].to_numpy(float)[ordem]
    tu = np.arange(t[0], t[-1], 1.0)                       # grade uniforme de 1 s
    tq_u, v_u = np.interp(tu, t, tq), np.interp(tu, t, v)

    w = min(janela, len(tu) - (1 - len(tu) % 2))           # janela ímpar e menor que os dados
    w = w if w % 2 == 1 else w - 1
    tq_s = savgol_filter(tq_u, w, 2)
    dtq = savgol_filter(tq_u, w, 2, deriv=1, delta=1.0)
    v_s = savgol_filter(v_u, w, 2)

    # descarta o aquecimento inicial do sensor (~40 s após o pico) e a borda do filtro
    inicio = int(np.argmax(tq_u)) + 40 + w // 2
    fim = len(tu) - w // 2
    sel = slice(inicio, fim)
    return {
        "arquivo": caminho.name, "meta": meta,
        "t": tu[sel] - tu[sel][0], "Tq": tq_s[sel], "dTq": dtq[sel], "V": v_s[sel],
        "Tq_bruto": tq_u, "t_bruto": tu - tu[0],
    }


def capacidade(meta, args):
    m_agua = float(meta.get("massa_agua_quente_kg", args.massa_agua or 0.100))
    if args.massa_agua:
        m_agua = args.massa_agua
    return m_agua * C_AGUA + args.massa_recipiente * args.c_recipiente, m_agua


# ----------------------------------------------------------------------------
# Ensaio 0 — curva de perdas
# ----------------------------------------------------------------------------
def ajustar_perdas(e0, args):
    C, m = capacidade(e0["meta"], args)
    x = e0["Tq"] - args.tamb
    perda = C * (-e0["dTq"])
    A = np.column_stack([x, x ** 2])                       # perda = a·ΔT + b·ΔT²  (zero no ambiente)
    (a, b), *_ = np.linalg.lstsq(A, perda, rcond=None)
    residuo = perda - A @ np.array([a, b])
    return {
        "a": a, "b": b, "C": C, "massa": m, "x": x, "perda": perda,
        "faixa": (float(e0["Tq"].min()), float(e0["Tq"].max())),
        "rms": float(np.sqrt(np.mean(residuo ** 2))),
        "f": lambda T: a * (T - args.tamb) + b * (T - args.tamb) ** 2,
    }


# ----------------------------------------------------------------------------
# Ensaios 1 e 2 — fluxos, eficiência e entropia
# ----------------------------------------------------------------------------
def integrar(y, t):
    return float(np.trapezoid(y, t)) if hasattr(np, "trapezoid") else float(np.trapz(y, t))


def analisar(e, perdas, com_carga, args):
    C, m = capacidade(e["meta"], args)
    R = float(e["meta"].get("resistor_carga_ohm", args.resistor))
    Tq_K, Tf_K = e["Tq"] + K, T_FRIO_C + K

    total = C * (-e["dTq"])                                # calor que a água quente perde
    perda = perdas["f"](e["Tq"])
    Qq = total - perda                                     # calor que atravessa o Peltier
    P = e["V"] ** 2 / R if com_carga else np.zeros_like(Qq)
    Qf = Qq - P
    S = Qf / Tf_K - Qq / Tq_K

    # sensibilidade: perdas 20 % menores ou maiores
    S_baixo = (total - 0.8 * perda - P) / Tf_K - (total - 0.8 * perda) / Tq_K
    S_alto = (total - 1.2 * perda - P) / Tf_K - (total - 1.2 * perda) / Tq_K

    eta_c = 1 - Tf_K / Tq_K
    valido = Qq > 0.2
    eta = np.where(valido, P / np.where(valido, Qq, 1), np.nan)

    r = {
        "nome": e["arquivo"], "C": C, "massa": m, "R": R, "carga": com_carga,
        "t": e["t"], "Tq": e["Tq"], "V": e["V"], "total": total, "perda": perda,
        "Qq": Qq, "P": P, "Qf": Qf, "S": S, "S_baixo": S_baixo, "S_alto": S_alto,
        "eta": eta, "eta_c": eta_c,
        "duracao": float(e["t"][-1]),
        "faixa": (float(e["Tq"].min()), float(e["Tq"].max())),
        "Qq_tot": integrar(Qq, e["t"]), "perda_tot": integrar(perda, e["t"]),
        "W_tot": integrar(P, e["t"]), "S_tot": integrar(S, e["t"]),
        "S_tot_baixo": integrar(S_baixo, e["t"]), "S_tot_alto": integrar(S_alto, e["t"]),
        "frac_S_pos": float(np.mean(S > 0)),
        "frac_perda": integrar(perda, e["t"]) / max(integrar(total, e["t"]), 1e-9),
        "eta_med": float(np.nanmean(eta)) if com_carga else 0.0,
        "eta_c_med": float(np.mean(eta_c)),
        "extrapola": e["Tq"].max() > perdas["faixa"][1] + 1 or e["Tq"].min() < perdas["faixa"][0] - 1,
    }
    dT = e["Tq"] - T_FRIO_C
    r["seebeck"] = float(np.polyfit(dT, e["V"], 1)[0]) if len(dT) > 10 else np.nan
    return r


# ----------------------------------------------------------------------------
# Figuras
# ----------------------------------------------------------------------------
def fig_perdas(e0, perdas):
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].plot(e0["t_bruto"], e0["Tq_bruto"], color="#d6604d")
    ax[0].set(xlabel="Tempo (s)", ylabel="Temperatura (°C)", title="Ensaio 0 — água quente nos dois lados")
    ax[0].grid(alpha=0.3)
    T = np.linspace(*perdas["faixa"], 100)
    ax[1].plot(e0["Tq"], perdas["perda"], ".", ms=2, color="#999999", label="medido")
    ax[1].plot(T, perdas["f"](T), color="#2166ac", lw=2,
               label=f"ajuste: {perdas['a']:.3f}·ΔT + {perdas['b']:.4f}·ΔT²")
    ax[1].set(xlabel="Temperatura da água (°C)", ylabel="Perda para o ambiente (W)",
              title="Perda em função da temperatura")
    ax[1].legend(); ax[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(SAIDA / "ensaio0_perdas.png", dpi=150); plt.close(fig)


def fig_ensaio(r, numero):
    fig, ax = plt.subplots(2, 2, figsize=(12, 8))
    titulo = "com carga (gera trabalho)" if r["carga"] else "sem carga (só conduz calor)"
    fig.suptitle(f"Ensaio {numero} — {titulo}", fontsize=13)

    ax[0, 0].plot(r["t"], r["Tq"], color="#d6604d", label="Água quente")
    ax[0, 0].axhline(T_FRIO_C, color="#4393c3", ls="--", label="Banho de gelo (0 °C)")
    ax[0, 0].set(xlabel="Tempo (s)", ylabel="Temperatura (°C)", title="Temperaturas")
    ax[0, 0].legend(); ax[0, 0].grid(alpha=0.3)

    ax[0, 1].plot(r["t"], r["total"], color="#777777", label="Total perdido pela água")
    ax[0, 1].plot(r["t"], r["perda"], color="#bbbbbb", ls="--", label="Perda para o ar (Ensaio 0)")
    ax[0, 1].plot(r["t"], r["Qq"], color="#d6604d", lw=2, label="Atravessa o Peltier (Q̇q)")
    if r["carga"]:
        ax[0, 1].plot(r["t"], r["Qf"], color="#4393c3", lw=1.2, label="Chega ao gelo (Q̇f)")
    ax[0, 1].set(xlabel="Tempo (s)", ylabel="Potência térmica (W)", title="Fluxos de calor (1ª lei)")
    ax[0, 1].legend(fontsize=8); ax[0, 1].grid(alpha=0.3)

    ax[1, 0].fill_between(r["t"], r["S_baixo"], r["S_alto"], color="#b8e186", alpha=0.6,
                          label="perdas ±20 %")
    ax[1, 0].plot(r["t"], r["S"], color="#4d9221", lw=1.8, label="Ṡ gerada")
    ax[1, 0].axhline(0, color="k", lw=0.8)
    ax[1, 0].set(xlabel="Tempo (s)", ylabel="W/K", title="Produção de entropia (2ª lei)")
    ax[1, 0].legend(fontsize=8); ax[1, 0].grid(alpha=0.3)

    if r["carga"]:
        ax[1, 1].semilogy(r["t"], 100 * r["eta_c"], color="#2166ac", label="Limite de Carnot")
        ax[1, 1].semilogy(r["t"], 100 * r["eta"], color="#d6604d", label="Eficiência real")
        ax[1, 1].set(xlabel="Tempo (s)", ylabel="% (escala log)", title="Eficiência × Carnot")
    else:
        dT = r["Tq"] - T_FRIO_C
        ax[1, 1].plot(dT, 1000 * r["V"], ".", ms=2, color="#4d9221", label="medido")
        ax[1, 1].plot(dT, 1000 * r["seebeck"] * dT, color="#333333",
                      label=f"V ≈ {1000 * r['seebeck']:.2f} mV/K × ΔT")
        ax[1, 1].set(xlabel="Diferença entre as águas (K)", ylabel="Tensão em aberto (mV)",
                     title="Efeito Seebeck: tensão cresce com ΔT")
    ax[1, 1].legend(fontsize=8); ax[1, 1].grid(alpha=0.3, which="both")
    fig.tight_layout(); fig.savefig(SAIDA / f"ensaio{numero}.png", dpi=150); plt.close(fig)


def fig_comparacao(ensaios):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    cores = {0: "#999999", 1: "#d6604d", 2: "#2166ac"}
    rotulos = {0: "Ensaio 0 (sem fluxo pelo Peltier)", 1: "Ensaio 1 (sem carga)", 2: "Ensaio 2 (com carga)"}
    for n, e in ensaios.items():
        ax.plot(e["t_bruto"], e["Tq_bruto"], color=cores[n], label=rotulos[n])
    ax.set(xlabel="Tempo (s)", ylabel="Temperatura da água quente (°C)",
           title="Com o Peltier ligado ao gelo, a água quente esfria mais rápido")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(SAIDA / "comparacao_ensaios.png", dpi=150); plt.close(fig)


# ----------------------------------------------------------------------------
# Relatório
# ----------------------------------------------------------------------------
def relatorio(perdas, resultados, args, avisos):
    L = ["# Resultados\n",
         f"Gerado por `python/analise.py` · temperatura ambiente usada: {args.tamb:.1f} °C · "
         f"recipiente: {args.massa_recipiente * 1000:.0f} g × {args.c_recipiente:.0f} J/(kg·K)\n",
         "## Ensaio 0 — perdas para o ambiente\n",
         f"Perda(T) = {perdas['a']:.3f}·(T − T_amb) + {perdas['b']:.4f}·(T − T_amb)² W, "
         f"válida de {perdas['faixa'][0]:.1f} a {perdas['faixa'][1]:.1f} °C "
         f"(resíduo rms {perdas['rms']:.2f} W).\n",
         "## Ensaios 1 e 2\n",
         "| Grandeza | " + " | ".join(f"Ensaio {n}" for n in resultados) + " |",
         "| --- | " + " | ".join("---" for _ in resultados) + " |"]

    def linha(nome, fmt):
        L.append(f"| {nome} | " + " | ".join(fmt(r) for r in resultados.values()) + " |")

    linha("Arquivo", lambda r: f"`{r['nome']}`")
    linha("Resistor de carga", lambda r: f"{r['R']:.2f} Ω" if r["carga"] else "desconectado")
    linha("Duração analisada", lambda r: f"{r['duracao']:.0f} s")
    linha("Faixa de temperatura", lambda r: f"{r['faixa'][1]:.1f} → {r['faixa'][0]:.1f} °C")
    linha("Calor que atravessou o Peltier", lambda r: f"{r['Qq_tot'] / 1000:.2f} kJ")
    linha("Calor perdido para o ar", lambda r: f"{r['perda_tot'] / 1000:.2f} kJ ({100 * r['frac_perda']:.0f} % do total)")
    linha("Trabalho elétrico", lambda r: f"{r['W_tot']:.2f} J" if r["carga"] else "0 (sem carga)")
    linha("Eficiência real média", lambda r: f"{100 * r['eta_med']:.3f} %" if r["carga"] else "—")
    linha("Limite de Carnot médio", lambda r: f"{100 * r['eta_c_med']:.1f} %")
    linha("Entropia gerada (total)", lambda r: f"{r['S_tot']:.2f} J/K (de {min(r['S_tot_baixo'], r['S_tot_alto']):.2f} a {max(r['S_tot_baixo'], r['S_tot_alto']):.2f})")
    linha("Pontos com Ṡ > 0", lambda r: f"{100 * r['frac_S_pos']:.0f} %")
    linha("Coef. Seebeck efetivo", lambda r: f"{1000 * r['seebeck']:.2f} mV/K" if not r["carga"] else "—")

    L += ["", "O intervalo da entropia corresponde a perdas 20 % menores ou maiores que as do ajuste.",
          "O coeficiente Seebeck efetivo usa a diferença entre as águas, e não entre as faces do módulo;",
          "por isso ele inclui as quedas de temperatura nos contatos e fica abaixo do valor do módulo.", ""]
    if avisos:
        L += ["## Avisos\n"] + [f"- {a}" for a in avisos]
    texto = "\n".join(L) + "\n"
    RESULTADOS.write_text(texto, encoding="utf-8")
    return texto


# ----------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Análise dos ensaios da segunda lei")
    p.add_argument("--ensaio0"); p.add_argument("--ensaio1"); p.add_argument("--ensaio2")
    p.add_argument("--tamb", type=float, default=24.0, help="temperatura ambiente (°C)")
    p.add_argument("--massa-agua", type=float, default=None,
                   help="massa de água quente (kg); por padrão vem do .json")
    p.add_argument("--resistor", type=float, default=2.2, help="usado se o .json não tiver o valor")
    p.add_argument("--massa-recipiente", type=float, default=0.0,
                   help="massa da caixa quente vazia (kg), para incluir a capacidade térmica dela")
    p.add_argument("--c-recipiente", type=float, default=460.0,
                   help="calor específico da caixa (J/kg·K): aço 460, alumínio 900")
    p.add_argument("--janela", type=int, default=41, help="pontos do filtro de suavização (s)")
    p.add_argument("--pasta", default=None,
                   help="subpasta de dados/ com uma montagem (ex.: montagem_1); "
                        "as figuras vão para figuras/<pasta> e a tabela para resultados_<pasta>.md")
    args = p.parse_args()

    global SAIDA, RESULTADOS
    pasta = DADOS / args.pasta if args.pasta else DADOS
    if args.pasta:
        SAIDA, RESULTADOS = FIGURAS / args.pasta, RAIZ / f"resultados_{args.pasta}.md"
    SAIDA.mkdir(parents=True, exist_ok=True)
    caminhos = {n: getattr(args, f"ensaio{n}") or mais_recente(f"ensaio{n}", pasta) for n in (0, 1, 2)}
    if not caminhos[0]:
        raise SystemExit(f"Não encontrei o Ensaio 0 em {pasta}. Ele é obrigatório para descontar as perdas.")

    ensaios = {n: carregar(c, args.janela) for n, c in caminhos.items() if c}
    perdas = ajustar_perdas(ensaios[0], args)
    fig_perdas(ensaios[0], perdas)

    resultados, avisos = {}, []
    for n in (1, 2):
        if n in ensaios:
            r = analisar(ensaios[n], perdas, com_carga=(n == 2), args=args)
            resultados[n] = r
            fig_ensaio(r, n)
            if r["extrapola"]:
                avisos.append(f"Ensaio {n} passou por temperaturas fora da faixa do Ensaio 0 "
                              f"({perdas['faixa'][0]:.0f}–{perdas['faixa'][1]:.0f} °C); "
                              "nessa parte, a perda foi extrapolada.")
            if r["frac_perda"] > 0.7:
                avisos.append(f"No Ensaio {n}, as perdas para o ar foram {100 * r['frac_perda']:.0f} % do calor "
                              "perdido pela água: o fluxo pelo Peltier é pequeno perto da correção, "
                              "e os valores de entropia têm incerteza grande.")
    fig_comparacao(ensaios)

    print(relatorio(perdas, resultados, args, avisos))
    print(f"Figuras salvas em {SAIDA}")


if __name__ == "__main__":
    main()
