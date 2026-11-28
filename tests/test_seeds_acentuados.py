"""Textos semeados no banco com acento (níveis e modelos de certificado) — v59.

Os padrões que o banco semeia (``DEFAULT_LEARNING_LEVELS``,
``DEFAULT_CERTIFICATE_TEMPLATES`` e as assinaturas da galeria) aparecem na tela
e nos certificados impressos, e estavam sem acento ("Intermediario",
"Certificado de Participacao"). Banco novo nasce acentuado; banco antigo é
corrigido pela migração v59, que só troca o valor gravado quando ele é
exatamente o padrão antigo — o padrão antigo é o novo dobrado para ASCII
(``to_ascii``). O que o usuário editou fica como está.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.core.database import Database
from src.database.migrations.legacy_migrations import LegacyMigrations
from src.services.text_ascii import to_ascii

_CAMPOS = {
    "learning_levels": ("name", "description"),
    "certificate_templates": (
        "name",
        "title_template",
        "body_template",
        "footer_template",
        "signature_left",
        "signature_right",
    ),
}


def _envelhecer(db: Database, versao: int = 58, tabelas: dict[str, tuple[str, ...]] | None = None) -> None:
    """Deixa o banco como a v58 gravava: todo texto semeado sem acento."""
    with closing(sqlite3.connect(db.db_path)) as conexao:
        for tabela, campos in (tabelas or _CAMPOS).items():
            for linha in conexao.execute(f"SELECT id, {', '.join(campos)} FROM {tabela}").fetchall():
                valores = [to_ascii(str(valor or "")) for valor in linha[1:]]
                atribuicoes = ", ".join(f"{campo} = ?" for campo in campos)
                conexao.execute(f"UPDATE {tabela} SET {atribuicoes} WHERE id = ?", (*valores, linha[0]))
        conexao.execute(f"PRAGMA user_version = {versao}")
        conexao.commit()


def _niveis(db: Database) -> dict[str, dict]:
    return {str(n["name"]): n for n in db.list_learning_levels(active_only=False)}


def _modelos(db: Database) -> dict[str, dict]:
    return {str(m["name"]): m for m in db.list_certificate_templates(active_only=False)}


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base = Path(self._tmp.name)
        self.db = Database(db_path=self.base / "t.db", backup_dir=self.base / "bk")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _reabrir(self) -> Database:
        return Database(db_path=self.base / "t.db", backup_dir=self.base / "bk")


class BancoNovoTest(_Base):
    def test_niveis_nascem_acentuados(self) -> None:
        niveis = _niveis(self.db)
        for nome in ("Iniciante", "Básico", "Intermediário", "Avançado", "Competitivo"):
            self.assertIn(nome, niveis)
        self.assertIn("peças", niveis["Iniciante"]["description"])
        self.assertIn("anotação", niveis["Intermediário"]["description"])

    def test_modelos_nascem_acentuados(self) -> None:
        modelos = _modelos(self.db)
        participacao = modelos["Participação padrão"]
        self.assertEqual("Certificado de Participação", participacao["title_template"])
        self.assertIn("colocação na classificação", participacao["body_template"])
        self.assertEqual("Organização", participacao["signature_left"])
        self.assertEqual("Arbitragem / Direção", participacao["signature_right"])
        self.assertIn("Peças marca d'água - Ranking interno", modelos)
        self.assertEqual("Coordenação", modelos["Membro aluno padrão"]["signature_left"])

    def test_nada_semeado_fica_sem_acento(self) -> None:
        """Nenhum texto semeado é a versão sem acento de outro que deveria ter."""
        for linha in [*self.db.list_learning_levels(), *self.db.list_certificate_templates()]:
            for campo in ("name", "description", "title_template", "body_template"):
                valor = str(linha.get(campo) or "")
                for palavra in ("Basico", "Intermediario", "Avancado", "Participacao", "Premiacao", "padrao"):
                    self.assertNotIn(palavra, valor, f"{campo} = {valor!r}")


class MigracaoV59Test(_Base):
    def test_versao_do_esquema(self) -> None:
        # A v59 existe e vem antes das seguintes (v60: sexo do membro, RG2-47).
        self.assertGreaterEqual(Database.SCHEMA_VERSION, 59)

    def test_padrao_antigo_vira_acentuado_e_edicao_do_usuario_fica(self) -> None:
        _envelhecer(self.db)
        # Edição do usuário: descrição de um nível e assinatura de um modelo.
        with closing(sqlite3.connect(self.db.db_path)) as conexao:
            conexao.execute(
                "UPDATE learning_levels SET description = 'Minha descricao propria' WHERE name = 'Avancado'"
            )
            conexao.execute(
                "UPDATE certificate_templates SET signature_right = 'Coordenacao geral' "
                "WHERE name = 'Evento padrao'"
            )
            conexao.commit()

        migrado = self._reabrir()
        niveis = _niveis(migrado)
        self.assertEqual(
            {"Iniciante", "Básico", "Intermediário", "Avançado", "Competitivo"}, set(niveis)
        )
        self.assertIn("anotação", niveis["Intermediário"]["description"])
        # Nome era o padrão antigo (troca); descrição foi editada (fica).
        self.assertEqual("Minha descricao propria", niveis["Avançado"]["description"])

        modelos = _modelos(migrado)
        self.assertNotIn("Participacao padrao", modelos)
        participacao = modelos["Participação padrão"]
        self.assertEqual("Certificado de Participação", participacao["title_template"])
        self.assertEqual("Arbitragem / Direção", participacao["signature_right"])
        evento = modelos["Evento padrão"]
        self.assertEqual("Organização", evento["signature_left"])
        self.assertEqual("Coordenacao geral", evento["signature_right"])
        with closing(sqlite3.connect(migrado.db_path)) as conexao:
            self.assertEqual(Database.SCHEMA_VERSION, conexao.execute("PRAGMA user_version").fetchone()[0])

    def test_referencias_continuam_ligadas(self) -> None:
        _envelhecer(self.db)
        intermediario = _niveis(self.db)["Intermediario"]
        membro = self.db.create_member("Ana", learning_level_id=int(intermediario["id"]))
        modelo = _modelos(self.db)["Participacao padrao"]
        emissoes = self.db.create_certificate_issuances(
            [
                {
                    "verification_code": "ALB-1",
                    "recipient_name": "Ana",
                    "template_id": int(modelo["id"]),
                    "template_name": "Participacao padrao",
                },
                {
                    # Nome gravado que não é o padrão antigo: fica.
                    "verification_code": "ALB-2",
                    "recipient_name": "Bia",
                    "template_id": int(modelo["id"]),
                    "template_name": "Outro nome",
                },
            ]
        )
        self.assertEqual(2, len(emissoes))

        migrado = self._reabrir()
        self.assertEqual("Intermediário", migrado.get_member(membro)["learning_level_name"])
        por_codigo = {e["verification_code"]: e for e in migrado.list_certificate_issuances()}
        self.assertEqual("Participação padrão", por_codigo["ALB-1"]["template_name"])
        self.assertEqual("Outro nome", por_codigo["ALB-2"]["template_name"])
        self.assertEqual(int(modelo["id"]), int(por_codigo["ALB-1"]["template_id"]))

    def test_galeria_ganha_assinatura_acentuada(self) -> None:
        from src.services.certificate_service import CertificateService
        from src.services.pairing_service import PairingService

        CertificateService(self.db, PairingService(self.db)).seed_gallery(3)
        # A galeria já grava nome e texto acentuados; só a assinatura vinha sem.
        _envelhecer(self.db, tabelas={"certificate_templates": ("signature_left", "signature_right")})
        migrado = self._reabrir()
        galeria = [m for m in migrado.list_certificate_templates() if " · " in str(m["name"])]
        self.assertEqual(3, len(galeria))
        for modelo in galeria:
            self.assertEqual("Organização", modelo["signature_left"])
            self.assertEqual("Arbitragem / Direção", modelo["signature_right"])

    def test_idempotente(self) -> None:
        _envelhecer(self.db)
        migrado = self._reabrir()
        antes = (_niveis(migrado), _modelos(migrado))
        with migrado.connect() as conexao:
            LegacyMigrations(migrado)._ensure_current_schema(conexao)
        depois = (_niveis(self._reabrir()), _modelos(self._reabrir()))
        self.assertEqual(
            {k: (v["id"], v["description"]) for k, v in antes[0].items()},
            {k: (v["id"], v["description"]) for k, v in depois[0].items()},
        )
        self.assertEqual(
            {k: (v["id"], v["title_template"], v["signature_left"]) for k, v in antes[1].items()},
            {k: (v["id"], v["title_template"], v["signature_left"]) for k, v in depois[1].items()},
        )

    def test_banco_antigo_nao_duplica_o_padrao(self) -> None:
        """Da v3 em diante as sementes (v4, v5, v8) rodam ANTES da v59.

        A semente nova não pode entrar ao lado da antiga ("Básico" junto de
        "Basico"): ela reconhece o padrão sem acento como já semeado.
        """
        _envelhecer(self.db, versao=3)
        migrado = self._reabrir()
        self.assertEqual(
            {"Iniciante", "Básico", "Intermediário", "Avançado", "Competitivo"}, set(_niveis(migrado))
        )
        nomes = set(_modelos(migrado))
        self.assertIn("Participação padrão", nomes)
        self.assertNotIn("Participacao padrao", nomes)

    def test_nome_acentuado_ja_criado_pelo_usuario_nao_quebra(self) -> None:
        """O usuário já tinha criado "Básico" à mão ao lado do "Básico" semeado."""
        _envelhecer(self.db)
        with closing(sqlite3.connect(self.db.db_path)) as conexao:
            conexao.execute(
                "INSERT INTO learning_levels (name, description, display_order, active, created_at, updated_at)"
                " VALUES ('Básico', 'criado a mao', 99, 1, '', '')"
            )
            conexao.commit()
        migrado = self._reabrir()
        niveis = _niveis(migrado)
        self.assertEqual("criado a mao", niveis["Básico"]["description"])
        self.assertIn("Basico", niveis)  # o semeado fica com o nome: não há para onde ir


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
