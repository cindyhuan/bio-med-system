import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import torch

try:
    from .model_def import DecoDoseNetChemBERTaVNN
except ImportError:
    from model_def import DecoDoseNetChemBERTaVNN


APP_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = APP_ROOT / "model_assets"
GENERATED_DIR = APP_ROOT / "generated"


def _find_col(df, candidates, required=True):
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    if required:
        raise KeyError(f"Cannot find any of {candidates}. Existing columns: {df.columns.tolist()[:20]}")
    return None


def _safe_float(value, default=0.0):
    try:
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return default
        return value
    except Exception:
        return default


def _unique_sorted(values):
    cleaned = {str(value).strip() for value in values if str(value).strip() and str(value).strip().lower() != "nan"}
    return sorted(cleaned)


class DecoDoseNetService:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.assets = {
            "model": ASSET_DIR / "best_decodosenet_chemberta2_vnn_article_style.pt",
            "combo": ASSET_DIR / "processed_combination_response.csv",
            "drug_info": ASSET_DIR / "ONEIL_DRUG.csv",
            "chemberta_features": ASSET_DIR / "chemberta2_features_precomputed.csv",
            "cell_expr": ASSET_DIR / "standardized_ONEIL_CELL_LINE_EXPRESSION.csv",
            "vnn_masks": ASSET_DIR / "vnn_masks.pt",
            "vnn_meta": ASSET_DIR / "vnn_meta.json",
            "chemberta_model": ASSET_DIR / "ChemBERTa-77M-MLM",
        }
        self._chemberta_tokenizer = None
        self._chemberta_model = None
        self._load_data()
        self._load_model()

    def _load_data(self):
        self.combo_df_raw = pd.read_csv(self.assets["combo"])
        self.drug_info = pd.read_csv(self.assets["drug_info"])
        self.feature_df = pd.read_csv(self.assets["chemberta_features"])
        self.cell_df = pd.read_csv(self.assets["cell_expr"])
        with open(self.assets["vnn_meta"], "r", encoding="utf-8") as f:
            self.vnn_meta = json.load(f)
        self.gene_names = self.vnn_meta["gene_names"]

        feature_cols = [c for c in self.feature_df.columns if c.startswith("feature_")]
        merged = self.drug_info.merge(
            self.feature_df[["PubChem_CID"] + feature_cols],
            on="PubChem_CID",
            how="left",
        )
        self.drug_features = (
            merged[["Name"] + feature_cols]
            .dropna()
            .rename(columns={"Name": "name"})
            .set_index("name")
            .astype(np.float32)
        )
        self.drug_smiles = (
            self.drug_info[["Name", "SMILES"]]
            .dropna()
            .drop_duplicates("Name")
            .set_index("Name")["SMILES"]
            .to_dict()
        )

        cell_col = _find_col(self.cell_df, ["Cell_Line", "cell_line", "CELL_LINE", "cell", "CellLine"])
        missing_genes = [gene for gene in self.gene_names if gene not in self.cell_df.columns]
        if missing_genes:
            raise RuntimeError(f"Cell expression matrix misses VNN genes: {missing_genes[:5]}")
        self.cell_features = (
            self.cell_df[[cell_col] + self.gene_names]
            .rename(columns={cell_col: "Cell_Line"})
            .set_index("Cell_Line")
            .astype(np.float32)
        )

        combo = self.combo_df_raw.copy()
        self.cols = {
            "drug_a": _find_col(combo, ["drugA_name", "DrugA", "drug_a_name", "drug1", "drug_a"]),
            "drug_b": _find_col(combo, ["drugB_name", "DrugB", "drug_b_name", "drug2", "drug_b"]),
            "cell": _find_col(combo, ["cell_line", "Cell_Line", "CELL_LINE", "cell"]),
            "dose_a": _find_col(combo, ["drugA Conc (\u00b5M)", "drugA Conc (碌M)", "drugA Conc (ÂµM)", "drugA_conc", "concA", "doseA"]),
            "dose_b": _find_col(combo, ["drugB Conc (\u00b5M)", "drugB Conc (碌M)", "drugB Conc (ÂµM)", "drugB_conc", "concB", "doseB"]),
            "single_a": _find_col(combo, ["single_resp_1", "single_response_1", "single_A", "single_resp_A"]),
            "single_b": _find_col(combo, ["single_resp_2", "single_response_2", "single_B", "single_resp_B"]),
            "target": _find_col(combo, ["X/X0", "x/x0", "viability", "response", "target", "Y"]),
        }
        for key in ["dose_a", "dose_b", "single_a", "single_b", "target"]:
            combo[self.cols[key]] = pd.to_numeric(combo[self.cols[key]], errors="coerce")
        combo = combo.dropna(subset=list(self.cols.values()))
        combo["inhib_target"] = 1.0 - combo[self.cols["target"]].astype(float)
        combo["inhib_single_a"] = 1.0 - combo[self.cols["single_a"]].astype(float)
        combo["inhib_single_b"] = 1.0 - combo[self.cols["single_b"]].astype(float)
        self.combo_df = combo

    def _load_model(self):
        ckpt = torch.load(self.assets["model"], map_location=self.device, weights_only=False)
        cfg = ckpt.get("config", {})
        self.model = DecoDoseNetChemBERTaVNN(
            drug_feat_dim=int(cfg.get("drug_feat_dim", 384)),
            gene_dim=len(self.gene_names),
            hidden_dim=int(cfg.get("hidden_dim", 256)),
            cell_hidden_dim=int(cfg.get("cell_hidden_dim", 256)),
            vnn_masks_path=str(self.assets["vnn_masks"]),
            dropout=float(cfg.get("dropout", 0.2)),
        ).to(self.device)
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()
        self.checkpoint_meta = {
            "epoch": ckpt.get("epoch"),
            "best_val_metrics": ckpt.get("best_val_metrics", {}),
            "device": str(self.device),
        }

    def _load_chemberta_encoder(self):
        if self._chemberta_model is not None:
            return
        from transformers import AutoModel, AutoTokenizer

        self._chemberta_tokenizer = AutoTokenizer.from_pretrained(str(self.assets["chemberta_model"]))
        self._chemberta_model = AutoModel.from_pretrained(str(self.assets["chemberta_model"]))
        self._chemberta_model = self._chemberta_model.to(self.device)
        self._chemberta_model.eval()

    def encode_smiles(self, smiles):
        self._load_chemberta_encoder()
        tokens = self._chemberta_tokenizer(
            smiles,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        tokens = {k: v.to(self.device) for k, v in tokens.items()}
        with torch.no_grad():
            outputs = self._chemberta_model(**tokens)
            vec = outputs.last_hidden_state[:, 0, :].detach().cpu().numpy()[0].astype(np.float32)
        return vec

    def get_drug_feature(self, drug_name=None, smiles=None):
        if smiles:
            return self.encode_smiles(smiles)
        if drug_name in self.drug_features.index:
            return self.drug_features.loc[drug_name].values.astype(np.float32)
        raise KeyError(f"Drug '{drug_name}' is not available and no SMILES was provided.")

    def estimate_single_response(self, drug, cell_line, dose, role):
        dose = max(float(dose), 0.0)
        c = self.cols
        candidates = []
        if role == "A":
            candidates.append((self.combo_df[c["drug_a"]] == drug, c["dose_a"], "inhib_single_a"))
            candidates.append((self.combo_df[c["drug_b"]] == drug, c["dose_b"], "inhib_single_b"))
        else:
            candidates.append((self.combo_df[c["drug_b"]] == drug, c["dose_b"], "inhib_single_b"))
            candidates.append((self.combo_df[c["drug_a"]] == drug, c["dose_a"], "inhib_single_a"))

        best = None
        for drug_mask, dose_col, response_col in candidates:
            sub = self.combo_df[drug_mask & (self.combo_df[c["cell"]] == cell_line)].copy()
            if sub.empty:
                sub = self.combo_df[drug_mask].copy()
            if sub.empty:
                continue
            sub["_dist"] = (np.log1p(sub[dose_col].astype(float)) - np.log1p(dose)).abs()
            row = sub.sort_values("_dist").iloc[0]
            best = float(row[response_col])
            break
        return float(np.clip(0.0 if best is None else best, 0.0, 1.0))

    def _make_batch(self, drug_a, drug_b, cell_line, dose_a, dose_b, smiles_a=None, smiles_b=None):
        if cell_line not in self.cell_features.index:
            raise KeyError(f"Cell line '{cell_line}' is not available.")
        return {
            "drugA_feat": torch.tensor(self.get_drug_feature(drug_a, smiles_a), dtype=torch.float32, device=self.device).unsqueeze(0),
            "drugB_feat": torch.tensor(self.get_drug_feature(drug_b, smiles_b), dtype=torch.float32, device=self.device).unsqueeze(0),
            "cell_expr": torch.tensor(self.cell_features.loc[cell_line].values, dtype=torch.float32, device=self.device).unsqueeze(0),
            "drugA_logconc": torch.tensor([np.log1p(max(float(dose_a), 0.0))], dtype=torch.float32, device=self.device),
            "drugB_logconc": torch.tensor([np.log1p(max(float(dose_b), 0.0))], dtype=torch.float32, device=self.device),
            "single_resp_1": torch.tensor([self.estimate_single_response(drug_a, cell_line, dose_a, "A")], dtype=torch.float32, device=self.device),
            "single_resp_2": torch.tensor([self.estimate_single_response(drug_b, cell_line, dose_b, "B")], dtype=torch.float32, device=self.device),
        }

    def predict(self, drug_a, drug_b, cell_line, dose_a, dose_b, smiles_a=None, smiles_b=None, keep_grad=False):
        batch = self._make_batch(drug_a, drug_b, cell_line, dose_a, dose_b, smiles_a, smiles_b)
        runner = torch.enable_grad() if keep_grad else torch.no_grad()
        with runner:
            outputs = self.model(**batch)
        result = {
            "final": float(outputs["final_pred"].detach().cpu()[0]),
            "hpb": float(outputs["hpb_pred"].detach().cpu()[0]),
            "idb": float(outputs["idb_pred"].detach().cpu()[0]),
            "theta1": float(outputs["theta1"].detach().cpu()[0]),
            "theta2": float(outputs["theta2"].detach().cpu()[0]),
            "epsilon": float(outputs["epsilon"].detach().cpu()[0]),
            "singleA": float(batch["single_resp_1"].detach().cpu()[0]),
            "singleB": float(batch["single_resp_2"].detach().cpu()[0]),
        }
        result["level"] = self.response_level(result["final"])
        result["confidence"] = self.estimate_confidence(drug_a, drug_b, cell_line, dose_a, dose_b)
        return result, batch, outputs

    def response_level(self, value):
        if value >= 0.75:
            return "high"
        if value >= 0.45:
            return "medium"
        return "low"

    def dose_ranges(self, drug_a, drug_b, cell_line=None):
        c = self.cols
        sub = self.combo_df[(self.combo_df[c["drug_a"]] == drug_a) & (self.combo_df[c["drug_b"]] == drug_b)]
        if cell_line:
            scoped = sub[sub[c["cell"]] == cell_line]
            if not scoped.empty:
                sub = scoped
        if sub.empty:
            sub = self.combo_df[(self.combo_df[c["drug_a"]] == drug_a) | (self.combo_df[c["drug_b"]] == drug_b)]
        if sub.empty:
            return {"doseA": [0.001, 10.0], "doseB": [0.001, 10.0]}
        return {
            "doseA": [float(max(sub[c["dose_a"]].min(), 0.0)), float(max(sub[c["dose_a"]].max(), 0.001))],
            "doseB": [float(max(sub[c["dose_b"]].min(), 0.0)), float(max(sub[c["dose_b"]].max(), 0.001))],
        }

    def estimate_confidence(self, drug_a, drug_b, cell_line, dose_a, dose_b):
        c = self.cols
        score = 0.55
        if drug_a in self.drug_features.index:
            score += 0.12
        if drug_b in self.drug_features.index:
            score += 0.12
        if cell_line in self.cell_features.index:
            score += 0.10
        ranges = self.dose_ranges(drug_a, drug_b, cell_line)
        score += 0.06 if ranges["doseA"][0] <= float(dose_a) <= ranges["doseA"][1] else -0.12
        score += 0.06 if ranges["doseB"][0] <= float(dose_b) <= ranges["doseB"][1] else -0.12
        pair_seen = not self.combo_df[
            (self.combo_df[c["drug_a"]] == drug_a)
            & (self.combo_df[c["drug_b"]] == drug_b)
            & (self.combo_df[c["cell"]] == cell_line)
        ].empty
        score += 0.09 if pair_seen else -0.05
        return float(np.clip(score, 0.05, 0.98))

    def options(self):
        c = self.cols
        combo_drugs = set(_unique_sorted(self.combo_df[c["drug_a"]])).union(_unique_sorted(self.combo_df[c["drug_b"]]))
        combo_cells = set(_unique_sorted(self.combo_df[c["cell"]]))
        model_drugs = combo_drugs & set(self.drug_features.index.astype(str))
        model_cells = combo_cells & set(self.cell_features.index.astype(str))
        pairs = self.combo_df[[c["drug_a"], c["drug_b"], c["cell"], c["dose_a"], c["dose_b"]]].head(30)
        examples = []
        for _, row in pairs.iterrows():
            if str(row[c["drug_a"]]) not in model_drugs or str(row[c["drug_b"]]) not in model_drugs:
                continue
            if str(row[c["cell"]]) not in model_cells:
                continue
            examples.append(
                {
                    "drugA": str(row[c["drug_a"]]),
                    "drugB": str(row[c["drug_b"]]),
                    "cellLine": str(row[c["cell"]]),
                    "doseA": _safe_float(row[c["dose_a"]]),
                    "doseB": _safe_float(row[c["dose_b"]]),
                }
            )
        return {
            "drugs": sorted(combo_drugs),
            "cellLines": sorted(combo_cells),
            "examples": examples,
            "model": self.checkpoint_meta,
        }

    def warnings_for(self, drug_a, drug_b, cell_line, dose_a, dose_b, prediction):
        warnings = []
        ranges = self.dose_ranges(drug_a, drug_b, cell_line)
        if drug_a == drug_b:
            warnings.append({"level": "danger", "title": "药物重复", "message": "药物 A 与药物 B 相同，联合用药解释不成立。"})
        if dose_a < ranges["doseA"][0] or dose_a > ranges["doseA"][1]:
            warnings.append({"level": "warning", "title": "剂量A外推", "message": "剂量 A 超出该组合/细胞系训练数据范围，数据覆盖可信度降低。"})
        if dose_b < ranges["doseB"][0] or dose_b > ranges["doseB"][1]:
            warnings.append({"level": "warning", "title": "剂量B外推", "message": "剂量 B 超出该组合/细胞系训练数据范围，数据覆盖可信度降低。"})
        if prediction["confidence"] < 0.55:
            warnings.append({"level": "warning", "title": "数据覆盖不足", "message": "模型数据覆盖度较低，建议谨慎作为候选组合筛选参考。"})
        if abs(prediction["hpb"] - prediction["idb"]) > 0.25:
            warnings.append({"level": "warning", "title": "预测差异提示", "message": "综合响应评分与机制解释分支差异较大，机制解释需要谨慎。"})
        if abs(prediction["epsilon"]) > 0.25:
            warnings.append({"level": "notice", "title": "剂量交互增强", "message": "剂量交互效应较高，提示当前剂量组合可能是重要驱动因素。"})
        warnings.append({"level": "info", "title": "科研用途", "message": "本系统仅用于科研分析、候选组合筛选和机制假设生成，不构成临床诊疗建议。所有预测结果需经独立实验验证。"})
        return warnings


@lru_cache(maxsize=1)
def get_service():
    return DecoDoseNetService()
