# API 设计

## GET /api/health

返回模型和资产加载状态。

## GET /api/options

返回可选药物、细胞系和示例组合。

## POST /api/analyze

输入：

```json
{
  "drugA": "AZD1775",
  "drugB": "MK-8776",
  "cellLine": "OVCAR3",
  "doseA": 0.2,
  "doseB": 1.15,
  "includeFragments": true,
  "includePathway": true,
  "gridSize": 8
}
```

输出：

```json
{
  "prediction": {
    "final": 0.958,
    "hpb": 0.958,
    "idb": 1.024,
    "theta1": 0.285,
    "theta2": 0.715,
    "epsilon": 0.382,
    "level": "high",
    "confidence": 0.86
  },
  "doseAnalysis": {},
  "fragmentAnalysis": {},
  "pathwayAnalysis": {},
  "warnings": [],
  "medicalSummary": "...",
  "reportUrl": "/generated/reports/analysis_xxx.html"
}
```

## 输出说明

- `prediction.final`：最终预测，来自 HPB 主预测分支。
- `prediction.idb`：机制解释分支预测。
- `theta1/theta2`：药物 A/B 动态贡献权重。
- `epsilon`：剂量依赖交互修正项。
- `doseAnalysis.values`：剂量 A x 剂量 B 的预测热图矩阵。
- `fragmentAnalysis`：RDKit 片段 + ChemBERTa 扰动解释。
- `pathwayAnalysis`：VNN GO 映射的基因-通路-预测桑基图数据。
