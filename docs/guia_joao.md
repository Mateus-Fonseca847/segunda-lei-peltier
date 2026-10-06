# Como completar o repositório

## 1. Ensaios e dados

Faça os três ensaios (0, 1 e 2) na mesma bancada, com as mesmas caixas, a mesma massa de água e as mesmas condições, seguindo o [guia de montagem](montagem.md). Antes de começar, anote a temperatura ambiente.

O painel salva cada ensaio em `dados/` (um `.csv` e um `.json`). Não edite esses arquivos. Tentativas que deram errado podem ir para `dados/descartados/`.

## 2. Análise

Dentro da pasta `python/`, rode com a temperatura ambiente anotada:

```bash
python analise.py --tamb 24.5
```

Opção útil: `--massa-recipiente 0.06` inclui a capacidade térmica da caixa quente (massa da caixa vazia, em kg); use também `--c-recipiente 460` para aço ou `900` para alumínio.

A análise gera as quatro figuras em `figuras/` e a tabela `resultados.md` na raiz. As figuras já aparecem no README automaticamente.

## 3. README

1. **Resultados:** copie a tabela de `resultados.md` para a seção "Resultados", no lugar de _(a preencher)_.
2. **Discussão:** escreva um parágrafo para cada tópico listado nos comentários da seção "Discussão", usando os números da tabela.
3. **Limitações:** revise os itens com as condições da sua montagem (isolamento, tampa, contato do módulo com as paredes). Se a análise mostrar avisos, mencione-os aqui.
4. **Autores:** acrescente seu nome e o link do seu LinkedIn.

## 4. Fotos

Salve as fotos em `docs/fotos/` com os nomes sugeridos em `docs/fotos/README.md`. A primeira, `montagem.jpg`, já aparece no topo do README. Capturas de tela do painel ao final de cada ensaio também são ótimas ilustrações. Para incluir outra foto:

```markdown
![Descrição da foto](docs/fotos/nome_da_foto.jpg)
```

