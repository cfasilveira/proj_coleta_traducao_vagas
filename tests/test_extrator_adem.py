"""Contrato do extrator do ADEM: delega navegacao/texto a scraping da lib."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import extrator_adem as ex
from proj_biblioteca import scraping


class _PageFake:
    def __init__(self, links, textos_por_url):
        self.links = links
        self.textos_por_url = textos_por_url
        self.visitadas = []
        self.titulos = {}

    async def _valor(self, v):
        return v

    async def wait_for_selector(self, seletor, timeout=0):
        return None

    async def set_default_timeout(self, timeout):
        return None

    async def query_selector_all(self, seletor):
        # Apenas o primeiro seletor "bom" retorna elementos com href.
        if seletor == "a[href*='/job-offer/']":
            return [SimpleNamespace(get_attribute=lambda n, h=h: self._valor(h)) for h in self.links]
        return []

    async def goto(self, url, timeout=0):
        self.visitadas.append(url)

    async def wait_for_load_state(self, estado, timeout=0):
        return None

    async def title(self):
        return self.titulos.get(self.visitadas[-1] if self.visitadas else "", "Sem título")

    async def inner_text(self, seletor):
        return self.textos_por_url.get(self.visitadas[-1], "")

    async def content(self):
        return "<html></html>"


class _NavegadorFake:
    def __init__(self, page):
        self._page = page

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def new_page(self):
        return self._page


def test_extrair_ofertas_busca_links_e_texto():
    links = ["https://adem.public.lu/job-offer/1", "https://adem.public.lu/job-offer/2"]
    textos = {
        "https://adem.public.lu/job-offer/1": "Vaga de analista\nAccept\nSalário 3.500",
        "https://adem.public.lu/job-offer/2": "Vaga de dev\nDecline\nRemoto",
    }
    page = _PageFake(links, textos)
    page.titulos = {links[0]: "Analista de Dados", links[1]: "Dev Python"}

    with patch.object(
        ex.scraping, "navegador", return_value=_NavegadorFake(page)
    ):
        ofertas = asyncio.run(ex.extrair_ofertas())

    assert ofertas is not None
    assert len(ofertas) == 2
    assert ofertas[0]["url"] == links[0]
    assert ofertas[0]["titulo"] == "Analista de Dados"
    assert "Vaga de analista" in ofertas[0]["texto"]
    assert "Accept" not in ofertas[0]["texto"]
    assert ofertas[1]["titulo"] == "Dev Python"


def test_extrair_ofertas_sem_links_retorna_lista_vazia():
    page = _PageFake([], {})
    with patch.object(
        ex.scraping, "navegador", return_value=_NavegadorFake(page)
    ):
        ofertas = asyncio.run(ex.extrair_ofertas())
    assert ofertas == []


def test_extrair_ofertas_navegador_indisponivel_retorna_none():
    with patch.object(
        ex.scraping,
        "navegador",
        side_effect=scraping.ScrapingIndisponivel("sem playwright"),
    ):
        assert asyncio.run(ex.extrair_ofertas()) is None
