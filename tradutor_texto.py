"""Tradução de ofertas do ADEM (português).

Delegado a ``proj_biblioteca.traducao.traduzir``, com o provedor ``Translator``
do ``googletrans`` injetado via fábrica. Mantém o contrato assíncrono:
``traduzir(texto) -> (sucesso, texto_resultado, retentavel)``.

Política preservada (fail-first / graceful fall):
- texto vazio -> (True, "", False)
- acima de LIMITE_CARACTERES -> (False, original, False)  [não retentável]
- rate limit / falha transitória -> (False, original, True) [retentável]
"""

from __future__ import annotations

from proj_biblioteca import traducao

LIMITE_CARACTERES = traducao.LIMITE_CARACTERES


async def traduzir(texto: str) -> tuple[bool, str, bool]:
    """Traduz `texto` para o português.

    Injetamos o ``Translator`` do ``googletrans`` como fábrica para evitar
    instanciar globalmente (problemas de sessão) e para não importar
    ``googletrans`` a menos que o módulo seja usado.
    """
    return await traducao.traduzir(
        texto,
        fabrica=lambda: _translator(),
        destino="pt",
        limite=LIMITE_CARACTERES,
    )


def _translator():
    from googletrans import Translator

    return Translator()
