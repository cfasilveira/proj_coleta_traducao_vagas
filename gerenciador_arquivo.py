"""Gerenciador de arquivo de saída do ADEM.

Renderiza o relatório de ofertas (específico do ADEM) e grava de forma atômica
via ``proj_biblioteca.persistencia.escrever_atomico`` (tempfile + fsync +
os.replace — nunca deixa arquivo pela metade), executado em thread para não
bloquear o loop asyncio.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from proj_biblioteca import persistencia

import auditor

ARQUIVO_SAIDA = "ofertas_Luxemburgo.txt"


def _renderizar_cabecalho(ofertas: list[dict]) -> str:
    traduzidas = sum(1 for o in ofertas if o.get("traduzido", False))
    nao_traduzidas = len(ofertas) - traduzidas
    linhas = [
        "=" * 80,
        "RELATÓRIO DE OFERTAS DE EMPREGO - ADEM LUXEMBURGO",
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Total de ofertas: {len(ofertas)}",
        f"Traduzidas: {traduzidas} | Não traduzidas: {nao_traduzidas}",
        "=" * 80,
        "",
    ]
    return "\n".join(linhas)


def _renderizar_oferta(idx: int, total: int, oferta: dict) -> str:
    partes = [
        "\n" + "#" * 80,
        f"OFERTA {idx} de {total}",
        f"URL: {oferta.get('url', 'N/A')}",
        "#" * 80,
        "",
    ]
    if oferta.get("traduzido", False):
        partes.append(oferta.get("texto_traduzido", ""))
    else:
        titulo = oferta.get("titulo", "Título não disponível")
        partes.append(f"[NÃO TRADUZIDO] {titulo}")
        partes.append("(Corpo do texto omitido conforme configuração.)")
    partes.append("\n")
    return "\n".join(partes)


async def salvar_ofertas(ofertas: list[dict]) -> bool:
    # Early Return
    if not ofertas:
        auditor.warning("arquivo", "Nenhuma oferta recebida. Arquivo não será criado.")
        return True

    auditor.info("arquivo", f"Gravando {len(ofertas)} ofertas em '{ARQUIVO_SAIDA}'...")

    # Performance: monta o conteúdo inteiro em memória e escreve uma vez.
    conteudo = _renderizar_cabecalho(ofertas) + "".join(
        _renderizar_oferta(i, len(ofertas), o) for i, o in enumerate(ofertas, start=1)
    )

    # Escrita atômica (tempfile + fsync + os.replace) via thread, sem bloquear o loop.
    try:
        await asyncio.to_thread(persistencia.escrever_atomico, ARQUIVO_SAIDA, conteudo)
        auditor.info(
            "arquivo", f"Arquivo salvo: '{ARQUIVO_SAIDA}' ({len(conteudo)} bytes)."
        )
        return True
    except PermissionError as e:
        auditor.fatal("arquivo", f"Sem permissão de escrita: {e}")
        return False
    except OSError as e:
        auditor.error("arquivo", f"Falha de I/O: {e}")
        try:
            if os.path.exists(ARQUIVO_SAIDA + ".tmp"):
                os.remove(ARQUIVO_SAIDA + ".tmp")
        except OSError:
            pass
        return False
