from googletrans import Translator
import auditor

# O tradutor agora é gerenciado dentro de um contexto assíncrono.
# Não instanciamos globalmente para evitar problemas de sessão.
_primeira_traducao_global = True

LIMITE_CARACTERES = 4000


def _detectar_rate_limit(erro: str) -> bool:
    marcadores = ("429", "too many requests", "quota", "503", "server error")
    return any(m in erro for m in marcadores)


async def traduzir(texto: str) -> tuple[bool, str, bool]:
    """
    Retorna (sucesso, texto_resultado, retentavel).
    """
    global _primeira_traducao_global

    # Early Return: texto vazio
    if not texto or not texto.strip():
        return True, "", False

    # Fail First: estouro de caracteres
    if len(texto) > LIMITE_CARACTERES:
        auditor.estouro_caracteres(
            "tradutor",
            f"Texto com {len(texto)} caracteres excede o limite de {LIMITE_CARACTERES}. "
            f"Tradução abortada por política de MVP.",
        )
        return False, texto, False

    try:
        # A correção principal: usar 'async with' e 'await'
        async with Translator() as translator:
            resultado = await translator.translate(texto, dest="pt")
            _primeira_traducao_global = False

            if resultado and resultado.text:
                return True, resultado.text, False
            else:
                auditor.warning("tradutor", "Tradução retornou vazia. Mantendo original.")
                return False, texto, True

    except Exception as e:
        msg_erro = str(e).lower()

        if _detectar_rate_limit(msg_erro):
            if _primeira_traducao_global:
                auditor.critical("tradutor", f"Bloqueio na 1ª tradução da sessão: {e}")
            else:
                auditor.error("tradutor", f"Rate limit detectado: {e}")
            return False, texto, True

        auditor.error("tradutor", f"Falha na tradução: {e}")
        return False, texto, True