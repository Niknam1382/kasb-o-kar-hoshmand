"""
تست: سازندهٔ PDFِ مستندات (scripts/build_docs_pdf.py)

۱. یکِ مارکداونِ نمونه (سرتیتر، جدول، لیست، بلوکِ کد) باید PDFِ معتبر بدهد: امضایِ %PDF،
   پایانِ %%EOF، فونتِ امبد‌شده و بیشترِ یکِ صفحه.
۲. هیچ «گلیفِ گم‌شده» نباید از fpdf بیرون بیاید (همان چیزی که در PDFِ فاکتور هم می‌پاییم);
   ایموجی و پیکان‌ها یا معادلِ فارسی می‌گیرند یا حذف، نه جعبهٔ خالی.
۳. فایلِ واقعیِ راهنما (docs/deployment-playbook.md) هم اگر داخلِ ایمیج باشد باید ساخته شود.

اجرا: python3 tests_manual/run_one.py test_p28_docs_pdf_builder.py
"""
from __future__ import annotations

import importlib.util
import logging
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SPEC = importlib.util.spec_from_file_location("build_docs_pdf", ROOT / "scripts" / "build_docs_pdf.py")
builder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(builder)

SAMPLE = """# راهنمایِ آزمایش

## بخشِ اول
یک پاراگرافِ فارسی با ⇒ و ⚠️ و 🧪 و یک «گیومه» و جدولِ زیر.

- موردِ یک
- موردِ دو با 💰 کیف‌پول

| ستونِ الف | ستونِ ب |
|---|---|
| مقدارِ یک | ۱۲۳ |
| مقدارِ دو | ۴۵۶ |

```bash
docker compose up -d
```

پاراگرافِ آخرِ بعدِ جدول، تا ببینیم جریانِ متن درست ادامه پیدا می‌کند یا نه.
"""


class _GlyphCatch(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _render(text: str, target: pathlib.Path) -> tuple[bytes, list[str]]:
    logger = logging.getLogger("fpdf.output")
    handler = _GlyphCatch()
    logger.addHandler(handler)
    level = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        builder.render(text, target, builder.plain(text.splitlines()[0].lstrip("# ").strip()))
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)
    payload = target.read_bytes()
    missing = [m for m in handler.messages if "missing the following glyphs" in m]
    return payload, missing


def test_sample_builds_a_valid_pdf(tmp_path: pathlib.Path) -> None:
    payload, missing = _render(SAMPLE, tmp_path / "out.pdf")
    assert payload.startswith(b"%PDF"), "امضایِ PDF"
    assert payload.rstrip().endswith(b"%%EOF"), "پایانِ استاندارد"
    assert b"/FontFile2" in payload, "فونتِ TTF باید امبد شود وگرنه فارسی رویِ دستگاهِ گیرنده خراب است"
    assert len(payload) > 2_000, len(payload)
    assert not missing, f"نمادهایِ نبودنی در فونت (جعبهٔ خالی): {missing}"
    print("✅ test_sample_builds_a_valid_pdf PASSED")


def test_glyph_sanitizer_covers_emoji_and_arrows() -> None:
    cleaned = builder.clean("⇒ ⚠️ 🧪 ← → ✓ ۱۴۵ پیام/s → ۸٬۷۰۰ کاربر «گیومه» — line")
    assert "⇒" not in cleaned and "⚠" not in cleaned and "🧪" not in cleaned, cleaned
    assert "پس" in cleaned, cleaned
    assert "«گیومه»" in cleaned and "—" in cleaned, "گیومهٔ فارسی و خطِ تیره در فونت هست، نباید حذف شوند"
    assert "۸٬۷۰۰" in cleaned, cleaned
    print("✅ test_glyph_sanitizer_covers_emoji_and_arrows PASSED")


def test_real_guide_renders_if_present(tmp_path: pathlib.Path) -> None:
    guide = ROOT / "docs" / "deployment-playbook.md"
    if not guide.is_file():  # `docs/` عمداً داخلِ ایمیج نمی‌رود (P24)
        print("⏭ test_real_guide_renders_if_present SKIPPED (docs/ در ایمیج نیست)")
        return
    payload, missing = _render(guide.read_text(encoding="utf-8"), tmp_path / "guide.pdf")
    assert payload.startswith(b"%PDF") and len(payload) > 20_000, len(payload)
    assert not missing, missing
    print("✅ test_real_guide_renders_if_present PASSED")


def main() -> None:
    tmp_path = pathlib.Path("/tmp/p28_docs_pdf")
    tmp_path.mkdir(parents=True, exist_ok=True)
    test_sample_builds_a_valid_pdf(tmp_path)
    test_glyph_sanitizer_covers_emoji_and_arrows()
    test_real_guide_renders_if_present(tmp_path)
    print("\n✅ همهٔ تست‌هایِ سازندهٔ PDFِ مستندات پاس شدند")


if __name__ == "__main__":
    main()
