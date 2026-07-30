"""
Dark Horse API V2.1 — با موتور V2 (بدون تعارض، گرادیان و اطمینان)
سازگار با فرانت‌اند (app.js) و سرور رندر
"""

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import List, Dict
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import asyncio

from dark_horse_engine_v2 import DarkHorseEngineV2

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("darkhorse_api")


# ======================= مدل درخواست =======================
class DarkHorseDiscoverRequest(BaseModel):
    micro_motives: List[str] = Field(default_factory=list)
    sjt_answers: Dict[str, str] = Field(default_factory=dict)
    conjoint_choices: Dict[str, str] = Field(default_factory=dict)


# ======================= توابع کمکی =======================
def get_fit_level(score: float) -> str:
    if score >= 80:
        return "همخوانی بسیار بالا"
    elif score >= 60:
        return "همخوانی بالا"
    elif score >= 40:
        return "همخوانی متوسط"
    else:
        return "همخوانی پایین"


def extract_score_from_fit(fit: dict) -> float:
    score = fit.get("score", 0)
    if score == 0:
        raw = fit.get("raw_components", {})
        m = raw.get("m_score", 0) / 100
        s = raw.get("s_score", 0) / 100
        v = raw.get("v_score", 0) / 100
        score = round((0.6 * m + 0.2 * s + 0.2 * v) * 100, 1)
    return score


# ======================= Lifespan =======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Dark Horse API V2 ...")

    # موتور رشته‌های دانشگاهی
    try:
        app.state.engine = DarkHorseEngineV2(
            motives_path="micro_motives.json",
            majors_path="majors_database_v2_final.json",
            trait_map_path="trait_map_v3.json",
            value_poles_path="value_poles_v2.json",
        )
        logger.info("✅ موتور رشته‌ها آماده است.")
    except Exception as e:
        logger.error(f"❌ خطا در موتور رشته‌ها: {e}")
        app.state.engine = None

    # موتور شاخه‌های دبیرستانی
    try:
        app.state.branch_engine = DarkHorseEngineV2(
            motives_path="micro_motives.json",
            majors_path="school_branches_v2.json",
            trait_map_path="trait_map_v3.json",
            value_poles_path="value_poles_v2.json",
        )
        logger.info("✅ موتور شاخه‌ها آماده است.")
    except Exception as e:
        logger.error(f"❌ خطا در موتور شاخه‌ها: {e}")
        app.state.branch_engine = None

    yield
    logger.info("🛑 Shutting down ...")


# ======================= FastAPI App =======================
app = FastAPI(title="Dark Horse API V2", version="2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================= Endpoints =======================
@app.get("/")
async def root():
    return {
        "name": "Dark Horse API V2",
        "engine_version": "2.0",
        "status": "online",
    }


@app.post("/api/v2/darkhorse/discover")
async def discover_v2(request: DarkHorseDiscoverRequest, req: Request):
    engine = req.app.state.engine
    if engine is None:
        raise HTTPException(503, detail="موتور رشته‌ها در دسترس نیست")

    try:
        discovery = await asyncio.to_thread(
            engine.discover_individuality,
            request.micro_motives,
            request.sjt_answers or {},
            request.conjoint_choices or {},
        )

        recommendations = []
        for item in discovery.get("discovered_majors", []):
            fit = item.get("individuality_fit", {})
            score = extract_score_from_fit(fit)
            level = fit.get("level", get_fit_level(score))

            recommendations.append({
                "major_id": item.get("major_id"),
                "major_name_fa": item.get("major_name_fa"),
                "realm_fa": item.get("realm_fa"),
                "fit_score": score,
                "fit_level": level,
                "market_demand_level": fit.get("market_demand_level", 2),
                "raw_components": fit.get("raw_components", {}),
                "evidence": fit.get("evidence", {}),
                "personalized_description": fit.get("personalized_description", ""),
            })

        recommendations.sort(key=lambda x: x["fit_score"], reverse=True)
        summary = discovery.get("summary", {})

        return {
            "session_id": str(uuid.uuid4()),
            "discovery_result": {
                "total_matches": len(recommendations),
                "high_fit_majors": summary.get("high_compatibility", 0),
                "medium_fit_majors": summary.get("medium_compatibility", 0),
                "recommendations": recommendations,
                "method": discovery.get("method", {}),
                "summary": summary,
                "next_step": discovery.get("next_step", ""),
            },
        }
    except Exception:
        logger.error("Error in /api/v2/darkhorse/discover", exc_info=True)
        raise HTTPException(500, detail="خطای داخلی سرور")


@app.post("/api/v2/darkhorse/branch-discovery")
async def branch_discovery_v2(request: DarkHorseDiscoverRequest, req: Request):
    engine = req.app.state.branch_engine
    if engine is None:
        engine = req.app.state.engine
    if engine is None:
        raise HTTPException(503, detail="موتور شاخه‌ها در دسترس نیست")

    try:
        discovery = await asyncio.to_thread(
            engine.discover_individuality,
            request.micro_motives,
            request.sjt_answers or {},
            request.conjoint_choices or {},
        )

        branches = []
        for item in discovery.get("discovered_majors", []):
            fit = item.get("individuality_fit", {})
            score = extract_score_from_fit(fit)
            level = fit.get("level", get_fit_level(score))

            branches.append({
                "branch_id": item.get("major_id"),
                "branch_name_fa": item.get("major_name_fa"),
                "group": item.get("realm_fa"),
                "fit_score": score,
                "fit_level": level,
                "raw_components": fit.get("raw_components", {}),
                "evidence": fit.get("evidence", {}),
                "personalized_description": fit.get("personalized_description", ""),
            })

        branches.sort(key=lambda x: x["fit_score"], reverse=True)

        return {
            "session_id": str(uuid.uuid4()),
            "branch_discovery_result": {
                "total_matches": len(branches),
                "branches": branches,
                "method": discovery.get("method", {}),
                "summary": discovery.get("summary", {}),
            },
        }
    except Exception:
        logger.error("Error in /api/v2/darkhorse/branch-discovery", exc_info=True)
        raise HTTPException(500, detail="خطای داخلی سرور")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_v2:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
