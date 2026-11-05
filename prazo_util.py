#!/usr/bin/env python3
"""
Calculo de prazo processual — dias uteis, CPC.

Regra de marco (confirmada pela usuaria em 31/08/2026, e' o que diz a lei):
  1. O recorte traz SEMPRE a data de disponibilizacao (campo `data`).
  2. Data de publicacao = primeiro dia util seguinte a disponibilizacao (CPC 224 §2o).
  3. Inicio da contagem = dia util seguinte a publicacao (CPC 224 caput).
  4. Contagem em dias uteis (CPC 219), excluidos sabados, domingos e feriados.

O campo `dataPublicacao` da API vem vazio em 100% da amostra — nao usar.
"""
from datetime import date, datetime, timedelta

# Feriados nacionais 2026 (Lei 662/49, 6.802/80, 14.759/23) + feriados forenses moveis
FERIADOS_NACIONAIS_2026 = {
    date(2026, 1, 1):   "Confraternização Universal",
    date(2026, 2, 16):  "Carnaval",
    date(2026, 2, 17):  "Carnaval",
    date(2026, 2, 18):  "Quarta-feira de Cinzas (expediente forense suspenso)",
    date(2026, 4, 3):   "Sexta-feira Santa",
    date(2026, 4, 21):  "Tiradentes",
    date(2026, 5, 1):   "Dia do Trabalho",
    date(2026, 6, 4):   "Corpus Christi",
    date(2026, 9, 7):   "Independência",
    date(2026, 10, 12): "Nossa Senhora Aparecida",
    date(2026, 11, 2):  "Finados",
    date(2026, 11, 15): "Proclamação da República",
    date(2026, 11, 20): "Consciência Negra",
    date(2026, 12, 25): "Natal",
}

# CPC art. 220 — suspensao dos prazos entre 20/12 e 20/01
def em_suspensao_forense(d):
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 20)

DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]


def motivo_nao_util(d):
    """Retorna o motivo de d nao ser dia util, ou None se for util."""
    if d.weekday() == 5:
        return "sábado"
    if d.weekday() == 6:
        return "domingo"
    if d in FERIADOS_NACIONAIS_2026:
        return FERIADOS_NACIONAIS_2026[d]
    if em_suspensao_forense(d):
        return "suspensão forense (CPC art. 220)"
    return None


def eh_util(d):
    return motivo_nao_util(d) is None


def proximo_util(d):
    """Primeiro dia util estritamente APOS d. Registra o que foi pulado."""
    pulados = []
    x = d + timedelta(days=1)
    while not eh_util(x):
        pulados.append((x, motivo_nao_util(x)))
        x += timedelta(days=1)
    return x, pulados


def calcula(disponibilizacao, dias_uteis):
    """Da disponibilizacao ao vencimento, com a conta inteira aberta.

    Retorna dict com cada etapa e a lista de dias nao uteis excluidos,
    para que a conferencia humana seja possivel sem refazer a conta.
    """
    publicacao, pulou_pub = proximo_util(disponibilizacao)
    inicio, pulou_ini = proximo_util(publicacao)

    excluidos = []
    contados = []
    d = inicio
    n = 0
    while n < dias_uteis:
        if eh_util(d):
            n += 1
            contados.append(d)
        else:
            excluidos.append((d, motivo_nao_util(d)))
        if n < dias_uteis:
            d += timedelta(days=1)
    vencimento = d

    return {
        "disponibilizacao": disponibilizacao,
        "publicacao": publicacao,
        "pulou_ate_publicacao": pulou_pub,
        "inicio": inicio,
        "pulou_ate_inicio": pulou_ini,
        "dias_uteis": dias_uteis,
        "excluidos_no_meio": excluidos,
        # As tres datas que a controladoria le (definidas por ela em 31/08/2026):
        #   fatal    = ultimo dia do prazo
        #   fatal -1 = prazo final de trabalho
        #   fatal -2 = dia de entrega no cartao do Trello
        # Contadas em DIAS UTEIS para tras. Em dias corridos, fatal-1 e fatal-2
        # cairiam em fim de semana e colidiriam entre si — datas nao acionaveis.
        "fatal": vencimento,
        "fatal_1": recua_uteis(vencimento, 1),
        "fatal_2": recua_uteis(vencimento, 2),
    }


def recua_uteis(d, n):
    """N dias uteis antes de d."""
    x = d
    for _ in range(n):
        x -= timedelta(days=1)
        while not eh_util(x):
            x -= timedelta(days=1)
    return x


def recua_util(d):
    """Ultimo dia util <= d. Usado pela margem de seguranca de 1 dia:
    se o dia anterior ao vencimento cair em fim de semana ou feriado,
    a margem recua para o dia util anterior."""
    while not eh_util(d):
        d -= timedelta(days=1)
    return d


def fmt(d):
    return f"{d.strftime('%d/%m/%Y')} ({DIAS_SEMANA[d.weekday()]})"


def explica(c):
    """Conta aberta, em texto — a usuaria confere, nao recalcula."""
    L = []
    L.append(f"Disponibilização: **{fmt(c['disponibilizacao'])}**")
    if c["pulou_ate_publicacao"]:
        p = ", ".join(f"{d.strftime('%d/%m')} {m}" for d, m in c["pulou_ate_publicacao"])
        L.append(f"Publicação (1º dia útil seguinte, CPC 224 §2º): **{fmt(c['publicacao'])}** — pulou {p}")
    else:
        L.append(f"Publicação (1º dia útil seguinte, CPC 224 §2º): **{fmt(c['publicacao'])}**")
    if c["pulou_ate_inicio"]:
        p = ", ".join(f"{d.strftime('%d/%m')} {m}" for d, m in c["pulou_ate_inicio"])
        L.append(f"Início da contagem (dia útil seguinte, CPC 224): **{fmt(c['inicio'])}** — pulou {p}")
    else:
        L.append(f"Início da contagem (dia útil seguinte, CPC 224): **{fmt(c['inicio'])}**")
    L.append(f"Contagem: **{c['dias_uteis']} dias úteis** (CPC 219)")
    if c["excluidos_no_meio"]:
        for d, m in c["excluidos_no_meio"]:
            L.append(f"  — excluído {d.strftime('%d/%m/%Y')}: {m}")
    L.append(tres_datas(c))
    return "\n".join(L)


def tres_datas(c):
    """O formato que a controladoria lê. Nunca alterar a ordem nem os rotulos."""
    return (f"**fatal: {c['fatal'].strftime('%d/%m/%Y')}** ; "
            f"fatal -1: {c['fatal_1'].strftime('%d/%m/%Y')} ; "
            f"fatal -2: {c['fatal_2'].strftime('%d/%m/%Y')}")


if __name__ == "__main__":
    for dias in (5, 15):
        print(explica(calcula(date(2026, 8, 31), dias)), "\n" + "-"*60)


def bloco_prazo(fatal, folga=2):
    """Bloco de prazo do cartao. FONTE UNICA — nenhum montador escreve o seu.

    Corrigido em 09/10/2026, depois de a usuaria apontar:

        "ela esta' lancando a conta certinha no lancamento do prazo no
         DataJuri. sua tarefa e' COPIAR! no maximo fazer a conta de
         fatal - 1 ou fatal - 2"

    O cartao vinha trazendo, embaixo das datas:

        "Marco: publicacao no Diario de Justica (1o dia util apos a
         disponibilizacao, CPC 224 §2o); contagem inicia no dia util
         seguinte (CPC 224), em dias uteis (CPC 219)."

    Isso AFIRMA uma contagem que nao foi feita aqui. O prazo fatal vem pronto
    do lancamento — quem contou foi a Controladoria. Se ela contou por outro
    caminho (e e' direito dela: e' quem sabe), o cartao descrevia errado a
    conta dela, no lugar em que ela confia.

    O que este bloco pode dizer:
      - o prazo fatal, COPIADO do lancamento, com a origem explicita
      - fatal -1 e fatal -2, que sao a unica conta nossa

    O que ele NAO pode dizer: marco inicial, artigo de lei, metodo de
    contagem. Nada disso foi apurado aqui.
    """
    if not fatal:
        return "⚠️ **Sem prazo fatal no lançamento do DataJuri.**"
    from datetime import datetime as _dt
    d = (_dt.strptime(fatal, "%d/%m/%Y").date()
         if isinstance(fatal, str) else fatal)
    # Enxuto por pedido da Controladoria em 29/10/2026: so' as datas, sem
    # explicacao nenhuma. Quem le' o cartao sabe o que sao — e texto que
    # explica o obvio rouba espaco do que importa, que e' a decisao.
    if not folga:
        return f"**fatal: {fmt(d)}**"
    return (f"**fatal: {fmt(d)}**  ·  "
            f"fatal −1: {fmt(recua_uteis(d, 1))}  ·  "
            f"**fatal −2: {fmt(recua_uteis(d, 2))}**")
