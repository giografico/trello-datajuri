# O prompt do resumo — e por que cada regra existe

O único ponto do projeto com IA: ler o teor de uma decisão judicial e
escrever um resumo de 1 a 3 frases para o topo do cartão. Tudo o resto —
prazo, agrupamento, duplicata, roteamento — é regra fixa em código, travada
pelos 291 testes. Esta é a peça que não dava para travar com `if`: pedir para
um modelo de linguagem ler texto jurídico variado e devolver o que importa.

O prompt não nasceu pronto. Foi ajustado depois de rodar contra casos reais
e medir o que saía errado — a mesma disciplina do resto do projeto, aplicada
ao prompt.

## O prompt principal

```
Você resume decisões judiciais para a Controladoria Jurídica de
um escritório de advocacia. O resumo vai no topo de um cartão de gestão de
prazos, e quem lê precisa entender em dez segundos o que aconteceu e o que
precisa ser feito.

REGRAS:
- 1 a 3 frases. Direto. Sem preâmbulo, sem "trata-se de".
- Comece pelo ato: o que o juízo decidiu ou determinou.
- Diga o prazo e a providência SE estiverem no texto.
- Use **negrito** no ato principal.
- Datas SEMPRE completas: 25/11/2026, nunca 25/11 nem 25/1.
- Se uma data aparecer INCOMPLETA ou cortada no texto, NÃO a complete e NÃO
  a adivinhe: omita a data e diga o resto. Data errada em cartão de prazo é
  pior que data nenhuma.
- NUNCA diga como o prazo foi contado, nem cite marco inicial ou os artigos
  de contagem (CPC 219, 224, 231). O prazo já vem calculado pela
  Controladoria. Citar o artigo que fundamenta o ato (ex: audiência do
  art. 334) é permitido SE estiver no texto.
- NÃO repita CPF, RG ou dados bancários.
- Se o texto trouxer QUALQUER informação aproveitável — que ato foi
  praticado, data de audiência, do que se trata — resuma essa informação e
  NÃO use ⚠️. Resumo curto é melhor que aviso.
- Use ⚠️ APENAS quando não houver absolutamente nada a resumir: o texto diz
  que existe algo no sistema, sem dizer o quê. Uma linha só.
- Responda APENAS com o resumo. Nada antes, nada depois.
```

## Por que cada regra existe

O prompt foi reajustado depois do primeiro teste com o código rodando
sozinho (12 cartões), quando três defeitos apareceram juntos:

**1. Metade dos cartões nascia com ⚠️ no topo — e vários avisavam E resumiam
ao mesmo tempo.** O modelo escrevia algo como "⚠️ o texto não traz a decisão"
seguido de "audiência designada para...". O aviso virava ruído, e ruído
repetido ensina a ignorar o aviso — inclusive o verdadeiro, no dia em que
importa. Resolvido invertendo a prioridade: resumir sempre que houver
qualquer informação aproveitável; o ⚠️ fica reservado para quando não há
literalmente nada.

**2. Uma data saiu truncada.** O título mandado ao modelo tinha sido cortado
em 90 caracteres antes de chegar ao prompt, e o corte caiu no meio de uma
data: "designada para dia 25/1". O prazo fatal verdadeiro era 25/11/2026. O
modelo, obedecendo à regra (já existente) de "datas sempre completas",
*completou* a data errada — "25/01/2027" — em vez de reconhecer que estava
cortada. Num cartão de prazo, data errada é pior que nenhuma data. A correção
teve duas partes: parar de truncar o título antes de mandar (o limite real do
campo é 200 caracteres; mandar inteiro é barato), e adicionar a regra
explícita de **não completar data incompleta — omitir**.

**3. A proibição de citar o CPC era ampla demais.** A regra existe para
impedir o cartão de *afirmar como o prazo foi contado* — essa conta é da
Controladoria, não do sistema, e o cartão não pode descrever uma contagem que
não foi feita ali. Mas a primeira versão da regra bloqueava qualquer menção a
artigo do CPC, inclusive quando o artigo fundamenta o próprio ato (por
exemplo, uma audiência designada com base no art. 334). Isso é informação
legítima do texto, não uma afirmação sobre contagem de prazo. A regra foi
reescrita para distinguir as duas coisas.

## O prompt de audiência — por que é diferente

```
Você prepara o cartão de uma AUDIÊNCIA para a Controladoria Jurídica de
um escritório de advocacia.

O título do cartão JÁ INFORMA o tipo de audiência, a data e a hora. NÃO repita
nada disso.

Sua tarefa é extrair do texto SOMENTE o que afeta a preparação do ato:
- provas que precisam ser levadas, e até quando
- testemunhas: quantas, se precisam de intimação, como participam
- necessidade de preposto ou carta de preposição
- prazo de contestação ou outra peça vinculado à audiência
- presença obrigatória da parte, consequência da ausência

REGRAS:
- 1 a 3 frases, direto.
- Se o texto NÃO trouxer nenhuma dessas informações, responda exatamente:
  SEM EXIGENCIAS
- Não repita o tipo, a data ou a hora da audiência.
- Datas SEMPRE completas (25/11/2026). Se vier incompleta, omita.
- NÃO repita CPF, RG ou dados bancários.
- Responda APENAS com o texto. Nada antes, nada depois.
```

Audiência não tem decisão a resumir — não há o que "aconteceu", só o que
precisa estar pronto até a data. Medido em 90 cartões de audiência: 98%
trazem só sistema e número do processo, e apenas 6% trazem alguma exigência
real do ato (prova, testemunha, preposto). Usar o prompt genérico aqui
produzia resumo redundante com o título — foi exatamente o caminho que gerou
a data errada do item 2. Por isso o prompt de audiência existe separado, com
uma saída explícita para "nada a dizer" (`SEM EXIGENCIAS`) em vez de forçar
um resumo onde não há nada para resumir.

## Regra dura: o modelo nunca inventa

Se o modelo falhar — API fora do ar, resposta vazia, texto curto demais para
ter decisão dentro — a função devolve `None`, e quem chamou decide. A
Controladoria prefere um cartão sem resumo a um cartão com resumo errado.
Não existe caminho de código que preencha esse vazio com um palpite.

## Dois caminhos para o mesmo resumo

O projeto aceita dois jeitos de gerar o resumo, nessa ordem de preferência:

| | custo | o que instala no servidor |
|---|---|---|
| API da Anthropic (se houver chave configurada) | cobrança por token | nada — é uma requisição HTTP |
| CLI de um agente de codificação, em modo não-interativo | zero (se já pago por outro uso) | um agente com acesso a arquivos e shell |

Quando o resumo virou algo que precisa rodar sozinho, num servidor, sem
ninguém por perto, a pergunta deixou de ser só "funciona?" e passou a ser
"o que esse processo tem permissão de fazer?". Um agente de codificação é,
por padrão, mais ferramenta do que uma tarefa de "entra texto, sai resumo"
precisa — ele pode ler e escrever arquivos, rodar comandos. Uma chamada
direta à API não instala nada e não tem acesso a nada além do texto que você
manda. Por isso, quando há chave de API configurada, o projeto usa ela; sem
chave, cai para o agente de codificação — e dá para trocar sem mexer em
código algum.
