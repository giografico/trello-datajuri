#!/usr/bin/env python3
"""
Conector da plataforma processual — leitura do recorte de intimações de
terceiros.

Uso:
    python3 cliente_plataforma.py diagnostico    # testa credenciais e mapeia a API
    python3 cliente_plataforma.py recorte        # baixa o recorte de intimações

Credenciais em .config-plataforma.json (mesmo diretório):
    {"client_id": "", "client_secret": "", "username": "", "password": ""}

Somente leitura. Nenhuma operação de escrita — a plataforma processual usada
neste projeto não possui API de escrita.

Nota sobre o fornecedor: este módulo é genérico de propósito. A plataforma
real usada em produção tem uma API própria (autenticação OAuth client
credentials + password, paginação por página/tamanho de página, limite
diário de requisições por escritório); o shape abaixo reflete isso sem
amarrar o código a um fornecedor nomeado.
"""
import json, sys, base64, urllib.request, urllib.parse, urllib.error, ssl, os

HOST = "https://api.plataforma-processual.exemplo.com.br"
from config import CONFIG_PLATAFORMA as CFG
CTX = ssl.create_default_context()
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    pass


def carrega_config():
    if not os.path.exists(CFG):
        sys.exit(f"ERRO: {CFG} nao encontrado.\n"
                 'Crie com: {"client_id":"","client_secret":"","username":"","password":""}')
    c = json.load(open(CFG))
    faltando = [k for k in ("client_id", "client_secret", "username", "password")
                if not c.get(k) or c[k].startswith("COLE_")]
    if faltando:
        sys.exit(f"ERRO: preencha em .config-plataforma.json: {', '.join(faltando)}")
    return c


def autentica(cfg, separador):
    """Fornecedores diferentes de API OAuth client-credentials usam
    separadores diferentes entre client_id e client_secret no Basic Auth.
    Testamos os dois para não depender de qual implementação está do
    outro lado."""
    basic = base64.b64encode(
        f"{cfg['client_id']}{separador}{cfg['client_secret']}".encode()
    ).decode()
    corpo = urllib.parse.urlencode({
        "grant_type": "password",
        "username": cfg["username"],
        "password": cfg["password"],
    }).encode()
    req = urllib.request.Request(
        f"{HOST}/oauth/token", data=corpo,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        return json.load(r)


def conecta(cfg, verboso=True):
    ultimo_erro = None
    for sep in (":", "@"):
        try:
            tk = autentica(cfg, sep)
            if verboso:
                print(f"  autenticado (separador '{sep}')")
                if "expires_in" in tk:
                    h = tk["expires_in"] / 3600
                    print(f"  token expira em {tk['expires_in']}s (~{h:.1f}h)")
                else:
                    print("  ATENCAO: resposta sem 'expires_in' — validade desconhecida")
                print(f"  refresh_token: {'sim' if tk.get('refresh_token') else 'NAO'}")
            return tk["access_token"]
        except urllib.error.HTTPError as e:
            ultimo_erro = f"HTTP {e.code} com separador '{sep}'"
        except Exception as e:
            ultimo_erro = f"{type(e).__name__}: {e}"
    sys.exit(f"ERRO de autenticacao. Ultimo: {ultimo_erro}\n"
             "Verifique client_id, client_secret, usuario e senha com o Administrador.")


def get(token, caminho, params=None):
    url = f"{HOST}{caminho}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        corpo = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"HTTP {e.code} em {caminho} — {corpo or '(corpo vazio)'}")


def diagnostico():
    cfg = carrega_config()
    print("=== 1. AUTENTICACAO ===")
    token = conecta(cfg)

    print("\n=== 2. MODULOS DISPONIVEIS ===")
    try:
        mods = get(token, "/v1/modulos")
        print(f"  {len(mods)} modulos")
        for m in mods:
            nome = m.get("nome", m) if isinstance(m, dict) else m
            if "ecorte" in str(nome) or "rocesso" in str(nome):
                print(f"    -> {nome}")
    except Exception as e:
        print(f"  FALHOU: {e}")

    print("\n=== 3. CAMPOS DO RECORTE DE INTIMAÇÕES ===")
    print("  (responde: existe campo de movimento? de lido? qual traz a publicacao?)")
    try:
        campos = get(token, "/v1/campos/RecorteIntimacoes")
        print(f"  {len(campos)} campos:")
        for c in campos:
            nome = c.get("nome", "?") if isinstance(c, dict) else str(c)
            rot = c.get("rotulo", "") if isinstance(c, dict) else ""
            print(f"    {nome:42s} {rot}")
        json.dump(campos, open("campos_recorteconsulta.json", "w"),
                  ensure_ascii=False, indent=2)
        print("  -> salvo em campos_recorteconsulta.json")
    except Exception as e:
        print(f"  FALHOU: {e}")

    print("\n=== 4. TOTAL DE REGISTROS ===")
    try:
        print(f"  {get(token, '/v1/entidades/total/RecorteIntimacoes')}")
    except Exception as e:
        print(f"  FALHOU: {e}")

    print("\n=== 5. AMOSTRA (2 registros, campos crus) ===")
    try:
        d = get(token, "/v1/entidades/RecorteIntimacoes", {"pageSize": 2, "page": 1})
        print(f"  listSize={d.get('listSize')}")
        for row in d.get("rows", [])[:2]:
            print("  ---")
            for k, v in row.items():
                print(f"    {k}: {str(v)[:90]}")
    except Exception as e:
        print(f"  FALHOU: {e}")


def recorte(dias=7, page_size=100):
    """Baixa o recorte de intimações. Filtro de fonte e dedup por
    movimento+processo sao aplicados na etapa de analise, nao aqui — a
    segunda fonte precisa vir junto para a checagem cruzada."""
    cfg = carrega_config()
    token = conecta(cfg, verboso=False)
    todos, page = [], 1
    while True:
        d = get(token, "/v1/entidades/RecorteIntimacoes",
                {"page": page, "pageSize": page_size, "removerHtml": "true"})
        linhas = d.get("rows", [])
        todos.extend(linhas)
        total = d.get("listSize", 0)
        print(f"  pagina {page}: {len(linhas)} registros (acumulado {len(todos)}/{total})")
        if len(linhas) < page_size or len(todos) >= total:
            break
        page += 1
        if page > 50:
            print("  AVISO: parou em 50 paginas por seguranca")
            break
    saida = "recorte_bruto.json"
    json.dump(todos, open(saida, "w"), ensure_ascii=False, indent=2)
    print(f"\n  {len(todos)} registros -> {saida}")
    print("  ATENCAO: contem dados de cliente. Nao versionar, nao compartilhar.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "diagnostico"
    if cmd == "diagnostico":
        diagnostico()
    elif cmd == "recorte":
        recorte()
    else:
        sys.exit(__doc__)
