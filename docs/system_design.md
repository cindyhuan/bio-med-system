# 系统设计

## 目标

本系统面向肿瘤联合治疗场景，输入药物 A、药物 B、细胞系、剂量 A、剂量 B，输出模型预测、剂量响应、子结构高亮、VNN 通路桑基图、风险提示和可导出报告。

## 架构

```text
frontend/
  index.html     分析工作台
  styles.css     医学科研风格界面
  app.js         输入、API 调用、Canvas 热图、SVG 桑基图

backend/
  app.py                    FastAPI 入口
  model_def.py              从 notebook 提取的 PyTorch 模型结构
  model_service.py          模型权重、数据、ChemBERTa、单点推理
  interpretation_service.py 剂量扫描、子结构、VNN 通路和报告

model_assets/
  best_decodosenet_chemberta2_vnn_article_style.pt
  chemberta2_features_precomputed.csv
  processed_combination_response.csv
  standardized_ONEIL_CELL_LINE_EXPRESSION.csv
  ONEIL_DRUG.csv
  vnn_masks.pt
  vnn_meta.json
  ChemBERTa-77M-MLM/
```

## 数据流

```text
用户输入
  -> POST /api/analyze
  -> ChemBERTa 药物向量 + 细胞表达 + VNN masks
  -> DecoDoseNet PyTorch 模型
  -> final / HPB / IDB / theta / epsilon
  -> 剂量扫描、RDKit 子结构扰动、VNN 梯度归因
  -> 前端图形化展示 + HTML 报告
```

## 可移植性

所有运行时数据都复制到 `model_assets`，后端只使用相对路径。Docker 镜像中包含 Python、PyTorch、FastAPI、Transformers 和 RDKit。

## 注意

系统输出为模型推理和解释分析，不能替代临床试验、药理实验或医生判断。
