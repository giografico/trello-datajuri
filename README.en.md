# Docket Control — deadline automation between legal practice software and Trello

Reads deadline entries from a law firm's case-management platform and
creates the matching cards in Trello — eliminating manual re-typing between
the two systems, without ever deciding anything that is a human call.

*(Leia isto em [português](README.md).)*

## Why this exists

A missed deadline is a lost right. The docket-control team at a law firm
logged every activity in the case-management platform and then re-typed the
same entry into Trello by hand — 2 to 3 hours behind, every day. This
project closes that gap by automating only the re-typing, never the
decision.

## Two earlier attempts failed — and the reason matters

Before this project, two other automations for the same problem were
abandoned. Both failed for the same reason: they handed the docket-control
team something to **fix**, not something to approve or complete — an
auto-generated pre-card with a wrong estimated deadline, a daily checklist
that turned into extra work. Every forced correction is one more reason not
to trust the next automation.

## What makes this one different

**The automation runs after the human decision, never before it.** When
information is missing, the card is born saying what's missing — never
filled in with a guess. An entry with no deadline at the source produces a
card with no due date and an explicit warning. A publication with nothing to
summarize produces a one-line warning, not a forced summary. The deadline
itself is never calculated by the system — it comes pre-computed from
whoever logged it; the code only copies it and, at most, computes how many
days of buffer to leave before it. See `CLAUDE.md` for the full set of rules
this implies.

## What the system does

```
1. reads deadline entries from the case-management platform
2. groups the ones that are the same procedural act (a motion for
   clarification and an appeal on the same docket entry become one card;
   nothing else is grouped by resemblance)
3. locates the source publication and decides whether there's a ruling
   worth summarizing
4. summarizes it with a language model — never invents, never completes a
   truncated date, never states how a deadline was counted
5. creates the Trello card, with due date, label and summary
6. checks its own work and only speaks up about exceptions
```

All of that is fixed logic in code, locked down by 291 tests. The only
place AI touches this project is the 1-to-3-sentence summary of a judicial
decision — see `docs/PROMPT_RESUMO.md` for the full prompt and why each rule
in it exists.

## Measured, not claimed

Numbers from the original project, measured against real human work — not
estimated, not specified up front:

| | |
|---|---|
| Business rules locked under test | 291 |
| Card title identical to what the docket team wrote by hand | 100% |
| Cards with an error, across 6 invariants checked over 150 cards | 0 |
| A full day of entries processed in | 94 seconds |
| Reduction in time spent on the task | 70% |
| Bug detection via mutation testing | 93% (14 of 15 bugs planted on purpose) |
| Tests that only checked for text in the source code, before the fix | 34% (78 of 231) |
| Cards born marked as done by mistake, before the fix | 51% (122 of 240) |

The full record of the decisions behind these numbers — what seemed right
before measuring, what the measurement showed, how it was fixed — is in
`docs/DECISOES_MEDIDAS.md` (Portuguese).

## What it doesn't do

- Doesn't decide how many deadlines a ruling generates, nor who executes or
  reviews the task.
- Doesn't calculate the deadline — it comes pre-computed from whoever logged
  it; the code only copies it and applies the prep-time buffer.
- Doesn't state how a deadline was counted, nor cite a counting statute,
  unless the ruling's own text already cites it.
- Doesn't complete incomplete data — a truncated date is omitted, never
  guessed.
- Doesn't access any court system, by any means.
- Doesn't edit, move, archive or delete any card — only creates.

## Run it in 3 commands

No real credentials needed — the case-management platform, Trello and the
language model are all swapped for fake versions:

```bash
pip3 install certifi             # the one optional dependency
python3 teste_regras.py          # 291 rules, no network access
python3 demo.py --reiniciar      # runs the full pipeline on made-up data
```

Demo mode covers the five hard cases the real system solves — a duplicate
notice arriving from two different sources, two entries on the same docket
movement with different deadlines, an entry with no deadline at all, a bar
registration number mistaken for a case number, and personal data embedded
in free text — and checks, on its own, that each one was handled correctly.
Cards are saved to `trabalho/demo_trello.json`; running `python3 demo.py`
again (without `--reiniciar`) shows the duplicate-detection guard at work.

## Running against real data

```bash
cp .config-plataforma.exemplo.json .config-plataforma.json   # fill in
cp .config-trello.exemplo.json   .config-trello.json         # fill in
cp .config-anthropic.exemplo.json .config-anthropic.json     # optional

python3 teste_ambiente.py       # checks credentials and Trello ids
python3 rotina.py lancamentos DD/MM/YYYY           # dry run, creates nothing
python3 rotina.py lancamentos DD/MM/YYYY --criar   # creates for real
```

Without an AI key in `.config-anthropic.json` and without Claude Code
installed, cards come out with no summary — never with an invented one.

## Quality verification

```bash
python3 qa_mutacao.py          # 14/15 planted bugs, detected
python3 qa_comportamento.py    # sections 1-5 are offline; 6-7 read real Trello state
python3 qa_reconciliacao.py    # compares source vs. destination as whole sets
```

All three only accept proof by execution — none of them scans source code
for text. `pipeline.py` runs `teste_regras.py` and `teste_ambiente.py`
before any batch creation; if either fails, nothing is created.

## Layout

| | |
|---|---|
| `rotina.py` | the program that runs the day — `manha`, `lancamentos`, `noite`, `vigia` modes |
| `cartao.py` | the rules applied when creating a card |
| `pipeline.py` | mandatory pre-flight checks, batch validation and post-verification |
| `consolida.py` | what becomes a single card |
| `prazo_util.py` | business days, holidays, the forensic-recess suspension (CPC art. 220) |
| `sanitiza.py` | strips CPF/ID numbers and bank data — never strips the case number or bar number |
| `modelo.py` | calls the language model (API or a coding agent) |
| `cliente_plataforma_fake.py`, `cliente_trello_fake.py`, `gerador_dados_ficticios.py` | demo mode |
| `qa_*.py` | the three QA tools that execute, rather than read code |
| `docs/` | measured decisions and the summary prompt, explained (Portuguese) |
| `CLAUDE.md` | governance for the AI agents that built and operate this project |

## License

MIT — see `LICENSE`.

---

Built between August and November 2026 for the docket-control team of a
Brazilian law firm, with Claude Code as the development agent. Published
after the firm migrated to an in-house platform — the technology still has
value for any firm running a case-management platform and Trello in the
same workflow.
