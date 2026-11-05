#!/usr/bin/env python3
"""
Rodape de procedencia do cartao — quem fez o que.

Decidido com a controladoria em 30/09/2026: o cartao ja' registrava que foi gerado
automaticamente, mas NAO dizia QUEM lancou a atividade no DataJuri que ele
esta' copiando. Agora diz.

O campo certo e' `criadoPor.nome`, nao `proprietario.nome`:

    criadoPor     -> quem LANCOU a atividade no DataJuri   <- e' este
    proprietario  -> quem e' RESPONSAVEL por executa-la
    encarregado   -> quem REVISA

Responsavel e revisor NAO vao para o cartao: quem marca e' a controladoria. Repetir
aqui o que veio do DataJuri induziria a tratar como definido o que ainda e'
decisao dela.

Medido nos lancamentos de PRZ (o escopo deste projeto): 20 de 20 foram
lancados pela controladoria. Nos demais tipos aparecem outras pessoas, mas sao CONS
e CST — consultivo e consultas, fora do escopo.

CAMPO OBRIGATORIO na consulta: `criadoPor.nome` precisa entrar na lista de
`campos` da chamada ao modulo Atividade. A API do DataJuri REJEITA campo
invalido com HTTP 400 desde ~09/2026, mas campo NAO PEDIDO simplesmente vem
vazio, em silencio. Sem pedir, o rodape sai sem autoria e nada falha.
"""

CAMPOS_NECESSARIOS = ("criadoPor.nome", "dataCadastro")


def comentario(ativ):
    """Frase de procedencia, para ir no COMENTARIO do cartao.

    Formato pedido pela Controladoria em 29/10/2026:

        Lançado no DataJuri por: Fernanda Lima Costa — em 29/10/2026 15:42

    Antes isto era um rodape na descricao, junto de publicacao de origem,
    cache usado e aviso de conferencia. Tudo isso saiu: a descricao e' para o
    teor da decisao e os dados operacionais. Procedencia mora no historico.
    """
    lancou = (ativ.get("criadoPor.nome") or "").strip()
    quando = (ativ.get("dataCadastro") or "").strip()
    if not lancou:
        return "⚠️ Lançado no DataJuri por: não informado no lançamento"
    return f"Lançado no DataJuri por: {lancou}" + (f" — em {quando}" if quando else "")


def montar(ativ, publicacao=None, n_lancamentos=1, extra=None, do_cache=None):
    """MANTIDA so' para compatibilidade — devolve vazio.

    O rodape de origem foi removido do cartao em 29/10/2026. A autoria passou
    para o comentario (ver `comentario`), e as demais informacoes de origem
    — publicacao localizada, cache usado, aviso de conferencia — sairam.
    """
    return ""
