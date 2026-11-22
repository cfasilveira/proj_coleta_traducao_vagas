"""Contrato do tradutor do ADEM: delega a traducao.traduzir da lib."""

import asyncio
from unittest.mock import patch

import pytest

import tradutor_texto as tt
from proj_biblioteca import traducao


@pytest.fixture
def _mock_traduzir():
    with patch.object(tt.traducao, "traduzir") as mock:
        yield mock


def test_texto_vazio_early_return(_mock_traduzir):
    _mock_traduzir.return_value = (True, "", False)
    assert asyncio.run(tt.traduzir("")) == (True, "", False)
    assert asyncio.run(tt.traduzir("   ")) == (True, "", False)
    _mock_traduzir.assert_called()


def test_estouro_de_limite_aborta_sem_retry(_mock_traduzir):
    _mock_traduzir.return_value = (False, "x" * (traducao.LIMITE_CARACTERES + 1), False)
    original = "x" * (traducao.LIMITE_CARACTERES + 1)
    assert asyncio.run(tt.traduzir(original)) == (False, original, False)
    _mock_traduzir.assert_called_once()


def test_traducao_bem_sucedida(_mock_traduzir):
    _mock_traduzir.return_value = (True, "olá mundo", False)
    assert asyncio.run(tt.traduzir("hello world")) == (True, "olá mundo", False)


def test_rate_limit_retentavel(_mock_traduzir):
    _mock_traduzir.return_value = (False, "hello world", True)
    assert asyncio.run(tt.traduzir("hello world")) == (False, "hello world", True)


def test_chama_traducao_com_fabrica_e_parametros(_mock_traduzir):
    _mock_traduzir.return_value = (True, "ok", False)
    asyncio.run(tt.traduzir("qualquer coisa"))
    args, kwargs = _mock_traduzir.call_args
    assert args[0] == "qualquer coisa"
    assert callable(kwargs["fabrica"])
    assert kwargs["destino"] == "pt"
    assert kwargs["limite"] == traducao.LIMITE_CARACTERES
