#!/usr/bin/env python3
"""
Regra de consolidacao de lancamentos em cartao.

Descoberto em 14/09/2026, ao ampliar o escopo para alem de PRZ: a chave
(processo, movimento) agrupava TUDO quando o movimento era None — juntando,
num cartao so, a audiencia, a preparacao, o substabelecimento e a
comunicacao ao cliente. Isso e' exatamente o que a secao 4.8 da SKILL
proibe: audiencia gera VARIOS cartoes, com responsaveis e prazos proprios.

Regra correta:

  PRZ com movimento  -> agrupa por processo + movimento.
                        Dois lancamentos do mesmo movimento (ED 5 dias e
                        recurso 15 dias) sao o mesmo trabalho de analise;
                        vale o prazo mais curto. Medido: a controladoria faz assim
                        em 4 de 4 casos.

  Todo o resto       -> um lancamento, um cartao. Nunca agrupar PROV, PAT
                        ou AUD: sao providencias distintas por natureza.

  Duplicata literal  -> unico caso em que o resto agrupa: titulo identico
                        E mesmo prazo fatal. Ai e' a mesma coisa lancada
                        duas vezes, nao duas providencias.
"""
import re, collections

from prefixo import sem_prefixo

RX_MOV = re.compile(r'\b(?:mov|ev|evento|movimento|fls|seq|Id)\.?\s*([\w/]{1,10})', re.I)


# Campos que `agrupa()` LE do lancamento. Pedir na consulta ao DataJuri, como
# em rodape.CAMPOS_NECESSARIOS e pelo mesmo motivo: campo nao pedido vem VAZIO,
# em silencio. Sem `processo.pasta` nenhum grupo se forma e cada lancamento vira
# um cartao — foi o que aconteceu no lote de 05-08/10/2026 (39 cartoes quando
# eram 35), alem do bug do prefixo descrito em prefixo.py.
CAMPOS_NECESSARIOS = ("assunto", "processo.pasta", "dataPrazoFatal")


def movimento(assunto):
    m = RX_MOV.search(assunto or "")
    return m.group(1) if m else None


def eh_prz(assunto):
    """A sigla operacional e' PRZ?

    Tira o prefixo de quadro antes de olhar. Sem isso, "PROD - PRZ - ..."
    responde False e leva junto `agrupa`, `folga_dias_uteis` e
    `preenche_prazo_fatal` — ver o cabecalho de prefixo.py.
    """
    return sem_prefixo(assunto).strip().upper().startswith("PRZ")


def agrupa(atividades):
    """Devolve lista de grupos. Cada grupo vira um cartao.

    PRZ agrupa quando compartilha, no mesmo processo, o MOVIMENTO ou o
    PRAZO FATAL — as duas regras valem juntas:

      mesmo movimento, fatais diferentes -> ED (5 dias) + recurso (15 dias)
                                            sao o mesmo trabalho de analise
      movimentos diferentes, mesmo fatal -> atos encadeados, um trabalho so'
                                            ("decisão de mov. 224 e certidão
                                            de mov. 226"). Medido: 5 de 7.

    Fora de PRZ, so' duplicata literal agrupa: titulo identico e mesmo fatal.
    PROV, PAT e AUD nunca agrupam — audiencia gera varios cartoes por design
    (SKILL secao 4.8).
    """
    grupos, avulsos = [], []
    for a in atividades:
        ass = (a.get("assunto") or "").strip()
        proc = a.get("processo.pasta") or ""
        mv = movimento(ass)
        fatal = a.get("dataPrazoFatal") or ""
        if not (eh_prz(ass) and proc and mv):
            avulsos.append(a)
            continue
        for g in grupos:
            if g["proc"] != proc:
                continue
            if mv in g["movs"] or (fatal and fatal in g["fatais"]):
                g["itens"].append(a)
                g["movs"].add(mv)
                if fatal:
                    g["fatais"].add(fatal)
                break
        else:
            grupos.append({"proc": proc, "movs": {mv},
                           "fatais": {fatal} if fatal else set(), "itens": [a]})

    # fora de PRZ: agrupa so' duplicata literal
    literais = collections.OrderedDict()
    for a in avulsos:
        chave = ((a.get("processo.pasta") or ""),
                 (a.get("assunto") or "").strip().lower(),
                 a.get("dataPrazoFatal") or "")
        literais.setdefault(chave, []).append(a)
    return [g["itens"] for g in grupos] + list(literais.values())


def fatal_do_grupo(itens):
    """O prazo fatal MAIS PROXIMO do grupo, e a lista dos demais.

    Por que o menor (09/10/2026): a regra de agrupamento junta, de proposito,
    o mesmo movimento com fatais diferentes — ED (5 dias) e recurso (15 dias)
    sao o mesmo trabalho de analise. Mas o CARTAO e' um so', e so' pode ter um
    vencimento.

    Usar o fatal do primeiro item do grupo e' sorteio: a ordem vem da API. Se
    sair o maior, o cartao vence DEPOIS do primeiro prazo — e o prazo curto
    passa sem ninguem ver. Visto no lote de 09/10/2026: acordao com ED em
    20/10 e recurso em 04/11, onde o primeiro item do grupo era o de 04/11.

    Devolve (menor, outros) com os demais para o cartao citar — a Controladoria
    precisa saber que ha' mais de um prazo ali dentro.
    """
    from datetime import datetime
    datas = []
    for a in itens:
        f = (a.get("dataPrazoFatal") or "").strip()
        if f:
            try:
                datas.append((datetime.strptime(f, "%d/%m/%Y").date(), f))
            except ValueError:
                pass
    if not datas:
        return None, []
    datas.sort()
    return datas[0][1], [f for _, f in datas[1:]]


def movimentos_do_grupo(itens):
    """Movimentos citados no grupo, para o titulo consolidado."""
    return [m for m in (movimento(i.get("assunto")) for i in itens) if m]


# ---------------------------------------------------------------------------
# Vencimento do cartao e campo Prazo Fatal, por tipo de atividade.
# Medido em 32 pares (14/09/2026), comparando com os cartoes da controladoria:
#
#   PRZ            -> due = fatal - 2 dias uteis.  Acerto 67-80%.
#                     A folga existe para ELABORAR a peca a protocolar.
#   PROV/PAT/AUD   -> due = o PROPRIO prazo fatal. Acerto 88% (28 de 32).
#                     Nao ha o que "entregar antes": comunicar cliente ou
#                     agendar audiencia e' na data.
#
#   Campo "Prazo Fatal": ela preenche em PRZ, mas so' em 3 de 32 cartoes
#   PROV/PAT/AUD. Preencher apenas em PRZ.
# ---------------------------------------------------------------------------

def folga_dias_uteis(assunto):
    """Quantos dias uteis antes do fatal vai o vencimento do cartao."""
    return 2 if eh_prz(assunto) else 0


def preenche_prazo_fatal(assunto):
    """Campo personalizado "Prazo Fatal" so' e' usado em cartoes de prazo."""
    return eh_prz(assunto)


# ---------------------------------------------------------------------------
# Titulo de cartao consolidado.
#
# Quando dois lancamentos do mesmo movimento viram um cartao (ED + recurso),
# a acao no titulo e' reescrita. Padrao medido em 8 de 8 cartoes da controladoria:
#
#     "Verificar eventual providência / ED / recurso"
#
# ATENCAO: esta regra ja' se perdeu uma vez (14/09/2026). Estava implementada
# no script de um lote e nao foi carregada para o script do lote seguinte —
# 4 cartoes sairam com o titulo antigo. Por isso mora AQUI, no modulo, e nao
# no script de execucao. Sempre chamar titulo_consolidado() ao criar.
# ---------------------------------------------------------------------------

_RX_ACAO = re.compile(
    r'Verificar\s+eventual\s+(?:oposi[çc][ãa]o\s+de\s+ED|interposi[çc][ãa]o\s+de\s+recurso)'
    r'(?:\s*/\s*\w+)?', re.I)


def titulo_consolidado(nome, n_lancamentos, outros_movimentos=()):
    """Reescreve o titulo quando o cartao cobre mais de um lancamento.

    Dois casos, ambos medidos:
      - ED + recurso do MESMO movimento -> acao vira
        "Verificar eventual providência / ED / recurso"
      - movimentos DIFERENTES com o mesmo prazo fatal -> o titulo cita os
        dois, como ela escreve: "Ciência da decisão de mov. 224 e certidão
        de mov. 226".
    """
    if n_lancamentos < 2:
        return nome
    if outros_movimentos:
        mv = movimento(nome)
        extras = [m for m in outros_movimentos if m and m != mv]
        if extras:
            alvo = re.search(r'(mov\.?|ev\.?|seq\.?)\s*' + re.escape(mv or ""), nome, re.I) if mv else None
            if alvo:
                cita = " e do mov. " + " e ".join(extras)
                return nome[:alvo.end()] + cita + nome[alvo.end():]
    novo, n = _RX_ACAO.subn("Verificar eventual providência / ED / recurso", nome, count=1)
    return novo if n else nome
