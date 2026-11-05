# Controladoria — automação de prazos entre sistema jurídico e Trello

Lê os prazos lançados na plataforma processual de um escritório de advocacia
e cria os cartões correspondentes no Trello — eliminando a redigitação
manual entre os dois sistemas, sem nunca decidir nada que seja critério
humano.

*(Read this in [English](README.en.md).)*

## Por que isso existe

Prazo perdido é direito perdido. A Controladoria Jurídica de um escritório
de advocacia lançava cada atividade na plataforma processual e redigitava o
mesmo lançamento no Trello à mão — com 2 a 3 horas de defasagem entre uma
coisa e outra, todo dia. Esse projeto fecha essa defasagem automatizando só
a redigitação, nunca a decisão.

## Duas tentativas anteriores falharam — e o motivo importa

Antes deste projeto, duas automações para o mesmo problema foram abandonadas.
As duas falharam pelo mesmo motivo: entregavam algo para a Controladoria
**corrigir**, não para aprovar ou completar — um pré-cartão com prazo
estimado errado, uma planilha de conferência que virava trabalho extra. Cada
correção forçada é um motivo a mais para não confiar na próxima automação.

## O que torna esta diferente

**A automação executa depois da decisão humana, nunca antes.** Quando falta
informação, o cartão nasce dizendo o que falta — nunca preenchido com
suposição. Um lançamento sem prazo fatal na origem produz um cartão sem
vencimento, com aviso explícito. Um texto sem decisão a resumir produz um
aviso de uma linha, não um resumo forçado. O prazo fatal em si nunca é
calculado pelo sistema — vem pronto de quem o lançou; o código só copia e,
no máximo, calcula a folga de dias antes do fatal. Ver `CLAUDE.md` para o
conjunto completo de regras que isso implica.

## O que o sistema faz

```
1. lê os lançamentos de prazo da plataforma processual
2. agrupa os que são o mesmo ato processual (ED + recurso do mesmo
   movimento viram um cartão; nada mais é agrupado por parecença)
3. localiza a publicação de origem e decide se há teor para resumir
4. resume o teor com um modelo de linguagem — nunca inventa, nunca
   completa data cortada, nunca afirma como o prazo foi contado
5. cria o cartão no Trello, com prazo, etiqueta e resumo
6. confere o próprio trabalho e avisa só por exceção
```

Tudo isso é regra fixa em código, travada por 291 testes. O único ponto com
IA é o resumo de 1 a 3 frases do teor da decisão — ver
`docs/PROMPT_RESUMO.md` para o prompt completo e o porquê de cada regra
dele.

## Medido, não afirmado

Números do projeto original, medidos contra o trabalho humano real — não
estimados, não especificados de antemão:

| | |
|---|---|
| Regras de negócio travadas em teste | 291 |
| Título do cartão idêntico ao que a Controladoria escrevia | 100% |
| Cartões com erro, em 6 invariantes verificadas sobre 150 cartões | 0 |
| Um dia inteiro de lançamentos processado em | 94 segundos |
| Redução no tempo da tarefa | 70% |
| Detecção de bugs por teste de mutação | 93% (14 de 15 introduzidos de propósito) |
| Testes que só verificavam texto no código-fonte, antes da correção | 34% (78 de 231) |
| Cartões que nasciam marcados como concluídos por engano, antes da correção | 51% (122 de 240) |

A íntegra das decisões que geraram esses números — o que parecia certo antes
de medir, o que a medição mostrou, como foi corrigido — está em
`docs/DECISOES_MEDIDAS.md`.

## O que ela não faz

- Não decide quantos prazos uma decisão gera, nem quem executa ou revisa.
- Não calcula prazo fatal — ele vem pronto de quem lançou; o código só copia
  e aplica a folga de dias de preparo.
- Não afirma como um prazo foi contado, nem cita artigo de lei sobre
  contagem, a menos que o próprio texto da decisão já traga essa citação.
- Não completa dado incompleto — data cortada é omitida, nunca adivinhada.
- Não acessa sistema de tribunal por nenhum meio.
- Não altera, move, arquiva nem exclui cartão nenhum — só cria.

## Como rodar em 3 comandos

Sem nenhuma credencial real — plataforma processual, Trello e modelo de
linguagem são todos substituídos por versões fictícias:

```bash
pip3 install certifi            # única dependência, opcional
python3 teste_regras.py         # 291 regras, não acessa rede
python3 demo.py --reiniciar     # roda o fluxo completo com dados inventados
```

O modo demonstração cobre os cinco casos difíceis que o sistema real
resolve — intimação duplicada vinda de duas fontes, dois lançamentos do
mesmo movimento com prazos diferentes, lançamento sem prazo fatal, número de
OAB confundido com número de processo, e dado pessoal dentro do texto — e
confere sozinho, ao final, que cada um foi tratado certo. Os cartões ficam
salvos em `trabalho/demo_trello.json`; rodar `python3 demo.py` de novo (sem
`--reiniciar`) mostra a trava de duplicata em ação.

## Para rodar com dados reais

```bash
cp .config-plataforma.exemplo.json .config-plataforma.json   # preencher
cp .config-trello.exemplo.json   .config-trello.json         # preencher
cp .config-anthropic.exemplo.json .config-anthropic.json     # opcional

python3 teste_ambiente.py       # confere credenciais e ids do Trello
python3 rotina.py lancamentos DD/MM/AAAA           # simula, não cria nada
python3 rotina.py lancamentos DD/MM/AAAA --criar   # cria de verdade
```

Sem chave de IA configurada em `.config-anthropic.json` nem o Claude Code
instalado, os cartões saem sem resumo — nunca com um resumo inventado.

## Verificação de qualidade

```bash
python3 qa_mutacao.py          # 14/15 bugs introduzidos de propósito, detectados
python3 qa_comportamento.py    # seções 1-5 são offline; 6-7 leem o Trello real
python3 qa_reconciliacao.py    # compara origem x destino pelo conjunto inteiro
```

Os três só aceitam prova por execução — nenhum lê código-fonte à procura de
texto. `pipeline.py` roda `teste_regras.py` e `teste_ambiente.py` antes de
qualquer criação em lote; se um dos dois falhar, nada é criado.

## Estrutura

| | |
|---|---|
| `rotina.py` | o programa do dia — modos `manha`, `lancamentos`, `noite`, `vigia` |
| `cartao.py` | as regras aplicadas na criação de um cartão |
| `pipeline.py` | pré-voo obrigatório, validação de lote e pós-verificação |
| `consolida.py` | o que vira um cartão só |
| `prazo_util.py` | dias úteis, feriados, suspensão do art. 220 do CPC |
| `sanitiza.py` | remove CPF, RG, CTPS e dados bancários — nunca remove CNJ ou OAB |
| `modelo.py` | chama o modelo de linguagem (API ou agente de codificação) |
| `cliente_plataforma_fake.py`, `cliente_trello_fake.py`, `gerador_dados_ficticios.py` | modo demonstração |
| `qa_*.py` | as três ferramentas de QA que executam, não leem código |
| `docs/` | decisões medidas e o prompt do resumo, explicados |
| `CLAUDE.md` | governança dos agentes de IA que construíram e operam o projeto |

## Licença

MIT — ver `LICENSE`.

---

Construído entre agosto e novembro de 2026 para a Controladoria Jurídica de
um escritório de advocacia, com Claude Code como agente de desenvolvimento.
Publicado depois que o escritório migrou para uma plataforma própria —
a tecnologia continua tendo valor para qualquer escritório que use uma
plataforma processual e o Trello no mesmo fluxo.
