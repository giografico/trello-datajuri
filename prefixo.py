#!/usr/bin/env python3
"""
Prefixo de quadro no titulo do lancamento.

Mora em modulo proprio desde 09/10/2026, e o motivo importa: estas funcoes
precisam ser usadas por `cartao` E por `consolida`, e `cartao` ja' importa
`consolida`. Deixa-las em `cartao` criava ciclo — e, pior, criou um BUG
SILENCIOSO que so' apareceu num teste de lote:

    eh_prz("PROD - PRZ - 5000001-15 - ...")  ->  False

A sigla do quadro entrou nos lancamentos em 24/09/2026. A partir dali,
`consolida.eh_prz` deixou de reconhecer PRZ, porque le a sigla no INICIO do
titulo. `cartao.criar()` nao sofria: la' o prefixo ja' tinha sido removido.
Mas `agrupa()`, `folga_dias_uteis()` e `preenche_prazo_fatal()` rodam ANTES,
com o titulo cru.

Efeito medido no lote de 05-08/10/2026, antes da correcao: 39 lancamentos
viraram 39 cartoes (nenhum agrupamento, quando havia 4 pares obvios), nenhum
com o campo Prazo Fatal, e todos com vencimento no dia fatal em vez de
fatal-2. Nada falhava — os cartoes nasciam errados, calados.
"""
import re

QUADRO_DESTE_PROJETO = "PROD"
# PARC e' o quadro de PARCEIROS, confirmado pela usuaria em 09/10/2026 — a
# mesma coisa que PAR, escrita de outro jeito. Importa registrar o motivo de
# nao bastar filtrar por tipo de processo: o quadro de parceiros e' sobretudo
# trabalhista, MAS tambem recebe familia. A sigla e' a unica fonte confiavel
# de roteamento; o CNJ nao basta.
# Antes da correcao, PARC caia em "sigla desconhecida, conferir" — barrado,
# que e' o lado seguro, mas pelo motivo errado.
QUADROS_FORA = ("PAR", "PARC", "CONS")
# O separador na pratica e' HIFEN, nao pipe. Em 01/10/2026, dos 36 lancamentos
# que ja' vinham com prefixo, 36 usavam "PROD - " e nenhum usava "PROD | ".
# A regex so' aceitava pipe, entao TODOS passavam como "sem prefixo" — o
# roteamento nunca teria funcionado, em silencio. Aceitar os dois.
#
# O prefixo so' e' reconhecido quando vem seguido de uma SIGLA OPERACIONAL
# conhecida (PRZ, PROV, PAT...). Sem isso, "PRZ - 0001234-56..." seria lido
# como prefixo "PRZ" e o titulo perderia a sigla.
# Siglas que podem vir DEPOIS do prefixo de quadro. Inclui as internas
# (PTE, PRE, CST...) de proposito: sem elas, "PROD | PTE - ..." nao teria o
# prefixo removido e seria barrado como "nota interna" em vez de "fluxo
# interno". O lancamento e' barrado nos dois casos, mas pelo motivo certo —
# motivo errado no relatorio e' diagnostico errado depois.
_SIGLAS_OPERACIONAIS = ("PRZ", "PROV", "PAT", "AUD", "NEG", "AÇÃO", "AÇÂO",
                        "ACAO", "DEFESA", "ACOMPANHAMENTO", "DIL", "VRF", "PER",
                        "PTE", "PRE", "CST", "CTTO", "SOLIC", "NOT", "SC", "REL")
_RX_PREFIXO = re.compile(
    r'^\s*([A-ZÀ-Ú]{2,6})\s*[|\-–]\s*(?=(' + "|".join(_SIGLAS_OPERACIONAIS) + r')\b)',
    re.I)


# Quadros conhecidos. Se o titulo comeca com um destes, e' prefixo de quadro
# — nao importa o que venha depois.
#
# Corrigido em 29/10/2026. A regex so' reconhecia o prefixo quando ele vinha
# seguido de uma sigla operacional CONHECIDA, para nao confundir
# "PRZ - PROV - ..." com prefixo. Mas isso fazia sigla nova passar batido:
#
#     PROD - PERÍCIA - 1234567-72... -> nasceu com "PROD" no nome do cartao
#     PROD - Onboarding - Unidade...  -> idem
#
# PROD, PARC, PAR e CONS nunca sao siglas operacionais. Reconhece-las direto
# resolve sem precisar adivinhar o que a sigla seguinte significa — e sem
# precisar atualizar lista toda vez que a Controladoria criar uma sigla.
_QUADROS = ("PROD", "PARC", "PAR", "CONS")
_RX_QUADRO = re.compile(r"^\s*(" + "|".join(_QUADROS) + r")\s*[|\-–]\s*", re.I)


def prefixo_de_quadro(assunto):
    """Sigla do quadro no titulo, ou None se o lancamento nao tiver prefixo."""
    mq = _RX_QUADRO.match(assunto or "")
    if mq:
        return mq.group(1).upper()
    m = _RX_PREFIXO.match(assunto or "")
    if not m:
        return None
    sig = m.group(1).upper()
    # "PRZ - PROV - ..." nao e' prefixo de quadro: e' sigla operacional seguida
    # de outra coisa. Prefixo de quadro nunca e' uma sigla operacional.
    return None if sig in _SIGLAS_OPERACIONAIS else sig


def sem_prefixo(assunto):
    """Titulo sem a sigla do quadro. O prefixo serve para ROTEAR; dentro do
    quadro certo ele e' redundante e nao vai para o nome do cartao."""
    a = (assunto or "").strip()
    if _RX_QUADRO.match(a):
        return _RX_QUADRO.sub("", a).strip()
    return _RX_PREFIXO.sub("", a).strip()


def eh_sigla_operacional(sig):
    return (sig or "").upper() in _SIGLAS_OPERACIONAIS


# ---------------------------------------------------------------------------
# NAO existe aqui funcao que adivinhe o quadro pelo numero do processo.
#
# Havia: `ramo_do_cnj` / `fora_do_escopo`, que liam o digito J do CNJ para
# identificar Justica do Trabalho. Removidas em 15/10/2026 — a usuaria foi
# explicita:
#
#   "nao e' tua funcao escolher para onde vai o lancamento, e' funcao dela e
#    ela ja' resolveu isso por voce"
#
# A divisao entre quadros e' OPERACIONAL, a criterio da Controladoria: o
# quadro de parceiros recebe trabalhista, familia e outros assuntos. O numero
# do processo nao carrega esse criterio.
#
# Se um lancamento chegar SEM sigla de quadro, o destino e' desconhecido —
# e desconhecido se pergunta, nao se adivinha.
