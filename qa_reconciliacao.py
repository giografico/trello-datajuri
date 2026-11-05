#!/usr/bin/env python3
"""
RECONCILIAÇÃO — origem contra destino, pelo conjunto inteiro.

Por que existe (20/10/2026). A usuaria nomeou as tres coisas que importam:
cartao ERRADO, DUPLICADO ou FALTANDO. Ate' aqui eu verificava o lote que
acabara de criar e generalizava para o quadro — foi assim que afirmei
"nenhum cartao tem CPF" com dois cartoes de setembro contendo CPF.

Reconciliacao e' a pratica padrao de QA para pipeline de dados: comparar a
origem e o destino pelo CONJUNTO, nao por amostra, e provar que nada se
perdeu nem se duplicou no caminho.

    python3 qa_reconciliacao.py [dias]        (padrao: 20 dias úteis)

Nao cria, nao altera, nao apaga nada. So' le e compara. Exige
`.config-plataforma.json` e `.config-trello.json` preenchidos — sem eles,
falha na conexão em vez de inventar dado.
"""
import collections
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cliente_plataforma as dj
import duplica_cartao as dc
from cartao import fora_de_escopo, sem_prefixo
from consolida import CAMPOS_NECESSARIOS as CC, agrupa
from prazo_util import eh_util
from rodape import CAMPOS_NECESSARIOS as CR

RXCNJ = re.compile(r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}")
RXMOV = re.compile(r"\b(?:mov|ev|evento|movimento|fls|seq|[Ii]d)\.?\s*([\w/]{1,10})", re.I)
CAMPOS = ",".join(sorted(set(CC) | set(CR) | {"assunto", "dataCadastro"}))


def cnj(s):
    m = RXCNJ.search(s or "")
    return re.sub(r"\D", "", m.group(0)) if m else None


def mov(s):
    m = RXMOV.search(s or "")
    return m.group(1).lower() if m else None


def nasceu(card_id):
    try:
        return datetime.fromtimestamp(int(card_id[:8], 16), tz=timezone.utc)
    except Exception:
        return None


def main(dias=20):
    tk = dj.conecta(dj.carrega_config(), verboso=False)
    hoje = date.today()
    uteis, d = [], hoje
    while len(uteis) < dias:
        if eh_util(d):
            uteis.append(d)
        d -= timedelta(days=1)
    uteis.reverse()
    print(f"RECONCILIAÇÃO · {uteis[0]:%d/%m} a {uteis[-1]:%d/%m} "
          f"({len(uteis)} dias úteis)\n")

    # ---------- ORIGEM: o que a Controladoria lançou, em escopo
    origem = []
    for d in uteis:
        rows = dj.get(tk, "/v1/entidades/Atividade",
                      {"campos": CAMPOS, "criterio": f"dataCadastro | igual a | {d:%d/%m/%Y}",
                       "pageSize": 100, "page": 1, "removerHtml": "true"}).get("rows", [])
        for r in rows:
            if not fora_de_escopo(r.get("assunto")):
                r["_dia"] = d
                origem.append(r)
    grupos = agrupa(origem)
    print(f"ORIGEM  : {len(origem)} lançamentos em escopo → {len(grupos)} cartões esperados")

    # ---------- DESTINO: o que existe no quadro
    cards = dc.trello(f"/boards/{dc.TESTE}/cards", fields="name,desc,shortUrl,due,idLabels")
    meus = [c for c in cards
            if "gerado automaticamente" in (c.get("desc") or "").lower()
            or "montado automaticamente" in (c.get("desc") or "").lower()]
    print(f"DESTINO : {len(meus)} cartões criados pela automação no quadro\n")

    # ---------- 1. FALTANDO
    idx = collections.defaultdict(list)
    for c in meus:
        k = cnj(c["name"])
        if k:
            idx[(k, mov(c["name"]))].append(c)
            idx[(k, None)].append(c)
    cobertura = set()
    hist = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "historico_execucoes.jsonl")
    if os.path.exists(hist):
        for linha in open(hist):
            try:
                ex = json.loads(linha)
            except ValueError:
                continue
            for c in ex.get("criados", []):
                for a in c.get("cobre", []):
                    if cnj(a):
                        cobertura.add((cnj(a), mov(a)))
    # So' faz sentido cobrar cartao de dia em que a rotina RODOU. Dia sem
    # execucao nao e' defeito — e' dia sem execucao. Sem esta distincao, uma
    # reconciliacao anterior acusou "faltando" lancamentos de dias que nunca
    # tinham sido processados.
    # CONCLUSIVO so' onde a rotina.py rodou — rotulo "rotina DD/MM/AAAA".
    # Os lotes manuais antigos ("semana 21/09 a 01/10") cobriam varios dias e
    # nao registravam quais lancamentos processaram, entao para eles nao da'
    # para afirmar se um cartao faltou ou se o lancamento nem foi tentado.
    # Misturar os dois e' o tipo de numero inflado que a usuaria ja' apontou.
    dias_rotina = set()
    if os.path.exists(hist):
        for linha in open(hist):
            try:
                ex = json.loads(linha)
            except ValueError:
                continue
            m = re.match(r"rotina (\d{2}/\d{2}/\d{4})", ex.get("rotulo", ""))
            if m:
                dias_rotina.add(m.group(1))

    faltando, nao_processados = [], collections.Counter()
    for g in grupos:
        a = g[0].get("assunto") or ""
        k = cnj(a)
        if not k:
            continue
        if (k, mov(a)) in idx or (k, mov(a)) in cobertura or (k, None) in idx:
            continue
        dia_str = f"{g[0]['_dia']:%d/%m/%Y}"
        if dia_str not in dias_rotina:
            nao_processados[dia_str] += 1      # inconclusivo: a rotina não rodou
            continue
        faltando.append((g[0]["_dia"], a))
    if nao_processados:
        print(f"   INCONCLUSIVO: {sum(nao_processados.values())} lançamentos em "
              f"{len(nao_processados)} dias em que a rotina não rodou")
        print(f"      ({', '.join(d[:5] for d in sorted(nao_processados))})")
    print(f"1. FALTANDO — rotina rodou no dia e o cartão não saiu: {len(faltando)}")
    for d, a in faltando[:10]:
        print(f"     {d:%d/%m}  {sem_prefixo(a)[:64]}")
    if len(faltando) > 10:
        print(f"     ... e mais {len(faltando)-10}")

    # ---------- 2. DUPLICADOS
    por_titulo = collections.defaultdict(list)
    for c in meus:
        por_titulo[re.sub(r"\W", "", c["name"].lower())].append(c)
    dups = {k: v for k, v in por_titulo.items() if len(v) > 1}
    print(f"\n2. DUPLICADOS — mesmo título, mais de um cartão: {len(dups)} par(es)")
    for k, v in list(dups.items())[:10]:
        ds = sorted(filter(None, (nasceu(c.get("id", "")) for c in v)))
        quando = f"{ds[0]:%d/%m %H:%M} e {ds[-1]:%d/%m %H:%M}" if len(ds) > 1 else "?"
        print(f"     {len(v)}x  {v[0]['name'][:52]}")
        print(f"          {quando}  ·  {' '.join(c['shortUrl'][-8:] for c in v)}")

    # ---------- 3. ERRADOS (invariantes que valem para TODO cartão)
    print(f"\n3. ERRADOS — invariantes sobre os {len(meus)} cartões")
    inv = {
        "nasceu marcado como concluído": lambda c: c.get("dueComplete"),
        "sem etiqueta e sem aviso": lambda c: (
            not c.get("idLabels") and "etiqueta cadastrada" not in (c.get("desc") or "")),
        "sigla de quadro no título": lambda c: bool(
            re.match(r"\s*(PROD|PARC|PAR|CONS)\s*[-–|]", c["name"])),
        "sem vencimento e sem aviso": lambda c: (
            not c.get("due") and "Sem prazo fatal" not in (c.get("desc") or "")),
        "afirma método de contagem": lambda c: bool(
            re.search(r"CPC\s*2(19|24)|marco\s*(inicial|:)", c.get("desc") or "", re.I)),
        "resumo duplicado": lambda c: (c.get("desc") or "").count("## Resumo da Decisão") > 1,
    }
    cards_full = dc.trello(f"/boards/{dc.TESTE}/cards",
                           fields="name,desc,due,dueComplete,idLabels,shortUrl")
    byurl = {c["shortUrl"]: c for c in cards_full}
    meus_full = [byurl.get(c["shortUrl"], c) for c in meus]
    total_erros = 0
    for nome, teste in inv.items():
        maus = [c for c in meus_full if teste(c)]
        total_erros += len(maus)
        marca = "ok " if not maus else "✗  "
        print(f"   {marca} {nome}: {len(maus)}")
        for c in maus[:3]:
            print(f"        {c['shortUrl']}  {c['name'][:48]}")

    print(f"\n{'='*70}")
    print(f"faltando {len(faltando)} · duplicados {len(dups)} par(es) · "
          f"invariantes violadas {total_erros}")
    return {"faltando": len(faltando), "duplicados": len(dups), "erros": total_erros}


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
