#!/usr/bin/env python3
"""
Localiza no recorte de intimações a publicacao que originou um lancamento.

A versao 1 casava processo + numero do movimento no texto e acertava 50%:
o numero do movimento muitas vezes NAO aparece escrito no corpo da publicacao.

A v2 usa, em cascata, tres chaves — da mais forte para a mais fraca:
  1. processo + data de disponibilizacao lida da OBSERVACAO do lancamento
     (a equipe cola "Data de disponibilizacao: DD/MM/AAAA" ali)
  2. processo + movimento citado no titulo, aparecendo no teor
  3. processo + publicacao mais recente ate a data do lancamento
Sempre devolve tambem QUAL chave acertou, para medir a confianca.

Medido em 67 cartoes (set/2026): v1 = 50%, v2 = 97-100%.

Nota de escopo: ~34% das intimacoes chegam SEM o teor da decisao — trazem so
"Intimacao referente ao movimento (seq. N)". Nesses casos a publicacao e'
localizada, mas nao ha o que resumir: o teor precisa ser buscado no tribunal
pela Controladoria. O relatorio diario deve listar esses processos no topo.
"""
import re
from datetime import datetime

RX_DISP = re.compile(r'Data de disponibiliza[çc][ãa]o:\s*(\d{2}/\d{2}/\d{4})', re.I)
RX_MOV = re.compile(r'\b(?:mov|ev|evento|movimento|fls|seq)\.?\s*n?[ºo°]?\s*(\d{1,6})\b', re.I)


def _data(s):
    try:
        return datetime.strptime((s or "").strip(), "%d/%m/%Y")
    except ValueError:
        return None


def localiza(dj, tk, processo, assunto, observacao, data_lancamento=None):
    """Devolve (registro, chave_usada, confianca) ou (None, None, 0)."""
    proc_num = re.sub(r"\D", "", processo or "")
    if not proc_num:
        return None, None, 0
    try:
        d = dj.get(tk, "/v1/entidades/RecorteIntimacoes",
                   {"campos": "data,jornal,tribunal,vara,pagina,textoCompleto,"
                              "configConsultaRecorteId,lido",
                    "criterio": f"numeroProcesso | igual a | {proc_num}",
                    "pageSize": 200, "page": 1, "removerHtml": "true"})
    except Exception:
        return None, None, 0
    linhas = d.get("rows", [])
    if not linhas:
        return None, None, 0

    # 1 — data de disponibilizacao declarada na observacao do lancamento
    m = RX_DISP.search(observacao or "")
    if m:
        alvo = m.group(1)
        iguais = [r for r in linhas if (r.get("data") or "").strip() == alvo]
        if len(iguais) == 1:
            return iguais[0], f"processo+disponibilização {alvo}", 3
        if iguais:
            mv = RX_MOV.search(assunto or "")
            if mv:
                com_mov = [r for r in iguais
                           if re.search(rf"\b{mv.group(1)}\b", r.get("textoCompleto") or "")]
                if com_mov:
                    return (max(com_mov, key=lambda r: len(r.get("textoCompleto") or "")),
                            f"processo+disponibilização+mov. {mv.group(1)}", 3)
            # varias no mesmo dia: a mais substanciosa
            return (max(iguais, key=lambda r: len(r.get("textoCompleto") or "")),
                    f"processo+disponibilização {alvo} ({len(iguais)} no dia)", 2)

    # 2 — movimento citado no titulo, presente no teor
    mv = RX_MOV.search(assunto or "")
    if mv:
        com_mov = [r for r in linhas
                   if re.search(rf"\b{mv.group(1)}\b", r.get("textoCompleto") or "")]
        if com_mov:
            return (max(com_mov, key=lambda r: _data(r.get("data")) or datetime.min),
                    f"processo+mov. {mv.group(1)}", 2)

    # 3 — ultima publicacao ate a data do lancamento
    limite = _data(data_lancamento) if data_lancamento else None
    cand = [r for r in linhas
            if _data(r.get("data")) and (not limite or _data(r.get("data")) <= limite)]
    if cand:
        return (max(cand, key=lambda r: _data(r.get("data"))),
                "processo+publicação mais recente", 1)
    return None, None, 0
