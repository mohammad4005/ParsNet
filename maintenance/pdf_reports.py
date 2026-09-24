from io import BytesIO
from pathlib import Path

import arabic_reshaper
import jdatetime
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


NAVY = colors.HexColor("#102448")
BLUE = colors.HexColor("#2F6FE1")
LIGHT_BLUE = colors.HexColor("#EDF3FF")
PALE = colors.HexColor("#F7F9FD")
GRAY = colors.HexColor("#71809B")
RED = colors.HexColor("#B52F3D")
GREEN = colors.HexColor("#087C5D")


def rtl(value):
    value = "—" if value in (None, "") else str(value)
    return get_display(arabic_reshaper.reshape(value))


def jalali(value, with_time=False):
    if not value: return "—"
    if hasattr(value, "date") and with_time:
        converted = jdatetime.datetime.fromgregorian(datetime=value)
        return converted.strftime("%Y/%m/%d - %H:%M")
    date_value = value.date() if hasattr(value, "date") else value
    return jdatetime.date.fromgregorian(date=date_value).strftime("%Y/%m/%d")


def _register_fonts():
    candidates = [
        (Path("C:/Windows/Fonts/tahoma.ttf"), Path("C:/Windows/Fonts/tahomabd.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    ]
    for regular, bold in candidates:
        if regular.exists():
            pdfmetrics.registerFont(TTFont("Persian", str(regular)))
            pdfmetrics.registerFont(TTFont("PersianBold", str(bold if bold.exists() else regular)))
            return
    raise RuntimeError("فونت فارسی مناسب برای ساخت PDF پیدا نشد.")


def build_report_pdf(report):
    _register_fonts()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=24 * mm, bottomMargin=16 * mm,
        title="ParsNet Maintenance Report", author="ParsNet",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("FaTitle", parent=styles["Title"], fontName="PersianBold", fontSize=19, leading=27, textColor=NAVY, alignment=TA_RIGHT)
    heading_style = ParagraphStyle("FaHeading", parent=styles["Heading2"], fontName="PersianBold", fontSize=13, leading=20, textColor=NAVY, alignment=TA_RIGHT, spaceBefore=8, spaceAfter=7)
    body_style = ParagraphStyle("FaBody", parent=styles["BodyText"], fontName="Persian", fontSize=7.5, leading=11, textColor=NAVY, alignment=TA_RIGHT)
    center_style = ParagraphStyle("FaCenter", parent=body_style, alignment=TA_CENTER)
    small_style = ParagraphStyle("FaSmall", parent=body_style, fontSize=7.5, leading=11, textColor=GRAY)
    header_style = ParagraphStyle("FaHeader", parent=body_style, fontName="PersianBold", textColor=colors.white, alignment=TA_CENTER)

    def p(value, style=body_style): return Paragraph(rtl(value), style)
    def hp(value): return p(value, header_style)
    def table(data, widths=None, header=True):
        result = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="RIGHT")
        commands = [
            ("FONTNAME", (0, 0), (-1, -1), "Persian"), ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#DDE5F1")),
            ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, PALE]),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]
        if header:
            commands += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "PersianBold")]
        result.setStyle(TableStyle(commands))
        return result

    status_label = {"all": "همه کارها", "completed": "فقط انجام‌شده", "overdue": "فقط عقب‌افتاده"}[report["status"]]
    group_label = {"overall": "کلی و جامع", "equipment": "تفکیک دستگاه", "category": "تفکیک دسته‌بندی"}[report["group_by"]]
    scope = "همه تجهیزات"
    if report["equipment_filter"]: scope = f"دستگاه: {report['equipment_filter'].name}"
    elif report["category_filter"]: scope = f"دسته: {report['category_filter'].name}"

    story = [
        p("گزارش تخصصی نگهداری و تعمیرات", title_style),
        p(f"بازه گزارش: {jalali(report['start_date'])} تا {jalali(report['end_date'])}", small_style),
        p(f"وضعیت: {status_label}  |  نوع گزارش: {group_label}  |  محدوده: {scope}", small_style),
        Spacer(1, 5 * mm),
    ]
    summary = [
        [hp("درخواست‌های تعمیر"), hp("کارهای عقب‌افتاده"), hp("کارهای انجام‌شده")],
        [p(report["work_orders_total"], center_style), p(report["overdue_total"], center_style), p(report["completed_total"], center_style)],
    ]
    summary_table = table(summary, [60 * mm] * 3)
    summary_table.setStyle(TableStyle([("BACKGROUND", (0, 1), (-1, 1), LIGHT_BLUE), ("FONTNAME", (0, 1), (-1, 1), "PersianBold"), ("FONTSIZE", (0, 1), (-1, 1), 16)]))
    story += [summary_table, Spacer(1, 5 * mm), p("خلاصه تفکیکی", heading_style)]

    group_data = [[hp("درخواست تعمیر"), hp("کنترل عقب‌افتاده"), hp("سرویس عقب‌افتاده"), hp("کنترل انجام‌شده"), hp("سرویس انجام‌شده"), hp("عنوان")]]
    for row in report["group_rows"]:
        group_data.append([p(row["work_orders"], center_style), p(row["overdue_controls"], center_style), p(row["overdue_services"], center_style), p(row["completed_controls"], center_style), p(row["completed_services"], center_style), p(row["label"])])
    if len(group_data) == 1: group_data.append([p("۰", center_style)] * 5 + [p("اطلاعاتی در این بازه وجود ندارد")])
    story += [table(group_data, [20*mm, 29*mm, 29*mm, 29*mm, 29*mm, 44*mm]), Spacer(1, 4 * mm)]

    if report["show_overdue"]:
        story.append(p("کارهای عقب‌افتاده", heading_style))
        overdue_data = [[hp("روز تأخیر"), hp("تاریخ سررسید"), hp("دسته"), hp("تجهیز"), hp("عنوان کار")]]
        for row in report["overdue_services"]:
            overdue_data.append([p(row.days_overdue, center_style), p(jalali(row.next_due_date)), p(row.equipment.category.name), p(row.equipment.name), p(f"سرویس: {row.display_name}")])
        for row in report["overdue_controls"]:
            overdue_data.append([p(row.days_overdue, center_style), p(jalali(row.next_due_date)), p(row.equipment.category.name), p(row.equipment.name), p(f"کنترل: {row.title}")])
        if len(overdue_data) == 1: overdue_data.append([p("—")] * 4 + [p("کار عقب‌افتاده‌ای در این بازه وجود ندارد")])
        story += [table(overdue_data, [18*mm, 28*mm, 32*mm, 42*mm, 60*mm]), Spacer(1, 4 * mm)]

    if report["show_completed"]:
        story.append(p("کارهای انجام‌شده", heading_style))
        completed_data = [[hp("مسئول / نتیجه"), hp("تاریخ انجام"), hp("دسته"), hp("تجهیز"), hp("عنوان کار")]]
        for row in report["completed_services"]:
            person = (row.performed_by.get_full_name() or row.performed_by.username) if row.performed_by else "ثبت نشده"
            completed_data.append([p(person), p(jalali(row.performed_at, True)), p(row.plan.equipment.category.name), p(row.plan.equipment.name), p(f"سرویس: {row.plan.display_name}")])
        for row in report["completed_controls"]:
            completed_data.append([p(row.get_result_display()), p(jalali(row.performed_at, True)), p(row.control_item.equipment.category.name), p(row.control_item.equipment.name), p(f"کنترل: {row.control_item.title}")])
        if len(completed_data) == 1: completed_data.append([p("—")] * 4 + [p("کار انجام‌شده‌ای در این بازه وجود ندارد")])
        story += [table(completed_data, [32*mm, 32*mm, 30*mm, 36*mm, 50*mm]), Spacer(1, 4 * mm)]

    story += [p("درخواست‌های تعمیر ثبت‌شده", heading_style)]
    order_data = [[hp("وضعیت"), hp("اولویت"), hp("تاریخ اعلام"), hp("دسته"), hp("تجهیز"), hp("عنوان درخواست")]]
    for row in report["work_orders"]:
        order_data.append([p(row.get_status_display()), p(row.get_priority_display()), p(jalali(row.reported_at, True)), p(row.equipment.category.name), p(row.equipment.name), p(row.title)])
    if len(order_data) == 1: order_data.append([p("—")] * 5 + [p("درخواستی در این بازه ثبت نشده است")])
    story.append(table(order_data, [18*mm, 20*mm, 29*mm, 28*mm, 35*mm, 50*mm]))

    def decorate_page(canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(NAVY); canvas.rect(0, height - 12*mm, width, 12*mm, fill=1, stroke=0)
        canvas.setFont("PersianBold", 10); canvas.setFillColor(colors.white); canvas.drawRightString(width - 14*mm, height - 7.8*mm, rtl("پارس نت - گزارش نگهداری و تعمیرات"))
        canvas.setStrokeColor(colors.HexColor("#DDE5F1")); canvas.line(14*mm, 10*mm, width - 14*mm, 10*mm)
        canvas.setFont("Persian", 8); canvas.setFillColor(GRAY); canvas.drawString(14*mm, 6*mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=decorate_page, onLaterPages=decorate_page)
    return buffer.getvalue()


def build_service_worksheet_pdf(schedule, filters):
    _register_fonts()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm,
        topMargin=21 * mm, bottomMargin=15 * mm,
        title="ParsNet Service Worksheets", author="ParsNet",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("WorksheetTitle", parent=styles["Title"], fontName="PersianBold", fontSize=15, leading=21, textColor=NAVY, alignment=TA_RIGHT)
    body_style = ParagraphStyle("WorksheetBody", parent=styles["BodyText"], fontName="Persian", fontSize=7.5, leading=10, textColor=NAVY, alignment=TA_RIGHT)
    small_style = ParagraphStyle("WorksheetSmall", parent=body_style, fontSize=6.8, leading=9, textColor=GRAY)
    center_style = ParagraphStyle("WorksheetCenter", parent=body_style, alignment=TA_CENTER)
    checkbox_style = ParagraphStyle("WorksheetCheckbox", parent=center_style, fontSize=13, leading=14)
    header_style = ParagraphStyle("WorksheetHeader", parent=body_style, fontName="PersianBold", textColor=colors.white, alignment=TA_CENTER)

    def p(value, style=body_style): return Paragraph(rtl(value), style)
    def hp(value): return p(value, header_style)
    def styled_table(data, widths, repeat=0, compact=False, row_heights=None):
        result = Table(data, colWidths=widths, rowHeights=row_heights, repeatRows=repeat, hAlign="RIGHT")
        result.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Persian"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), .45, colors.HexColor("#CFD9E8")),
            ("TOPPADDING", (0, 0), (-1, -1), 4 if compact else 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 if compact else 6),
            ("ROWBACKGROUNDS", (0, repeat), (-1, -1), [colors.white, PALE]),
        ]))
        if repeat:
            result.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, repeat - 1), NAVY), ("TEXTCOLOR", (0, 0), (-1, repeat - 1), colors.white)]))
        return result

    story = []
    for index, entry in enumerate(schedule):
        plan = entry["plan"]
        if index:
            story.append(PageBreak())
        story += [
            p("فرم میدانی بازدید و سرویس دوره‌ای", title_style),
            p(f"{plan.display_name} - {plan.equipment.name}", body_style),
            Spacer(1, 3 * mm),
        ]
        meta = [
            [p(f"تاریخ برنامه‌ریزی: {jalali(entry['due_date'])}"), p(f"تناوب: {plan.get_frequency_display()}"), p(f"دسته: {plan.equipment.category.name}"), p(f"کد تجهیز: {plan.equipment.code}")],
            [p("ساعت انجام: ................"), p("تاریخ انجام: ....../....../......"), p("نام بازدیدکننده: ..............................."), p(f"محل: {plan.equipment.location or '—'}")],
        ]
        story += [styled_table(meta, [45*mm]*4, compact=True), Spacer(1, 3 * mm)]
        rows = [[hp("توضیحات"), hp("اقدام"), hp("مشکل"), hp("سالم"), hp("راهنما"), hp("مورد کنترل و سرویس"), hp("ردیف")]]
        for number, item in enumerate(plan.checklist.items.all(), start=1):
            rows.append([p(""), p("□", checkbox_style), p("□", checkbox_style), p("□", checkbox_style), p(item.help_text or "—", small_style), p(item.title), p(number, center_style)])
        if len(rows) == 1:
            rows.append([p("—")] * 5 + [p("موردی برای این برنامه تعریف نشده است"), p("1", center_style)])
        story += [styled_table(rows, [33*mm, 12*mm, 12*mm, 12*mm, 40*mm, 61*mm, 10*mm], repeat=1, compact=True), Spacer(1, 3*mm)]
        notes = Table([[p("شرح ایرادها و اقدامات لازم")], [p(" ")], [p(" ")]], colWidths=[180*mm], rowHeights=[8*mm, 12*mm, 12*mm])
        notes.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.45,colors.HexColor("#CFD9E8")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
        story += [notes, Spacer(1, 2*mm)]
        result_line = f"نتیجه نهایی:   □ قابل بهره‌برداری     □ نیازمند توقف     □ درخواست تعمیر ثبت شود"
        story += [styled_table([[p(result_line)]], [180*mm], compact=True), Spacer(1, 2*mm)]
        story += [styled_table([[p("قطعات یا اقلام مصرف‌شده: ........................................................................................................................................")]], [180*mm], compact=True), Spacer(1, 3*mm)]
        signatures = [[Paragraph(rtl("ثبت در نرم‌افزار توسط")+"<br/><br/>........................", center_style), Paragraph(rtl("تأیید سرپرست واحد")+"<br/><br/>........................", center_style), Paragraph(rtl("امضای انجام‌دهنده")+"<br/><br/>........................", center_style)]]
        story.append(styled_table(signatures, [60*mm]*3, compact=True, row_heights=[18*mm]))

    if not story:
        story = [p("فرم سرویس دوره‌ای", title_style), Spacer(1, 10*mm), p("در بازه انتخاب‌شده برنامه‌ای برای چاپ وجود ندارد.")]

    def decorate_page(canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(NAVY); canvas.rect(0, height - 11*mm, width, 11*mm, fill=1, stroke=0)
        canvas.setFont("PersianBold", 9); canvas.setFillColor(colors.white); canvas.drawRightString(width - 12*mm, height - 7.2*mm, rtl("پارس نت - فرم بازدید و سرویس دوره‌ای"))
        canvas.setStrokeColor(colors.HexColor("#DDE5F1")); canvas.line(12*mm, 9*mm, width - 12*mm, 9*mm)
        canvas.setFont("Persian", 7); canvas.setFillColor(GRAY); canvas.drawString(12*mm, 5.5*mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=decorate_page, onLaterPages=decorate_page)
    return buffer.getvalue()
