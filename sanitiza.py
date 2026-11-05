#!/usr/bin/env python3
"""
Remocao de dados pessoais sensiveis antes de gravar no cartao.

CLAUDE.md secao 5: nao processar registros com CPF, RG ou dados bancarios.

Descoberto em 01/10/2026: a `observacao` do lancamento as vezes traz a
qualificacao completa da parte — CPF, RG, carteira de trabalho, telefone. Ao
copiar a observacao para o cartao (que e' o que fazemos em PROV e NEG, onde
nao ha decisao judicial a resumir), esses dados iam junto. 2 de 89 cartoes.

Nao basta confiar em quem escreve o conteudo: a sanitizacao roda SEMPRE, na
porta de criacao, sobre descricao e titulo.

O que NAO e' removido: numero de processo (CNJ), OAB, valores, datas. Sao
dados do caso, nao da pessoa.
"""
import re

# CPF 000.000.000-00 e CNPJ de pessoa fisica mascarado como CPF
_RX_CPF = re.compile(r'\b\d{3}\.\d{3}\.\d{3}\s*-\s*\d{2}\b')
# RG / cedula de identidade: 6 a 12 digitos apos a marca
_RX_RG = re.compile(r'\b(RG|R\.G\.|cédula de identidade|carteira de identidade)'
                    r'\s*(n?[ºo°.]*\s*)?[\d.\-/]{6,14}\b', re.I)
# CTPS
_RX_CTPS = re.compile(r'\b(CTPS|Carteira de Trabalho e Previdência Social)'
                      r'\s*(n?[ºo°.]*\s*)?[\d.\-/\s]{5,20}\b', re.I)
# CPF por extenso, sem pontuacao, quando precedido da marca
_RX_CPF_MARCA = re.compile(r'\b(CPF|CPF/MF|CPF/CNPJ)\s*(n?[ºo°.]*\s*)?[\d.\-]{11,18}\b', re.I)
# conta bancaria com agencia
_RX_BANCO = re.compile(r'\b(ag[êe]ncia|ag\.)\s*[\d.\-]{3,8}[,;\s]+(conta|c/c|cc)\s*[\d.\-]{4,14}\b', re.I)

_SUB = "[dado pessoal removido]"


def sanitizar(texto):
    """Remove CPF, RG, CTPS e dados bancarios. Devolve (texto, quantos)."""
    if not texto:
        return texto, 0
    n = 0
    for rx in (_RX_CPF_MARCA, _RX_CPF, _RX_RG, _RX_CTPS, _RX_BANCO):
        texto, k = rx.subn(_SUB, texto)
        n += k
    return texto, n


def tem_dado_pessoal(texto):
    return sanitizar(texto)[1] > 0
