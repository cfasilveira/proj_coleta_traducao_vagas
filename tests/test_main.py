"""Contrato do main do ADEM: tradução primária + retry via lib."""

import asyncio
from unittest.mock import patch

import pytest

import main as main_module


def _oferta(texto: str) -> dict:
    return {"url": "https://x/1", "titulo": "T", "texto": texto, "traduzido": False, "texto_traduzido": ""}


def test_todas_traduzem_na_primaria():
    with patch.object(main_module, "traduzir", return_value=(True, "traduzido", False)):
        resultado = asyncio.run(main_module._traduzir_com_buffer([_oferta("texto 1"), _oferta("texto 2")]))
    assert len(resultado) == 2
    assert all(o["traduzido"] is True and o["texto_traduzido"] == "traduzido" for o in resultado)


def test_estouro_de_tamanho_nao_entra_no_retry():
    longo = "x" * (main_module.LIMITE_CARACTERES if hasattr(main_module, "LIMITE_CARACTERES") else 4000 + 1)
    with patch.object(main_module, "traduzir", return_value=(False, longo, False)):
        resultado = asyncio.run(main_module._traduzir_com_buffer([_oferta(longo)]))
    assert len(resultado) == 1
    assert resultado[0]["traduzido"] is False
    assert resultado[0]["texto_traduzido"] == ""


def test_falha_retentavel_vai_para_retry_e_fica_apos_esgotar():
    # Sempre falha (retentável): repetir_async esgota as tentativas e levanta.
    with patch.object(main_module, "traduzir", return_value=(False, "texto", True)), \
         patch.object(main_module, "ESPERA_ENTRE_RETRIES", (0, 0, 0)):
        resultado = asyncio.run(main_module._traduzir_com_buffer([_oferta("texto")]))
    assert len(resultado) == 1
    assert resultado[0]["traduzido"] is False
    assert resultado[0]["texto_traduzido"] == ""


def test_falha_retentavel_sucesso_no_retry():
    chamadas = {"n": 0}

    def traduzir_fake(texto):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            return (False, texto, True)  # retentável -> repetir_async retenta
        return (True, texto.upper(), False)

    with patch.object(main_module, "traduzir", side_effect=lambda t: traduzir_fake(t)), \
         patch.object(main_module, "ESPERA_ENTRE_RETRIES", (0, 0, 0)):
        oferta = _oferta("ola")
        resultado = asyncio.run(main_module._traduzir_com_buffer([oferta]))
    assert resultado[0]["traduzido"] is True
    assert resultado[0]["texto_traduzido"] == "OLA"
    assert chamadas["n"] == 2
