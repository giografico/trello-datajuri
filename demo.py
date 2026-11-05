#!/usr/bin/env python3
"""
MODO DEMONSTRAÇÃO — roda o pipeline de ponta a ponta sem nenhuma credencial
real: nem plataforma processual, nem Trello, nem chave de IA.

    python3 demo.py [DD/MM/AAAA]

Troca, só para esta execução, os dois pontos de rede do projeto pelos
clientes falsos (`cliente_plataforma_fake.py`, `cliente_trello_fake.py`) —
o resto do código (`cartao.py`, `consolida.py`, `pipeline.py`, `rotina.py`...)
roda exatamente como roda em produção, sem saber que está num ambiente de
mentira. É a prova de que a lógica de negócio não depende de rede nenhuma.

O pré-voo (`pipeline.py`) normalmente roda `teste_ambiente.py`, que confere
o Trello REAL — no modo demo não há Trello real para conferir, então essa
etapa fica marcada como pulada aqui. A parte que importa continua de pé:
`teste_regras.py` roda de verdade, e um cartão só nasce se os 291 passarem.

Sem chave da Anthropic configurada (nem Claude Code disponível), o resumo da
decisão usa um texto fixo, claramente marcado como exemplo — nunca finge
ter sido gerado por IA.

Cria o quadro em `trabalho/demo_trello.json`. Rodar de novo no mesmo dia
mostra a trava de duplicata funcionando: nenhum cartão novo nasce para os
mesmos lançamentos.
"""
import os
import subprocess
import sys
from datetime import date, datetime, timedelta

import cliente_plataforma
import cliente_plataforma_fake
import duplica_cartao
import cliente_trello_fake
import modelo
import pipeline
import gerador_dados_ficticios

RESUMO_EXEMPLO = ("**[resumo de exemplo — nenhuma chave de IA configurada]** "
                   "O juízo decidiu sobre o pedido da parte, conforme consta "
                   "na intimação. Verificar eventual providência.")


def _liga_clientes_falsos():
    cliente_plataforma.carrega_config = cliente_plataforma_fake.carrega_config
    cliente_plataforma.conecta = cliente_plataforma_fake.conecta
    cliente_plataforma.get = cliente_plataforma_fake.get
    duplica_cartao.trello = cliente_trello_fake.trello

    chave_api, _ = modelo._chave_api()
    if chave_api:
        print("  chave de API da Anthropic encontrada — o resumo roda de verdade.\n")
    else:
        modelo.disponivel = lambda: False   # evita sondar o Claude Code de verdade

        def _resumo_exemplo(texto, contexto=""):
            return RESUMO_EXEMPLO if len((texto or "").strip()) >= 120 else None

        def _resumo_audiencia_exemplo(texto, contexto=""):
            return None   # sem exigência a extrair, no exemplo fixo

        modelo.resumir = _resumo_exemplo
        modelo.resumir_audiencia = _resumo_audiencia_exemplo
        print("  sem chave de IA configurada — usando resumo fixo de exemplo, "
              "claramente marcado.\n")

    def _previoo_demo():
        print("  pré-voo: teste_regras.py ... ", end="", flush=True)
        r = subprocess.run([sys.executable, os.path.join(pipeline.AQUI, "teste_regras.py")],
                           capture_output=True, text=True)
        print("ok" if r.returncode == 0 else "FALHOU")
        if r.returncode != 0:
            print(r.stdout[-2000:])
            return False
        print("  pré-voo: teste_ambiente.py ... pulado (modo demo não tem "
              "Trello real para conferir ids de quadro/lista/campo)")
        return True
    pipeline._previoo = _previoo_demo


def main(dia_str=None, reiniciar=False):
    hoje = (datetime.strptime(dia_str, "%d/%m/%Y").date() if dia_str
            else date.today())
    hoje_str, ontem_str = hoje.strftime("%d/%m/%Y"), (hoje - timedelta(days=1)).strftime("%d/%m/%Y")

    print(f"=== MODO DEMONSTRAÇÃO — {hoje_str} — nenhuma credencial real é usada ===\n")
    # NÃO reinicia o quadro por padrão: rodar duas vezes com o mesmo dia é
    # exatamente o que prova a trava de duplicata (cartao.criar -> ja_criei).
    # Reiniciar aqui sempre esconderia essa prova.
    if reiniciar or not os.path.exists(cliente_trello_fake.ARQUIVO):
        cliente_trello_fake.reiniciar()
    _liga_clientes_falsos()

    recorte_ontem, lancamentos_hoje, recorte_hoje = gerador_dados_ficticios.gera(hoje)

    import rotina
    tk = cliente_plataforma.conecta(cliente_plataforma.carrega_config(), verboso=False)

    print(f"--- manhã de ontem ({ontem_str}) — publicação chega pelo AtitudeJur ---")
    cliente_plataforma_fake.definir_dados([], recorte_ontem)
    rotina.manha(ontem_str, tk)

    print(f"\n--- manhã de hoje ({hoje_str}) — a MESMA publicação chega pelo "
          "Alerte, e precisa ser reconhecida como repetida ---")
    cliente_plataforma_fake.definir_dados(lancamentos_hoje, recorte_hoje)
    saida_manha = rotina.manha(hoje_str, tk)
    repetidas = saida_manha["intimacoes"]["totais"].get("repetidas", 0)
    print(f"\n  >>> {repetidas} intimação(ões) reconhecida(s) como já vista(s) "
          "ontem por outra fonte" + (" — caso A confirmado." if repetidas else
          " — ⚠️ caso A NÃO reproduzido, confira as datas do gerador."))

    print(f"\n--- lançamentos de hoje — cria os cartões ---")
    resultado = rotina.lancamentos(hoje_str, tk, criar=True)

    print("\n--- resultado ---")
    criados = (resultado.get("criados") or {}).get("criados", [])
    for c in criados:
        marca = f"  -> {', '.join(c['problemas'])}" if c["problemas"] else ""
        print(f"  {c['url']}  {c['nome'][:70]}{marca}")
    ja_existiam = (resultado.get("criados") or {}).get("pulados", [])
    for p in ja_existiam:
        print(f"  (pulado — {p['motivo']})  {p['assunto'][:60]}")
    pulados = resultado.get("fora") or {}
    if pulados:
        print(f"\n  fora de escopo: {pulados}")
    total_no_quadro = len(duplica_cartao.trello(
        f"/boards/{duplica_cartao.TESTE}/cards", fields="name"))
    print(f"\n{len(criados)} cartão(ões) criado(s) nesta execução · "
          f"{total_no_quadro} no total no quadro de demonstração "
          f"({cliente_trello_fake.ARQUIVO}).")

    _confere_casos_dificeis(repetidas, duplica_cartao.trello(
        f"/boards/{duplica_cartao.TESTE}/cards", fields="name,desc,due"))

    print("\nRode `python3 demo.py " + hoje_str + "` de novo: a trava de "
          "duplicata deve impedir cartões repetidos para os mesmos lançamentos.")


def _confere_casos_dificeis(repetidas, cartoes):
    """Não basta rodar — confere, igual ao resto do projeto, que cada caso
    difícil foi tratado do jeito certo."""
    texto_total = " ".join((c.get("name", "") + " " + c.get("desc", ""))
                           for c in cartoes)
    pat = next((c for c in cartoes if c.get("name", "").startswith("PAT")), None)
    prz = [c for c in cartoes if c.get("name", "").startswith("PRZ")]

    casos = [
        ("A. duplicata entre duas fontes reconhecida", repetidas == 1),
        ("B. ED + recurso do mesmo movimento viraram UM cartão", len(prz) == 1),
        ("C. cartão sem prazo fatal nasceu sem vencimento, sem virar defeito",
         bool(pat) and not pat.get("due")),
        ("D. número de OAB não virou intimação (não aparece em nenhum cartão)",
         "099001" not in texto_total),
        ("E. CPF fictício não vazou para nenhum cartão",
         "123.456.789-00" not in texto_total),
    ]
    print("\n--- os 5 casos difíceis, conferidos (não só rodados) ---")
    for nome, ok in casos:
        print(f"  {'ok ' if ok else 'FALHOU'} {nome}")
    if not all(ok for _, ok in casos):
        sys.exit(1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--reiniciar"]
    main(args[0] if args else None, reiniciar="--reiniciar" in sys.argv)
