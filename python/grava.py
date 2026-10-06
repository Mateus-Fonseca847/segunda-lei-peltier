"""
Gravador simples pelo terminal (plano B do painel.py).
Uso: python grava.py nome_do_arquivo.csv   — Ctrl+C para parar.
"""
import csv
import sys

import serial

PORTA = "COM3"   # troque pela porta do seu Arduino (Arduino IDE → Ferramentas → Porta)
ARQUIVO = sys.argv[1] if len(sys.argv) > 1 else "dados.csv"

porta = serial.Serial(PORTA, 115200, timeout=2)
print(f"Gravando em {ARQUIVO}. Aperte Ctrl+C para parar.")

with open(ARQUIVO, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t_s", "Tq_C", "Tf_C", "V_V"])
    try:
        while True:
            linha = porta.readline().decode(errors="ignore").strip()
            try:
                t, Tq, Tf, V = map(float, linha.split(","))
            except ValueError:
                if linha:
                    print("  (ignorada)", linha)   # cabeçalho, erros ou linha cortada
                continue
            w.writerow([t, Tq, Tf, V])
            f.flush()
            print(f"t = {t:7.1f} s   Tq = {Tq:6.2f} °C   V = {V:.4f} V")
    except KeyboardInterrupt:
        print("Gravação encerrada.")

porta.close()
