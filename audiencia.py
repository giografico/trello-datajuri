#!/usr/bin/env python3
"""
Cartao de audiencia — o que ele leva e o que falta nele.

Medido em 15/10/2026 sobre os 90 cartoes AUD do quadro oficial:

    98%  sistema (PROJUDI/PJe/eproc) + numero do processo
    77%  contatos do cliente
    76%  link dos documentos (Drive)
    66%  link de acesso (Teams/Zoom)
    50%  chave da audiencia
     6%  prazo ou exigencia do ato     <- a unica parte "resumo"

A descricao de audiencia e' OPERACIONAL, nao analitica: diz como entrar, onde
estao os documentos e com quem falar. Nao resume decisao — nao ha' decisao a
resumir, a publicacao so' diz "audiencia designada, veja no sistema".

DE ONDE VEM CADA PARTE, no nosso fluxo:

    titulo (com data e hora)      do lancamento no DataJuri
    Drive, pasta, contatos        da duplicacao do cartao anterior
    exigencias do ato             do teor da intimacao, quando houver
    chave + link de acesso        NAO TEMOS. So' existem no sistema do
                                  tribunal, e o projeto nao acessa tribunal
                                  (CLAUDE.md secao 8).

Por isso o cartao de audiencia nasce incompleto, e tem de DIZER isso: entregar
algo para COMPLETAR e' o desenho do projeto; entregar algo que PARECE pronto e
nao esta' e' o erro que afundou as tentativas anteriores.

MODALIDADE IMPORTA. Medido nos mesmos 90 cartoes:

    virtual         70 cartoes   57% com chave   84% com link
    semipresencial   7 cartoes   57% com chave   86% com link
    presencial       8 cartoes    0% com chave   25% com link

Audiencia presencial nao tem chave nem sala virtual — avisar ali seria ruido,
e ruido repetido ensina a ignorar o aviso.
"""
import re

RX_AUD = re.compile(r"^\s*AUD\b", re.I)
_MODOS = (("semipresencial", r"semipresencial"),
          ("virtual",        r"virtual|videoconfer|v[ií]deoconfer"),
          ("presencial",     r"presencial"))


def eh_audiencia(assunto):
    return bool(RX_AUD.match(assunto or ""))


def modalidade(assunto):
    """virtual · semipresencial · presencial · None (não declarada)."""
    a = (assunto or "").lower()
    for nome, rx in _MODOS:
        if re.search(rx, a):
            return nome
    return None


def precisa_sala_virtual(assunto):
    """A audiencia acontece em sala virtual, logo exige chave e link?

    Modalidade nao declarada conta como SIM: 70 dos 90 cartoes sao virtuais,
    e o custo de avisar a toa e' menor que o de a pessoa chegar na hora sem o
    link.
    """
    return modalidade(assunto) != "presencial"


def falta_completar(assunto):
    """Aviso do que o cartao nao pode trazer, ou None."""
    if not eh_audiencia(assunto) or not precisa_sala_virtual(assunto):
        return None
    return ("⚠️ **Falta completar:** chave da audiência e link de acesso — "
            "obter no sistema do tribunal.")
