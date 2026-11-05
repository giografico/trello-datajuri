#!/usr/bin/env python3
"""
A unica peca que precisa de um modelo: ler a decisao e escrever o resumo.

Por que existe (15/10/2026): ate' hoje este passo era feito POR MIM, numa
sessao de conversa. Isso nunca foi codigo — e, quando o projeto for para o
servidor, nao havera' sessao nenhuma. O programa precisa saber se virar.

Chama o Claude Code em modo nao-interativo (`claude -p`). A conta sai do
assento do Claude Team que o escritorio ja' tem, sem chave de API separada.

REGRA DURA: se o modelo falhar, nao inventa resumo. Devolve None, e quem
chamou decide — a Controladoria prefere um cartao sem resumo a um cartao com
resumo errado.

PROMPT AJUSTADO EM 15/10/2026, depois do primeiro teste com o codigo rodando
sozinho (08/10, 12 cartoes). Tres defeitos medidos ali:

  1. METADE dos cartoes nascia com ⚠️ no topo, e varios avisavam E resumiam
     ao mesmo tempo: "⚠️ o texto nao traz a decisao" seguido de "audiencia
     designada para ...". O aviso virava ruido, e ruido repetido ensina a
     ignorar o aviso — inclusive o verdadeiro.
  2. Uma DATA saiu truncada: "designada para 25/1", quando o prazo fatal era
     25/11/2026. Num cartao de prazo, data pela metade e' pior que data
     nenhuma.
  3. A proibicao de citar o CPC era ampla demais. Ela existe para impedir o
     cartao de afirmar COMO o prazo foi contado (a conta e' da Controladoria,
     nao nossa). Citar o artigo que fundamenta o ato, quando esta' no texto,
     e' informacao legitima.
"""
import json
import os
import re
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request

TIMEOUT = 180        # segundos por chamada
EXECUTAVEL = shutil.which("claude") or "claude"

INSTRUCAO = """Você resume decisões judiciais para a Controladoria Jurídica de
um escritório de advocacia. O resumo vai no topo de um cartão de gestão de
prazos, e quem lê precisa entender em dez segundos o que aconteceu e o que
precisa ser feito.

REGRAS:
- 1 a 3 frases. Direto. Sem preâmbulo, sem "trata-se de".
- Comece pelo ato: o que o juízo decidiu ou determinou.
- Diga o prazo e a providência SE estiverem no texto.
- Use **negrito** no ato principal.
- Datas SEMPRE completas: 25/11/2026, nunca 25/11 nem 25/1.
- Se uma data aparecer INCOMPLETA ou cortada no texto, NÃO a complete e NÃO
  a adivinhe: omita a data e diga o resto. Data errada em cartão de prazo é
  pior que data nenhuma.
- NUNCA diga como o prazo foi contado, nem cite marco inicial ou os artigos
  de contagem (CPC 219, 224, 231). O prazo já vem calculado pela
  Controladoria. Citar o artigo que fundamenta o ato (ex: audiência do
  art. 334) é permitido SE estiver no texto.
- NÃO repita CPF, RG ou dados bancários.
- Se o texto trouxer QUALQUER informação aproveitável — que ato foi
  praticado, data de audiência, do que se trata — resuma essa informação e
  NÃO use ⚠️. Resumo curto é melhor que aviso.
- Use ⚠️ APENAS quando não houver absolutamente nada a resumir: o texto diz
  que existe algo no sistema, sem dizer o quê. Uma linha só.
- Responda APENAS com o resumo. Nada antes, nada depois.

DECISÃO:
"""


# Prompt proprio para AUDIENCIA. Medido em 90 cartoes do quadro oficial: a
# descricao de audiencia e' OPERACIONAL, nao analitica — 98% trazem sistema e
# numero, mas so' 6% trazem alguma exigencia do ato. O titulo do lancamento ja'
# diz o tipo, a data e a hora; repetir isso no resumo e' ruido, e foi onde
# nasceu a data errada de 15/10/2026.
INSTRUCAO_AUDIENCIA = """Você prepara o cartão de uma AUDIÊNCIA para a
Controladoria Jurídica de um escritório de advocacia.

O título do cartão JÁ INFORMA o tipo de audiência, a data e a hora. NÃO repita
nada disso.

Sua tarefa é extrair do texto SOMENTE o que afeta a preparação do ato:
- provas que precisam ser levadas, e até quando
- testemunhas: quantas, se precisam de intimação, como participam
- necessidade de preposto ou carta de preposição
- prazo de contestação ou outra peça vinculado à audiência
- presença obrigatória da parte, consequência da ausência

REGRAS:
- 1 a 3 frases, direto.
- Se o texto NÃO trouxer nenhuma dessas informações, responda exatamente:
  SEM EXIGENCIAS
- Não repita o tipo, a data ou a hora da audiência.
- Datas SEMPRE completas (25/11/2026). Se vier incompleta, omita.
- NÃO repita CPF, RG ou dados bancários.
- Responda APENAS com o texto. Nada antes, nada depois.

TEXTO:
"""


def resumir_audiencia(texto, contexto=""):
    """Exigencias do ato, ou None se nao houver nenhuma.

    Devolve None tambem quando o modelo responde SEM EXIGENCIAS — que e' a
    resposta certa na maioria dos casos: a publicacao de audiencia costuma
    so' dizer "designada, veja no sistema".
    """
    texto = re.sub(r"\s+", " ", texto or "").strip()
    if len(texto) < 80:
        return None
    prompt = (INSTRUCAO_AUDIENCIA + (f"[{(contexto or '')[:400]}]\n\n" if contexto else "")
              + texto[:12000])
    bruto = _pedir(prompt)
    if not bruto:
        return None
    s = re.sub(r"^```[a-z]*\n|\n```$", "", bruto).strip()
    if not s or "SEM EXIGENCIAS" in s.upper() or len(s) < 25:
        return None
    return s[:800]


# ---------------------------------------------------------------------------
# DOIS CAMINHOS PARA O MESMO RESUMO
#
# Ate' 04/11/2026 so' havia o Claude Code. O desenvolvedor que hospeda o
# servidor levantou — com razao — que o Claude Code e' um AGENTE: por padrao
# tem acesso a ler e escrever arquivos e executar comandos no shell. Para uma
# tarefa que e' "entra texto, sai resumo", e' mais ferramenta do que o
# necessario num servidor de producao.
#
# A chamada direta a' API nao instala nada no servidor e nao tem acesso a
# nada: e' uma requisicao HTTP.
#
#     Claude Code   custo zero (assento do Team ja' pago) · agente no servidor
#     API direta    cobranca por token · nada instalado, nenhum acesso
#
# Medido em 04/11: o Claude Code leva ~10s por resumo (4 a 14s), boa parte
# disso subindo o processo Node. A API fica em torno de 3s.
#
# QUAL E' USADO: se houver chave de API configurada, usa a API. Senao, cai no
# Claude Code. Assim da' para trocar sem mexer em codigo.
API_URL = "https://api.anthropic.com/v1/messages"
API_MODELO = "claude-sonnet-5"
API_MAX_TOKENS = 700

_CTX = ssl.create_default_context()
try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    pass


def _chave_api():
    """Chave da Anthropic, ou None se nao estiver configurada."""
    from config import AQUI
    caminho = os.path.join(os.environ.get("CJ_CONFIG") or AQUI,
                           ".config-anthropic.json")
    if os.path.exists(caminho):
        try:
            c = json.load(open(caminho))
            if (c.get("api_key") or "").strip():
                return c["api_key"].strip(), (c.get("modelo") or API_MODELO)
        except (ValueError, OSError):
            pass
    amb = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return (amb, API_MODELO) if amb else (None, None)


def _via_api(prompt, chave, modelo):
    """Resumo pela API da Anthropic. Devolve texto ou None."""
    corpo = json.dumps({
        "model": modelo,
        "max_tokens": API_MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(API_URL, data=corpo, method="POST", headers={
        "x-api-key": chave,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        # nunca repetir a chave em mensagem de erro
        raise RuntimeError(f"API HTTP {e.code}") from None
    except Exception as e:
        raise RuntimeError(type(e).__name__) from None
    partes = [b.get("text", "") for b in d.get("content", [])
              if b.get("type") == "text"]
    return "".join(partes).strip() or None


def _pedir(prompt):
    """Manda o prompt pelo caminho configurado. Devolve texto ou None."""
    chave, modelo = _chave_api()
    if chave:
        try:
            return _via_api(prompt, chave, modelo)
        except RuntimeError:
            return None
    try:
        r = subprocess.run([EXECUTAVEL, "-p", prompt],
                           capture_output=True, text=True, timeout=TIMEOUT)
    except Exception:
        return None
    return (r.stdout or "").strip() if r.returncode == 0 else None


def caminho_em_uso():
    """"api" ou "claude-code" — para o diagnostico do pre-voo."""
    return "api" if _chave_api()[0] else "claude-code"


def disponivel():
    """O executavel existe e responde?"""
    try:
        r = subprocess.run([EXECUTAVEL, "-p", "responda apenas: ok"],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and "ok" in r.stdout.lower()
    except Exception:
        return False


def resumir(texto, contexto=""):
    """Resumo da decisao, ou None se o modelo falhar.

    `contexto` entra como cabecalho (titulo do lancamento, vara). Nunca
    inclua dado pessoal aqui — o que chega ja' passou por sanitiza.py.

    NAO TRUNCAR O CONTEXTO. Em 15/10/2026, a rotina mandava o titulo cortado
    em 90 caracteres e o corte caiu no meio de uma data:

        "...Audiencia de conciliacao virtual designada para dia 25/1"
                                                                  ^ cortado

    O titulo completo dizia 25/11/2026. O modelo, obedecendo a regra de
    "datas sempre completas", devolveu 25/01/2027 — data errada num cartao
    de prazo. O titulo do DataJuri tem no maximo 200 caracteres; cabe
    inteiro, e e' barato demais para arriscar.
    """
    contexto = (contexto or "")[:400]
    texto = re.sub(r"\s+", " ", texto or "").strip()
    if len(texto) < 120:
        return None                      # curto demais para ter decisao dentro
    prompt = INSTRUCAO + (f"[{contexto}]\n\n" if contexto else "") + texto[:12000]
    saida = _pedir(prompt)
    if not saida:
        return None
    # o modelo as vezes devolve cercas de codigo ou preambulo; limpar
    saida = re.sub(r"^```[a-z]*\n|\n```$", "", saida).strip()
    if not saida or len(saida) < 40:
        return None
    if len(saida) > 1200:                # resumo nao e' transcricao
        saida = saida[:1200].rsplit(".", 1)[0] + "."
    return saida


if __name__ == "__main__":
    print("executável:", EXECUTAVEL)
    print("disponível:", disponivel())
