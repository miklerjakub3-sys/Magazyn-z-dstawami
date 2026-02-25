#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moduł eksportu danych do PDF."""

import os
from datetime import datetime

from .config import ITEM_TYPE_TO_LABEL as TYPE_TO_LABEL

PDF_AVAILABLE = True
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import Image as RLImage
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except Exception:
    PDF_AVAILABLE = False

from .database import get_first_delivery_image

_FONT_NAME = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_FONT_READY = False


def setup_polish_fonts():
    """Konfiguracja czcionki z polskimi znakami dla PDF."""
    global _FONT_NAME, _FONT_BOLD, _FONT_READY
    if not PDF_AVAILABLE:
        return False
    if _FONT_READY:
        return True

    try:
        font_paths = [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\times.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
        ]
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont("PolishFont", font_path))
                    _FONT_NAME = "PolishFont"
                    _FONT_BOLD = "PolishFont"
                    _FONT_READY = True
                    return True
                except Exception:
                    continue
    except Exception:
        from .log import get_logger

        get_logger("magazyn.pdf").exception("Nie udało się załadować polskiej czcionki")

    _FONT_READY = True
    return False


def _date_label(value: str, fallback: str) -> str:
    return value if value else fallback


def _build_styles():
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = _FONT_NAME
    styles["Title"].fontName = _FONT_BOLD
    styles.add(
        ParagraphStyle(
            name="Info",
            parent=styles["Normal"],
            fontName=_FONT_NAME,
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#374151"),
        )
    )
    return styles


def _on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont(_FONT_NAME, 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 10, f"Strona {doc.page}")
    canvas.restoreState()


def export_devices_to_pdf(filename, rows, date_from, date_to, type_label):
    """Eksport urządzeń do PDF."""
    if not PDF_AVAILABLE:
        raise Exception("Brak biblioteki reportlab")

    setup_polish_fonts()
    styles = _build_styles()
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
        author="Jakub",
        title="Raport magazynowy – Przyjęcia",
    )

    story = [
        Paragraph("Raport magazynowy – Przyjęcia", styles["Title"]),
        Spacer(1, 6),
        Paragraph(
            f"Zakres dat: {_date_label(date_from, 'brak')} — {_date_label(date_to, 'brak')} | "
            f"Filtr typu: {type_label or 'Wszystkie'} | Rekordy: {len(rows)}",
            styles["Info"],
        ),
        Paragraph(f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Info"]),
        Spacer(1, 10),
    ]

    header = ["ID", "Data", "Typ", "Nazwa", "SN/Kod", "IMEI1", "IMEI2", "Kod produktu", "Dostawa"]
    data = [header]
    for r in rows:
        item_type_label = TYPE_TO_LABEL.get(r[2], r[2])
        delivery_label = str(r[10]) if (len(r) > 10 and r[10] is not None) else "—"
        data.append([
            str(r[0]),
            r[1] or "",
            item_type_label,
            r[3] or "",
            r[4] or "",
            r[5] or "",
            r[6] or "",
            r[7] or "",
            delivery_label,
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9ca3af")),
                ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), _FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
            ]
        )
    )
    story.append(table)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)


def export_deliveries_to_pdf(filename, rows, date_from, date_to, type_label):
    """Eksport dostaw do PDF."""
    if not PDF_AVAILABLE:
        raise Exception("Brak biblioteki reportlab")

    setup_polish_fonts()
    styles = _build_styles()
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
        author="Jakub",
        title="Raport magazynowy – Dostawy",
    )

    story = [
        Paragraph("Raport magazynowy – Dostawy", styles["Title"]),
        Spacer(1, 6),
        Paragraph(
            f"Zakres dat: {_date_label(date_from, 'brak')} — {_date_label(date_to, 'brak')} | "
            f"Typ dostawy: {type_label or 'Wszystkie'} | Rekordy: {len(rows)}",
            styles["Info"],
        ),
        Paragraph(f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Info"]),
        Spacer(1, 10),
    ]

    header = ["ID", "Data", "Zdjęcie", "Nadawca", "Kurier", "Typ", "Nr przesyłki", "VAT"]
    data = [header]
    for r in rows:
        img_path = get_first_delivery_image(int(r[0]))
        img_cell = ""
        if img_path and os.path.isfile(img_path):
            try:
                img_cell = RLImage(img_path, width=48, height=36)
            except Exception:
                img_cell = ""

        data.append([
            str(r[0]),
            r[1] or "",
            img_cell,
            r[2] or "",
            r[3] or "",
            r[4] or "",
            r[5] or "",
            "TAK" if int(r[6] or 0) == 1 else "NIE",
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9ca3af")),
                ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), _FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
            ]
        )
    )

    story.append(table)
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
