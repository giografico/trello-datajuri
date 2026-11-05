#!/usr/bin/env python3
"""
MUTATION TESTING — os testes pegam bug de verdade?

Por que existe (20/10/2026). Medindo a suite: de 231 testes, **78 apenas
verificavam se um TEXTO existia no codigo-fonte** — passariam com a logica
quebrada. Isso explica por que os defeitos so' apareciam rodando em producao.

A tecnica e' a padrao de QA para avaliar uma suite: introduzir bugs de
proposito ("mutantes") e contar quantos a suite detecta. Mutante que sobrevive
e' um bug que passaria despercebido.

    python3 qa_mutacao.py

NAO deixa o codigo alterado: cada mutacao e' aplicada, testada e desfeita,
com restauracao garantida mesmo se o processo for interrompido.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))

# (arquivo, regex a procurar, substituicao, o que o bug faria na pratica)
MUTACOES = [
    ("consolida.py", r"return 2 if eh_prz\(assunto\) else 0",
     "return 3 if eh_prz(assunto) else 0",
     "vencimento 3 dias antes do fatal, não 2"),
    ("consolida.py", r"return 2 if eh_prz\(assunto\) else 0",
     "return 0 if eh_prz(assunto) else 0",
     "PRZ passa a vencer no próprio dia fatal"),
    ("consolida.py", r'return sem_prefixo\(assunto\)\.strip\(\)\.upper\(\)\.startswith\("PRZ"\)',
     'return assunto.strip().upper().startswith("PRZ")',
     "o prefixo PROD volta a cegar a consolidação"),
    ("consolida.py", r"datas\.sort\(\)", "datas.sort(reverse=True)",
     "cartão agrupado usa o prazo MAIS LONGE, não o mais próximo"),
    ("prazo_util.py", r"def recua_uteis\(d, n\):\n(\s+)\"\"\"",
     "def recua_uteis(d, n):\n\\1\"\"\"",
     "(sem efeito — controle)"),
    ("prazo_util.py", r"x -= timedelta\(days=1\)\n(\s+)while not eh_util\(x\):",
     "x -= timedelta(days=1)\n\\1while False and not eh_util(x):",
     "a conta passa a ser em dias corridos, não úteis"),
    ("prefixo.py", r'QUADROS_FORA = \("PAR", "PARC", "CONS"\)',
     'QUADROS_FORA = ("PAR", "CONS")',
     "lançamentos do quadro de parceiros (PARC) entram"),
    ("prefixo.py", r"return None if sig in _SIGLAS_OPERACIONAIS else sig",
     "return sig",
     "sigla operacional é confundida com sigla de quadro"),
    ("sanitiza.py", r"_RX_CPF = re\.compile\(r'\\b",
     "_RX_CPF = re.compile(r'(?!x)x\\b",
     "CPF deixa de ser removido"),
    ("cartao.py", r"existe = dc\.ja_criei\(nome, processo\)",
     "existe = None",
     "a trava de duplicata para de funcionar"),
    ("cartao.py", r'if prefixo_de_quadro\(assunto\) is None:',
     'if False:',
     "lançamento sem sigla deixa de ser avisado"),
    ("cartao.py", r"if not lb:", "if False:",
     "cartão sem etiqueta deixa de ser avisado"),
    ("audiencia.py", r'return modalidade\(assunto\) != "presencial"',
     'return True',
     "audiência presencial passa a pedir chave e link"),
    ("audiencia.py", r'if not eh_audiencia\(assunto\) or not precisa_sala_virtual\(assunto\):',
     'if False:',
     "cartão de prazo passa a pedir chave de audiência"),
    ("fila_intimacoes.py", r'return d if len\(d\) == 20 else ""',
     "return d",
     "número de OAB volta a ser aceito como processo"),
]


def roda_suite():
    """True se a suite PASSA (ou seja, nao detectou nada)."""
    r = subprocess.run([sys.executable, os.path.join(AQUI, "teste_regras.py")],
                       capture_output=True, text=True, cwd=AQUI)
    return r.returncode == 0


def main():
    print("MUTATION TESTING — introduzindo bugs e vendo se a suíte os pega\n")
    print(f"{'bug introduzido':58s} {'suíte'}")
    print("-" * 72)
    mortos, vivos = [], []
    for arquivo, procura, troca, descricao in MUTACOES:
        caminho = os.path.join(AQUI, arquivo)
        original = open(caminho, encoding="utf-8").read()
        mutado, n = re.subn(procura, troca, original, count=1)
        if n == 0:
            print(f"{descricao[:58]:58s} —  (padrão não encontrado)")
            continue
        try:
            open(caminho, "w", encoding="utf-8").write(mutado)
            passou = roda_suite()
        finally:
            open(caminho, "w", encoding="utf-8").write(original)   # sempre restaura
        if passou:
            vivos.append((arquivo, descricao))
            print(f"{descricao[:58]:58s} ✗  NÃO PEGOU")
        else:
            mortos.append((arquivo, descricao))
            print(f"{descricao[:58]:58s} ok pegou")
    tot = len(mortos) + len(vivos)
    print("-" * 72)
    if tot:
        print(f"\n{len(mortos)}/{tot} bugs detectados ({len(mortos)/tot*100:.0f}%)")
    if vivos:
        print(f"\nBUGS QUE PASSARIAM DESPERCEBIDOS:")
        for a, d in vivos:
            print(f"  ✗ {a}: {d}")
    return {"mortos": len(mortos), "vivos": len(vivos)}


if __name__ == "__main__":
    main()
