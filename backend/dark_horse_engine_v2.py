"""
Dark Horse Engine V2 — نسخه یکپارچه و نهایی
موتور tunggal توصیه رشته/شاخه (جایگزین V2 + V22 + V23)
بدون تعارض درونی، گرادیان صعود و شاخص اطمینان

فرمول اصلی: Total = 0.60×M + 0.20×S + 0.20×V
فیلترها: M ≥ 15% و Total ≥ 30%
"""
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("dark_horse_engine_v2")


class DarkHorseEngineV2:
    """موتور توصیه رشته/شاخه — نسخه یکپارچه"""

    def __init__(
        self,
        motives_path: str = "micro_motives.json",
        majors_path: str = "majors_database_v2_final.json",
        trait_map_path: str = "trait_map_v3.json",
        value_poles_path: str = "value_poles_v2.json",
    ):
        self.motives_map: Dict[str, str] = {}
        self.majors_db: Dict[str, Dict] = {}
        self.trait_map: Dict[str, Dict] = {}
        self.value_poles: Dict[str, str] = {}
        self._load_data(motives_path, majors_path, trait_map_path, value_poles_path)

    @staticmethod
    def _resolve(path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), path)

    def _load_data(self, motives_path, majors_path, trait_map_path, value_poles_path):
        try:
            self.motives_map = self._load_json(motives_path, key_field="code", value_field="description_fa")
            logger.info(f"✅ {len(self.motives_map)} میکروموتیو بارگذاری شد.")
        except Exception as e:
            logger.error(f"خطا در بارگذاری میکروموتیوها: {e}")

        try:
            self.majors_db = self._load_json(majors_path, key_field="id")
            logger.info(f"✅ {len(self.majors_db)} رشته/شاخه بارگذاری شد.")
        except Exception as e:
            logger.error(f"خطا در بارگذاری رشته‌ها: {e}")

        try:
            self.trait_map = self._load_json(trait_map_path)
            logger.info(f"✅ تریت مپ بارگذاری شد ({len(self.trait_map)} کلید).")
        except Exception as e:
            logger.error(f"خطا در بارگذاری تریت مپ: {e}")

        try:
            with open(self._resolve(value_poles_path), "r", encoding="utf-8") as f:
                self.value_poles = json.load(f)
            logger.info(f"✅ value_poles بارگذاری شد ({len(self.value_poles)} قطب).")
        except Exception as e:
            logger.error(f"خطا در بارگذاری value_poles: {e}")

    def _load_json(self, path: str, key_field: Optional[str] = None,
                   value_field: Optional[str] = None) -> Dict:
        full = self._resolve(path)
        with open(full, "r", encoding="utf-8") as f:
            data = json.load(f)
        if key_field and isinstance(data, list):
            if value_field:
                return {item[key_field]: item.get(value_field, "") for item in data if key_field in item}
            return {item[key_field]: item for item in data if key_field in item}
        return data

    # ── M: امتیاز میکروموتیو ──
    def _compute_m_score(self, user_motives: List[str], major_data: Dict) -> Tuple[float, List[Dict]]:
        if not user_motives:
            return 0.0, []
        raw_codes = major_data.get("micro_motive_codes", [])
        if not raw_codes:
            return 0.0, []
        user_set = {str(m).strip().lower() for m in user_motives if m and str(m).strip()}
        major_set = {str(c).strip().lower() for c in raw_codes if c and str(c).strip()}
        matched = user_set & major_set
        if not matched:
            return 0.0, []
        # m_score_denom_limit: حداکثر مخرج برای شاخه‌هایی با کدهای زیاد
        denom_limit = major_data.get("m_score_denom_limit")
        if denom_limit and denom_limit > 0:
            denom = min(len(major_set), denom_limit)
        else:
            denom = len(major_set)
        score = len(matched) / denom * 100 if denom > 0 else 0.0
        evidence = []
        for code in matched:
            orig = next((c for c in raw_codes if str(c).strip().lower() == code), code)
            desc = self.motives_map.get(orig, self.motives_map.get(code.upper(), code))
            evidence.append({"code": orig, "description": desc})
        return round(score, 1), evidence

    # ── S: امتیاز راهبرد — S = (1/25) × Σ(chosen_w / max_w) ──
    def _compute_s_score(self, strategy_answers: List[int],
                         strategy_weights: List[List[float]]) -> Tuple[float, List[Dict]]:
        if not strategy_weights or not strategy_answers:
            return 0.0, []
        total = 0.0
        highlights = []
        n = len(strategy_weights)
        for i, row in enumerate(strategy_weights):
            if i >= len(strategy_answers):
                break
            idx = strategy_answers[i]
            if idx < 0 or idx >= len(row):
                continue
            max_w = max(row)
            if max_w <= 0:
                continue
            chosen_w = row[idx]
            total += chosen_w / max_w
            if chosen_w >= 0.15:
                traits = self.trait_map.get(f"S{i+1:02d}", {}).get(str(idx), [])
                highlights.append({
                    "question": f"S{i+1:02d}",
                    "choice": idx,
                    "weight": round(chosen_w, 3),
                    "traits": traits,
                })
        score = (total / n) * 100 if n else 0.0
        return round(score, 1), highlights

    # ── V: امتیاز ارزش ──
    def _compute_v_score(self, value_choices: List[str],
                         value_weights: Dict[str, float]) -> Tuple[float, List[Dict]]:
        if not value_choices or not value_weights:
            return 0.0, []
        total = 0.0
        count = 0
        highlights = []
        for v in value_choices:
            if not v or not str(v).strip():
                continue
            v = str(v).strip()
            weight = value_weights.get(v, 0.0)
            total += weight
            count += 1
            pole = self.value_poles.get(v, v)
            highlights.append({"pole": v, "label": pole, "weight": round(weight, 3)})
        score = (total / count * 100) if count else 0.0
        return round(score, 1), highlights

    # ── ساخت شواهد ──
    def _build_evidence(self, m_evidence, s_highlights, v_highlights,
                        mis_traits, mis_poles) -> Dict:
        evidence = {"micro_motives_matched": m_evidence}
        if s_highlights:
            evidence["strategy_highlights"] = s_highlights[:5]
        if v_highlights:
            evidence["value_alignment"] = v_highlights[:5]
        if mis_traits:
            evidence["misaligned_traits"] = mis_traits[:5]
        if mis_poles:
            evidence["misaligned_poles"] = mis_poles[:5]
        return evidence

    # ── سطح تناسب ──
    @staticmethod
    def _get_fit_level(score: float) -> str:
        if score >= 80:
            return "همخوانی بسیار بالا"
        elif score >= 60:
            return "همخوانی بالا"
        elif score >= 40:
            return "همخوانی متوسط"
        else:
            return "همخوانی پایین"

    # ── استخراج ویژگی‌های ناهمسو ──
    def _extract_s_misaligned_traits(self, strategy_answers, strategy_weights) -> List[Dict]:
        mis = []
        for i, row in enumerate(strategy_weights):
            if i >= len(strategy_answers):
                break
            idx = strategy_answers[i]
            if idx < 0 or idx >= len(row):
                continue
            max_w = max(row)
            if max_w <= 0:
                continue
            if row[idx] / max_w < 0.4:
                traits = self.trait_map.get(f"S{i+1:02d}", {}).get(str(idx), [])
                mis.append({"question": f"S{i+1:02d}", "traits": traits})
        return mis

    def _extract_v_misaligned_poles(self, value_choices, value_weights) -> List[Dict]:
        mis = []
        for v in value_choices:
            if not v or not str(v).strip():
                continue
            v = str(v).strip()
            user_weight = value_weights.get(v, 0.0)
            opposite = v[:-1] + ("B" if v.endswith("A") else "A")
            opp_weight = value_weights.get(opposite, 0.0)
            if opp_weight > user_weight:
                mis.append({"pole": v, "label": self.value_poles.get(v, v)})
        return mis

    # ── توضیح سناریو ──
    def _generate_scenario_description(self, major_name, m_evidence,
                                       m_score, s_score, v_score) -> str:
        if not m_evidence:
            return ""
        top = m_evidence[0].get("description", "")
        return (
            f"بر اساس خرده‌انگیزه‌هایت، «{major_name}» می‌تواند گزینه مناسبی برایت باشد. "
            f"قوی‌ترین انگیزه‌ات: {top}"
        )

    # ── متد اصلی: کشف فردیت ──
    def discover_individuality(self, user_motives, sjt_answers, conjoint_choices) -> Dict:
        # تبدیل پاسخ‌های SJT (حروف A-E به اعداد 0-4)
        strategy_answers = []
        for i in range(1, 26):
            key = f"sjt_{i}"
            ans = str((sjt_answers or {}).get(key, "")).strip().upper()
            strategy_answers.append(ord(ans) - ord('A') if len(ans) == 1 and 'A' <= ans <= 'E' else -1)

        # تبدیل پاسخ‌های ارزشی
        value_choices = []
        for i in range(1, 16):
            key = f"conj_{i}"
            val = str((conjoint_choices or {}).get(key, "")).strip().upper()
            value_choices.append(val if val.startswith('Q') else "")

        discovered = []
        for major_id, major_data in self.majors_db.items():
            try:
                m_score, m_ev = self._compute_m_score(user_motives or [], major_data)
                if m_score < 15.0:
                    continue

                s_score, s_high = self._compute_s_score(
                    strategy_answers, major_data.get("strategy_weights", [])
                )
                v_score, v_high = self._compute_v_score(
                    value_choices, major_data.get("value_weights", {})
                )

                total = (0.60 * m_score) + (0.20 * s_score) + (0.20 * v_score)
                final_score = round(total, 1)

                if final_score < 30.0:
                    continue

                mis_traits = self._extract_s_misaligned_traits(
                    strategy_answers, major_data.get("strategy_weights", [])
                )
                mis_poles = self._extract_v_misaligned_poles(
                    value_choices, major_data.get("value_weights", {})
                )
                evidence = self._build_evidence(m_ev, s_high, v_high, mis_traits, mis_poles)
                description = self._generate_scenario_description(
                    major_data.get("name", ""), m_ev, m_score, s_score, v_score
                )

                discovered.append({
                    "major_id": major_id,
                    "major_name_fa": major_data.get("name", ""),
                    "realm_fa": major_data.get("group", ""),
                    "cluster": major_data.get("cluster", ""),
                    "individuality_fit": {
                        "score": final_score,
                        "level": self._get_fit_level(final_score),
                        "market_demand_level": major_data.get("market_demand_level", 2),
                        "raw_components": {
                            "m_score": m_score,
                            "s_score": s_score,
                            "v_score": v_score,
                        },
                        "evidence": evidence,
                        "personalized_description": description,
                    },
                })
            except Exception as e:
                logger.error(f"خطا در پردازش رشته {major_id}: {e}")
                continue

        discovered.sort(key=lambda x: x["individuality_fit"]["score"], reverse=True)

        high = sum(1 for d in discovered if d["individuality_fit"]["score"] >= 80)
        med = sum(1 for d in discovered if 60 <= d["individuality_fit"]["score"] < 80)
        low = sum(1 for d in discovered if d["individuality_fit"]["score"] < 60)

        return {
            "discovered_majors": discovered,
            "summary": {
                "total_majors_analyzed": len(self.majors_db),
                "total_matches": len(discovered),
                "high_compatibility": high,
                "medium_compatibility": med,
                "low_compatibility": low,
            },
            "method": {
                "principle": "کشف فردیت — نسخه یکپارچه",
                "scoring": "Total = 0.60×M + 0.20×S + 0.20×V",
                "s_score_formula": "S = (1/25) × Σ(chosen_w / max_w)",
                "filter": "نمایش رشته‌ها با Total ≥ 30% و M ≥ 15%",
                "version": "unified-1.0",
                "trait_map_version": "v3 (چند ویژگی در هر گزینه)",
            },
            "next_step": "لطفاً رشته‌های معرفی‌شده را بررسی کن و گزینه‌های مورد علاقه‌ات را انتخاب کن.",
        }
