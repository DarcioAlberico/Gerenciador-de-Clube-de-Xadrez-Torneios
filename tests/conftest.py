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
