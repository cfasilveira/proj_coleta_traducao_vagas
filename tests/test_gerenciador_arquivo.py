"""Contrato do gerenciador de arquivo: escrita atômica via persistencia da lib."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

import gerenciador_arquivo as ga


def test_salvar_ofertas_vazio_early_return(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gravou = {}

    def falso(caminho, conteudo):
        gravou["chamado"] = True
        gravou["conteudo"] = conteudo

    with patch.object(ga.persistencia, "escrever_atomico", side_effect=falso):
        assert asyncio.run(ga.salvar_ofertas([])) is True
    assert not gravou  # early return: nada gravado


def test_salvar_ofertas_grava_conteudo_correto(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gravou = {}

    def falso(caminho, conteudo):
        gravou["caminho"] = str(caminho)
        gravou["conteudo"] = conteudo
        return Path(caminho)

    ofertas = [
        {"url": "https://x/1", "titulo": "Vaga A", "traduzido": True, "texto_traduzido": "texto A"},
        {"url": "https://x/2", "titulo": "Vaga B", "traduzido": False},
    ]
    with patch.object(ga.persistencia, "escrever_atomico", side_effect=falso):
        assert asyncio.run(ga.salvar_ofertas(ofertas)) is True
    assert gravou["caminho"] == "ofertas_Luxemburgo.txt"
    conteudo = gravou["conteudo"]
    assert "RELATÓRIO DE OFERTAS DE EMPREGO" in conteudo
    assert "https://x/1" in conteudo and "texto A" in conteudo
    assert "[NÃO TRADUZIDO] Vaga B" in conteudo
    assert "Traduzidas: 1 | Não traduzidas: 1" in conteudo


def test_salvar_ofertas_permission_error_retorna_falso(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def falso(caminho, conteudo):
        raise PermissionError("sem permissão")

    with patch.object(ga.persistencia, "escrever_atomico", side_effect=falso):
        assert asyncio.run(ga.salvar_ofertas([{"url": "u", "titulo": "t"}])) is False


def test_salvar_ofertas_os_error_retorna_falso(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def falso(caminho, conteudo):
        raise OSError("disco cheio")

    with patch.object(ga.persistencia, "escrever_atomico", side_effect=falso):
        assert asyncio.run(ga.salvar_ofertas([{"url": "u", "titulo": "t"}])) is False
