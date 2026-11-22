"""Extrator de ofertas do ADEM (Luxemburgo).

Delegado a ``proj_biblioteca.scraping`` (navegador, coleta de links e limpeza
de texto). Mantém a filosofia do ADEM: fail-first (sem link → lista vazia),
graceful fall (texto 100% de ruído → devolve o bruto) e fechamento garantido do
navegador (evita processo zumbi).
"""

from __future__ import annotations

from urllib.parse import urljoin

from proj_biblioteca import scraping

import auditor

BASE_URL = "https://adem.public.lu/en/jobboard.html#q=data+analyst&mode=any"

LINK_SELECTORS = [
    "a[href*='/job-offer/']",
    "a[href*='/offre-emploi/']",
    ".job-offer-link",
    "article a",
]

# Linhas de ruído comuns em todas as páginas ADEM (não são ofertas).
_RUIDO_MARCADORES = (
    "This site uses cookies",
    "Accept",
    "Decline",
    "Manage cookies",
    "Go to main menu",
    "Go to content",
    "The Luxembourg Jobmarket",
    "Jobseekers",
    "Employees",
    "Employers",
    "Job Mobility",
    "Access to JobBoard",
    "Home",
    "Listen",
    "Back to results",
    "Footer",
    "Agence pour le développement",
    "Where to find us",
    "The Contact Center",
    "Monday to Friday",
    "Our agencies welcome",
    "Facebook",
    "LinkedIn",
    "Instagram",
    "YouTube",
    "Latest news",
    "Publications",
    "Forms",
    "Contact",
    "FAQ",
    "Sitemap",
    "Accessibility",
    "About this site",
    "Legal notice",
    "Data Protection",
    "ADEM recruits",
)


async def _coletar_links(page) -> list[str]:
    for seletor in LINK_SELECTORS:
        try:
            await page.wait_for_selector(seletor, timeout=5000)
            elementos = await page.query_selector_all(seletor)
        except scraping.ScrapingIndisponivel:
            raise
        except Exception:  # timeout do Playwright: tenta o próximo seletor
            continue
        hrefs = [await el.get_attribute("href") for el in elementos]
        unicos = scraping.links_unicos(hrefs, urljoin(BASE_URL, "/"))
        if unicos:
            auditor.info("extrator", f"Seletor '{seletor}' coletou {len(unicos)} URLs.")
            return unicos
    return []


async def extrair_ofertas() -> list[dict] | None:
    ofertas: list[dict] = []

    try:
        async with scraping.navegador(headless=False) as browser:
            page = await browser.new_page()
            page.set_default_timeout(45000)

            auditor.info("extrator", f"Acessando: {BASE_URL}")
            try:
                response = await page.goto(BASE_URL, timeout=60000)
                if response and response.status >= 400:
                    auditor.fatal(
                        "extrator", f"Página inicial retornou HTTP {response.status}."
                    )
                    return None
                await page.wait_for_load_state("networkidle", timeout=30000)
            except Exception as e:  # noqa: BLE001 - falha de carregamento da inicial
                auditor.warning("extrator", f"Rede não ficou ociosa a tempo: {e}. Continuando.")

            urls = await _coletar_links(page)

            if not urls:
                auditor.warning("extrator", "Nenhum link encontrado. Salvando HTML de debug.")
                try:
                    html = await page.content()
                    with open("debug_page.html", "w", encoding="utf-8") as f:
                        f.write(html)
                except OSError as e:
                    auditor.error("extrator", f"Falha ao salvar HTML de debug: {e}")
                return []

            auditor.info("extrator", f"Extraindo {len(urls)} ofertas...")

            for i, url in enumerate(urls, start=1):
                auditor.info("extrator", f"[{i}/{len(urls)}] {url}")
                try:
                    await page.goto(url, timeout=60000)
                    await page.wait_for_load_state("domcontentloaded", timeout=30000)

                    titulo = (await page.title()).strip() or "Sem título"

                    bruto = await page.inner_text("body")
                    texto_final = scraping.extrair_texto(bruto, _RUIDO_MARCADORES)

                    ofertas.append({"url": url, "titulo": titulo, "texto": texto_final})

                except Exception as e:  # noqa: BLE001 - falha em uma oferta: pula (graceful fall)
                    auditor.error("extrator", f"Erro ao extrair {url}: {e}. Pulando.")

    except scraping.ScrapingIndisponivel as e:
        auditor.fatal("extrator", f"Navegador indisponível: {e}")
        return None
    except Exception as e:  # noqa: BLE001 - catch-all final do pipeline
        auditor.fatal("extrator", f"Erro catastrófico: {e}")
        return None

    return ofertas
