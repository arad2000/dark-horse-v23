"""
Dark Horse Engine V2.2 — گسترش نسخه ۲.۱ با دو شاخص جدید:
  ۱. شاخص تعارض درونی (Internal Conflict Index)
  ۲. شاخص اطمینان (Confidence Index)

این ماژول فایل اصلی را تغییر نمی‌دهد؛ بلکه کلاس DarkHorseEngineV2 را گسترش می‌دهد.
پاسخ به نقد ارزیاب + هم‌راستا با یافته‌های گزارش DHR Global (بحران هویت حرفه‌ای)
"""
import importlib.util
import os

# ─── بارگذاری کلاس پایه از فایل اصلی ───
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ENGINE_PATH = os.path.join(_BASE_DIR, "dark_horse_engine_v2.py")

_spec = importlib.util.spec_from_file_location("darkhorse_base", _ENGINE_PATH)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
DarkHorseEngineV2 = _base.DarkHorseEngineV2


class DarkHorseEngineV22(DarkHorseEngineV2):
    """نسخه ۲.۲ — با شاخص‌های تعارض درونی و اطمینان"""

    # ═══════════════════════════════════════════════════════════
    #  شاخص ۱: تعارض درونی (برای هر رشته)
    # ═══════════════════════════════════════════════════════════
    def _compute_internal_conflict(self, m, s, v):
        """
        اختلاف بین سه لایه M، S، V را می‌سنجد.
        تعارض بالا = ریسک بحران هویت حرفه‌ای در آینده (یافته DHR Global)
        m, s, v: مقادیر ۰ تا ۱
        """
        values = [m, s, v]

        # بازه (max - min)
        spread = max(values) - min(values)

        # انحراف معیار
        mean = sum(values) / 3
        std = (sum((x - mean) ** 2 for x in values) / 3) ** 0.5

        # شاخص ترکیبی (میانگین بازه و انحراف معیار)
        index = round((spread + std) / 2, 3)

        # شناسایی منبع تعارض (کدام دو لایه بیشترین اختلاف را دارند)
        pairs = [
            (abs(m - s), "انگیزه-راهبرد"),
            (abs(m - v), "انگیزه-ارزش"),
            (abs(s - v), "راهبرد-ارزش"),
        ]
        pairs.sort(reverse=True)
        source = pairs[0][1]
        source_gap = round(pairs[0][0], 3)

        # تفسیر کیفی
        if index < 0.10:
            level = "همسویی درونی بسیار بالا"
            warning = None
        elif index < 0.20:
            level = "همسویی درونی بالا"
            warning = None
        elif index < 0.35:
            level = "تعارض متوسط"
            warning = f"بین لایه‌های {source} تفاوت قابل توجهی وجود دارد."
        else:
            level = "تعارض بالا"
            warning = (
                f"⚠️ تعارض درونی شدید بین {source}. "
                f"این الگو می‌تواند در آینده به کاهش انگیزه و بحران هویت حرفه‌ای منجر شود."
            )

        return {
            "index": index,
            "spread": round(spread, 3),
            "std": round(std, 3),
            "level": level,
            "source": source,
            "source_gap": source_gap,
            "components": {"m": round(m, 3), "s": round(s, 3), "v": round(v, 3)},
            "warning": warning,
        }

    # ═══════════════════════════════════════════════════════════
    #  شاخص ۲: اطمینان (سراسری — مقایسه رتبه‌ها)
    # ═══════════════════════════════════════════════════════════
    def _compute_confidence(self, discovered):
        """
        نشان می‌دهد چقدر می‌توان به رتبه‌بندی اعتماد کرد.
        اگر رتبه ۱ و ۲ نزدیک باشند، اطمینان پایین است.
        """
        if not discovered:
            return {
                "index": 0.0,
                "level": "نامشخص",
                "interpretation": "هیچ رشته‌ای از فیلتر عبور نکرد.",
            }

        score1 = discovered[0]["individuality_fit"]["score"]

        if len(discovered) == 1:
            return {
                "index": 1.0,
                "level": "اطمینان کامل (تک‌گزینه)",
                "rank1_name": discovered[0]["major_name_fa"],
                "rank1_score": score1,
                "competitive_count": 1,
                "interpretation": "فقط یک رشته از فیلتر عبور کرد؛ گزینه جایگزین قوی وجود ندارد.",
            }

        score2 = discovered[1]["individuality_fit"]["score"]
        gap = score1 - score2
        relative_gap = gap / score1 if score1 > 0 else 0

        # تعداد رشته‌های رقابتی (امتیاز ≥ ۹۰٪ رتبه اول)
        threshold = score1 * 0.90
        competitive = sum(
            1 for d in discovered if d["individuality_fit"]["score"] >= threshold
        )

        index = round(min(1.0, relative_gap * 2), 3)

        if relative_gap > 0.40:
            level = "اطمینان بسیار بالا"
        elif relative_gap > 0.20:
            level = "اطمینان بالا"
        elif relative_gap > 0.10:
            level = "اطمینان متوسط"
        else:
            level = "اطمینان پایین"

        return {
            "index": index,
            "level": level,
            "rank1_name": discovered[0]["major_name_fa"],
            "rank1_score": score1,
            "rank2_name": discovered[1]["major_name_fa"],
            "rank2_score": score2,
            "gap": round(gap, 1),
            "relative_gap": round(relative_gap, 3),
            "competitive_count": competitive,
            "interpretation": (
                f"اختلاف رتبه ۱ ({discovered[0]['major_name_fa']}) و رتبه ۲ "
                f"({discovered[1]['major_name_fa']}) برابر {round(gap, 1)}٪ است. "
                f"{competitive} رشته در بازه رقابتی قرار دارند."
            ),
        }

    # ═══════════════════════════════════════════════════════════
    #  بازنویسی متد اصلی — افزودن دو شاخص به خروجی
    # ═══════════════════════════════════════════════════════════
    def discover_individuality(self, user_motives, sjt_answers, conjoint_choices):
        # اجرای منطق پایه (نسخه ۲.۱)
        result = super().discover_individuality(user_motives, sjt_answers, conjoint_choices)

        # افزودن شاخص تعارض درونی به هر رشته
        for item in result["discovered_majors"]:
            raw = item["individuality_fit"]["raw_components"]
            conflict = self._compute_internal_conflict(
                raw["m_score"] / 100,
                raw["s_score"] / 100,
                raw["v_score"] / 100,
            )
            item["individuality_fit"]["internal_conflict"] = conflict

        # افزودن شاخص اطمینان به خلاصه
        result["summary"]["confidence"] = self._compute_confidence(result["discovered_majors"])

        # تعارض درونی رشته برتر (برای دسترسی سریع)
        if result["discovered_majors"]:
            result["summary"]["top_choice_conflict"] = result["discovered_majors"][0][
                "individuality_fit"
            ]["internal_conflict"]

        # به‌روزرسانی متادیتا
        result["method"]["version"] = "2.2"
        result["method"]["new_features"] = [
            "internal_conflict_index (شاخص تعارض درونی)",
            "confidence_index (شاخص اطمینان)",
        ]
        result["method"]["based_on"] = "پاسخ به نقد ارزیاب نسخه ۳.۰ + یافته‌های DHR Global"

        return result
