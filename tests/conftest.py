"""Configuração global da suíte de testes.

Em produção os motores padrão de pareamento E de desempate são o Gacrux
(subprocess, motor FIDE oficial). Nos testes forçamos os motores próprios
(in-process): determinísticos e rápidos, sem rodar um subprocesso a cada rodada
ou a cada cálculo de classificação. Os testes do Gacrux ativam-no
explicitamente (ver tests/test_pairing_gacrux.py e
tests/test_pairing_gacrux_tiebreak.py).

As variáveis são lidas em runtime por
src.core.database_tournament_core.default_pairing_system /
default_tiebreak_engine, então basta defini-las aqui, antes de qualquer torneio
ser criado.
"""
import os

os.environ.setdefault("ALBERICUS_DEFAULT_PAIRING_SYSTEM", "fide_dutch")
os.environ.setdefault("ALBERICUS_DEFAULT_TIEBREAK_ENGINE", "albericus")

# Nota: manter aqui uma raiz Tk "ancora" viva pela sessao parece resolver os
# skips de criacao de raiz (ver cancel_pending_callbacks), mas NAO funciona: a
# ancora vira o _default_root do tkinter e os menus da AlbericusApp passam a ser
# criados no interpretador errado, quebrando ~6 testes de layout. Ja tentado.
