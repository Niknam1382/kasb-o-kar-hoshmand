#!/usr/bin/env bash
# P44 · موردِ ۵۱: حلقهِ بکاپِ روزانهٔ دیتابیس.
#
# چرا یکِ کانتینرِ جدا با ایمیجِ خودِ postgres:16؟
#   · `pg_dump` باید هم‌نسخهٔ سرور باشد (نسخهٔ ۱۵ نمی‌تواند نسخهٔ ۱۶ را بگیرد) و ایمیجِ اپ
#     فقط پایتون دارد؛ با همین ایمیج، نسخه همیشه جفت است و بستهٔ تازه‌ای نصب نمی‌شود.
#   · رمزِ دیتابیس از متغیرهایِ محیطیِ همین کانتینر خوانده می‌شود (PGPASSWORD) و هیچ‌جا
#     نوشته نمی‌شود؛ نه در آرگومانِ دستور، نه در لاگ.
#   · کارِ این اسکریپت فقط «ساختنِ فایل» است. فرستادنِ فایل به ادمین و پاک‌کردنِ قدیمی‌ها
#     را خودِ اپ انجام می‌دهد (app/services/backup_service.py) تا یکِ سوییچِ پنلی رویِ کلِ
#     مسیر اثر بگذارد و مهلتِ نگه‌داشتن یکِ جایِ قابلِ تست داشته باشد.
set -u

DIR="${BACKUP_DIR:-/backups}"
HOUR="${BACKUP_AT_HOUR_UTC:-3}"
MINUTE="${BACKUP_AT_MINUTE_UTC:-5}"

mkdir -p "$DIR"
# اگر volume از نسخهٔ قبلی مانده، مالکش root است و کانتینرِ اپ (کاربرِ بدونِ root) نمی‌تواند
# فایلِ قدیمی را پاک کند. این یکِ خط، همان پوشه را برایِ هر دو کانتینر قابلِ نوشتن می‌کند.
# (فایل‌ها 0644 می‌مانند؛ فقطِ نامِ پوشهٔ داخلیِ volume باز است، نه چیزی بیرونِ داکر.)
chmod 0777 "$DIR" 2>/dev/null || true

run_backup() {
  stamp="$(date -u +%Y%m%d-%H%M%S)"
  tmp="$DIR/.tmp-$stamp.dump"
  # -Fc ⇒ فرمتِ فشردهٔ خودِ pg_dump (با pg_restore برمی‌گردد)، -Z6 ⇒ فشرده‌سازیِ متوسط.
  if pg_dump -Fc -Z6 -f "$tmp" "${PGDATABASE:-postgres}" 2>/tmp/pgdump.err; then
    mv "$tmp" "$DIR/kasbokar-$stamp.dump"
    # کاربرِ بدونِ دسترسیِ root در کانتینرِ اپ باید بتواند فایل را بخواند تا آن را برایِ ادمین بفرستد.
    chmod 0644 "$DIR/kasbokar-$stamp.dump"
    echo "بکاپ ساخته شد: kasbokar-$stamp.dump ($(stat -c%s "$DIR/kasbokar-$stamp.dump") بایت)"
  else
    rm -f "$tmp"
    echo "بکاپ ناموفق بود: $(tr '\n' ' ' < /tmp/pgdump.err)"
  fi
}

echo "حلقهِ بکاپ: هر روز ساعت ${HOUR}:${MINUTE} UTC در پوشهٔ ${DIR}"
while true; do
  now="$(date -u +%s)"
  next="$(date -u -d "today ${HOUR}:${MINUTE}" +%s)"
  if [ "$next" -le "$now" ]; then
    next="$(date -u -d "tomorrow ${HOUR}:${MINUTE}" +%s)"
  fi
  sleep "$(( next - now ))"
  run_backup
done
