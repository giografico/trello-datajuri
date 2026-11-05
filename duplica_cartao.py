#!/usr/bin/env python3
"""
Cria cartao de prazo DUPLICANDO o ultimo cartao do mesmo processo.

Por que duplicar em vez de montar do zero (descoberto em 14/09/2026):
o link da pasta no Drive, o caminho H:\\, os contatos do cliente e a origem
do sistema NAO existem no DataJuri — eles viajam de cartao em cartao desde
o primeiro do processo. Montar do zero perde tudo isso. Duplicando, o que e
permanente do caso vem junto e so o conteudo da intimacao e reescrito.

Ao duplicar, a controladoria apaga manualmente o que nao deve viajar. O mesmo aqui:
  - etiqueta de executor (EXEC. *) e URGENTE  -> removidas
  - membros atribuidos                        -> removidos
  - vencimento antigo                         -> substituido
  - resumo da decisao anterior                -> substituido pelo novo
Preservados: cabecalho do sistema, LINK DOS DOCUMENTOS / LINK DA PASTA,
caminho H:\\, CONTATOS CLIENTE.

PADRAO DE TITULO EM CONSOLIDACAO (medido em 4 de 4 cartoes da controladoria, 09/09/2026):
quando dois lancamentos do mesmo movimento viram um cartao (ED + recurso), a
acao no titulo e' escrita como "Verificar eventual providência / ED / recurso".
"""
import json, re, ssl, urllib.request, urllib.parse
from datetime import datetime, timezone

from config import CONFIG_TRELLO as TRELLO_CFG, ids_trello

# IDs do quadro de teste, da lista de cartões e do campo "Prazo Fatal", lidos
# do arquivo de configuração — não embutidos no código (ver config.py). Sem
# config (rodando só os testes, que não acessam rede), vêm como placeholders.
TESTE, LISTA, CF_PRAZO_FATAL = ids_trello()   # LISTA: lista de cartões para conferência

CTX = ssl.create_default_context()
try:
    import certifi; CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    pass

# Onde o conteudo da decisao ANTERIOR comeca — tudo daqui ate o bloco
# permanente e' descartado.
INICIO_CONTEUDO = re.compile(
    r'^.{0,40}?\**\s*(resumo\s+d[ao]\s+(decis[ãa]o|intima[çc][ãa]o)|'
    r'conte[úu]do\s+d[ao]\s+decis[ãa]o|conte[úu]do)\s*:?\**\s*$', re.I | re.M)
# Blocos que sempre ficam.
# O marcador pode vir enfeitado: "### :link: **LINK DOS DOCUMENTOS:**".
# Sem aceitar prefixo, o fatiador nao achava nada e herdava a descricao
# inteira — inclusive o resumo da decisao ANTERIOR (visto em 14/09/2026,
# cartoes de 9.000 caracteres com dois resumos).
INICIO_PERMANENTE = re.compile(
    r'^.{0,40}?(LINK\s+D[OA]S?\s+(DOCUMENTOS|PASTA)|CONTATOS?\s+CLIENTE)\s*:?\**',
    re.I | re.M)


def trello(path, metodo="GET", json_body=None, **q):
    """POST/PUT mandam os campos no CORPO. Na query string, uma descricao de
    alguns milhares de caracteres estoura o limite da URI (HTTP 414).

    `json_body`: só o endpoint de campo personalizado precisa de corpo JSON
    aninhado ({"value": {"date": ...}}) em vez de form-urlencoded — os dois
    PUTs de customField (aqui e em cartao.py) passam por aqui agora, em vez
    de montar a chamada HTTP na mão, para ganhar o mesmo retry de rede."""
    cfg = json.load(open(TRELLO_CFG))
    auth = {"key": cfg["key"], "token": cfg["token"]}
    if metodo == "GET":
        url = f"https://api.trello.com/1{path}?" + urllib.parse.urlencode({**q, **auth})
        req = urllib.request.Request(url)
    elif json_body is not None:
        url = f"https://api.trello.com/1{path}?" + urllib.parse.urlencode(auth)
        req = urllib.request.Request(
            url, data=json.dumps(json_body).encode(), method=metodo,
            headers={"Content-Type": "application/json"})
    else:
        url = f"https://api.trello.com/1{path}?" + urllib.parse.urlencode(auth)
        req = urllib.request.Request(
            url, data=urllib.parse.urlencode(q).encode(), method=metodo,
            headers={"Content-Type": "application/x-www-form-urlencoded"})
    # Tentar de novo quando a rede falha. Em 16/10/2026 um timeout nesta
    # funcao derrubou o processo do dia inteiro as 17h40 — a chamada de
    # duplicata percorre 3.535 cartoes, e uma leitura lenta bastou.
    # Espera crescente: 2s, 6s, 18s. Sem isto, uma oscilacao de rede de
    # segundos custa as horas restantes do expediente.
    import time as _t
    ultimo = None
    for tentativa in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
                corpo = r.read().decode()
                return json.loads(corpo) if corpo.strip() else {}
        except urllib.error.HTTPError:
            raise                      # 4xx/5xx e' resposta, nao falha de rede
        except Exception as e:
            ultimo = e
            if tentativa < 3:
                _t.sleep(2 * 3 ** tentativa)
    raise ultimo


def fatia(desc):
    """Separa a descricao herdada em (cabecalho, permanentes)."""
    m_cont = INICIO_CONTEUDO.search(desc or "")
    m_perm = INICIO_PERMANENTE.search(desc or "")
    cabecalho = (desc[:m_cont.start()] if m_cont else
                 (desc[:m_perm.start()] if m_perm else desc or "")).rstrip()
    permanentes = desc[m_perm.start():].rstrip() if m_perm else ""
    return cabecalho, permanentes


def monta_desc(desc_fonte, conteudo, rodape):
    cab, perm = fatia(desc_fonte)
    partes = [p for p in (cab, conteudo, perm, rodape) if p and p.strip()]
    return "\n\n".join(partes)


# Assinaturas dos cartoes que EU criei. Duplicar um deles herda o defeito em
# vez do bom — aconteceu em 14/09/2026: pegou meu proprio cartao como fonte,
# herdou o teor bruto com CPF e perdeu o link da pasta.
MINHA_ASSINATURA = ("gerado automaticamente", "Cartão duplicado do último",
                    "cartão de prazo gerado", "Cartão criado a partir do lançamento")


def meu_cartao(c):
    d = c.get("desc") or ""
    return (c.get("idList") == LISTA) or any(a in d for a in MINHA_ASSINATURA)


def cartao_fonte(processo, excluir_ids=()):
    """Ultimo cartao HUMANO do processo no quadro de teste.

    Ignora os cartoes da automacao — a fonte tem de ser trabalho da equipe,
    senao o defeito se propaga de duplicata em duplicata."""
    cards = trello(f"/boards/{TESTE}/cards",
                   fields="name,desc,idLabels,idMembers,idList")
    do_proc = [c for c in cards
               if processo in c["name"] and c["id"] not in excluir_ids
               and not meu_cartao(c)]
    if not do_proc:
        return None
    return max(do_proc, key=lambda c: int(c["id"][:8], 16))


# Siglas de TIPO de atividade. O cartao novo e' PRZ; herdar o tipo do cartao
# anterior deixa um cartao de prazo marcado como PROV ou DIL (visto em 5 de
# 17 cartoes, 14/09/2026).
TIPOS = ("PRZ", "PROV", "PAT", "DIL", "AUD", "VRF", "PER", "NEG", "NOT", "AÇÃO", "ACAO")

# Campo "Data Revisao" do quadro NAO e' usado pela equipe: 0 de 15 cartoes dela
# tinham o campo preenchido (medido em 14/09/2026). Preencher so' polui.
# Preencher apenas "Prazo Fatal".

# Atribuir membro e etiqueta EXEC.* e' tarefa da Controladoria — decisao da
# usuaria em 14/09/2026 — ainda que a plataforma processual traga o
# responsavel do lancamento.
# Ela atribui em 15/15 cartoes; nos nao atribuimos em nenhum, de proposito.


def etiquetas_limpas(fonte_labels, sigla_nova="PRZ"):
    """Mantem as de assunto (DEFESA, HONORARIOS...). Remove:
    - EXEC.* e urgencia  -> decisao humana
    - tipo de atividade  -> vem do cartao novo, nao do antigo"""
    nomes = {l["id"]: (l.get("name") or "") for l in trello(f"/boards/{TESTE}/labels", fields="name")}
    manter = []
    for lid in fonte_labels:
        n = nomes.get(lid, "").upper()
        if n.startswith("EXEC.") or n in ("URGENTE", "24 HORAS", "IMPULSIONAR", "BLOQUEIO"):
            continue
        if any(n.startswith(t) for t in TIPOS):
            continue
        if n:
            manter.append(lid)
    # a etiqueta de tipo do cartao NOVO
    for l in trello(f"/boards/{TESTE}/labels", fields="name"):
        if (l.get("name") or "").upper().startswith(sigla_nova):
            manter.append(l["id"])
            break
    return manter


def cria(processo, nome, conteudo, due, prazo_fatal_iso, rodape="", excluir_ids=()):
    fonte = cartao_fonte(processo, excluir_ids)
    if not fonte:
        return None, "sem cartão anterior deste processo — criar do zero"
    desc = monta_desc(fonte.get("desc") or "", conteudo, rodape)
    novo = trello("/cards", "POST",
                  idList=LISTA, idCardSource=fonte["id"],
                  keepFromSource="none",          # nada de labels/members/due/anexos
                  name=nome, desc=desc, due=due,
                  # O Trello copia o dueComplete do cartao-fonte mesmo com
                  # keepFromSource="none". Como a fonte costuma ser um cartao
                  # antigo ja' em FEITO!, o cartao NOVO nascia marcado como
                  # concluido — 122 de 240 cartoes (51%), detectado em
                  # 15/09/2026. Cartao de prazo que nasce feito ninguem
                  # trabalha. Forcar false SEMPRE.
                  dueComplete="false",
                  idLabels=",".join(etiquetas_limpas(fonte.get("idLabels", []))),
                  pos="top")
    # garantia: se algo veio junto, limpar explicitamente
    for m in trello(f"/cards/{novo['id']}/members", fields="id"):
        trello(f"/cards/{novo['id']}/idMembers/{m['id']}", "DELETE")
    if prazo_fatal_iso:
        trello(f"/cards/{novo['id']}/customField/{CF_PRAZO_FATAL}/item", "PUT",
               json_body={"value": {"date": prazo_fatal_iso}})
    return novo, fonte


_CACHE_CARTOES = {"quando": 0.0, "dados": None}


def cartoes_do_quadro(forcar=False):
    """Lista de cartoes do quadro, com cache curto.

    Sao 3.535 cartoes. `ja_criei` e' chamado uma vez por cartao do lote, e sem
    cache um lote de 6 baixava a lista 6 vezes — alguns megabytes cada. Foi
    uma dessas leituras que estourou o tempo em 16/10/2026 e derrubou o
    processo do dia.

    Validade de 60s: curto o bastante para nao perder um cartao criado agora
    por outra via, longo o bastante para cobrir um lote inteiro.
    """
    import time as _t
    if (not forcar and _CACHE_CARTOES["dados"] is not None
            and _t.time() - _CACHE_CARTOES["quando"] < 60):
        return _CACHE_CARTOES["dados"]
    dados = trello(f"/boards/{TESTE}/cards", fields="name,idList,shortUrl,desc")
    _CACHE_CARTOES.update(quando=_t.time(), dados=dados)
    return dados


def registrar_novo(cartao):
    """Acrescenta ao cache um cartao recem-criado.

    SEM ISTO O CACHE VIRA UMA JANELA DE DUPLICACAO. Visto em 19/10/2026:
    dois cartoes identicos nasceram com 56 segundos de diferenca — dentro da
    validade de 60s do cache. Quando o segundo foi verificado, `ja_criei`
    consultou uma lista anterior a' existencia do primeiro, e deixou passar.

    O cache foi introduzido no dia anterior para resolver um timeout. Resolveu
    — e abriu este buraco. Toda criacao precisa alimentar o cache na hora.
    """
    if _CACHE_CARTOES["dados"] is not None and cartao:
        _CACHE_CARTOES["dados"] = list(_CACHE_CARTOES["dados"]) + [{
            "name": cartao.get("name", ""),
            "idList": cartao.get("idList", ""),
            "shortUrl": cartao.get("shortUrl", ""),
            "desc": cartao.get("desc", "")}]


def ja_criei(nome, processo=None):
    """Ja existe cartao meu para este MESMO lancamento?

    Sem isto, rodar duas vezes sobre o mesmo dia cria duplicata — o erro que
    afundou as duas tentativas anteriores de automacao. A comparacao ignora
    pontuacao e espaco, porque o mesmo titulo as vezes volta do DataJuri com
    hifen ou espaco diferente.

    EXIGE O PROCESSO quando o titulo nao traz CNJ. Corrigido em 15/10/2026,
    no primeiro teste de criacao pelo caminho automatico: o lancamento de
    14/10 se chamava apenas

        "Audiência"

    — sem CNJ, sem sigla, sem cliente — e a trava barrou a criacao porque ja'
    havia no quadro um cartao de teste antigo com esse mesmo nome, de outro
    processo. Falso positivo: o lancamento foi descartado em silencio.

    Ha' 8 cartoes de nome curto no quadro ("Novo teste", "ACESSO CORREIOS",
    "Audiência"...), entao a colisao nao e' hipotese remota.

    Regra: titulo que ja' traz CNJ identifica sozinho. Titulo generico so'
    conta como duplicata se o PROCESSO tambem bater — e, sem processo para
    comparar, nao barra: criar um cartao a mais e' visivel e corrigivel;
    descartar um lancamento e' invisivel.
    """
    def dur(x):
        return re.sub(r"[^a-z0-9]", "", (x or "").lower())

    def cnj(x):
        m = re.search(r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}", x or "")
        return re.sub(r"\D", "", m.group(0)) if m else None

    alvo = dur(nome)
    alvo_cnj = cnj(nome)
    generico = alvo_cnj is None and len(alvo) < 30
    proc_alvo = re.sub(r"\D", "", processo or "") or None

    # procurar no QUADRO INTEIRO, nao so' na lista de destino: os primeiros
    # cartoes nasceram em TO DO - SPRINT, antes de a lista propria existir.
    # Olhar so' a lista atual recriaria esses — duplicata silenciosa.
    for c in cartoes_do_quadro():
        if dur(c["name"]) != alvo:
            continue
        if not generico:
            return c
        # titulo generico: so' e' duplicata se o processo bater
        if not proc_alvo:
            continue
        if proc_alvo in re.sub(r"\D", "", (c.get("name") or "") + (c.get("desc") or "")):
            return c
    return None


# ---------------------------------------------------------------------------
# Veio de sincroniza_trello.py em 09/10/2026, quando aquele modulo foi
# removido: de 392 linhas, so' esta e `fora_do_escopo` ainda eram usadas. O
# resto era o fluxo antigo, anterior as travas — inclusive uma criacao de
# cartao que nao passava por pre-voo, sanitizacao nem pos-verificacao.
def tocado_por_humano(card_id):
    """Regra da usuaria (01/09/2026): preencher campo faz parte de CRIAR,
    mesmo com intervalo entre as chamadas. Mas a partir do momento em que
    a controladoria ou qualquer humano altera o cartao, mexer nele passa a ser
    ALTERAR — e alterar e' proibido.

    Só se aplica a RETENTATIVA. No fluxo de criação a checagem é pulada:
    o proprio POST gera um `updateCard` (o Trello registra o `due` assim),
    o que dava falso positivo — visto em 01/09/2026.

    Margem de 120s apos a criacao do cartao: o timestamp de criacao esta
    nos 8 primeiros digitos hex do id.
    """
    # O id do Trello tem 24 digitos hex e carrega o timestamp de criacao nos 8
    # primeiros. O shortLink (o das URLs, "wJggf0T1") NAO serve: nao e' hex, e
    # a conversao estourava no `except` abaixo, devolvendo True — "tocado por
    # humano" — para um cartao recem-criado. Falha segura, mas calada: em
    # 09/10/2026 isso bloqueou a correcao de um cartao que ninguem tinha
    # tocado, e a mensagem dizia o contrario do que havia acontecido.
    if not re.fullmatch(r"[0-9a-f]{24}", (card_id or "").strip()):
        raise ValueError(
            f"id de cartão inválido: {card_id!r}. Esperado o id de 24 dígitos "
            "hex, não o shortLink da URL — buscar com "
            "trello(f'/cards/{shortLink}', fields='id')['id'].")
    try:
        nasceu = int(card_id[:8], 16) + 120
        for a in trello(f"/cards/{card_id}/actions",
                        filter="updateCard,commentCard,addMemberToCard,addAttachmentToCard"):
            # o Trello devolve UTC ("...Z"); sem tzinfo o Python leria como hora
            # local e a acao pareceria 3h no futuro (visto em 01/09/2026)
            quando = datetime.strptime(a["date"][:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc).timestamp()
            if quando > nasceu:
                return True
        return False
    except Exception:
        return True   # na duvida, nao mexe
