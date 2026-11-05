#!/usr/bin/env python3
"""
Teste de AMBIENTE: confere se os ids fixos no codigo ainda existem no Trello.

    python3 teste_ambiente.py

Por que existe: `teste_regras.py` valida decisoes puras e nao acessa rede.
Ele nunca pegaria um id de etiqueta, lista ou campo personalizado errado —
e esse erro e' silencioso do pior jeito: o Trello aceita a criacao e
simplesmente ignora o id invalido. O cartao nasce SEM a etiqueta, sem nada
falhar. Em lote, sao 40 cartoes mudos.

Rodar junto com teste_regras.py antes de qualquer criacao em lote, e sempre
que alguem mexer no quadro (renomear lista, apagar etiqueta, trocar campo).
"""
import sys
import duplica_cartao as dc
from duplica_cartao import CF_PRAZO_FATAL
from cartao import _ETIQUETAS

FALHAS = []


def checa(nome, ok, detalhe=""):
    if not ok:
        FALHAS.append(f"{nome} — {detalhe}")
    print(f"  {'ok ' if ok else 'FALHOU'} {nome}{'' if ok else '  -> ' + detalhe}")


print(f"quadro de teste: {dc.TESTE}")
b = dc.trello(f"/boards/{dc.TESTE}", fields="name,closed")
checa("quadro de teste existe e está aberto",
      b.get("name") and not b.get("closed"), str(b)[:60])

listas = {l["id"]: l["name"] for l in dc.trello(f"/boards/{dc.TESTE}/lists", fields="name")}
checa("lista de destino existe", dc.LISTA in listas,
      f"id {dc.LISTA} não está entre as {len(listas)} listas")

labels = {l.get("name") for l in dc.trello(f"/boards/{dc.TESTE}/labels", fields="name")}
for _, nome in _ETIQUETAS:
    checa(f"etiqueta '{nome}' existe", nome in labels, "não encontrada no quadro")

campos = {f["id"]: f["name"] for f in dc.trello(f"/boards/{dc.TESTE}/customFields")}
checa("campo Prazo Fatal existe pelo id", CF_PRAZO_FATAL in campos,
      f"id {CF_PRAZO_FATAL} não está entre {list(campos.values())}")
if CF_PRAZO_FATAL in campos:
    checa("o id aponta mesmo para 'Prazo Fatal'",
          campos[CF_PRAZO_FATAL] == "Prazo Fatal", campos[CF_PRAZO_FATAL])

print()
if FALHAS:
    print(f"{len(FALHAS)} PROBLEMA(S) DE AMBIENTE — NÃO criar cartões antes de resolver:\n")
    for f in FALHAS:
        print("  " + f)
    sys.exit(1)

# --------------------------------------------------------------------------
# AMBIENTE DA MAQUINA (15/10/2026). Ate' esta data o projeto so' rodava na
# maquina de quem o escreveu: o cliente da plataforma processual morava fora
# do repositorio e as credenciais eram apontadas por caminho absoluto.
# Clonar e rodar dava ModuleNotFoundError. Estas checagens falham ANTES de
# qualquer cartao.
import config as _cfg
_d = _cfg.diagnostico()
_falhas_amb = []
if not _d["config_plataforma_existe"]:
    _falhas_amb.append(f"credencial da plataforma processual não encontrada: "
                       f"{_d['config_plataforma']}\n"
                       "    defina CJ_CONFIG ou ponha o arquivo ao lado do código")
if not _d["config_trello_existe"]:
    _falhas_amb.append(f"credencial do Trello não encontrada: {_d['config_trello']}")
if not _d["claude_cli"]:
    _falhas_amb.append("Claude Code não encontrado no PATH — os resumos não serão "
                       "gerados. Instalar, ou aceitar cartões sem resumo.")
try:
    import cliente_plataforma as _cp   # noqa: F401
except ImportError:
    _falhas_amb.append("cliente_plataforma.py ausente — a integração não sobe")
_cfg.garante_trabalho()
if _falhas_amb:
    print("\nAMBIENTE INCOMPLETO:\n")
    for f in _falhas_amb:
        print(f"  ✗ {f}")
    import sys as _s
    _s.exit(1)
print("  ok  ambiente da máquina: credenciais, Claude Code e diretório de trabalho")

print("ambiente íntegro: ids de lista, etiqueta e campo conferem.")
