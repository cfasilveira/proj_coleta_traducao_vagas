import os
import aiofiles
from datetime import datetime
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

    # Performance: monta o conteúdo inteiro em memória e escreve uma vez
    conteudo = _renderizar_cabecalho(ofertas) + "".join(
        _renderizar_oferta(i, len(ofertas), o) for i, o in enumerate(ofertas, start=1)
    )

    # Escrita atômica: grava em .tmp e renomeia
    tmp_path = ARQUIVO_SAIDA + ".tmp"
    try:
        async with aiofiles.open(tmp_path, "w", encoding="utf-8", errors="replace") as f:
            await f.write(conteudo)
        os.replace(tmp_path, ARQUIVO_SAIDA)
        auditor.info("arquivo", f"Arquivo salvo: '{ARQUIVO_SAIDA}' ({len(conteudo)} bytes).")
        return True

    except PermissionError as e:
        auditor.fatal("arquivo", f"Sem permissão de escrita: {e}")
        return False
    except OSError as e:
        auditor.error("arquivo", f"Falha de I/O: {e}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False