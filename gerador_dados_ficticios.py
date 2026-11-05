#!/usr/bin/env python3
"""
Gerador de dados fictícios para o modo demonstração.

Produz dois dias de recorte e um dia de lançamentos, todos INVENTADOS,
cobrindo os casos difíceis que o sistema real resolve:

  A. intimação duplicada vinda de duas fontes, em dias diferentes
     (AtitudeJur publica "ontem"; o Alerte entrega a MESMA no dia seguinte,
     com a disponibilização real escrita no texto, não no campo `data`)
  B. ED e recurso do mesmo movimento, com prazos fatais diferentes
  C. lançamento sem prazo fatal na origem
  D. número de OAB no lugar de número de processo (índice por advogados)
  E. dado pessoal (CPF) dentro do texto do lançamento

Nenhum nome, processo ou texto aqui corresponde a caso real — é tudo
inventado para o programa ter o que processar.
"""
from datetime import date, timedelta

ATITUDE = "AtitudeJur Publicações"
ALERTE = "Alerte - Web Service"


def _cnj(sequencial, ano, segmento, tribunal, origem):
    """Monta um CNJ fictício com dígito verificador válido (Res. CNJ 65/2008)."""
    num18 = f"{sequencial:07d}{ano:04d}{segmento:01d}{tribunal:02d}{origem:04d}"
    resto = int(num18 + "00") % 97
    dv = 98 - resto
    return f"{sequencial:07d}-{dv:02d}.{ano}.{segmento}.{tribunal:02d}.{origem:04d}"


def gera(hoje=None):
    """Devolve (recorte_ontem, lancamentos_hoje, recorte_hoje).

    `hoje` é um `date`. `recorte_ontem` simula o que o AtitudeJur já tinha
    entregado no dia anterior — o `demo.py` roda `rotina.manha()` duas vezes,
    uma pra cada dia, pra provar a deduplicação ENTRE DIAS (caso A)."""
    hoje = hoje or date.today()
    ontem = hoje - timedelta(days=1)
    hoje_str, ontem_str = hoje.strftime("%d/%m/%Y"), ontem.strftime("%d/%m/%Y")
    ano = hoje.year
    # Varia por dia (não só por ano): rodar o modo demo em datas diferentes
    # gera processos diferentes, em vez do mesmo punhado de cartões sempre —
    # é o que dá ao dashboard mais de um dia de histórico para mostrar.
    off = hoje.toordinal() % 900_000

    cnj_a = _cnj(1111001 + off, ano, 8, 16, 1)      # caso A — duplicata entre fontes
    cnj_b = _cnj(2222002 + off, ano, 8, 16, 1)      # caso B — ED + recurso
    cnj_c = _cnj(3333003 + off, ano, 8, 16, 1)      # caso C — sem prazo fatal
    cnj_e = _cnj(5555005 + off, ano, 8, 16, 1)      # caso E — dado pessoal no texto

    _TEOR_A = ("Vistos. Trata-se de ação de cobrança movida pela parte "
               "autora. O juízo decide pela procedência do pedido, "
               "condenando a parte ré ao pagamento do valor pleiteado, com "
               "correção monetária e juros de mora a partir da citação. "
               "Intimem-se as partes.")

    def _fmt(d):
        return d.strftime("%d/%m/%Y")

    # ----------------------------------------------------- RECORTE: ONTEM --
    # A. publicada pelo AtitudeJur — o campo `data` já É a disponibilização.
    recorte_ontem = [
        {"id": "demo-a-atitude", "data": ontem_str, "numeroProcesso": cnj_a,
         "configConsultaRecorteId": ATITUDE, "lido": "não",
         "jornal": "DJEN", "tribunal": "TJPR", "vara": "2ª Vara Cível",
         "textoCompleto": _TEOR_A},
    ]

    # ------------------------------------------------------ RECORTE: HOJE --
    recorte_hoje = [
        # A. a MESMA intimação, entregue hoje pelo Alerte — o campo `data`
        # vem um dia útil à frente (hoje), e a disponibilização real (ontem)
        # só existe escrita no texto. Sem normalizar isso, o sistema trataria
        # como uma intimação NOVA, quando já foi vista ontem.
        {"id": "demo-a-alerte", "data": hoje_str, "numeroProcesso": cnj_a,
         "configConsultaRecorteId": ALERTE, "lido": "não",
         "jornal": "DJEN", "tribunal": "TJPR", "vara": "2ª Vara Cível",
         "textoCompleto": f"disponibilizado em: {ontem_str} " + _TEOR_A},

        # B. decisão de um só movimento, citada nos dois lançamentos (ED e
        # recurso) que o agrupamento deve consolidar num cartão só.
        {"id": "demo-b", "data": hoje_str, "numeroProcesso": cnj_b,
         "configConsultaRecorteId": ATITUDE, "lido": "não",
         "jornal": "DJEN", "tribunal": "TJPR", "vara": "1ª Vara Cível",
         "textoCompleto": (
             "Vistos. O Tribunal, por unanimidade, negou provimento ao "
             "recurso interposto, mantendo a sentença por seus próprios "
             "fundamentos. Publique-se. Intimem-se. Transitado em julgado, "
             "baixem-se os autos à origem.")},

        # C. lançamento de pauta, teor curto — não tem o que resumir, e o
        # cartão precisa DIZER isso, não inventar.
        {"id": "demo-c", "data": hoje_str, "numeroProcesso": cnj_c,
         "configConsultaRecorteId": ATITUDE, "lido": "não",
         "jornal": "DJEN", "tribunal": "TJPR", "vara": "Câmara Cível",
         "textoCompleto": (
             "Intimação referente ao movimento (seq. 12) INCLUSÃO EM PAUTA "
             "(20112026). Acesse o sistema Projudi para mais detalhes.")},

        # D. índice por advogados — numeroProcesso vem com a OAB, não um CNJ.
        # so_digitos() tem de rejeitar (só aceita 20 dígitos), e a linha não
        # pode virar intimação de verdade.
        {"id": "demo-d", "data": hoje_str, "numeroProcesso": "099001",
         "configConsultaRecorteId": ATITUDE, "lido": "não",
         "jornal": "DJEN", "tribunal": "TJPR", "vara": "",
         "textoCompleto": "Índice de publicações por advogado — OAB/PR 99.001"},

        # E. decisão real, mas a OBSERVAÇÃO do lançamento (abaixo) é que leva
        # o dado pessoal — sanitiza() precisa limpar antes do cartão nascer.
        {"id": "demo-e", "data": hoje_str, "numeroProcesso": cnj_e,
         "configConsultaRecorteId": ATITUDE, "lido": "não",
         "jornal": "DJEN", "tribunal": "TJPR", "vara": "Vara de Família",
         "textoCompleto": (
             "Intimação referente ao movimento (seq. 30) JUNTADA DE PETIÇÃO "
             "(20112026). Acesse o sistema Projudi para mais detalhes.")},
    ]

    # ------------------------------------------------------- LANÇAMENTOS ---
    lancamentos_hoje = [
        # B. dois lançamentos do MESMO movimento (seq. 80), prazos
        # diferentes — ED (5 dias, mais curto) e recurso (15 dias). O
        # agrupamento tem de virar um cartão só, usando o prazo mais próximo.
        {"assunto": (f"PROD | PRZ - {cnj_b} - Ciência do acórdão de mov. 80 - "
                     "Verificar eventual oposição de ED - CLIENTE FICTÍCIO"),
         "processo.pasta": cnj_b,
         "dataPrazoFatal": _fmt(hoje + timedelta(days=5)),
         "criadoPor.nome": "Fulana da Controladoria",
         "dataCadastro": f"{hoje_str} 09:14", "observacao": ""},
        {"assunto": (f"PROD | PRZ - {cnj_b} - Ciência do acórdão de mov. 80 - "
                     "Verificar eventual interposição de recurso - CLIENTE FICTÍCIO"),
         "processo.pasta": cnj_b,
         "dataPrazoFatal": _fmt(hoje + timedelta(days=15)),
         "criadoPor.nome": "Fulana da Controladoria",
         "dataCadastro": f"{hoje_str} 09:15", "observacao": ""},

        # C. PAT sem prazo fatal na origem — o cartão deve nascer sem
        # vencimento, mas SEM ser contado como defeito (a origem não trouxe).
        {"assunto": (f"PROD | PAT - {cnj_c} - Incluído em pauta de julgamento "
                     "do dia 20/11/2026 - CLIENTE FICTÍCIO"),
         "processo.pasta": cnj_c, "dataPrazoFatal": "",
         "criadoPor.nome": "Fulana da Controladoria",
         "dataCadastro": f"{hoje_str} 09:20", "observacao": ""},

        # E. PROV: a observação carrega a qualificação completa da parte —
        # com CPF — que o sanitiza.py tem de remover antes do cartão nascer.
        {"assunto": (f"PROD | PROV - {cnj_e} - Avaliar andamento processual - "
                     "CLIENTE FICTÍCIO"),
         "processo.pasta": cnj_e,
         "dataPrazoFatal": _fmt(hoje + timedelta(days=10)),
         "criadoPor.nome": "Fulana da Controladoria",
         "dataCadastro": f"{hoje_str} 09:25",
         "observacao": ("Qualificação: Fulano de Tal Exemplo, CPF "
                        "123.456.789-00, residente na Rua Fictícia, 123.")},
    ]

    return recorte_ontem, lancamentos_hoje, recorte_hoje
