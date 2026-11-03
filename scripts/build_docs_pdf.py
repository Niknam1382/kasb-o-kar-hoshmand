#!/usr/bin/env python3
"""مارکداونِ فارسی ← PDFِ راست‌به‌چپ با فونتِ خودِ پروژه (Vazirmatn).

چرا این اسکریپت هست: در ایمیج و رویِ میزبان هیچ رندرکنندهٔ PDF نیست (pdftoppm/ghostscript/
PyMuPDF نصب نیستند)، پس «خروجیِ PDFِ راهنما» هم باید با همان fpdf2 و همان shapingِ `invoice_service`
ساخته شود. متنِ پیش ازِ shaping خط‌بندی می‌شود (نکتهٔ مهم: خط‌بندی رویِ رشتهٔ شکل‌گرفته غلط درمی‌آید)
و هر بلوکِ کد بدونِ shaping و چپ‌چین رستر می‌شود تا دستورِ شل و شماره‌پورت درست خوانده شود.

اجرا (داخل کانتینر، چون fpdf2/arabic_reshaper/python-bidi در ایمیج هستند):
    docker compose run --rm bot python3 scripts/build_docs_pdf.py docs/deployment-playbook.md
خروجی کنارِ همان فایل نوشته می‌شود (با پسوندهایِ .pdf).
"""
from __future__ import annotations

import pathlib
import re
import sys

MARGIN = 16.0
PAGE_WIDTH = 210.0
USABLE = PAGE_WIDTH - 2 * MARGIN
FONT_CANDIDATES = (
    "app/assets/fonts/Vazirmatn-Regular.ttf",
    "/app/app/assets/fonts/Vazirmatn-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
BRAND = (15, 94, 92)
INK = (24, 28, 32)
INK_SOFT = (96, 104, 112)
CODE_BG = (243, 245, 245)
ZEBRA = (248, 250, 250)
RULE = (205, 213, 216)
BOTTOM_LIMIT = 24.0  # فاصله‌یِ پایینِ صفحه که متن نباید واردش شود (جایِ فوتر)

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*")
_CODE = re.compile(r"`([^`]+)`")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_digits(value: object) -> str:
    return str(value).translate(FA_DIGITS)


def font_path() -> str:
    root = pathlib.Path(__file__).resolve().parent.parent
    for candidate in FONT_CANDIDATES:
        path = pathlib.Path(candidate)
        if not path.is_absolute():
            path = root / path
        if path.is_file():
            return str(path)
    raise SystemExit("هیچ فونتِ فارسی پیدا نشد؛ راهنما را PDF نکن.")


# فونتِ باندل‌شده (Vazirmatn) ایموجی و بعضی نمادها را ندارد و fpdf آن‌ها را «جعبه» می‌کند.
# پیش ازِ رستر، نمادهایِ پشتیبانی‌نشده یا با معادلِ فارسی جایگزین یا حذف می‌شوند (تستِ گلیفِ
# فاکتور هم همین را می‌پاید؛ اینجا همان درس).
_REPLACEMENTS = str.maketrans({
    "⇒": " پس ", "→": " به ", "←": " از ", "⚠": "", "️": "",
    "≤": "<=", "≥": ">=", "✓": ":", "×": "x",
})
_SAFE_EXTRA = {0x200C, 0x200D, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x00AB, 0x00BB}


def clean(text: str) -> str:
    """هر نویسه بیرونِ الفبایِ فارسی/لاتین/نشانه‌هایِ امن را حذف می‌کند تا «جعبه» در PDF نیفتد."""
    out = text.translate(_REPLACEMENTS)
    kept = "".join(ch for ch in out if ord(ch) < 0x2000 or ord(ch) in _SAFE_EXTRA)
    return " ".join(kept.split()) if "  " in kept else kept


def plain(text: str) -> str:
    """نمادهایِ مارکداون را برمی‌دارد (فونتِ باندل‌شده یکِ وزن دارد، پس bold با رنگ نشان داده می‌شود)."""
    text = _CODE.sub(r"\1", text)
    text = _BOLD.sub(r"\1", text)
    return clean(_ITALIC.sub(r"\1", text).strip())


def wrap(pdf, text: str, width: float) -> list[str]:
    """خط‌بندیِ حریصانه رویِ رشتهٔ *منطقی* (قبل از shaping)."""
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if pdf.get_string_width(trial) <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class Builder:
    def __init__(self, pdf, shape) -> None:
        self.pdf = pdf
        self.shape = shape

    def _move(self, height: float) -> None:
        self.pdf.ln(height)

    def heading(self, text: str, level: int) -> None:
        sizes = {1: 19.0, 2: 14.5, 3: 12.0}
        before = {1: 2.0, 2: 7.0, 3: 4.5}[level]
        after = {1: 4.0, 2: 3.0, 3: 2.2}[level]
        self._move(before)
        self.pdf.set_font("fa", "", sizes[level])
        self.pdf.set_text_color(*(BRAND if level == 2 else INK))
        for line in wrap(self.pdf, text, USABLE):
            self.pdf.cell(USABLE, sizes[level] * 0.62, self.shape(line), new_x="LMARGIN", new_y="NEXT", align="R")
        if level == 2:
            y = self.pdf.get_y() + 0.8
            self.pdf.set_draw_color(*BRAND)
            self.pdf.set_line_width(0.5)
            self.pdf.line(MARGIN, y, MARGIN + USABLE, y)
            self._move(1.6)
        else:
            self._move(after)
        self.pdf.set_text_color(*INK)

    def paragraph(self, text: str, *, size: float = 10.0, indent: float = 0.0) -> None:
        self.pdf.set_font("fa", "", size)
        self.pdf.set_text_color(*INK)
        width = USABLE - indent
        for line in wrap(self.pdf, text, width):
            self.pdf.set_xy(MARGIN, self.pdf.get_y())
            self.pdf.cell(width, size * 0.62, self.shape(line), new_x="LMARGIN", new_y="NEXT", align="R")
        self._move(1.8)

    def bullet(self, text: str, *, marker: str = "•", size: float = 10.0, level: int = 0) -> None:
        self.pdf.set_font("fa", "", size)
        self.pdf.set_text_color(*INK)
        indent = 4.0 + 5.0 * level
        width = USABLE - indent
        lines = wrap(self.pdf, text, width - 4.0)
        for index, line in enumerate(lines):
            self.pdf.set_xy(MARGIN, self.pdf.get_y())
            self.pdf.cell(width, size * 0.62, self.shape(f"{marker}  {line}" if index == 0 else "    " + line), align="R")
            self.pdf.set_y(self.pdf.get_y() + size * 0.62)
        self._move(1.0)

    def code_block(self, lines: list[str]) -> None:
        if not lines:
            return
        self.pdf.set_font("fa", "", 8.6)
        row_h = 4.6
        height = row_h * len(lines) + 3.0
        if self.pdf.get_y() + height > self.pdf.h - BOTTOM_LIMIT:
            self.pdf.add_page()
        top = self.pdf.get_y()
        self.pdf.set_fill_color(*CODE_BG)
        self.pdf.rect(MARGIN, top, USABLE, height, style="F")
        self.pdf.set_text_color(*INK)
        self.pdf.set_xy(MARGIN + 2.0, top + 1.6)
        for line in lines:
            self.pdf.set_xy(MARGIN + 2.0, self.pdf.get_y())
            self.pdf.cell(USABLE - 4.0, row_h, line, align="L")
            self.pdf.set_y(self.pdf.get_y() + row_h)
        self.pdf.set_xy(MARGIN, top + height + 2.0)
        self.pdf.set_text_color(*INK)

    def table(self, rows: list[list[str]]) -> None:
        if len(rows) < 2:
            return
        header, body = rows[0], rows[1:]
        columns = len(header)
        widths = [USABLE / columns] * columns
        for _ in range(2):
            weights = []
            for index in range(columns):
                cells = [header[index]] + [row[index] if index < len(row) else "" for row in body]
                widest = max(self.pdf.get_string_width(self.shape(cell.split()[0])) if cell.split() else 0 for cell in cells)
                weights.append(max(widest, 12.0))
            total = sum(weights)
            widths = [max(16.0, USABLE * weight / total) for weight in weights]
            scale = USABLE / sum(widths)
            widths = [width * scale for width in widths]
        self.pdf.set_font("fa", "", 9.0)

        def draw_row(cells: list[str], *, fill=None, bold_row: bool = False) -> None:
            line_sets = []
            for index, cell in enumerate(cells):
                line_sets.append(wrap(self.pdf, plain(cell), widths[index] - 3.0))
            height = max(len(lines) for lines in line_sets) * 4.6 + 3.4
            if self.pdf.get_y() + height > self.pdf.h - BOTTOM_LIMIT:
                self.pdf.add_page()
            top = self.pdf.get_y()
            x = MARGIN + USABLE
            for index, lines in enumerate(line_sets):
                width = widths[index]
                x -= width
                self.pdf.set_xy(x, top)
                if fill is not None:
                    self.pdf.set_fill_color(*fill)
                self.pdf.set_text_color(*(255, 255, 255) if bold_row else INK)
                self.pdf.cell(width, height, "", border="B", fill=fill is not None)
                self.pdf.set_font("fa", "", 9.0)
                inner_y = top + 1.7
                for line in lines:
                    self.pdf.set_xy(x + 1.5, inner_y)
                    self.pdf.cell(width - 3.0, 4.6, self.shape(line), align="R")
                    inner_y += 4.6
            self.pdf.set_text_color(*INK)
            self.pdf.set_xy(MARGIN, top + height)

        draw_row(header, fill=BRAND, bold_row=True)
        for index, row in enumerate(body):
            padded = [row[i] if i < len(row) else "" for i in range(columns)]
            draw_row(padded, fill=ZEBRA if index % 2 else None)
        self._move(3.0)


def render(markdown: str, out: pathlib.Path, title: str) -> None:
    import arabic_reshaper
    from bidi.algorithm import get_display
    from fpdf import FPDF

    def shape(text: str) -> str:
        return get_display(arabic_reshaper.reshape(text)) if text else ""


    class Doc(FPDF):
        def footer(self):
            self.set_y(-13)
            self.set_font("fa", "", 8.4)
            self.set_text_color(*INK_SOFT)
            label = shape(f"{title} · صفحهٔ {fa_digits(self.page_no())}")
            self.cell(0, 5, label, align="C")

    pdf = Doc(format="A4")
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(True, margin=BOTTOM_LIMIT)
    pdf.add_font("fa", "", font_path())
    pdf.set_title(title)
    pdf.alias_nb_pages = False
    pdf.add_page()
    b = Builder(pdf, shape)

    lines = markdown.splitlines()
    index = 0
    table: list[list[str]] = []
    code: list[str] | None = None
    first_heading_done = False
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if code is not None:
            if stripped.startswith("```"):
                b.code_block(code)
                code = None
            else:
                code.append(raw.replace("\t", "    "))
            index += 1
            continue
        if stripped.startswith("```"):
            code = []
            index += 1
            continue
        if _TABLE_ROW.match(stripped):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not all(set(c) <= set("-: ") for c in cells):
                table.append(cells)
            index += 1
            continue
        if table:
            b.table(table)
            table = []
        if not stripped:
            index += 1
            continue
        if stripped.startswith("# "):
            b.heading(plain(stripped[2:]), 1)
            first_heading_done = True
        elif stripped.startswith("## "):
            b.heading(plain(stripped[3:]), 2)
        elif stripped.startswith("### "):
            b.heading(plain(stripped[4:]), 3)
        elif re.match(r"^[-*] ", stripped):
            level = 1 if raw.startswith("  ") or raw.startswith("\t") else 0
            b.bullet(plain(stripped[2:]), level=level)
        elif re.match(r"^\d+[.)] ", stripped):
            marker = stripped.split(" ", 1)[0]
            b.bullet(plain(stripped.split(" ", 1)[1]), marker=marker)
        elif stripped.startswith("> "):
            b.paragraph(plain(stripped[2:]), size=9.6, indent=4.0)
        elif stripped == "---":
            y = pdf.get_y() + 1.5
            pdf.set_draw_color(*RULE)
            pdf.set_line_width(0.3)
            pdf.line(MARGIN, y, MARGIN + USABLE, y)
            b._move(3.0)
        else:
            b.paragraph(plain(stripped))
        index += 1
    if table:
        b.table(table)
    if code is not None:
        b.code_block(code)

    pdf.output(str(out))

    if not first_heading_done:
        print("هشدار: فایلِ ورودی سرتیترِ # نداشت")


def main() -> int:
    if len(sys.argv) < 2:
        print("استفاده: python3 scripts/build_docs_pdf.py <فایل.md> [<خروجی.pdf>]")
        return 2
    source = pathlib.Path(sys.argv[1])
    if not source.is_file():
        print(f"یافت نشد: {source}")
        return 2
    target = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else source.with_suffix(".pdf")
    text = source.read_text(encoding="utf-8")
    title = plain(text.splitlines()[0].lstrip("# ").strip()) if text else source.stem
    render(text, target, title[:70])
    print(f"PDF ساخته شد: {target} ({target.stat().st_size:,} بایت)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
