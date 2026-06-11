def _pubchem(cid):
    return f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"


def _pubmed_query(query):
    return f"https://pubmed.ncbi.nlm.nih.gov/?term={query.replace(' ', '+')}"


DRUG_REFERENCE_MAP = {
    "5-fu": {
        "displayName": "5-FU",
        "category": "氟嘧啶类抗代谢药",
        "mechanism": (
            "5-FU 属于氟嘧啶类抗代谢药，其抗肿瘤作用主要与胸苷酸合成酶抑制、"
            "以及代谢产物掺入 RNA/DNA 后影响核酸合成和修复有关。当前高亮区域可理解为模型对 5-FU 核心结构的敏感性提示。"
        ),
        "targets": ["TYMS", "RNA/DNA synthesis"],
        "boundary": (
            "文献可支持 5-FU 的已知药理机制，但不能直接证明本次扰动得到的正向或负向贡献方向；"
            "贡献方向仍属于 DosePathSyn 的模型解释结果，需要后续结构类似物或体外扰动实验验证。"
        ),
        "references": [
            {"label": "Longley 等，5-FU 作用机制综述", "url": "https://pubmed.ncbi.nlm.nih.gov/12724731/"},
            {"label": "PubChem：Fluorouracil", "url": _pubchem("3385")},
        ],
    },
    "abt-888": {
        "displayName": "ABT-888 / Veliparib",
        "category": "PARP 抑制剂",
        "mechanism": (
            "ABT-888（veliparib）是 PARP 抑制剂，主要用于干扰 DNA 单链断裂修复，"
            "可增强 DNA 损伤类治疗背景下的细胞毒性。当前高亮区域可作为模型识别到的 PARP 抑制剂结构敏感区域。"
        ),
        "targets": ["PARP1", "PARP2", "DNA repair"],
        "boundary": "文献支持其 PARP/DNA 修复相关机制，但片段正负贡献方向仍来自本系统扰动归因，不等同于已验证 SAR 结论。",
        "references": [
            {"label": "PubMed：Veliparib PARP inhibitor 机制文献", "url": _pubmed_query("veliparib ABT-888 PARP inhibitor DNA repair")},
            {"label": "PubChem：Veliparib", "url": _pubchem("11960529")},
        ],
    },
    "azd1775": {
        "displayName": "AZD1775 / Adavosertib",
        "category": "WEE1 检查点激酶抑制剂",
        "mechanism": (
            "AZD1775（adavosertib）是 WEE1 抑制剂，可削弱 G2/M 检查点调控，"
            "促使携带 DNA 损伤的肿瘤细胞进入有丝分裂，从而增加复制压力和细胞死亡风险。"
        ),
        "targets": ["WEE1", "G2/M checkpoint", "DNA damage response"],
        "boundary": "文献支持 WEE1 检查点机制；当前片段贡献方向仍是模型扰动结果，需要结构类似物或细胞实验验证。",
        "references": [
            {"label": "PubMed：Adavosertib/WEE1 inhibitor 文献", "url": _pubmed_query("AZD1775 adavosertib WEE1 inhibitor DNA damage response")},
            {"label": "PubChem：Adavosertib", "url": _pubchem("24856436")},
        ],
    },
    "bez-235": {
        "displayName": "BEZ-235 / Dactolisib",
        "category": "PI3K/mTOR 双靶点抑制剂",
        "mechanism": (
            "BEZ-235（dactolisib/NVP-BEZ235）是 PI3K/mTOR 双靶点抑制剂，"
            "其芳香杂环骨架与激酶抑制活性相关。当前高亮区域提示模型在该结构区域上存在较高敏感性。"
        ),
        "targets": ["PI3K", "mTOR"],
        "boundary": (
            "文献可支持 BEZ-235 的双 PI3K/mTOR 抑制机制和抗肿瘤研究背景，"
            "但具体片段的正负贡献方向来自模型扰动归因，不应直接解释为已验证的 SAR 结论或临床药效方向。"
        ),
        "references": [
            {"label": "Maira 等，NVP-BEZ235 识别与表征", "url": "https://pubmed.ncbi.nlm.nih.gov/18606717/"},
            {"label": "PubChem：Dactolisib", "url": _pubchem("11977753")},
        ],
    },
    "l778123": {
        "displayName": "L-778123",
        "category": "法尼基转移酶抑制剂",
        "mechanism": (
            "L-778123 是法尼基转移酶抑制剂，主要用于干扰 RAS 等蛋白的异戊二烯化修饰，"
            "从而影响膜定位及下游增殖信号。当前结构高亮表示模型对该候选结构区域的敏感性。"
        ),
        "targets": ["Farnesyltransferase", "RAS prenylation"],
        "boundary": "文献支持其法尼基转移酶/RAS 修饰相关机制；片段方向仍为模型解释，需实验验证。",
        "references": [
            {"label": "PubMed：L-778123 farnesyltransferase inhibitor 文献", "url": _pubmed_query("L-778123 farnesyltransferase inhibitor Ras")},
            {"label": "PubChem：L-778123", "url": _pubchem("216453")},
        ],
    },
    "mk-2206": {
        "displayName": "MK-2206",
        "category": "AKT 变构抑制剂",
        "mechanism": (
            "MK-2206 是 AKT 变构抑制剂，可抑制 PI3K/AKT 生存信号通路，"
            "并影响肿瘤细胞增殖、存活和药物敏感性。"
        ),
        "targets": ["AKT1", "AKT2", "AKT3"],
        "boundary": "文献支持其 AKT 通路机制；当前片段正负贡献方向仍来自模型扰动归因。",
        "references": [
            {"label": "PubMed：MK-2206 allosteric AKT inhibitor 文献", "url": _pubmed_query("MK-2206 allosteric AKT inhibitor cancer")},
            {"label": "PubChem：MK-2206", "url": _pubchem("24964624")},
        ],
    },
    "mk-4541": {
        "displayName": "MK-4541",
        "category": "选择性雄激素受体调节剂 / 5α-还原酶相关研究化合物",
        "mechanism": (
            "MK-4541 是与雄激素受体调节和 5α-还原酶抑制相关的研究化合物，"
            "在前列腺癌相关模型中被用于探索 AR 依赖性生长调控。"
        ),
        "targets": ["AR", "5α-reductase"],
        "boundary": "文献支持其 AR/雄激素相关研究背景；当前片段解释不等同于已验证抗肿瘤药效团。",
        "references": [
            {"label": "MK-4541 前列腺癌模型研究", "url": "https://www.sciencedirect.com/science/article/pii/S0960076016301030"},
            {"label": "PubChem：MK-4541", "url": _pubchem("59691338")},
        ],
    },
    "mk-4827": {
        "displayName": "MK-4827 / Niraparib",
        "category": "PARP 抑制剂",
        "mechanism": (
            "MK-4827（niraparib）是 PARP 抑制剂，作用于 DNA 损伤修复网络，"
            "在同源重组缺陷等背景下可增强 DNA 损伤累积。"
        ),
        "targets": ["PARP1", "PARP2", "DNA repair"],
        "boundary": "文献支持其 PARP 抑制机制；片段正负方向属于模型解释结果。",
        "references": [
            {"label": "PubMed：Niraparib PARP inhibitor 文献", "url": _pubmed_query("niraparib MK-4827 PARP inhibitor")},
            {"label": "PubChem：Niraparib", "url": _pubchem("24958200")},
        ],
    },
    "mk-5108": {
        "displayName": "MK-5108",
        "category": "Aurora A 激酶抑制剂",
        "mechanism": (
            "MK-5108 是 Aurora A 激酶抑制剂，主要影响有丝分裂纺锤体形成、染色体分离和细胞周期进程，"
            "可用于解释与增殖和有丝分裂压力相关的响应。"
        ),
        "targets": ["AURKA", "mitosis"],
        "boundary": "文献支持其 Aurora A/有丝分裂调控机制；片段贡献方向仍需实验验证。",
        "references": [
            {"label": "PubMed：MK-5108 Aurora A inhibitor 文献", "url": _pubmed_query("MK-5108 Aurora A kinase inhibitor")},
            {"label": "PubChem：MK-5108", "url": _pubchem("24748204")},
        ],
    },
    "mk-8669": {
        "displayName": "MK-8669 / Ridaforolimus",
        "category": "mTOR 抑制剂",
        "mechanism": (
            "MK-8669（ridaforolimus）是雷帕霉素类似物类 mTOR 抑制剂，"
            "主要影响 mTOR 介导的细胞生长、蛋白合成和营养感知信号。"
        ),
        "targets": ["mTOR", "FKBP12"],
        "boundary": "文献支持其 mTOR 通路机制；当前结构片段方向为模型扰动解释。",
        "references": [
            {"label": "PubMed：Ridaforolimus/MK-8669 mTOR inhibitor 文献", "url": _pubmed_query("ridaforolimus MK-8669 mTOR inhibitor")},
            {"label": "PubChem：Ridaforolimus", "url": _pubchem("11520894")},
        ],
    },
    "mk-8776": {
        "displayName": "MK-8776 / SCH900776",
        "category": "CHK1 检查点激酶抑制剂",
        "mechanism": (
            "MK-8776（SCH900776）是 CHK1 抑制剂，可削弱 DNA 损伤检查点，"
            "增强复制压力和 DNA 损伤背景下的细胞死亡风险。"
        ),
        "targets": ["CHEK1", "DNA damage checkpoint"],
        "boundary": "文献支持其 CHK1/DNA 损伤检查点机制；片段贡献方向属于模型解释。",
        "references": [
            {"label": "PubMed：MK-8776/SCH900776 CHK1 inhibitor 文献", "url": _pubmed_query("MK-8776 SCH900776 CHK1 inhibitor")},
            {"label": "PubChem：MK-8776", "url": _pubchem("16224745")},
        ],
    },
    "mrk-003": {
        "displayName": "MRK-003",
        "category": "γ-分泌酶 / Notch 通路抑制剂",
        "mechanism": (
            "MRK-003 是 γ-分泌酶抑制剂，常用于调控 Notch 信号通路，"
            "可影响肿瘤细胞分化、增殖和存活相关过程。"
        ),
        "targets": ["γ-secretase", "NOTCH signaling"],
        "boundary": "文献支持其 Notch/γ-分泌酶通路机制；当前片段方向仍需实验验证。",
        "references": [
            {"label": "PubMed：MRK-003 gamma-secretase Notch 文献", "url": _pubmed_query("MRK-003 gamma secretase inhibitor Notch cancer")},
            {"label": "PubChem：MRK-003", "url": _pubchem("56841621")},
        ],
    },
    "pd325901": {
        "displayName": "PD325901 / PD0325901",
        "category": "MEK 抑制剂",
        "mechanism": (
            "PD325901（常与 PD0325901 名称关联）是 MEK 抑制剂，作用于 RAF-MEK-ERK/MAPK 信号轴，"
            "与肿瘤细胞增殖和生长信号调控相关。"
        ),
        "targets": ["MEK1", "MEK2", "MAPK pathway"],
        "boundary": "文献支持其 MEK/MAPK 通路机制；当前片段正负方向来自模型解释。",
        "references": [
            {"label": "PubMed：PD0325901/PD325901 MEK inhibitor 文献", "url": _pubmed_query("PD0325901 PD325901 MEK inhibitor cancer")},
            {"label": "PubChem：PD325901", "url": _pubchem("9826528")},
        ],
    },
    "sn-38": {
        "displayName": "SN-38",
        "category": "拓扑异构酶 I 抑制剂",
        "mechanism": (
            "SN-38 是伊立替康的活性代谢物，主要抑制拓扑异构酶 I，"
            "导致复制相关 DNA 损伤累积并影响肿瘤细胞存活。"
        ),
        "targets": ["TOP1", "DNA replication damage"],
        "boundary": "文献支持其 TOP1/DNA 损伤机制；当前片段解释不等同于已验证临床药效方向。",
        "references": [
            {"label": "PubMed：SN-38 topoisomerase I inhibitor 文献", "url": _pubmed_query("SN-38 topoisomerase I inhibitor irinotecan")},
            {"label": "PubChem：SN-38", "url": _pubchem("104842")},
        ],
    },
}

DRUG_ALIASES = {
    "fluorouracil": "5-fu",
    "5-fluorouracil": "5-fu",
    "veliparib": "abt-888",
    "abt888": "abt-888",
    "adavosertib": "azd1775",
    "nvp-bez235": "bez-235",
    "dactolisib": "bez-235",
    "bez235": "bez-235",
    "l-778123": "l778123",
    "l-778,123": "l778123",
    "l778123": "l778123",
    "mk2206": "mk-2206",
    "mk4541": "mk-4541",
    "mk4827": "mk-4827",
    "niraparib": "mk-4827",
    "mk5108": "mk-5108",
    "mk8669": "mk-8669",
    "ridaforolimus": "mk-8669",
    "deforolimus": "mk-8669",
    "mk8776": "mk-8776",
    "sch900776": "mk-8776",
    "mrk003": "mrk-003",
    "pd0325901": "pd325901",
    "pd-0325901": "pd325901",
    "pd325901": "pd325901",
}


def normalize_drug_name(drug_name):
    key = (drug_name or "").strip().lower()
    key = key.replace("_", "-")
    return DRUG_ALIASES.get(key, key)


def get_drug_medical_support(drug_name):
    key = normalize_drug_name(drug_name)
    item = DRUG_REFERENCE_MAP.get(key)
    if item:
        support = dict(item)
        support["levels"] = [
            {"label": "文献支持", "value": support["category"]},
            {"label": "模型解释", "value": "当前片段贡献方向"},
            {"label": "实验状态", "value": "需结构类似物或湿实验验证"},
        ]
        return support
    return {
        "displayName": drug_name,
        "category": "待补充",
        "mechanism": (
            f"{drug_name} 的结构敏感区域来自模型扰动归因，可用于形成候选结构解释假设。"
            "建议结合该药物已知靶点、类似物 SAR 和细胞实验背景进一步判断其药理意义。"
        ),
        "targets": [],
        "boundary": "当前片段贡献方向为模型解释结果，不等同于已验证药效团或临床药效判断。",
        "levels": [
            {"label": "文献支持", "value": "待结合具体药物补充"},
            {"label": "模型解释", "value": "当前片段贡献方向"},
            {"label": "实验状态", "value": "需要独立验证"},
        ],
        "references": [],
    }
