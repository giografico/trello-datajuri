#!/usr/bin/env python3
"""
Dashboard de qualidade — lê `historico_execucoes.jsonl` e monta um relatório
HTML autocontido (sem framework, sem rede, um arquivo só).

    python3 dashboard.py

O histórico não vem versionado no repositório (tem dado de caso quando
rodado em produção — ver CLAUDE.md seção 3). Para ter o que mostrar aqui,
rode o modo demonstração algumas vezes, em dias diferentes:

    for d in 01/11/2026 02/11/2026 03/11/2026 04/11/2026 05/11/2026; do
        python3 demo.py $d
    done
    python3 dashboard.py

Gera `dashboard.html` na raiz do projeto (também não versionado — é saída,
não código).
"""
import collections
import html
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(AQUI, "historico_execucoes.jsonl")
SAIDA = os.path.join(AQUI, "dashboard.html")


def _le_historico():
    if not os.path.exists(LOG):
        return []
    execucoes = []
    with open(LOG) as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            try:
                execucoes.append(json.loads(linha))
            except ValueError:
                continue
    return execucoes


def _agrega(execucoes):
    por_dia = collections.OrderedDict()
    problemas = collections.Counter()
    motivos_pulado = collections.Counter()
    total_criados = total_pulados = total_defeituosos = 0
    duracoes = []

    for ex in execucoes:
        dia = (ex.get("quando") or "")[:10]
        d = por_dia.setdefault(dia, {"criados": 0, "defeituosos": 0, "pulados": 0})
        criados = ex.get("criados") or []
        pulados = ex.get("pulados") or []
        defeituosos = ex.get("defeituosos") or []
        d["criados"] += len(criados)
        d["defeituosos"] += len(defeituosos)
        d["pulados"] += len(pulados)
        total_criados += len(criados)
        total_pulados += len(pulados)
        total_defeituosos += len(defeituosos)
        for c in defeituosos:
            for p in c.get("problemas", []):
                problemas[p] += 1
        for p in pulados:
            motivo = (p.get("motivo") or "").split(":")[0]
            motivos_pulado[motivo] += 1
        if "duracao_segundos" in ex:
            duracoes.append(ex["duracao_segundos"])

    taxa_limpo = (1 - total_defeituosos / total_criados) * 100 if total_criados else 100
    media_duracao = sum(duracoes) / len(duracoes) if duracoes else 0

    return {
        "por_dia": por_dia, "problemas": problemas, "motivos_pulado": motivos_pulado,
        "total_criados": total_criados, "total_pulados": total_pulados,
        "total_defeituosos": total_defeituosos, "taxa_limpo": taxa_limpo,
        "media_duracao": media_duracao, "execucoes": len(execucoes),
    }


def _barra(valor, maximo, cor):
    largura = round(valor / maximo * 100) if maximo else 0
    return (f'<div class="trilha"><div class="barra" style="width:{largura}%;'
            f'background:{cor}"></div></div>')


def _html(ag):
    dias = list(ag["por_dia"].items())
    max_dia = max((d["criados"] for _, d in dias), default=1) or 1

    linhas_dias = "\n".join(
        f'<tr><td>{html.escape(dia)}</td><td>{d["criados"]}</td>'
        f'<td>{_barra(d["criados"], max_dia, "#4f8cff")}</td>'
        f'<td>{d["defeituosos"]}</td><td>{d["pulados"]}</td></tr>'
        for dia, d in dias)

    max_prob = max(ag["problemas"].values(), default=1) or 1
    linhas_problemas = "\n".join(
        f'<tr><td>{html.escape(nome)}</td><td>{n}</td>'
        f'<td>{_barra(n, max_prob, "#ff6b6b")}</td></tr>'
        for nome, n in ag["problemas"].most_common()) or \
        '<tr><td colspan="3">nenhuma — todos os cartões saíram limpos</td></tr>'

    linhas_pulados = "\n".join(
        f'<tr><td>{html.escape(nome)}</td><td>{n}</td></tr>'
        for nome, n in ag["motivos_pulado"].most_common()) or \
        '<tr><td colspan="2">nenhum lançamento pulado</td></tr>'

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Dashboard de qualidade</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 900px;
         margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
  h1 {{ font-size: 1.4rem; }}
  .cartoes {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr));
             gap: 1rem; margin: 1.5rem 0; }}
  .cartao {{ border: 1px solid #8884; border-radius: 10px; padding: 1rem; }}
  .cartao .numero {{ font-size: 1.8rem; font-weight: 700; }}
  .cartao .rotulo {{ opacity: .7; font-size: .85rem; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0 2rem; }}
  th, td {{ text-align: left; padding: .4rem .6rem; border-bottom: 1px solid #8883; }}
  .trilha {{ background: #8882; border-radius: 4px; height: 10px; width: 120px; }}
  .barra {{ height: 10px; border-radius: 4px; }}
  footer {{ opacity: .6; font-size: .8rem; margin-top: 2rem; }}
</style>
</head>
<body>
<h1>Dashboard de qualidade — dados do modo demonstração</h1>
<p>Lido de <code>historico_execucoes.jsonl</code>, {ag['execucoes']} execução(ões).</p>

<div class="cartoes">
  <div class="cartao"><div class="numero">{ag['total_criados']}</div>
       <div class="rotulo">cartões criados</div></div>
  <div class="cartao"><div class="numero">{ag['taxa_limpo']:.0f}%</div>
       <div class="rotulo">saíram sem defeito</div></div>
  <div class="cartao"><div class="numero">{ag['total_pulados']}</div>
       <div class="rotulo">lançamentos pulados</div></div>
  <div class="cartao"><div class="numero">{ag['media_duracao']:.2f}s</div>
       <div class="rotulo">duração média por execução</div></div>
</div>

<h2>Cartões por dia</h2>
<table>
  <tr><th>dia</th><th>criados</th><th></th><th>com defeito</th><th>pulados</th></tr>
  {linhas_dias}
</table>

<h2>Problemas encontrados, por tipo</h2>
<table>
  <tr><th>problema</th><th>vezes</th><th></th></tr>
  {linhas_problemas}
</table>

<h2>Lançamentos pulados, por motivo</h2>
<table>
  <tr><th>motivo</th><th>vezes</th></tr>
  {linhas_pulados}
</table>

<footer>Gerado por dashboard.py a partir de dados fictícios do modo demonstração — nenhum dado de caso real.</footer>
</body>
</html>
"""


def main():
    execucoes = _le_historico()
    if not execucoes:
        print(f"Nada em {LOG} ainda.")
        print("Rode o modo demonstração primeiro, em um ou mais dias:")
        print("  python3 demo.py 01/11/2026")
        print("  python3 demo.py 02/11/2026")
        print("  python3 dashboard.py")
        return 1
    ag = _agrega(execucoes)
    with open(SAIDA, "w") as f:
        f.write(_html(ag))
    print(f"{ag['execucoes']} execução(ões) lida(s) · {ag['total_criados']} cartões · "
          f"{ag['taxa_limpo']:.0f}% sem defeito")
    print(f"-> {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
