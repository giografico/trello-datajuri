#!/usr/bin/env python3
"""
Regras de normalização da fila de intimações, a partir do recorte de
terceiros da plataforma processual.

REGRA DE FONTE (corrigida em 14/09/2026 pela usuaria):
  Processar SEMPRE as DUAS fontes — AtitudeJur Publicacoes e Alerte - Web
  Service. Uma intimacao que aparece nas duas e' a MESMA intimacao: agrupa
  pela regra de duplicata normal (mesmo processo + mesmo movimento), sem
  distincao de fonte.

  A versao anterior processava so' o AtitudeJur e tratava o Alerte como
  checagem cruzada. Isso estava errado e perdia prazo: um prazo real
  (0009999-11, mov. 972) veio pelo Alerte e NAO estava no AtitudeJur.

ARMADILHA DO CAMPO `data` — as duas fontes nao significam a mesma coisa:
  AtitudeJur -> `data` E' a data de disponibilizacao.
  Alerte     -> `data` e' um dia util A FRENTE; a disponibilizacao real vem
                escrita no texto, como "disponibilizado em: DD/MM/AAAA".
  Medido em 10 e 11/09/2026: campo 10/09 -> texto diz 09/09; campo 11/09 ->
  texto diz 10/09. Usar o campo do Alerte como disponibilizacao faria todo
  prazo dessa fonte sair um dia mais longo do que e'.
  Por isso `disponibilizacao()` normaliza antes de qualquer calculo.

Duplicata: match EXATO de processo + movimento. Nada de similaridade.
Verificacoes falam por excecao.
"""
import re

RX_MOV = re.compile(
    r'movimento\s*\(seq\.\s*(\d{1,6})\)|'
    r'\bev(?:\.|ento)\s*n?[ºo°]?\s*(\d{1,6})\b|'
    r'\bmov(?:\.|imento)\s*n?[ºo°]?\s*(\d{1,6})\b', re.I)
RX_DISP = re.compile(r'disponibilizad[oa] em:?\s*(\d{2}/\d{2}/\d{4})', re.I)

ATITUDE = "AtitudeJur Publicações"
ALERTE = "Alerte - Web Service"


def so_digitos(processo):
    """Chave canonica do processo.

    As duas fontes gravam o CNJ em formatos diferentes:
      AtitudeJur -> "88888889020258260002"      (sem mascara)
      Alerte     -> "8888888-90.2025.8.26.0002" (com mascara)
    Comparar as strings cruas faz a duplicata entre fontes NUNCA ser
    detectada — visto em 15/09/2026, com a mesma intimacao aparecendo duas
    vezes na fila. Normalizar antes de qualquer comparacao.

    Devolve "" se nao for um CNJ. O recorte traz linhas de INDICE POR
    ADVOGADOS, em que o campo numeroProcesso vem com o numero da OAB:

        numeroProcesso = "099001"   <- OAB, nao processo
        numeroProcesso = "099002"

    Sem validar, essas linhas entram na fila como se fossem intimacao e sao
    resumidas de manha a toa — 2 de 33 em 02 e 05/10/2026. O CNJ tem 20
    digitos (Res. CNJ 65/2008); nada mais e' processo.
    """
    d = re.sub(r"\D", "", processo or "")
    return d if len(d) == 20 else ""


def movimento(texto):
    m = RX_MOV.search(texto or "")
    return next((g for g in m.groups() if g), None) if m else None


def disponibilizacao(fonte, campo_data, texto):
    """Data de disponibilizacao REAL, normalizada entre as fontes.
    No Alerte o campo `data` esta um dia util a frente — ver docstring."""
    if (fonte or "").startswith("Alerte"):
        m = RX_DISP.search(texto or "")
        if m:
            return m.group(1)
    return campo_data
