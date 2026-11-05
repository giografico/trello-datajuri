# Decisões medidas

Versão curta do registro de decisões do projeto original — reescrita para o
repositório público, sem nenhum dado do escritório. Os números são os mesmos
medidos no projeto real; os nomes de pessoas viraram papéis.

Formato: o que eu achava antes de medir → o que a medição mostrou → como foi
resolvido. Nenhuma dessas regras foi especificada de antemão — todas vieram
de comparar o que o código produzia com o que uma pessoa fazia manualmente.

---

## 1. Duplicata não é parecença de texto — é processo + movimento, exato

**Achava**: títulos parecidos (ou o mesmo processo, em geral) seriam
suficiente pra detectar duas entradas da mesma intimação.

**Acontecia**: múltiplos clientes no mesmo processo geram várias entradas
para o *mesmo* movimento — isso é a mesma intimação e precisa agrupar. Mas
dois movimentos diferentes do mesmo processo (uma decisão em março, outra em
julho) são intimações **distintas**, mesmo com título parecido.

**Resolvido**: duplicata é match exato de (processo, movimento). Fora disso,
nunca agrupar por parecença — cada movimento é seu próprio cartão, a não ser
que caia na próxima regra.

## 2. Montar o cartão do zero perde o que é permanente do processo

**Achava**: criar o cartão novo com os dados do lançamento resolveria.

**Acontecia**: o link da pasta no Drive, os contatos do cliente e a origem
do sistema não existem no lançamento — eles viajam de cartão em cartão desde
o primeiro do processo. Montar do zero perdia tudo isso, toda vez.

**Resolvido**: duplicar o último cartão **humano** do processo (nunca um
cartão que a própria automação criou, para não propagar defeito), e
reescrever só o conteúdo da nova intimação. O que é permanente do caso vem
junto automaticamente.

## 3. Cartão nunca pode nascer marcado como concluído

**Achava**: duplicar um cartão e sobrescrever o conteúdo bastava.

**Acontecia**: a plataforma copia o status "concluído" do cartão-fonte, e a
fonte costuma já estar marcada como feita — então o cartão **novo** nascia
igual. Medido: **51% dos cartões duplicados (122 de 240)** nasciam
concluídos. Ninguém trabalha um cartão que já parece pronto.

**Resolvido**: forçar "não concluído" explicitamente em toda criação, e
conferir de novo depois — duas camadas, porque a primeira sozinha já tinha
falhado silenciosamente uma vez.

## 4. As duas fontes de recorte dizem coisas diferentes com o mesmo campo

**Achava**: processar uma fonte de intimações bastava; a segunda seria só
checagem cruzada eventual.

**Acontecia**: a segunda fonte entrega a MESMA intimação que a primeira já
tinha trazido, só que um dia depois — perder isso é perder prazo real, não
só duplicar trabalho. E pior: as duas fontes usam o mesmo nome de campo
(`data`) para coisas diferentes — numa, é a data real; na outra, vem um dia
útil adiantada, com a data real escrita só dentro do texto.

**Resolvido**: processar as duas fontes sempre, agrupando pela mesma regra
de duplicata (processo + movimento, sem distinção de fonte), e normalizar a
data da segunda fonte lendo o texto antes de qualquer cálculo de prazo.

## 5. O prefixo de roteamento cegou a lógica que vinha antes dele

**Achava**: acrescentar uma sigla de roteamento no começo do título do
lançamento não afetaria nada que já funcionava.

**Acontecia**: a lógica que decidia "isso é um prazo?" lia a sigla no
**início** do título — e com o prefixo novo na frente, parou de reconhecer.
O efeito era silencioso: lançamentos continuavam virando cartão, só que sem
agrupamento, sem o campo de prazo fatal preenchido, e com vencimento errado.
Nada quebrava visivelmente; só saía errado.

**Resolvido**: toda leitura de sigla operacional passa primeiro por uma
função que remove o prefixo de roteamento — centralizada, pra não repetir o
mesmo erro em cada lugar que lê o título.

## 6. QA que lê código em vez de executar não prova nada

**Achava**: uma suíte de testes que cresce é uma suíte que protege mais.

**Acontecia**: medindo a suíte depois de uma rodada de revisão, **34% dos
testes (78 de 231)** só verificavam se um texto existia no código-fonte —
passariam com a lógica completamente quebrada. Isso não aparece lendo a
suíte; só aparece medindo.

**Resolvido**: dois QAs novos, que só aceitam prova por execução — chamar a
função de verdade, ou ler o estado real da plataforma de destino — e teste
por mutação, que introduz bugs de propósito e mede quantos a suíte pega.
Primeira rodada: 93% de detecção. O que sobrou virou teste novo.

## 7. O cache que resolveu um problema abriu outro

**Achava**: cachear a lista de cartões por alguns segundos reduziria carga
sem risco nenhum, já que a janela era curta.

**Acontecia**: dois cartões idênticos nasceram com menos de um minuto de
diferença, dentro da janela do cache — o segundo cartão consultou uma lista
anterior à existência do primeiro, e não o viu.

**Resolvido**: toda criação alimenta o cache imediatamente, no mesmo
instante em que o cartão nasce — não espera a próxima consulta.

## 8. A audiência não é uma decisão para resumir

**Achava**: o mesmo resumo de decisão serviria para cartão de audiência.

**Acontecia**: medido em 90 cartões de audiência: 98% trazem só sistema e
número do processo; **apenas 6%** trazem alguma exigência real do ato
(prova, testemunha, preposto). O título já diz tipo, data e hora — resumir
isso de novo é ruído, e foi exatamente esse ruído que gerou uma data errada
num cartão (ver `docs/PROMPT_RESUMO.md`).

**Resolvido**: audiência tem rotina própria, que extrai só o que falta
preparar — e responde explicitamente "sem exigências" quando não há nada,
em vez de forçar um resumo onde não existe decisão nenhuma.

## 9. "Sem vencimento" nem sempre é defeito do código

**Achava**: todo cartão sem data de vencimento é um bug a corrigir.

**Acontecia**: alguns lançamentos chegam sem prazo fatal na própria origem
— não há o que calcular, porque a informação não existe. Tratar isso igual
a um bug real inflava a lista de problemas e fazia ela perder valor: a causa
"o código errou" e a causa "a origem não trouxe o dado" exigem reação
diferente, e misturar as duas é o mesmo erro de alarme em excesso de novo.

**Resolvido**: distinguir as duas causas explicitamente — o cartão sem
vencimento só é listado como defeito quando a origem **tinha** o prazo e o
código não usou.

## 10. O primeiro dia rodando sozinho encontrou o que nenhum teste tinha coberto

**Achava**: com os testes de regra e os QAs passando, o sistema estava
pronto para rodar sem ninguém olhando.

**Acontecia**: o primeiro dia inteiro sem supervisão direta encontrou dois
problemas que nenhum teste isolado cobria — um timeout de rede sem nova
tentativa, que derrubou o processo inteiro faltando pouco para o fim do
expediente, e um tipo de lançamento sem etiqueta mapeada, que fazia o
cartão desaparecer dos filtros que a equipe usa no dia a dia.

**Resolvido**: toda chamada de rede ganhou nova tentativa com espera
crescente, e sigla sem etiqueta mapeada passou a gerar aviso explícito em
vez de cartão mudo. Nenhum dos dois era "código errado" isoladamente — eram
falhas que só existem na composição das peças, rodando juntas, por um dia
inteiro. Por isso o modo demonstração deste repositório roda o fluxo
completo de ponta a ponta, não só funções isoladas.
