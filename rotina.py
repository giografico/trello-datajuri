#!/usr/bin/env python3
"""
O PROGRAMA DO DIA — o que o servidor executa, sem ninguém por perto.

    python3 rotina.py manha      [DD/MM/AAAA]
    python3 rotina.py lancamentos [DD/MM/AAAA] [--criar]
    python3 rotina.py noite      [DD/MM/AAAA]
    python3 rotina.py dia        [DD/MM/AAAA] [--criar]     (os três em ordem)

Por que existe (15/10/2026). Até hoje as peças do projeto funcionavam, mas
quem as amarrava era uma pessoa, digitando no terminal a cada teste. Isso
nunca foi código. Os defeitos de 09 e 15/10 nasceram todos aí: campos não
pedidos na consulta, prazo fatal do item errado, texto afirmando contagem que
não foi feita. Nenhuma trava pegou, porque não havia código para travar.

No servidor não há ninguém digitando. Este arquivo é o que falta.

O QUE ELE NÃO FAZ, de propósito:
  - não decide para qual quadro vai o cartão (a sigla decide)
  - não calcula prazo fatal (vem do lançamento; aqui só fatal−1 e fatal−2)
  - não decide quantos prazos uma decisão gera, nem quem executa ou revisa
  - não escreve nada na plataforma processual
  - não toca em cartão que um humano já tocou
"""
import argparse
import time
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import janela
import cache_resumos
import cliente_plataforma as dj
import duplica_cartao as dc
import modelo
import audiencia
import prepara_manha
import teor as teor_mod
from cartao import fora_de_escopo, sem_prefixo
from consolida import (CAMPOS_NECESSARIOS as CAMPOS_CONSOLIDA, agrupa, eh_prz,
                       fatal_do_grupo, folga_dias_uteis, movimentos_do_grupo)
from localiza_recorte import localiza
from pipeline import executar
from prazo_util import bloco_prazo
from rodape import CAMPOS_NECESSARIOS as CAMPOS_RODAPE, comentario
from sanitiza import sanitizar

RXCNJ = re.compile(r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}")
CAMPOS = ",".join(sorted(set(CAMPOS_CONSOLIDA) | set(CAMPOS_RODAPE)
                         | set(teor_mod.CAMPOS_NECESSARIOS) | {
    "assunto", "dataCadastro", "observacao",
    "processo.cliente.nome", "processo.adverso.nome"}))


def _log(etapa, msg):
    print(f"[{datetime.now():%H:%M:%S}] {etapa:12s} {msg}", flush=True)


def _cnj(s):
    m = RXCNJ.search(s or "")
    return re.sub(r"\D", "", m.group(0)) if m else None


def _lancamentos(tk, dia):
    todos, page = [], 1
    while True:
        d = dj.get(tk, "/v1/entidades/Atividade",
                   {"campos": CAMPOS, "criterio": f"dataCadastro | igual a | {dia}",
                    "page": page, "pageSize": 100, "removerHtml": "true"})
        linhas = d.get("rows", [])
        todos += linhas
        if len(linhas) < 100 or len(todos) >= d.get("listSize", 0):
            break
        page += 1
    return todos


# --------------------------------------------------------------------- manhã
def manha(dia, tk):
    """Lê o recorte, junta as fontes e adianta os resumos que der."""
    _log("manhã", f"recorte de {dia}")
    cache_resumos.limpar_antigos()
    saida = prepara_manha.main(dia)
    prontas = saida["para_resumir"]
    _log("manhã", f"{saida['totais']['unicas']} intimações · "
                  f"{len(prontas)} com teor · "
                  f"{saida['totais'].get('repetidas', 0)} repetidas de dia anterior")
    if not modelo.disponivel():
        _log("manhã", "⚠️ MODELO INDISPONÍVEL — nenhum resumo adiantado hoje")
        return {"resumidas": 0, "falhas": len(prontas), "intimacoes": saida}
    feitos, falhas = [], 0
    for i, it in enumerate(prontas, 1):
        texto, _ = sanitizar(it.get("texto") or "")
        r = modelo.resumir(texto, contexto=f"processo {it.get('processo_fmt')}")
        if r:
            it["resumo"] = r
            feitos.append(it)
        else:
            falhas += 1
        if i % 5 == 0 or i == len(prontas):
            _log("manhã", f"resumidos {len(feitos)}/{i}")
    if feitos:
        cache_resumos.guardar(dia, feitos)
    _log("manhã", f"cache: {len(feitos)} resumos · {falhas} falharam")
    return {"resumidas": len(feitos), "falhas": falhas, "intimacoes": saida}


# ---------------------------------------------------------------- lançamentos
def lancamentos(dia, tk, criar=False):
    """Monta os cartões dos lançamentos do dia. Sem criar, só relata."""
    brutos = _lancamentos(tk, dia)
    escopo, fora = [], {}
    for r in brutos:
        m = fora_de_escopo(r.get("assunto"))
        if m:
            fora[m] = fora.get(m, 0) + 1
        else:
            escopo.append(r)
    _log("lançamentos", f"{len(brutos)} lançados · {len(escopo)} em escopo")
    grupos = agrupa(escopo)
    _log("lançamentos", f"{len(escopo)} lançamentos → {len(grupos)} cartões")

    itens, sem_resumo, sem_publicacao, usou_observacao = [], 0, 0, 0
    for g in grupos:
        r0 = g[0]
        assunto = r0.get("assunto") or ""
        proc = r0.get("processo.pasta") or (_cnj(assunto) and RXCNJ.search(assunto).group(0))
        fatal, outros = fatal_do_grupo(g)
        rec = chave = None
        if proc:
            rec, chave, _ = localiza(dj, tk, proc, assunto,
                                     r0.get("observacao"), r0.get("dataCadastro"))
        if not rec:
            sem_publicacao += 1
        # De onde vem o teor: regra oficial de 24/09/2026, em teor.py
        bruto, origem_teor = teor_mod.escolher(
            (rec or {}).get("textoCompleto"), r0.get("observacao"))
        if origem_teor == "observacao":
            usou_observacao += 1
        teor, _ = sanitizar(bruto)
        mv = (movimentos_do_grupo(g) or [None])[0] if len(g) > 1 else None
        if audiencia.eh_audiencia(sem_prefixo(assunto)):
            # Audiencia nao tem decisao a resumir: o titulo ja' diz tipo, data
            # e hora. O que importa e' o que afeta a PREPARACAO do ato, e o
            # que o cartao nao pode trazer (chave e link so' existem no
            # sistema do tribunal). Ver audiencia.py.
            corpo, do_cache = [], None
            exig = modelo.resumir_audiencia(teor, contexto=sem_prefixo(assunto))
            if exig:
                corpo.append(exig)
            falta = audiencia.falta_completar(sem_prefixo(assunto))
            if falta:
                corpo.append(falta)

            if not exig:
                sem_resumo += 1
        else:
            resumo, do_cache = cache_resumos.buscar(
                _cnj(assunto), mv, (rec or {}).get("data"), dia)
            if not resumo:
                resumo = modelo.resumir(teor, contexto=sem_prefixo(assunto))
            if not resumo:
                sem_resumo += 1
                resumo = ("⚠️ **Resumo não gerado.** Conferir a decisão no "
                          "DataJuri ou no sistema do tribunal.")
            corpo = [resumo]
        if outros:
            corpo.append(f"\n⚠️ **Outros prazos fatais deste cartão:** "
                         f"{', '.join(outros)}")
        # O bloco "fatal · fatal −1 · fatal −2" saiu da descrição em
        # 29/10/2026, a pedido da Controladoria: as datas já estão no
        # vencimento do cartão e no campo Prazo Fatal. Repeti-las no texto
        # roubava espaço do que importa, que é a decisão.
        pub = None
        if rec:
            f = (rec.get("configConsultaRecorteId") or "")
            pub = (f"Publicação localizada no recorte de {rec.get('data')} "
                   f"({'AtitudeJur' if f.startswith('Atitude') else 'Alerte'}, "
                   f"chave `{chave}`)")
        itens.append({
            "assunto": assunto, "conteudo": "\n".join(corpo),
            "rodape": "",      # rodapé de origem removido (29/10/2026)
            "comentario_autoria": comentario(
                {"criadoPor.nome": r0.get("criadoPor.nome"),
                 "dataCadastro": r0.get("dataCadastro")}),
            "n_lancamentos": len(g), "prazo_fatal": fatal, "processo": proc,
            "lancamentos": [x.get("assunto") for x in g]})
    _log("lançamentos", f"{sem_publicacao} sem publicação · {sem_resumo} sem resumo"
                        + (f" · {usou_observacao} com teor colado pela equipe"
                           if usou_observacao else ""))
    if not criar:
        _log("lançamentos", "MODO SIMULAÇÃO — nenhum cartão criado")
        return {"cartoes": itens, "fora": fora, "criados": None}
    rel = executar(itens, rotulo=f"rotina {dia}")
    return {"cartoes": itens, "fora": fora, "criados": rel}


# --------------------------------------------------------------------- noite
def noite(dia, tk):
    """As tres conferencias. Falam por excecao: dia limpo nao produz nada.

    Corrigidas em 15/10/2026, no primeiro teste delas:

    1. FONTE UNICA dava 15 avisos num dia, quando a medicao de 25 dias uteis
       apontava ~0,9/dia. Todos eram "so' pelo AtitudeJur" — e o motivo ja'
       era conhecido: o Alerte entrega a MESMA intimacao no dia seguinte.
       Olhar so' o recorte do proprio dia acusa o Alerte de nao ter trazido
       algo que ele ainda vai trazer. Agora espera DIAS_ESPERA_ALERTE.

    3. LANCADO SEM CARTAO comparava TITULO, e dava falso positivo em cartao
       consolidado: quando dois lancamentos viram um cartao, `agrupa` e
       `titulo_consolidado` reescrevem o nome, que deixa de bater com o de
       cada lancamento. Agora compara PROCESSO + MOVIMENTO.
    """
    avisos = []
    DIAS_ESPERA_ALERTE = 2      # dias uteis que o Alerte pode atrasar

    # ------------------------------------------------- 1. uma fonte so' trouxe
    def _chaves(d, so_nao_lidas=False):
        out = {}
        for r0 in prepara_manha.baixar(d):
            # INTIMAÇÃO JÁ LIDA NÃO É PENDÊNCIA. A plataforma marca `lido` no
            # recorte quando a equipe trata o registro. Avisar sobre o que
            # ela já leu é cobrar trabalho feito — e ruído repetido ensina a
            # ignorar o aviso, inclusive o verdadeiro.
            #
            # Medido em 29/10/2026: das 6 intimações que o relatório acusava
            # como "paradas há mais de 3 dias", TODAS as 6 estavam marcadas
            # como lidas. O aviso inteiro era falso positivo.
            if so_nao_lidas and str(r0.get("lido") or "").strip().lower() in ("sim", "true", "1"):
                continue
            texto = r0.get("textoCompleto") or ""
            f = r0.get("configConsultaRecorteId") or ""
            p = prepara_manha.so_digitos(r0.get("numeroProcesso"))
            if not p:
                continue
            k = (p, prepara_manha.movimento(texto),
                 prepara_manha.disponibilizacao(f, r0.get("data"), texto))
            out.setdefault(k, set()).add(
                "AtitudeJur" if f.startswith("Atitude") else "Alerte")
        return out

    porfonte = {}
    d0 = datetime.strptime(dia, "%d/%m/%Y").date()
    d, vistos_dias = d0, 0
    while vistos_dias <= DIAS_ESPERA_ALERTE:
        for k, fontes in _chaves(d.strftime("%d/%m/%Y")).items():
            porfonte.setdefault(k, set()).update(fontes)
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        vistos_dias += 1

    # so' as intimacoes DISPONIBILIZADAS no dia conferido
    do_dia = {k: v for k, v in porfonte.items() if k[2] == dia}
    so_uma = {k: v for k, v in do_dia.items() if len(v) == 1}
    for (p, mv, disp), fontes in so_uma.items():
        avisos.append({"tipo": "fonte única", "processo": p,
                       "detalhe": f"só pelo {list(fontes)[0]} · disp {disp}"
                                  + (f" · mov {mv}" if mv else "")})

    # --------------------------------- 2. chegou e nao virou lancamento
    # A pergunta nao e' "o que chegou HOJE e nao foi lancado" — isso e' so' o
    # dia andando. E' "o que chegou NOS ULTIMOS DIAS e segue sem lancamento".
    # Por isso olha para tras, e cruza com os lancamentos de TODO o periodo.
    DIAS_OLHAR = 8
    recorte_janela = {}
    d = d0
    voltas = 0
    while voltas < DIAS_OLHAR:
        for k, fontes in _chaves(d.strftime("%d/%m/%Y"), so_nao_lidas=True).items():
            recorte_janela.setdefault(k, set()).update(fontes)
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        voltas += 1
    lanc_janela, dd = [], d0
    voltas = 0
    while voltas < DIAS_OLHAR + 3:        # o lancamento pode vir depois
        lanc_janela += _lancamentos(tk, dd.strftime("%d/%m/%Y"))
        dd -= timedelta(days=1)
        while dd.weekday() >= 5:
            dd -= timedelta(days=1)
        voltas += 1
    lanc = _lancamentos(tk, dia)
    cnjs_lanc = {_cnj(r0.get("assunto")) for r0 in lanc_janela} - {None}
    sem_lanc = {k for k in recorte_janela if k[0] not in cnjs_lanc}
    # IDADE da intimacao nao lancada. Regra da usuaria (29/10/2026): passando
    # de 3 dias uteis desde a disponibilizacao sem virar lancamento, avisar
    # com destaque. Abaixo disso e' o dia andando — ela lanca quando chega na
    # vez, e cobrar antes vira ruido.
    URGENTE_APOS = 3
    nao_lancadas = []
    for (p, mv, disp) in sem_lanc:
        try:
            d_disp = datetime.strptime(disp, "%d/%m/%Y").date()
        except (ValueError, TypeError):
            continue
        idade = 0
        d = d_disp
        while d < d0:
            d += timedelta(days=1)
            if d.weekday() < 5:
                idade += 1
        nao_lancadas.append({"processo": p, "movimento": mv,
                             "disponibilizacao": disp, "dias_uteis": idade,
                             "urgente": idade > URGENTE_APOS})
    nao_lancadas.sort(key=lambda x: -x["dias_uteis"])
    for n in nao_lancadas:
        if n["urgente"]:
            avisos.append({
                "tipo": "não lançada há mais de 3 dias", "processo": n["processo"],
                "detalhe": f"disponibilizada em {n['disponibilizacao']} — "
                           f"{n['dias_uteis']} dias úteis sem lançamento"})

    # ------------------- 3. foi lancado e nao virou cartao (audita o proprio)
    def _mov(s):
        m = re.search(r"\b(?:mov|ev|evento|movimento|fls|seq|[Ii]d)\.?\s*"
                      r"([\w/]{1,10})", s or "", re.I)
        return (m.group(1).lower() if m else None)

    meus = set()
    for c in dc.trello(f"/boards/{dc.TESTE}/cards", fields="name"):
        k = _cnj(c["name"])
        if k:
            meus.add((k, _mov(c["name"])))
            meus.add((k, None))
    # o historico diz QUAIS lancamentos cada cartao cobriu — e' o unico jeito
    # de saber que um cartao consolidado cobre um movimento que nao esta' no
    # titulo dele (ver pipeline.executar, campo "cobre")
    hist = os.path.join(AQUI, "historico_execucoes.jsonl")
    if os.path.exists(hist):
        with open(hist) as fh:
            for linha in fh:
                try:
                    ex = json.loads(linha)
                except ValueError:
                    continue
                for c in ex.get("criados", []):
                    for a in c.get("cobre", []):
                        k = _cnj(a)
                        if k:
                            meus.add((k, _mov(a)))
    # So' faz sentido cobrar cartao de dia em que a rotina RODOU. Dia sem
    # execucao nao e' defeito — mesma distincao da reconciliacao (20/10).
    rodou_hoje = False
    hist = os.path.join(AQUI, "historico_execucoes.jsonl")
    if os.path.exists(hist):
        with open(hist) as fh:
            rodou_hoje = any(f"rotina {dia}" in l for l in fh)
    faltando = []
    for r0 in (lanc if rodou_hoje else []):
        a = r0.get("assunto") or ""
        if fora_de_escopo(a):
            continue
        k = _cnj(a)
        if not k:
            continue
        if (k, _mov(a)) not in meus:
            faltando.append(a)
    for a in faltando:
        avisos.append({"tipo": "lançado sem cartão", "processo": _cnj(a),
                       "detalhe": a[:70]})

    _log("noite", f"fonte única: {len(so_uma)} · sem lançamento: {len(sem_lanc)} "
                  f"· lançado sem cartão: {len(faltando)}")
    return {"avisos": avisos, "fonte_unica": len(so_uma),
            "sem_lancamento": len(sem_lanc), "sem_cartao": len(faltando),
            "nao_lancadas": nao_lancadas,
            "urgentes": sum(1 for n in nao_lancadas if n["urgente"])}


def vigia(dia, tk, ate="18:00", criar=False):
    """O DIA INTEIRO: verifica na frequencia da janela ate' a hora limite.

    E' isto que o servidor executa — nao uma chamada por vez, um processo que
    fica de pe'. Ate' 16/10/2026 o projeto so' sabia rodar uma vez; quem
    repetia era uma pessoa, e no servidor nao ha' ninguem.

    Cada ciclo faz UMA chamada leve (so' a lista de assuntos do dia). O
    trabalho caro — localizar publicacao, chamar o modelo, montar o cartao —
    so' acontece quando aparece lancamento que ainda nao foi visto.

    A frequencia vem de janela.py, que respeita o limite diario de
    requisicoes da plataforma processual: 3s no pico da tarde, 1 hora a' noite.
    """
    hlim, mlim = (int(x) for x in ate.split(":"))
    vistos = set()
    ciclos = chamadas = novos = criados = falhas_proc = 0
    t0 = datetime.now()
    _log("vigia", f"de pé até as {ate} · modo {'CRIAR' if criar else 'simulação'}")
    while True:
        agora = datetime.now()
        if (agora.hour, agora.minute) >= (hlim, mlim):
            break
        intervalo = janela.intervalo_em(agora)
        if intervalo is None:                      # fora da janela
            time.sleep(60)
            continue
        ciclos += 1
        try:
            brutos = _lancamentos(tk, dia)
            chamadas += 1
        except Exception as e:                     # rede caiu: tenta de novo
            _log("vigia", f"⚠️ falha na consulta ({type(e).__name__}) — segue")
            time.sleep(intervalo)
            continue
        agora_ids = {(r0.get("assunto") or "") + "|" + (r0.get("dataCadastro") or "")
                     for r0 in brutos}
        # A memoria e' CUMULATIVA, nao um retrato do ultimo ciclo.
        #
        # Descoberto em 19/10/2026: a API da plataforma processual devolve
        # quantidades DIFERENTES para a mesma consulta, em segundos —
        #
        #     15:03  9 lançados      15:06  11 → 11 → 11 → 12 → 11
        #     15:05  10 → 12 → 12    15:07  11 → 11
        #
        # oscilando para cima e para baixo, e lancamento nao desaparece. E'
        # inconsistencia de leitura do lado deles (provavelmente replicas).
        #
        # Com `vistos = agora_ids`, qualquer oscilacao fazia um lancamento
        # ja' processado reaparecer como novo, e o ciclo reprocessava sem
        # parar: 1 lancamento processado 40+ vezes em 5 minutos, gastando
        # modelo e cota de API. Nenhum cartao duplicado foi criado — a trava
        # de duplicata segurou —, mas o desperdicio foi real.
        frescos = agora_ids - vistos
        if vistos and frescos:                     # ignora a 1a leitura
            novos += len(frescos)
            _log("vigia", f"{len(frescos)} lançamento(s) novo(s) — processando")
            # PROTEGIDO de proposito: um lancamento problematico nao pode
            # derrubar o dia inteiro. Sem isto, qualquer excecao no meio do
            # processamento — modelo lento, Trello recusando, dado estranho —
            # mataria o vigia e os lancamentos seguintes se perderiam, em
            # silencio, ate' alguem perceber que o processo nao estava de pe'.
            # Risco encontrado em 16/10/2026, com o vigia ja' rodando.
            try:
                rel = lancamentos(dia, tk, criar=criar)
                if rel.get("criados"):
                    criados += len(rel["criados"].get("criados", []))
            except Exception as e:
                falhas_proc += 1
                _log("vigia", f"⚠️ FALHA ao processar ({type(e).__name__}: "
                              f"{str(e)[:90]}) — segue, será retentado")
                vistos -= frescos   # esquece SO' os que falharam, para retentar
                time.sleep(intervalo)
                continue
        vistos |= agora_ids        # acumula: o que foi visto nao desaparece
        time.sleep(intervalo)
    dur = (datetime.now() - t0).total_seconds() / 60
    _log("vigia", f"encerrado · {dur:.0f} min · {ciclos} ciclos · "
                  f"{chamadas} chamadas · {novos} lançamentos novos · "
                  f"{criados} cartões criados"
                  + (f" · {falhas_proc} falhas de processamento" if falhas_proc else ""))
    return {"ciclos": ciclos, "chamadas": chamadas, "novos": novos,
            "criados": criados, "minutos": round(dur), "falhas": falhas_proc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("etapa", choices=["manha", "lancamentos", "noite", "dia", "vigia"])
    ap.add_argument("dia", nargs="?", default=date.today().strftime("%d/%m/%Y"))
    ap.add_argument("--criar", action="store_true")
    ap.add_argument("--ate", default="18:00")
    a = ap.parse_args()
    tk = dj.conecta(dj.carrega_config(), verboso=False)
    _log("início", f"etapa={a.etapa} dia={a.dia} criar={a.criar}")
    r = {}
    if a.etapa in ("manha", "dia"):
        r["manha"] = manha(a.dia, tk)
    if a.etapa in ("lancamentos", "dia"):
        r["lancamentos"] = lancamentos(a.dia, tk, criar=a.criar)
    if a.etapa == "vigia":
        r["manha"] = manha(a.dia, tk)          # primeira leitura do dia
        r["vigia"] = vigia(a.dia, tk, ate=a.ate, criar=a.criar)
        r["noite"] = noite(a.dia, tk)          # conferências ao fim
    if a.etapa in ("noite", "dia"):
        r["noite"] = noite(a.dia, tk)
    _log("fim", "ok")
    return r


if __name__ == "__main__":
    main()
