#!/usr/bin/env python3
"""
Cache de resumos pre-processados.

Por que existe (decidido em 30/09/2026): ler a decisao e escrever o resumo e'
o unico passo que exige o modelo, e e' o que domina o tempo — ~1 a 5 minutos
por cartao, contra ~10 segundos de trabalho mecanico.

Medido em 5 dias uteis (108 intimacoes):
  83% das intimacoes do recorte viram lancamento  -> pre-processar desperdica pouco
  74% ja' vem com teor no proprio recorte         -> da' para resumir de manha

Entao: de manha o modelo le o recorte do dia e escreve os resumos das que tem
teor. Quando a controladoria lanca a atividade, o resumo JA' EXISTE e o cartao sai em
~15 segundos. As sem teor continuam sendo processadas na hora — o teor delas
so' passa a existir quando a equipe cola no lancamento.

ONDE FICA: scratchpad da sessao, NUNCA no repositorio. O resumo carrega teor
de decisao e nome de cliente (CLAUDE.md secao 5).

VALIDADE: um dia. Resumo de terca nao serve para quarta — a intimacao pode ter
sido republicada, e colar resumo velho em cartao novo e' pior que nao ter
resumo nenhum.
"""
import json
import os
import re
from datetime import date, datetime

from config import TRABALHO as _SC


def _arquivo(dia):
    return os.path.join(_SC, f"resumos_{dia.replace('/', '-')}.json")


def _so_digitos(processo):
    return re.sub(r"\D", "", processo or "")


def chaves(processo, movimento=None, disponibilizacao=None):
    """Chaves possiveis para um item, da mais forte para a mais fraca.

    Processo + movimento e' exato. Sem movimento, processo + disponibilizacao.
    Se nenhuma bater na hora do lancamento, o resumo e' descartado e o item e'
    processado do zero — melhor perder o cache do que colar resumo errado.
    """
    p = _so_digitos(processo)
    if not p:
        return []
    out = []
    if movimento:
        out.append(f"{p}+mov{movimento}")
    if disponibilizacao:
        out.append(f"{p}+disp{disponibilizacao}")
    return out


def guardar(dia, itens):
    """itens: lista de dicts com processo, movimento, disponibilizacao, resumo."""
    os.makedirs(_SC, exist_ok=True)
    banco = {}
    for it in itens:
        for k in chaves(it.get("processo"), it.get("movimento"),
                        it.get("disponibilizacao")):
            banco[k] = {"resumo": it["resumo"],
                        "processo": it.get("processo"),
                        "movimento": it.get("movimento"),
                        "disponibilizacao": it.get("disponibilizacao"),
                        "gerado_em": datetime.now().isoformat(timespec="seconds")}
    with open(_arquivo(dia), "w") as f:
        json.dump(banco, f, ensure_ascii=False, indent=2)
    return len(banco)


def _carregar(dia):
    try:
        with open(_arquivo(dia)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def buscar(processo, movimento=None, disponibilizacao=None, dia=None):
    """Resumo pronto para este item, ou None.

    Devolve (resumo, chave_usada) ou (None, None). A chave usada entra no
    rodape do cartao — se o resumo veio do cache, isso precisa ser auditavel.
    """
    dia = dia or date.today().strftime("%d/%m/%Y")
    banco = _carregar(dia)
    if not banco:
        return None, None
    for k in chaves(processo, movimento, disponibilizacao):
        if k in banco:
            return banco[k]["resumo"], k
    return None, None


def estatisticas(dia=None):
    dia = dia or date.today().strftime("%d/%m/%Y")
    banco = _carregar(dia)
    unicos = {v["resumo"][:80] for v in banco.values()}
    return {"dia": dia, "chaves": len(banco), "resumos": len(unicos),
            "arquivo": _arquivo(dia)}


def limpar_antigos(manter_dias=2):
    """Resumo velho e' lixo com teor de cliente dentro. Apagar."""
    if not os.path.isdir(_SC):
        return 0
    hoje = date.today()
    apagados = 0
    for nome in os.listdir(_SC):
        m = re.match(r"resumos_(\d{2})-(\d{2})-(\d{4})\.json$", nome)
        if not m:
            continue
        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if (hoje - d).days > manter_dias:
            os.remove(os.path.join(_SC, nome))
            apagados += 1
    return apagados
