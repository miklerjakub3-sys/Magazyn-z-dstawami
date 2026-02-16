#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Moduł eksportu danych do PDF
"""

import os
from datetime import datetime
from .config import ITEM_TYPE_TO_LABEL as TYPE_TO_LABEL

# Opcjonalna biblioteka PDF
PDF_AVAILABLE = True
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.platypus import Image as RLImage
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except Exception:
    PDF_AVAILABLE = False

# Import funkcji z database
from .database import get_first_delivery_image


def setup_polish_fonts():
    """Konfiguracja polskich czcionek dla PDF"""
    if not PDF_AVAILABLE:
        return
    
    try:
        # Próba rejestracji popularnych czcionek systemowych z polskimi znakami
        font_paths = [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\times.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('PolishFont', font_path))
                    return True
                except Exception:
                    continue
    except Exception as e:
        from .log import get_logger
        get_logger("magazyn.pdf").exception("Nie udało się załadować polskiej czcionki")
    
    return False


def export_devices_to_pdf(filename, rows, date_from, date_to, type_label):
    """Eksport urządzeń do PDF"""
    if not PDF_AVAILABLE:
        raise Exception("Brak biblioteki reportlab")
    
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        filename, 
        pagesize=landscape(A4), 
        leftMargin=18, 
        rightMargin=18, 
        topMargin=18, 
        bottomMargin=18
    )

    story = []
    story.append(Paragraph("Raport magazynowy – Przyjęcia", styles["Title"]))
    story.append(Paragraph(f"Zakres dat: {date_from} — {date_to}", styles["Normal"]))
    story.append(Paragraph(f"Filtr typu: {type_label}", styles["Normal"]))
    story.append(Paragraph(f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    story.append(Paragraph(f"Liczba rekordów: {len(rows)}", styles["Normal"]))
    story.append(Spacer(1, 10))

    # Podział na strony (max 30 rekordów na stronę)
    page_size = 30
    for page_num, i in enumerate(range(0, len(rows), page_size), 1):
        page_rows = rows[i:i + page_size]
        
        if page_num > 1:
            story.append(PageBreak())
        
        header = ["ID", "Data", "Typ", "Nazwa", "SN/Kod", "IMEI1", "IMEI2", "Kod prod.", "Dostawa"]
        data = [header]
        
        for r in page_rows:
            item_type_label = TYPE_TO_LABEL.get(r[2], r[2])
            delivery_label = str(r[10]) if (len(r) > 10 and r[10] is not None) else "—"
            data.append([
                str(r[0]), r[1] or "", item_type_label, r[3] or "", r[4] or "", 
                r[5] or "", r[6] or "", r[7] or "", delivery_label
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ]))
        story.append(table)
        
        # Info o stronie
        if len(rows) > page_size:
            story.append(Spacer(1, 5))
            story.append(Paragraph(
                f"Strona {page_num} z {(len(rows) + page_size - 1) // page_size}", 
                styles["Normal"]
            ))
    
    doc.build(story)


def export_deliveries_to_pdf(filename, rows, date_from, date_to, type_label):
    """Eksport dostaw do PDF"""
    if not PDF_AVAILABLE:
        raise Exception("Brak biblioteki reportlab")
    
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(A4),
        leftMargin=18,
        rightMargin=18,
        topMargin=18,
        bottomMargin=18
    )

    story = []
    story.append(Paragraph("Raport – Dostawy", styles["Title"]))
    story.append(Paragraph(f"Zakres dat: {date_from} — {date_to}", styles["Normal"]))
    story.append(Paragraph(f"Typ dostawy: {type_label or 'Wszystkie'}", styles["Normal"]))
    story.append(Paragraph(f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    story.append(Paragraph(f"Liczba rekordów: {len(rows)}", styles["Normal"]))
    story.append(Spacer(1, 10))

    # Podział na strony
    page_size = 20
    for page_num, i in enumerate(range(0, len(rows), page_size), 1):
        page_rows = rows[i:i + page_size]
        
        if page_num > 1:
            story.append(PageBreak())
        
        header = ["ID", "Data", "Zdjęcie", "Nadawca", "Kurier", "Typ", "Nr", "VAT"]
        data = [header]

        for r in page_rows:
            img_path = get_first_delivery_image(int(r[0]))
            img_cell = ""
            if img_path and os.path.isfile(img_path):
                try:
                    img_cell = RLImage(img_path, width=50, height=38)
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
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ]))

        story.append(table)
        
        if len(rows) > page_size:
            story.append(Spacer(1, 5))
            story.append(Paragraph(
                f"Strona {page_num} z {(len(rows) + page_size - 1) // page_size}", 
                styles["Normal"]
            ))

    doc.build(story)
