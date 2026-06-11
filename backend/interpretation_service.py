import hashlib
from html import escape

import numpy as np

try:
    from .drug_reference_map import get_drug_medical_support
    from .model_service import GENERATED_DIR
except ImportError:
    from drug_reference_map import get_drug_medical_support
    from model_service import GENERATED_DIR


def _round(value, digits=4):
    try:
        return round(float(value), digits)
    except Exception:
        return 0.0


def medical_summary(drug_a, drug_b, cell_line, dose_a, dose_b, prediction, warnings=None):
    level_map = {"high": "高响应", "medium": "中等响应", "low": "低响应"}
    level = level_map.get(prediction["level"], "不确定")
    theta_a = float(prediction["theta1"])
    theta_b = float(prediction["theta2"])
    epsilon = float(prediction["epsilon"])
    confidence = float(prediction.get("confidence", 0.0))
    warnings = warnings or []

    if abs(theta_a - theta_b) < 0.08:
        contribution_text = "两种药物的影响权重较为接近"
    else:
        higher_drug = "药物 A" if theta_a > theta_b else "药物 B"
        contribution_text = f"{higher_drug} 的影响权重相对更高"

    abs_epsilon = abs(epsilon)
    if abs_epsilon >= 0.25:
        direction = "增强预测响应" if epsilon > 0 else "降低预测响应"
        dose_text = f"剂量交互效应较高，提示当前剂量组合可能存在较明显的双药剂量依赖交互影响，方向表现为{direction}"
    elif abs_epsilon >= 0.10:
        dose_text = "剂量交互效应处于中等水平，提示剂量组合可能对预测结果产生一定影响"
    else:
        dose_text = "剂量交互效应较低，当前预测主要由两药基础作用和细胞背景共同影响"

    warning_titles = {warning.get("title") for warning in warnings}
    has_dose_extrapolation = bool({"剂量A外推", "剂量B外推"} & warning_titles)
    has_low_coverage = confidence < 0.55 or "数据覆盖不足" in warning_titles
    if has_dose_extrapolation:
        research_advice = "由于当前剂量超出训练数据覆盖范围，该结果仅可作为外推参考，不建议直接作为实验优先依据"
    elif has_low_coverage:
        research_advice = "由于模型对当前药物、细胞系或剂量条件的数据覆盖不足，该结果应谨慎解读，建议优先选择数据覆盖更充分的组合"
    elif prediction["level"] == "high":
        research_advice = "该结果提示该组合具有较高的后续体外实验验证价值，可作为优先候选组合关注"
    elif prediction["level"] == "medium":
        research_advice = "该结果可作为后续体外实验验证的候选组合筛选参考，建议结合实验成本和研究目标进一步评估"
    else:
        research_advice = "该结果提示当前剂量组合的预测抑制效果有限，暂不建议作为优先验证组合，可考虑调整剂量或更换组合后再评估"

    return (
        f"当前药物组合在 {cell_line} 细胞系和给定剂量条件下预测为{level}。"
        f"模型结果显示，药物 A 与药物 B 对当前预测均有贡献，其中{contribution_text}。"
        f"{dose_text}。{research_advice}。"
        "本系统仅用于科研分析、候选组合筛选和机制假设生成，不构成临床诊疗建议。所有预测结果需经独立实验验证。"
    )


def dose_scan(service, drug_a, drug_b, cell_line, dose_a, dose_b, grid_size=8):
    ranges = service.dose_ranges(drug_a, drug_b, cell_line)
    min_a, max_a = ranges["doseA"]
    min_b, max_b = ranges["doseB"]
    min_a = max(min_a, 1e-4)
    min_b = max(min_b, 1e-4)
    max_a = max(max_a, min_a * 1.2)
    max_b = max(max_b, min_b * 1.2)
    axis_a = np.geomspace(min_a, max_a, grid_size)
    axis_b = np.geomspace(min_b, max_b, grid_size)
    values = []
    best = {"doseA": None, "doseB": None, "prediction": -1.0}
    low_dose_best = {"doseA": None, "doseB": None, "prediction": -1.0, "doseBurden": None}
    high_response_threshold = 0.65
    high_response_count = 0
    for b in axis_b:
        row = []
        for a in axis_a:
            pred, _, _ = service.predict(drug_a, drug_b, cell_line, float(a), float(b))
            val = float(pred["final"])
            row.append(_round(val))
            if val >= high_response_threshold:
                high_response_count += 1
            burden = (float(a) / max_a + float(b) / max_b) / 2
            if val > best["prediction"]:
                best = {"doseA": float(a), "doseB": float(b), "prediction": val}
            if val >= high_response_threshold and burden < (low_dose_best["doseBurden"] or 99):
                low_dose_best = {"doseA": float(a), "doseB": float(b), "prediction": val, "doseBurden": burden}
        values.append(row)
    current = service.predict(drug_a, drug_b, cell_line, dose_a, dose_b)[0]
    improvement = float(best["prediction"] - current["final"])
    trend = "随剂量升高出现增强趋势" if improvement > 0.08 else "当前剂量接近预测响应平台"
    total_points = max(1, grid_size * grid_size)
    high_ratio = high_response_count / total_points
    if current["final"] >= high_response_threshold:
        conclusion = "当前输入剂量已处于较高预测响应区间，可结合实验可操作性和后续验证成本进一步评估。"
    elif improvement > 0.12:
        conclusion = "当前输入剂量与扫描范围内预测响应最高点仍有差距，模型提示可在训练数据覆盖范围内进一步探索剂量优化。"
    elif high_response_count > 0:
        conclusion = "热图中存在局部高响应候选区域，但当前剂量点不在预测响应较高区域，建议围绕高响应候选区域进行小范围验证。"
    else:
        conclusion = "当前扫描范围内未出现明显高响应候选区域，该组合在该细胞背景下可优先作为低响应参考。"
    return {
        "axisA": [_round(x, 5) for x in axis_a],
        "axisB": [_round(x, 5) for x in axis_b],
        "values": values,
        "current": {"doseA": float(dose_a), "doseB": float(dose_b), "prediction": _round(current["final"])},
        "best": {k: _round(v, 5) if isinstance(v, float) else v for k, v in best.items()},
        "lowDoseCandidate": {k: _round(v, 5) if isinstance(v, float) else v for k, v in low_dose_best.items()},
        "threshold": high_response_threshold,
        "highResponseCount": high_response_count,
        "highResponseRatio": _round(high_ratio),
        "improvement": _round(improvement),
        "conclusion": conclusion,
        "summary": f"剂量扫描显示该组合{trend}。热图中亮色区域代表预测抑制响应更高，当前剂量点和扫描范围内预测响应最高点已在图中标记。",
    }


def _mix_rgb(light, dark, strength):
    strength = max(0.0, min(1.0, float(strength or 0.0)))
    return tuple(light[i] + (dark[i] - light[i]) * strength for i in range(3))


def _fragment_rgb(direction, strength=1.0):
    if direction == "negative":
        return _mix_rgb((0.58, 0.75, 0.98), (0.08, 0.26, 0.78), strength)
    return _mix_rgb((0.98, 0.64, 0.64), (0.72, 0.06, 0.12), strength)


def _rgb_hex(color):
    return "#{:02X}{:02X}{:02X}".format(*(int(max(0, min(1, channel)) * 255) for channel in color))


def _apply_highlight_opacity(svg, highlight_fragments):
    import re

    color_opacity = {}
    for fragment in highlight_fragments or []:
        color = _fragment_rgb(fragment.get("direction"), fragment.get("strength", 1.0))
        color_hex = _rgb_hex(color)
        strength = max(0.0, min(1.0, float(fragment.get("strength") or 0.0)))
        color_opacity[color_hex] = max(color_opacity.get(color_hex, 0.0), 0.22 + 0.30 * strength)

    for color_hex, opacity in color_opacity.items():
        element_pattern = rf"(<(?:path|ellipse)[^>]*style='[^']*(?:fill|stroke):{re.escape(color_hex)}[^']*')"

        def update_style(match):
            element = match.group(1)
            if "fill-opacity:" in element:
                element = re.sub(r"fill-opacity:[0-9.]+", f"fill-opacity:{opacity:.2f}", element)
            elif f"fill:{color_hex};" in element:
                element = element.replace(f"fill:{color_hex};", f"fill:{color_hex};fill-opacity:{opacity:.2f};")
            element = re.sub(r"stroke-opacity:[0-9.]+", f"stroke-opacity:{opacity:.2f}", element)
            return element

        svg = re.sub(element_pattern, update_style, svg)
    return svg


def _drug_svg(smiles, highlight_fragments=None, legend=""):
    from rdkit import Chem
    from rdkit.Chem import Draw

    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return ""
    drawer = Draw.MolDraw2DSVG(560, 340)
    opts = drawer.drawOptions()
    opts.addAtomIndices = False
    opts.legendFontSize = 16

    highlight_atoms = []
    highlight_bonds = []
    atom_colors = {}
    bond_colors = {}

    for fragment in highlight_fragments or []:
        atoms = [int(i) for i in fragment.get("atoms", [])]
        if not atoms:
            continue
        color = _fragment_rgb(fragment.get("direction"), fragment.get("strength", 1.0))

        for atom in atoms:
            if atom not in highlight_atoms:
                highlight_atoms.append(atom)
            atom_colors[atom] = color

        atom_set = set(atoms)
        for bond in mol.GetBonds():
            if bond.GetBeginAtomIdx() in atom_set and bond.GetEndAtomIdx() in atom_set:
                bond_idx = bond.GetIdx()
                if bond_idx not in highlight_bonds:
                    highlight_bonds.append(bond_idx)
                bond_colors[bond_idx] = color
    drawer.DrawMolecule(
        mol,
        highlightAtoms=highlight_atoms,
        highlightAtomColors=atom_colors,
        highlightBonds=highlight_bonds,
        highlightBondColors=bond_colors,
        legend=legend,
    )
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText().replace("svg:", "")
    return _apply_highlight_opacity(svg, highlight_fragments)


def _fragment_atom_sets(smiles):
    from rdkit import Chem
    from rdkit.Chem import BRICS

    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return []
    bonds = list(BRICS.FindBRICSBonds(mol))
    atom_sets = []
    seen = set()

    def add_atom_set(atoms):
        atoms = tuple(sorted(set(int(x) for x in atoms)))
        if len(atoms) <= 1 or len(atoms) >= mol.GetNumAtoms() or atoms in seen:
            return
        seen.add(atoms)
        atom_sets.append(list(atoms))

    if bonds:
        cut_bonds = []
        for (a1, a2), _labels in bonds[:8]:
            bond = mol.GetBondBetweenAtoms(int(a1), int(a2))
            if bond is not None:
                cut_bonds.append(bond.GetIdx())
        fragmented = Chem.FragmentOnBonds(mol, cut_bonds, addDummies=False)
        for frag in Chem.GetMolFrags(fragmented, asMols=False, sanitizeFrags=False):
            add_atom_set(frag)
    for ring in mol.GetRingInfo().AtomRings():
        add_atom_set(ring)
    for atom in mol.GetAtoms():
        neighborhood = [atom.GetIdx()] + [neighbor.GetIdx() for neighbor in atom.GetNeighbors()]
        add_atom_set(neighborhood)
    for bond in mol.GetBonds():
        add_atom_set([bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()])
    if not atom_sets:
        atom_sets = [[i] for i in range(min(6, mol.GetNumAtoms()))]
    return atom_sets[:12]


def _remove_atoms_smiles(smiles, atoms):
    from rdkit import Chem

    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return None
    rw = Chem.RWMol(mol)
    for idx in sorted(set(int(i) for i in atoms), reverse=True):
        if idx < rw.GetNumAtoms():
            rw.RemoveAtom(idx)
    try:
        new_mol = rw.GetMol()
        Chem.SanitizeMol(new_mol)
        return Chem.MolToSmiles(new_mol)
    except Exception:
        return None


def fragment_analysis(service, drug_a, drug_b, cell_line, dose_a, dose_b):
    baseline = service.predict(drug_a, drug_b, cell_line, dose_a, dose_b)[0]["final"]
    analyses = []
    for tag, target, other in [("drugA", drug_a, drug_b), ("drugB", drug_b, drug_a)]:
        smiles = service.drug_smiles.get(target, "")
        fragments = []
        for idx, atoms in enumerate(_fragment_atom_sets(smiles)):
            perturbed = _remove_atoms_smiles(smiles, atoms)
            score = 0.0
            if perturbed:
                try:
                    if tag == "drugA":
                        pred = service.predict(target, other, cell_line, dose_a, dose_b, smiles_a=perturbed)[0]
                    else:
                        pred = service.predict(other, target, cell_line, dose_a, dose_b, smiles_b=perturbed)[0]
                    score = baseline - pred["final"]
                except Exception:
                    score = 0.0
            fragments.append(
                {
                    "id": idx + 1,
                    "atoms": atoms,
                    "perturbedSmiles": perturbed,
                    "importance": _round(score),
                    "absImportance": _round(abs(score)),
                    "direction": "positive" if score >= 0 else "negative",
                }
            )
        fragments = sorted(fragments, key=lambda x: x["absImportance"], reverse=True)
        max_abs = max((float(item["absImportance"]) for item in fragments), default=0.001) or 0.001
        for rank, item in enumerate(fragments, start=1):
            item["rank"] = rank
            item["label"] = f"P{rank}"
            item["strength"] = _round(min(1.0, float(item["absImportance"]) / max_abs), 3)
        significant_fragments = [item for item in fragments if float(item.get("absImportance") or 0) >= 0.001]
        top_fragments = significant_fragments[:3]
        medical_support = get_drug_medical_support(target)
        analyses.append(
            {
                "tag": tag,
                "drug": target,
                "smiles": smiles,
                "svg": _drug_svg(smiles, top_fragments, f"{target} 预测敏感子结构"),
                "fragments": fragments,
                "summary": medical_support["mechanism"],
                "medicalSupport": medical_support,
            }
        )
    return {
        "baseline": _round(baseline),
        "method": "RDKit BRICS/ring fragments + ChemBERTa local encoder perturbation",
        "note": "片段扰动为模型解释，不等同于已实验验证药效团。",
        "drugs": analyses,
    }


def _pathway_category(name):
    text = (name or "").lower()
    rules = [
        ("转录调控", "与基因表达、RNA polymerase 或转录调控相关，可能反映细胞状态重编程。", ["transcription", "rna polymerase", "gene expression"]),
        ("缺氧应答", "与缺氧、氧感知或应激适应相关，可作为肿瘤细胞压力反应的机制假设。", ["hypoxia", "oxygen", "hif"]),
        ("血管生成", "与血管生成或血管发育相关，可能提示微环境适应相关信号。", ["angiogenesis", "blood vessel", "vascular", "vasculature"]),
        ("凋亡调控", "与凋亡或细胞死亡调控相关，可能影响药物诱导的细胞损伤响应。", ["apopt", "cell death"]),
        ("细胞迁移", "与细胞迁移、运动或侵袭相关，需结合肿瘤类型和具体基因进一步解释。", ["migration", "motility", "invasion"]),
        ("细胞周期与增殖", "与细胞周期、分裂或增殖相关，可能反映抗癌药物对增殖程序的影响。", ["cell cycle", "mitotic", "proliferation", "division"]),
        ("免疫/炎症相关", "与免疫或炎症过程相关，需结合细胞系和实验体系判断其生物学含义。", ["immune", "inflammatory", "cytokine", "interferon"]),
        ("发育相关过程", "属于发育类 GO 术语，可能来自共享调控网络，需结合具体基因和实验背景谨慎解释。", ["development", "embryonic", "neuron", "morphogenesis", "differentiation"]),
    ]
    for category, interpretation, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return category, interpretation
    return "相关生物过程", "该 GO 术语为模型归因得到的高贡献节点，需结合具体基因和实验背景解释。"


def _mechanism_summary(pathways):
    if not pathways:
        return "当前样本未形成稳定的 Top 通路归因结果，机制解释应谨慎参考。"
    categories = []
    for item in pathways:
        category = item.get("categoryZh", "相关生物过程")
        if category not in categories:
            categories.append(category)
    main_categories = [category for category in categories if category != "发育相关过程"][:3]
    if not main_categories:
        main_categories = categories[:3]
    category_text = "、".join(main_categories)
    dev_note = "同时也出现部分发育相关 GO 术语，相关解释需结合具体基因和实验背景进一步验证。" if "发育相关过程" in categories else ""
    tumor_hint_terms = [c for c in categories if c in {"转录调控", "缺氧应答", "血管生成", "凋亡调控", "细胞迁移", "细胞周期与增殖"}]
    if tumor_hint_terms:
        signal_text = "、".join(tumor_hint_terms[:3])
        signal_sentence = f"这些结果提示模型可能捕获到与{signal_text}相关的肿瘤细胞状态或微环境适应信号。"
    else:
        signal_sentence = "这些结果提示模型可能捕获到与当前细胞背景相关的调控信号。"
    return (
        f"VNN 结果显示，当前预测的高贡献节点主要集中在{category_text}相关过程。"
        f"{dev_note}{signal_sentence}该解释为模型生成的机制假设，需要进一步实验验证。"
    )


def pathway_sankey(service, drug_a, drug_b, cell_line, dose_a, dose_b):
    batch = service._make_batch(drug_a, drug_b, cell_line, dose_a, dose_b)
    batch["cell_expr"].requires_grad_(True)
    service.model.zero_grad(set_to_none=True)
    outputs = service.model(**batch)
    outputs["final_pred"].sum().backward()
    expr = batch["cell_expr"].detach().cpu().numpy()[0]
    grad = batch["cell_expr"].grad.detach().cpu().numpy()[0]
    scores = np.abs(expr * grad)
    top_idx = np.argsort(scores)[::-1][:10]
    top_genes = [{"gene": service.gene_names[i], "score": _round(scores[i], 6)} for i in top_idx]
    gene_to_go = service.vnn_meta.get("gene_to_go_terms", {})
    go_names = service.vnn_meta.get("go_name_map", {})
    go_scores = {}
    go_gene_links = []
    for item in top_genes:
        for term in gene_to_go.get(item["gene"], [])[:8]:
            go_scores[term] = go_scores.get(term, 0.0) + item["score"]
            go_gene_links.append((item["gene"], term, item["score"]))
    top_terms = sorted(go_scores.items(), key=lambda x: x[1], reverse=True)[:8]
    top_term_ids = {term for term, _ in top_terms}
    nodes = []
    links = []
    for item in top_genes[:8]:
        nodes.append({"id": item["gene"], "label": item["gene"], "type": "gene"})
    for term, score in top_terms:
        nodes.append({"id": term, "label": go_names.get(term, term), "type": "pathway", "score": _round(score, 6)})
    nodes.append({"id": "prediction", "label": "预测响应", "type": "prediction"})
    for gene, term, score in go_gene_links:
        if term in top_term_ids and any(n["id"] == gene for n in nodes):
            links.append({"source": gene, "target": term, "value": max(_round(score, 6), 0.0001)})
    for term, score in top_terms:
        links.append({"source": term, "target": "prediction", "value": max(_round(score, 6), 0.0001)})
    top_pathways = []
    for term, score in top_terms:
        name = go_names.get(term, term)
        category, interpretation = _pathway_category(name)
        top_pathways.append(
            {
                "goId": term,
                "name": name,
                "score": _round(score, 6),
                "categoryZh": category,
                "interpretation": interpretation,
            }
        )
    mechanism_summary = _mechanism_summary(top_pathways)
    return {
        "genes": top_genes,
        "pathways": top_pathways,
        "nodes": nodes,
        "links": links,
        "summary": "VNN 通路解释基于细胞表达梯度归因，并映射到 GO 层级节点。桑基图展示 Top 基因经由主要通路流向模型预测响应的贡献路径。",
        "mechanismSummary": mechanism_summary,
    }


def _html_text(value):
    return escape(str(value if value is not None else ""))


def _metric(label, value, digits=4):
    try:
        text = f"{float(value):.{digits}f}"
    except Exception:
        text = "--"
    return f"<div class='metric'><span>{_html_text(label)}</span><b>{text}</b></div>"


def make_report(payload):
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    report_dir = GENERATED_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(repr(payload).encode("utf-8")).hexdigest()[:10]
    path = report_dir / f"analysis_{key}.html"

    pred = payload["prediction"]
    input_data = payload["input"]
    dose = payload.get("doseAnalysis") or {}
    pathway = payload.get("pathwayAnalysis") or {}
    fragments = payload.get("fragmentAnalysis") or {}
    warnings = payload.get("warnings") or []

    warning_html = "".join(
        f"<li><b>{_html_text(item.get('title'))}</b>：{_html_text(item.get('message'))}</li>"
        for item in warnings
    ) or "<li>暂无额外风险提示。</li>"

    dose_html = f"""
      <p>{_html_text(dose.get('summary', '未生成剂量响应分析。'))}</p>
      <p><b>当前剂量预测响应：</b>{_html_text((dose.get('current') or {}).get('prediction', '--'))}</p>
      <p><b>扫描范围内预测响应最高点：</b>A={_html_text((dose.get('best') or {}).get('doseA', '--'))} uM，
      B={_html_text((dose.get('best') or {}).get('doseB', '--'))} uM，
      预测响应={_html_text((dose.get('best') or {}).get('prediction', '--'))}</p>
      <p><b>高响应候选点数量：</b>{_html_text(dose.get('highResponseCount', '--'))} 个剂量点
      （预测响应 ≥ {_html_text(dose.get('threshold', 0.65))}）。该阈值仅用于模型候选区域展示，不代表临床疗效判断标准。</p>
      <p><b>剂量结论：</b>{_html_text(dose.get('conclusion', '暂无剂量结论。'))}</p>
    """

    pathway_rows = "".join(
        f"<tr><td>{_html_text(item.get('name'))}</td><td>{_html_text(item.get('categoryZh'))}</td><td>{_html_text(item.get('interpretation'))}</td><td>{_html_text(item.get('score'))}</td></tr>"
        for item in (pathway.get("pathways") or [])[:8]
    ) or "<tr><td colspan='4'>未生成通路机制分析。</td></tr>"
    pathway_html = f"""
      <p>{_html_text(pathway.get('mechanismSummary', pathway.get('summary', '未生成通路机制分析。')))}</p>
      <table><thead><tr><th>Top GO 术语</th><th>中文类别</th><th>解释提示</th><th>贡献分数</th></tr></thead><tbody>{pathway_rows}</tbody></table>
    """

    fragment_cards = []
    for drug in fragments.get("drugs") or []:
        display_fragments = [
            frag for frag in (drug.get("fragments") or [])
            if float(frag.get("absImportance") or 0) >= 0.001
        ][:3]
        rows = "".join(
            f"<tr><td>敏感片段 {idx}</td><td>{_html_text(frag.get('importance'))}</td><td>{_html_text(frag.get('direction'))}</td></tr>"
            for idx, frag in enumerate(display_fragments, start=1)
        ) or "<tr><td colspan='3'>未检测到绝对扰动影响不为 0 的敏感片段。</td></tr>"
        svg = drug.get("svg") or ""
        support = drug.get("medicalSupport") or {}
        support_refs = "".join(
            f"<li><a href='{_html_text(ref.get('url'))}'>{_html_text(ref.get('label'))}</a></li>"
            for ref in support.get("references", [])
        ) or "<li>暂无可展示参考依据。</li>"
        support_levels = "；".join(
            f"{_html_text(item.get('label'))}：{_html_text(item.get('value'))}"
            for item in support.get("levels", [])
        )
        support_targets = "、".join(_html_text(target) for target in support.get("targets", [])) or "暂无靶点说明"
        fragment_cards.append(
            f"""
            <div class='fragment-card'>
              <h3>{_html_text(drug.get('drug'))}</h3>
              <div class='mol'>{svg}</div>
              <table><thead><tr><th>片段</th><th>贡献分数</th><th>方向</th></tr></thead><tbody>{rows}</tbody></table>
              <p><b>医学支持说明：</b>{_html_text(support.get('mechanism', drug.get('summary')))}</p>
              <p><b>主要靶点：</b>{support_targets}</p>
              <p><b>证据边界与参考依据：</b>{_html_text(support.get('boundary'))}</p>
              <p><b>证据等级：</b>{support_levels}</p>
              <ul>{support_refs}</ul>
            </div>
            """
        )
    fragment_html = "".join(fragment_cards) or "<p>未生成结构贡献结果。</p>"

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DecoDoseNet 肿瘤联合治疗剂量-机制解释报告</title>
  <style>
    :root {{
      --bg:#eef3f7; --panel:#fff; --ink:#102033; --muted:#64748b; --line:#d7e2ea;
      --navy:#0b2540; --teal:#0f766e; --amber:#d97706; --red:#dc2626;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font-family:Arial,'Microsoft YaHei',sans-serif; line-height:1.7; }}
    header {{ padding:28px 36px; color:white; background:linear-gradient(120deg,var(--navy),#12385c 58%,var(--teal)); }}
    h1 {{ margin:0 0 8px; font-size:28px; }}
    h2 {{ margin:0 0 14px; color:var(--navy); font-size:20px; }}
    h3 {{ margin:0 0 8px; color:var(--navy); font-size:16px; }}
    main {{ max-width:1120px; margin:22px auto; padding:0 18px 32px; }}
    section {{ margin-bottom:16px; padding:18px; border:1px solid var(--line); border-radius:8px; background:var(--panel); }}
    .notice {{ color:#d9f6f2; margin:0; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }}
    .metric {{ padding:12px; border:1px solid var(--line); border-radius:8px; background:#f8fbfd; }}
    .metric span {{ display:block; color:var(--muted); font-size:12px; }}
    .metric b {{ display:block; margin-top:6px; color:var(--navy); font-size:22px; }}
    .summary {{ border-left:4px solid var(--teal); background:#f0fdfa; }}
    .warn {{ border-left:4px solid var(--amber); background:#fffbeb; }}
    table {{ width:100%; border-collapse:collapse; margin-top:10px; font-size:13px; }}
    th,td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ color:#334155; background:#f8fbfd; }}
    .fragment-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
    .fragment-card {{ padding:12px; border:1px solid var(--line); border-radius:8px; }}
    .mol {{ overflow:auto; min-height:160px; background:#fbfdff; border-radius:7px; }}
    ul {{ margin:0; padding-left:20px; }}
    @media (max-width:800px) {{ .grid,.fragment-grid {{ grid-template-columns:1fr; }} header {{ padding:22px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>DecoDoseNet 肿瘤联合治疗剂量-机制解释报告</h1>
    <p class="notice">面向抗癌药物组合响应预测、剂量分析与机制解释的本地科研分析平台</p>
    <p class="notice">本系统仅用于科研分析、候选组合筛选和机制假设生成，不构成临床诊疗建议。所有预测结果需经独立实验验证。</p>
  </header>
  <main>
    <section>
      <h2>分析条件</h2>
      <p><b>药物组合：</b>{_html_text(input_data['drugA'])} + {_html_text(input_data['drugB'])}</p>
      <p><b>细胞系：</b>{_html_text(input_data['cellLine'])}</p>
      <p><b>剂量：</b>{_html_text(input_data['doseA'])} / {_html_text(input_data['doseB'])} uM</p>
    </section>
    <section>
      <h2>核心评分</h2>
      <div class="grid">
        {_metric('联合治疗响应预测', pred.get('final'))}
        {_metric('综合响应评分', pred.get('hpb'))}
        {_metric('剂量依赖交互评分', pred.get('epsilon'))}
        {_metric('数据覆盖可信度', pred.get('confidence'), 3)}
        {_metric('药物A相对作用贡献', pred.get('theta1'))}
        {_metric('药物B相对作用贡献', pred.get('theta2'))}
        {_metric('剂量交互效应', pred.get('epsilon'))}
      </div>
    </section>
    <section>
      <h2>剂量响应分析</h2>
      {dose_html}
    </section>
    <section>
      <h2>通路机制分析</h2>
      {pathway_html}
    </section>
    <section>
      <h2>结构贡献摘要</h2>
      <div class="fragment-grid">{fragment_html}</div>
    </section>
    <section>
      <h2>风险与边界提示</h2>
      <ul>{warning_html}</ul>
    </section>
    <section class="warn">
      <h2>科研用途声明</h2>
      <p>本系统仅用于科研分析、候选组合筛选和机制假设生成，不构成临床诊疗建议。所有预测结果需经独立实验验证。</p>
    </section>
  </main>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")
    return f"/generated/reports/{path.name}"
