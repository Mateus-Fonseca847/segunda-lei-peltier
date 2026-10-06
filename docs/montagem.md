# Guia de montagem

## 1. Circuito

![Mapa da protoboard](protoboard.svg)

Na protoboard de 400 pontos, os trilhos de cima levam 5V e GND, a metade de cima recebe o sensor e a metade de baixo recebe o Peltier. Os cinco furos de uma coluna, dentro de cada metade, estão ligados entre si; os trilhos são ligados de ponta a ponta.

| De | Para |
| --- | --- |
| Pino 5V do Arduino | Trilho + de cima (linha vermelha) |
| Pino GND do Arduino | Trilho − de cima (linha azul) |
| Trilho − de cima | Trilho − de baixo (jumper pela lateral direita) |
| Sensor: fio vermelho | Trilho + de cima |
| Sensor: fio preto | Trilho − de cima |
| Sensor: fio azul (dados) | Coluna 12, metade de cima |
| Resistor 4,7 kΩ (pull-up) | Coluna 12 e trilho + de cima |
| Coluna 12 | Pino 2 do Arduino |
| Peltier: fio positivo | e20 |
| Peltier: fio negativo | Trilho − de baixo |
| Resistor de carga 2,2 Ω, 5 W | a20 e trilho − de baixo (só no Ensaio 2) |
| Resistor 4,7 kΩ (proteção) | c20 e c24 |
| a24 | Pino A0 do Arduino |

As pontas dos fios flexíveis (sensor e Peltier) devem ser estanhadas, com pouca solda, para entrar firmes nos furos. Prenda os cabos com fita na mesa, com folga até a protoboard, para que um puxão não chegue aos fios encaixados.

## 2. Testes da eletrônica 

1. **Alimentação:** com o USB conectado, o LED "ON" do Arduino deve ficar aceso. Se apagar, há curto entre 5V e GND.
2. **Sensor:** carregue `arduino/diagnostico`. O Monitor Serial (115200 baud) deve mostrar "Sensores encontrados: 1", "modo parasita: nao" e a temperatura ambiente.
3. **Fio de dados:** se o sensor não for encontrado, carregue `arduino/teste_pino`. Com o pull-up no lugar, o pino 2 deve ler 1. Lendo 0 com o fio azul fora da protoboard, o problema está no pull-up ou no jumper até o pino 2; lendo 0 só com o fio azul ligado, o sensor está prendendo a linha em zero.
4. **Polaridade do Peltier:** carregue `arduino/segunda_lei`, desconecte o resistor de carga e encoste a face com texto do módulo no gelo e a outra na água quente. A tensão no Monitor Serial deve subir. Se ficar em zero, inverta os fios do Peltier.

## 3. Montagem térmica

1. Escolha uma parede lisa de cada caixa para o Peltier, longe de dobradiças e rebites, e sem etiquetas (fita é isolante).
2. Passe uma camada fina de pasta térmica nas duas faces do módulo (um grão de arroz espalhado em cada face).
3. Encaixe o módulo entre as paredes, com a face com texto voltada para a caixa do gelo, o mais baixo possível, para ficar abaixo da linha da água.
4. Prenda as duas caixas com elásticos, um acima e outro abaixo da altura do módulo.
5. Confira olhando de lado que o módulo encosta nas duas paredes por inteiro, e não só pela borda de cima. Se as paredes forem inclinadas, calce as caixas para deixá-las paralelas.
6. Posicione a ponta do sensor no meio da água da caixa quente, a meia altura, sem encostar no metal. Só a ponta metálica fica na água, nunca a emenda com o cabo.

## 4. Ensaios

Use sempre a mesma massa de água quente, a mesma temperatura inicial e as mesmas condições de bancada (sem ventilador, mesma janela, mexer as duas caixas a cada minuto). No painel, clique em Iniciar antes de despejar a água quente.

| | Ensaio 0 | Ensaio 1 | Ensaio 2 |
| --- | --- | --- | --- |
| Caixa quente | Água quente | Água quente | Água quente |
| Caixa fria | A mesma água quente | Gelo picado com pouca água | Gelo picado com pouca água |
| Resistor de carga | Desconectado | Desconectado | Conectado |
| Nome no painel | `ensaio0` | `ensaio1` | `ensaio2` |
| Duração | 20 min | 10 min | 10 min |

Antes de começar, anote a temperatura ambiente (sensor no ar, painel com "Gravar em arquivo" desmarcado). Ela é usada na análise: `python analise.py --tamb <valor>`.