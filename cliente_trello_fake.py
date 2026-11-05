#!/usr/bin/env python3
"""
Trello FALSO, para o modo demonstração — grava os cartões num arquivo JSON
local em vez de chamar a API de verdade.

Implementa a mesma função `trello(path, metodo, json_body=None, **q)` de
`duplica_cartao.py`, com a MESMA assinatura — por isso `demo.py` consegue
trocar uma pela outra sem mexer em `cartao.py`, `duplica_cartao.py`,
`pipeline.py` nem `rotina.py`: todo o resto do projeto continua achando que
está falando com o Trello de verdade.

Guardado em `trabalho/demo_trello.json` (já no .gitignore). Apagar o arquivo
reinicia o quadro de demonstração do zero.
"""
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone

from config import TRABALHO, garante_trabalho
from duplica_cartao import TESTE, LISTA, CF_PRAZO_FATAL
from cartao import _ETIQUETAS

ARQUIVO = os.path.join(TRABALHO, "demo_trello.json")


def _novo_id():
    """24 hex chars, os 8 primeiros são o timestamp — mesmo formato de um id
    real do Trello (duplica_cartao.tocado_por_humano depende disso)."""
    return f"{int(time.time()):08x}{uuid.uuid4().hex[:16]}"


def _agora_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _estado_vazio():
    nomes_etiqueta = sorted({nome for _, nome in _ETIQUETAS})
    return {
        "board": {"id": TESTE, "name": "Quadro de demonstração (fictício)",
                  "closed": False},
        "lists": [{"id": LISTA, "name": "CLAUDE — P/ CONFERÊNCIA (demo)"}],
        "labels": [{"id": f"label-{i}", "name": n}
                   for i, n in enumerate(nomes_etiqueta)],
        "customFields": [{"id": CF_PRAZO_FATAL, "name": "Prazo Fatal"}],
        "cards": [],
    }


def _carrega():
    garante_trabalho()
    if not os.path.exists(ARQUIVO):
        return _estado_vazio()
    try:
        with open(ARQUIVO) as f:
            return json.load(f)
    except (OSError, ValueError):
        return _estado_vazio()


def _salva(db):
    with open(ARQUIVO, "w") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def reiniciar():
    """Apaga o quadro de demonstração e recomeça do zero."""
    db = _estado_vazio()
    _salva(db)
    return db


def _card_publico(c):
    """Só os campos que o código real espera encontrar num cartão."""
    pub = {k: v for k, v in c.items() if not k.startswith("_")}
    if c.get("_custom_fields"):
        pub["customFieldItems"] = [
            {"idCustomField": fid, "value": v}
            for fid, v in c["_custom_fields"].items()]
    return pub


def trello(path, metodo="GET", json_body=None, **q):
    db = _carrega()

    m = re.fullmatch(r"/boards/([^/]+)", path)
    if m:
        return dict(db["board"])

    if re.fullmatch(r"/boards/[^/]+/cards", path):
        return [_card_publico(c) for c in db["cards"]]

    if re.fullmatch(r"/boards/[^/]+/lists", path):
        return list(db["lists"])

    if re.fullmatch(r"/boards/[^/]+/labels", path):
        return list(db["labels"])

    if re.fullmatch(r"/boards/[^/]+/customFields", path):
        return list(db["customFields"])

    if path == "/cards" and metodo == "POST":
        cid = _novo_id()
        novo = {
            "id": cid, "shortUrl": f"https://trello.com/c/demo{cid[-8:]}",
            "name": q.get("name", ""), "desc": q.get("desc", ""),
            "idList": q.get("idList", LISTA),
            # o Trello recebe "true"/"false" como string no formulário, mas
            # devolve booleano de verdade na API — sem essa conversão, a
            # string "false" é VERDADEIRA em Python, e todo cartão nasceria
            # acusado de "concluído por engano" (foi exatamente isso: achei
            # rodando o primeiro teste do modo demo).
            "due": q.get("due"), "dueComplete": q.get("dueComplete") == "true",
            "idLabels": [l for l in (q.get("idLabels") or "").split(",") if l],
            "idMembers": [], "_comments": [], "_custom_fields": {},
        }
        db["cards"].insert(0, novo)
        _salva(db)
        return _card_publico(novo)

    m = re.fullmatch(r"/cards/([^/]+)", path)
    if m and metodo == "GET":
        for c in db["cards"]:
            if c["id"] == m.group(1):
                return _card_publico(c)
        return {}
    if m and metodo == "PUT":
        for c in db["cards"]:
            if c["id"] == m.group(1):
                for campo in ("dueComplete", "idLabels", "due", "name", "desc"):
                    if campo in q:
                        v = q[campo]
                        if campo == "idLabels":
                            v = v.split(",") if v else []
                        elif campo == "dueComplete":
                            v = v == "true"
                        c[campo] = v
                _salva(db)
                return _card_publico(c)
        return {}

    m = re.fullmatch(r"/cards/([^/]+)/members", path)
    if m:
        return []   # nunca atribuímos membro — não há o que listar

    m = re.fullmatch(r"/cards/([^/]+)/idMembers/([^/]+)", path)
    if m and metodo == "DELETE":
        return {}   # nada a remover no modo demo

    m = re.fullmatch(r"/cards/([^/]+)/actions/comments", path)
    if m and metodo == "POST":
        for c in db["cards"]:
            if c["id"] == m.group(1):
                c["_comments"].append({"id": _novo_id(), "date": _agora_iso(),
                                       "data": {"text": q.get("text", "")}})
                _salva(db)
        return {}

    m = re.fullmatch(r"/cards/([^/]+)/actions", path)
    if m and metodo == "GET":
        for c in db["cards"]:
            if c["id"] == m.group(1):
                return [{"type": "commentCard", "date": com["date"],
                        "data": com["data"]} for com in c["_comments"]]
        return []

    m = re.fullmatch(r"/cards/([^/]+)/customField/([^/]+)/item", path)
    if m and metodo == "PUT":
        for c in db["cards"]:
            if c["id"] == m.group(1):
                c["_custom_fields"][m.group(2)] = (json_body or {}).get("value", {})
                _salva(db)
        return {}

    raise RuntimeError(f"cliente_trello_fake: rota não implementada: {metodo} {path}")
