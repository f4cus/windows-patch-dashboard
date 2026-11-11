"""Reviewed Microsoft lifecycle facts, independent of KB discovery and known issues."""

from __future__ import annotations

from datetime import date
from typing import Any

from windows_patch_collector.models import OsIdentity
from windows_patch_collector.products import WINDOWS_SERVER_2012, WINDOWS_SERVER_2012_R2

ESU_ENDED_ON = date(2026, 10, 13)
ESU_EXPLANATION = (
    "Microsoft finalizó el programa de Actualizaciones de Seguridad Extendidas (ESU) "
    "el 13/10/2026. Se recomienda migrar a una versión compatible de Windows Server."
)
# Actual retrieval instants from the official pages reviewed on 2026-11-10.
_OVERVIEW = {
    "type": "lifecycle",
    "url": "https://learn.microsoft.com/es-es/windows-server/get-started/"
    "extended-security-updates-overview",
    "retrievedAt": "2026-11-10T20:45:35.203781Z",
}
_PRODUCT_SOURCES = {
    WINDOWS_SERVER_2012: {
        "type": "lifecycle",
        "url": "https://support.microsoft.com/es-es/servicing/os/server-2012/2026/10/"
        "kb5126835-windows-server-2012-mr",
        "retrievedAt": "2026-11-10T20:45:37.516553Z",
    },
    WINDOWS_SERVER_2012_R2: {
        "type": "lifecycle",
        "url": "https://support.microsoft.com/es-es/servicing/os/windows-8-1/2026/10/"
        "kb5126836-windows-8-1-mr",
        "retrievedAt": "2026-11-10T20:45:40.181229Z",
    },
}


def esu_ended(identity: OsIdentity, month: str) -> bool:
    """Ordinary ESU ends after October; exceptional official updates remain eligible."""

    return identity in _PRODUCT_SOURCES and month > ESU_ENDED_ON.strftime("%Y-%m")


def ended_product_history_pages(month: str) -> tuple[tuple[OsIdentity, str], ...]:
    """Official reviewed product-history pages may document exceptional later updates."""
    return tuple(
        (identity, source["url"])
        for identity, source in _PRODUCT_SOURCES.items()
        if esu_ended(identity, month)
    )


def attach_lifecycle(row: dict[str, Any], identity: OsIdentity, month: str) -> None:
    """Annotate lifecycle without changing a published KB or inferring its existence."""

    if not esu_ended(identity, month):
        return
    row["lifecycle"] = {"status": "esu-ended", "endedOn": ESU_ENDED_ON.isoformat()}
    row["sources"] += [dict(_OVERVIEW), dict(_PRODUCT_SOURCES[identity])]
    if row["kb"] == "NO PUBLICADO":
        row.update(
            updateType="unknown",
            changesSummary=ESU_EXPLANATION,
            resolvedIssuesSummary="No disponible: no hay una actualización que evaluar.",
            knownIssuesSummary="No disponible: no hay una actualización que evaluar.",
            knownIssuesStatus="unknown",
        )
