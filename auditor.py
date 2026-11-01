import logging
import sys

LOG_FILE = "execucao.log"

_logger = logging.getLogger("auditor")
_logger.setLevel(logging.DEBUG)

if not _logger.handlers:
    # Fail First: falha de log não derruba o pipeline
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        _logger.addHandler(file_handler)
    except OSError as e:
        print(f"[AUDITOR] Aviso: não foi possível abrir {LOG_FILE}: {e}", file=sys.stderr)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    ))
    _logger.addHandler(console_handler)


def _fmt(modulo: str, mensagem: str) -> str:
    return f"[{modulo.upper():<10}] {mensagem}"


def info(modulo: str, mensagem: str) -> None:
    _logger.info(_fmt(modulo, mensagem))


def warning(modulo: str, mensagem: str) -> None:
    _logger.warning(_fmt(modulo, mensagem))


def error(modulo: str, mensagem: str) -> None:
    _logger.error(_fmt(modulo, mensagem))


def critical(modulo: str, mensagem: str) -> None:
    _logger.critical(_fmt(modulo, mensagem))


def fatal(modulo: str, mensagem: str) -> None:
    _logger.critical(_fmt(modulo, f"FATAL: {mensagem}"))


def estouro_caracteres(modulo: str, mensagem: str) -> None:
    """
    Categoria dedicada: texto excedeu o limite operacional do MVP.
    É uma falha esperada e caracterizada — não é erro de rede nem bloqueio.
    """
    _logger.warning(_fmt(modulo, f"[ESTOURO_CARACTERES] {mensagem}"))