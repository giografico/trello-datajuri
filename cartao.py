#!/usr/bin/env python3
"""
PORTA ÚNICA de criação de cartão. Todo script deve usar `criar()` daqui.

Por que existe (14/09/2026): a regra de reescrita do título consolidado foi
implementada no script de um lote e nao veio para o script do lote seguinte.
Quatro cartoes sairam errados e o acerto de titulo caiu de 98% para 90%.

Mover a regra para um modulo a tornou DISPONIVEL, nao OBRIGATORIA — o script
seguinte poderia esquecer de chama-la do mesmo jeito. Esta funcao fecha isso:
aplica TODAS as regras medidas de uma vez, e nenhum script monta cartao por
conta propria. Se uma regra nova surgir, entra aqui e vale para todos.

Regras aplicadas (medidas):
  1. titulo consolidado reescrito quando o cartao cobre 2+ lancamentos
  2. vencimento: PRZ = fatal-2 dias uteis; PROV/PAT/AUD = o proprio fatal
  3. campo Prazo Fatal preenchido so' em PRZ
  4. etiqueta pela sigla; nunca etiqueta de executor
  5. nunca atribuir membro — e' tarefa da Controladoria
  6. duplica o ultimo cartao HUMANO do processo; do zero so' se nao houver
  7. nao cria se ja existe cartao meu com o mesmo titulo
  8. materia trabalhista e nota interna nao viram cartao
  9. cartao NUNCA nasce marcado como concluido
 10. so' entra o que e' do quadro deste projeto (prefixo PROD ou sem prefixo);
     o prefixo e' removido do nome do cartao
 11. CPF, RG, CTPS e dados bancarios sao removidos de titulo, conteudo e rodape
"""
import json, re, urllib.request
from datetime import datetime

import duplica_cartao as dc
from consolida import (eh_prz, folga_dias_uteis, preenche_prazo_fatal,
                       titulo_consolidado)
from sanitiza import sanitizar

from prazo_util import recua_uteis

# ---------------------------------------------------------------------------
# TRAVA DE PRE-VOO. criar() se RECUSA a rodar enquanto os testes nao passarem
# nesta sessao. Nao e' convencao nem lembrete: e' excecao.
#
# Por que: as verificacoes eram um passo que alguem tinha de LEMBRAR de fazer.
# Em 14/09/2026 uma regra se perdeu exatamente assim. Agora, sem pre-voo, nao
# existe criacao — e o erro diz o que rodar.
# ---------------------------------------------------------------------------
_PREVOO = {"ok": False, "quando": None}


class PreVooNaoExecutado(RuntimeError):
    pass


def liberar(_token):
    """Chamado SO' pelo pipeline, depois que os dois testes passam."""
    if _token != "testes-passaram":
        raise PreVooNaoExecutado("liberar() só pode ser chamado pelo pipeline")
    _PREVOO["ok"] = True
    _PREVOO["quando"] = datetime.now().isoformat(timespec="seconds")


def _exige_previoo():
    if not _PREVOO["ok"]:
        raise PreVooNaoExecutado(
            "criação bloqueada: o pré-voo não foi executado nesta sessão.\n"
            "    Use  python3 pipeline.py  — ele roda teste_regras.py e\n"
            "    teste_ambiente.py e só então libera a criação.")


SIGLAS_INTERNAS = ("PTE", "PRE", "CST", "CTTO", "SOLIC", "NOT", "VERIFICAR",
                   "CONFIRMAR", "CONTRATO", "SC", "FECHR", "REL")

# ---------------------------------------------------------------------------
# PREFIXO DE QUADRO (decidido em 24/09/2026, mapa confirmado em 25/09/2026).
#
# O lancamento na plataforma processual passa a trazer a sigla do quadro na
# frente do titulo, separada por "|":
#
#     PROD | PRZ - 0001234-85.2026.8.16.0001 - Ciência da decisão... - CLIENTE
#
#     PROD -> Producao Juridica     (o quadro deste projeto)
#     PAR  -> Parceiros             (fora do escopo)
#     CONS -> Consultivo            (fora do escopo)
#
# Estamos automatizando SO' a Producao Juridica — o quadro de teste e' a
# copia dela. PAR e CONS ficam de fora.
#
# Lancamento SEM prefixo entra normalmente: os anteriores a 24/09/2026 nao
# tem prefixo, e barrar por ausencia descartaria todo o historico.
# ---------------------------------------------------------------------------
# Hora das datas no cartao. O Trello guarda em UTC e exibe no fuso de quem
# olha; Brasilia e' UTC-3. Usavamos T12:00Z, que aparecia como 9h — a
# Controladoria usa 12h (pedido de 29/10/2026). 15:00 UTC = 12:00 em Brasilia.
HORA_UTC = "15:00:00.000Z"

AVISO_SEM_ETIQUETA = (
    "⚠️ **Não há etiqueta cadastrada para a sigla deste lançamento.** O cartão "
    "nasceu sem etiqueta — classificar manualmente.")

AVISO_SEM_SIGLA = (
    "⚠️ **O lançamento no DataJuri veio sem a sigla do quadro.** Este cartão "
    "foi criado na Produção Jurídica por padrão — confirmar se é o destino "
    "certo.")

from prefixo import (QUADRO_DESTE_PROJETO, QUADROS_FORA,  # noqa: F401
                     _SIGLAS_OPERACIONAIS, _RX_PREFIXO,
                     prefixo_de_quadro, sem_prefixo)

# VER e VRF sao a mesma coisa — confirmado pela usuaria em 19/10/2026.
# Nao foi mapeado antes de perguntar: adivinhar equivalencia de sigla e' o
# mesmo erro do filtro por ramo do CNJ, removido em 15/10. A sigla e' escrita
# pela Controladoria; so' ela sabe o que e' equivalente.
_ETIQUETAS = [("PRZ", "PRZ - Prazo"), ("PROV", "PROV - Providências"),
              ("VER", "VRF - Verificação"), ("VRF", "VRF - Verificação"),
              ("PERÍCIA", "PER - Perícia"), ("PERICIA", "PER - Perícia"),
              ("PER", "PER - Perícia"), ("DIL", "DIL - Diligência"),
              ("PAT", "PAT - Pauta"), ("INCLUÍDO", "PAT - Pauta"),
              ("AUD", "AUD - Audiência"), ("NEG", "NEGOCIAÇÃO"),
              ("DEFESA", "DEFESA"), ("AÇÃO", "AÇÃO"), ("AÇÂO", "AÇÃO"),
              ("ACOMPANHAMENTO", "ACOMPANHAMENTO")]


def nota_interna(assunto):
    """Titulo informal = lembrete da equipe, nao cartao. Medido: 14 de 64 na
    semana de 24-30/08 nao tinham par no quadro oficial."""
    a = (assunto or "").strip()
    if not a:
        return True
    primeira = a.split()[0]
    tem_sigla = any(a.upper().startswith(s) for s, _ in _ETIQUETAS)
    tem_cnj = bool(re.search(r'\d{7}-\d{2}\.\d{4}', a))
    if primeira.islower():                      # "ver lanc...", "lançar..."
        return True
    if not tem_sigla and not tem_cnj:
        return True
    if re.search(r'lan[çc]ar eventos para a audi', a, re.I):
        return True
    return False


def fora_de_escopo(assunto):
    """Devolve o motivo, ou None se o lancamento deve virar cartao."""
    a = (assunto or "").strip()
    q = prefixo_de_quadro(a)
    if q in QUADROS_FORA:
        return f"quadro {q} — fora do escopo deste projeto"
    if q and q != QUADRO_DESTE_PROJETO:
        return f"quadro {q} — sigla desconhecida, conferir"
    a = sem_prefixo(a)
    sig = a.split()[0].upper().strip("-–") if a else "?"
    if sig in SIGLAS_INTERNAS:
        return f"fluxo interno ({sig})"
    # NAO ha' filtro por tipo de processo aqui, de proposito.
    #
    # Removido em 15/10/2026, por decisao da usuaria:
    #
    #   "nao e' tua funcao escolher para onde vai o lancamento, e' funcao
    #    dela e ela ja' resolveu isso por voce"
    #
    # O destino vem da SIGLA DE QUADRO no titulo, e so' dela. A divisao entre
    # os quadros e' OPERACIONAL, a criterio da Controladoria — o quadro de
    # parceiros recebe trabalhista, familia e outros assuntos. Nenhuma leitura
    # do numero do processo reproduz esse criterio, e tentar reproduzi-lo e'
    # decidir no lugar de quem decide.
    #
    # O que havia aqui era um filtro por ramo do CNJ (J=5, trabalhista). Ele
    # BARROU 2 lancamentos marcados PROD pela Controladoria, em 853 medidos
    # entre 01/09 e 15/10 — descartando em silencio o trabalho dela.
    if nota_interna(a):
        return "nota interna, não é cartão"
    return None


def _etiqueta(assunto, labels):
    s = (assunto or "").strip().upper()
    for pref, nome in _ETIQUETAS:
        if s.startswith(pref) and nome in labels:
            return [labels[nome]]
    return []


def criar(assunto, conteudo, rodape, n_lancamentos=1, prazo_fatal=None,
          processo=None, simular=False, comentario_autoria=None):
    """Cria UM cartao com todas as regras aplicadas.

    Devolve (cartao, motivo). Se cartao for None, `motivo` diz por que nao
    foi criado — fora de escopo, ja existe, etc.
    """
    _exige_previoo()
    assunto = (assunto or "").strip()
    motivo = fora_de_escopo(assunto)
    if motivo:
        return None, motivo

    nome = titulo_consolidado(sem_prefixo(assunto), n_lancamentos)   # regra 1 + prefixo
    # regra 11: CPF, RG, CTPS e dados bancarios saem SEMPRE, na porta. A
    # observacao do lancamento as vezes traz a qualificacao completa da parte,
    # e ela e' copiada para o cartao em PROV e NEG (2 de 89 cartoes, 01/10/2026).
    nome, _ = sanitizar(nome)
    conteudo, _ = sanitizar(conteudo)
    rodape, _ = sanitizar(rodape)

    # regra 12: lancamento SEM sigla de quadro nasce aqui, mas avisado.
    #
    # Decidido em 15/10/2026. O destino do cartao e' decisao da Controladoria,
    # registrada na sigla do titulo (PROD/PARC/CONS). Quando a sigla nao vem,
    # nao ha' decisao a seguir — e adivinhar pelo tipo de processo foi
    # proibido no mesmo dia, por ser decidir no lugar dela.
    #
    # Entao: cria na Producao Juridica, que era o destino unico antes de a
    # sigla existir, e DIZ no cartao que o destino nao foi confirmado. O aviso
    # vai no topo da descricao, nao no rodape: quem abre o cartao tem de ver
    # antes de trabalhar nele.
    #
    # Medido na semana de 09 a 15/10/2026: 11 de 75 lancamentos (15%) tinham
    # sigla operacional (PRZ/PROV) mas nenhuma sigla de quadro — 1 a 2 por dia.
    if prefixo_de_quadro(assunto) is None:
        conteudo = (AVISO_SEM_SIGLA + "\n\n" + conteudo).strip()

    existe = dc.ja_criei(nome, processo)                        # regra 7
    if existe:
        return None, f"já existe: {existe['shortUrl']}"

    due = None
    if prazo_fatal:                                             # regra 2
        f = datetime.strptime(prazo_fatal, "%d/%m/%Y").date()
        due = recua_uteis(f, folga_dias_uteis(nome)).isoformat() + f"T{HORA_UTC}"

    if simular:
        return {"name": nome, "due": due, "simulado": True}, "simulação"

    labels = {l.get("name"): l["id"]
              for l in dc.trello(f"/boards/{dc.TESTE}/labels", fields="name")}
    lb = _etiqueta(nome, labels)                                # regra 4
    # regra 13: sigla sem etiqueta cadastrada nao faz o cartao nascer mudo.
    #
    # Em 16/10/2026 um lancamento "VER - ... - Confirmar se ainda ha'
    # necessidade de ..." nasceu SEM ETIQUETA: a sigla VER nao esta' no mapa,
    # e o quadro tem "VRF - Verificação", que PARECE equivalente.
    #
    # Nao mapeamos VER -> VRF de proposito. Adivinhar equivalencia de sigla e'
    # o mesmo erro do filtro por ramo do CNJ, removido em 15/10: decidir no
    # lugar de quem decide. A sigla e' escrita pela Controladoria e so' ela
    # sabe se sao a mesma coisa.
    #
    # Entao: o cartao nasce sem etiqueta, mas DIZENDO que nasceu — sem
    # etiqueta ele some dos filtros do quadro, que e' como a equipe trabalha.
    if not lb:
        conteudo = (AVISO_SEM_ETIQUETA + "\n\n" + conteudo).strip()

    novo = None
    if processo:                                                # regra 6
        try:
            novo, _ = dc.cria(processo=processo, nome=nome, conteudo=conteudo,
                              due=due, prazo_fatal_iso=None, rodape=rodape)
        except Exception:
            novo = None
    if novo:
        # reforco: mesmo com dueComplete="false" no POST, conferir e corrigir.
        # E' a diferenca entre um cartao de prazo aberto e um que ninguem ve.
        ajuste = {}
        if lb:
            ajuste["idLabels"] = ",".join(lb)
        atual = dc.trello(f"/cards/{novo['id']}", fields="dueComplete")
        if atual.get("dueComplete"):
            ajuste["dueComplete"] = "false"
        if ajuste:
            dc.trello(f"/cards/{novo['id']}", "PUT", **ajuste)
    else:
        desc = "\n\n".join([conteudo, rodape,
                            "\n‌\n⚠️ **Sem cartão anterior deste processo para herdar** — "
                            "faltam link da pasta e contatos do cliente."])
        p = {"idList": dc.LISTA, "name": nome, "desc": desc, "pos": "top",
             "dueComplete": "false"}
        if due:
            p["due"] = due
        if lb:
            p["idLabels"] = ",".join(lb)
        novo = dc.trello("/cards", "POST", **p)

    if prazo_fatal and preenche_prazo_fatal(nome):              # regra 3
        cfg = json.load(open(dc.TRELLO_CFG))
        f = datetime.strptime(prazo_fatal, "%d/%m/%Y").date()
        req = urllib.request.Request(
            f"https://api.trello.com/1/cards/{novo['id']}/customField/"
            f"{dc.CF_PRAZO_FATAL}/item?key={cfg['key']}&token={cfg['token']}",
            data=json.dumps({"value": {"date": f"{f.isoformat()}T{HORA_UTC}"}}).encode(),
            method="PUT", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60, context=dc.CTX) as r:
            r.read()

    # AUTORIA VAI PARA O COMENTARIO, nao para a descricao (pedido da
    # Controladoria em 29/10/2026). A descricao e' para o teor da decisao e
    # para os dados operacionais; quem lancou e' procedencia, e procedencia
    # mora no historico do cartao.
    if comentario_autoria:
        try:
            dc.trello(f"/cards/{novo['id']}/actions/comments", "POST",
                      text=comentario_autoria)
        except Exception:
            pass          # perder o comentario nao invalida o cartao

    # O cartao recem-criado entra no cache AGORA. Sem isto, outro lancamento
    # igual nos 60s seguintes nao o enxerga e nasce duplicado — aconteceu em
    # 19/10/2026, com 56 segundos de diferenca. Ver duplica_cartao.registrar_novo.
    dc.registrar_novo(novo)

    # regra 5: membro nunca e' atribuido — nada a fazer, so' nao fazer
    return novo, "criado"
