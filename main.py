"""Entry point do pipeline ADEM (Luxemburgo).

Orquestra extração, tradução (com retry) e gravação de ofertas. Nunca termina
com traceback bruto.
"""

from __future__ import annotations

import asyncio

from proj_biblioteca import retry

from extrator_adem import extrair_ofertas
from tradutor_texto import traduzir
from gerenciador_arquivo import salvar_ofertas
import auditor

MAX_TENTATIVAS_RETRY = 3
ESPERA_ENTRE_RETRIES = (30, 60, 120)
PAUSA_ENTRE_TRADUCOES = 1


async def _traduzir_una(oferta: dict) -> None:
    """Traduz uma oferta, atualizando-a in-place.

    Levanta quando a tradução falhou mas é retentável, para que
    ``retry.repetir_async`` possa retentar. Falhas caracterizadas (não
    retentáveis) não levantam.
    """
    sucesso, texto, retentavel = await traduzir(oferta["texto"])
    oferta["traduzido"] = sucesso
    oferta["texto_traduzido"] = texto if sucesso else ""
    if not sucesso and retentavel:
        raise RuntimeError(f"Tradução falhou (retentável) para {oferta.get('url', '?')}")


async def _traduzir_com_buffer(ofertas: list[dict]) -> list[dict]:
    lista_final: list[dict] = []
    buffer_retry: list[dict] = []
    descartadas_por_tamanho = 0

    auditor.info("main", f"Tradução primária de {len(ofertas)} ofertas...")
    for i, oferta in enumerate(ofertas, start=1):
        auditor.info("main", f"  Traduzindo [{i}/{len(ofertas)}]")
        sucesso, texto, retentavel = await traduzir(oferta["texto"])
        oferta["traduzido"] = sucesso
        oferta["texto_traduzido"] = texto if sucesso else ""

        if sucesso:
            lista_final.append(oferta)
        elif retentavel:
            buffer_retry.append(oferta)
        else:
            # Falha caracterizada (ex: estouro de caracteres) → não retenta
            lista_final.append(oferta)
            descartadas_por_tamanho += 1

        await asyncio.sleep(PAUSA_ENTRE_TRADUCOES)

    auditor.info(
        "main",
        f"Primária: {len(lista_final)} ok, {len(buffer_retry)} no buffer, "
        f"{descartadas_por_tamanho} descartada(s) por tamanho.",
    )

    for tentativa, espera in enumerate(ESPERA_ENTRE_RETRIES, start=1):
        if not buffer_retry:
            break
        auditor.warning(
            "main",
            f"Retry {tentativa}/{MAX_TENTATIVAS_RETRY}: {len(buffer_retry)} pendente(s). "
            f"Aguardando {espera}s...",
        )
        await asyncio.sleep(espera)

        novos_falhos: list[dict] = []
        for oferta in buffer_retry:
            try:
                # repetir_async tenta até MAX_TENTATIVAS_RETRY com esperas entre elas.
                await retry.repetir_async(
                    lambda o=oferta: _traduzir_una(o),
                    tentativas=MAX_TENTATIVAS_RETRY,
                    esperas=ESPERA_ENTRE_RETRIES,
                )
                lista_final.append(oferta)
            except Exception as erro:  # noqa: BLE001 - ainda falhou após todas as tentativas
                auditor.error("main", f"Oferta ainda falhou após retry: {erro}")
                oferta["traduzido"] = False
                oferta["texto_traduzido"] = ""
                novos_falhos.append(oferta)
        buffer_retry = novos_falhos

    for oferta in buffer_retry:
        oferta["traduzido"] = False
        oferta["texto_traduzido"] = ""
        lista_final.append(oferta)

    if buffer_retry:
        auditor.error(
            "main",
            f"{len(buffer_retry)} oferta(s) não traduzida(s) após {MAX_TENTATIVAS_RETRY} tentativas.",
        )
    if descartadas_por_tamanho:
        auditor.estouro_caracteres(
            "main",
            f"{descartadas_por_tamanho} oferta(s) descartada(s) da tradução por excesso de tamanho.",
        )

    return lista_final


async def main() -> None:
    auditor.info("main", "=" * 60)
    auditor.info("main", "INICIANDO PIPELINE")
    auditor.info("main", "=" * 60)

    ofertas = await extrair_ofertas()

    if ofertas is None:
        auditor.fatal("main", "Extração falhou criticamente. Abortando.")
        return

    if not ofertas:
        auditor.warning("main", "Nenhuma oferta extraída. Encerrando.")
        return

    auditor.info("main", f"Extração: {len(ofertas)} oferta(s).")

    lista_final = await _traduzir_com_buffer(ofertas)

    if len(lista_final) != len(ofertas):
        auditor.error(
            "main",
            f"Discrepância: extraídas={len(ofertas)}, consolidadas={len(lista_final)}.",
        )

    if not await salvar_ofertas(lista_final):
        auditor.fatal("main", "Falha ao salvar arquivo final.")
        return

    traduzidas = sum(1 for o in lista_final if o.get("traduzido", False))
    auditor.info("main", "=" * 60)
    auditor.info(
        "main",
        f"CONCLUÍDO | total={len(lista_final)} | "
        f"traduzidas={traduzidas} | falhas={len(lista_final) - traduzidas}",
    )
    auditor.info("main", "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
