"""Offline HTML projection of the ledger. It does not fetch anything."""

from __future__ import annotations

import html

from raee_reverse.store import Store


def render_html(store: Store) -> str:
    summary = store.status_summary()
    rows = []
    for claim in summary["claims"]:
        cells = "".join(
            f"<li><code>{html.escape(key)}</code>: {html.escape(str(claim[key]))}</li>"
            for key in (
                "id",
                "accepted_pass",
                "execution_result",
                "applicability",
                "support_status",
                "independent_support_count",
                "provenance",
                "usage",
            )
        )
        rows.append(
            "<section><h2>"
            + html.escape(str(claim.get("statement") or claim["id"]))
            + "</h2><ul>"
            + cells
            + "</ul></section>"
        )
    body = "\n".join(rows) or "<p>No claims are recorded.</p>"
    return (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset=\"utf-8\"><title>RAEE Reverse Lite report</title></head><body>\n"
        "<h1>RAEE Reverse Lite report</h1>\n"
        "<p>This file is a projection of one ledger. accepted_pass is limited to the recorded scope. "
        "It is not a universal pass. No network resource is required to read this file.</p>\n"
        f"<p>{html.escape(summary['note'])}</p>\n"
        f"{body}\n"
        "</body></html>\n"
    )
