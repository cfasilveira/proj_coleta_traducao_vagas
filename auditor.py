"""Auditor de execução do ADEM.

Delegado a ``proj_biblioteca.log.configurar_log`` (logger de execução com
arquivo + console, idempotente). Mantém a API histórica:
``info/warning/error/critical/fatal/estouro_caracteres(modulo, mensagem)``,
com prefixo ``[MODULO]`` e gravação em ``execucao.log``.

Nunca levanta: falhas de log são absorvidas (graceful fall) para não derrubar
o pipeline.
"""

from __future__ import annotations

from proj_biblioteca.log import configurar_log

_LOGGER = configurar_log(
    "auditor",
    arquivo="execucao.log",
    console=True,
    nivel="DEBUG",
    formato="texto",
)


def _fmt(modulo: str, mensagem: str) -> str:
    return f"[{modulo.upper():<10}] {mensagem}"


def info(modulo: str, mensagem: str) -> None:
    _LOGGER.info(_fmt(modulo, mensagem))


def warning(modulo: str, mensagem: str) -> None:
    _LOGGER.warning(_fmt(modulo, mensagem))


def error(modulo: str, mensagem: str) -> None:
    _LOGGER.error(_fmt(modulo, mensagem))


def critical(modulo: str, mensagem: str) -> None:
    _LOGGER.critical(_fmt(modulo, mensagem))


def fatal(modulo: str, mensagem: str) -> None:
    _LOGGER.critical(_fmt(modulo, f"FATAL: {mensagem}"))


def estouro_caracteres(modulo: str, mensagem: str) -> None:
    """Categoria dedicada: texto excedeu o limite operacional do MVP.

    Falha esperada e caracterizada — não é erro de rede nem bloqueio.
    """
    _LOGGER.warning(_fmt(modulo, f"[ESTOURO_CARACTERES] {mensagem}"))
