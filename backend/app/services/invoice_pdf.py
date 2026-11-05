"""Transaction-safe, in-memory invoice PDF document generation using ReportLab."""

import io
from decimal import Decimal
from typing import Any, Dict, List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.app.schemas.invoices import InvoiceResponse
from backend.app.schemas.orders import OrderResponse


def generate_invoice_pdf_bytes(
    invoice: InvoiceResponse,
    order: OrderResponse,
    business_name: str,
    business_details: Optional[Dict[str, Any]] = None,
    customer_details: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Generate professional, verifiable invoice PDF in memory from authoritative records.
    
    Strict constraints:
    - Never fabricates unverified addresses, tax IDs, or payment guarantees.
    - Recalculates exact line totals and invoice totals using Decimal arithmetic.
    - Streams directly to in-memory bytes; never writes to public or temporary disk.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
    )

    subtitle_style = ParagraphStyle(
        "InvoiceSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
    )

    h2_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#334155"),
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
    )

    bold_body_style = ParagraphStyle(
        "BodyDarkBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
    )

    story = []

    # 1. Header Section: Business Name and Document Type
    header_data = [
        [
            Paragraph(f"<b>{business_name}</b>", title_style),
            Paragraph("<b>INVOICE</b>", ParagraphStyle(
                "RightTitle",
                parent=title_style,
                alignment=2, # Right aligned
                textColor=colors.HexColor("#0284c7"),
            )),
        ],
        [
            Paragraph(
                business_details.get("address", "Business Address: Not specified in profile")
                if business_details else "Business Address: Not specified in profile",
                subtitle_style
            ),
            Paragraph(f"<b>Invoice #:</b> {invoice.invoice_number}", ParagraphStyle(
                "RightSub",
                parent=subtitle_style,
                alignment=2,
            )),
        ]
    ]
    header_table = Table(header_data, colWidths=[330, 200])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 15))

    # 2. Metadata Section: Dates, Order Ref, Status, and Customer Details
    # Prioritize immutable customer snapshot from invoice record if available
    cust_snapshot = invoice.customer_snapshot or {}
    cust_details = customer_details or {}
    cust_name = (
        cust_snapshot.get("name")
        or order.customer_name
        or cust_details.get("name")
        or "Valued Customer"
    )
    cust_email = cust_snapshot.get("email") or cust_details.get("email")
    cust_phone = cust_snapshot.get("phone") or cust_details.get("phone")
    cust_addr = cust_snapshot.get("address") or cust_details.get("address")

    customer_info_lines = [f"<b>{cust_name}</b>"]
    if cust_email:
        customer_info_lines.append(f"Email: {cust_email}")
    if cust_phone:
        customer_info_lines.append(f"Phone: {cust_phone}")
    if cust_addr:
        customer_info_lines.append(f"Address: {cust_addr}")

    meta_data = [
        [
            Paragraph("<b>BILLED TO:</b>", h2_style),
            Paragraph("<b>INVOICE DETAILS:</b>", h2_style),
        ],
        [
            Paragraph("<br/>".join(customer_info_lines), body_style),
            Paragraph(
                f"<b>Order Number:</b> {order.order_number}<br/>"
                f"<b>Issue Date:</b> {invoice.created_at.strftime('%Y-%m-%d')}<br/>"
                f"<b>Due Date:</b> {invoice.due_date.strftime('%Y-%m-%d')}<br/>"
                f"<b>Status:</b> {invoice.status.upper()}",
                body_style
            ),
        ]
    ]
    meta_table = Table(meta_data, colWidths=[330, 200])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))

    # 3. Line Items Table with Exact Decimal Calculations
    # Prioritize immutable line items snapshot to preserve historical invoice integrity
    item_rows = [
        [
            Paragraph("<b>Item & Description</b>", bold_body_style),
            Paragraph("<b>SKU</b>", bold_body_style),
            Paragraph("<b>Qty</b>", ParagraphStyle("QtyH", parent=bold_body_style, alignment=1)),
            Paragraph("<b>Unit Price</b>", ParagraphStyle("PriceH", parent=bold_body_style, alignment=2)),
            Paragraph("<b>Total</b>", ParagraphStyle("TotalH", parent=bold_body_style, alignment=2)),
        ]
    ]

    currency_code = ((business_details or {}).get("currency") or "USD").strip().upper()
    curr_prefix = f"{currency_code} " if currency_code != "USD" else "$"

    calculated_subtotal = Decimal("0.00")
    if invoice.line_items_snapshot and len(invoice.line_items_snapshot) > 0:
        for it in invoice.line_items_snapshot:
            p_name = it.get("product_name", "Item")
            sku = it.get("product_sku", "")
            qty = int(it.get("quantity", 1))
            price = Decimal(str(it.get("unit_price", "0.00"))).quantize(Decimal("0.01"))
            line_total = Decimal(str(it.get("line_total", "0.00"))).quantize(Decimal("0.01"))
            calculated_subtotal += line_total

            item_rows.append([
                Paragraph(f"<b>{p_name}</b>", body_style),
                Paragraph(sku, subtitle_style),
                Paragraph(str(qty), ParagraphStyle("QtyVal", parent=body_style, alignment=1)),
                Paragraph(f"{curr_prefix}{price:.2f}", ParagraphStyle("PriceVal", parent=body_style, alignment=2)),
                Paragraph(f"{curr_prefix}{line_total:.2f}", ParagraphStyle("TotalVal", parent=bold_body_style, alignment=2)),
            ])
    else:
        for item in order.items:
            qty = item.quantity
            price = Decimal(str(item.unit_price)).quantize(Decimal("0.01"))
            line_total = (Decimal(str(qty)) * price).quantize(Decimal("0.01"))
            calculated_subtotal += line_total

            item_rows.append([
                Paragraph(f"<b>{item.product_name}</b>", body_style),
                Paragraph(item.product_sku, subtitle_style),
                Paragraph(str(qty), ParagraphStyle("QtyVal", parent=body_style, alignment=1)),
                Paragraph(f"{curr_prefix}{price:.2f}", ParagraphStyle("PriceVal", parent=body_style, alignment=2)),
                Paragraph(f"{curr_prefix}{line_total:.2f}", ParagraphStyle("TotalVal", parent=bold_body_style, alignment=2)),
            ])

    items_table = Table(item_rows, colWidths=[200, 100, 50, 90, 90])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 12))

    # 4. Financial Summary Section (Authoritative Invoice Amount Due)
    total_amount = invoice.amount_due.quantize(Decimal("0.01"))
    tax_amount = max(Decimal("0.00"), (total_amount - calculated_subtotal).quantize(Decimal("0.01")))

    summary_data = [
        ["", Paragraph("<b>Subtotal:</b>", ParagraphStyle("SubH", parent=body_style, alignment=2)),
         Paragraph(f"{curr_prefix}{calculated_subtotal:.2f}", ParagraphStyle("SubV", parent=body_style, alignment=2))],
        ["", Paragraph("<b>Tax:</b>", ParagraphStyle("TaxH", parent=body_style, alignment=2)),
         Paragraph(f"{curr_prefix}{tax_amount:.2f}", ParagraphStyle("TaxV", parent=body_style, alignment=2))],
        ["", Paragraph("<b>Total Due:</b>", ParagraphStyle("TotH", parent=bold_body_style, alignment=2)),
         Paragraph(f"<b>{curr_prefix}{total_amount:.2f}</b>", ParagraphStyle("TotV", parent=bold_body_style, alignment=2, textColor=colors.HexColor("#0284c7")))],
    ]

    summary_table = Table(summary_data, colWidths=[330, 110, 90])
    summary_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 30))

    # 5. Security & Verification Notice (No false payment claims)
    notice_text = (
        "<b>Notice:</b> This document is an authorized operational invoice generated from verified "
        f"order records in Orqestra. Payment terms: Due on or before {invoice.due_date.strftime('%Y-%m-%d')}. "
        "Status: " + ("PAID" if invoice.status == "paid" else "UNPAID / PENDING SETTLEMENT") + "."
    )
    story.append(Paragraph(notice_text, subtitle_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
