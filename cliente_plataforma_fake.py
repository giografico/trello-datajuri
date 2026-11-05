#!/usr/bin/env python3
"""
Cliente FALSO da plataforma processual, para o modo demonstração.

Mesma interface de `cliente_plataforma.py` (carrega_config, conecta, get),
para que `rotina.py`, `prepara_manha.py` e `localiza_recorte.py` rodem sem
mudar uma linha — só trocando qual módulo o `demo.py` liga no lugar.

Não acessa rede. Os dados vêm de `gerador_dados_ficticios.py`, carregados
por `definir_dados()` antes de qualquer chamada.
"""

_DADOS = {"lancamentos": [], "recorte": []}


def definir_dados(lancamentos, recorte):
    _DADOS["lancamentos"] = lancamentos
    _DADOS["recorte"] = recorte


def carrega_config():
    return {"client_id": "demo", "client_secret": "demo",
            "username": "demo", "password": "demo"}


def conecta(cfg, verboso=True):
    if verboso:
        print("  autenticado (modo demonstração — sem rede)")
    return "token-demo"


def _criterio(params):
    """Devolve (campo, valor) do criterio 'campo | operador | valor', ou
    (None, None) se não houver."""
    crit = (params or {}).get("criterio")
    if not crit:
        return None, None
    partes = [p.strip() for p in crit.split("|")]
    if len(partes) < 3:
        return None, None
    return partes[0], partes[2]


def get(token, caminho, params=None):
    page = int((params or {}).get("page", 1))
    if page > 1:                      # um só "lote" no modo demo
        return {"rows": [], "listSize": 0}

    if caminho == "/v1/entidades/Atividade":
        campo, valor = _criterio(params)
        linhas = _DADOS["lancamentos"]
        if campo == "dataCadastro" and valor:
            linhas = [r for r in linhas
                      if (r.get("dataCadastro") or "").startswith(valor)]
        return {"rows": linhas, "listSize": len(linhas)}

    if caminho == "/v1/entidades/RecorteIntimacoes":
        campo, valor = _criterio(params)
        linhas = _DADOS["recorte"]
        if campo == "data" and valor:
            linhas = [r for r in linhas if (r.get("data") or "") == valor]
        elif campo == "numeroProcesso" and valor:
            import re as _re
            alvo = _re.sub(r"\D", "", valor)
            linhas = [r for r in linhas
                      if _re.sub(r"\D", "", r.get("numeroProcesso") or "") == alvo]
        return {"rows": linhas, "listSize": len(linhas)}

    return {"rows": [], "listSize": 0}
