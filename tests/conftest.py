"""Configuração global da suíte de testes.

Em produção o motor de pareamento padrão é o Gacrux (subprocess, motor FIDE
oficial). Nos testes forçamos o motor próprio (in-process): determinístico e
rápido, sem rodar um subprocesso a cada rodada. Os testes do Gacrux ativam-no
explicitamente (ver tests/test_pairing_gacrux.py).

A variável é lida em runtime por src.core.database_tournament_core.default_pairing_system,
então basta defini-la aqui, antes de qualquer torneio ser criado.
"""
import os

os.environ.setdefault("ALBERICUS_DEFAULT_PAIRING_SYSTEM", "fide_dutch")
