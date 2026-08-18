from __future__ import annotations

import math
import re
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from app.knowledge_graph.examples import build_testosterone_alopecia_graph
from app.knowledge_graph.graph import BiologicalGraph
from app.knowledge_graph.models import (
    BaseNode,
    BiomarkerNode,
    CompoundNode,
    EdgeData,
    EdgeType,
    EnzymeNode,
    IonChannelNode,
    PhenotypeNode,
    PhysiologyNode,
    ReactionNode,
    ReceptorNode,
    SignalingPathwayNode,
    TransporterNode,
)
from app.services.catalog_service import CatalogService


def normalize_stack_name(value: Any) -> str:
    """Normalize string token by lowercasing and replacing underscores/hyphens with spaces."""
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def canonicalize_match_token(value: Any) -> str:
    """Strip all non-alphanumeric characters for fuzzy synonym and key matching."""
    return "".join(ch for ch in normalize_stack_name(value) if ch.isalnum())


def parse_compound_spec(spec: Any) -> Dict[str, Any]:
    """Parse compound name/key and optional dose specification (e.g., 'clenbuterol:40ug', 'nebivolol:5mg', or structured dict)."""
    from app.services.dosing_service import get_default_compound_dose, parse_dose_string_or_spec

    if isinstance(spec, dict):
        key = str(spec.get("key") or spec.get("compound") or spec.get("name") or "").strip()
        dose = spec.get("dose") or spec.get("dose_val") or spec.get("dose_mg")
        unit = str(spec.get("unit") or spec.get("dose_unit") or "").strip().lower()

        if isinstance(dose, (int, float)) and float(dose) > 0:
            val = float(dose)
            if unit in ["ug", "mcg", "μg", "µg"]:
                dose_mg = val / 1000.0
                fmt_str = f"{val:g} μg"
            elif unit in ["g", "grams"]:
                dose_mg = val * 1000.0
                fmt_str = f"{val:g} g"
            elif unit in ["iu"]:
                dose_mg = val * 0.025
                fmt_str = f"{val:g} IU"
            else:
                dose_mg = val
                fmt_str = f"{val:g} mg"
            return {"key": key, "dose_mg": dose_mg, "dose_str": fmt_str}
        elif isinstance(dose, str) and dose.strip():
            return parse_compound_spec(f"{key}:{dose.strip()}")
        else:
            default_info = get_default_compound_dose(key)
            return {"key": key, "dose_mg": default_info["dose_mg"], "dose_str": default_info["dose_display"]}

    spec_str = str(spec or "").strip()
    if not spec_str:
        return {"key": "", "dose_mg": 10.0, "dose_str": "10 mg"}

    parsed = parse_dose_string_or_spec(spec_str)
    return {"key": parsed["key"], "dose_mg": parsed["dose_mg"], "dose_str": parsed["dose_display"]}



def resolve_stack_to_catalog_keys(stack: List[Any] | None, catalog_service: CatalogService | None = None) -> List[str]:
    """Map raw user input compound names/synonyms to canonical catalog keys directly in the database."""
    if not stack:
        return []

    service = catalog_service or CatalogService()
    resolved: List[str] = []

    for item in stack:
        parsed = parse_compound_spec(item)
        text = parsed["key"]
        if not text:
            continue

        try:
            compound = service.get_compound(text, auto_enrich=False)
        except TypeError:
            compound = service.get_compound(text)

        if compound and compound["key"] not in resolved:
            resolved.append(compound["key"])
        else:
            # Fallback search
            try:
                matches = service.search_compounds(text, limit=1, auto_enrich=False)
            except TypeError:
                matches = service.search_compounds(text, limit=1)
            if matches and matches[0]["key"] not in resolved:
                resolved.append(matches[0]["key"])

    return resolved


def classify_target_action(action: Any) -> tuple[EdgeType, float]:
    """Classify pharmacological action description into a standardized edge type and vector magnitude."""
    normalized = str(action or "").lower()
    if "antagonist" in normalized or "antagonizes" in normalized or "blocker" in normalized or "blocks" in normalized:
        return EdgeType.ANTAGONIZES, -1.0
    if "agonist" in normalized or "agonizes" in normalized or "activator" in normalized or "activates" in normalized or "antioxidant" in normalized or "scavenger" in normalized:
        return EdgeType.AGONIZES, 1.0
    if any(token in normalized for token in ["inhibitor", "inhibits", "inhibition", "suppresses", "protects", "hepatoprotective", "cytoprotective"]):
        return EdgeType.INHIBITS_ENZYME, -0.8
    if any(token in normalized for token in ["substrate", "metabolized by", "converted by", "cleaved by"]):
        return EdgeType.SUBSTRATE_OF, 0.5
    if any(token in normalized for token in ["inducer", "induces", "induction"]):
        return EdgeType.INDUCES_ENZYME, 0.8
    if any(token in normalized for token in ["pam", "positive allosteric"]):
        return EdgeType.POSITIVE_ALLOSTERIC_MODULATOR, 0.8
    if any(token in normalized for token in ["nam", "negative allosteric"]):
        return EdgeType.NEGATIVE_ALLOSTERIC_MODULATOR, -0.8
    if any(token in normalized for token in ["supports", "enhances transport", "biliary"]):
        return EdgeType.INHIBITS_CASCADE, -0.8
    if any(token in normalized for token in ["modulator", "modulates", "cofactor"]):
        return EdgeType.MODULATES, 0.5
    return EdgeType.MODULATES, 0.5


from app.services.pathway_service import PathwayService

_PATHWAY_SERVICE_SINGLETON: Optional[PathwayService] = None


def get_pathway_service() -> PathwayService:
    global _PATHWAY_SERVICE_SINGLETON
    if _PATHWAY_SERVICE_SINGLETON is None:
        _PATHWAY_SERVICE_SINGLETON = PathwayService()
    return _PATHWAY_SERVICE_SINGLETON


# Dynamically load registered biological targets from PathwayService & SQLite database
TARGET_REGISTRY: List[Dict[str, Any]] = get_pathway_service().get_all_target_registries()

# Dynamic high-speed O(1) identifier index
TARGET_LOOKUP_INDEX: Dict[str, Dict[str, Any]] = {}
for _target_entry in TARGET_REGISTRY:
    for _uid in _target_entry.get("uniprot_ids", []):
        TARGET_LOOKUP_INDEX[_uid.lower()] = _target_entry
    for _cid in _target_entry.get("chembl_target_ids", []):
        TARGET_LOOKUP_INDEX[_cid.lower()] = _target_entry
    TARGET_LOOKUP_INDEX[_target_entry["gene_symbol"].lower()] = _target_entry
    for _alias in _target_entry.get("aliases", []):
        TARGET_LOOKUP_INDEX[canonicalize_match_token(_alias)] = _target_entry


# Dynamically load target cascades from PathwayService & SQLite database
CANONICAL_TARGET_CASCADES: List[Dict[str, Any]] = get_pathway_service().get_all_target_cascades()

CASCADE_EXACT_GENE_SYMBOLS: Dict[str, List[str]] = {}
for _target_entry in TARGET_REGISTRY:
    _name = _target_entry.get("canonical_name", "")
    _sym = _target_entry.get("gene_symbol", "")
    if _name and _sym:
        CASCADE_EXACT_GENE_SYMBOLS.setdefault(_name, []).append(_sym)

# Dynamic high-speed exact O(1) identifier index for Target Cascades
EXACT_CASCADE_LOOKUP: Dict[str, Dict[str, Any]] = {}
for _cascade in CANONICAL_TARGET_CASCADES:
    _t_name = _cascade.get("target_name", "")
    if _t_name:
        EXACT_CASCADE_LOOKUP[_t_name.lower()] = _cascade
        EXACT_CASCADE_LOOKUP[canonicalize_match_token(_t_name)] = _cascade
    if _cascade.get("symbol"):
        EXACT_CASCADE_LOOKUP[_cascade["symbol"].lower()] = _cascade
    if _cascade.get("uniprot_id"):
        EXACT_CASCADE_LOOKUP[_cascade["uniprot_id"].lower()] = _cascade


def get_exact_target_cascade_blueprint(
    target_name: str,
    gene_symbol: Optional[str] = None,
    uniprot_id: Optional[str] = None,
    chembl_target_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Dynamic O(1) lookup of downstream signaling pathway, physiology, and biomarker cascade blueprints.
    Matches deterministically on UniProt Accession, HGNC Gene Symbol, ChEMBL Target ID, or Canonical Target Name,
    and dynamically resolves novel/unmapped targets via PathwayService (with SQLite caching).
    """
    candidates = [
        uniprot_id,
        chembl_target_id,
        gene_symbol,
        target_name,
    ]
    for cand in candidates:
        if not cand:
            continue
        c_str = str(cand).strip().lower()
        if c_str in EXACT_CASCADE_LOOKUP:
            return EXACT_CASCADE_LOOKUP[c_str]
        c_tok = canonicalize_match_token(cand)
        if c_tok in EXACT_CASCADE_LOOKUP:
            return EXACT_CASCADE_LOOKUP[c_tok]
        if c_str in TARGET_LOOKUP_INDEX:
            c_name = TARGET_LOOKUP_INDEX[c_str]["canonical_name"]
            if c_name.lower() in EXACT_CASCADE_LOOKUP:
                return EXACT_CASCADE_LOOKUP[c_name.lower()]
            if canonicalize_match_token(c_name) in EXACT_CASCADE_LOOKUP:
                return EXACT_CASCADE_LOOKUP[canonicalize_match_token(c_name)]

    # Check via TARGET_LOOKUP_INDEX canonical normalization
    norm_name = _normalize_target_node_id(target_name, chembl_target_id, uniprot_id)
    if norm_name:
        if norm_name.lower() in EXACT_CASCADE_LOOKUP:
            return EXACT_CASCADE_LOOKUP[norm_name.lower()]
        norm_tok = canonicalize_match_token(norm_name)
        if norm_tok in EXACT_CASCADE_LOOKUP:
            return EXACT_CASCADE_LOOKUP[norm_tok]

    # Dynamic fallback to PathwayService live Reactome/OpenTargets query & SQLite caching
    effective_name = target_name
    if (not effective_name or effective_name.lower() == "unknown") and norm_name and norm_name.lower() != "unknown":
        effective_name = norm_name
    elif (not effective_name or effective_name.lower() == "unknown") and uniprot_id and uniprot_id.lower() in TARGET_LOOKUP_INDEX:
        effective_name = TARGET_LOOKUP_INDEX[uniprot_id.lower()]["canonical_name"]
    elif (not effective_name or effective_name.lower() == "unknown") and gene_symbol and gene_symbol.lower() in TARGET_LOOKUP_INDEX:
        effective_name = TARGET_LOOKUP_INDEX[gene_symbol.lower()]["canonical_name"]
    elif (not effective_name or effective_name.lower() == "unknown") and chembl_target_id and chembl_target_id.lower() in TARGET_LOOKUP_INDEX:
        effective_name = TARGET_LOOKUP_INDEX[chembl_target_id.lower()]["canonical_name"]

    pw_service = get_pathway_service()
    dynamic_cascade = pw_service.get_dynamic_target_cascade(
        effective_name,
        {"label": effective_name, "uniprot_id": uniprot_id, "gene_symbol": gene_symbol, "target_id": chembl_target_id}
    )
    if dynamic_cascade:
        EXACT_CASCADE_LOOKUP[effective_name.lower()] = dynamic_cascade
        EXACT_CASCADE_LOOKUP[canonicalize_match_token(effective_name)] = dynamic_cascade
        if gene_symbol:
            EXACT_CASCADE_LOOKUP[gene_symbol.lower()] = dynamic_cascade
        if uniprot_id:
            EXACT_CASCADE_LOOKUP[uniprot_id.lower()] = dynamic_cascade
        if chembl_target_id:
            EXACT_CASCADE_LOOKUP[chembl_target_id.lower()] = dynamic_cascade
        return dynamic_cascade


def _normalize_target_node_id(
    raw_name: str,
    target_id: Optional[str] = None,
    accessions: Optional[str] = None,
) -> str:
    """
    Normalize molecular target to standard clinical node label using O(1) biomedical ontology indexing
    with dynamic UniProt / HGNC / ChEMBL metadata resolution.
    """
    # 1. Check UniProt Accession
    if accessions:
        acc_tokens = str(accessions).replace(";", " ").replace(",", " ").split()
        for token in acc_tokens:
            entry = TARGET_LOOKUP_INDEX.get(token.lower())
            if entry:
                return entry["canonical_name"]

    # 2. Check ChEMBL Target ID
    if target_id:
        entry = TARGET_LOOKUP_INDEX.get(str(target_id).strip().lower())
        if entry:
            return entry["canonical_name"]

    # 3. Check HGNC / Exact Alias Token
    clean_token = canonicalize_match_token(raw_name)
    if clean_token in TARGET_LOOKUP_INDEX:
        return TARGET_LOOKUP_INDEX[clean_token]["canonical_name"]
    if str(raw_name).strip().lower() in TARGET_LOOKUP_INDEX:
        return TARGET_LOOKUP_INDEX[str(raw_name).strip().lower()]["canonical_name"]

    # 4. Dynamic fallback to PathwayService metadata resolution
    pw_meta = get_pathway_service().resolve_target_metadata(raw_name)
    if pw_meta.get("name") and pw_meta.get("name") != "Unknown Target":
        return pw_meta["name"]
    cleaned = str(raw_name or "").strip()
    return cleaned


from app.services.dosing_service import CLINICAL_REFERENCE_DOSES_MG, get_default_compound_dose

DEFAULT_THERAPEUTIC_DOSES_MG: Dict[str, float] = CLINICAL_REFERENCE_DOSES_MG


def is_steroidal_androgen(compound: Dict[str, Any]) -> bool:
    """Determine if a compound is a steroidal androgen from its drug class, mechanism, or structure."""
    drug_class = str(compound.get("drug_class") or "").lower()
    mech = str(compound.get("mechanism") or "").lower()
    cats = [str(c).lower() for c in (compound.get("categories") or [])]
    all_text = f"{drug_class} {mech} {' '.join(cats)}"
    
    if any(k in all_text for k in ["aromatase inhibitor", "glucocorticoid", "mineralocorticoid", "corticosteroid", "estrogen receptor modulator", "serm"]):
        return False
    if any(k in all_text for k in ["androgen", "anabolic", "androstan"]):
        if any(k in all_text for k in ["non-steroidal", "sarm", "selective androgen receptor", "antiandrogen", "androgen receptor antagonist"]):
            return False
        return True
    return False


def is_aromatizable_androgen(compound: Dict[str, Any]) -> bool:
    """
    Determine if a compound is chemically capable of being aromatized to estradiol by CYP19A1.
    CYP19A1 requires a steroidal C19-methyl Delta-4-3-one or 3-hydroxy-Delta-5 sterol A-ring structure
    (e.g., testosterone, androstenedione, boldenone, DHEA).
    
    Non-aromatizable compounds include:
    1. Non-steroidal AR agonists (SARMs: RAD140, LGD-4033, Ostarine, etc.)
    2. 5-Alpha reduced / Androstane DHT derivatives (Drostanolone, Oxandrolone, Stanozolol, Methenolone, Mesterolone)
    3. Highly conjugated / modified non-aromatizable 19-nor trienes (Trenbolone)
    """
    if not is_steroidal_androgen(compound):
        return False
    
    drug_class = str(compound.get("drug_class") or "").lower()
    mech = str(compound.get("mechanism") or "").lower()
    smiles = str(compound.get("smiles") or "")
    
    # 1. Check chemical classification / ATC taxonomy
    if "androstan" in drug_class or "dht" in drug_class or "dihydrotestosterone" in drug_class:
        return False
    if "androstan" in mech or "dht derivative" in mech:
        return False
    
    # 2. Check SMILES structural features for delta-4-3-one steroid ring
    if smiles:
        # Check for conjugated triene (e.g. trenbolone)
        if "C=CC3=C" in smiles or bool(re.search(r"=C\d*C=C\d*C=C", smiles)):
            return False
        # Check for delta-4-3-one enone (e.g., C4=CC(=O)CCC)
        has_delta4_enone = bool(re.search(r"(=CC\(=O\)|C\(=O\)C=C|C=C\d*C\(=O\)|C\(=O\)CCC\d*=C)", smiles, re.IGNORECASE))
        if not has_delta4_enone:
            return False
            
    return True


def is_5alpha_reductase_substrate(compound: Dict[str, Any]) -> bool:
    """
    Determine if a compound is a substrate for 5-Alpha Reductase (SRD5A1/2).
    5AR reduces the 4,5-double bond of Delta-4-3-keto steroids into 5-alpha reduced metabolites.
    5-alpha reduced androstanes, 19-nor trienes, and non-steroidal SARMs cannot undergo 5-alpha reduction.
    """
    if not is_steroidal_androgen(compound):
        return False
    drug_class = str(compound.get("drug_class") or "").lower()
    if "androstan" in drug_class or "dht" in drug_class or "dihydrotestosterone" in drug_class:
        return False
    return is_aromatizable_androgen(compound)


def build_selected_compound_graph(stack: List[Any], catalog_service: CatalogService | None = None) -> BiologicalGraph:
    """
    Builds a multi-tier dynamic biological cascade graph for the selected stack:
    Tier 1: Compound Nodes (with ADMET properties and specific dose)
    Tier 2: Molecular Target Nodes (Receptors, Enzymes, Transporters)
    Tier 3: Intracellular Signaling Pathway Nodes (Reactome)
    Tier 4: Organ & Physiological Function Nodes (with dynamic cross-talk bridges)
    Tier 5: Clinical Laboratory Biomarker Nodes
    Tier 6: Clinical Phenotype & Safety Outcome Nodes
    """
    service = catalog_service or CatalogService()
    
    # 1. Parse and standardize compound specifications
    parsed_items: List[Dict[str, Any]] = []
    for item in (stack or []):
        parsed = parse_compound_spec(item)
        if parsed.get("key"):
            parsed_items.append(parsed)

    # 2. Canonicalize and merge duplicate compounds/synonyms with dose aggregation
    merged_stack = service.canonicalize_and_merge_stack(parsed_items)

    if not merged_stack:
        return build_testosterone_alopecia_graph()

    # Pre-fetch stack compounds to evaluate stack-level endocrine context
    stack_compounds: List[Dict[str, Any]] = []
    for item in merged_stack:
        c_obj = service.get_compound(item.get("key") or "")
        if c_obj:
            stack_compounds.append(c_obj)

    has_bioidentical_test_in_stack = any(
        ("testosterone" in str(c.get("canonical_name") or c.get("name") or c.get("key") or "").lower()
         and not any(w in str(c.get("canonical_name") or c.get("name") or c.get("key") or "").lower()
                     for w in ["trenbolone", "nandrolone", "drostanolone", "oxandrolone", "boldenone", "stanozolol", "dihydrotestosterone", "epitestosterone", "sarm", "rad140", "lgd", "ostarine", "s-4", "yk-11"]))
        or "hcg" in str(c.get("canonical_name") or c.get("name") or c.get("key") or "").lower()
        for c in stack_compounds
    )

    graph = BiologicalGraph()

    for compound_entry in merged_stack:
        compound_key = compound_entry.get("key") or "compound"
        compound = service.get_compound(compound_key)

        dose_mg = float(compound_entry.get("dose_mg") if compound_entry.get("dose_mg") is not None else compound_entry.get("dose", 10.0))
        dose_str = str(compound_entry.get("dose_str") or (f"{dose_mg:g} mg" if dose_mg >= 1.0 else f"{dose_mg * 1000.0:g} μg"))

        if compound is None:
            graph.add_node(
                CompoundNode(
                    node_id=compound_key,
                    label=compound_key.title(),
                ),
                dose_mg=dose_mg,
                dose_str=dose_str,
            )
            continue

        compound_id = str(compound.get("key") or compound_key)
        compound_label = str(compound.get("name") or compound_id)

        # 1. Add Compound Node
        graph.add_node(
            CompoundNode(
                node_id=compound_id,
                label=compound_label,
                smiles=compound.get("smiles"),
                inchikey=compound.get("inchikey"),
                logP=compound.get("logp"),
                tpsa=compound.get("tpsa"),
                molecular_weight=compound.get("molecular_weight"),
                base_half_life=float(re.search(r"(\d+)", str(compound.get("half_life") or "")).group(1)) if re.search(r"(\d+)", str(compound.get("half_life") or "")) else None,
                drug_class=compound.get("drug_class"),
                is_narrow_therapeutic_index=bool(compound.get("is_narrow_therapeutic_index")),
            ),
            dose_mg=dose_mg,
            dose_str=dose_str,
            molecular_weight=compound.get("molecular_weight"),
            oral_bioavailability=compound.get("oral_bioavailability") or compound.get("bioavailability_f"),
            volume_of_distribution=compound.get("volume_of_distribution") or compound.get("volume_of_distribution_l_kg"),
            protein_binding=compound.get("protein_binding") or compound.get("protein_binding_pct"),
        )

        receptor_targets = list(compound.get("receptor_targets") or [])
        mechanism_text = str(compound.get("mechanism") or "").lower()
        c_name_lower = str(compound.get("canonical_name") or compound.get("name") or compound_key).lower()
        drug_class_lower = str(compound.get("drug_class") or "").lower()

        # Connect exogenous bioidentical testosterone to circulating hormone pool (while excluding synthetic derivatives)
        is_bioidentical_test = "testosterone" in c_name_lower and not any(w in c_name_lower for w in ["trenbolone", "nandrolone", "drostanolone", "oxandrolone", "boldenone", "stanozolol", "dihydrotestosterone", "epitestosterone", "sarm", "rad140", "lgd"])
        if is_bioidentical_test:
            if dose_mg <= 10.0:
                exo_efficacy = 0.62 * (max(0.1, dose_mg) / 10.0)
            else:
                exo_efficacy = 0.62 + 0.015 * (dose_mg - 10.0)
            
            existing_pool = next((t for t in receptor_targets if "circulating" in str(t.get("target", "")).lower() or "serum testosterone pool" in str(t.get("target", "")).lower()), None)
            if existing_pool:
                existing_pool["intrinsic_efficacy"] = exo_efficacy
                existing_pool["pre_computed_stress"] = True
            else:
                receptor_targets.insert(0, {
                    "target": "Circulating Serum Testosterone Pool",
                    "action": "agonist",
                    "family": "Endocrine Pool",
                    "affinity_ki": 1.0,
                    "intrinsic_efficacy": exo_efficacy,
                    "pre_computed_stress": True,
                })

            exo_arom_eff = 0.20 * (max(0.1, dose_mg) / 10.0) if dose_mg <= 10.0 else min(0.48, 0.20 + 0.0025 * (dose_mg - 10.0))
            existing_arom = next((t for t in receptor_targets if "aromatase" in str(t.get("target", "")).lower() or "cyp19a1" in str(t.get("target", "")).lower()), None)
            if existing_arom:
                existing_arom["intrinsic_efficacy"] = exo_arom_eff
                existing_arom["pre_computed_stress"] = True
            else:
                receptor_targets.append({
                    "target": "Aromatase (CYP19A1)",
                    "action": "substrate",
                    "family": "Steroidogenesis",
                    "affinity_ki": 1.0,
                    "intrinsic_efficacy": exo_arom_eff,
                    "pre_computed_stress": True,
                })

        # Aromatase Inhibitor (Anastrozole, Letrozole, Exemestane)
        is_ai = any(w in c_name_lower or w in drug_class_lower or w in mechanism_text for w in ["aromatase inhibitor", "anastrozole", "letrozole", "exemestane"])
        if is_ai and not any("aromatase" in str(t.get("target", "")).lower() for t in receptor_targets):
            ai_eff = -min(0.95, 0.50 + 0.15 * math.log10(max(1.0, dose_mg)))
            receptor_targets.append({
                "target": "Aromatase (CYP19A1)",
                "action": "inhibitor",
                "family": "Enzyme",
                "intrinsic_efficacy": ai_eff,
                "pre_computed_stress": True,
            })

        is_androgen = (is_steroidal_androgen(compound) or ("androgen" in drug_class_lower and "antagonist" not in drug_class_lower and "inhibitor" not in drug_class_lower) or "sarm" in drug_class_lower) and not is_ai
        is_arom = is_aromatizable_androgen(compound) if is_androgen else True
        is_5ar = is_5alpha_reductase_substrate(compound) if is_androgen else True

        # Endocrine negative feedback: Synthetic androgens / SARMs without bioidentical testosterone base shut down HPG axis
        if is_androgen and not is_bioidentical_test:
            if not any("androgen receptor" in str(t.get("target", "")).lower() for t in receptor_targets):
                receptor_targets.append({
                    "target": "Androgen Receptor (AR / NR3C4)",
                    "action": "agonist",
                    "family": "Nuclear Receptor",
                    "affinity_ki": 1.0,
                    "intrinsic_efficacy": 0.85,
                    "pre_computed_stress": True,
                })

        # 19-nor progestogenic stimulation (Trenbolone, Nandrolone)
        is_19nor = any(w in c_name_lower or w in drug_class_lower or w in mechanism_text for w in ["19-nor", "nandrolone", "trenbolone", "nortestosterone", "progest"])
        if is_19nor and not any("progesterone receptor" in str(t.get("target", "")).lower() for t in receptor_targets):
            receptor_targets.append({
                "target": "Progesterone Receptor (PGR / NR3C3)",
                "action": "agonist",
                "family": "Nuclear Receptor",
                "intrinsic_efficacy": 0.85,
                "pre_computed_stress": True,
            })

        # Dopamine Agonist prolactin suppression (Cabergoline, Pramipexole)
        is_d2_agonist = any(w in c_name_lower or w in drug_class_lower or w in mechanism_text for w in ["cabergoline", "pramipexole", "bromocriptine", "dopamine agonist"])
        if is_d2_agonist and not any("dopamine" in str(t.get("target", "")).lower() for t in receptor_targets):
            receptor_targets.append({
                "target": "Dopamine Transporter & Receptors (SLC6A3 / DRD2)",
                "action": "agonist",
                "family": "GPCR",
                "intrinsic_efficacy": 0.90,
                "pre_computed_stress": True,
            })

        # Exogenous Thyroid (T3 / Liothyronine, T4 / Levothyroxine)
        is_thyroid = any(w in c_name_lower or w in drug_class_lower or w in mechanism_text for w in ["liothyronine", "levothyroxine", "thyroid hormone", "triiodothyronine", "t3", "t4"]) and not any(w in c_name_lower for w in ["ashwagandha", "iodine", "selenium", "tyrosine"])
        if is_thyroid and not any("thyroid hormone receptor" in str(t.get("target", "")).lower() for t in receptor_targets):
            receptor_targets.append({
                "target": "Thyroid Hormone Receptor Alpha & Beta (THRA/THRB / NR1A1/NR1A2)",
                "action": "agonist",
                "family": "Nuclear Receptor",
                "intrinsic_efficacy": 0.85,
                "pre_computed_stress": True,
            })

        # Exogenous Glucocorticoids (Prednisone, Dexamethasone, Hydrocortisone)
        is_glucocorticoid = any(w in c_name_lower or w in drug_class_lower or w in mechanism_text for w in ["prednisone", "dexamethasone", "hydrocortisone", "methylprednisolone", "budesonide", "corticosteroid", "glucocorticoid"])
        if is_glucocorticoid and not any("glucocorticoid receptor" in str(t.get("target", "")).lower() for t in receptor_targets):
            receptor_targets.append({
                "target": "Glucocorticoid Receptor (GR / NR3C1)",
                "action": "agonist",
                "family": "Nuclear Receptor",
                "intrinsic_efficacy": 0.85,
                "pre_computed_stress": True,
            })

        # Dynamic First-Principles Organ Stress & Clearance Pathway Synthesis
        cyp_info = compound.get("cyp_enzymes") or {}
        transporter_info = compound.get("transporters") or {}
        phase2_info = compound.get("phase2_enzymes") or {}
        clearance_routes = str(compound.get("clearance_routes") or "").lower()
        logp_val = float(compound.get("logp") or 0.0)
        warnings_text = str(compound.get("warnings") or "").lower()
        is_17aa = any(w in c_name_lower for w in ["methyl", "stanozolol", "superdrol", "anadrol", "oxymetholone", "halotestin", "fluoxymesterone", "dianabol", "methandrostenolone", "turinabol", "winstrol"])

        is_blocker = any(w in drug_class_lower for w in ["blocker", "antagonist", "inhibitor"])
        comp_class_lower = str(compound.get("compound_class") or "").lower()
        is_antioxidant = any(
            w in drug_class_lower or w in mechanism_text or w in comp_class_lower or w in c_name_lower
            for w in [
                "antioxidant",
                "glutathione",
                "scavenger",
                "n-acetylcysteine",
                "acetylcysteine",
                "tudca",
                "mucolytic",
                "reductant",
                "neutralizing reactive oxygen",
                "protects against oxidative",
                "radical scavenger",
                "lipoic acid",
                "coq10",
                "ubiquinone",
                "ubiquinol",
                "tocopherol",
                "ascorbic",
                "curcumin",
                "omega",
            ]
        )

        # 1. Dynamic Hepatic Metabolic Clearance & Hepatobiliary Stress
        # Routine hepatic metabolism is normal physiology — NOT hepatotoxicity.
        # Only structurally hepatotoxic features should drive meaningful transaminase elevation.
        has_hep_clearance = (
            bool(cyp_info.get("substrates"))
            or bool(cyp_info.get("inhibitors"))
            or bool(phase2_info.get("substrates"))
            or "hepatic" in clearance_routes
            or "liver" in clearance_routes
            or is_steroidal_androgen(compound)
            or logp_val >= 3.2
        )
        if has_hep_clearance and not is_antioxidant and not any("hepatic metabolic clearance" in str(t.get("target", "")).lower() for t in receptor_targets):
            # Tiered hepatotoxicity scoring based on structural features
            hep_risk_score = 0.0

            # 17-alpha-alkylated orals (methyltestosterone, stanozolol, superdrol) — genuinely hepatotoxic
            if is_17aa:
                hep_risk_score += 0.50
            # Known hepatotoxicity warnings
            if any(w in warnings_text for w in ["hepatotox", "liver damage", "liver injury", "cholestatic", "jaundice", "liver failure"]):
                hep_risk_score += 0.35
            # CYP inhibitors (competitive inhibition increases reactive metabolite accumulation)
            if bool(cyp_info.get("inhibitors")):
                hep_risk_score += 0.08
            # Very high lipophilicity (logP > 5) increases hepatic accumulation
            if logp_val >= 5.0:
                hep_risk_score += 0.06
            elif logp_val >= 3.5:
                hep_risk_score += 0.02
            # Injectable steroids (non-17aa) — mild hepatic load
            if is_steroidal_androgen(compound) and not is_17aa:
                hep_risk_score += 0.04
            # Routine CYP substrate metabolism — background noise
            if bool(cyp_info.get("substrates")) and hep_risk_score < 0.05:
                hep_risk_score += 0.02

            # Dose scaling: only amplify for genuinely hepatotoxic compounds
            dose_factor = 1.0 + 0.15 * math.log10(max(1.0, dose_mg)) if hep_risk_score >= 0.10 else 1.0
            hep_efficacy = min(0.85, hep_risk_score * dose_factor)

            # Only add target if there's a meaningful hepatic signal
            if hep_efficacy >= 0.01:
                receptor_targets.append({
                    "target": "Hepatic Metabolic Clearance & Hepatobiliary System",
                    "action": "substrate",
                    "family": "Xenobiotic Clearance",
                    "intrinsic_efficacy": hep_efficacy,
                    "pre_computed_stress": True,
                })

        # 2. Dynamic Renal Filtration & Tubular Hemodynamic Stress
        # Distinguish nephroprotective agents (ARBs, aldosterone antagonists, SGLT2i) from nephrotoxic ones
        is_nephroprotective = any(w in drug_class_lower for w in ["arb", "angiotensin", "sartan", "sglt2", "aldosterone antagonist", "mineralocorticoid"])
        is_nephroprotective = is_nephroprotective or any(w in mechanism_text for w in ["angiotensin", "aldosterone", "sglt2", "mineralocorticoid receptor"])
        is_nephrotoxic = any(w in drug_class_lower for w in ["nsaid", "aminoglycoside", "cisplatin", "contrast"])
        is_nephrotoxic = is_nephrotoxic or any(w in warnings_text for w in ["nephrotox", "kidney damage", "renal failure", "renal impairment"])

        has_ren_involvement = (
            "renal" in clearance_routes
            or "kidney" in clearance_routes
            or any(t in str(transporter_info).upper() for t in ["OAT", "OCT", "P-GP", "ABCB1", "SLC22"])
            or is_nephroprotective
            or is_nephrotoxic
            or any(w in mechanism_text for w in ["raas", "cox-1", "cox-2"])
        )
        if has_ren_involvement and not any("glomerular filtration" in str(t.get("target", "")).lower() for t in receptor_targets):
            if is_nephroprotective:
                # ARBs, SGLT2i, MRAs are nephroprotective — they reduce GFR stress long-term
                # Short-term they may transiently raise creatinine (hemodynamic effect), but this is mild
                ren_efficacy = 0.04 + 0.02 * math.log10(max(1.0, dose_mg))
            elif is_nephrotoxic:
                # Genuinely nephrotoxic agents
                ren_efficacy = min(0.70, 0.25 + 0.15 * math.log10(max(1.0, dose_mg)))
            else:
                # Routine renal clearance — background noise
                ren_efficacy = 0.02

            if ren_efficacy >= 0.01:
                receptor_targets.append({
                    "target": "Glomerular Filtration & Renal Tubular Transport",
                    "action": "substrate",
                    "family": "Renal Elimination",
                    "intrinsic_efficacy": ren_efficacy,
                    "pre_computed_stress": True,
                })

        # 3. Dynamic Cellular Redox & Mitochondrial Stress
        is_blocker = any(w in drug_class_lower for w in ["blocker", "antagonist", "inhibitor"])
        comp_class_lower = str(compound.get("compound_class") or "").lower()
        is_antioxidant = any(
            w in drug_class_lower or w in mechanism_text or w in comp_class_lower or w in c_name_lower
            for w in [
                "antioxidant",
                "glutathione",
                "scavenger",
                "n-acetylcysteine",
                "acetylcysteine",
                "tudca",
                "mucolytic",
                "reductant",
                "neutralizing reactive oxygen",
                "protects against oxidative",
                "radical scavenger",
                "lipoic acid",
                "coq10",
                "ubiquinone",
                "ubiquinol",
                "tocopherol",
                "ascorbic",
            ]
        )
        has_redox_stress = (
            not is_blocker
            and not is_antioxidant
            and (
                is_17aa
                or ("beta" in drug_class_lower and "agonist" in drug_class_lower)
                or any(w in drug_class_lower for w in ["sympathomimetic", "xanthine", "stimulant", "mitochondrial uncoupler", "quinone", "17alpha-alkylated", "17a-alkylated"])
                or any(w in mechanism_text for w in ["beta-1 agonist", "beta-2 agonist", "camp surge", "uncoupl", "generates reactive oxygen", "mitochondrial uncoupling", "induces ros", "oxidative phosphorylation uncoupling", "lipid peroxidation"])
            )
        )
        if has_redox_stress and not any("cellular redox" in str(t.get("target", "")).lower() for t in receptor_targets):
            ox_efficacy = min(0.65, (0.25 if is_17aa else 0.15) + 0.10 * math.log10(max(1.0, dose_mg)))
            receptor_targets.append({
                "target": "Cellular Redox Homeostasis & Mitochondrial Bioenergetics",
                "action": "stimulator",
                "family": "Redox Homeostasis",
                "intrinsic_efficacy": ox_efficacy,
                "pre_computed_stress": True,
            })
        elif is_antioxidant and not any("glutathione" in str(t.get("target", "")).lower() or "cystine" in str(t.get("target", "")).lower() or "antioxidant defense" in str(t.get("target", "")).lower() for t in receptor_targets):
            antiox_efficacy = min(0.85, 0.35 + 0.15 * math.log10(max(1.0, dose_mg)))
            receptor_targets.append({
                "target": "Glutathione Biosynthesis & Cellular Antioxidant Defense (System xc- / Nrf2 / GCL)",
                "action": "agonist",
                "family": "Antioxidant Defense",
                "intrinsic_efficacy": antiox_efficacy,
            })

        # Connect Targets & Multi-Tier Cascades
        for receptor in receptor_targets:
            if not isinstance(receptor, dict):
                continue
            target_raw = str(receptor.get("target") or receptor.get("name") or "unknown_target").strip()
            if not target_raw:
                continue

            target_raw_lower = target_raw.lower()
            action_lower = str(receptor.get("action") or "").lower()

            # Filter out aromatase substrate edges for chemically non-aromatizable compounds
            if is_androgen and not is_arom:
                if any(w in target_raw_lower for w in ["aromatase", "cyp19", "cyp19a1", "estrogen receptor", "esr1", "esr2"]) and any(act in action_lower for act in ["substrate", "agonist", "stimulator", "cleaved"]):
                    continue

            # Filter out 5AR substrate edges for DHT derivatives and non-5AR substrates
            if is_androgen and not is_5ar:
                if any(w in target_raw_lower for w in ["5-alpha reductase", "srd5a", "5ar"]) and any(act in action_lower for act in ["substrate", "agonist"]):
                    continue

            target_id = _normalize_target_node_id(
                raw_name=target_raw,
                target_id=receptor.get("target_id"),
                accessions=receptor.get("accessions") or receptor.get("uniprot_id"),
            )
            target_label = target_id
            edge_type, vector_magnitude = classify_target_action(receptor.get("action"))

            # If androgen/exogenous hormone connects to HPG Axis, ensure it exerts negative feedback suppression
            if any(w in target_raw_lower or w in target_id.lower() for w in ["hpg", "hypothalamic-pituitary-gonadal", "gnrh"]) and is_androgen:
                edge_type = EdgeType.INHIBITS_PATHWAY
                vector_magnitude = -0.9

            affinity_ki_raw = receptor.get("affinity_ki")
            inhibition_ic50_raw = receptor.get("inhibition_ic50")
            ec50_raw = receptor.get("ec50")

            affinity_ki: Optional[float] = None
            if affinity_ki_raw is not None:
                try:
                    val = float(affinity_ki_raw)
                    if val > 0.0:
                        affinity_ki = val
                except (ValueError, TypeError):
                    pass

            inhibition_ic50: Optional[float] = None
            if inhibition_ic50_raw is not None:
                try:
                    val = float(inhibition_ic50_raw)
                    if val > 0.0:
                        inhibition_ic50 = val
                except (ValueError, TypeError):
                    pass

            ec50: Optional[float] = None
            if ec50_raw is not None:
                try:
                    val = float(ec50_raw)
                    if val > 0.0:
                        ec50 = val
                except (ValueError, TypeError):
                    pass

            if receptor.get("intrinsic_efficacy") is not None:
                vector_magnitude = float(receptor["intrinsic_efficacy"])

            # Check Canonical Cascade Mapping & Target Node Type (Zero-Regex Exact Biological Matching)
            matched_cascade = get_exact_target_cascade_blueprint(
                target_name=target_id,
                gene_symbol=receptor.get("gene_symbol"),
                uniprot_id=receptor.get("uniprot_id") or receptor.get("accessions"),
                chembl_target_id=receptor.get("chembl_target_id") or receptor.get("target_id"),
            )
            if matched_cascade is None and target_raw != target_id:
                matched_cascade = get_exact_target_cascade_blueprint(
                    target_name=target_raw,
                    gene_symbol=receptor.get("gene_symbol"),
                    uniprot_id=receptor.get("uniprot_id") or receptor.get("accessions"),
                    chembl_target_id=receptor.get("chembl_target_id") or receptor.get("target_id"),
                )

            cascade_node_type = str(matched_cascade.get("node_type", "")).lower() if matched_cascade else ""
            target_fam = str(receptor.get("family") or "").lower()
            target_lower = target_id.lower()

            # Instantiate accurate biological node type (Enzyme, Transporter, Ion Channel, or Receptor)
            if (
                cascade_node_type == "enzyme"
                or any(w in target_lower or w in target_fam for w in ["enzyme", "synthase", "reductase", "aromatase", "cyp", "cox", "pde", "kinase", "esterase", "oxygenase", "dehydrogenase"])
            ):
                target_node = EnzymeNode(
                    node_id=target_id,
                    label=target_label,
                    enzyme_family=receptor.get("family") or "Enzyme",
                )
            elif (
                cascade_node_type == "transporter"
                or any(w in target_lower or w in target_fam for w in ["transporter", "sert", "dat", "net", "vmat", "p-gp", "oat", "oct", "mrp", "bcrp", "slc", "abc"])
            ):
                target_node = TransporterNode(
                    node_id=target_id,
                    label=target_label,
                    transporter_family=receptor.get("family") or "Membrane Transporter",
                )
            elif (
                cascade_node_type == "ion_channel"
                or any(w in target_lower or w in target_fam for w in ["channel", "herg", "kcnh2", "cav", "nav"])
            ):
                target_node = IonChannelNode(
                    node_id=target_id,
                    label=target_label,
                    channel_type=receptor.get("family") or "Ion Channel",
                )
            else:
                target_node = ReceptorNode(
                    node_id=target_id,
                    label=target_label,
                    receptor_family=receptor.get("family") or "Molecular Target",
                )

            graph.add_node(target_node)

            # Edge 1: Compound -> Target
            is_pre_computed_stress = bool(receptor.get("pre_computed_stress"))
            graph.add_edge(
                compound_id,
                target_id,
                edge_type=edge_type,
                edge_data=EdgeData(
                    affinity_ki=affinity_ki,
                    inhibition_ic50=inhibition_ic50,
                    vector_magnitude=vector_magnitude,
                ),
                dose_mg=dose_mg,
                dose_str=dose_str,
                pre_computed_stress=is_pre_computed_stress,
            )

            # Check Dynamic Pathway Service (Reactome + Open Targets + SQLite Cache)
            from app.services.pathway_service import PathwayService
            pathway_service = PathwayService(db_path=getattr(service, "db_path", None))
            dyn_cascade = pathway_service.get_dynamic_target_cascade(target_id, {"label": target_label, "name": target_raw})

            # Check Canonical Cascade Mapping
            if matched_cascade:
                clean_tgt = re.sub(r"[^a-z0-9_]", "_", str(target_id).lower()).strip("_")
                p_info = matched_cascade["pathway"]
                phys_info = matched_cascade["physiology"]
                p_id = f"{p_info['id']}_{clean_tgt}"
                phys_id = f"{phys_info['id']}_{clean_tgt}"
                reactome_pws = dyn_cascade.get("raw_pathways", [])
                p_label = f"{p_info['label']} ({reactome_pws[0]['pathway_name']})" if reactome_pws else p_info["label"]

                # Add Primary Pathway Node
                graph.add_node(
                    SignalingPathwayNode(
                        node_id=p_id,
                        label=p_label,
                        pathway_database="Reactome" if reactome_pws else p_info["db"],
                    )
                )

                # Edge 2: Target -> Pathway
                graph.add_edge(
                    target_id,
                    p_id,
                    edge_type=EdgeType.ACTIVATES_PATHWAY,
                    edge_data=EdgeData(vector_magnitude=1.0),
                )

                # Add dynamic Reactome pathway node if available
                if reactome_pws and reactome_pws[0].get("pathway_id"):
                    r_id = f"{reactome_pws[0]['pathway_id']}_{clean_tgt}"
                    graph.add_node(
                        SignalingPathwayNode(
                            node_id=r_id,
                            label=f"{reactome_pws[0].get('pathway_name') or r_id} ({target_label})",
                            pathway_database="Reactome",
                        )
                    )
                    graph.add_edge(
                        target_id,
                        r_id,
                        edge_type=EdgeType.ACTIVATES_PATHWAY,
                        edge_data=EdgeData(vector_magnitude=1.0),
                    )

                # Add Physiology Node
                graph.add_node(
                    PhysiologyNode(
                        node_id=phys_id,
                        label=phys_info["label"],
                        organ_system=phys_info["organ"],
                    )
                )

                # Edge 3: Pathway -> Physiology
                graph.add_edge(
                    p_id,
                    phys_id,
                    edge_type=EdgeType.ALTERS_PHYSIOLOGY,
                    edge_data=EdgeData(vector_magnitude=1.0),
                )

                # Add Biomarkers & Edges
                for b_info in matched_cascade.get("biomarkers", []):
                    graph.add_node(
                        BiomarkerNode(
                            node_id=b_info["id"],
                            label=b_info["label"],
                            unit=b_info["unit"],
                            biomarker_panel=b_info["panel"],
                            safe_lower_bound=b_info["lower"],
                            safe_upper_bound=b_info["upper"],
                            onset_days=float(b_info.get("onset_days", 1.0)),
                            half_time_days=float(b_info.get("half_time_days", 3.0)),
                            time_to_steady_state_weeks=float(b_info.get("time_to_steady_state_weeks", 1.0)),
                            kinetic_profile=str(b_info.get("kinetic_profile", "direct_receptor")),
                        )
                    )
                    b_mag = float(b_info.get("mag", 1.0))
                    graph.add_edge(
                        phys_id,
                        b_info["id"],
                        edge_type=EdgeType.MODIFIES_BIOMARKER,
                        edge_data=EdgeData(vector_magnitude=b_mag),
                    )

                # Add Phenotypes & Edges
                for pheno in matched_cascade.get("phenotypes", []):
                    graph.add_node(
                        PhenotypeNode(
                            node_id=pheno["id"],
                            label=pheno["label"],
                            phenotype_category=pheno["cat"],
                            severity=pheno["sev"],
                        )
                    )
                    pheno_mag = float(pheno.get("mag", 1.0))
                    graph.add_edge(
                        phys_id,
                        pheno["id"],
                        edge_type=EdgeType.DRIVES_PHENOTYPE if pheno_mag > 0 else EdgeType.MITIGATES_PHENOTYPE,
                        edge_data=EdgeData(vector_magnitude=pheno_mag),
                    )

            # Universal Dynamic Target Cascade Fallback for unmapped targets from Reactome & Open Targets
            if not matched_cascade:
                p_dyn = dyn_cascade.get("pathway", {})
                phys_dyn = dyn_cascade.get("physiology", {})

                pathway_id = p_dyn.get("id", f"pathway_{re.sub(r'[^a-z0-9_]', '_', target_id.lower()).strip('_')}")
                p_dyn_label = p_dyn.get("label", "")
                pathway_label = f"{target_label} Transduction Cascade ({p_dyn_label})" if p_dyn_label else f"{target_label} Transduction Cascade"
                phys_id = phys_dyn.get("id", f"phys_{re.sub(r'[^a-z0-9_]', '_', target_id.lower()).strip('_')}")
                phys_dyn_label = phys_dyn.get("label", "")
                phys_label = f"{target_label} Downstream Physiological Function ({phys_dyn_label})" if phys_dyn_label else f"{target_label} Downstream Physiological Function"

                graph.add_node(
                    SignalingPathwayNode(
                        node_id=pathway_id,
                        label=pathway_label,
                        pathway_database="Reactome",
                    )
                )
                graph.add_edge(
                    target_id,
                    pathway_id,
                    edge_type=EdgeType.ACTIVATES_PATHWAY,
                    edge_data=EdgeData(vector_magnitude=1.0),
                )
                graph.add_node(
                    PhysiologyNode(
                        node_id=phys_id,
                        label=phys_label,
                        organ_system="Systemic",
                    )
                )
                graph.add_edge(
                    pathway_id,
                    phys_id,
                    edge_type=EdgeType.ALTERS_PHYSIOLOGY,
                    edge_data=EdgeData(vector_magnitude=1.0),
                )

                # Dynamic biomarkers from Open Targets / Reactome
                if dyn_cascade.get("biomarkers"):
                    for b_info in dyn_cascade.get("biomarkers", []):
                        graph.add_node(
                            BiomarkerNode(
                                node_id=b_info["id"],
                                label=b_info["label"],
                                unit=b_info["unit"],
                                biomarker_panel=b_info["panel"],
                                safe_lower_bound=b_info["lower"],
                                safe_upper_bound=b_info["upper"],
                            )
                        )
                        graph.add_edge(
                            phys_id,
                            b_info["id"],
                            edge_type=EdgeType.MODIFIES_BIOMARKER,
                            edge_data=EdgeData(vector_magnitude=float(b_info.get("mag", 0.75))),
                        )
                else:
                    bio_id = f"bio_{re.sub(r'[^a-z0-9_]', '_', target_id.lower()).strip('_')}_activity"
                    graph.add_node(
                        BiomarkerNode(
                            node_id=bio_id,
                            label=f"{target_label} Functional Index",
                            unit="index",
                            biomarker_panel="Functional Panel",
                            safe_lower_bound=0.0,
                            safe_upper_bound=100.0,
                        )
                    )
                    graph.add_edge(
                        phys_id,
                        bio_id,
                        edge_type=EdgeType.MODIFIES_BIOMARKER,
                        edge_data=EdgeData(vector_magnitude=0.75),
                    )

                # Dynamic phenotypes from Open Targets
                if dyn_cascade.get("phenotypes"):
                    for ph_info in dyn_cascade.get("phenotypes", []):
                        graph.add_node(
                            PhenotypeNode(
                                node_id=ph_info["id"],
                                label=ph_info["label"],
                                phenotype_category=ph_info.get("cat", "adverse_effect"),
                                severity=ph_info.get("sev", "moderate"),
                            )
                        )
                        graph.add_edge(
                            phys_id,
                            ph_info["id"],
                            edge_type=EdgeType.DRIVES_PHENOTYPE,
                            edge_data=EdgeData(vector_magnitude=float(ph_info.get("mag", 0.75))),
                        )
                else:
                    pheno_id = f"pheno_{re.sub(r'[^a-z0-9_]', '_', target_id.lower()).strip('_')}_modulation"
                    graph.add_node(
                        PhenotypeNode(
                            node_id=pheno_id,
                            label=f"{target_label} Downstream Outcome",
                            phenotype_category="therapeutic_benefit",
                            severity="moderate",
                        )
                    )
                    graph.add_edge(
                        phys_id,
                        pheno_id,
                        edge_type=EdgeType.DRIVES_PHENOTYPE,
                        edge_data=EdgeData(vector_magnitude=0.75),
                    )

        # Connect Pharmacokinetic CYP450 Metabolism Enzymes
        cyp_info = compound.get("cyp_enzymes") or {}
        if isinstance(cyp_info, dict):
            for sub in cyp_info.get("substrates") or []:
                enz_id = str(sub).strip().upper()
                if enz_id:
                    graph.add_node(
                        EnzymeNode(
                            node_id=enz_id,
                            label=f"{enz_id} (Substrate)",
                            enzyme_family="CYP450 Metabolism",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        enz_id,
                        edge_type=EdgeType.SUBSTRATE_OF,
                        edge_data=EdgeData(
                            vector_magnitude=1.0,
                            description=f"{compound_label} is metabolized as a substrate of {enz_id}",
                        ),
                    )
            for inh in cyp_info.get("inhibitors") or []:
                enz_id = str(inh).strip().upper()
                if enz_id:
                    graph.add_node(
                        EnzymeNode(
                            node_id=enz_id,
                            label=f"{enz_id} (Inhibitor)",
                            enzyme_family="CYP450 Metabolism",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        enz_id,
                        edge_type=EdgeType.INHIBITS_ENZYME,
                        edge_data=EdgeData(
                            vector_magnitude=-1.0,
                            description=f"{compound_label} inhibits enzymatic clearance activity of {enz_id}",
                        ),
                    )
            for ind in cyp_info.get("inducers") or []:
                enz_id = str(ind).strip().upper()
                if enz_id:
                    graph.add_node(
                        EnzymeNode(
                            node_id=enz_id,
                            label=f"{enz_id} (Inducer)",
                            enzyme_family="CYP450 Metabolism",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        enz_id,
                        edge_type=EdgeType.INDUCES_ENZYME,
                        edge_data=EdgeData(
                            vector_magnitude=1.0,
                            description=f"{compound_label} induces expression of {enz_id}",
                        ),
                    )

        # Connect Pharmacokinetic Membrane Transporters
        transporter_info = compound.get("transporters") or {}
        if isinstance(transporter_info, dict):
            for sub in transporter_info.get("substrates") or []:
                t_id = str(sub).strip().upper()
                if t_id:
                    graph.add_node(
                        TransporterNode(
                            node_id=t_id,
                            label=f"{t_id} (Substrate)",
                            transporter_family="Membrane Transporter",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        t_id,
                        edge_type=EdgeType.EFFLUXED_BY,
                        edge_data=EdgeData(
                            vector_magnitude=1.0,
                            description=f"{compound_label} is transported as a substrate by {t_id}",
                        ),
                    )
            for inh in transporter_info.get("inhibitors") or []:
                t_id = str(inh).strip().upper()
                if t_id:
                    graph.add_node(
                        TransporterNode(
                            node_id=t_id,
                            label=f"{t_id} (Inhibitor)",
                            transporter_family="Membrane Transporter",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        t_id,
                        edge_type=EdgeType.INHIBITS_CASCADE,
                        edge_data=EdgeData(
                            vector_magnitude=-1.0,
                            description=f"{compound_label} inhibits transport via {t_id}",
                        ),
                    )

        # Connect Phase II Conjugation Enzymes
        phase2_info = compound.get("phase2_enzymes") or {}
        if isinstance(phase2_info, dict):
            for sub in phase2_info.get("substrates") or []:
                p2_id = str(sub).strip().upper()
                if p2_id:
                    graph.add_node(
                        EnzymeNode(
                            node_id=p2_id,
                            label=f"{p2_id} (Phase II)",
                            enzyme_family="Phase II Conjugation",
                            category="Pharmacokinetics (PK)",
                        )
                    )
                    graph.add_edge(
                        compound_id,
                        p2_id,
                        edge_type=EdgeType.SUBSTRATE_OF,
                        edge_data=EdgeData(
                            vector_magnitude=1.0,
                            description=f"{compound_label} undergoes Phase II conjugation via {p2_id}",
                        ),
                    )

    # Phase 2: Dynamic Biological Cross-Talk Bridges
    # Connects upstream physiological neurotransmitters/hormones to downstream target receptors when applicable
    for cascade in CANONICAL_TARGET_CASCADES:
        phys_id = cascade["physiology"]["id"]
        if phys_id not in graph.graph:
            continue
        for bridge in cascade.get("bridges", []):
            pattern = bridge["target_node_pattern"]
            edge_type = bridge.get("edge_type", EdgeType.MODULATES)
            vec_mag = float(bridge.get("vector_magnitude", 1.0))
            desc = bridge.get("description", "")
            
            matching_nodes = []
            for node in list(graph.graph.nodes()):
                if node == phys_id:
                    continue
                node_label = str(graph.graph.nodes[node].get("label", node)).lower()
                node_id_lower = str(node).lower()
                if re.search(pattern, node_label) or re.search(pattern, node_id_lower):
                    nt = str(graph.graph.nodes[node].get("node_type", "")).lower()
                    if nt in ("receptor", "enzyme", "transporter", "ion_channel", "carrier_protein", "target"):
                        tier_rank = 1
                    elif nt == "signaling_pathway":
                        tier_rank = 2
                    elif nt == "physiology":
                        tier_rank = 3
                    else:
                        tier_rank = 4
                    matching_nodes.append((tier_rank, node))

            if matching_nodes:
                matching_nodes.sort(key=lambda x: x[0])
                best_tier = matching_nodes[0][0]
                for rank, node in matching_nodes:
                    if rank == best_tier:
                        if not graph.graph.has_edge(phys_id, node):
                            graph.add_edge(
                                phys_id,
                                node,
                                edge_type=edge_type,
                                edge_data=EdgeData(
                                    vector_magnitude=vec_mag,
                                    description=desc,
                                    is_bridge=True,
                                ),
                            )

    if graph.graph.number_of_nodes() == 0:
        return build_testosterone_alopecia_graph()

    return graph


def filter_graph_by_stack(graph: BiologicalGraph, stack: List[Any] | None, max_depth: int = 5) -> BiologicalGraph:
    """Filter the biological knowledge graph to the cascade subgraph connected to selected compounds."""
    if not stack:
        return graph

    raw_items = [
        str(i.get("compound") or i.get("key") or i.get("name") if isinstance(i, dict) else i).strip().lower()
        for i in stack
        if i
    ]
    normalized_stack = list(dict.fromkeys(item for item in resolve_stack_to_catalog_keys(stack) if item))

    start_nodes = list(dict.fromkeys(
        [item for item in raw_items if item in graph.graph] +
        [item for item in normalized_stack if item in graph.graph]
    ))

    if not start_nodes:
        fallback = BiologicalGraph()
        items_to_add = sorted(set(raw_items or normalized_stack))
        for item in items_to_add:
            fallback.graph.add_node(
                item,
                node_id=item,
                label=item.title(),
                node_type="compound",
            )
        return fallback

    visited = set()
    depth_map = {node_id: 0 for node_id in start_nodes}
    frontier = deque(start_nodes)

    while frontier:
        current = frontier.popleft()
        if current in visited:
            continue
        visited.add(current)

        current_depth = depth_map.get(current, 0)
        if current_depth >= max_depth:
            continue

        for neighbor in list(graph.graph.successors(current)) + list(graph.graph.predecessors(current)):
            if neighbor not in visited:
                depth_map[neighbor] = current_depth + 1
                frontier.append(neighbor)

    filtered = BiologicalGraph()
    filtered.graph.add_nodes_from((node, graph.graph.nodes[node].copy()) for node in visited)
    filtered.graph.add_edges_from(
        (source, target, graph.graph.edges[source, target].copy())
        for source, target in graph.graph.edges
        if source in visited and target in visited
    )

    for item in sorted(start_nodes):
        if item not in filtered.graph.nodes:
            filtered.graph.add_node(
                item,
                node_id=item,
                label=item.title(),
                node_type="compound",
            )

    return filtered


def compute_target_combined_effects(
    graph: BiologicalGraph,
    custom_doses: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Computes combined pharmacodynamic receptor activation, fractional occupancy,
    and competitive displacement for all molecular targets (receptors, enzymes,
    ion channels, transporters) with incoming compound/ligand connections.
    Takes into account actual free molar biophase concentrations derived from dose (mg)
    and target binding affinities (Ki / IC50 in nM).
    """
    results: Dict[str, Dict[str, Any]] = {}
    custom_doses = custom_doses or {}

    target_types = {
        "receptor",
        "enzyme",
        "transporter",
        "ion_channel",
        "carrier_protein",
        "target",
    }

    for node_id, node_attrs in graph.graph.nodes(data=True):
        nt = str(node_attrs.get("node_type", "")).lower()
        if nt not in target_types and not any(t in node_id.lower() for t in ["receptor", "channel", "cyp", "transporter", "enzyme", "cox", "pde", "sert", "dat"]):
            continue

        # Find incoming compound edges
        incoming_compounds = []
        for pred in graph.graph.predecessors(node_id):
            pred_attrs = graph.graph.nodes[pred]
            pred_type = str(pred_attrs.get("node_type", "")).lower()
            if pred_type != "compound" and graph.graph.in_degree(pred) > 0:
                if pred_type not in ["compound", "mixture", "selected"]:
                    continue

            edge_data = graph.graph.edges[pred, node_id]
            edge_type = str(edge_data.get("edge_type", "MODULATES")).upper()
            mag = float(edge_data.get("vector_magnitude", 1.0))
            ki = edge_data.get("affinity_ki")
            ic50 = edge_data.get("inhibition_ic50")
            ec50 = edge_data.get("ec50")
            pred_label = pred_attrs.get("label", pred)

            # Determine action classification & intrinsic efficacy
            is_pam = "POSITIVE_ALLOSTERIC" in edge_type or "PAM" in edge_type
            is_nam = "NEGATIVE_ALLOSTERIC" in edge_type or "NAM" in edge_type
            is_antagonist = any(k in edge_type for k in ["ANTAGONIZ", "BLOCK"])
            is_inhibitor = not is_antagonist and any(k in edge_type for k in ["INHIBIT"])
            is_substrate = "SUBSTRATE" in edge_type
            is_agonist = not is_antagonist and not is_inhibitor and not is_substrate and any(k in edge_type for k in ["AGONIZ", "ACTIVAT", "OPEN", "INDUCE"])

            if is_pam:
                action_name = "Positive Allosteric Modulator (PAM)"
                efficacy = 0.8
                is_allosteric = True
            elif is_nam:
                action_name = "Negative Allosteric Modulator (NAM)"
                efficacy = -0.8
                is_allosteric = True
            elif is_antagonist:
                action_name = "Receptor Antagonist (Blocker)"
                efficacy = -1.0
                is_allosteric = False
            elif is_inhibitor:
                action_name = "Enzymatic / Functional Inhibitor"
                efficacy = -0.85
                is_allosteric = False
            elif is_substrate:
                action_name = "Enzymatic Substrate"
                efficacy = float(mag) if mag is not None and mag > 0 else 0.95
                is_allosteric = False
            elif is_agonist:
                action_name = "Receptor Agonist (Activator)"
                efficacy = 1.0 if mag >= 0.8 else (0.6 if mag > 0 else 1.0)
                is_allosteric = False
            else:
                action_name = "Allosteric / Functional Modulator"
                efficacy = mag
                is_allosteric = False

            # Resolve Dose (mg) & Dose Display
            dose_mg = custom_doses.get(pred) or custom_doses.get(pred.lower()) or custom_doses.get(canonicalize_match_token(pred))
            if dose_mg is None:
                dose_mg = edge_data.get("dose_mg") or pred_attrs.get("dose_mg") or DEFAULT_THERAPEUTIC_DOSES_MG.get(pred.lower()) or DEFAULT_THERAPEUTIC_DOSES_MG.get(canonicalize_match_token(pred)) or DEFAULT_THERAPEUTIC_DOSES_MG.get(canonicalize_match_token(pred_label)) or 10.0

            if dose_mg >= 1.0:
                dose_val = round(dose_mg, 2)
                dose_unit = "mg"
                dose_display = f"{dose_mg:g} mg"
            else:
                dose_val = round(dose_mg * 1000.0, 2)
                dose_unit = "μg"
                dose_display = f"{dose_mg * 1000.0:g} μg"

            # Pharmacokinetic free biophase concentration estimation (in nM) directly from node ADMET properties
            def _parse_num(v: Any, default: float) -> float:
                if v is None:
                    return default
                if isinstance(v, (int, float)):
                    return float(v)
                v_str = str(v).replace("%", "").strip()
                matches = re.findall(r"(\d+(?:\.\d+)?)", v_str)
                if matches:
                    nums = [float(x) for x in matches]
                    return sum(nums) / len(nums)
                return default

            mw = _parse_num(pred_attrs.get("molecular_weight"), 300.0)
            
            raw_f = pred_attrs.get("oral_bioavailability") or pred_attrs.get("bioavailability_f") or pred_attrs.get("bioavailability_pct")
            if raw_f is not None:
                f_val = _parse_num(raw_f, 80.0)
                f_bio = f_val if f_val <= 1.0 else f_val / 100.0
            else:
                f_bio = 0.80

            vd_lkg = _parse_num(pred_attrs.get("volume_of_distribution") or pred_attrs.get("volume_of_distribution_l_kg"), 2.5)

            raw_pb = pred_attrs.get("protein_binding") or pred_attrs.get("protein_binding_pct")
            if raw_pb is not None:
                pb_val = _parse_num(raw_pb, 60.0)
                pb_pct = pb_val if pb_val > 1.0 else pb_val * 100.0
            else:
                pb_pct = 60.0

            # Effective bioavailable fraction in tissue biophases (accounting for rapid albumin dissociation and cellular uptake)
            fu = max(0.005, min(1.0, 1.0 - (pb_pct / 100.0)))
            fu_eff = max(fu, min(1.0, 1.0 - (pb_pct / 100.0) * 0.98))
            c_free_nm = (dose_mg * f_bio * fu_eff * 1e6) / (vd_lkg * 70.0 * mw)

            # Calculate Biophysical Receptor Binding Drive W_i = [L_free] / K_i
            affinity_val = ki or ic50 or ec50
            if affinity_val and float(affinity_val) > 0:
                potency_weight = max(0.0001, c_free_nm / float(affinity_val))
            else:
                potency_weight = max(0.05, abs(mag) * (dose_mg / 10.0))

            incoming_compounds.append({
                "compound_id": pred,
                "compound_label": pred_label,
                "action": action_name,
                "edge_type": edge_type,
                "raw_vector": mag,
                "intrinsic_efficacy": efficacy,
                "affinity_ki": float(ki) if ki else None,
                "inhibition_ic50": float(ic50) if ic50 else None,
                "ec50": float(ec50) if ec50 else None,
                "dose_mg": round(dose_mg, 4),
                "dose_val": dose_val,
                "dose_unit": dose_unit,
                "dose_display": dose_display,
                "c_free_nm": round(c_free_nm, 3),
                "potency_weight": round(potency_weight, 4),
                "is_allosteric": is_allosteric,
                "is_pam": is_pam,
                "is_nam": is_nam,
                "is_antagonist": is_antagonist or is_inhibitor,
                "is_agonist": is_agonist,
            })

        if not incoming_compounds:
            continue

        target_label = node_attrs.get("label", node_id)
        total_potency = sum(c["potency_weight"] for c in incoming_compounds)

        # Total receptor saturation theta: W_total / (1.0 + W_total)
        receptor_saturation_pct = round((total_potency / (1.0 + total_potency)) * 100.0, 1)
        unoccupied_reserve_pct = round(max(0.0, 100.0 - receptor_saturation_pct), 1)

        # Compute fractional occupancy & individual effects
        for c in incoming_compounds:
            c["fractional_occupancy_pct"] = round((c["potency_weight"] / max(total_potency, 0.0001)) * 100.0, 1)
            c["absolute_saturation_pct"] = round((c["potency_weight"] / (1.0 + total_potency)) * 100.0, 1)
            c["individual_effect_pct"] = round(c["intrinsic_efficacy"] * 100.0, 1)

        # Calculate Net Combined Activation Score (-1.0 to +1.0) scaled by Absolute Receptor Saturation
        orthosteric_compounds = [c for c in incoming_compounds if not c["is_allosteric"]]
        allosteric_pams = [c for c in incoming_compounds if c["is_pam"]]
        allosteric_nams = [c for c in incoming_compounds if c["is_nam"]]

        ortho_total = sum(c["potency_weight"] for c in orthosteric_compounds)
        if orthosteric_compounds:
            ortho_net = sum(
                c["intrinsic_efficacy"] * c["potency_weight"]
                for c in orthosteric_compounds
            ) / (1.0 + ortho_total)
        else:
            ortho_net = 0.0

        # Apply allosteric modulators (ternary complex model)
        pam_multiplier = 1.0 + sum(
            c["intrinsic_efficacy"] * (c["potency_weight"] / (1.0 + c["potency_weight"]))
            for c in allosteric_pams
        )
        nam_multiplier = max(
            0.05,
            1.0 - sum(abs(c["intrinsic_efficacy"]) * (c["potency_weight"] / (1.0 + c["potency_weight"])) for c in allosteric_nams)
        )

        if orthosteric_compounds:
            net_score = ortho_net * pam_multiplier * nam_multiplier
        else:
            pam_score = sum(c["intrinsic_efficacy"] * (c["potency_weight"] / (1.0 + c["potency_weight"])) for c in allosteric_pams)
            nam_score = sum(c["intrinsic_efficacy"] * (c["potency_weight"] / (1.0 + c["potency_weight"])) for c in allosteric_nams)
            net_score = pam_score + nam_score

        net_score = max(-1.0, min(1.0, net_score))
        net_pct = round(net_score * 100.0, 1)

        has_agonists = any(c["is_agonist"] for c in incoming_compounds)
        has_antagonists = any(c["is_antagonist"] for c in incoming_compounds)
        has_opposing = has_agonists and has_antagonists
        has_synergistic = len([c for c in incoming_compounds if c["is_agonist"]]) > 1 or (has_agonists and bool(allosteric_pams))

        # Dominant compound
        dominant = max(incoming_compounds, key=lambda x: x["potency_weight"])

        # Determine receptor state classification
        if len(incoming_compounds) == 1:
            c0 = incoming_compounds[0]
            if c0["intrinsic_efficacy"] > 0.2:
                state_str = "Monotherapy Agonism / Activation"
            elif c0["intrinsic_efficacy"] < -0.2:
                state_str = "Monotherapy Blockade / Inhibition"
            else:
                state_str = "Monotherapy Modulation"
        elif has_opposing:
            if net_score > 0.15:
                state_str = "Competitive Attenuation (Agonist Dominant)"
            elif net_score < -0.15:
                state_str = "Competitive Blockade (Antagonist Dominant)"
            else:
                state_str = "Competitive Equilibrium / Balanced Antagonism"
        elif has_synergistic:
            if allosteric_pams:
                state_str = "Allosteric Potentiation / Synergistic Agonism"
            else:
                state_str = "Additive / Synergistic Agonism"
        elif net_score > 0.15:
            state_str = "Net Receptor Activation (Stimulated)"
        elif net_score < -0.15:
            state_str = "Net Receptor Blockade (Inhibited)"
        else:
            state_str = "Basal Equilibrium Tone"

        # Generate clinical pharmacological explanation
        if len(incoming_compounds) == 1:
            c0 = incoming_compounds[0]
            summary_text = (
                f"{c0['compound_label']} ({c0['dose_display']}) occupies {c0['absolute_saturation_pct']}% of {target_label}, "
                f"yielding an estimated {net_pct:+.1f}% functional signal modulation with {unoccupied_reserve_pct}% baseline reserve remaining."
            )
        elif has_opposing:
            agonists = [f"{c['compound_label']} ({c['dose_display']})" for c in incoming_compounds if c["is_agonist"]]
            antagonists = [f"{c['compound_label']} ({c['dose_display']})" for c in incoming_compounds if c["is_antagonist"]]
            summary_text = (
                f"Receptor Competition: {', '.join(agonists)} (Agonist) and {', '.join(antagonists)} (Antagonist) "
                f"compete for {receptor_saturation_pct}% total receptor saturation at {target_label}. {dominant['compound_label']} commands "
                f"{dominant['fractional_occupancy_pct']}% of occupied sites ({dominant['absolute_saturation_pct']}% absolute saturation), yielding a net activation of {net_pct:+.1f}%."
            )
        elif has_synergistic:
            comp_names = [f"{c['compound_label']} ({c['dose_display']})" for c in incoming_compounds]
            summary_text = (
                f"Synergistic Convergence: {', '.join(comp_names)} saturate {receptor_saturation_pct}% of {target_label}, "
                f"driving a unified net receptor activation of {net_pct:+.1f}%."
            )
        else:
            comp_names = [f"{c['compound_label']} ({c['dose_display']} • {c['absolute_saturation_pct']}% sat)" for c in incoming_compounds]
            summary_text = (
                f"Multi-Ligand Engagement: {', '.join(comp_names)} bind {target_label} ({receptor_saturation_pct}% saturation) with net activation of {net_pct:+.1f}%."
            )

        # Compute Dynamic Receptor Regulation (Desensitization / Downregulation / Upregulation)
        # Agonist occupancy drives homologous desensitization (GRK / beta-arrestin / internalization)
        # Antagonist occupancy drives compensatory target upregulation (Bmax increase)
        ago_occupancy = sum(c["absolute_saturation_pct"] for c in incoming_compounds if c["is_agonist"]) / 100.0
        ant_occupancy = sum(c["absolute_saturation_pct"] for c in incoming_compounds if c["is_antagonist"]) / 100.0

        is_gpcr = any(x in target_label.lower() for x in ["adrenergic", "receptor", "adrb", "adra", "at1", "5-ht", "dopamine", "opioid", "cannabinoid", "gaba", "muscarinic"])
        kappa_desens = 0.65 if is_gpcr else 0.25
        kappa_up = 0.25 if is_gpcr else 0.15

        rho_down = 1.0 / (1.0 + kappa_desens * (ago_occupancy ** 2))
        rho_up = 1.0 + kappa_up * ant_occupancy
        regulation_multiplier = round(rho_down * rho_up, 3)

        if ago_occupancy >= 0.50 and rho_down < 0.88:
            regulation_state = "Downregulated / Desensitized (Tachyphylaxis Risk)"
        elif ant_occupancy >= 0.50 and rho_up > 1.10:
            regulation_state = "Upregulated / Supersensitized (Rebound Sensitivity Risk)"
        else:
            regulation_state = "Homeostatic / Normal Receptor Density"

        results[node_id] = {
            "target_id": node_id,
            "target_label": target_label,
            "target_type": nt,
            "ligand_count": len(incoming_compounds),
            "has_multiple_ligands": len(incoming_compounds) > 1,
            "has_opposing_effects": has_opposing,
            "has_synergistic_effects": has_synergistic,
            "receptor_saturation_pct": receptor_saturation_pct,
            "unoccupied_reserve_pct": unoccupied_reserve_pct,
            "net_activation_score": round(net_score, 3),
            "net_activation": round(net_score, 3),
            "net_activation_pct": net_pct,
            "receptor_state": state_str,
            "dominant_compound": dominant["compound_label"],
            "regulation_state": regulation_state,
            "regulation_multiplier": regulation_multiplier,
            "compounds": incoming_compounds,
            "pharmacological_summary": summary_text,
        }

    return results

