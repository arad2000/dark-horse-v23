"""
Dark Horse Engine V2.3.2 — هماهنگ‌سازی دوطرفه شدت و نوع تعارض
• جهت ۱: aligned → بدون برچسب «تعارض»
• جهت ۲: تعارض واقعی → حداقل «تعارض خفیف»
"""
import importlib.util
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_V22_PATH = os.path.join(_BASE_DIR, "darkhorse_v22.py")

_spec = importlib.util.spec_from_file_location("darkhorse_v22", _V22_PATH)
_v22 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_v22)
DarkHorseEngineV22 = _v22.DarkHorseEngineV22


class DarkHorseEngineV23(DarkHorseEngineV22):
    """نسخه ۲.۳.۲ — تعارض وزن‌دار + هماهنگ‌سازی دوطرفه + گرادیان + روایت"""

    # وزن‌های نظری تعارض
    W_MV = 1.00
    W_MS = 0.50
    W_SV = 0.60

    # آستانه‌ها
    TH_MV_CRISIS = 0.45
    TH_MV_GAP = 0.30
    TH_MS = 0.40
    TH_SV = 0.40

    # ═══════════════════════════════════════════════════════════
    #  شاخص تعارض درونی — نسخه ۲.۳.۲ (هماهنگ‌سازی دوطرفه)
    # ═══════════════════════════════════════════════════════════
    def _compute_internal_conflict(self, m, s, v):
        gap_mv = abs(m - v)
        gap_ms = abs(m - s)
        gap_sv = abs(s - v)

        # شاخص وزن‌دار
        w_sum = self.W_MV + self.W_MS + self.W_SV
        weighted = (gap_mv * self.W_MV + gap_ms * self.W_MS + gap_sv * self.W_SV) / w_sum
        index = round(weighted, 3)

        # ── گام ۱: شدت اولیه بر اساس index ──
        if index < 0.15:
            severity, severity_label = "very_low", "همسویی درونی بسیار بالا"
        elif index < 0.25:
            severity, severity_label = "low", "همسویی درونی خوب"
        elif index < 0.35:
            severity, severity_label = "moderate", "تعارض خفیف"
        elif index < 0.50:
            severity, severity_label = "high", "تعارض متوسط"
        else:
            severity, severity_label = "severe", "تعارض شدید"

        # ── گام ۲: نوع تعارض بر اساس gap غالب ──
        gaps = {"m_v": gap_mv, "m_s": gap_ms, "s_v": gap_sv}
        dominant = max(gaps, key=gaps.get)

        is_warning = False
        if dominant == "m_v":
            if gap_mv > self.TH_MV_CRISIS:
                conflict_type, type_label = "identity_crisis", "بحران هویت حرفه‌ای"
                is_warning = True
            elif gap_mv > self.TH_MV_GAP:
                conflict_type, type_label = "mv_gap", "شکاف طبیعی انگیزه-ارزش"
            else:
                conflict_type, type_label = "aligned", "همسویی درونی"
        elif dominant == "m_s":
            if gap_ms > self.TH_MS:
                conflict_type, type_label = "path_friction", "کندی مسیر (قابل حل)"
                is_warning = True
            else:
                conflict_type, type_label = "aligned", "همسویی درونی"
        else:  # s_v
            if gap_sv > self.TH_SV:
                conflict_type, type_label = "style_friction", "اصطکاک سبک-ارزش"
                is_warning = True
            else:
                conflict_type, type_label = "aligned", "همسویی درونی"

        # ── گام ۳: هماهنگ‌سازی دوطرفه شدت و نوع ──
        if conflict_type == "aligned":
            # جهت ۱: همسو → برچسب «تعارض» نده
            if index < 0.15:
                severity, severity_label = "very_low", "همسویی درونی بسیار بالا"
            elif index < 0.25:
                severity, severity_label = "low", "همسویی درونی خوب"
            else:
                severity, severity_label = "acceptable", "همسویی درونی قابل قبول"
        else:
            # جهت ۲: تعارض واقعی → حداقل «تعارض خفیف»
            if severity in ("very_low", "low"):
                severity, severity_label = "moderate", "تعارض خفیف"

        return {
            "index": index,
            "severity": severity,
            "severity_label": severity_label,
            "type": conflict_type,
            "type_label": type_label,
            "dominant_gap": dominant,
            "gaps": {k: round(val, 3) for k, val in gaps.items()},
            "weights": {"m_v": self.W_MV, "m_s": self.W_MS, "s_v": self.W_SV},
            "is_warning": is_warning,
            "components": {"m": round(m, 3), "s": round(s, 3), "v": round(v, 3)},
        }

    # ═══════════════════════════════════════════════════════════
    #  شاخص گرادیان صعود (بدون تغییر)
    # ═══════════════════════════════════════════════════════════
    def _compute_gradient_alignment(self, m, s, v):
        values = [m, s, v]
        mean = sum(values) / 3
        if mean == 0:
            return {"index": 0.0, "level": "نامشخص", "interpretation": "داده کافی نیست."}
        std = (sum((x - mean) ** 2 for x in values) / 3) ** 0.5
        cv = std / mean
        index = round(max(0.0, 1.0 - cv), 3)

        if index >= 0.90:
            level = "گرادیان صعود قوی"
        elif index >= 0.75:
            level = "گرادیان صعود خوب"
        elif index >= 0.50:
            level = "گرادیان متوسط"
        else:
            level = "گرادیان ضعیف"

        return {"index": index, "level": level, "mean_alignment": round(mean, 3), "dispersion": round(std, 3)}

    # ═══════════════════════════════════════════════════════════
    #  روایت دانش‌آموزی (بدون تغییر)
    # ═══════════════════════════════════════════════════════════
    def _generate_individuality_insight(self, conflict, gradient):
        ctype = conflict["type"]
        grad = gradient["index"]
        grad_pct = int(grad * 100)

        if ctype == "aligned":
            if grad >= 0.90:
                narrative = (
                    "🐴 تو پتانسیل یک اسب سیاه واقعی را داری! "
                    "هر سه لایهٔ فردیت تو — خرده‌انگیزه‌ها، راهبردها و ارزش‌هایت — در یک راستا هستند. "
                    "درست مثل الگوریتم گرادیان صعود، نیروهای درونی‌ات همدیگر را تقویت می‌کنند "
                    "و با سرعت بیشتری به رضایت و موفقیت می‌رسی. قدر این همسویی را بدان! ✨"
                )
            else:
                narrative = (
                    f"✨ سه لایهٔ فردیت تو همسویی خوبی دارند (همسویی درونی {grad_pct}٪). "
                    "مسیرت هموار است — با اعتماد به نفس ادامه بده! 💪"
                )
            return narrative

        if ctype == "mv_gap":
            narrative = (
                "🔵 خرده‌انگیزه‌های تو بسیار قوی هستند و ارزش‌هایت هم در سطح خوبی قرار دارند، "
                "اما بین این دو کمی فاصله دیده می‌شود. این یک شکاف طبیعی است و جای نگرانی ندارد. "
                "با شناخت بیشتر خودت، این فاصله به‌تدریج کمتر می‌شود. 😊"
            )
        elif ctype == "path_friction":
            narrative = (
                "🟡 خرده‌انگیزه‌ها و ارزش‌های تو با هم همسو هستند، "
                "اما راهبردهای فعلی‌ات کمی با آن‌ها فاصله دارد. "
                "خبر خوب؟ راهبردها پویا هستند — با آزمون و خطا می‌توانی "
                "سبک عملکرد جدیدی یاد بگیری که با انگیزه‌هایت همخوان‌تر باشد. "
                "این تعارض مسیرت را کمی کند می‌کند، اما هرگز متوقف نمی‌کند. 💪"
            )
        elif ctype == "identity_crisis":
            narrative = (
                "⚠️ یک نکتهٔ مهم که ارزش فکر کردن دارد: "
                "خرده‌انگیزه‌ها و ارزش‌های بنیادین تو فاصلهٔ زیادی با هم دارند. "
                "از آنجا که این دو لایه معمولاً در برابر تغییر مقاوم‌اند "
                "(هرچند ممکن است در طول زمان به‌صورت نامحسوس تغییر کنند)، "
                "این فاصله می‌تواند در آینده به بحران هویت حرفه‌ای منجر شود. "
                "پیشنهاد می‌کنیم قبل از انتخاب نهایی، با یک مشاور صحبت کنی. 🤝"
            )
        elif ctype == "style_friction":
            narrative = (
                "🟢 سبک عملکرد تو با ارزش‌هایت فاصله دارد. "
                "چون راهبردها پویا و قابل تنظیم هستند، این فاصله با انتخاب آگاهانهٔ "
                "سبک کاری مناسب کاهش می‌یابد. جای نگرانی نیست! 😊"
            )
        else:
            narrative = ""

        if grad >= 0.75:
            narrative += f" 📈 همسویی درونی تو {grad_pct}٪ است؛ مسیرت نسبتاً هموار خواهد بود."
        elif grad >= 0.50:
            narrative += f" 📈 همسویی درونی تو {grad_pct}٪ است؛ با همسو کردن لایه‌ها، سرعت پیشرفتت بیشتر می‌شود."
        else:
            narrative += f" 📈 همسویی درونی تو {grad_pct}٪ است؛ همسو کردن لایه‌ها کلید رسیدن به رضایت است."
        return narrative

    # ═══════════════════════════════════════════════════════════
    #  متد اصلی
    # ═══════════════════════════════════════════════════════════
    def discover_individuality(self, user_motives, sjt_answers, conjoint_choices):
        result = super().discover_individuality(user_motives, sjt_answers, conjoint_choices)

        for item in result["discovered_majors"]:
            raw = item["individuality_fit"]["raw_components"]
            m, s, v = raw["m_score"] / 100, raw["s_score"] / 100, raw["v_score"] / 100

            conflict = self._compute_internal_conflict(m, s, v)
            gradient = self._compute_gradient_alignment(m, s, v)

            fit = item["individuality_fit"]
            fit["internal_conflict"] = conflict
            fit["gradient_alignment"] = gradient
            fit["individuality_insight"] = self._generate_individuality_insight(conflict, gradient)

        if result["discovered_majors"]:
            top_fit = result["discovered_majors"][0]["individuality_fit"]
            result["summary"]["top_choice_conflict"] = top_fit["internal_conflict"]
            result["summary"]["top_choice_gradient"] = top_fit["gradient_alignment"]
            result["summary"]["top_choice_insight"] = top_fit["individuality_insight"]

        result["method"]["version"] = "2.3.2"
        result["method"]["new_features"] = [
            "internal_conflict_index_weighted (شاخص تعارض وزن‌دار)",
            "two-way severity/type alignment (هماهنگ‌سازی دوطرفه شدت/نوع)",
            "gradient_alignment_index (شاخص گرادیان صعود)",
            "individuality_insight (روایت دانش‌آموزی)",
            "confidence_index (شاخص اطمینان)",
        ]
        return result