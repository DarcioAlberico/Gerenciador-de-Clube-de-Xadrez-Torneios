"""Catálogo de textos da interface (B-3 / P2-12).

Módulo **puro**: não importa Tk. Lê um JSON por idioma de ``i18n/`` e resolve
chaves em texto.

**Isto é preparação, não tradução** (ESPEC_UI_UX §6 e §8: "extrair strings
mantendo só PT-BR ativo; **não** implementar EN agora"). O valor imediato não é
falar inglês — é ter um lugar único onde o texto da interface mora, em vez de
espalhado por 21 telas. Quando as exportações FIDE em inglês chegarem, o
trabalho será acrescentar um arquivo, não caçar literais.

    t("nav.club")                      # "Perfil do Clube"
    t("shell.reload.empty")            # "Nada para recarregar."
    t("dialog.delete.confirm", nome="Ana")

**Chave faltando devolve a própria chave** — e isso é deliberado: aparece na
tela como ``nav.club``, feio e impossível de ignorar. O contrário (cair num
texto padrão) esconderia o erro justamente de quem poderia corrigi-lo. O que
impede isso de chegar ao usuário é o teste que varre as chamadas de ``t()`` e
cobra que cada chave exista no catálogo.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("src.ui.i18n")

DEFAULT_LOCALE = "pt_BR"


def _base_dir() -> Path:
    """Raiz do projeto — ou a pasta do executável, quando empacotado.

    Mesma convenção de `assets/` (ver ``database._base_dir``), repetida aqui em
    três linhas em vez de importada: este módulo é puro, e puxar a camada de
    banco só para descobrir um caminho seria trocar independência por atalho.
    O `albericus.spec` leva `i18n/` junto no build.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


CATALOG_DIR = _base_dir() / "i18n"


class Catalog:
    """Textos de um idioma. Imutável depois de carregado."""

    def __init__(self, entries: dict[str, str], locale: str = DEFAULT_LOCALE) -> None:
        self._entries = dict(entries)
        self.locale = locale

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, key: str) -> bool:
        return key in self._entries

    @property
    def keys(self) -> set[str]:
        return set(self._entries)

    def get(self, key: str, **params: Any) -> str:
        """Texto da chave, com ``{parametros}`` aplicados.

        Parâmetro faltando **não** derruba a tela: devolve o texto cru, que ao
        menos comunica alguma coisa, e registra o erro. Um rótulo com
        ``{nome}`` visível é ruim; uma tela que não abre é pior.
        """
        texto = self._entries.get(key)
        if texto is None:
            logger.error("Chave de texto ausente no catalogo %s: %s", self.locale, key)
            return key
        if not params:
            return texto
        try:
            return texto.format(**params)
        except (KeyError, IndexError, ValueError):
            logger.exception("Parametro ausente ao formatar %s", key)
            return texto


def catalog_path(locale: str = DEFAULT_LOCALE, base_dir: Path | None = None) -> Path:
    return (base_dir or CATALOG_DIR) / f"{locale}.json"


def load_catalog(locale: str = DEFAULT_LOCALE, base_dir: Path | None = None) -> Catalog:
    """Lê o catálogo do disco. Arquivo ausente ou quebrado vira catálogo vazio.

    Vazio e não exceção: o app abrindo com as chaves à mostra é diagnosticável;
    o app não abrindo por causa de um arquivo de texto, não.
    """
    caminho = catalog_path(locale, base_dir)
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("Catalogo de textos nao encontrado: %s", caminho)
        return Catalog({}, locale)
    except (ValueError, OSError):
        logger.exception("Catalogo de textos ilegivel: %s", caminho)
        return Catalog({}, locale)
    if not isinstance(dados, dict):
        logger.error("Catalogo de textos com formato inesperado: %s", caminho)
        return Catalog({}, locale)
    return Catalog({str(k): str(v) for k, v in dados.items()}, locale)


_catalog: Catalog | None = None


def current_catalog() -> Catalog:
    """Catálogo em uso, carregando na primeira chamada."""
    global _catalog
    if _catalog is None:
        _catalog = load_catalog()
    return _catalog


def set_catalog(catalog: Catalog) -> None:
    """Troca o catálogo em uso (troca de idioma, teste)."""
    global _catalog
    _catalog = catalog


def set_locale(locale: str, base_dir: Path | None = None) -> Catalog:
    catalog = load_catalog(locale, base_dir)
    set_catalog(catalog)
    return catalog


def current_locale() -> str:
    return current_catalog().locale


def t(key: str, **params: Any) -> str:
    """Texto da interface. Ponto único de leitura do catálogo."""
    return current_catalog().get(key, **params)
