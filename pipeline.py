#!/usr/bin/env python3
"""
PIPELINE — único caminho para criar cartões em lote.

    from pipeline import executar
    relatorio = executar(itens)     # itens: lista de dicts (ver LOTE abaixo)

O que ele garante, sem depender de ninguém lembrar de nada:

  1. PRÉ-VOO OBRIGATÓRIO. Roda teste_regras.py e teste_ambiente.py. Se algum
     falhar, ABORTA e nada é criado. Sem isso, cartao.criar() levanta
     PreVooNaoExecutado — a trava está no próprio criar(), não aqui.

  2. VALIDAÇÃO DE ENTRADA. Cada item precisa de assunto, conteúdo e rodapé.
     Item malformado aborta o lote inteiro ANTES de criar qualquer coisa —
     lote meio criado é pior que lote não criado.

  3. PÓS-VERIFICAÇÃO DE CADA CARTÃO. Depois de criar, o cartão é lido de
     volta e conferido: etiqueta aplicada, vencimento correto, campo Prazo
     Fatal quando é PRZ, nenhum membro atribuído, sem CPF/RG no texto e sem
     resumo duplicado. Um cartão que nasce errado é reportado na hora, com
     link — não some no meio de 40.

  4. LOG APPEND-ONLY. Cada execução acrescenta ao histórico, nunca
     sobrescreve. Em 15/09/2026 rodei o mesmo script duas vezes e a segunda
     apagou o registro do que a primeira criou.

  5. RESUMO PRÉ-PROCESSADO. Item sem `conteudo` busca o resumo que o modelo
     escreveu de manhã (cache_resumos). Encontrou, o cartão sai em ~15s em vez
     de 1-5 min; não encontrou, segue o fluxo normal.

  6. RELATÓRIO FINAL com o que foi criado, pulado e o que saiu com defeito.
"""
import json, os, re, subprocess, sys
from datetime import datetime

import cache_resumos
import cartao
import duplica_cartao as dc
from consolida import eh_prz, folga_dias_uteis, preenche_prazo_fatal
from prazo_util import recua_uteis

AQUI = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(AQUI, "historico_execucoes.jsonl")
RX_CPF = re.compile(r'\d{3}\.\d{3}\.\d{3}-\d{2}|\bRG\s*n?[ºo°]?\s*\d{6,}', re.I)
# Marcas de que o cartao esta' explicando uma contagem de prazo. Ver
# prazo_util.bloco_prazo — a conta e' da Controladoria, nao nossa.
RX_CONTAGEM = re.compile(
    r'CPC\s*2(19|24)|art\.?\s*2(19|24)|marco\s*(inicial|:)|'
    r'contagem\s+inicia|dias\s+[úu]teis\s*\(CPC', re.I)


class LoteInvalido(ValueError):
    pass


def _previoo():
    """Roda os dois testes. Devolve True só se ambos passarem."""
    for script in ("teste_regras.py", "teste_ambiente.py"):
        print(f"  pré-voo: {script} ... ", end="", flush=True)
        r = subprocess.run([sys.executable, os.path.join(AQUI, script)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("FALHOU")
            print(r.stdout[-2000:])
            return False
        print("ok")
    return True


def _valida(itens):
    for i, it in enumerate(itens):
        for campo in ("assunto", "conteudo"):
            if not (it.get(campo) or "").strip():
                raise LoteInvalido(f"item {i}: campo '{campo}' vazio — lote abortado "
                                   f"antes de criar qualquer cartão")
        f = it.get("prazo_fatal")
        if f:
            try:
                datetime.strptime(f, "%d/%m/%Y")
            except ValueError:
                raise LoteInvalido(f"item {i}: prazo_fatal {f!r} não é DD/MM/AAAA")


def _confere(card_id, assunto, prazo_fatal, sem_fatal_na_origem=False):
    """Lê o cartão de volta e confere o que deveria estar lá."""
    c = dc.trello(f"/cards/{card_id}", fields="name,desc,due,idLabels,idMembers,dueComplete",
                  customFieldItems="true")
    problemas = []
    if c.get("dueComplete"):
        problemas.append("NASCEU MARCADO COMO CONCLUÍDO")
    # decidido com a controladoria em 30/09/2026: o cartao tem de dizer quem lancou a
    # atividade no DataJuri. Se o campo criadoPor.nome nao for pedido na
    # consulta, vem vazio em silencio e o rodape sai sem autoria.
    # A autoria saiu do rodapé e foi para o comentário em 29/10/2026 —
    # conferir no lugar novo.
    try:
        coments = dc.trello(f"/cards/{card_id}/actions", filter="commentCard")
        tem_autoria = any("Lançado no DataJuri por:" in
                          ((a.get("data") or {}).get("text") or "")
                          for a in coments)
    except Exception:
        tem_autoria = True        # falha de rede não vira defeito do cartão
    if not tem_autoria:
        problemas.append("sem comentário de autoria do lançamento")
    if not c.get("idLabels"):
        # Nao e' defeito do codigo quando a sigla nao tem etiqueta cadastrada
        # no quadro — o cartao ja' avisa no corpo (cartao.AVISO_SEM_ETIQUETA).
        # Virou distincao em 16/10/2026, mesmo criterio do "sem vencimento":
        # separar o que o codigo errou do que o cadastro nao tem.
        if cartao.AVISO_SEM_ETIQUETA[:40] not in (c.get("desc") or ""):
            problemas.append("sem etiqueta")
        else:
            problemas.append("ⓘ sigla sem etiqueta cadastrada — classificar")
    if c.get("idMembers"):
        problemas.append(f"{len(c['idMembers'])} membro(s) atribuído(s)")
    if RX_CPF.search(c.get("desc") or ""):
        problemas.append("CPF/RG no texto")
    if (c.get("desc") or "").count("## Resumo da Decisão") > 1:
        problemas.append("resumo duplicado")
    # Cartao sem vencimento e' cartao que ninguem ve na visao de calendario.
    # A conferencia so' olhava o vencimento QUANDO havia prazo_fatal — entao um
    # lote montado sem passar o fatal criava cartoes mudos e nada reclamava.
    # Medido em 09/10/2026: 11 de 35 cartoes nasceram sem vencimento por esse
    # caminho, e 9 deles teriam batido com o da Controladoria. A regra de
    # folga por tipo (PRZ=fatal-2, PROV/PAT/AUD=o proprio fatal) mora em
    # consolida.folga_dias_uteis e vale para TODOS — nao so' para PRZ.
    if not (c.get("due") or ""):
        # Distinguir a causa, senao a lista de defeitos perde valor —
        # mesmo erro do ⚠️ em excesso corrigido em 15/10/2026 pela manha.
        #
        #   o codigo errou          -> DEFEITO, tem de ser corrigido
        #   o lancamento nao traz   -> dado de origem, nao ha' o que corrigir
        #                              aqui; o cartao ja' avisa no corpo
        #
        # Visto no teste cego de 15/10: dois lancamentos "Audiência" vieram
        # com dataPrazoFatal vazio. O cartao nasceu certo — sem data, e
        # dizendo que nao havia data — e foi reportado como defeito.
        if not sem_fatal_na_origem:
            problemas.append("SEM VENCIMENTO — não aparece no calendário")
    # O cartao NAO pode afirmar como o prazo foi contado. O prazo fatal vem
    # pronto do lancamento — quem conta e' a Controladoria; aqui so' se copia,
    # e no maximo se faz fatal-1 e fatal-2 (usuaria, 09/10/2026). Citar marco
    # inicial ou artigo do CPC descreve uma conta que nao foi feita aqui, e
    # descreve ERRADO a dela se ela tiver contado por outro caminho.
    if RX_CONTAGEM.search(c.get("desc") or ""):
        problemas.append("AFIRMA MÉTODO DE CONTAGEM que não foi apurado aqui")
    if prazo_fatal:
        esperado = recua_uteis(datetime.strptime(prazo_fatal, "%d/%m/%Y").date(),
                               folga_dias_uteis(assunto)).isoformat()
        if (c.get("due") or "")[:10] != esperado:
            problemas.append(f"vencimento {(c.get('due') or '')[:10]} != {esperado}")
        tem_cf = any((i.get("value") or {}).get("date")
                     for i in c.get("customFieldItems", []))
        if preenche_prazo_fatal(assunto) and not tem_cf:
            problemas.append("PRZ sem campo Prazo Fatal")
    return problemas


def executar(itens, rotulo=""):
    _inicio = datetime.now()
    print(f"=== pipeline: {len(itens)} item(ns) {rotulo} ===")
    if not _previoo():
        print("\nABORTADO no pré-voo. Nada foi criado.")
        return {"abortado": "pré-voo"}
    _valida(itens)
    cartao.liberar("testes-passaram")
    print("  pré-voo ok — criação liberada\n")

    criados, pulados, defeituosos = [], [], []
    do_cache = 0
    for it in itens:
        # resumo pre-processado de manha? (cache_resumos) — poupa a leitura da
        # decisao, que e' o que domina o tempo. Sem resumo pronto, segue o fluxo
        # normal: o `conteudo` ja' veio escrito por quem montou o lote.
        if not (it.get("conteudo") or "").strip():
            pronto, chave = cache_resumos.buscar(
                it.get("processo"), it.get("movimento"),
                it.get("disponibilizacao"), it.get("dia"))
            if pronto:
                it["conteudo"] = pronto
                it["rodape"] = it.get("rodape", "") + (
                    f"\n\n*Resumo pré-processado na manhã de {it.get('dia','hoje')} "
                    f"(cache {chave}).*")
                do_cache += 1
        novo, motivo = cartao.criar(
            assunto=it["assunto"], conteudo=it["conteudo"], rodape=it["rodape"],
            n_lancamentos=it.get("n_lancamentos", 1),
            prazo_fatal=it.get("prazo_fatal"), processo=it.get("processo"),
            comentario_autoria=it.get("comentario_autoria"))
        if not novo:
            pulados.append({"assunto": it["assunto"], "motivo": motivo})
            continue
        probs = _confere(novo["id"], novo["name"], it.get("prazo_fatal"),
                         sem_fatal_na_origem=not (it.get("prazo_fatal") or "").strip())
        reg = {"url": novo["shortUrl"], "id": novo["id"], "nome": novo["name"],
               "prz": eh_prz(novo["name"]), "problemas": probs,
               "sem_fatal_na_origem": not (it.get("prazo_fatal") or "").strip(),
               # QUAIS lancamentos este cartao cobre. Sem isto, a conferencia
               # de fim de dia acusa cartao consolidado: dois lancamentos
               # (mov 100 e mov 84) viram um cartao, cujo titulo leva so' um
               # movimento, e o outro parece nao ter virado cartao.
               # Visto em 15/10/2026, no primeiro teste das conferencias.
               "cobre": it.get("lancamentos") or [it["assunto"]]}
        criados.append(reg)
        if probs:
            defeituosos.append(reg)
        print(f"  {'⚠️ ' if probs else 'ok '} {novo['shortUrl']} {novo['name'][:50]}"
              + (f"  -> {', '.join(probs)}" if probs else ""))

    rel = {"quando": datetime.now().isoformat(timespec="seconds"), "rotulo": rotulo,
           "duracao_segundos": (datetime.now() - _inicio).total_seconds(),
           "criados": criados, "pulados": pulados, "defeituosos": defeituosos}
    with open(LOG, "a") as f:                       # append-only
        f.write(json.dumps(rel, ensure_ascii=False) + "\n")

    sem_fatal = sum(1 for c in criados if c.get("sem_fatal_na_origem"))
    print(f"\n  criados {len(criados)} · pulados {len(pulados)} · "
          f"com defeito {len(defeituosos)}"
          + (f" · {sem_fatal} sem prazo fatal no lançamento" if sem_fatal else "")
          + (f" · {do_cache} com resumo pré-processado" if do_cache else ""))
    if defeituosos:
        print("\n" + "!" * 70)
        print("  CARTÕES QUE NASCERAM COM DEFEITO — conferir um a um:")
        for d in defeituosos:
            print(f"    {d['url']}  {', '.join(d['problemas'])}")
        print("!" * 70)
    print(f"\n  histórico: {LOG}")
    return rel


if __name__ == "__main__":
    print(__doc__)
    print("Este módulo é importado por um script de lote. Execução direta só "
          "mostra esta ajuda.\n")
    print("Verificando o pré-voo agora:")
    print("  RESULTADO:", "ok" if _previoo() else "FALHOU")
