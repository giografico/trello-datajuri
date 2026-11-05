#!/usr/bin/env python3
"""
DE ONDE VEM O TEOR DA DECISÃO — regra oficial, em um lugar só.

Decidido com a controladoria em 24/09/2026:

    SOMENTE quando a intimação vier SEM teor, a equipe cola a decisão na
    OBSERVAÇÃO DO LANÇAMENTO no DataJuri. Quando a intimação já vem com
    teor, nada muda — o teor continua vindo do recorte.

Cobre o terço das intimações que só trazem a referência ao movimento.

POR QUE ISTO É UM MÓDULO, e não duas linhas dentro da rotina:

A regra existia desde 24/09 e estava implementada errada até 29/10:

    teor = recorte or observacao

O `or` só cai na observação se o recorte estiver VAZIO. Mas intimação sem
teor não vem vazia — vem com "Intimação referente ao movimento (seq. 47).
Acesse o sistema Projudi para mais detalhes". Como não é vazio, a observação
NUNCA era lida, e o trabalho de colar o teor era jogado fora. Dois casos num
único dia (27/10/2026).

CAMPO OBRIGATÓRIO na consulta: `observacao` precisa entrar na lista de
`campos` da chamada ao módulo Atividade. A API do DataJuri REJEITA campo
inválido com HTTP 400, mas campo NÃO PEDIDO simplesmente vem vazio, em
silêncio — a mesma armadilha do `criadoPor.nome` (rodape.py).
"""
from prepara_manha import tem_teor

CAMPOS_NECESSARIOS = ("observacao",)

# Abaixo disto, a observação não carrega uma decisão — é anotação curta,
# referência de protocolo, instrução interna.
MINIMO_OBSERVACAO = 300


def _extra_da_observacao(observacao, texto_recorte):
    """O que a observacao tem ALEM do que ja' vem do recorte.

    A Controladoria cola o teor da decisao no MESMO campo de observacao que
    ja' traz o texto padrao da intimacao ("Data de disponibilização... Jornal
    ... Intimação referente ao movimento (seq. 47). Acesse o sistema
    Projudi"). Confirmado com ela em 29/10/2026.

    Entao a observacao quase sempre passa de 300 caracteres, mesmo sem teor
    nenhum — medido em 27/10: 849 caracteres so' de texto padrao. Contar
    tamanho nao serve; e' preciso ver o que ha' de NOVO ali.

    Compara em blocos: o que do texto da observacao nao aparece no recorte.
    """
    import re as _re
    ob = _re.sub(r"\s+", " ", (observacao or "")).strip()
    tr = _re.sub(r"\s+", " ", (texto_recorte or "")).strip()
    if not ob:
        return ""
    if not tr:
        return ob
    # blocos de 60 caracteres do recorte, para comparar
    blocos = {tr[i:i + 60] for i in range(0, len(tr), 30)}
    sobra = []
    for i in range(0, len(ob), 60):
        pedaco = ob[i:i + 60]
        if not any(pedaco[:40] in b or b[:40] in pedaco for b in blocos):
            sobra.append(pedaco)
    return " ".join(sobra).strip()


def escolher(texto_recorte, observacao):
    """Devolve (texto, origem).

    origem: "recorte" · "observacao" · "nenhum"

    A decisão é pelo CONTEÚDO, nunca por o campo estar vazio.
    """
    tr = (texto_recorte or "").strip()
    ob = (observacao or "").strip()
    if tr and tem_teor(tr):
        return tr, "recorte"                 # a publicação traz a decisão
    # A observacao traz o texto padrao da intimacao. So' conta como teor
    # colado se houver conteudo ALEM dele.
    extra = _extra_da_observacao(ob, tr)
    if len(extra) >= MINIMO_OBSERVACAO:
        return ob, "observacao"              # a equipe colou o teor
    if tr or ob:
        return (tr or ob), "nenhum"          # só referência: melhor que nada
    return "", "nenhum"


def tem_decisao(texto_recorte, observacao):
    """Há decisão para resumir, de alguma das duas fontes?"""
    return escolher(texto_recorte, observacao)[1] != "nenhum"
