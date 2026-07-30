"""
Dark Horse API V2.1 — با موتور V2 (بدون تعارض، گرادیان و اطمینان)
"""

import json
import logging
import os
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel, Field
import asyncio

# ─── تغییر کلیدی: استفاده از موتور V2 ───
from dark_horse_engine_v2 import DarkHorseEngineV2   # ← این خط را اصلاح کنید

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("darkhorse_api_v2")


# ======================= مدل‌های Pydantic =======================
class DarkHorseDiscoverRequest(BaseModel):
    micro_motives: list = Field(default_factory=list)
    sjt_answers: object = Field(default_factory=dict)
    conjoint_choices: object = Field(default_factory=dict)
    strategy_answers: list = Field(default_factory=list)
    value_choices: list = Field(default_factory=list)
    branch: str = None
    exam_group: str = None
    cluster: str = None
    top_n: int = 10

    def get_motives(self) -> list:
        return self.micro_motives or []

    def get_strategy(self) -> list:
        raw = self.strategy_answers if self.strategy_answers else self.sjt_answers
        if not raw:
            return []
        if isinstance(raw, dict):
            result = []
            for i in range(1, 26):
                key = f"S{i:02d}"
                val = raw.get(key, raw.get(str(i), 0))
                result.append(int(val) if val is not None else 0)
            return result
        elif isinstance(raw, list):
            return [int(x) for x in raw]
        return []

    def get_values(self) -> list:
        raw = self.value_choices if self.value_choices else self.conjoint_choices
        if not raw:
            return []
        if isinstance(raw, dict):
            result = []
            for i in range(1, 16):
                key = f"Q{i}"
                val = raw.get(key, raw.get(f"V{i:02d}", ""))
                if val:
                    result.append(str(val))
            return result
        elif isinstance(raw, list):
            return [str(x) for x in raw]
        return []


# ======================= Lifespan =======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Dark Horse API V2.1 (Engine V2) ...")

    # ─── موتور رشته‌های دانشگاهی ───
    try:
        app.state.engine = DarkHorseEngineV2(
            motives_path="micro_motives.json",
            majors_path="majors_database_v2_final.json",
            trait_map_path="trait_map_v3.json",
            value_poles_path="value_poles_v2.json"
        )
        logger.info("✅ DarkHorseEngineV2 (رشته‌ها) آماده است.")
    except Exception as e:
        logger.error(f"❌ Engine init failed: {e}")
        app.state.engine = None

    # ─── موتور شاخه‌های دبیرستانی ───
    try:
        app.state.branch_engine = DarkHorseEngineV2(
            motives_path="micro_motives.json",
            majors_path="school_branches_v2.json",
            trait_map_path="trait_map_v3.json",
            value_poles_path="value_poles_v2.json"
        )
        logger.info("✅ DarkHorseEngineV2 (شاخه‌ها) آماده است.")
    except Exception as e:
        logger.error(f"❌ BranchEngine init failed: {e}")
        app.state.branch_engine = None

    yield
    logger.info("🛑 Shutting down V2.1 ...")


# ======================= FastAPI App =======================
app = FastAPI(title="Dark Horse API V2.1", version="2.1", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ======================= Endpoints =======================
@app.get("/")
async def root():
    return {
        "name": "Dark Horse API V2.1",
        "engine_version": "2.1 (V2)",
        "status": "online",
        "features": [
            "M-Score (خرده‌انگیزه‌ها)",
            "S-Score (راهبردها)",
            "V-Score (ارزش‌ها)",
            "personalized_description",
        ]
    }


@app.post("/api/v2/darkhorse/discover")
async def discover_v2(request: DarkHorseDiscoverRequest, req: Request):
    engine = req.app.state.engine
    if engine is None:
        raise HTTPException(503, detail="موتور V2 در دسترس نیست")

    try:
        discovery = await asyncio.to_thread(
            engine.discover_individuality,
            request.micro_motives,
            request.sjt_answers or {},
            request.conjoint_choices or {}
        )

        recommendations = []
        for item in discovery.get("discovered_majors", []):
            fit = item.get("individuality_fit", {})
            recommendations.append({
                "major_id": item.get("major_id"),
                "major_name_fa": item.get("major_name_fa"),
                "realm_fa": item.get("realm_fa"),
                "fit_score": fit.get("score", 0),
                "fit_level": fit.get("level", ""),
                "market_demand_level": fit.get("market_demand_level", 2),
                "raw_components": fit.get("raw_components", {}),
                "evidence": fit.get("evidence", {}),
                "personalized_description": fit.get("personalized_description", ""),
            })

        recommendations.sort(key=lambda x: x["fit_score"], reverse=True)
        high = sum(1 for r in recommendations if r["fit_score"] >= 80)
        med = sum(1 for r in recommendations if 60 <= r["fit_score"] < 80)

        return {
            "session_id": str(uuid.uuid4()),
            "discovery_result": {
                "total_matches": len(recommendations),
                "high_fit_majors": high,
                "medium_fit_majors": med,
                "recommendations": recommendations,
                "method": discovery.get("method", {}),
                "summary": discovery.get("summary", {}),
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
        raise HTTPException(503, detail="موتور شاخه‌ها در دسترس نیست")

    try:
        discovery = await asyncio.to_thread(
            engine.discover_individuality,
            request.micro_motives,
            request.sjt_answers or {},
            request.conjoint_choices or {}
        )

        branches = []
        for item in discovery.get("discovered_majors", []):
            fit = item.get("individuality_fit", {})
            branches.append({
                "branch_id": item.get("major_id"),
                "branch_name_fa": item.get("major_name_fa"),
                "group": item.get("realm_fa"),
                "fit_score": fit.get("score", 0),
                "fit_level": fit.get("level", ""),
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
