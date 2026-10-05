"""QR codes dos links de pedido de cada sala.

Gerados no servidor, em SVG, pelo segno — biblioteca em Python puro, sem
dependência nativa nem serviço externo: funciona offline e não pede nenhuma
origem nova na Content-Security-Policy.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import segno
from markupsafe import Markup

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}


def qr_svg(url: str) -> Markup:
    """SVG inline do QR code; as cores vêm do CSS (``.qr-code-line``)."""

    code = segno.make(url, error="m")
    svg = code.svg_inline(
        scale=4,
        border=2,
        svgclass="qr-code",
        lineclass="qr-code-line",
        omitsize=True,
    )
    return Markup(svg)


def is_loopback(base_url: str) -> bool:
    """Endereço que só a própria máquina abre: inútil num QR code."""

    host = urlsplit(base_url).hostname or ""
    return host in LOOPBACK_HOSTS or host.startswith("127.")
