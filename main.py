import asyncio
from urllib.parse import urljoin

import aiofiles
from deep_translator import GoogleTranslator
from playwright.async_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

BASE_URL = "https://adem.public.lu/en/jobboard.html#q=data+analyst&mode=any"
OUTPUT_FILE = "ofertas_Luxemburgo.txt"
DEBUG_HTML = "debug_page.html"

LINK_SELECTORS = [
    "a[href*='/job-offer/']",
    "a[href*='/offre-emploi/']",
    "a[href*='job']",
    ".job-offer-link",
    "article a",  # Seletor genérico para artigos com links
]


async def coletar_links(page) -> list[str]:
    print("\n--- INICIANDO COLETA DE LINKS ---")
    for seletor in LINK_SELECTORS:
        print(f"Tentando seletor: {seletor} ...")
        try:
            await page.wait_for_selector(seletor, timeout=5000)
            elementos = await page.query_selector_all(seletor)
            print(f"  -> Encontrados {len(elementos)} elementos com este seletor.")
            if elementos:
                urls = []
                for el in elementos:
                    href = await el.get_attribute("href")
                    if href:
                        urls.append(urljoin("https://adem.public.lu", href))
                unique_urls = list(dict.fromkeys(urls))
                print(f"  -> Total de {len(unique_urls)} URLs únicas coletadas.")
                return unique_urls
        except PlaywrightTimeoutError:
            print(f"  -> Seletor '{seletor}' não encontrado (timeout).")
            continue
    print("--- NENHUM LINK ENCONTRADO COM OS SELETORES ATUAIS ---")
    return []


async def main():
    print("Iniciando script...")
    async with async_playwright() as p:
        print("Abrindo navegador Chromium...")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Acessando a página de busca: {BASE_URL}")
        try:
            await page.goto(BASE_URL, timeout=60000)
            print("Página carregada. Aguardando rede ficar ociosa...")
            await page.wait_for_load_state("networkidle", timeout=30000)
            print("Rede ociosa.")
        except PlaywrightTimeoutError:
            print("Aviso: A página demorou a ficar ociosa. Continuando...")
        except PlaywrightError as e:
            print(f"Erro ao carregar a página inicial: {e}")
            await browser.close()
            return

        # Salva o HTML da página de busca para depuração
        print(f"Salvando HTML da página de busca em '{DEBUG_HTML}'...")
        async with aiofiles.open(DEBUG_HTML, "w", encoding="utf-8") as f:
            await f.write(await page.content())
        print("HTML salvo.")

        # Coleta os links
        urls = await coletar_links(page)

        if not urls:
            print("\nNenhuma oferta encontrada. O arquivo 'debug_page.html' foi gerado.")
            print("Abra-o no VS Code e procure por um link de oferta para ajustar os seletores.")
            await browser.close()
            return

        print(f"\nTotal de {len(urls)} ofertas encontradas. Iniciando extração...")
        translator = GoogleTranslator(source="auto", target="pt")

        print(f"Criando arquivo de saída: {OUTPUT_FILE}")
        async with aiofiles.open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            for i, url in enumerate(urls, start=1):
                print(f"\n[{i}/{len(urls)}] Processando: {url}")
                try:
                    await page.goto(url, timeout=60000)
                    await page.wait_for_load_state("domcontentloaded", timeout=30000)
                    print("  -> Página da oferta carregada. Extraindo texto...")

                    texto_original = await page.inner_text("body")
                    linhas = [linha.strip() for linha in texto_original.split("\n") if linha.strip()]
                    texto_limpo = "\n".join(linhas)
                    print(f"  -> Texto extraído ({len(texto_limpo)} caracteres). Traduzindo...")

                    try:
                        texto_traduzido = translator.translate(texto_limpo)
                        print("  -> Tradução concluída.")
                    except Exception as e_trans:  # noqa: BLE001
                        print(f"  -> Erro na tradução: {e_trans}. Salvando original.")
                        texto_traduzido = "[ERRO NA TRADUÇÃO - TEXTO ORIGINAL]\n" + texto_limpo

                    separador = "=" * 80 + "\n"
                    await f.write(separador)
                    await f.write(f"URL: {url}\n")
                    await f.write(separador)
                    await f.write(texto_traduzido)
                    await f.write("\n\n\n")
                    print("  -> Dados gravados no arquivo.")

                    await asyncio.sleep(2)

                except PlaywrightTimeoutError:
                    print(f"  -> Timeout ao processar {url}")
                    await f.write(f"ERRO: Timeout ao acessar {url}\n\n")
                except PlaywrightError as e:
                    print(f"  -> Erro do Playwright em {url}: {e}")
                    await f.write(f"ERRO: {e} em {url}\n\n")

        print(f"\nProcessamento concluído! Dados salvos em '{OUTPUT_FILE}'")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())