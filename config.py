#!/usr/bin/env python3
"""
Onde ficam as coisas — resolvido em UM lugar, para o codigo rodar em
qualquer maquina.

Por que existe. Ate' certo ponto o projeto so' funcionava na maquina de quem
o escreveu: `cliente_plataforma.py` morava fora do repositorio, as
credenciais eram apontadas por caminho absoluto e o diretorio de trabalho
apontava para uma pasta temporaria de sessao. Clonar o repositorio em outro
lugar e rodar dava:

    ModuleNotFoundError: No module named 'cliente_plataforma'

Tudo aqui tem PADRAO SENSATO e pode ser sobrescrito por variavel de ambiente,
que e' como o servidor vai configurar.

    CJ_CONFIG   onde estao os .config-*.json   (padrao: ao lado do codigo)
    CJ_TRABALHO diretorio de trabalho do dia   (padrao: ./trabalho)

O diretorio de trabalho guarda resumos do dia, que carregam teor de decisao e
nome de cliente. NAO versionar, NAO incluir em backup que saia do escritorio,
e apagar diariamente (cache_resumos.limpar_antigos).
"""
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))

# Credenciais. Procura, nesta ordem: variavel de ambiente, ao lado do codigo.
_CANDIDATOS = [os.environ.get("CJ_CONFIG"), AQUI]


def _acha(nome):
    for base in _CANDIDATOS:
        if base and os.path.exists(os.path.join(base, nome)):
            return os.path.join(base, nome)
    return os.path.join(os.environ.get("CJ_CONFIG") or AQUI, nome)


CONFIG_PLATAFORMA = _acha(".config-plataforma.json")
CONFIG_TRELLO = _acha(".config-trello.json")

# Diretorio de trabalho: resumos do dia, filas, arquivos intermediarios.
TRABALHO = os.environ.get("CJ_TRABALHO") or os.path.join(AQUI, "trabalho")


def garante_trabalho():
    os.makedirs(TRABALHO, exist_ok=True)
    return TRABALHO


def ids_trello():
    """IDs do quadro de teste, lista de cartões e campo "Prazo Fatal", do
    .config-trello.json. Sem config (por exemplo rodando só os testes, que
    não acessam rede), devolve placeholders — o valor exato não importa
    para a suíte de regras, só precisa ser consistente consigo mesmo."""
    try:
        c = json.load(open(CONFIG_TRELLO))
    except (OSError, ValueError):
        c = {}
    return (c.get("quadro_teste") or "QUADRO_NAO_CONFIGURADO",
            c.get("lista_cartoes") or "LISTA_NAO_CONFIGURADA",
            c.get("campo_prazo_fatal") or "CAMPO_NAO_CONFIGURADO")


def diagnostico():
    """O que o pre-voo precisa saber antes de deixar o dia comecar."""
    import shutil
    return {
        "codigo": AQUI,
        "config_plataforma": CONFIG_PLATAFORMA,
        "config_plataforma_existe": os.path.exists(CONFIG_PLATAFORMA),
        "config_trello": CONFIG_TRELLO,
        "config_trello_existe": os.path.exists(CONFIG_TRELLO),
        "trabalho": TRABALHO,
        "trabalho_existe": os.path.isdir(TRABALHO),
        "claude_cli": shutil.which("claude"),
    }


if __name__ == "__main__":
    for k, v in diagnostico().items():
        marca = ""
        if k.endswith("_existe"):
            marca = "  ✓" if v else "  ✗ FALTA"
        print(f"  {k:24s} {v}{marca}")
