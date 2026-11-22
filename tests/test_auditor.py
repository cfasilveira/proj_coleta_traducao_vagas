"""Contrato do auditor: as funções nunca levantam e encaminham ao logger
de execução (configurar_log) com prefixo ``[MODULO]``."""

import logging

import pytest

import auditor


@pytest.fixture(autouse=True)
def _limpa_execucao_log():
    """Remove o efeito colateral de arquivo criado no import do auditor."""
    from pathlib import Path

    caminho = Path("execucao.log")
    if caminho.exists():
        caminho.unlink()
    yield


def test_funcoes_nao_levantam(caplog):
    for funcao in (auditor.info, auditor.warning, auditor.error, auditor.critical, auditor.fatal):
        with caplog.at_level(logging.DEBUG, logger="exec.auditor"):
            funcao("modulo_teste", "mensagem de prova")
    auditor.estouro_caracteres("modulo_teste", "texto muito longo")


def test_info_warning_error_critical_usam_prefixo(caplog):
    casos = [
        (auditor.info, logging.INFO),
        (auditor.warning, logging.WARNING),
        (auditor.error, logging.ERROR),
        (auditor.critical, logging.CRITICAL),
    ]
    for funcao, nivel in casos:
        with caplog.at_level(nivel, logger="exec.auditor"):
            funcao("modulo_teste", "mensagem de prova")
        registros = [r for r in caplog.records if r.name == "exec.auditor"]
        assert registros, f"{funcao.__name__} não gravou"
        assert "[MODULO_TESTE]" in registros[-1].getMessage()
        assert "mensagem de prova" in registros[-1].getMessage()


def test_fatal_marca_fatal(caplog):
    with caplog.at_level(logging.CRITICAL, logger="exec.auditor"):
        auditor.fatal("modulo_teste", "erro grave")
    registros = [r for r in caplog.records if r.name == "exec.auditor"]
    assert "FATAL: erro grave" in registros[-1].getMessage()


def test_estouro_caracteres_marca_estouro(caplog):
    with caplog.at_level(logging.WARNING, logger="exec.auditor"):
        auditor.estouro_caracteres("modulo_teste", "limite excedido")
    registros = [r for r in caplog.records if r.name == "exec.auditor"]
    assert "[ESTOURO_CARACTERES]" in registros[-1].getMessage()
    assert "limite excedido" in registros[-1].getMessage()


def test_logger_usa_nivel_debug():
    assert auditor._LOGGER.level == logging.DEBUG
    assert auditor._LOGGER.name == "exec.auditor"
