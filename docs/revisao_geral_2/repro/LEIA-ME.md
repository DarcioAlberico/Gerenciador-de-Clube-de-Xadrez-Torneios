# Reprodução dos achados da Revisão Geral 2

Scripts escritos pelos revisores 2 a 10 (`rN/` = revisão N), copiados do rascunho da sessão de 2026-11-27. São **rascunhos**: servem de ponto de partida para o teste vermelho de cada RG2, não de teste. Cada RG2 da spec cita o script que o reproduziu.

Rodar a partir da raiz do projeto, sempre com banco temporário:

```powershell
$env:PYTHONPATH = (Get-Location).Path
uv run --extra dev python docs/revisao_geral_2/repro/r2/prune_live.py
```

As sondas de janela da revisão 4 usam o executor próprio:

```powershell
uv run --extra dev python docs/revisao_geral_2/repro/r4/run.py docs/revisao_geral_2/repro/r4/test_probe_r4.py enter_na_tabela
```

Dois scripts (`r6/dbg1.py`, `r8/t2.py`) têm caminho do rascunho escrito no código; ajuste antes de rodar. Os scripts da revisão 10 que leem um banco real (`cols.py`, `outbox.py`, `realdb.py`, `size.py`) abrem o arquivo em modo **somente leitura** (`?mode=ro`); passe o caminho de uma cópia mesmo assim.

`../achados_brutos.md` tem as notas condensadas de cada revisão, antes da consolidação.
