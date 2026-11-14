"""پ۶۹ · موردِ ۳۶: برآوردِ هزینهٔ *تمام‌شده* از توکن‌هایِ واقعیِ هر فراخوانیِ AI.

چرا این فایل جدا است: تا این نسخه، قیمت‌گذاری دو عددِ *ثابت* داشت — `wallet_cost_per_1k_tokens_toman`
(چیزی که فروشگاه‌دار می‌پردازد) و `ai_cost_usd_per_1m_tokens` × `usd_to_toman_rate` (چیزی که ما به
ارائه‌دهنده می‌پردازیم، به‌عنوانِ فرض). هیچ‌جا ثبت نمی‌شد هر فراخوانی *واقعاً* چند توکن مصرف کرده،
پس نمی‌شد گفت آن فرض درست است یا نه. این سرویس همان مقایسه را از ردیف‌هایِ دفترِ کیف‌پول
(`wallet_transactions.ai_total_tokens`) می‌سازد.

سه خطِ واژگان که در همه‌جا حفظ می‌شود:
* MEASURED — چیزی که از ردیف‌هایِ دارایِ توکن خوانده می‌شود (تعداد، جمعِ توکن، جمعِ گرفته‌شده).
* EXTRAPOLATED — هزینهٔ خامِ آن توکن‌ها با نرخِ *تنظیم‌شده* در پنل (درست است اگر نرخ درست باشد).
* ESTIMATED — کفِ پرامپتِ سیستمی (تقریبِ نویسه÷توکن؛ tokenizerِ ارائه‌دهنده در دسترس نیست).

صراحتِ لازم: `ai_total_tokens` رویِ ردیف‌هایِ پیش از پ۶۹، کسرهایِ بی‌AI و مسیرِ صوت (که usage ندارد)
خالی است ⇒ صفحه عمداً «پوشش: x از y فراخوانی» را نشان می‌دهد و عددِ ساختگی از گذشته نمی‌سازد.
"""
from __future__ import annotations

import dataclasses
import datetime
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import TenantMode, WalletTransaction, WalletTransactionReason
from app.services import ai_context, wallet_service

# فقط این هشت دلیل «مصرفِ AI» هستند؛ شارژ، کمیسیون، انقضا و اصلاحِ ادمین در برآورد نمی‌آیند.
AI_REASONS: tuple[WalletTransactionReason, ...] = (
    WalletTransactionReason.CHAT_MESSAGE,
    WalletTransactionReason.PHOTO_ANALYSIS,
    WalletTransactionReason.RECEIPT_ANALYSIS,
    WalletTransactionReason.VOICE_TRANSCRIPTION,
    WalletTransactionReason.ORDER_DETECTION,
    WalletTransactionReason.CART_EDIT,
    WalletTransactionReason.CRM_SUMMARY,
    WalletTransactionReason.OWNER_ASSISTANT,
)
AI_REASON_VALUES: tuple[str, ...] = tuple(reason.value for reason in AI_REASONS)

# تقریبِ رایج برایِ فارسی/انگلیسیِ قاطی: هر توکن ≈ ۳٫۵ نویسه. tokenizerِ ارائه‌دهنده در دسترس نیست،
# پس هر عددی که با این ساخته می‌شود ESTIMATED است و هرگز MEASURED خوانده نمی‌شود.
CHARS_PER_TOKEN = 3.5


def _dec(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def estimate_tokens(text: str | None) -> int:
    """تقریبِ تعدادِ توکنِ یکِ متن — برایِ مقایسهٔ اندازه، نه صورتحساب (ESTIMATED)."""
    if not text:
        return 0
    return round(len(text) / CHARS_PER_TOKEN)


def prompt_floor_text(*, consultation: bool, global_prompt: str | None = None) -> str:
    """پرامپتِ سیستمیِ یکِ فروشگاه با صفرِ محصول و صفرِ دانش — همان چیزی که *همیشه* پرداخت می‌شود."""
    shop_bot = SimpleNamespace(
        tenant_mode=TenantMode.CONSULTATION if consultation else TenantMode.SALES, ai_instructions=""
    )
    return ai_context.build_system_prompt(shop_bot, [], global_system_prompt=global_prompt)


def prompt_floor_tokens(*, consultation: bool, global_prompt: str | None = None) -> int:
    return estimate_tokens(prompt_floor_text(consultation=consultation, global_prompt=global_prompt))


@dataclasses.dataclass(frozen=True)
class FeatureRow:
    """جمعِ یکِ قابلیتِ AI در پنجرهٔ زمانی؛ `measured_calls` همیشه ⊆ `calls` است."""

    reason: str
    calls: int
    measured_calls: int
    tokens: int
    charged_toman: int
    charged_measured_toman: int

    @property
    def mean_tokens(self) -> int:
        return round(self.tokens / self.measured_calls) if self.measured_calls else 0

    @property
    def charged_per_1k(self) -> int:
        """آنچه به‌ازایِ هر ۱۰۰۰ توکن *واقعاً* از فروشگاه گرفته شده (MEASURED)."""
        if not self.tokens:
            return 0
        return round(self.charged_measured_toman * 1000 / self.tokens)


@dataclasses.dataclass(frozen=True)
class CostView:
    since: datetime.datetime
    until: datetime.datetime
    rows: tuple[FeatureRow, ...]
    price_per_1k_toman: int  # تنظیمِ فعلیِ پنل (چیزی که فروشگاه می‌پردازد)
    raw_cost_per_1m_usd: Decimal  # تنظیمِ فعلیِ پنل (چیزی که ما به ارائه‌دهنده می‌دهیم)
    usd_to_toman_rate: int
    markup_multiplier: Decimal
    suggested_price_per_1k: int  # همان فرمولِ دکمهٔ «محاسبهٔ خودکار»
    prompt_floor_sales: int
    prompt_floor_consultation: int

    @property
    def calls(self) -> int:
        return sum(row.calls for row in self.rows)

    @property
    def measured_calls(self) -> int:
        return sum(row.measured_calls for row in self.rows)

    @property
    def tokens(self) -> int:
        return sum(row.tokens for row in self.rows)

    @property
    def charged_toman(self) -> int:
        return sum(row.charged_toman for row in self.rows)

    @property
    def raw_cost_per_1k_toman(self) -> Decimal:
        """هزینهٔ خامِ هر ۱۰۰۰ توکن به تومان (EXTRAPOLATED از دو تنظیمِ نرخِ پنل)."""
        return _dec(self.raw_cost_per_1m_usd) * _dec(self.usd_to_toman_rate) / Decimal(1000)

    @property
    def measured_raw_cost_toman(self) -> Decimal:
        """هزینهٔ خامِ توکن‌هایِ اندازه‌گرفته‌شده در این پنجره (EXTRAPOLATED)."""
        return _dec(self.tokens) * self.raw_cost_per_1k_toman / Decimal(1000)

    @property
    def mean_tokens(self) -> int:
        return round(self.tokens / self.measured_calls) if self.measured_calls else 0

    @property
    def charged_per_1k(self) -> int:
        if not self.tokens:
            return 0
        return round(sum(row.charged_measured_toman for row in self.rows) * 1000 / self.tokens)

    @property
    def coverage(self) -> float:
        """سهمِ فراخوانی‌هایی که توکنشان ثبت شده — می‌گوید عدد چقدر واقعی است."""
        return self.measured_calls / self.calls if self.calls else 0.0

    def margin_ratio(self, reason_value: str | None = None) -> Decimal | None:
        """چند برابرِ هزینهٔ خام از فروشگاه گرفته می‌شود؛ None وقتی دادهٔ اندازه‌گرفته نداریم."""
        rows = [row for row in self.rows if (reason_value is None or row.reason == reason_value) and row.tokens]
        if not rows:
            return None
        charged = _dec(sum(row.charged_measured_toman for row in rows)) * 1000 / _dec(sum(row.tokens for row in rows))
        raw = self.raw_cost_per_1k_toman
        return charged / raw if raw > 0 else None


async def observe(
    session: AsyncSession, *, since: datetime.datetime, until: datetime.datetime, admin_settings
) -> CostView:
    """یکِ جملهٔ GROUP BY ⇒ جمعِ هر قابلیتِ AI در پنجرهٔ `[since, until)`."""
    measured = WalletTransaction.ai_total_tokens.is_not(None)
    stmt = (
        select(
            WalletTransaction.reason,
            func.count(),
            func.count(WalletTransaction.ai_total_tokens),
            func.coalesce(func.sum(case((measured, WalletTransaction.ai_total_tokens), else_=0)), 0),
            func.coalesce(func.sum(-WalletTransaction.amount_toman), 0),
            func.coalesce(func.sum(case((measured, -WalletTransaction.amount_toman), else_=0)), 0),
        )
        .where(
            WalletTransaction.amount_toman < 0,
            WalletTransaction.reason.in_(list(AI_REASON_VALUES)),
            WalletTransaction.created_at >= since,
            WalletTransaction.created_at < until,
        )
        .group_by(WalletTransaction.reason)
    )
    rows = []
    for raw_reason, calls, measured_calls, tokens, charged, charged_measured in (await session.execute(stmt)).all():
        reason = getattr(raw_reason, "value", raw_reason)
        rows.append(
            FeatureRow(
                reason=str(reason),
                calls=int(calls),
                measured_calls=int(measured_calls),
                tokens=int(tokens),
                charged_toman=int(charged),
                charged_measured_toman=int(charged_measured),
            )
        )
    rows.sort(key=lambda row: (-row.tokens, row.reason))
    global_prompt = admin_settings.global_ai_system_prompt
    return CostView(
        since=since,
        until=until,
        rows=tuple(rows),
        price_per_1k_toman=int(admin_settings.wallet_cost_per_1k_tokens_toman),
        raw_cost_per_1m_usd=_dec(admin_settings.ai_cost_usd_per_1m_tokens),
        usd_to_toman_rate=int(admin_settings.usd_to_toman_rate),
        markup_multiplier=_dec(admin_settings.wallet_markup_multiplier),
        suggested_price_per_1k=wallet_service.compute_cost_per_1k_tokens_from_formula(admin_settings),
        prompt_floor_sales=prompt_floor_tokens(consultation=False, global_prompt=global_prompt),
        prompt_floor_consultation=prompt_floor_tokens(consultation=True, global_prompt=global_prompt),
    )
