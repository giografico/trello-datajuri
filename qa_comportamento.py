#!/usr/bin/env python3
"""
QA DE COMPORTAMENTO — executa as afirmacoes, nao le o codigo.

Por que existe (20/10/2026). A usuaria apontou que eu vinha afirmando coisas
sobre o codigo sem prova. Medindo a suite: de 231 testes, **78 (34%) apenas
verificavam se um TEXTO existia no codigo-fonte** — passariam mesmo com a
logica quebrada.

Este arquivo so' aceita prova por execucao. Cada verificacao CHAMA a funcao,
ou LE do Trello o estado real, e compara com o afirmado.

    python3 qa_comportamento.py

As seções 1–5 são puras (não acessam rede). As seções 6–7 leem o quadro de
teste do Trello de verdade — exigem `.config-trello.json` preenchido.
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FALHAS = []
TOTAL = 0


def prova(afirmacao, obtido, esperado):
    global TOTAL
    TOTAL += 1
    ok = obtido == esperado
    print(f"  {'ok ' if ok else 'FALHA'} {afirmacao}")
    if not ok:
        print(f"        afirmei : {esperado!r}")
        print(f"        é        : {obtido!r}")
        FALHAS.append(afirmacao)
    return ok


print("QA DE COMPORTAMENTO — cada item executa de verdade\n")

# ---------------------------------------------------------------- 1. escopo
print("1. O que o sistema se recusa a fazer")
import cartao
from cartao import fora_de_escopo
prova("lançamento do quadro de parceiros é recusado",
      bool(fora_de_escopo("PARC - PRZ - 0001234-95.2020.8.16.0001 - x")), True)
prova("lançamento do consultivo é recusado",
      bool(fora_de_escopo("CONS - PRZ - 0001234-95.2020.8.16.0001 - x")), True)
prova("sigla de quadro desconhecida é recusada",
      bool(fora_de_escopo("ZZZ - PRZ - 0001234-95.2020.8.16.0001 - x")), True)
prova("lançamento PROD é aceito",
      fora_de_escopo("PROD - PRZ - 0001234-95.2020.8.16.0001 - x"), None)
prova("fluxo interno (PTE) é recusado",
      bool(fora_de_escopo("PTE - Pedido de Protocolo")), True)

# --------------------------------------------------------- 2. dado pessoal
print("\n2. Dado pessoal não passa")
from sanitiza import sanitizar
prova("CPF é removido do texto",
      "123.456.789-00" in sanitizar("Fulano, CPF 123.456.789-00, residente")[0], False)
prova("RG é removido",
      "9.876.543" in sanitizar("RG nº 9.876.543-2 SSP")[0], False)
prova("CNJ NÃO é removido (é dado do caso)",
      "0001234-95.2020.8.16.0001" in sanitizar("Processo 0001234-95.2020.8.16.0001")[0], True)
prova("valor em reais NÃO é removido",
      "33.667,24" in sanitizar("valor de R$ 33.667,24")[0], True)

# ------------------------------------------------------------- 3. o prazo
print("\n3. O prazo é copiado, não calculado")
from prazo_util import bloco_prazo, recua_uteis
from datetime import date
b = bloco_prazo("21/10/2026")
prova("o bloco traz as três datas", all(x in b for x in ("fatal:", "−1", "−2")), True)
prova("o bloco NÃO cita artigo do CPC", bool(re.search(r"CPC\s*2(19|24)", b)), False)
prova("o bloco NÃO afirma marco inicial", "marco" in b.lower(), False)
prova("o bloco não explica nada — só datas", len(b) < 130, True)
prova("fatal −2 pula o feriado de 12/10", recua_uteis(date(2026,10,13), 2), date(2026,10,8))
prova("sem prazo fatal, sinaliza em vez de inventar", "⚠️" in bloco_prazo(None), True)

# ------------------------------------------------------- 4. consolidação
print("\n4. Consolidação")
from consolida import agrupa, fatal_do_grupo, folga_dias_uteis, eh_prz
g = [{"assunto": "PROD - PRZ - 1 - Ciência da decisão de mov. 47",
      "processo.pasta": "P1", "dataPrazoFatal": "20/10/2026"},
     {"assunto": "PROD - PRZ - 1 - Ciência da decisão de mov. 47",
      "processo.pasta": "P1", "dataPrazoFatal": "04/11/2026"}]
prova("dois PRZ do mesmo movimento viram UM cartão", len(agrupa(g)), 1)
prova("o cartão usa o prazo MAIS PRÓXIMO", fatal_do_grupo(g)[0], "20/10/2026")
prova("os outros prazos são devolvidos", fatal_do_grupo(g)[1], ["04/11/2026"])
prova("PRZ recua 2 dias úteis", folga_dias_uteis("PROD - PRZ - 1 - x"), 2)
prova("PROV usa o próprio fatal", folga_dias_uteis("PROD - PROV - 1 - x"), 0)
prova("eh_prz enxerga através do prefixo", eh_prz("PROD - PRZ - 1 - x"), True)

# ------------------------------------------------------------ 5. audiência
print("\n5. Audiência")
import audiencia
prova("AUD virtual pede chave e link",
      "chave" in (audiencia.falta_completar("AUD - 1 - Audiência Virtual") or ""), True)
prova("AUD presencial NÃO pede chave",
      audiencia.falta_completar("AUD - 1 - Audiência presencial"), None)
prova("PRZ nunca pede chave de audiência",
      audiencia.falta_completar("PRZ - 1 - Ciência"), None)

# ------------------------------------------------- 6. estado real no Trello
print("\n6. Estado real dos cartões no Trello (lido agora)")
import duplica_cartao as dc
cards = dc.trello(f"/boards/{dc.TESTE}/cards",
                  fields="name,dueComplete,idMembers,desc")
meus = [c for c in cards if "gerado automaticamente" in (c.get("desc") or "").lower()
        or "Cartão montado automaticamente" in (c.get("desc") or "")]
prova("nenhum cartão meu nasceu marcado como concluído",
      sum(1 for c in meus if c.get("dueComplete")), 0)
prova("nenhum cartão meu tem membro atribuído",
      sum(1 for c in meus if c.get("idMembers")), 0)
RX_CPF = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")
prova("nenhum cartão meu tem CPF no texto",
      sum(1 for c in meus if RX_CPF.search(c.get("desc") or "")), 0)
prova("nenhum cartão meu tem sigla de quadro no título",
      sum(1 for c in meus if re.match(r"\s*(PROD|PARC|PAR|CONS)\s*[-–|]", c["name"])), 0)
print(f"        ({len(meus)} cartões meus no quadro)")

# --------------------------------------------- 7. duplicata entre cartões
print("\n7. Duplicatas no quadro")
import collections
dup = {n: q for n, q in collections.Counter(
    re.sub(r"\W", "", c["name"].lower()) for c in meus).items() if q > 1}
prova("nenhum par de cartões meus com título idêntico", len(dup), 0)
if dup:
    for n, q in list(dup.items())[:5]:
        orig = [c["name"] for c in meus if re.sub(r"\W","",c["name"].lower()) == n]
        print(f"        {q}x  {orig[0][:60]}")

print(f"\n{'='*70}")
print(f"{TOTAL} verificações por EXECUÇÃO · {len(FALHAS)} falharam")
if FALHAS:
    print("\nAFIRMAÇÕES QUE NÃO SE SUSTENTAM:")
    for f in FALHAS:
        print(f"  ✗ {f}")
    sys.exit(1)
print("todas as afirmações se sustentam quando executadas.")
