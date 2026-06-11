from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from .interpretation_service import dose_scan, fragment_analysis, make_report, medical_summary, pathway_sankey
    from .model_service import APP_ROOT, GENERATED_DIR, get_service
except ImportError:
    from interpretation_service import dose_scan, fragment_analysis, make_report, medical_summary, pathway_sankey
    from model_service import APP_ROOT, GENERATED_DIR, get_service


FRONTEND_DIR = APP_ROOT / "frontend"


class AnalyzeRequest(BaseModel):
    drugA: str = Field(..., min_length=1)
    drugB: str = Field(..., min_length=1)
    cellLine: str = Field(..., min_length=1)
    doseA: float = Field(..., ge=0)
    doseB: float = Field(..., ge=0)
    smilesA: Optional[str] = None
    smilesB: Optional[str] = None
    includeFragments: bool = True
    includePathway: bool = True
    gridSize: int = Field(8, ge=5, le=12)


app = FastAPI(
    title="DecoDoseNet Tumor Combination Therapy Explorer",
    version="1.0.0",
    description="PyTorch + RDKit + VNN explainability system for oncology combination therapy analysis.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GENERATED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(GENERATED_DIR)), name="generated")
app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/styles.css")
def styles():
    return FileResponse(FRONTEND_DIR / "styles.css")


@app.get("/app.js")
def app_js():
    return FileResponse(FRONTEND_DIR / "app.js")


@app.get("/config.js")
def config_js():
    return FileResponse(FRONTEND_DIR / "config.js")


@app.get("/api/health")
def health():
    service = get_service()
    return {
        "status": "ok",
        "device": service.checkpoint_meta["device"],
        "modelEpoch": service.checkpoint_meta.get("epoch"),
        "assets": "loaded",
    }


@app.get("/api/options")
def options():
    try:
        return get_service().options()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    try:
        service = get_service()
        prediction, _, _ = service.predict(
            req.drugA,
            req.drugB,
            req.cellLine,
            req.doseA,
            req.doseB,
            smiles_a=req.smilesA,
            smiles_b=req.smilesB,
        )
        dose = dose_scan(service, req.drugA, req.drugB, req.cellLine, req.doseA, req.doseB, req.gridSize)
        fragments = fragment_analysis(service, req.drugA, req.drugB, req.cellLine, req.doseA, req.doseB) if req.includeFragments else None
        pathway = pathway_sankey(service, req.drugA, req.drugB, req.cellLine, req.doseA, req.doseB) if req.includePathway else None
        warnings = service.warnings_for(req.drugA, req.drugB, req.cellLine, req.doseA, req.doseB, prediction)
        payload = {
            "input": {
                "drugA": req.drugA,
                "drugB": req.drugB,
                "cellLine": req.cellLine,
                "doseA": req.doseA,
                "doseB": req.doseB,
            },
            "prediction": prediction,
            "doseAnalysis": dose,
            "fragmentAnalysis": fragments,
            "pathwayAnalysis": pathway,
            "warnings": warnings,
            "medicalSummary": medical_summary(req.drugA, req.drugB, req.cellLine, req.doseA, req.doseB, prediction, warnings),
        }
        payload["reportUrl"] = make_report(payload)
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def main():
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
