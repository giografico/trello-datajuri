#!/usr/bin/env python3
"""
Janela de verificação do DataJuri — de quanto em quanto tempo perguntar se
houve lançamento novo.

REESCRITA EM 09/10/2026. A versão anterior (2 em 2 minutos, 294 chamadas/dia)
foi dimensionada quando não se sabia o limite da API. O DataJuri publicou os
números em 02/10/2026:

    120 requisições por MINUTO por token
    10.000 requisições por DIA por escritório   <- é este que aperta

O teto diário é o que decide. Uma chamada por segundo das 10h às 18h daria
29.028 por dia — 290% do limite — e a cota acabaria às 12h44, ANTES do bloco
14h–18h, que concentra 62% dos lançamentos. O sistema morreria todo dia no
meio da tarde, em silêncio.

DISTRIBUIÇÃO REAL, medida em 49 dias úteis (03/08 a 09/10/2026), sobre 548
lançamentos já filtrados por escopo:

     14h  11.3%     16h  19.3%  <- pico
     15h  14.8%     17h  16.8%

O bloco 14h–18h sozinho tem 62%. As pontas importam mais do que parecia:
7,7% antes das 9h (há lançamentos às 6h) e 9,3% depois das 18h — cerca de 1
por dia, em 15 dos 49 dias. Por isso a janela vai das 6h às 22h.

ALOCAÇÃO. O intervalo de cada hora sai de minimizar o atraso esperado dentro
do orçamento diário: dá-se mais frequência onde há mais movimento. As horas
vazias (7h, 20h–22h: 1,3% somadas) financiam o pico.

Não dá para ir a 1 segundo no pico: 15h, 16h e 17h a cada segundo consomem
10.800 chamadas — mais que o limite diário inteiro, sem sobrar nada para as
outras catorze horas.

Fora da janela nada se perde: a verificação pergunta "o que entrou desde a
última vez?", então um lançamento da madrugada é capturado às 6h. Só atrasa.

A verificação NÃO aciona o modelo — é script puro. O modelo só entra quando
há lançamento novo: 7,7 por dia em média, pico de 17.
"""
from datetime import time as _t

# (hora_inicial, hora_final, intervalo em SEGUNDOS)
JANELA = [
    (6,  7,  600),   #  2.7% — 10 min
    (7,  8,  600),   #  0.4% — 10 min
    (8,  9,   10),   #  4.2%
    (9,  10,  10),   #  1.6%
    (10, 13,   5),   # 16.1%
    (13, 14,  15),   #  3.1%
    (14, 15,   5),   # 11.3%
    (15, 16,   3),   # 14.8%  pico
    (16, 18,   3),   # 36.1%  pico
    (18, 19,   5),   #  5.8%
    (19, 20,  15),   #  2.6%
    (20, 23, 3600),  #  0.9% — 1 em 1 hora
]

LIMITE_DIA = 10_000      # por escritório, não por token
LIMITE_MIN = 120         # por minuto, por token


def intervalo_em(agora):
    """Segundos entre verificações neste horário, ou None se fora da janela."""
    if agora.weekday() >= 5:          # sábado e domingo: sem expediente
        return None
    h = agora.hour
    for ini, fim, seg in JANELA:
        if ini <= h < fim:
            return seg
    return None


def deve_verificar(agora):
    return intervalo_em(agora) is not None


def chamadas_por_dia():
    return sum((fim - ini) * 3600 // seg for ini, fim, seg in JANELA)


def dentro_do_limite():
    """(cabe, chamadas, pior_por_minuto) — o pré-voo chama isto."""
    n = chamadas_por_dia()
    pior = max(60 / seg for _, _, seg in JANELA)
    return n <= LIMITE_DIA and pior <= LIMITE_MIN, n, pior


if __name__ == "__main__":
    from datetime import datetime
    cabe, n, pior = dentro_do_limite()
    print(f"janela: {n:,} chamadas por dia útil  "
          f"({n/LIMITE_DIA*100:.0f}% do limite de {LIMITE_DIA:,})")
    print(f"pior caso por minuto: {pior:.0f}  (limite {LIMITE_MIN})")
    print(f"cabe no limite: {'SIM' if cabe else 'NÃO'}\n")
    for ini, fim, seg in JANELA:
        print(f"  {ini:02d}h–{fim:02d}h   a cada {seg:3d}s   "
              f"{(fim-ini)*3600//seg:5,d} chamadas")
    print()
    for hh in (5, 6, 8, 10, 13, 16, 18, 20, 23):
        i = intervalo_em(datetime(2026, 10, 9, hh, 0))
        print(f"  {hh:02d}h -> {f'a cada {i}s' if i else 'fora da janela'}")
