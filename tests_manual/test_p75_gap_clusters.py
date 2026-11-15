"""پ۷۵ · خواستهٔ مالک (موردِ ۹، ۲۰۲۶-۱۱-۱۲): «سوال‌هایِ بی‌جوابِ مشابه را گروه کن و از آن‌ها دانش بساز».

پوششِ داده‌شده:
۱. `cluster_signature`: امضایِ واژگانی (بدونِ ترتیبِ کلمات، بدونِ علامت/اعراب/پرهملول) — دو شکلِ یکِ
   سوال یکِ امضا، دو سوالِ متفاوت امضایِ متفاوت، و سوالِ بی‌محتوا None (تا با هیچ چیز گروه نشود).
۲. `record_gap` امضا را همان لحظه می‌نویسد و `backfill_cluster_keys` ردیف‌هایِ قدیمیِ NULL را پر
   می‌کند (بدونِ اسکریپتِ جدا، بدونِ تغییرِ متنِ سوال).
۳. `list_gap_clusters`: فقط گروهِ ≥۲ سوالی، شمارِ سوال‌ها و جمعِ تکرارها، ترتیبِ پایدار، و
   بیرون‌نشدنِ گپ‌هایِ بسته/نادیده‌گرفته‌شده.
۴. `answer_cluster`: یکِ پرسش‌وپاسخِ فعال با سوالِ نماینده + بستنِ همهٔ عضوهایِ باز؛ جوابِ خالی یا
   گروهِ بسته ⇒ KnowledgeError و **هیچ** تغییری در وضعیتِ گپ‌ها.
۵. پنل: «🧩 سوال‌هایِ بی‌جواب» ⇒ «🧠 سوال‌هایِ مشابه» ⇒ دیدنِ گروه ⇒ «✍️ یکِ جواب برایِ همه» ⇒
   پیش‌نمایش ⇒ تایید ⇒ دانش ساخته شد و گپ‌ها بسته شد؛ انصراف، شناسهٔ دست‌کاری‌شده/فروشگاهِ دیگر،
   و تپِ تاییدِ بی‌state همه رد می‌شوند.
۶. کیبورد: بودجهٔ ۶۴ بایتیِ `gapc_*` و ارقامِ جلالی در متن‌ها.

اجرا: python3 tests_manual/run_one.py test_p75_gap_clusters.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.database.models import KnowledgeGap, KnowledgeGapStatus, LearnedAnswer  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import knowledge_service  # noqa: E402
from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_A = 997_601
SHOP_A = 997_602
OWNER_B = 997_603
SHOP_B = 997_604
NOW = dt.datetime(2026, 11, 15, 8, 0, tzinfo=dt.timezone.utc)
IDS: dict[str, int] = {}


async def _seed() -> None:
    await reset_database()
    IDS["shop_a"] = await seed_usable_shop(OWNER_A, SHOP_A)
    IDS["shop_b"] = await seed_usable_shop(OWNER_B, SHOP_B)


async def _ask(shop_key: str, question: str, *, occurrences: int = 1, when: dt.datetime | None = None) -> int:
    async with session_scope() as session:
        await knowledge_service.record_gap(session, IDS[shop_key], question, now=when or NOW)
        if occurrences > 1:
            gap = (
                await session.execute(
                    select(KnowledgeGap).where(
                        KnowledgeGap.shop_bot_id == IDS[shop_key], KnowledgeGap.question_text == question
                    )
                )
            ).scalar_one()
            gap.occurrences = occurrences
        await session.commit()
    async with session_scope() as session:
        return (
            await session.execute(
                select(KnowledgeGap.id).where(
                    KnowledgeGap.shop_bot_id == IDS[shop_key], KnowledgeGap.question_text == question
                )
            )
        ).scalar_one()


async def _gap(gap_id: int) -> KnowledgeGap:
    async with session_scope() as session:
        return await session.get(KnowledgeGap, gap_id)


async def _gap_statuses(shop_key: str) -> dict[str, str]:
    async with session_scope() as session:
        rows = (
            await session.execute(select(KnowledgeGap.question_text, KnowledgeGap.status).where(KnowledgeGap.shop_bot_id == IDS[shop_key]))
        ).all()
    return {question: status.value if hasattr(status, "value") else str(status) for question, status in rows}


async def _learned(shop_key: str) -> list[LearnedAnswer]:
    async with session_scope() as session:
        return list(
            (await session.execute(select(LearnedAnswer).where(LearnedAnswer.shop_bot_id == IDS[shop_key]))).scalars().all()
        )


# ============================================================================= ۱ — امضا
def test_signature_groups_word_order_and_drops_noise() -> None:
    signature = knowledge_service.cluster_signature
    assert signature("قیمت ارسال چنده؟") == signature("چنده قیمت ارسال")
    assert signature("قیمتِ   ارسال چنده") == signature("قیمت ارسال چنده")
    assert signature("هزینه ارسال چقدر است") != signature("قیمت ارسال چنده"), "واژه‌هایِ محتوایی فرق دارند"
    assert signature("رنگ دیگر هم دارید؟") == signature("دیگر رنگ دارید")
    assert signature("کاپ‌کیک شکلاتی دارید") == signature("شکلاتی کاپ‌کیک دارید"), "نیم‌فاصله هم یکی می‌شود"
    assert signature("سلام") is None, "سوالِ بی‌محتوا نباید با چیزی گروه شود"
    assert signature("???") is None and signature(None) is None and signature("") is None
    assert signature("يک قيمت ارسال؟") == signature("یک قیمت ارسال"), "ی/کِ عربی و اعراب"
    assert len(signature("قیمت ارسال چنده")) == 64
    print("PASS test_signature_groups_word_order_and_drops_noise")


# ============================================================================= ۲ — ثبت و backfill
async def test_record_stores_signature_and_backfill_fills_old_rows() -> None:
    await _seed()
    gap_id = await _ask("shop_a", "قیمت ارسال چنده؟")
    gap = await _gap(gap_id)
    assert gap.cluster_key == knowledge_service.cluster_signature("قیمت ارسال چنده؟"), "امضا همان لحظه نوشته می‌شود"

    async with session_scope() as session:
        old = KnowledgeGap(
            shop_bot_id=IDS["shop_a"],
            question_text="چنده قیمت ارسال",
            question_key=knowledge_service.make_question_key("چنده قیمت ارسال"),
            cluster_key=None,
            occurrences=2,
            first_seen_at=NOW,
            last_seen_at=NOW,
            status=KnowledgeGapStatus.OPEN,
        )
        session.add(old)
        await session.flush()
        old_id = old.id
        filled = await knowledge_service.backfill_cluster_keys(session, IDS["shop_a"])
        await session.commit()
    assert filled == 1, filled
    assert (await _gap(old_id)).cluster_key == gap.cluster_key, "ردیفِ قدیمی به همان گروه می‌پیوندد"
    async with session_scope() as session:
        assert await knowledge_service.backfill_cluster_keys(session, IDS["shop_a"]) == 0, "دوباره کاری نیست"
    print("PASS test_record_stores_signature_and_backfill_fills_old_rows")


# ============================================================================= ۳ و ۴ — خوشه و دانش
async def test_clusters_and_cluster_answer() -> None:
    await _seed()
    await _ask("shop_a", "قیمت ارسال چنده؟", occurrences=4)
    await _ask("shop_a", "چنده قیمت ارسال", occurrences=2)
    await _ask("shop_a", "ارسال چند روز طول می‌کشه", occurrences=3)
    await _ask("shop_a", "رنگ دیگر دارید", occurrences=1)
    await _ask("shop_b", "قیمت ارسال چنده؟", occurrences=9)

    async with session_scope() as session:
        clusters = await knowledge_service.list_gap_clusters(session, IDS["shop_a"])
    assert len(clusters) == 1, [cluster["questions"] for cluster in clusters]
    cluster = clusters[0]
    assert cluster["size"] == 2 and cluster["occurrences"] == 6, cluster
    assert cluster["representative"].question_text == "قیمت ارسال چنده؟", "نماینده = پرتکرارترین"
    assert set(cluster["questions"]) == {"قیمت ارسال چنده؟", "چنده قیمت ارسال"}

    async with session_scope() as session:
        learned, answered = await knowledge_service.answer_cluster(session, IDS["shop_a"], cluster["signature"], "ارسال ۳۵ هزار تومان است.")
        await session.commit()
    assert answered == 2, answered
    statuses = await _gap_statuses("shop_a")
    assert statuses["قیمت ارسال چنده؟"] == "answered" and statuses["چنده قیمت ارسال"] == "answered", statuses
    assert statuses["ارسال چند روز طول می‌کشه"] == "open", "سوالِ تنها دست‌نخورده می‌ماند"
    rows = await _learned("shop_a")
    assert len(rows) == 1 and rows[0].question == "قیمت ارسال چنده؟", rows
    assert rows[0].answer == "ارسال ۳۵ هزار تومان است." and rows[0].is_active is True
    assert rows[0].source_gap_id == cluster["representative"].id

    async with session_scope() as session:
        try:
            await knowledge_service.answer_cluster(session, IDS["shop_a"], cluster["signature"], "دوباره")
            raise AssertionError("گروهِ بسته نباید دوباره جواب بگیرد")
        except knowledge_service.KnowledgeError as exc:
            assert exc.code == "gap_not_open", exc.code
        try:
            await knowledge_service.answer_cluster(session, IDS["shop_a"], "0" * 64, "   ")
            raise AssertionError("جوابِ خالی نباید پذیرفته شود")
        except knowledge_service.KnowledgeError as exc:
            assert exc.code == "gap_not_open", exc.code
    assert len(await _learned("shop_a")) == 1, "هیچ دانشِ تازه‌ای ساخته نشد"
    other = await _learned("shop_b")
    assert other == [], "فروشگاهِ دیگر دست‌نخورده"
    print("PASS test_clusters_and_cluster_answer")


# ============================================================================= ۵ — پنل
async def test_cluster_panel_flow(main_dp) -> None:
    await _seed()
    big = await _ask("shop_a", "قیمت ارسال چنده؟", occurrences=5)
    await _ask("shop_a", "چنده قیمت ارسال", occurrences=2)
    lone = await _ask("shop_a", "رنگ دیگر دارید", occurrences=1)

    owner = Chat(main_dp, OWNER_A)
    await owner.say("🧩 سوال‌هایِ بی‌جواب")
    flat = callbacks(owner.last_markup)
    assert "gap_clusters" in flat, flat

    await owner.tap("gap_clusters")
    body = owner.last_edit_text
    assert "🧠 سوال‌هایِ مشابه — ۱ گروه از ۳ سوالِ باز" in body, body
    assert "۲ سوال · ۷ تکرار" in body, body
    assert "۱ سوالِ باز در هیچ گروهی نیستند" in body, body
    assert not any(char.isascii() and char.isdigit() for char in body), body
    flat = callbacks(owner.last_edit_markup)
    assert f"gapc_view:{big}" in flat and f"gapc_answer:{big}" in flat, flat
    assert all(len(item.encode("utf-8")) <= 64 for item in flat), flat

    await owner.tap(f"gapc_view:{big}")
    assert "گروه با ۲ سوالِ متفاوت · ۷ بار پرسیده شده" in owner.last_edit_text, owner.last_edit_text

    await owner.tap(f"gapc_answer:{big}")
    assert "برایِ همهٔ ۲ سوال ذخیره می‌شود" in owner.last_text, owner.last_text
    await owner.say("ارسال تهران ۲۵ هزار تومان است.")
    preview = owner.last_text
    assert "ارسال تهران ۲۵ هزار تومان است." in preview and "قیمت ارسال چنده؟" in preview, preview
    assert "gapc_save_confirm" in callbacks(owner.last_markup), owner.last_markup

    await owner.tap("gapc_save_confirm")
    body = owner.last_edit_text
    assert "دانش ساخته شد و ۲ سوالِ این گروه بسته شد" in body, body
    statuses = await _gap_statuses("shop_a")
    assert statuses["قیمت ارسال چنده؟"] == statuses["چنده قیمت ارسال"] == "answered", statuses
    assert len(await _learned("shop_a")) == 1

    # گروه دیگر باز نیست ⇒ رد، بی‌تغییریِ دانش
    await owner.tap("gap_clusters")
    assert "فعلاً دو سوالِ شبیه هم نداری" in owner.last_edit_text, owner.last_edit_text

    # سوالِ تنها خوشه نیست ⇒ شناسه‌اش رد می‌شود
    edits_before = len(owner.edits)
    await owner.tap(f"gapc_answer:{lone}")
    assert owner.last_toast["text"] == texts.GAP_CLUSTER_STALE, owner.last_toast
    await owner.tap("gapc_view:999999")
    assert owner.last_toast["text"] == texts.GAP_CLUSTER_STALE
    await owner.tap(f"gapc_view:{big}")
    assert owner.last_toast["text"] == texts.GAP_CLUSTER_STALE, "گپِ بسته‌شده دیگر نماینده نیست"
    assert len(owner.edits) == edits_before

    # انصراف در میانهٔ نوشتنِ جواب ⇒ چیزی ذخیره نمی‌شود و حالت پاک می‌شود
    await _ask("shop_a", "کاپ‌کیک شکلاتی دارید", occurrences=2)
    await _ask("shop_a", "شکلاتی کاپ‌کیک دارید", occurrences=1)
    async with session_scope() as session:
        fresh = await knowledge_service.list_gap_clusters(session, IDS["shop_a"])
    new_rep = [item for item in fresh if item["size"] == 2][0]["representative"].id
    await owner.tap("gap_clusters")
    await owner.tap(f"gapc_answer:{new_rep}")
    before = len(owner.sent)
    await owner.say("انصراف")
    assert owner.last_text == texts.OPERATION_CANCELLED, owner.last_text
    assert len(owner.sent) == before + 1, "فقط پیامِ انصراف"
    statuses = await _gap_statuses("shop_a")
    assert statuses["کاپ‌کیک شکلاتی دارید"] == "open" and len(await _learned("shop_a")) == 1
    print("PASS test_cluster_panel_flow")


async def test_panel_rejects_other_shop_and_stale_confirm(main_dp) -> None:
    await _seed()
    await _ask("shop_a", "قیمت ارسال چنده؟", occurrences=3)
    await _ask("shop_a", "چنده قیمت ارسال", occurrences=1)
    async with session_scope() as session:
        clusters = await knowledge_service.list_gap_clusters(session, IDS["shop_a"])
        rep_id = clusters[0]["representative"].id

    other = Chat(main_dp, OWNER_B)
    await other.say("🧩 سوال‌هایِ بی‌جواب")
    assert "gap_clusters" not in callbacks(other.last_markup), "فهرستِ خالی دکمهٔ گروه ندارد"
    edits_before = len(other.edits)
    await other.tap(f"gapc_answer:{rep_id}")
    assert other.last_toast["text"] == texts.GAP_CLUSTER_STALE, other.last_toast
    await other.tap(f"gapc_view:{rep_id}")
    assert other.last_toast["text"] == texts.GAP_CLUSTER_STALE
    assert len(other.edits) == edits_before, "گپِ فروشگاهِ دیگر صفحه نمی‌سازد"
    assert len(await _learned("shop_b")) == 0

    # تایید بدونِ state ⇒ همان گاردِ کهنه، نه ذخیره
    stranger = Chat(main_dp, OWNER_A)
    await stranger.tap("gap_save_confirm")
    assert stranger.last_toast["text"] != texts.GAP_SAVED, stranger.last_toast
    await stranger.tap("gapc_save_confirm")
    assert stranger.last_toast["text"] != texts.CLUSTER_SAVED, stranger.last_toast
    assert len(await _learned("shop_a")) == 0, "بدونِ state هیچ دانشی ساخته نشد"
    print("PASS test_panel_rejects_other_shop_and_stale_confirm")


def test_keyboard_labels_and_limits() -> None:
    class _Gap:
        id = 4242
        question_text = "قیمت ارسال چنده؟"
        occurrences = 3
        status = KnowledgeGapStatus.OPEN

    cluster = {"signature": "a" * 64, "representative": _Gap(), "questions": ["قیمت ارسال چنده؟"], "size": 2, "occurrences": 5}
    flat = callbacks(keyboards.gap_clusters_keyboard([cluster]))
    assert flat == ["gapc_view:4242", "gapc_answer:4242", "gap_list:0"], flat
    assert all(len(item.encode("utf-8")) <= 64 for item in flat), flat
    assert callbacks(keyboards.gap_cluster_detail_keyboard(cluster)) == ["gapc_answer:4242", "gap_clusters"], flat
    body = texts.gap_clusters_text([cluster], 5)
    assert "۱ گروه از ۵ سوالِ باز" in body and "۲ سوال · ۵ تکرار" in body, body
    assert texts.gap_clusters_text([], 0) == texts.GAP_CLUSTERS_EMPTY
    print("PASS test_keyboard_labels_and_limits")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_signature_groups_word_order_and_drops_noise()
    await test_record_stores_signature_and_backfill_fills_old_rows()
    await test_clusters_and_cluster_answer()
    await test_cluster_panel_flow(main_dp)
    await test_panel_rejects_other_shop_and_stale_confirm(main_dp)
    test_keyboard_labels_and_limits()
    print("📊 نتیجه: ۶ تستِ پ۷۵ (خوشه‌بندیِ سوال‌هایِ بی‌جواب + دانش‌سازیِ گروهی) پاس شد")


if __name__ == "__main__":
    asyncio.run(main())
