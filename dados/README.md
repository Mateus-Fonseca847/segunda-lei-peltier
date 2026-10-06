# Dados brutos

Cada ensaio gravado pelo `python/painel.py` gera dois arquivos com o mesmo nome:

- `ensaioN_AAAA-MM-DD_HHMMSS.csv` — uma linha por leitura (cerca de 1,5 por segundo)
- `ensaioN_AAAA-MM-DD_HHMMSS.json` — anotações do ensaio

| Coluna do CSV | Significado | Unidade |
| --- | --- | --- |
| `t_s` | Tempo desde o início da gravação | s |
| `Tq_C` | Temperatura da água quente (DS18B20) | °C |
| `Tf_C` | Temperatura do lado frio (fixa: banho de gelo) | °C |
| `V_V` | Tensão do Peltier medida no pino A0 | V |

O `.json` guarda a massa de água quente, o resistor de carga, se a carga estava marcada no painel, a porta, os horários de início e fim e quantas leituras e avisos houve.

**Não edite estes arquivos à mão.** Eles são o registro original do experimento; correções (por exemplo, um campo marcado errado no painel) são feitas na análise ou anotadas no README. Se um ensaio deu errado, mantenha o arquivo e registre o motivo, ou mova-o para uma subpasta `descartados/`.
