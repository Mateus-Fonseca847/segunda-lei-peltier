"""
Painel do experimento — Segunda Lei com Peltier e Arduino

Lê o Arduino pela porta serial, mostra gráficos e valores ao vivo
e grava cada ensaio num arquivo CSV (mais um .json com as anotações).

Requisitos:  pip install pyserial matplotlib numpy
Uso:         python painel.py
"""

import csv
import json
import os
import queue
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import serial
import serial.tools.list_ports
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# ----------------------------------------------------------------------------
# Constantes do experimento
# ----------------------------------------------------------------------------
BAUD = 115200            # precisa ser igual ao Serial.begin() do Arduino
C_AGUA = 4190.0          # calor específico da água, J/(kg·K)
T_FRIO_C = 0.0           # banho de gelo: 0 °C enquanto houver gelo
JANELA_TAXA_S = 30.0     # últimos N segundos usados para estimar dT/dt ao vivo
_BASE = Path(__file__).resolve().parent
PASTA_DADOS = (_BASE.parent if _BASE.name == "python" else _BASE) / "dados"   # no repositório: ../dados


def ler_numero(texto):
    """Aceita '2,2' ou '2.2'."""
    return float(texto.strip().replace(",", "."))


def nome_seguro(texto):
    """Transforma o nome do ensaio num nome de arquivo válido."""
    texto = re.sub(r"[^A-Za-z0-9_-]+", "_", texto.strip())
    return texto.strip("_") or "ensaio"


def leitor_serial(porta, fila, parar):
    """Roda em segundo plano: lê linhas da porta e entrega à janela pela fila.
    (A janela não pode ficar esperando a porta, senão ela congela.)"""
    while not parar.is_set():
        try:
            bruto = porta.readline()
        except (serial.SerialException, OSError, TypeError, AttributeError) as erro:
            if not parar.is_set():
                fila.put(("falha", str(erro)))
            return
        if bruto:
            fila.put(("linha", bruto.decode(errors="ignore").strip()))


class Painel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Segunda Lei — Painel do experimento")
        self.geometry("1300x760")
        self.minsize(1050, 640)
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        try:
            self.state("zoomed")          # tela cheia no Windows
        except tk.TclError:
            pass

        self.fila = queue.Queue()
        self.parar = threading.Event()
        self.porta = None
        self.thread = None
        self.arquivo = None
        self.escritor = None
        self.caminho_csv = None
        self.caminho_meta = None
        self.meta = {}
        self.rodando = False
        self.massa = 0.250
        self.R = 2.2
        self.carga = False
        self.limpar_dados()

        self.montar_interface()
        self.atualizar_portas()

    # ------------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------------
    def montar_interface(self):
        estilo = ttk.Style(self)
        if "clam" in estilo.theme_names():
            estilo.theme_use("clam")
        estilo.configure("Secao.TLabel", font=("Segoe UI", 11, "bold"))
        estilo.configure("Rotulo.TLabel", font=("Segoe UI", 9), foreground="#555555")
        estilo.configure("Valor.TLabel", font=("Segoe UI", 16, "bold"))
        estilo.configure("Grande.TButton", font=("Segoe UI", 11, "bold"), padding=8)

        lateral = ttk.Frame(self, padding=14)
        lateral.pack(side="left", fill="y")
        area_graficos = ttk.Frame(self, padding=(0, 14, 14, 14))
        area_graficos.pack(side="right", fill="both", expand=True)

        # --- Configuração do ensaio -----------------------------------------
        ttk.Label(lateral, text="Configuração do ensaio", style="Secao.TLabel").pack(anchor="w")
        form = ttk.Frame(lateral)
        form.pack(fill="x", pady=(6, 10))

        ttk.Label(form, text="Porta do Arduino").grid(row=0, column=0, sticky="w", pady=3)
        self.porta_var = tk.StringVar()
        self.combo_porta = ttk.Combobox(form, textvariable=self.porta_var, width=26, state="readonly")
        self.combo_porta.grid(row=1, column=0, sticky="we")
        self.botao_portas = ttk.Button(form, text="↻", width=3, command=self.atualizar_portas)
        self.botao_portas.grid(row=1, column=1, padx=(4, 0))

        ttk.Label(form, text="Nome do ensaio").grid(row=2, column=0, sticky="w", pady=(5, 2))
        self.nome_var = tk.StringVar(value="ensaio1")
        self.campo_nome = ttk.Entry(form, textvariable=self.nome_var)
        self.campo_nome.grid(row=3, column=0, columnspan=2, sticky="we")

        ttk.Label(form, text="Massa de água quente (g)").grid(row=4, column=0, sticky="w", pady=(5, 2))
        self.massa_var = tk.StringVar(value="250")
        self.campo_massa = ttk.Entry(form, textvariable=self.massa_var)
        self.campo_massa.grid(row=5, column=0, columnspan=2, sticky="we")

        ttk.Label(form, text="Resistor de carga (Ω)").grid(row=6, column=0, sticky="w", pady=(5, 2))
        self.r_var = tk.StringVar(value="2,2")
        self.campo_r = ttk.Entry(form, textvariable=self.r_var)
        self.campo_r.grid(row=7, column=0, columnspan=2, sticky="we")

        self.carga_var = tk.BooleanVar(value=False)
        self.caixa_carga = ttk.Checkbutton(form, text="Resistor de carga ligado", variable=self.carga_var)
        self.caixa_carga.grid(row=8, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self.gravar_var = tk.BooleanVar(value=True)
        self.caixa_gravar = ttk.Checkbutton(form, text="Gravar em arquivo", variable=self.gravar_var)
        self.caixa_gravar.grid(row=9, column=0, columnspan=2, sticky="w", pady=(4, 0))
        form.columnconfigure(0, weight=1)

        self.campos = [self.combo_porta, self.botao_portas, self.campo_nome, self.campo_massa,
                       self.campo_r, self.caixa_carga, self.caixa_gravar]

        self.botao = ttk.Button(lateral, text="▶  Iniciar", style="Grande.TButton", command=self.alternar)
        self.botao.pack(fill="x", pady=(4, 6))
        ttk.Button(lateral, text="Abrir pasta de dados", command=self.abrir_pasta).pack(fill="x")

        # --- Status ---------------------------------------------------------
        self.status = tk.StringVar(value="Escolha a porta e clique em Iniciar.")
        ttk.Label(lateral, textvariable=self.status, wraplength=280, foreground="#1f5fa8").pack(
            anchor="w", pady=(8, 0))
        self.contador = tk.StringVar(value="")
        ttk.Label(lateral, textvariable=self.contador, style="Rotulo.TLabel").pack(anchor="w")

        ttk.Separator(lateral).pack(fill="x", pady=10)

        # --- Leituras ao vivo -----------------------------------------------
        ttk.Label(lateral, text="Agora", style="Secao.TLabel").pack(anchor="w")
        grade = ttk.Frame(lateral)
        grade.pack(fill="x", pady=(2, 0))
        self.vars = {}
        leituras = [
            ("tempo", "Tempo de ensaio"),     ("Tq", "Água quente"),
            ("V", "Tensão do Peltier"),       ("P", "Potência útil"),
            ("Q", "Calor saindo*"),           ("eta", "Eficiência real*"),
            ("etaC", "Limite de Carnot"),
        ]
        for i, (chave, rotulo) in enumerate(leituras):
            linha, coluna = divmod(i, 2)
            celula = ttk.Frame(grade)
            celula.grid(row=linha, column=coluna, sticky="w", padx=(0, 18), pady=(6, 0))
            ttk.Label(celula, text=rotulo, style="Rotulo.TLabel").pack(anchor="w")
            self.vars[chave] = tk.StringVar(value="—")
            ttk.Label(celula, textvariable=self.vars[chave], style="Valor.TLabel").pack(anchor="w")
        ttk.Label(lateral, text="* estimativa ao vivo pelos últimos 30 s, sem descontar as perdas "
                  "para o ar. Os valores finais saem da análise.",
                  style="Rotulo.TLabel", wraplength=280).pack(anchor="w", pady=(8, 0))

        # --- Gráficos -------------------------------------------------------
        self.figura = Figure(figsize=(8, 6), dpi=100)
        self.ax_t, self.ax_v = self.figura.subplots(2, 1, sharex=True)
        self.figura.subplots_adjust(left=0.09, right=0.97, top=0.95, bottom=0.10, hspace=0.12)

        (self.linha_tq,) = self.ax_t.plot([], [], color="#d6604d", lw=1.8, label="Água quente")
        self.ax_t.axhline(T_FRIO_C, color="#4393c3", lw=1.5, ls="--", label="Banho de gelo (0 °C)")
        self.ax_t.set_ylabel("Temperatura (°C)")
        self.ax_t.legend(loc="upper right")
        self.ax_t.grid(alpha=0.3)

        (self.linha_v,) = self.ax_v.plot([], [], color="#4d9221", lw=1.8)
        self.ax_v.set_ylabel("Tensão do Peltier (V)")
        self.ax_v.set_xlabel("Tempo (s)")
        self.ax_v.grid(alpha=0.3)

        self.canvas = FigureCanvasTkAgg(self.figura, master=area_graficos)
        barra = NavigationToolbar2Tk(self.canvas, area_graficos, pack_toolbar=False)
        barra.update()
        barra.pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().configure(width=500, height=400)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    # ------------------------------------------------------------------------
    # Portas
    # ------------------------------------------------------------------------
    def atualizar_portas(self):
        portas = list(serial.tools.list_ports.comports())
        opcoes = [f"{p.device} — {p.description}" for p in portas]
        self.combo_porta["values"] = opcoes
        if not opcoes:
            self.porta_var.set("")
            self.status.set("Nenhuma porta encontrada. Conecte o Arduino e clique em ↻.")
            return
        preferida = next((o for o in opcoes if re.search(r"arduino|ch340|usb", o, re.I)), opcoes[0])
        if self.porta_var.get() not in opcoes:
            self.porta_var.set(preferida)

    # ------------------------------------------------------------------------
    # Iniciar / parar
    # ------------------------------------------------------------------------
    def alternar(self):
        if self.rodando:
            self.parar_aquisicao("Ensaio parado.")
        else:
            self.iniciar()

    def iniciar(self):
        nome_porta = self.porta_var.get().split(" ")[0]
        if not nome_porta:
            messagebox.showwarning("Sem porta", "Conecte o Arduino, clique em ↻ e escolha a porta.")
            return
        try:
            massa = ler_numero(self.massa_var.get()) / 1000.0
            resistor = ler_numero(self.r_var.get())
            if massa <= 0 or resistor <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Valor inválido",
                                 "Confira a massa e o resistor: use números positivos, como 250 e 2,2.")
            return
        try:
            self.porta = serial.Serial(nome_porta, BAUD, timeout=1)
        except (serial.SerialException, OSError) as erro:
            messagebox.showerror("Não foi possível abrir a porta",
                                 f"{erro}\n\nFeche o Monitor Serial da Arduino IDE (ou a IDE inteira) "
                                 "e confira se a porta escolhida é a do Arduino.")
            self.porta = None
            return

        self.limpar_dados()
        self.linha_tq.set_data([], [])          # apaga o gráfico do ensaio anterior
        self.linha_v.set_data([], [])
        for var in self.vars.values():
            var.set("—")
        self.atualizar_contador()
        self.canvas.draw_idle()
        self.massa, self.R, self.carga = massa, resistor, self.carga_var.get()
        if self.gravar_var.get():
            self.abrir_arquivo(nome_porta)

        self.fila = queue.Queue()
        self.parar.clear()
        self.thread = threading.Thread(target=leitor_serial, args=(self.porta, self.fila, self.parar),
                                       daemon=True)
        self.thread.start()
        self.rodando = True

        self.botao.configure(text="■  Parar")
        for campo in self.campos:
            campo.state(["disabled"])
        destino = f" Gravando em {self.caminho_csv.name}." if self.caminho_csv else " (sem gravar)"
        self.status.set(f"Conectado em {nome_porta}.{destino} O Arduino reinicia ao conectar; "
                        "as leituras começam em 2 a 3 segundos.")
        self.after(200, self.processar_fila)
        self.after(1000, self.ciclo_graficos)

    def parar_aquisicao(self, mensagem):
        self.rodando = False
        self.parar.set()
        if self.porta is not None:
            try:
                self.porta.close()
            except Exception:
                pass
            self.porta = None
        if self.thread is not None:
            self.thread.join(timeout=2)
            self.thread = None
        if self.arquivo is not None:
            self.arquivo.close()
            self.arquivo = None
            self.escritor = None
            self.meta.update(fim=datetime.now().isoformat(timespec="seconds"),
                             leituras=self.leituras, avisos_do_arduino=self.avisos,
                             duracao_s=round(self.t[-1], 1) if self.t else 0)
            self.salvar_meta()
            mensagem += f" {self.leituras} leituras salvas em {self.caminho_csv.name}."
        self.caminho_csv = None

        self.botao.configure(text="▶  Iniciar")
        for campo in self.campos:
            campo.state(["!disabled"])
        self.combo_porta.state(["readonly"])
        self.redesenhar()
        self.status.set(mensagem)

    # ------------------------------------------------------------------------
    # Arquivos
    # ------------------------------------------------------------------------
    def abrir_arquivo(self, nome_porta):
        PASTA_DADOS.mkdir(exist_ok=True)
        carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        base = f"{nome_seguro(self.nome_var.get())}_{carimbo}"
        self.caminho_csv = PASTA_DADOS / f"{base}.csv"
        self.caminho_meta = PASTA_DADOS / f"{base}.json"
        self.arquivo = open(self.caminho_csv, "w", newline="", encoding="utf-8")
        self.escritor = csv.writer(self.arquivo)
        self.escritor.writerow(["t_s", "Tq_C", "Tf_C", "V_V"])
        self.arquivo.flush()
        self.meta = {
            "ensaio": self.nome_var.get().strip(),
            "inicio": datetime.now().isoformat(timespec="seconds"),
            "porta": nome_porta,
            "massa_agua_quente_kg": self.massa,
            "resistor_carga_ohm": self.R,
            "carga_ligada": self.carga,
            "T_frio_C": T_FRIO_C,
            "observacao": "t_s = segundos desde o início da gravação",
        }
        self.salvar_meta()

    def salvar_meta(self):
        if self.caminho_meta is None:
            return
        with open(self.caminho_meta, "w", encoding="utf-8") as f:
            json.dump(self.meta, f, ensure_ascii=False, indent=2)

    def abrir_pasta(self):
        PASTA_DADOS.mkdir(exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(PASTA_DADOS)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(PASTA_DADOS)])
        else:
            subprocess.Popen(["xdg-open", str(PASTA_DADOS)])

    # ------------------------------------------------------------------------
    # Dados
    # ------------------------------------------------------------------------
    def limpar_dados(self):
        self.t, self.tq, self.v = [], [], []
        self.ultimo_bruto = None
        self.leituras = 0
        self.avisos = 0

    def processar_fila(self):
        try:
            while True:
                tipo, conteudo = self.fila.get_nowait()
                if tipo == "linha":
                    self.tratar_linha(conteudo)
                elif self.rodando:
                    self.parar_aquisicao("A conexão com o Arduino caiu.")
                    messagebox.showerror("Conexão perdida",
                                         f"{conteudo}\n\nConfira o cabo USB e inicie de novo.")
                    return
        except queue.Empty:
            pass
        if self.rodando:
            self.after(200, self.processar_fila)

    def tratar_linha(self, conteudo):
        if conteudo.startswith("#"):
            self.avisos += 1
            self.status.set(f"Aviso do Arduino: {conteudo.lstrip('# ')}")
            self.atualizar_contador()
            return
        partes = conteudo.split(",")
        if len(partes) != 4:
            return
        try:
            t_bruto, tq, tf, v = (float(p) for p in partes)
        except ValueError:
            return  # cabeçalho ou linha cortada

        # Tempo contínuo desde o início da gravação (sobrevive a um reinício do Arduino)
        if self.ultimo_bruto is None:
            t = 0.0
        elif t_bruto >= self.ultimo_bruto:
            t = self.t[-1] + (t_bruto - self.ultimo_bruto)
        else:
            t = self.t[-1] + 1.0
        self.ultimo_bruto = t_bruto

        if self.escritor is not None:
            self.escritor.writerow([f"{t:.3f}", f"{tq:.4f}", f"{tf:.4f}", f"{v:.4f}"])
            self.arquivo.flush()

        self.t.append(t)
        self.tq.append(tq)
        self.v.append(v)
        self.leituras += 1
        self.atualizar_leituras(tq, v)
        self.atualizar_contador()

    def estimar_calor(self):
        """Calor saindo da água quente (W) pela inclinação dos últimos segundos."""
        if len(self.t) < 10:
            return None
        t = np.array(self.t)
        sel = t >= t[-1] - JANELA_TAXA_S
        if sel.sum() < 10 or t[sel][-1] - t[sel][0] < 10:
            return None
        inclinacao = np.polyfit(t[sel], np.array(self.tq)[sel], 1)[0]   # °C por segundo
        return self.massa * C_AGUA * (-inclinacao)

    def atualizar_leituras(self, tq, v):
        minutos, segundos = divmod(int(self.t[-1]), 60)
        self.vars["tempo"].set(f"{minutos:02d}:{segundos:02d}")
        self.vars["Tq"].set(f"{tq:.2f} °C")
        self.vars["V"].set(f"{v:.4f} V")

        eta_c = 1 - (T_FRIO_C + 273.15) / (tq + 273.15)
        self.vars["etaC"].set(f"{100 * eta_c:.1f} %")

        potencia = v * v / self.R if self.carga else 0.0
        self.vars["P"].set(f"{1000 * potencia:.1f} mW" if self.carga else "0 (sem carga)")

        calor = self.estimar_calor()
        if calor is None:
            self.vars["Q"].set("…")
            self.vars["eta"].set("—")
            return
        self.vars["Q"].set(f"{calor:.1f} W")
        if self.carga and calor > 0.5:
            self.vars["eta"].set(f"{100 * potencia / calor:.2f} %")
        else:
            self.vars["eta"].set("—")

    def atualizar_contador(self):
        self.contador.set(f"Leituras: {self.leituras}   ·   Avisos do Arduino: {self.avisos}")

    # ------------------------------------------------------------------------
    # Gráficos
    # ------------------------------------------------------------------------
    def ciclo_graficos(self):
        if self.rodando:
            self.redesenhar()
            self.after(1000, self.ciclo_graficos)

    def redesenhar(self):
        if self.t:
            self.linha_tq.set_data(self.t, self.tq)
            self.linha_v.set_data(self.t, self.v)
            for ax in (self.ax_t, self.ax_v):
                ax.relim()
                ax.autoscale_view()
        self.canvas.draw_idle()

    # ------------------------------------------------------------------------
    def fechar(self):
        if self.rodando:
            self.parar_aquisicao("Encerrando.")
        self.destroy()


if __name__ == "__main__":
    Painel().mainloop()
