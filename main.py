import asyncio
from extrator_adem import extrair_ofertas
from tradutor_texto import traduzir
from gerenciador_arquivo import salvar_ofertas
import auditor

MAX_TENTATIVAS_RETRY = 3
ESPERA_ENTRE_RETRIES = (30, 60, 120)
PAUSA_ENTRE_TRADUCOES = 1


async def _traduzir_com_buffer(ofertas: list[dict]) -> list[dict]:
    lista_final: list[dict] = []
    buffer_retry: list[dict] = []
    descartadas_por_tamanho = 0

    auditor.info("main", f"Tradução primária de {len(ofertas)} ofertas...")
    for i, oferta in enumerate(ofertas, start=1):
        auditor.info("main", f"  Traduzindo [{i}/{len(ofertas)}]")
        # CORREÇÃO: traduzir() agora é async, precisa de await
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
            # CORREÇÃO: traduzir() agora é async, precisa de await
            sucesso, texto, retentavel = await traduzir(oferta["texto"])
            if sucesso:
                oferta["traduzido"] = True
                oferta["texto_traduzido"] = texto
                lista_final.append(oferta)
            elif retentavel:
                novos_falhos.append(oferta)
            else:
                # Falha caracterizada durante retry → descarta do buffer
                lista_final.append(oferta)
                descartadas_por_tamanho += 1
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