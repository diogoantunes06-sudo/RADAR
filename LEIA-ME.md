# Radar

Site de consulta das suas ações e fundos, com cotações atualizadas sozinhas.

- **Site** (`index.html`): resumo do dia (variação média, quantos em alta e em baixa, Selic), três quadros de destaque e os ativos separados em Ações, Fundos imobiliários e Fiagros. Dentro de cada um, os ativos ficam agrupados por setor (ações) ou tipo de fundo, cada grupo com a variação e o DY médios e um botão para recolher. Dá para ver em **Cartões** (com a régua de 52 semanas) ou em **Lista** (tabela compacta). Clique num ativo para abrir os detalhes. Abre no PC e no celular.
- **Robô** (`bot.py` + `.github/workflows/atualizar.yml`): roda nos servidores do GitHub a cada 30 minutos durante o pregão (9h às 18h30, dias úteis) e mais uma vez às 20h17 com os preços de fechamento. Busca cotações e proventos no Yahoo Finance e a Selic no Banco Central, recalcula tudo e grava `dados.json`.

## Arquivos que você edita

| Arquivo | Para quê |
|---|---|
| `ativos.json` | A lista do que acompanhar. |
| `analise.json` | Preço-alvo, LPA, VPA e setor (ações); segmento e valor patrimonial (fundos). O setor e o segmento definem o grupo em que o ativo aparece no site. Muda pouco: atualize quando sair notícia ou peça ao Claude. |
| `config.json` | Premissas: rendimento mínimo de Bazin (6%), diferença CDI x Selic, IR. |

Para **incluir uma ação**, edite `ativos.json` no site do GitHub (ícone do lápis) e acrescente, antes do último `]`:

```json
,
  {
    "ticker": "WEGE3",
    "nome": "WEG",
    "tipo": "acao"
  }
```

`tipo` é `acao`, `fii` ou `fiagro`. Ao salvar, o robô roda sozinho em um ou dois minutos. Sem dados em `analise.json`, o ativo aparece no grupo "Outras ações" (ou "Outros fundos") com "sem alvo"; o resto (cotação, DY, preço-teto) funciona normalmente. Para colocá-lo num grupo, acrescente em `analise.json` algo como `"WEGE3": {"setor": "Indústria"}` ou, para fundo, `"XXXX11": {"segmento": "Tijolo: galpões"}`.

Para tirar um ativo, apague o bloco dele (e a vírgula que sobrar).

## Instalação (uns 15 minutos, tudo pelo site do GitHub)

1. **Novo repositório**: github.com > **New**. Nome: `radar`. Marque **Public** (o site grátis do GitHub Pages exige). Clique em **Create repository**.
2. **Enviar arquivos**: clique em **uploading an existing file** e arraste `index.html`, `bot.py`, `ativos.json`, `analise.json`, `config.json` e `LEIA-ME.md`. **Commit changes**.
3. **Arquivo do robô**: **Add file > Create new file**. No nome, digite `.github/workflows/atualizar.yml`. Cole o conteúdo do arquivo `atualizar.yml` do pacote. **Commit changes**.
4. **Ligar o site**: **Settings > Pages**. Em **Branch**, escolha `main` e `/ (root)`, **Save**. Em um ou dois minutos aparece o endereço, algo como `https://SEU-USUARIO.github.io/radar/`.
5. **Primeira execução**: aba **Actions**. Se pedir, clique em **I understand my workflows, go ahead and enable them**. Depois **Atualizar cotacoes > Run workflow**. Em menos de um minuto o `dados.json` aparece e o site se preenche.

Se o passo "Salvar dados.json" der erro: **Settings > Actions > General > Workflow permissions**, marque **Read and write permissions** e salve.

## Reserva para as cotações (opcional)

O Yahoo às vezes bloqueia os servidores do GitHub por alguns minutos. Se isso acontecer com frequência, crie uma conta grátis em brapi.dev, copie o token e cadastre em **Settings > Secrets and variables > Actions > New repository secret** com o nome `BRAPI_TOKEN`. O robô passa a usar a brapi quando o Yahoo falhar. Se as duas falharem, o site mantém o último preço e marca "cotação antiga".

## Bom saber

- O repositório é público: qualquer pessoa com o endereço vê a lista de ativos, mas não há quantidades nem valores seus.
- Os horários do GitHub atrasam de 5 a 20 minutos em dias cheios. Serve para acompanhar, não para operar no minuto.
- Os proventos vêm do Yahoo e incluem JCP pelo valor bruto. O DY pode diferir um pouco do Status Invest.
- Preço-teto das ações: proventos de 12 meses / 6% (Bazin). Dos fundos: rendimentos de 12 meses / CDI líquido de IR.
- Nada aqui é recomendação de compra ou venda.
