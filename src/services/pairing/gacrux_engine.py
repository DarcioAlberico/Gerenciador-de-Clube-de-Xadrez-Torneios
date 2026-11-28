from __future__ import annotations
import os
import sys
import tempfile
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Sequence

# RESERVE_ENGINE_LABEL mora em constants (RGS-18); reexportado aqui.
from src.services.constants import RESERVE_ENGINE_LABEL, AppError
from src.services.export_service import ExportService
from src.services.federation_exporters.trf16 import TRF16Exporter
from src.core.resources import PROJECT_ROOT
from src.services.pairing import gacrux_runner
from src.services.pairing.acceleration import acceleration_spec
from src.services.pairing.constraints import seeding_order
from src.services.pairing.initial_color import resolve_initial_color
from src.services.pairing.gacrux_trf import (
    PairingScore,
    acceleration_records,
    pairing_score,
    prohibition_records,
    rebased_score_lines,
    reconcile_scores,
)
from src.services.pairing.pairing_check import (
    PairingCheck,
    checker_round,
    paired_player_ids,
    pairs_from_checker,
    stored_pairs,
    unchecked,
)

logger = logging.getLogger(__name__)

# Teto de tempo do subprocesso do Gacrux: evita pendurar a aplicação se o motor
# travar (essencial agora que o Gacrux pode ser o motor padrão de pareamento).
GACRUX_TIMEOUT_SECONDS = 120




class GacruxRefusal(AppError):
    """O Gacrux não pareia esta rodada, e o motor reserva pode (RGS-18).

    E o que a tela de Rodadas transforma na oferta "Parear com o motor
    reserva", com confirmação e auditoria; nunca uma queda silenciosa.
    ``refusal`` diz em poucas palavras o porque, para o aviso e o evento
    ``pairing_engine_fallback``.
    """

    refusal = "o Gacrux recusou a rodada"
    # O motor reserva é saída para esta recusa? Não quando não existe pareamento
    # legal nenhum (RG2-22): o reserva também não teria.
    offers_reserve = True

    def __init__(self, round_number: int | None, details: list[str], message: str) -> None:
        self.round_number = None if round_number is None else int(round_number)
        self.details = list(details)
        if self.offers_reserve:
            message = f"{message}\n\nÉ possível parear esta rodada com o {RESERVE_ENGINE_LABEL}."
        super().__init__(message)


# Marca que o motor vendorizado (`gacrux/pairing.py`) põe na falha de
# viabilidade; o teste do RG2-22 confere que os dois textos continuam iguais.
NO_LEGAL_PAIRING_TAG = "GACRUX-SEM-PAREAMENTO-LEGAL"


class GacruxNoLegalPairing(GacruxRefusal):
    """Não existe pareamento que respeite os critérios absolutos (RG2-22).

    Antes era um ``AppError`` com o stderr do Gacrux — o árbitro lia um
    traceback, e pedir o motor reserva dava o mesmo traceback. O reserva não é
    oferecido: a saída é encerrar o torneio ou rever as ausências.
    """

    refusal = "não existe pareamento legal"
    offers_reserve = False

    def __init__(self, round_number: int | None, details: list[str]) -> None:
        rodada = f"Rodada {round_number}: n" if round_number is not None else "N"
        super().__init__(
            round_number,
            details,
            f"{rodada}ão existe pareamento que respeite os critérios absolutos da FIDE "
            "(C.04.1): ninguém joga duas vezes contra o mesmo adversário e ninguém "
            "recebe um segundo bye."
            + "".join(f"\n- {item}" for item in details)
            + "\n\nO motor reserva também não teria saída. Você pode encerrar o torneio "
            "aqui ou rever as ausências (quem está ausente ou retirado) e gerar de novo.",
        )


class GacruxScoreMismatch(GacruxRefusal):
    """O Gacrux contaria pontos diferentes dos da classificação (RGS-03).

    O motor FIDE soma as células do TRF. Desde a Fase 3 o arquivo do pareamento
    leva o registro 162 (valor do PAB = ``bye_points``) e um 299 por ajuste de
    pontos, e as rodadas de ausência do entrante tardio viram células de bye.
    O que ainda assim não tem representação (PAB fora de 0/0,5/1, ajuste de
    rodada futura, diferença fora das rodadas de ausência) e recusado ANTES de
    rodar o motor, que parearia com outro placar ou quebraria; quem chama pode
    oferecer o motor reserva.
    """

    refusal = "o Gacrux recusou a pontuação"

    def __init__(self, round_number: int, details: list[str]) -> None:
        super().__init__(
            round_number,
            details,
            f"Rodada {round_number}: o motor FIDE (Gacrux) parearia com pontos "
            "diferentes dos da classificação - o arquivo TRF não consegue dizer "
            "esta pontuação ao motor.\n\n"
            + "\n".join(f"- {item}" for item in details),
        )


class GacruxOutputRejected(GacruxRefusal):
    """A saída do Gacrux veio vazia, ausente ou não confere (RGS-19).

    Antes era um ``AppError`` simples: a rodada parava sem a oferta do motor
    reserva que a recusa de pontuação já tinha.
    """

    refusal = "a saída do Gacrux não conferiu"

    def __init__(self, round_number: int | None, details: list[str]) -> None:
        rodada = f" da rodada {round_number}" if round_number is not None else ""
        super().__init__(
            round_number,
            details,
            f"A saída do motor Gacrux{rodada} não confere e foi recusada:\n"
            + "\n".join(f"- {item}" for item in details)
            + "\n\nA rodada não foi gerada. O arquivo de entrada ficou no log.",
        )


def pairings_from_gacrux(
    pairs: Sequence[Sequence[int]],
    rank_to_player_id: dict[int, int],
    ranks_to_pair: set[int],
    *,
    round_number: int | None = None,
) -> list[dict[str, Any]]:
    """Mesas do Albericus a partir dos pares do Gacrux, conferidos (RGS-19).

    Cada start-rank de ``ranks_to_pair`` aparece exatamente uma vez, nenhum
    outro aparece e há no máximo um PAB (``0`` do outro lado). Antes, um número
    sem mapeamento era pulado em silêncio e um repetido entrava em duas mesas:
    uma saída corrompida virava rodada com gente faltando. Agora e ``AppError``.
    """
    appearances: dict[int, int] = {}
    normal: list[dict[str, Any]] = []
    byes: list[dict[str, Any]] = []
    unreadable: list[str] = []
    for pair in pairs:
        try:
            white_rank, black_rank = (int(value) for value in pair)
        except (TypeError, ValueError):
            unreadable.append(repr(pair))
            continue
        if white_rank == 0 and black_rank == 0:
            continue  # par vazio: não envolve ninguém
        for rank in (white_rank, black_rank):
            if rank:
                appearances[rank] = appearances.get(rank, 0) + 1
        if white_rank == 0 or black_rank == 0:
            byes.append({
                "board_number": 9999,
                "white_player_id": rank_to_player_id.get(white_rank or black_rank),
                "black_player_id": None,
                "result": "BYE",
                "is_bye": 1,
            })
        else:
            normal.append({
                "board_number": 0,
                "white_player_id": rank_to_player_id.get(white_rank),
                "black_player_id": rank_to_player_id.get(black_rank),
                "result": "",
                "is_bye": 0,
            })

    problems = [f"par ilegível: {item}" for item in unreadable]
    unknown = sorted(rank for rank in appearances if rank not in rank_to_player_id)
    outsiders = sorted(
        rank for rank in appearances if rank in rank_to_player_id and rank not in ranks_to_pair
    )
    duplicated = sorted(rank for rank, count in appearances.items() if count > 1)
    missing = sorted(set(ranks_to_pair) - set(appearances))
    if unknown:
        problems.append(f"número(s) que não existem no torneio: {_ranks(unknown)}")
    if outsiders:
        problems.append(f"jogador(es) que não deveriam jogar esta rodada: {_ranks(outsiders)}")
    if duplicated:
        problems.append(f"jogador(es) que aparecem mais de uma vez: {_ranks(duplicated)}")
    if missing:
        problems.append(f"jogador(es) faltando: {_ranks(missing)}")
    if not pairs and ranks_to_pair:
        problems.append(
            "o motor não encontrou pareamento que respeite os critérios absolutos "
            "FIDE (C.04.1: sem repetir adversário nem dar um segundo PAB)"
        )
    if len(byes) > 1:
        problems.append(f"{len(byes)} byes alocados (o máximo é 1)")
    if problems:
        raise GacruxOutputRejected(round_number, problems)

    final_pairings = normal + byes
    for index, pairing in enumerate(final_pairings, start=1):
        pairing["board_number"] = index
    return final_pairings


def _ranks(ranks: Sequence[int]) -> str:
    return ", ".join(f"SNo {rank}" for rank in ranks)


class GacruxEngine:
    def __init__(self, db) -> None:
        self.db = db
        # Avisos da última rodada pareada (PAR-02): o que o arquivo TRF não
        # conseguiu contar ao motor. Quem chama repassa ao árbitro.
        self.warnings: list[str] = []

    def pair_round(
        self,
        tournament_id: int,
        to_pair: list[dict[str, Any]],
        round_number: int,
        *,
        accelerated_player_ids: Sequence[int] = (),
        acceleration_bonus: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Executes Swiss pairing for the specified round using the FIDE-approved Gacrux engine.
        Re-uses the existing TRF16Exporter to serialize the tournament state, runs Gacrux,
        and parses back the results.

        `accelerated_player_ids` recebe o bônus fictício de `acceleration_bonus`
        nesta rodada (PAR-02): o motor não tem parâmetro de aceleração, ela viaja
        como registro 250 no TRF. Ver `gacrux_trf.acceleration_records`.
        """
        self.warnings = []
        to_pair_ids = {int(p["id"]) for p in to_pair}

        # Use a temporary directory for file exchange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.trf"
            output_path = Path(tmpdir) / "output.json"

            rank_to_player_id = self.write_pairing_trf(
                tournament_id,
                round_number,
                input_path,
                accelerated_player_ids=accelerated_player_ids,
                acceleration_bonus=acceleration_bonus,
            )
            # Quem NÃO é pareado nesta rodada (inativo, bye solicitado) vai no -u.
            ranks_to_pair = {
                rank for rank, player_id in rank_to_player_id.items() if player_id in to_pair_ids
            }
            unpaired_ranks = [
                str(rank) for rank in sorted(rank_to_player_id) if rank not in ranks_to_pair
            ]

            if logger.isEnabledFor(logging.DEBUG):
                with open(input_path, "r", encoding="utf-8") as f:
                    logger.debug("TRF gerado para o Gacrux:\n%s", "".join(f.readlines()[:25]))

            # RGS-01: o comando (script no desenvolvimento, `Albericus.exe
            # --gacrux` no executável) mora num lugar só.
            script_path = gacrux_runner.script_path("pairing")
            if not script_path.exists():
                raise AppError(f"Motor Gacrux não encontrado em: {script_path}")
            project_root = PROJECT_ROOT

            cmd = gacrux_runner.gacrux_command("pairing", [
                "-i", str(input_path),
                "-o", str(output_path),
                "-b", "utf-8",
                "-p",
                "-n", str(round_number),
                "-m", "dutch",
                "-F", "JSON",
                "-v",
            ])
            if unpaired_ranks:
                cmd.extend(["-u"] + unpaired_ranks)

            env = os.environ.copy()
            env["PYTHONPATH"] = str(project_root)

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=str(project_root),
                    env=env,
                    timeout=GACRUX_TIMEOUT_SECONDS,
                )
                logger.debug("Gacrux STDOUT: %s", result.stdout)
                logger.debug("Gacrux STDERR: %s", result.stderr)
            except subprocess.TimeoutExpired as exc:
                raise AppError(
                    f"O motor Gacrux excedeu {GACRUX_TIMEOUT_SECONDS}s ao parear a rodada "
                    f"{round_number} e foi interrompido. Tente novamente ou use o motor próprio "
                    "nas configurações do torneio."
                ) from exc
            except Exception as e:
                raise AppError(f"Falha ao executar o motor Gacrux: {e}")

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Erro desconhecido"
                if NO_LEGAL_PAIRING_TAG in error_msg:
                    logger.warning("Gacrux sem pareamento legal na rodada %s: %s", round_number, error_msg)
                    raise GacruxNoLegalPairing(round_number, [])
                raise AppError(f"Erro no emparceiramento Gacrux: {error_msg}")

            if not output_path.exists():
                raise GacruxOutputRejected(
                    round_number, ["o motor não gerou o arquivo de saída esperado"]
                )

            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.debug("Gacrux data: %s", data)
            except (OSError, ValueError) as e:
                raise GacruxOutputRejected(
                    round_number, [f"arquivo de saída ilegível: {e}"]
                ) from e

            # Check status returned by Gacrux
            status = data.get("status", {})
            if status.get("code") != 0:
                errors = status.get("error", [])
                err_text = "; ".join(errors) if errors else "Erro interno do Gacrux"
                raise AppError(f"Gacrux: {err_text}")

            pairs = data.get("pairingResult", {}).get("pairs", [])
            try:
                final_pairings = pairings_from_gacrux(
                    pairs, rank_to_player_id, ranks_to_pair, round_number=round_number
                )
            except GacruxOutputRejected:
                # RGS-19: a saída não confere. O TRF que a produziu vai ao log
                # para o caso poder ser reproduzido fora do Albericus.
                logger.error(
                    "Saida do Gacrux recusada na rodada %s. Pares: %s\nTRF de entrada:\n%s",
                    round_number,
                    pairs,
                    input_path.read_text(encoding="utf-8"),
                )
                raise

            logger.debug("Rank -> player id: %s", rank_to_player_id)
            logger.debug("Pareamentos mapeados: %s", final_pairings)
            return final_pairings

    def write_pairing_trf(
        self,
        tournament_id: int,
        round_number: int,
        path: Path,
        *,
        accelerated_player_ids: Sequence[int] = (),
        acceleration_bonus: float = 0.0,
    ) -> dict[int, int]:
        """Grava em ``path`` o TRF que o Gacrux lê para parear ``round_number``.

        Devolve ``{start_rank: player_id}``. Levanta ``GacruxScoreMismatch`` se
        o arquivo não consegue dizer ao motor o placar da classificação (RGS-03).
        """
        from src.services.pairing_service import PairingService
        pairing_service = PairingService(self.db)
        export_service = ExportService(self.db, pairing_service)
        exporter = TRF16Exporter(export_service)

        # Mesma ordenação do exportador: o índice e o start-rank do TRF, que
        # segue a ordem inicial do torneio (`seeding_key`, RGS-13).
        all_players = seeding_order(
            self.db.list_players(tournament_id, active_only=False),
            self.db.get_tournament_settings(tournament_id) or {},
        )
        rank_to_player_id = {index: int(p["id"]) for index, p in enumerate(all_players, start=1)}

        exporter.export(tournament_id, path)
        # RGS-14: sem o 152 o Gacrux sorteia a cor a cada chamada, e a prévia
        # da R1 saia com uma cor e a geração com outra.
        initial_colour = resolve_initial_color(self.db, tournament_id)
        tournament = self.db.get_tournament(tournament_id) or {}
        score = pairing_score(
            float(tournament.get("bye_points", 1.0) or 0.0),
            self.db.list_point_adjustments(tournament_id),
            {player_id: rank for rank, player_id in rank_to_player_id.items()},
            round_number,
        )
        accelerated = {int(player_id) for player_id in accelerated_player_ids}
        self._adjust_trf_for_pairing(
            path,
            round_number,
            [rank for rank, player_id in rank_to_player_id.items() if player_id in accelerated],
            acceleration_bonus,
            score,
            prohibition_records(
                self.db.list_prohibited_pairings(tournament_id),
                round_number,
                {player_id: rank for rank, player_id in rank_to_player_id.items()},
            ),
            initial_colour=initial_colour,
            past_acceleration=self._past_acceleration_records(
                tournament_id,
                round_number,
                {player_id: rank for rank, player_id in rank_to_player_id.items()},
            ),
        )
        return rank_to_player_id

    def _past_acceleration_records(
        self,
        tournament_id: int,
        round_number: int,
        rank_by_player: dict[int, int],
    ) -> list[str]:
        """250 de cada rodada acelerada JÁ disputada (RGS-30).

        Float de rodada passada se mede pelo score de pareamento DELA (C.04.7
        1.5): só com o 250 da rodada pareada, o Gacrux via na R1/R2 floats que
        não houve e divergia do bbpPairings na R3/R4 — no Baku e na clássica.
        O plano de cada rodada e o mesmo que a pareou (`_round_acceleration`).
        """
        settings = self.db.get_tournament_settings(tournament_id) or {}
        if acceleration_spec(str(settings.get("acceleration_method") or "none"))["scheme"] == "none":
            return []
        from src.services.pairing_service import PairingService
        service = PairingService(self.db)
        lines: list[str] = []
        for past in range(1, int(round_number)):
            plan = service._round_acceleration(tournament_id, past)
            lines.extend(acceleration_records(
                float(plan.get("bonus") or 0.0),
                past,
                [rank_by_player[pid] for pid in plan.get("player_ids") or () if pid in rank_by_player],
            ))
        return lines

    def _adjust_trf_for_pairing(
        self,
        input_path: Path,
        round_number: int,
        accelerated_ranks: list[int],
        bonus: float,
        score: PairingScore,
        prohibitions: Sequence[str] = (),
        initial_colour: str = "",
        past_acceleration: Sequence[str] = (),
    ) -> None:
        """Reescreve o TRF exportado com o que só o PAREAMENTO precisa (PAR-02).

        O arquivo oficial de envio continua sendo o do exportador, intocado: o que
        entra aqui — registros 250 (aceleração), 162 (valor do PAB) e 299 (ajustes
        do árbitro), e células coerentes com os pontos da classificação — existe
        para o motor pontuar como a classificação pontua (RGS-03). Os 260
        (`prohibitions`) levam as proibições desta rodada (RGS-15). O 152 leva a
        cor inicial gravada no torneio (RGS-14).
        """
        with open(input_path, "r", encoding="utf-8", newline="") as handle:
            lines = handle.read().splitlines()

        # O exportador também declara a aceleração (registro 250, FED-03), mas
        # para o TORNEIO inteiro; aqui o que vale e o conjunto acelerado DESTA
        # rodada (PAR-02). Duas declarações deixariam a última vencer por ordem
        # no arquivo — preferimos remover a do exportador e escrever a nossa.
        # O mesmo vale para 162/299: quem diz o placar ao motor e o `score`.
        lines = [line for line in lines if line[:3] not in {"250", "162", "299", "260", "152"}]
        lines, mismatches = reconcile_scores(lines, score)
        if mismatches:
            # RGS-03: a checagem continua DEPOIS de reconcile_scores. O que o
            # arquivo ainda não consegue dizer ao motor recusa a rodada antes de
            # o Gacrux rodar — ele parearia com outro placar ou quebraria.
            for item in mismatches:
                logger.warning("Rodada %s (Gacrux recusado): %s", round_number, item)
            raise GacruxScoreMismatch(round_number, mismatches)
        if initial_colour in ("W", "B"):
            # `trf2json.parse_trf_initialcolor` lê `line[4:]`: "152 W" ou "152 B".
            lines.append(f"152 {initial_colour}")
        lines.extend(score.records())
        lines.extend(past_acceleration)
        lines.extend(acceleration_records(bonus, round_number, accelerated_ranks))
        lines.extend(prohibitions)

        with open(input_path, "w", encoding="utf-8", newline="") as handle:
            handle.write("".join(f"{line}\r\n" for line in lines))

    # ------------------------------------------------------------------ #
    # Verificação (RGS-16): `pairingchecker -c` sobre a rodada gravada
    # ------------------------------------------------------------------ #
    def check_round(
        self,
        tournament_id: int,
        round_number: int,
        *,
        accelerated_player_ids: Sequence[int] = (),
        acceleration_bonus: float = 0.0,
    ) -> PairingCheck:
        """Confere a rodada GRAVADA contra o que o holandês do Gacrux produziria.

        Roda o ``pairingchecker`` em modo de verificação (``-c -n <rodada>``)
        sobre o TRF do torneio com a rodada já pareada: o motor refaz o
        pareamento dela a partir das rodadas anteriores e devolve os dois.
        Nunca levanta: o que impede a conferência volta como
        ``PairingCheck(checked=False, error=...)`` — quem chama registra.
        """
        try:
            return self._check_round(
                tournament_id,
                round_number,
                accelerated_player_ids=accelerated_player_ids,
                acceleration_bonus=acceleration_bonus,
            )
        except AppError as exc:
            logger.warning("Rodada %s nao verificada pelo Gacrux: %s", round_number, exc)
            return unchecked(round_number, str(exc))
        except Exception as exc:  # pragma: no cover - defesa: verificar nunca derruba a rodada
            logger.exception("Falha inesperada ao verificar a rodada %s", round_number)
            return unchecked(round_number, f"falha inesperada: {exc}")

    def _check_round(
        self,
        tournament_id: int,
        round_number: int,
        *,
        accelerated_player_ids: Sequence[int],
        acceleration_bonus: float,
    ) -> PairingCheck:
        round_data = self.db.get_round_by_number(tournament_id, round_number)
        if not round_data:
            raise AppError(f"rodada {round_number} não encontrada")
        pairings = self.db.get_pairings_for_round(int(round_data["id"]))
        stored = stored_pairs(pairings)
        paired_ids = paired_player_ids(pairings)

        from src.services.pairing_service import PairingService
        export_service = ExportService(self.db, PairingService(self.db))
        all_players = seeding_order(
            self.db.list_players(tournament_id, active_only=False),
            self.db.get_tournament_settings(tournament_id) or {},
        )
        rank_to_player_id = {index: int(p["id"]) for index, p in enumerate(all_players, start=1)}
        rank_by_player = {player_id: rank for rank, player_id in rank_to_player_id.items()}
        names = {int(p["id"]): str(p.get("name") or "") for p in all_players}

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "check.trf"
            output_path = Path(tmpdir) / "check.json"
            TRF16Exporter(export_service).export(tournament_id, input_path)
            tournament = self.db.get_tournament(tournament_id) or {}
            score = pairing_score(
                float(tournament.get("bye_points", 1.0) or 0.0),
                self.db.list_point_adjustments(tournament_id),
                rank_by_player,
                round_number,
            )
            lines = input_path.read_text(encoding="utf-8").splitlines()
            lines = [line for line in lines if line[:3] not in {"250", "260"}]
            # O campo de pontos do exportador e o da classificação (rodadas
            # FECHADAS); as células já trazem a rodada verificada (o PAB dela
            # inclusive). O alvo e recalculado das células, como no desempate.
            lines, problems = rebased_score_lines(
                lines,
                score,
                {rank_by_player[int(p["id"])]: float(p.get("starting_points") or 0.0) for p in all_players},
            )
            if problems:
                raise AppError("; ".join(problems))
            accelerated = {int(player_id) for player_id in accelerated_player_ids}
            lines.extend(self._past_acceleration_records(tournament_id, round_number, rank_by_player))
            lines.extend(acceleration_records(
                acceleration_bonus,
                round_number,
                [rank for rank, player_id in rank_to_player_id.items() if player_id in accelerated],
            ))
            lines.extend(prohibition_records(
                self.db.list_prohibited_pairings(tournament_id), round_number, rank_by_player
            ))
            input_path.write_text("".join(f"{line}\r\n" for line in lines), encoding="utf-8", newline="")

            unpaired = [str(rank) for rank, player_id in sorted(rank_to_player_id.items()) if player_id not in paired_ids]
            cmd = gacrux_runner.gacrux_command("pairing", [
                "-i", str(input_path),
                "-o", str(output_path),
                "-b", "utf-8",
                "-c",
                "-n", str(round_number),
                "-m", "dutch",
                "-F", "JSON",
            ])
            if unpaired:
                cmd.extend(["-u"] + unpaired)
            data = self._run_checker(cmd, output_path, round_number, input_path)

        bloco = checker_round(data, round_number)
        if bloco is None:
            raise AppError("o verificador não devolveu a rodada")
        return PairingCheck(
            round_number=int(round_number),
            checked=True,
            stored=stored,
            expected=pairs_from_checker(bloco.get("pairs") or [], rank_to_player_id),
            names=names,
        )

    @staticmethod
    def _run_checker(
        cmd: list[str], output_path: Path, round_number: int, input_path: Path
    ) -> dict[str, Any]:
        if not gacrux_runner.script_path("pairing").exists():
            raise AppError("motor Gacrux não encontrado")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                cwd=str(PROJECT_ROOT),
                env=env,
                timeout=GACRUX_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise AppError(f"o verificador excedeu {GACRUX_TIMEOUT_SECONDS}s") from exc
        # Modo -c: código 1 = "pareamento difere", que é resposta, não erro.
        if result.returncode not in (0, 1) or not output_path.exists():
            logger.error(
                "Verificador Gacrux falhou na rodada %s (%s): %s\nTRF:\n%s",
                round_number,
                result.returncode,
                (result.stderr or result.stdout).strip(),
                input_path.read_text(encoding="utf-8"),
            )
            raise AppError(
                (result.stderr.strip() or result.stdout.strip() or "erro desconhecido")[-500:]
            )
        try:
            data = json.loads(output_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise AppError(f"saída ilegível do verificador: {exc}") from exc
        status = data.get("status", {})
        if status.get("code") not in (0, 1):
            raise AppError("; ".join(status.get("error", [])) or "erro interno do Gacrux")
        return data
