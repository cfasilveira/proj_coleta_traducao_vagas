from urllib.parse import urljoin
from playwright.async_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)
import auditor

BASE_URL = "https://adem.public.lu/en/jobboard.html#q=data+analyst&mode=any"

LINK_SELECTORS = [
    "a[href*='/job-offer/']",
    "a[href*='/offre-emploi/']",
    ".job-offer-link",
    "article a",
]

# Linhas de ruído comuns em todas as páginas ADEM
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


def _limpar_texto(linhas: list[str]) -> list[str]:
    """Remove linhas de menu, cookies e rodapé. Mantém o conteúdo da oferta."""
    limpas = []
    for linha in linhas:
        if any(ruido in linha for ruido in _RUIDO_MARCADORES):
            continue
        limpas.append(linha)
    return limpas


async def _coletar_links(page) -> list[str]:
    for seletor in LINK_SELECTORS:
        try:
            await page.wait_for_selector(seletor, timeout=5000)
            elementos = await page.query_selector_all(seletor)
            if elementos:
                urls = []
                for el in elementos:
                    href = await el.get_attribute("href")
                    if href:
                        urls.append(urljoin("https://adem.public.lu", href))
                unicas = list(dict.fromkeys(urls))
                auditor.info("extrator", f"Seletor '{seletor}' coletou {len(unicas)} URLs.")
                return unicas
        except PlaywrightTimeoutError:
            continue
    return []


async def extrair_ofertas() -> list[dict] | None:
    ofertas: list[dict] = []
    browser = None

    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=False)
            except PlaywrightError as e:
                auditor.fatal("extrator", f"Falha ao abrir navegador: {e}")
                return None

            page = await browser.new_page()
            page.set_default_timeout(45000)

            auditor.info("extrator", f"Acessando: {BASE_URL}")
            try:
                response = await page.goto(BASE_URL, timeout=60000)
                if response and response.status >= 400:
                    auditor.fatal(
                        "extrator",
                        f"Página inicial retornou HTTP {response.status}.",
                    )
                    return None
                await page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                auditor.warning("extrator", "Rede não ficou ociosa a tempo. Continuando.")
            except PlaywrightError as e:
                auditor.fatal("extrator", f"Falha ao carregar página inicial: {e}")
                return None

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

                    # Título real via page.title() (sem ruído)
                    titulo = (await page.title()).strip() or "Sem título"

                    bruto = await page.inner_text("body")
                    linhas = [l.strip() for l in bruto.split("\n") if l.strip()]
                    linhas_limpas = _limpar_texto(linhas)

                    # Sanity check: se ficou vazio, usa o bruto (Fall Gracefully)
                    texto_final = (
                        "\n".join(linhas_limpas)
                        if linhas_limpas
                        else "\n".join(linhas)
                    )

                    ofertas.append({
                        "url": url,
                        "titulo": titulo,
                        "texto": texto_final,
                    })

                except PlaywrightTimeoutError:
                    auditor.error("extrator", f"Timeout em {url}. Pulando.")
                except PlaywrightError as e:
                    auditor.error("extrator", f"Erro Playwright em {url}: {e}. Pulando.")

    except Exception as e:  # noqa: BLE001 - catch-all final do pipeline
        auditor.fatal("extrator", f"Erro catastrófico: {e}")
        return None
    finally:
        # Garante fechamento mesmo em erro (evita processo zumbi)
        if browser is not None:
            try:
                await browser.close()
            except PlaywrightError as e:
                auditor.warning("extrator", f"Falha ao fechar navegador: {e}")

    return ofertas