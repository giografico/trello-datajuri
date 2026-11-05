#!/usr/bin/env python3
"""
Preparacao da manha — separa o que da' para resumir antes do lancamento.

    python3 prepara_manha.py [DD/MM/AAAA]

O que faz: le o recorte do dia, separa as intimacoes que JA' TRAZEM o teor da
decisao daquelas que so' trazem a referencia ao movimento, e entrega a lista
para o modelo resumir. Os resumos vao para o cache (cache_resumos.py) e sao
usados quando a controladoria lanca a atividade.

O que NAO faz: nao escreve o resumo. Isso exige o modelo ler a decisao — e' a
unica etapa nao automatizavel. Este script prepara o material; o modelo
resume; guardar() salva.

Medido em 5 dias uteis, 108 intimacoes:
  74% ja' vem com teor  -> resumo pronto de manha, cartao sai em ~15s
  26% sem teor          -> processadas na hora, quando a equipe cola o teor
  83% viram lancamento  -> o desperdicio do pre-processamento e' pequeno

Saida: JSON no scratchpad. CONTEM DADOS DE CLIENTE — nao versionar.
"""
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cliente_plataforma as dj
from fila_intimacoes import disponibilizacao, movimento, so_digitos

from config import TRABALHO as SC

CAMPOS = ("data,numeroProcesso,faseProcessoId,configConsultaRecorteId,lido,jornal,"
          "tribunal,vara,pagina,textoCompleto,faseProcesso.processo.cliente.nome,"
          "faseProcesso.processo.adverso.nome,faseProcesso.processo.proprietario.nome")

# Marcas de que a publicacao NAO traz o teor — so' a referencia ao movimento.
RX_SEM_TEOR = re.compile(
    r'Acesse o sistema Projudi|Intimação referente ao movimento \(seq\.\s*\d+\)\s*'
    r'[A-ZÀ-Ú\s]{4,60}\(\d{2}/?\d{2}/?\d{4}\)', re.I)
# Um teor de verdade raramente cabe em menos de 900 caracteres uteis.
MIN_TEOR = 900


def tem_teor(texto):
    """A publicacao traz a decisao, ou so' aponta para ela?"""
    t = re.sub(r'\s+', ' ', texto or '').strip()
    t_util = re.sub(r'https?\S+', '', t)
    if RX_SEM_TEOR.search(t_util) and len(t_util) < 1200:
        return False
    return len(t_util) >= MIN_TEOR


def baixar(dia):
    cfg = dj.carrega_config()
    tk = dj.conecta(cfg, verboso=False)
    todos, page = [], 1
    while True:
        d = dj.get(tk, "/v1/entidades/RecorteIntimacoes",
                   {"campos": CAMPOS, "criterio": f"data | igual a | {dia}",
                    "page": page, "pageSize": 100, "removerHtml": "true"})
        linhas = d.get("rows", [])
        todos.extend(linhas)
        if len(linhas) < 100 or len(todos) >= d.get("listSize", 0):
            break
        page += 1
    return todos


def vistas_antes(dia, dias_atras=5):
    """Chaves das intimacoes ja' vistas nos dias anteriores.

    Por que existe (medido em 06/10/2026, sobre 02 e 05/10): 15 de 48
    registros eram A MESMA intimacao contada duas vezes. O AtitudeJur publica
    na sexta; o Alerte entrega a mesma na segunda, trazendo a disponibilizacao
    correta de sexta no proprio texto. A deduplicacao olhava so' dentro do dia
    e nao via.

    Efeito de nao ter isto: a mesma decisao e' resumida de novo no dia
    seguinte (gasta cota do modelo a' toa) e a contagem de intimacoes do dia
    sai inflada em ate' um terco.

    A chave inclui a disponibilizacao, entao bater aqui significa a MESMA
    publicacao — nao e' republicacao nem movimento novo.
    """
    try:
        d0 = datetime.strptime(dia, "%d/%m/%Y").date()
    except ValueError:
        return {}
    vistas = {}
    for n in range(1, dias_atras + 1):
        d = d0 - timedelta(days=n)
        caminho = os.path.join(SC, f"manha_{d.strftime('%d-%m-%Y')}.json")
        try:
            with open(caminho) as f:
                j = json.load(f)
        except (OSError, ValueError):
            continue
        for it in j.get("para_resumir", []) + j.get("sem_teor", []):
            ch = (it.get("processo"), it.get("movimento"),
                  it.get("disponibilizacao"))
            vistas.setdefault(ch, d.strftime("%d/%m/%Y"))
    return vistas


def main(dia):
    brutos = baixar(dia)
    antes = vistas_antes(dia)
    prontas, sem_teor, repetidas, vistos = [], [], [], set()
    for r in brutos:
        texto = r.get("textoCompleto") or ""
        fonte = r.get("configConsultaRecorteId") or ""
        proc = so_digitos(r.get("numeroProcesso"))
        mv = movimento(texto)
        disp = disponibilizacao(fonte, r.get("data"), texto)
        chave = (proc, mv, disp)
        if not proc or chave in vistos:      # mesma intimacao pelas duas fontes
            continue
        vistos.add(chave)
        if chave in antes:                   # ja' vista em dia anterior
            repetidas.append({"processo_fmt": r.get("faseProcessoId")
                              or r.get("numeroProcesso"),
                              "disponibilizacao": disp, "vista_em": antes[chave]})
            continue
        item = {
            "processo": proc,
            "processo_fmt": r.get("faseProcessoId") or r.get("numeroProcesso"),
            "movimento": mv,
            "disponibilizacao": disp,
            "fonte": fonte,
            "cliente": r.get("faseProcesso.processo.cliente.nome") or "",
            "adverso": r.get("faseProcesso.processo.adverso.nome") or "",
            "responsavel": r.get("faseProcesso.processo.proprietario.nome") or "",
            "tribunal": r.get("tribunal"), "vara": r.get("vara"),
            "jornal": r.get("jornal"), "pagina": r.get("pagina"),
            "texto": texto,
        }
        (prontas if tem_teor(texto) else sem_teor).append(item)

    saida = {"dia": dia,
             "totais": {"bruto": len(brutos), "unicas": len(vistos),
                        "repetidas": len(repetidas),
                        "novas": len(vistos) - len(repetidas),
                        "com_teor": len(prontas), "sem_teor": len(sem_teor)},
             "para_resumir": prontas, "sem_teor": sem_teor,
             "repetidas": repetidas}
    os.makedirs(SC, exist_ok=True)
    dest = os.path.join(SC, f"manha_{dia.replace('/', '-')}.json")
    with open(dest, "w") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    t = saida["totais"]
    print(f"recorte de {dia}: {t['bruto']} registros -> {t['unicas']} intimações únicas")
    if t["repetidas"]:
        print(f"  já vistas em dia anterior       : {t['repetidas']:3d}  "
              f"(não resumir de novo)")
    print(f"  NOVAS deste dia                 : {t['novas']:3d}")
    print(f"  COM teor, dá para resumir agora : {t['com_teor']:3d}")
    print(f"  SEM teor, aguardam o lançamento : {t['sem_teor']:3d}")
    if t["unicas"]:
        print(f"  cobertura do pré-processamento  : {t['com_teor']/t['unicas']*100:.0f}%")
    print(f"\n-> {dest}  (CONTÉM DADOS DE CLIENTE — não versionar)")
    print("\nPróximo passo: o modelo lê `para_resumir`, escreve os resumos e chama")
    print("cache_resumos.guardar(dia, itens) com o campo `resumo` preenchido.")
    return saida


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else date.today().strftime("%d/%m/%Y"))
