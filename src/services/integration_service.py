from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class IntegrationService:
    """Serviço responsável por se comunicar com APIs externas (Lichess e Chess.com)."""

    def __init__(self) -> None:
        self.headers = {"User-Agent": "Albericus Chess Club Manager (github.com/albericus)"}

    def fetch_lichess_ratings(self, username: str) -> Dict[str, int]:
        """Busca o rating de Blitz e Rapid no Lichess.org."""
        url = f"https://lichess.org/api/user/{username}"
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                return {
                    "blitz": data.get("perfs", {}).get("blitz", {}).get("rating", 0),
                    "rapid": data.get("perfs", {}).get("rapid", {}).get("rating", 0),
                }
        except urllib.error.HTTPError as e:
            logger.warning("Erro HTTP ao buscar Lichess para %s: %s", username, e.code)
        except Exception as e:
            logger.warning("Falha ao buscar Lichess para %s: %s", username, e)
        return {"blitz": 0, "rapid": 0}

    def fetch_chesscom_ratings(self, username: str) -> Dict[str, int]:
        """Busca o rating de Blitz e Rapid no Chess.com."""
        url = f"https://api.chess.com/pub/player/{username}/stats"
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                return {
                    "blitz": data.get("chess_blitz", {}).get("last", {}).get("rating", 0),
                    "rapid": data.get("chess_rapid", {}).get("last", {}).get("rating", 0),
                }
        except urllib.error.HTTPError as e:
            logger.warning("Erro HTTP ao buscar Chess.com para %s: %s", username, e.code)
        except Exception as e:
            logger.warning("Falha ao buscar Chess.com para %s: %s", username, e)
        return {"blitz": 0, "rapid": 0}
