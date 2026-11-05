#!/usr/bin/env python3
"""
Teste das regras medidas. Rodar SEMPRE antes de criar cartoes em lote:

    python3 teste_regras.py

Existe porque uma regra ja se perdeu entre um script e outro (14/09/2026):
a reescrita do titulo consolidado sumiu e 4 cartoes sairam errados, sem que
nada acusasse. Cada caso aqui veio de uma medicao real contra os cartoes da
controladoria — se um quebrar, a regra correspondente foi perdida ou alterada.

Nao acessa rede: testa so' as decisoes puras.
"""
import sys
from datetime import date
from consolida import (agrupa, eh_prz, folga_dias_uteis, preenche_prazo_fatal,
                       titulo_consolidado)
from cartao import fora_de_escopo, nota_interna, prefixo_de_quadro, sem_prefixo
from duplica_cartao import meu_cartao, fatia, LISTA
from fila_intimacoes import disponibilizacao
from prazo_util import calcula, recua_uteis

FALHAS = []


def checa(nome, obtido, esperado):
    if obtido != esperado:
        FALHAS.append(f"{nome}\n     esperado: {esperado!r}\n     obtido  : {obtido!r}")
    print(f"  {'ok ' if obtido == esperado else 'FALHOU'} {nome}")


# 1 — titulo consolidado (a regra que se perdeu)
checa("título consolidado reescreve a ação",
      titulo_consolidado("PRZ - 1 - Ciência do acórdão - Verificar eventual oposição de ED - X", 2),
      "PRZ - 1 - Ciência do acórdão - Verificar eventual providência / ED / recurso - X")
checa("título consolidado também cobre 'interposição de recurso'",
      titulo_consolidado("PRZ - 1 - Verificar eventual interposição de recurso - X", 2),
      "PRZ - 1 - Verificar eventual providência / ED / recurso - X")
checa("lançamento único NÃO tem título reescrito",
      titulo_consolidado("PRZ - 1 - Verificar eventual oposição de ED - X", 1),
      "PRZ - 1 - Verificar eventual oposição de ED - X")

# 2 — vencimento por tipo
checa("PRZ usa folga de 2 dias úteis", folga_dias_uteis("PRZ - 1 - x"), 2)
checa("PROV usa o próprio fatal", folga_dias_uteis("PROV - 1 - x"), 0)
checa("PAT usa o próprio fatal", folga_dias_uteis("PAT - 1 - x"), 0)
checa("AUD usa o próprio fatal", folga_dias_uteis("AUD - 1 - x"), 0)

# 3 — campo Prazo Fatal
checa("Prazo Fatal só em PRZ", preenche_prazo_fatal("PRZ - 1 - x"), True)
checa("Prazo Fatal não em PROV", preenche_prazo_fatal("PROV - 1 - x"), False)

# 4 — consolidação
_PRZ = lambda mv, f: {"assunto": f"PRZ - 0001234-95.2020.8.16.0001 - mov. {mv} - x",
                      "processo.pasta": "0001234-95.2020.8.16.0001", "dataPrazoFatal": f}
checa("dois PRZ do mesmo movimento viram um cartão",
      len(agrupa([_PRZ(10, "01/09/2026"), _PRZ(10, "15/09/2026")])), 1)
# ATENÇÃO: este caso já afirmou o contrário. Até 15/09/2026 o teste dizia que
# movimentos diferentes nunca agrupam — suposição escrita antes de medir. A
# medição (5 de 7 casos) mostrou que a controladoria consolida movimentos diferentes
# quando o PRAZO FATAL é o mesmo. O que não agrupa é movimento diferente COM
# fatal diferente.
checa("PRZ de movimentos E fatais diferentes NÃO agrupam",
      len(agrupa([_PRZ(10, "01/09/2026"), _PRZ(11, "20/09/2026")])), 2)
_AUD = lambda t: {"assunto": t, "processo.pasta": "0002-2.2020.8.16.0001",
                  "dataPrazoFatal": "01/10/2026"}
checa("providências de audiência NÃO agrupam (bug de 14/09)",
      len(agrupa([_AUD("AUD - 0002-2.2020.8.16.0001 - Audiência"),
                  _AUD("PROV - 0002-2.2020.8.16.0001 - Preparação"),
                  _AUD("PROV - 0002-2.2020.8.16.0001 - Substabelecimento")])), 3)

# 4-A — consolidação por prazo fatal (movimentos diferentes, mesmo prazo)
_MF = lambda mv, f: {"assunto": f"PRZ - 2222222-40.2020.8.16.0189 - Ciência de mov. {mv} - x",
                     "processo.pasta": "2222222-40.2020.8.16.0189", "dataPrazoFatal": f}
checa("movimentos diferentes com MESMO prazo fatal viram um cartão",
      len(agrupa([_MF(224, "17/08/2026"), _MF(226, "17/08/2026")])), 1)
checa("movimentos diferentes com prazos fatais diferentes NÃO agrupam",
      len(agrupa([_MF(224, "17/08/2026"), _MF(226, "25/08/2026")])), 2)
checa("título consolidado cita o segundo movimento",
      titulo_consolidado("PRZ - 1 - Ciência da decisão mov. 224 - Verificar - X", 2, ["226"]),
      "PRZ - 1 - Ciência da decisão mov. 224 e do mov. 226 - Verificar - X")

# 4-B — prefixo de quadro (decidido 24/09, mapa 25/09)
checa("PROD com PIPE entra", fora_de_escopo("PROD | PRZ - 0001234-95.2020.8.16.0001 - x - Y"), None)
# A equipe escreve com HÍFEN, não pipe: 36 de 36 lançamentos em 01/10/2026.
# A regex só aceitava pipe — todos passavam como "sem prefixo", em silêncio.
checa("PROD com HÍFEN entra (é como a equipe escreve)",
      fora_de_escopo("PROD - PRZ - 0001234-95.2020.8.16.0001 - x - Y"), None)
checa("prefixo com hífen é reconhecido",
      prefixo_de_quadro("PROD - PRZ - 0001234-95.2020.8.16.0001 - x - Y"), "PROD")
checa("PAR com hífen fica fora",
      fora_de_escopo("PAR - PRZ - 0001234-95.2020.8.16.0001 - x - Y"),
      "quadro PAR — fora do escopo deste projeto")
checa("sigla operacional NÃO é confundida com prefixo de quadro",
      prefixo_de_quadro("PRZ - 0001234-95.2020.8.16.0001 - x - Y"), None)
checa("prefixo com hífen é removido do nome",
      sem_prefixo("PROD - PRZ- 0001234-95.2020.8.16.0001 - x - Y"),
      "PRZ- 0001234-95.2020.8.16.0001 - x - Y")
checa("PAR fica fora", fora_de_escopo("PAR | PRZ - 0001234-95.2020.8.16.0001 - x - Y"),
      "quadro PAR — fora do escopo deste projeto")
checa("CONS fica fora", fora_de_escopo("CONS | PROV - 0001234-95.2020.8.16.0001 - x - Y"),
      "quadro CONS — fora do escopo deste projeto")
checa("sigla de quadro desconhecida é sinalizada, não ignorada",
      fora_de_escopo("XPTO | PRZ - 0001234-95.2020.8.16.0001 - x - Y"),
      "quadro XPTO — sigla desconhecida, conferir")
checa("lançamento SEM prefixo continua entrando (histórico anterior a 24/09)",
      fora_de_escopo("PRZ - 0001234-95.2020.8.16.0001 - x - Y"), None)
checa("filtro interno ainda vale com prefixo",
      fora_de_escopo("PROD | PTE - Pedido de Protocolo"), "fluxo interno (PTE)")
checa("com sigla PROD, trabalhista PASSA — a sigla manda",
      fora_de_escopo("PROD | PRZ - 3333333-84.2024.5.09.0005 - x - Y"), None)
checa("prefixo é removido do nome do cartão",
      sem_prefixo("PROD | PRZ - 0001234-95.2020.8.16.0001 - x - Y"),
      "PRZ - 0001234-95.2020.8.16.0001 - x - Y")
checa("título sem prefixo permanece intacto",
      sem_prefixo("PRZ - 0001234-95.2020.8.16.0001 - x - Y"),
      "PRZ - 0001234-95.2020.8.16.0001 - x - Y")

# 5 — escopo
# Sem sigla, NAO ha' o que decidir aqui: o tipo de processo nao diz o quadro.
checa("trabalhista sem sigla NÃO é barrado por tipo de processo",
      fora_de_escopo("PRZ - 3333333-84.2024.5.09.0005 - x"), None)
checa("PTE é fluxo interno", fora_de_escopo("PTE - Pedido de Protocolo"), "fluxo interno (PTE)")
checa("nota em minúscula não vira cartão",
      fora_de_escopo("ver lanc. intimação 08"), "nota interna, não é cartão")
checa("'Lançar eventos para a audiência' não vira cartão",
      fora_de_escopo("PROV - 0003-3.2026.8.16.0182 - Lançar eventos para a audiência - X"),
      "nota interna, não é cartão")
checa("PRZ estadual normal entra",
      fora_de_escopo("PRZ - 4444444-39.2025.8.16.0017 - x"), None)

# 6 — prazo: marco e contagem
c = calcula(date(2026, 8, 31), 5)
checa("publicação = 1º dia útil após disponibilização", c["publicacao"], date(2026, 9, 1))
checa("contagem inicia no dia útil seguinte", c["inicio"], date(2026, 9, 2))
checa("5 dias úteis pulando o feriado de 07/09", c["fatal"], date(2026, 9, 9))
checa("fatal -2 recua em dias úteis", recua_uteis(date(2026, 9, 14), 2), date(2026, 9, 10))

# 7 — duplicação: a fonte tem de ser cartão HUMANO (seção 2)
checa("cartão na minha lista é reconhecido como meu",
      meu_cartao({"idList": LISTA, "desc": "qualquer"}), True)
checa("cartão com minha assinatura é reconhecido como meu",
      meu_cartao({"idList": "outra", "desc": "... cartão de prazo gerado automaticamente ..."}), True)
checa("cartão da equipe NÃO é meu",
      meu_cartao({"idList": "outra", "desc": "**PROJUDI/TJPR**\n\n## Resumo da Decisão"}), False)
_FONTE = ("**PROJUDI/TJPR**\n\n0001-1.2020.8.16.0001\n\n"
          "## Resumo da Decisão\n\nteor ANTIGO que não pode viajar\n\n"
          "### :link: **LINK DOS DOCUMENTOS:**\n\nhttps://drive.google.com/x\n\n"
          "### :telephone: **CONTATOS CLIENTE:**\n\nfulano@x.com")
_cab, _perm = fatia(_FONTE)
checa("fatiador descarta o resumo anterior", "ANTIGO" in _cab, False)
checa("fatiador preserva o link da pasta", "drive.google.com" in _perm, True)
checa("fatiador preserva os contatos", "CONTATOS CLIENTE" in _perm, True)
checa("fatiador preserva o cabeçalho do sistema", "PROJUDI/TJPR" in _cab, True)

# 8 — normalização da data entre as fontes (seção 4)
_TXT_ALERTE = "2026-09-11 PR-JUD TJPRDN DJEN - disponibilizado em: 10/09/2026 ..."
checa("Alerte: usa a disponibilização escrita no texto",
      disponibilizacao("Alerte - Web Service", "11/09/2026", _TXT_ALERTE), "10/09/2026")
checa("AtitudeJur: usa o campo data",
      disponibilizacao("AtitudeJur Publicações", "11/09/2026", "texto qualquer"), "11/09/2026")
checa("Alerte sem a marca no texto cai para o campo",
      disponibilizacao("Alerte - Web Service", "11/09/2026", "sem a marca"), "11/09/2026")

# 9-A — cartão nunca nasce marcado como concluído (seção 13)
import inspect as _i, duplica_cartao as _dc, cartao as _c, pipeline as _p
checa("duplicação força dueComplete=false",
      'dueComplete="false"' in _i.getsource(_dc.cria), True)
checa("criação do zero força dueComplete=false",
      '"dueComplete": "false"' in _i.getsource(_c.criar), True)
checa("criação confere e corrige dueComplete herdado",
      'dueComplete' in _i.getsource(_c.criar) and 'atual.get("dueComplete")' in _i.getsource(_c.criar), True)
checa("pós-verificação acusa cartão concluído",
      "NASCEU MARCADO COMO CONCLUÍDO" in _i.getsource(_p._confere), True)

# 9 — nunca atribuir membro (seção 8)
import inspect, cartao
_src = inspect.getsource(cartao.criar)
checa("criar() nunca passa idMembers", "idMembers" in _src, False)

# 10 — janela de verificação (reescrita 09/10/2026 pelo limite real da API)
# O DataJuri publicou os limites em 02/10/2026: 120/min por token e
# 10.000/DIA por escritório. O teto diário é o que aperta — 1 chamada por
# segundo das 10h às 18h daria 29.028/dia e a cota acabaria às 12h44, ANTES
# do bloco 14h-18h que concentra 62% dos lançamentos.
# Intervalos agora em SEGUNDOS, alocados pela distribuição medida em 49 dias
# úteis (548 lançamentos em escopo).
from datetime import datetime as _dt
from janela import intervalo_em, chamadas_por_dia, dentro_do_limite, LIMITE_DIA
checa("pico das 16h-18h verifica a cada 3s", intervalo_em(_dt(2026,10,9,16,30)), 3)
checa("15h verifica a cada 3s", intervalo_em(_dt(2026,10,9,15,30)), 3)
checa("14h e 18h verificam a cada 5s", intervalo_em(_dt(2026,10,9,18,30)), 5)
checa("manhã cedo (6h e 7h) a cada 10 min",
      intervalo_em(_dt(2026,10,9,6,30)), 600)
checa("9h a cada 10s", intervalo_em(_dt(2026,10,9,9,30)), 10)
checa("noite (20h–23h) de hora em hora",
      intervalo_em(_dt(2026,10,9,21,0)), 3600)
checa("8h entra na janela — 4,2% dos lançamentos",
      intervalo_em(_dt(2026,10,9,8,30)), 10)
checa("19h ainda é verificado — 2,6% dos lançamentos",
      intervalo_em(_dt(2026,10,9,19,30)), 15)
checa("antes das 6h fica fora da janela", intervalo_em(_dt(2026,10,9,5,0)), None)
checa("depois das 23h fica fora da janela", intervalo_em(_dt(2026,10,9,23,30)), None)
checa("fim de semana fica fora da janela", intervalo_em(_dt(2026,10,10,16,0)), None)
checa("total de chamadas por dia útil", chamadas_por_dia(), 8415)
# A trava que importa: se alguem apertar a janela sem refazer a conta, a cota
# acaba no meio da tarde e os cartoes param de sair em silencio.
_cabe, _n, _pior = dentro_do_limite()
checa("a janela CABE no limite diário do DataJuri", _cabe, True)
checa("não estoura o limite por minuto", _pior <= 120, True)
# Folga de 1.585 chamadas (16%) depois de a usuária afrouxar o pico de 2s
# para 3s em 09/10/2026. Serve para retry de rede, para outra integração do
# escritório dividir a cota, e para dia atípico. Quem apertar a janela
# precisa refazer a conta inteira — o teste acima barra se estourar.
checa("sobra folga para retry", LIMITE_DIA - _n >= 300, True)

# 11 — cache de resumos pré-processados (30/09/2026)
import cache_resumos as _cr
from prepara_manha import tem_teor as _tem_teor
_cr.guardar("01/01/2000", [{"processo": "00011112220268160001", "movimento": "7",
                            "disponibilizacao": "01/01/2000", "resumo": "RESUMO-X"}])
checa("cache acha por processo+movimento",
      _cr.buscar("0001111-22.2026.8.16.0001", "7", None, "01/01/2000")[0], "RESUMO-X")
checa("cache normaliza o CNJ com máscara",
      _cr.buscar("00011112220268160001", "7", None, "01/01/2000")[0], "RESUMO-X")
checa("movimento diferente NÃO devolve resumo do cache",
      _cr.buscar("0001111-22.2026.8.16.0001", "99", None, "01/01/2000")[0], None)
checa("processo desconhecido NÃO devolve resumo do cache",
      _cr.buscar("0009999-99.2026.8.16.0009", "7", None, "01/01/2000")[0], None)
checa("dia diferente NÃO devolve resumo (validade de um dia)",
      _cr.buscar("0001111-22.2026.8.16.0001", "7", None, "02/01/2000")[0], None)
checa("publicação com teor é reconhecida", _tem_teor("D E C I S Ã O " + "x " * 600), True)
checa("publicação só com referência ao movimento NÃO é",
      _tem_teor("Intimação referente ao movimento (seq. 319) JUNTADA DE OFÍCIO "
                "(31/08/2026). Acesse o sistema Projudi do Tribunal para mais detalhes."),
      False)

# 12 — autoria do lançamento e limite do campo assunto (30/09/2026)
# O rodapé virou COMENTÁRIO em 29/10/2026 — as regras continuam valendo, só
# mudou o lugar: a descrição é para a decisão; procedência vai no histórico.
from rodape import comentario as _rod, CAMPOS_NECESSARIOS as _CN
_A = {"criadoPor.nome": "Marina Alves", "proprietario.nome": "Patrícia Souza",
      "encarregado.nome": "Rafael Lima", "dataCadastro": "30/09/2026 15:12"}
checa("comentário nomeia quem LANÇOU",
      "Lançado no DataJuri por: Marina Alves" in _rod(_A), True)
checa("comentário não confunde lançou com responsável",
      "Patrícia" in _rod(_A), False)
checa("comentário NÃO traz responsável — quem marca é a controladoria",
      "Responsável pela atividade" in _rod(_A), False)
checa("comentário NÃO traz revisor — quem marca é a controladoria",
      "Revisor (DataJuri)" in _rod(_A), False)

checa("autoria ausente é SINALIZADA, não omitida",
      "⚠️" in _rod({"proprietario.nome": "X"}), True)
checa("criadoPor.nome está na lista de campos obrigatórios", "criadoPor.nome" in _CN, True)

# limite do campo `assunto` do DataJuri: 200 caracteres (informado 30/09/2026).
# O titulo do cartao COPIA esse campo, entao nenhum titulo pode passar disso.
from consolida import titulo_consolidado as _tc
_LONGO = ("PROD | PRZ - 0001234-85.2026.8.16.0001 - Ciência da decisão de mov. 22 - "
          + "x" * 160 + " - CLIENTE")
checa("título que já cabe em 200 não é alterado por engano",
      len(_tc("PRZ - 0001 - x - Y", 1)) <= 200, True)
checa("consolidação não estoura 200 caracteres",
      len(_tc(_LONGO[:180], 2, ["99"])) <= 200 + 20, True)

# 13 — sanitização de dados pessoais (01/10/2026)
from sanitiza import sanitizar as _san, tem_dado_pessoal as _tdp
checa("CPF formatado é removido",
      _tdp("Fulano CPF 123.456.789-00 residente"), True)
checa("RG é removido", _tdp("cédula de identidade R.G. no 9.876.543-2"), True)
checa("CTPS é removida", _tdp("Carteira de Trabalho e Previdência Social no 12345 678"), True)
checa("CNJ NÃO é removido (é dado do caso)",
      _tdp("Processo 0001234-85.2026.8.16.0001"), False)
checa("OAB e valor NÃO são removidos",
      _tdp("OAB 99001PR, valor R$ 33.667,24"), False)
import inspect as _i2, cartao as _c2
checa("criar() sanitiza antes de gravar", "sanitizar(conteudo)" in _i2.getsource(_c2.criar), True)

# 14 — validacao de CNJ e deduplicacao entre dias (06/10/2026)
# Medido sobre o recorte de 02 e 05/10: 2 de 33 "intimacoes" eram linhas de
# INDICE POR ADVOGADOS, com a OAB no campo numeroProcesso; e 15 de 48
# registros eram a MESMA intimacao, vista na sexta pelo AtitudeJur e na
# segunda pelo Alerte.
from fila_intimacoes import so_digitos as _sd
checa("CNJ de 20 dígitos é aceito",
      _sd("8888888-90.2025.8.26.0002"), "88888889020258260002")
checa("CNJ já sem máscara continua aceito",
      _sd("88888889020258260002"), "88888889020258260002")
checa("OAB NÃO é aceita como processo (índice de advogados)", _sd("099001"), "")
checa("número curto NÃO é aceito como processo", _sd("2135"), "")
checa("vazio não vira processo", _sd(None), "")

import prepara_manha as _pm, inspect as _i3
checa("prepara_manha consulta os dias anteriores antes de resumir",
      "vistas_antes(dia)" in _i3.getsource(_pm.main), True)
checa("a chave entre dias inclui a disponibilização",
      'it.get("disponibilizacao")' in _i3.getsource(_pm.vistas_antes), True)
checa("repetida de dia anterior NÃO entra para resumir",
      'continue' in _i3.getsource(_pm.main).split("ja' vista em dia anterior")[1][:400],
      True)

# 15 — o prefixo de quadro NAO pode cegar a sigla operacional (09/10/2026)
# A sigla do quadro entrou nos lancamentos em 24/09. A partir dali
# consolida.eh_prz("PROD - PRZ - ...") respondia False, e levava junto
# agrupa(), folga_dias_uteis() e preenche_prazo_fatal(). Nada falhava: os
# cartoes nasciam sem agrupamento, sem Prazo Fatal e com vencimento errado.
import consolida as _cs
from consolida import eh_prz as _ep, agrupa as _ag
checa("eh_prz enxerga PRZ através do prefixo de quadro",
      _ep("PROD - PRZ - 5000001-15.2025.8.16.0029 - Ciência"), True)
checa("eh_prz continua valendo sem prefixo",
      _ep("PRZ - 5000001-15.2025.8.16.0029 - Ciência"), True)
checa("eh_prz NÃO confunde PROV com PRZ atrás do prefixo",
      _ep("PROD - PROV - 5000001-15 - Peticionar"), False)
checa("folga de 2 dias úteis sobrevive ao prefixo",
      folga_dias_uteis("PROD - PRZ - 1 - x"), 2)
checa("Prazo Fatal sobrevive ao prefixo",
      preenche_prazo_fatal("PROD - PRZ - 1 - x"), True)
_mesmo = [{"assunto": "PROD - PRZ - 1 - Ciência da decisão de mov. 47",
           "processo.pasta": "P1", "prazoFatal": "20/10/2026"},
          {"assunto": "PROD - PRZ - 1 - Ciência da decisão de mov. 47",
           "processo.pasta": "P1", "prazoFatal": "20/10/2026"}]
checa("dois PRZ com prefixo ainda agrupam num cartão só", len(_ag(_mesmo)), 1)
checa("consolida declara os campos que agrupa() precisa",
      set(_cs.CAMPOS_NECESSARIOS) >= {"processo.pasta", "dataPrazoFatal"}, True)
# Sem processo.pasta a duplicata LITERAL ainda protege (titulo identico +
# mesmo fatal). O que se perde e' o agrupamento inteligente de PRZ: dois
# movimentos DIFERENTES com o mesmo prazo fatal deveriam virar um cartao so',
# e viram dois. Dai os CAMPOS_NECESSARIOS acima.
_movs_dif = [{"assunto": "PROD - PRZ - 1 - Ciência da decisão de mov. 47",
              "dataPrazoFatal": "20/10/2026"},
             {"assunto": "PROD - PRZ - 1 - Ciência da certidão de mov. 49",
              "dataPrazoFatal": "20/10/2026"}]
checa("COM pasta, movimentos diferentes e mesmo fatal agrupam",
      len(_ag([dict(x, **{"processo.pasta": "P1"}) for x in _movs_dif])), 1)
checa("SEM pasta, o agrupamento de PRZ se perde (por isso os campos são exigidos)",
      len(_ag(_movs_dif)), 2)
checa("mas a duplicata literal protege mesmo sem pasta",
      len(_ag([{"assunto": "PRZ - 1 - x", "dataPrazoFatal": "20/10/2026"}] * 2)), 1)

# 16 — cartao sem vencimento tem de ser DENUNCIADO (09/10/2026)
# A pos-verificacao so' olhava o vencimento quando havia prazo_fatal. Um lote
# montado sem passar o fatal criava cartoes sem data e nada reclamava: 11 de 35
# no teste de 05-08/10, sendo que 9 teriam batido com o da Controladoria.
import inspect as _i4, pipeline as _pl
_src = _i4.getsource(_pl._confere)
checa("pós-verificação denuncia cartão sem vencimento",
      "SEM VENCIMENTO" in _src, True)
checa("a denúncia NÃO depende de haver prazo_fatal",
      _src.index("SEM VENCIMENTO") < _src.index("if prazo_fatal:"), True)
checa("folga por tipo vale para não-PRZ também (o próprio fatal)",
      folga_dias_uteis("PROV - 1 - x") == 0 and folga_dias_uteis("AUD - 1 - x") == 0,
      True)

# 17 — PARC e' o quadro de parceiros (09/10/2026, confirmado pela usuaria)
# Aparecia como "sigla desconhecida". Barrava — lado seguro — mas pelo motivo
# errado, e motivo errado no relatorio vira diagnostico errado depois.
from cartao import fora_de_escopo as _fe
checa("PARC é reconhecido como quadro de parceiros",
      "PARC" in (_fe("PARC - PRZ - 5555555-53.2024.5.09.0029 - x") or ""), True)
checa("PARC é barrado como quadro conhecido, não como sigla desconhecida",
      "desconhecida" in (_fe("PARC - PRZ - 5555555-53.2024.5.09.0029 - x") or ""), False)
checa("PAR continua barrado", "PAR" in (_fe("PAR - PRZ - 1 - x") or ""), True)
checa("PROD continua passando", _fe("PROD - PRZ - 0001234-95.2020.8.16.0001 - x"), None)

# 18 — o cartao NAO afirma como o prazo foi contado (09/10/2026)
# Correcao da usuaria: "ela esta' lancando a conta certinha no lancamento do
# prazo no DataJuri. sua tarefa e' COPIAR! no maximo fazer a conta de
# fatal - 1 ou fatal - 2". O cartao vinha citando CPC 224/219 e marco inicial
# — descrevendo uma contagem que nao foi feita aqui, e descrevendo ERRADO a
# dela se ela tiver contado por outro caminho.
from prazo_util import bloco_prazo as _bp
_b = _bp("21/10/2026")
# O texto "copiado do lançamento" saiu em 29/10/2026, a pedido da
# Controladoria: só as datas, sem explicação. A REGRA continua a mesma — o
# fatal vem do lançamento e nada aqui o calcula — só não é mais dita no cartão.
checa("o bloco traz as três datas", all(x in _b for x in ("fatal:", "−1", "−2")), True)
checa("bloco de prazo NÃO cita artigo do CPC",
      bool(_pl.RX_CONTAGEM.search(_b)), False)
checa("bloco de prazo traz fatal −1 e fatal −2", "−1" in _b and "−2" in _b, True)
checa("sem prazo fatal, o bloco SINALIZA em vez de inventar",
      "⚠️" in _bp(None), True)
checa("não-PRZ não ganha fatal −1/−2", "−2" in _bp("21/10/2026", folga=0), False)
checa("pós-verificação denuncia afirmação de método de contagem",
      bool(_pl.RX_CONTAGEM.search(
          "contagem inicia no dia útil seguinte (CPC 224)")), True)
checa("texto normal de decisão NÃO é confundido com método de contagem",
      bool(_pl.RX_CONTAGEM.search(
          "Intime-se a parte para manifestação em 15 dias úteis")), False)

# 19 — fatal -1 e fatal -2 sao em dias UTEIS (usuaria, 09/10/2026)
# ATENCAO a quem for "corrigir" isto depois: a MEDICAO apontava para o outro
# lado. Comparando 20 cartoes PRZ com os da Controladoria em 05-08/10/2026:
#
#     13/20 (65%)  fatal - 2 dias UTEIS      <- a regra
#     15/20 (75%)  fatal - 2 dias CORRIDOS, recuando para o dia util anterior
#
# A usuaria foi consultada com o caso concreto e confirmou DIAS UTEIS. A
# decisao dela vence a medicao: os 2 casos de diferenca tem outra explicacao
# (pareamento por CNJ pode casar com outro cartao do mesmo processo), e nao
# justificam trocar a regra.
#
# Caso que separa as duas hipoteses — prazo fatal em 13/10/2026 (terca), com
# o feriado de 12/10 (Nossa Senhora Aparecida) no meio:
#     -2 dias uteis   -> 08/10   <- correto
#     -2 dias corridos -> 09/10
from datetime import date as _d
checa("fatal −2 em dias ÚTEIS pula o feriado de 12/10",
      recua_uteis(_d(2026, 10, 13), 2), _d(2026, 10, 8))
checa("fatal −1 em dias úteis, mesmo caso",
      recua_uteis(_d(2026, 10, 13), 1), _d(2026, 10, 9))
checa("fatal −2 atravessa o fim de semana",
      recua_uteis(_d(2026, 10, 20), 2), _d(2026, 10, 16))
checa("o bloco de prazo usa a mesma conta em dias úteis",
      "08/10/2026" in _bp("13/10/2026"), True)

# 20 — o cartao consolidado usa o fatal MAIS PROXIMO (09/10/2026)
# A regra de agrupamento junta de proposito ED (5 dias) e recurso (15 dias):
# e' o mesmo trabalho de analise. Mas o cartao e' um so'. Pegar o fatal do
# primeiro item e' sorteio — a ordem vem da API. Se sair o maior, o cartao
# vence DEPOIS do prazo curto, e o prazo curto passa sem ninguem ver.
# Caso real do lote de 09/10/2026: acordao com ED em 20/10 e recurso em
# 04/11, e o primeiro item do grupo era o de 04/11.
from consolida import fatal_do_grupo as _fg
_grp = [{"assunto": "PRZ - 1 - Ciência do acórdão de mov. 309",
         "dataPrazoFatal": "04/11/2026"},
        {"assunto": "PRZ - 1 - Ciência do acórdão de mov. 309",
         "dataPrazoFatal": "20/10/2026"}]
checa("grupo com fatais diferentes usa o MAIS PRÓXIMO", _fg(_grp)[0], "20/10/2026")
checa("os outros fatais são devolvidos para o cartão citar",
      _fg(_grp)[1], ["04/11/2026"])
checa("ordem invertida dá o mesmo resultado (não é sorteio)",
      _fg(list(reversed(_grp)))[0], "20/10/2026")
checa("grupo de um item só devolve o próprio fatal",
      _fg([_grp[0]]), ("04/11/2026", []))
checa("grupo sem fatal nenhum não inventa data", _fg([{"assunto": "x"}]), (None, []))

# 21 — tocado_por_humano() recusa id invalido em vez de mentir (09/10/2026)
# Mora em duplica_cartao.py desde 09/10/2026 (veio de sincroniza_trello, que
# foi removido).
# Recebia o shortLink da URL ("wJggf0T1"), estourava na conversao hex e caia
# no `except: return True` — reportando "tocado por humano" para um cartao
# criado havia segundos. Falha segura, mas que diz o CONTRARIO do ocorrido:
# bloqueou a correcao de um cartao intocado e a mensagem culpou um humano.
from duplica_cartao import tocado_por_humano as _th
try:
    _th("wJggf0T1")
    _recusou = False
except ValueError:
    _recusou = True
checa("shortLink é RECUSADO, não tratado como toque humano", _recusou, True)
try:
    _th("")
    _vazio = False
except ValueError:
    _vazio = True
checa("id vazio também é recusado", _vazio, True)

# 22 — nao existe outro caminho para criar cartao (09/10/2026)
# sincroniza_trello.py era o fluxo antigo, anterior as travas. Criava cartao
# com um POST direto: sem pre-voo, sem remocao da sigla de quadro, sem
# sanitizacao de CPF, sem pos-verificacao. E rodava com um comando.
# De 392 linhas, so' duas funcoes ainda eram usadas — foram para prefixo.py
# e duplica_cartao.py, e o arquivo foi removido.
# Este teste existe para o caminho nao reaparecer: qualquer modulo que faca
# POST /cards fora de cartao.criar() e' porta dos fundos.
import os as _os, re as _re2
_PERMITIDOS = {"cartao.py", "duplica_cartao.py", "teste_regras.py"}
_portas = []
for _f in _os.listdir(_os.path.dirname(_os.path.abspath(__file__)) or "."):
    if not _f.endswith(".py") or _f in _PERMITIDOS:
        continue
    _s = open(_f).read()
    if _re2.search(r'["\']\/cards["\']\s*,\s*(metodo|method)?\s*=?\s*["\']POST', _s):
        _portas.append(_f)
checa("nenhum módulo cria cartão fora de cartao.criar()", _portas, [])
checa("sincroniza_trello.py não existe mais",
      _os.path.exists("sincroniza_trello.py"), False)
checa("tocado_por_humano mora em duplica_cartao.py",
      hasattr(__import__("duplica_cartao"), "tocado_por_humano"), True)

# 23 — SO' a sigla decide o quadro (15/10/2026)
#   "nao e' tua funcao escolher para onde vai o lancamento, e' funcao dela e
#    ela ja' resolveu isso por voce"
# A divisao entre quadros e' OPERACIONAL, a criterio da Controladoria: o de
# parceiros recebe trabalhista, familia e outros assuntos. O numero do
# processo nao carrega esse criterio.
# Media do estrago antes da correcao: em 853 lancamentos (01/09 a 15/10), 2
# marcados PROD foram BARRADOS por um filtro de ramo do CNJ — o trabalho dela
# descartado em silencio.
checa("PROD em processo trabalhista PASSA — a sigla manda",
      _fe("PROD - PRZ - 6666666-62.1999.5.09.0009 - Ciência do despacho"), None)
checa("PARC é barrado pela SIGLA, não pelo tipo de processo",
      "PARC" in (_fe("PARC - PRZ - 6666666-62.1999.5.09.0009 - x") or ""), True)
checa("PARC em processo ESTADUAL também é barrado — é a sigla que manda",
      "PARC" in (_fe("PARC - PRZ - 0001234-95.2020.8.16.0001 - x") or ""), True)
checa("PROD estadual continua passando",
      _fe("PROD - PRZ - 0001234-95.2020.8.16.0001 - x"), None)
# A trava de verdade: nenhum modulo pode voltar a adivinhar o quadro pelo
# numero do processo. "nao e' tua funcao escolher para onde vai o lancamento"
import os as _os3, re as _re3
_adivinha = []
for _f in _os3.listdir(_os3.path.dirname(_os3.path.abspath(__file__)) or "."):
    if not _f.endswith(".py") or _f == "teste_regras.py":
        continue
    _s = open(_f).read()
    if _re3.search(r"def (ramo_do_cnj|fora_do_escopo)\b", _s):
        _adivinha.append(_f)
checa("nenhum módulo adivinha o quadro pelo número do processo", _adivinha, [])

# 24 — lancamento sem sigla de quadro nasce AVISADO (15/10/2026)
# Decisao da usuaria: passa como PROD, mas o cartao diz no topo da descricao
# que o destino nao foi confirmado. Medido na semana de 09-15/10: 11 de 75
# lancamentos (15%) tinham sigla operacional mas nenhuma sigla de quadro.
from cartao import AVISO_SEM_SIGLA as _av
import inspect as _i5, cartao as _ct
_src_criar = _i5.getsource(_ct.criar)
checa("criar() avisa quando não há sigla de quadro",
      "prefixo_de_quadro(assunto) is None" in _src_criar, True)
checa("o aviso vai no TOPO do conteúdo, não no rodapé",
      "AVISO_SEM_SIGLA + " in _src_criar, True)
checa("o aviso diz onde o cartão foi criado",
      "Produção Jurídica" in _av, True)
checa("o aviso pede confirmação do destino",
      "confirmar" in _av.lower(), True)
checa("o aviso é visível (⚠️)", "⚠️" in _av, True)
# com sigla, nao avisa: o destino foi decidido
checa("cartão COM sigla não leva o aviso",
      _av in _ct.criar.__doc__ if _ct.criar.__doc__ else False, False)

# 25 — o PROGRAMA DO DIA (rotina.py) e o que ele nao pode fazer (15/10/2026)
# Ate' 15/10 as pecas existiam mas quem as amarrava era uma PESSOA, digitando
# no terminal. No servidor nao ha' ninguem digitando — e todos os defeitos de
# 09 e 15/10 nasceram ali: campos nao pedidos, prazo fatal do item errado,
# texto afirmando contagem que nao foi feita.
# Estes testes garantem que a rotina nao refaca o que ja' foi proibido.
import inspect as _i6, rotina as _rt
_rot = _i6.getsource(_rt)
checa("a rotina usa consolida.agrupa (não agrupa por conta própria)",
      "agrupa(escopo)" in _rot, True)
checa("a rotina usa fatal_do_grupo (não pega o fatal do primeiro item)",
      "fatal_do_grupo(g)" in _rot, True)
# O bloco de datas saiu da descrição em 29/10/2026 — a rotina não o usa mais.
checa("a rotina NÃO escreve bloco de datas na descrição",
      "bloco_prazo(" in _rot, False)
checa("a rotina NÃO afirma método de contagem",
      bool(_pl.RX_CONTAGEM.search(_rot)), False)
# A autoria saiu do rodapé e foi para o COMENTÁRIO do cartão (29/10/2026).
checa("a rotina monta o comentário de autoria", "comentario(" in _rot, True)
checa("a rotina sanitiza antes de mandar texto ao modelo",
      "sanitizar(" in _rot, True)
checa("a rotina cria SÓ pelo pipeline", "executar(itens" in _rot, True)
checa("a rotina NÃO decide quadro pelo tipo de processo",
      bool(_re3.search(r"ramo_do_cnj|fora_do_escopo", _rot)), False)
checa("a rotina pede os campos que consolida exige",
      "CAMPOS_CONSOLIDA" in _rot, True)
checa("a rotina pede os campos que o rodapé exige",
      "CAMPOS_RODAPE" in _rot, True)
# o modelo e' falivel: sem resumo, SINALIZA — nao inventa
import modelo as _md
checa("modelo.resumir devolve None em texto curto (não inventa)",
      _md.resumir("x" * 50), None)
checa("a rotina sinaliza quando o resumo não sai",
      "Resumo não gerado" in _rot, True)
# Ajustado em 15/10/2026 depois do primeiro teste com o código sozinho.
checa("o prompt proíbe afirmar como o prazo foi contado",
      "NUNCA diga como o prazo foi contado" in _md.INSTRUCAO, True)
checa("o prompt cita os artigos de contagem que não podem aparecer",
      all(a in _md.INSTRUCAO for a in ("219", "224", "231")), True)
checa("o prompt exige datas completas",
      "Datas SEMPRE completas" in _md.INSTRUCAO, True)
# O ⚠️ so' quando nao ha' NADA. Metade dos cartoes nascia avisado no teste de
# 08/10, varios avisando E resumindo ao mesmo tempo — ruido repetido ensina a
# ignorar o aviso, inclusive o verdadeiro.
checa("o prompt manda resumir em vez de avisar, quando há informação",
      "NÃO use ⚠️" in _md.INSTRUCAO, True)
checa("o prompt restringe o ⚠️ ao caso sem nada a resumir",
      "APENAS quando não houver absolutamente nada" in _md.INSTRUCAO, True)
checa("o prompt continua proibindo dado pessoal",
      "NÃO repita CPF" in _md.INSTRUCAO, True)

# 26 — nao truncar o titulo ao mandar para o modelo (15/10/2026)
# Encontrado no primeiro teste com o codigo rodando sozinho. A rotina mandava
# o titulo cortado em 90 caracteres e o corte caiu no meio de uma data:
#
#     "...Audiencia de conciliacao virtual designada para dia 25/1"
#                                                               ^ cortado
#
# O titulo completo dizia 25/11/2026. O modelo, obedecendo a regra nova de
# "datas sempre completas", devolveu 25/01/2027 — data ERRADA num cartao de
# prazo. A regra criada para evitar data pela metade produziu data errada.
# O titulo do DataJuri cabe em 200 caracteres: mandar inteiro e' barato.
import inspect as _i7, rotina as _rt2, modelo as _md2
checa("a rotina manda o título INTEIRO ao modelo",
      "sem_prefixo(assunto))" in _i7.getsource(_rt2.lancamentos), True)
checa("a rotina não corta o título em 90 caracteres",
      "sem_prefixo(assunto)[:90]" in _i7.getsource(_rt2.lancamentos), False)
checa("o prompt proíbe completar data incompleta",
      "NÃO a complete" in _md2.INSTRUCAO, True)
checa("o prompt diz o que fazer com data cortada: omitir",
      "omita a data" in _md2.INSTRUCAO, True)
_t149 = ("AUD – 7777777-66.2026.8.16.0001 - Audiência de conciliação virtual "
         "designada para dia 25/11/2026 às 10:20 - CLIENTE (Fulano)")
checa("título real de 149 caracteres cabe no contexto sem corte",
      len(_t149) <= 400, True)
checa("o limite do contexto é maior que o limite do assunto no DataJuri",
      400 > 200, True)

# 27 — cartao de AUDIENCIA (15/10/2026), medido em 90 cartoes do quadro oficial
#   98% trazem sistema e numero · 77% contatos · 76% Drive · 66% link de
#   acesso · 50% chave da audiencia · apenas 6% alguma exigencia do ato.
# A descricao de audiencia e' OPERACIONAL, nao analitica. O titulo ja' diz
# tipo, data e hora — repetir isso no resumo foi o que gerou a data errada
# (25/01/2027 em vez de 25/11/2026).
# Chave e link so' existem no sistema do tribunal, que o projeto nao acessa:
# o cartao nasce incompleto e TEM de dizer isso.
import audiencia as _ad
checa("AUD é reconhecido", _ad.eh_audiencia("AUD - 0001 - Audiência de conciliação"), True)
checa("PRZ não é audiência", _ad.eh_audiencia("PRZ - 0001 - Ciência"), False)
checa("modalidade virtual", _ad.modalidade("AUD - 1 - Audiência Virtual"), "virtual")
checa("semipresencial não é confundido com presencial",
      _ad.modalidade("AUD - 1 - Audiência Semipresencial"), "semipresencial")
checa("presencial NÃO recebe aviso de chave/link",
      _ad.falta_completar("AUD - 1 - Audiência de conciliação presencial"), None)
checa("virtual RECEBE aviso de chave/link",
      "chave da audiência" in (_ad.falta_completar("AUD - 1 - Audiência Virtual") or ""), True)
checa("modalidade não declarada recebe aviso (70 de 90 são virtuais)",
      _ad.falta_completar("AUD - 1 - Audiência de conciliação") is not None, True)
checa("PRZ nunca recebe aviso de audiência",
      _ad.falta_completar("PRZ - 1 - Ciência da decisão"), None)
# o prompt de audiencia nao pode repetir o titulo
checa("prompt de audiência proíbe repetir tipo, data e hora",
      "não repita o tipo, a data ou a hora" in _md.INSTRUCAO_AUDIENCIA.lower(), True)
checa("prompt de audiência pede exigências do ato",
      all(p in _md.INSTRUCAO_AUDIENCIA for p in ("testemunhas", "preposto", "provas")), True)
checa("prompt de audiência tem saída explícita para 'nada a dizer'",
      "SEM EXIGENCIAS" in _md.INSTRUCAO_AUDIENCIA, True)
checa("resumir_audiencia devolve None em texto curto", _md.resumir_audiencia("x"*40), None)
checa("a rotina trata audiência por caminho próprio",
      "audiencia.eh_audiencia" in _i7.getsource(_rt2.lancamentos), True)
# O bloco de datas saiu da descrição; o vencimento continua vindo da folga
# por tipo, aplicada dentro de cartao.criar().
checa("audiência usa o próprio fatal como vencimento (folga 0)",
      folga_dias_uteis("AUD - 1 - Audiência"), 0)

# 28 — as tres conferencias de fim de dia (15/10/2026)
# Falam por EXCECAO: dia limpo nao produz nada. Medido em 4 dias (06-09/10):
# 3, 1, 2 e 0 avisos — media de 1,5/dia. O dia 09/10 produziu silencio.
#
# Dois defeitos corrigidos no primeiro teste delas:
#
# 1. FONTE UNICA dava 15 avisos num dia, contra ~0,9/dia medido em 25 dias
#    uteis. Todos eram "so' pelo AtitudeJur" — o Alerte entrega a MESMA
#    intimacao no dia seguinte, e olhar so' o recorte do proprio dia acusa
#    o Alerte de nao ter trazido algo que ele ainda vai trazer.
#
# 2. LANCADO SEM CARTAO comparava TITULO e acusava cartao consolidado: dois
#    lancamentos (mov 100 e mov 84) viram um cartao, cujo titulo leva so' um
#    movimento. Agora compara processo+movimento E le o campo "cobre" do
#    historico, que diz quais lancamentos cada cartao cobriu.
_rotsrc = _i7.getsource(_rt2.noite)
checa("conferência de fonte única espera o Alerte atrasar",
      "DIAS_ESPERA_ALERTE" in _rotsrc, True)
checa("só avisa de intimação DISPONIBILIZADA no dia conferido",
      'k[2] == dia' in _rotsrc, True)
checa("conferência de cartão compara processo + movimento",
      "_mov(a)) not in meus" in _rotsrc, True)
checa("conferência lê a cobertura registrada no histórico",
      'c.get("cobre"' in _rotsrc, True)
checa("as três conferências existem",
      all(x in _rotsrc for x in ("fonte única", "lançado sem cartão", "sem_lancamento")),
      True)
checa("o pipeline registra quais lançamentos cada cartão cobre",
      '"cobre": it.get("lancamentos")' in _i6.getsource(_pl), True)
checa("a rotina passa os lançamentos do grupo ao pipeline",
      '"lancamentos": [x.get("assunto") for x in g]' in _rot, True)
# o cartao consolidado cobre TODOS os movimentos do grupo
_g = [{"assunto": "PRZ - 9999999-49.2026.8.16.0182 - Ciência da decisão de mov. 100",
       "processo.pasta": "P", "dataPrazoFatal": "20/10/2026"},
      {"assunto": "PRZ - 9999999-49.2026.8.16.0182 - Ciência da decisão de mov. 84",
       "processo.pasta": "P", "dataPrazoFatal": "20/10/2026"}]
checa("dois movimentos do mesmo processo viram UM cartão", len(_ag(_g)), 1)

# 29 — titulo generico nao pode gerar falso positivo de duplicata (15/10/2026)
# Achado no primeiro teste de criacao pelo caminho automatico. O lancamento de
# 14/10 se chamava apenas "Audiência" — sem CNJ, sem sigla, sem cliente — e a
# trava barrou a criacao porque ja' havia no quadro um cartao de teste antigo
# com esse mesmo nome, de OUTRO processo. O lancamento foi descartado calado.
# Ha' 8 cartoes de nome curto no quadro, entao a colisao nao e' remota.
# Regra: titulo com CNJ identifica sozinho; titulo generico so' e' duplicata
# se o PROCESSO bater. Sem processo para comparar, NAO barra — criar cartao a
# mais e' visivel e corrigivel; descartar lancamento e' invisivel.
import inspect as _i8, duplica_cartao as _dc2
_src_jc = _i8.getsource(_dc2.ja_criei)
checa("ja_criei recebe o processo", "processo=None" in _src_jc, True)
checa("título genérico é detectado", "generico = " in _src_jc, True)
checa("genérico só barra se o processo bater", "if not proc_alvo:" in _src_jc, True)
checa("criar() passa o processo para a trava",
      "dc.ja_criei(nome, processo)" in _i2.getsource(_c2.criar), True)
# a regra em si: o que torna um título identificável é trazer o CNJ
_rxc = __import__("re").compile(r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}")
checa("título com CNJ identifica o lançamento sozinho",
      bool(_rxc.search("PRZ - 0001234-95.2020.8.16.0001 - Ciência")), True)
checa("'Audiência' não identifica nada sozinho",
      bool(_rxc.search("Audiência")), False)
checa("o código usa o CNJ como critério, não o tamanho",
      "alvo_cnj is None" in _src_jc, True)

# 30 — "sem vencimento" nem sempre e' defeito (15/10/2026, teste cego)
# Dois lancamentos "Audiência" vieram do DataJuri com dataPrazoFatal VAZIO.
# O cartao nasceu certo — sem data, e DIZENDO no corpo que nao havia data —
# e mesmo assim foi reportado como "cartao que nasceu com defeito".
#
# Se isso ficasse assim, todo lancamento sem prazo entraria na lista de
# defeitos, e a lista perderia valor: o mesmo erro do ⚠️ em excesso corrigido
# horas antes. Distinguir a CAUSA:
#     o codigo errou         -> defeito, tem de ser corrigido
#     o lancamento nao traz  -> dado de origem, o cartao ja' avisa no corpo
_src_cf = _i6.getsource(_pl._confere)
checa("a pós-verificação sabe se o lançamento tinha prazo fatal",
      "sem_fatal_na_origem" in _src_cf, True)
checa("sem vencimento só é defeito quando a origem TINHA prazo",
      "if not sem_fatal_na_origem:" in _src_cf, True)
checa("o pipeline informa a origem ao conferir",
      "sem_fatal_na_origem=not" in _i6.getsource(_pl), True)
checa("o relatório conta à parte os sem prazo na origem",
      "sem prazo fatal no lançamento" in _i6.getsource(_pl), True)
# e o cartao continua avisando no corpo, que e' onde a Controladoria ve'
checa("bloco de prazo sinaliza ausência em vez de inventar",
      "⚠️" in _bp(None) and "Sem prazo fatal" in _bp(None), True)

# 31 — um lancamento problematico nao derruba o dia (16/10/2026)
# Encontrado com o vigia ja' rodando: a CONSULTA estava protegida, o
# PROCESSAMENTO nao. Qualquer excecao no meio — modelo lento, Trello
# recusando, dado estranho — mataria o processo e os lancamentos seguintes
# se perderiam em silencio, ate' alguem notar que o servico nao estava de pe'.
_vig = _i7.getsource(_rt2.vigia)
checa("a consulta ao DataJuri é protegida", _vig.count("try:") >= 1, True)
checa("o PROCESSAMENTO também é protegido",
      "rel = lancamentos(dia, tk, criar=criar)" in
      _vig.split("try:")[-1].split("except")[0] or
      _vig.count("try:") >= 2, True)
checa("falha de processamento é contada e reportada",
      "falhas_proc" in _vig, True)
checa("depois da falha, o lançamento é retentado no ciclo seguinte",
      "vistos = set()" in _vig, True)
checa("o loop respeita a janela", "janela.intervalo_em(agora)" in _vig, True)
checa("o loop tem hora para encerrar", "(hlim, mlim)" in _vig, True)

# 32 — o que derrubou o dia de 16/10/2026, e o que nasceu mudo
#
# A) TIMEOUT SEM RETRY. As 17h40 uma leitura do Trello estourou o tempo e
#    MATOU o processo do dia, 20 min antes do fim. A chamada de duplicata
#    percorre 3.535 cartoes, e `ja_criei` e' chamada uma vez por cartao do
#    lote — um lote de 6 baixava a lista 6 vezes, alguns megabytes cada.
# B) SIGLA SEM ETIQUETA. Um lancamento "VER - ..." nasceu sem etiqueta: a
#    sigla nao esta' no mapa. Sem etiqueta o cartao some dos filtros do
#    quadro, que e' como a equipe trabalha.
import duplica_cartao as _dc3
_tr = _i8.getsource(_dc3.trello)
checa("a chamada ao Trello tenta de novo quando a rede falha",
      "for tentativa in range" in _tr, True)
checa("a espera entre tentativas é crescente", "3 ** tentativa" in _tr, True)
checa("erro HTTP NÃO é retentado (é resposta, não falha de rede)",
      "except urllib.error.HTTPError:" in _tr and "raise" in _tr, True)
checa("existe cache da lista de cartões", hasattr(_dc3, "cartoes_do_quadro"), True)
checa("o cache tem validade curta",
      "< 60" in _i8.getsource(_dc3.cartoes_do_quadro), True)
checa("ja_criei usa o cache, não baixa 3.535 cartões a cada chamada",
      "cartoes_do_quadro()" in _i8.getsource(_dc3.ja_criei), True)
# sigla sem etiqueta: avisa em vez de nascer mudo
checa("existe aviso para sigla sem etiqueta",
      hasattr(_c2, "AVISO_SEM_ETIQUETA"), True)
checa("criar() aplica o aviso quando não acha etiqueta",
      "if not lb:" in _i2.getsource(_c2.criar), True)
checa("o aviso diz para classificar manualmente",
      "classificar" in _c2.AVISO_SEM_ETIQUETA, True)
# VER = VRF: confirmado pela usuaria em 19/10/2026, DEPOIS de perguntar.
# O cartao de 16/10 nasceu sem etiqueta de proposito — adivinhar equivalencia
# de sigla seria o mesmo erro do filtro por ramo do CNJ, removido em 15/10.
checa("VER foi mapeada para VRF (confirmado, não adivinhado)",
      any(s == "VER" for s, _ in _c2._ETIQUETAS), True)
checa("VRF também mapeia para a mesma etiqueta",
      any(s == "VRF" for s, _ in _c2._ETIQUETAS), True)
checa("sigla desconhecida continua sem etiqueta, e avisando",
      any(s == "XYZ" for s, _ in _c2._ETIQUETAS), False)

# 33 — a memoria do vigia e' CUMULATIVA, porque a fonte e' instavel (19/10/2026)
# A API do DataJuri devolve quantidades DIFERENTES para a mesma consulta, em
# segundos: 9 → 10 → 12 → 11 → 12 → 11, oscilando para cima e para baixo. E
# lancamento nao desaparece — e' inconsistencia de leitura do lado deles.
# Com memoria de retrato (`vistos = agora_ids`), qualquer oscilacao fazia um
# lancamento ja' processado reaparecer como novo: 1 lancamento processado 40+
# vezes em 5 minutos, gastando modelo e cota de API. Nenhum cartao duplicado
# saiu — a trava segurou — mas o desperdicio foi real.
checa("a memória do vigia acumula, não substitui",
      "vistos |= agora_ids" in _vig, True)
# procurar na LINHA DE CÓDIGO, não no comentário que explica o defeito
_linhas_cod = [l.split("#")[0] for l in _vig.split(chr(10))]
checa("não existe mais substituição do retrato",
      any("vistos = agora_ids" in l for l in _linhas_cod), False)
checa("falha de processamento esquece SÓ os que falharam",
      "vistos -= frescos" in _vig, True)
# a regra em si, contra uma fonte que oscila:
def _simula(acumula):
    leituras = [{"a","b","c"}, {"a","b"}, {"a","b","c","d"}, {"a","c","d"}]
    vistos, n = set(), 0
    for ag in leituras:
        fr = ag - vistos
        if vistos and fr:
            n += len(fr)
        vistos = (vistos | ag) if acumula else ag
    return n
checa("memória cumulativa processa cada lançamento UMA vez", _simula(True), 1)
checa("memória de retrato reprocessaria (o defeito)", _simula(False) > 1, True)

# 34 — o cache nao pode virar janela de duplicacao (19/10/2026)
# Dois cartoes identicos nasceram com 56 SEGUNDOS de diferenca, dentro da
# validade de 60s do cache de cartoes. Quando o segundo foi verificado,
# `ja_criei` consultou uma lista anterior a' existencia do primeiro.
# O cache foi introduzido no dia anterior para resolver um timeout: resolveu,
# e abriu este buraco. Toda criacao alimenta o cache na hora.
checa("existe função para registrar cartão novo no cache",
      hasattr(_dc3, "registrar_novo"), True)
checa("criar() alimenta o cache após criar",
      "dc.registrar_novo(novo)" in _i2.getsource(_c2.criar), True)
# comportamento: registrar faz o proximo ja_criei enxergar
_dc3._CACHE_CARTOES["dados"] = [{"name": "X", "desc": "", "shortUrl": "u", "idList": "l"}]
_antes = len(_dc3._CACHE_CARTOES["dados"])
_dc3.registrar_novo({"name": "PRZ - 0001234-95.2020.8.16.0001 - novo",
                     "shortUrl": "u2", "idList": "l", "desc": ""})
checa("registrar_novo acrescenta ao cache",
      len(_dc3._CACHE_CARTOES["dados"]) - _antes, 1)
checa("o cartão registrado é encontrado pela trava",
      any("0001234-95" in c["name"] for c in _dc3._CACHE_CARTOES["dados"]), True)
_dc3._CACHE_CARTOES["dados"] = None      # limpa, para não afetar outros testes

# 35 — os dois buracos que o mutation testing encontrou (20/10/2026)
# Introduzindo 15 bugs de proposito, a suite pegou 12. Os dois reais que
# passaram:
#
#   A) "CPF deixa de ser removido" — os testes chamavam tem_dado_pessoal()
#      (que DETECTA) e nunca sanitizar() (que REMOVE). Quebrar a remocao nao
#      quebrava teste nenhum.
#   B) "sigla operacional confundida com sigla de quadro" — se
#      prefixo_de_quadro("PRZ - ...") devolvesse "PRZ" em vez de None, TODO
#      lancamento sem prefixo seria lido como sigla desconhecida e BARRADO,
#      em silencio. E' a familia de defeito que mais custou neste projeto.
from sanitiza import sanitizar as _sanit
from prefixo import prefixo_de_quadro as _pq
checa("sanitizar REMOVE o CPF do texto devolvido",
      "123.456.789-00" in _sanit("Fulano CPF 123.456.789-00 residente")[0], False)
checa("sanitizar REMOVE o RG",
      "9.876.543-2" in _sanit("cédula de identidade R.G. no 9.876.543-2")[0], False)
checa("sanitizar REMOVE CPF colado em CNPJ (caso real de 14/09)",
      "428.647.668-50" in _sanit("(RG 134321032 e CPFCNPJ 428.647.668-50)")[0], False)
checa("sanitizar NÃO remove o CNJ",
      "0001234-95.2020.8.16.0001" in _sanit("Processo 0001234-95.2020.8.16.0001")[0], True)
checa("sanitizar NÃO remove valor em reais",
      "33.667,24" in _sanit("valor de R$ 33.667,24")[0], True)
checa("sanitizar devolve texto, não None", isinstance(_sanit("x")[0], str), True)

# B) sigla operacional NUNCA é lida como sigla de quadro
for _s in ("PRZ", "PROV", "AUD", "PAT", "DIL", "VRF", "PER", "NEG"):
    checa(f"{_s} não é confundido com sigla de quadro",
          _pq(f"{_s} - 0001234-95.2020.8.16.0001 - texto"), None)
checa("PROD seguido de sigla operacional É sigla de quadro",
      _pq("PROD - PRZ - 0001234-95.2020.8.16.0001 - x"), "PROD")
checa("sem sigla nenhuma devolve None",
      _pq("Audiência de conciliação"), None)
# O caso que de fato ALCANÇA a linha que decide: a regex só casa quando a
# sigla vem seguida de OUTRA sigla operacional. Sem este teste, trocar
# `return None if sig in _SIGLAS_OPERACIONAIS else sig` por `return sig`
# passava despercebido — e aí TODO lançamento "PRZ - PROV - ..." seria lido
# como quadro desconhecido e barrado em silêncio.
checa("PRZ seguido de PROV: PRZ não é sigla de quadro",
      _pq("PRZ - PROV - 0001234-95.2020.8.16.0001 - x"), None)
checa("PROV seguido de PRZ: PROV não é sigla de quadro",
      _pq("PROV - PRZ - 0001234-95.2020.8.16.0001 - x"), None)
checa("AUD seguido de PAT: AUD não é sigla de quadro",
      _pq("AUD - PAT - 0001234-95.2020.8.16.0001 - x"), None)
checa("mas PROD seguido de PRZ É sigla de quadro",
      _pq("PROD - PRZ - 0001234-95.2020.8.16.0001 - x"), "PROD")

# 36 — o teor colado pela Controladoria tem prioridade (29/10/2026)
# Decidido com a controladoria em 24/09: quando a intimacao vem SEM teor, a equipe
# cola a decisao na observacao do lancamento. Cobre o terco das intimacoes
# que so' trazem a referencia ao movimento.
#
# Estava implementado ERRADO desde entao:
#
#     teor = recorte or observacao
#
# O `or` so' cai na observacao se o recorte estiver VAZIO. Mas intimacao sem
# teor nao vem vazia — vem com "Intimação referente ao movimento (seq. 47).
# Acesse o sistema Projudi". Como nao e' vazio, a observacao NUNCA era lida,
# e o trabalho de colar o teor era jogado fora. Medido em 27/10/2026: dois
# casos num unico dia.
from prepara_manha import tem_teor as _tt
_src_lanc = _i7.getsource(_rt2.lancamentos)
checa("a rotina decide pelo CONTEÚDO, via teor.escolher",
      "teor_mod.escolher" in _src_lanc, True)
checa("sem teor na publicação, conta que usou a observação",
      'origem_teor == "observacao"' in _src_lanc, True)
checa("o relatório diz quantos usaram o teor colado",
      "teor colado pela equipe" in _src_lanc, True)
# a regra mora em teor.py, nao espalhada pela rotina
import teor as _teor
checa("teor.py declara observacao como campo obrigatório",
      "observacao" in _teor.CAMPOS_NECESSARIOS, True)
checa("a rotina pede o campo observacao na consulta",
      "observacao" in _rt2.CAMPOS, True)
checa("a rotina usa teor.escolher, não decide por conta própria",
      "teor_mod.escolher" in _src_lanc, True)
# comportamento da regra oficial de 24/09
_ref = ("Processo 44444443920258160017 Intimação referente ao movimento "
        "(seq. 47) JUNTADA DE PETIÇÃO. Acesse o sistema Projudi.")
_dec = "Vistos. " + "O juízo decide sobre o pedido da parte. " * 60
checa("publicação SEM teor + observação longa -> usa a OBSERVAÇÃO",
      _teor.escolher(_ref, "x" * 500)[1], "observacao")
checa("publicação COM teor -> usa o RECORTE mesmo havendo observação",
      _teor.escolher(_dec, "x" * 500)[1], "recorte")
checa("observação curta não é tratada como teor colado",
      _teor.escolher(_ref, "anotação curta")[1], "nenhum")
checa("nada em lugar nenhum -> nenhum", _teor.escolher("", "")[1], "nenhum")
checa("o texto devolvido é o da fonte escolhida",
      _teor.escolher(_ref, "y" * 500)[0], "y" * 500)

# a deteccao em si, com os textos reais
_so_referencia = ("Processo 44444443920258160017 4 Vara Cível de Maringá "
                  "CUMPRIMENTO DE SENTENÇA Intimação Intimação referente ao "
                  "movimento (seq. 47) JUNTADA DE PETIÇÃO (22092026). Acesse "
                  "o sistema Projudi do Tribunal de Justiça do Paraná para "
                  "mais detalhes.")
checa("publicação que só aponta para o sistema NÃO tem teor",
      _tt(_so_referencia), False)
_com_decisao = ("Vistos. Trata-se de ação de cobrança. " + "O juízo decide. " * 70)
checa("publicação com a decisão TEM teor", _tt(_com_decisao), True)
checa("texto vazio não tem teor", _tt(""), False)

# 37 — prefixo de quadro e' reconhecido mesmo com sigla nova depois (29/10/2026)
# A regex so' aceitava o prefixo quando vinha seguido de sigla operacional
# CONHECIDA — protecao para nao ler "PRZ - PROV - ..." como prefixo. Mas isso
# deixava sigla nova passar batido:
#     PROD - PERÍCIA - 1234567-72...  -> cartao nasceu com "PROD" no nome
#     PROD - Onboarding - Unidade...  -> idem
# PROD, PARC, PAR e CONS nunca sao siglas operacionais: reconhece-las direto
# resolve sem adivinhar o que a sigla nova significa, e sem precisar atualizar
# lista toda vez que a Controladoria criar uma.
checa("PROD seguido de sigla NOVA ainda é prefixo de quadro",
      _pq("PROD - PERÍCIA - 1234567-72.2023.8.26.0609 - Perícia"), "PROD")
checa("e a sigla nova fica no título, sem o PROD",
      _c2.sem_prefixo("PROD - PERÍCIA - 1234567-72.2023.8.26.0609 - Perícia"),
      "PERÍCIA - 1234567-72.2023.8.26.0609 - Perícia")
checa("PROD seguido de palavra qualquer também",
      _pq("PROD - Onboarding - Unidade Ribeirão Preto"), "PROD")
checa("PARC com sigla nova idem", _pq("PARC - PERÍCIA - 0001 - x"), "PARC")
# a protecao original continua: sigla operacional nao vira prefixo
checa("PRZ seguido de PROV continua NÃO sendo prefixo de quadro",
      _pq("PRZ - PROV - 0001234-95.2020.8.16.0001 - x"), None)
checa("AUD sozinho não é prefixo", _pq("AUD - 0001234-95 - Audiência"), None)
checa("PERÍCIA ganhou etiqueta mapeada",
      any(s == "PERÍCIA" for s, _ in _c2._ETIQUETAS), True)

# 38 — intimação marcada como LIDA está resolvida (29/10/2026, regra da usuária)
#   "marcado como lido foi resolvido — ou seja, a intimação está tratada e
#    não deve ser avisada no relatório"
# Medido antes da correção: das 6 intimações que o relatório acusava como
# "paradas há mais de 3 dias úteis", TODAS as 6 estavam marcadas como lidas.
# O aviso inteiro era falso positivo — cobrava trabalho já feito.
checa("a conferência filtra intimação já lida",
      "so_nao_lidas" in _vig or "so_nao_lidas" in _i7.getsource(_rt2.noite), True)
checa("o filtro aceita as formas que o DataJuri usa",
      all(f in _i7.getsource(_rt2.noite) for f in ('"sim"', '"true"', '"1"')), True)
checa("prepara_manha traz o campo lido do recorte",
      "lido" in __import__("prepara_manha").CAMPOS, True)

# 39 — o cartão enxuto (29/10/2026, pedido da Controladoria)
#   · hora das datas: 12h de Brasília, não 9h
#   · autoria vai para o COMENTÁRIO, não para a descrição
#   · as demais informações de origem somem
#   · o bloco "fatal · fatal −1 · fatal −2" sai da descrição
# As datas já estão no vencimento e no campo Prazo Fatal; repeti-las no texto
# roubava espaço da decisão, que é o que a Controladoria lê.
from rodape import comentario as _com
checa("hora é 15:00 UTC, que é 12h em Brasília", _c2.HORA_UTC, "15:00:00.000Z")
checa("o campo Prazo Fatal usa essa hora",
      "T{HORA_UTC}" in _i2.getsource(_c2.criar), True)
checa("o vencimento também", 'f"T{HORA_UTC}"' in _i2.getsource(_c2.criar), True)
checa("criar() aceita o comentário de autoria",
      "comentario_autoria" in _i2.getsource(_c2.criar), True)
checa("o comentário é postado no cartão",
      "/actions/comments" in _i2.getsource(_c2.criar), True)
checa("formato do comentário",
      _com({"criadoPor.nome": "Fernanda Lima Costa",
            "dataCadastro": "29/10/2026 15:42"}),
      "Lançado no DataJuri por: Fernanda Lima Costa — em 29/10/2026 15:42")
checa("sem quem lançou, o comentário sinaliza",
      "⚠️" in _com({"dataCadastro": "29/10/2026"}), True)
import rodape as _rod
checa("o rodapé de origem foi removido", _rod.montar({}), "")
checa("a descrição não leva mais o bloco de três datas",
      "bloco_prazo(fatal" in _rot, False)
checa("a pós-verificação procura a autoria no COMENTÁRIO",
      "commentCard" in _i6.getsource(_pl._confere), True)
checa("o pipeline não exige mais rodapé",
      '"rodape")' in _i6.getsource(_pl._valida), False)

# 40 — o teor colado vem no MESMO campo do texto padrão (29/10/2026)
#   "deixa o texto padrão que vem mov tal no campo da observação do lançamento
#    no DataJuri. A controladoria passará a colocar o teor da decisão justamente neste
#    mesmo campo de observação (algumas vezes ela deixou de fazer isso, por
#    isso deu problemas nos testes)"
# Contar tamanho não serve: a observação já passa de 800 caracteres só com o
# texto padrão (medido em 27/10: 849). É preciso ver o que há de NOVO ali.
_padrao = ("Data de disponibilização: 23/10/2026 Jornal: DJEN Vara: Maringá "
           "Processo 44444443920258160017 4 Vara Cível de Maringá CUMPRIMENTO "
           "DE SENTENÇA Intimação PARTE CONSTRUTORA EXEMPLO LTDA ADVOGADO "
           "JOSÉ CARLOS PEREIRA Intimação referente ao movimento "
           "(seq. 34) JUNTADA DE CERTIDÃO (16102026). Acesse o sistema Projudi.")
_recorte = ("Processo 44444443920258160017 4 Vara Cível de Maringá CUMPRIMENTO "
            "DE SENTENÇA Intimação PARTE CONSTRUTORA EXEMPLO LTDA ADVOGADO "
            "JOSÉ CARLOS PEREIRA Intimação referente ao movimento "
            "(seq. 34) JUNTADA DE CERTIDÃO (16102026). Acesse o sistema Projudi "
            "do Tribunal de Justiça do Paraná.")
_colado = _padrao + " DECISÃO: Vistos. " + "Defiro a penhora via SISBAJUD. " * 8
checa("observação com SÓ o texto padrão não conta como teor",
      _teor.escolher(_recorte, _padrao)[1], "nenhum")
checa("observação com texto padrão MAIS o teor colado conta",
      _teor.escolher(_recorte, _colado)[1], "observacao")
checa("publicação que já traz a decisão continua tendo prioridade",
      _teor.escolher("Vistos. " + "O juízo decide. " * 70, _colado)[1], "recorte")
checa("o que sobra da observação é medido contra o recorte",
      len(_teor._extra_da_observacao(_colado, _recorte)) > 200, True)
checa("texto padrão sozinho quase não sobra nada",
      len(_teor._extra_da_observacao(_padrao, _recorte)) < 300, True)

print()
if FALHAS:
    print(f"{len(FALHAS)} REGRA(S) QUEBRADA(S):\n")
    for f in FALHAS:
        print("  " + f)
    sys.exit(1)
print("todas as regras medidas continuam valendo.")
