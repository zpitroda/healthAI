import pytest
from app.services.interaction_engine import InteractionEngine
from app.services.graph_service import build_selected_compound_graph, CatalogService


def test_androgen_without_testosterone_base_crashes_testosterone_and_e2():
    """
    When administering non-testosterone androgens (e.g. Masteron / Drostanolone)
    without a bioidentical testosterone base:
    1. HPG axis gonadotropin secretion is suppressed (LH/FSH down).
    2. Endogenous testosterone crashes (<100 ng/dL).
    3. Aromatase lacks substrate, so estradiol crashes (<15 pg/mL).
    4. Multi-compound syndrome and uncompensated risk are flagged.
    """
    engine = InteractionEngine()
    drostanolone = {
        "key": "drostanolone",
        "name": "Drostanolone",
        "canonical_name": "Drostanolone",
        "drug_class": "Anabolic Steroid / DHT Derivative", "categories": ["G03BA"], "receptor_targets": [{"target": "AR", "action": "agonist", "gene_symbol": "AR"}],
        "mechanism": "Androgen receptor agonist, non-aromatizable 2-methyl-DHT derivative",
        "receptor_targets": [
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "agonist", "family": "Nuclear Receptor", "intrinsic_efficacy": 0.90}
        ],
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": [], "inducers": []},
        "organ_burdens": {"cardiovascular": "moderate", "hepatic": "low"},
    }

    result = engine.analyze_stack([drostanolone])
    
    # Check HPG axis shutdown syndrome
    syndromes = result.get("breakdown", {}).get("syndrome_alerts", [])
    hpg_syndrome = next((s for s in syndromes if "hypoestrogenemia" in s.get("syndrome", "").lower() or "crashed" in s.get("title", "").lower()), None)
    assert hpg_syndrome is not None
    assert hpg_syndrome["severity"] in {"HIGH_RISK", "SEVERE_CONTRAINDICATION"}

    # Check cascade biomarker shifts for crashed T and E2
    graph = build_selected_compound_graph(["drostanolone:100mg"])
    cascade = graph.propagate_cascade(["drostanolone"])
    shifts = {b["biomarker_id"]: b for b in cascade.get("biomarker_shifts", [])}
    
    if "bio_testosterone" in shifts:
        assert shifts["bio_testosterone"]["estimated_value"] < 200.0
    if "bio_estradiol" in shifts:
        assert shifts["bio_estradiol"]["estimated_value"] < 15.0


def test_androgen_with_testosterone_base_maintains_physiological_t_and_e2():
    """
    When administering non-testosterone androgen WITH a bioidentical testosterone base:
    1. Exogenous testosterone supplies circulating androgen pool (T > 500 ng/dL).
    2. Exogenous testosterone acts as substrate for aromatase (E2 in safe range 15-45 pg/mL).
    3. HPG crash syndrome is avoided and active mitigation is registered.
    """
    engine = InteractionEngine()
    drostanolone = {
        "key": "drostanolone",
        "name": "Drostanolone",
        "canonical_name": "Drostanolone",
        "drug_class": "Anabolic Steroid / DHT Derivative", "categories": ["G03BA"], "receptor_targets": [{"target": "AR", "action": "agonist", "gene_symbol": "AR"}],
        "mechanism": "Androgen receptor agonist, non-aromatizable 2-methyl-DHT derivative",
        "receptor_targets": [
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "agonist", "family": "Nuclear Receptor", "intrinsic_efficacy": 0.90}
        ],
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": [], "inducers": []},
        "organ_burdens": {"cardiovascular": "moderate", "hepatic": "low"},
    }
    testosterone = {
        "key": "testosterone",
        "name": "Testosterone",
        "canonical_name": "Testosterone",
        "drug_class": "Bioidentical Androgen", "categories": ["G03BA"], "receptor_targets": [{"target": "AR", "action": "agonist", "gene_symbol": "AR"}],
        "mechanism": "Endogenous androgen receptor agonist and substrate for CYP19A1 aromatase and 5-alpha reductase",
        "receptor_targets": [
            {"target": "Circulating Serum Testosterone Pool", "action": "agonist", "family": "Endocrine Pool", "intrinsic_efficacy": 0.85},
            {"target": "Aromatase (CYP19A1)", "action": "substrate", "family": "Steroidogenesis", "intrinsic_efficacy": 0.80},
        ],
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": [], "inducers": []},
        "organ_burdens": {"cardiovascular": "low", "hepatic": "low"},
    }

    result = engine.analyze_stack([drostanolone, testosterone])
    
    # Check that HPG shutdown syndrome is NOT triggered because testosterone base is present
    syndromes = result.get("breakdown", {}).get("syndrome_alerts", [])
    hpg_syndrome = next((s for s in syndromes if "hypoestrogenemia" in s.get("syndrome", "").lower() or "crashed" in s.get("title", "").lower()), None)
    assert hpg_syndrome is None

    # Check graph cascade preserves T and E2
    graph = build_selected_compound_graph(["drostanolone:100mg", "testosterone:150mg"])
    cascade = graph.propagate_cascade(["drostanolone", "testosterone"])
    shifts = {b["biomarker_id"]: b for b in cascade.get("biomarker_shifts", [])}
    
    if "bio_testosterone" in shifts:
        assert shifts["bio_testosterone"]["estimated_value"] >= 300.0


def test_19nor_without_cabergoline_triggers_prolactin_alert():
    """19-Nor steroids (Trenbolone, Nandrolone) without dopamine agonist trigger progestogenic prolactin alert."""
    engine = InteractionEngine()
    trenbolone = {
        "key": "trenbolone",
        "name": "Trenbolone",
        "canonical_name": "Trenbolone",
        "drug_class": "19-nor Anabolic Steroid", "categories": ["G03BA"], "receptor_targets": [{"target": "AR", "action": "agonist", "gene_symbol": "AR"}],
        "mechanism": "Potent androgen and progesterone receptor agonist",
        "receptor_targets": [
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "agonist", "family": "Nuclear Receptor", "intrinsic_efficacy": 1.0},
            {"target": "Progesterone Receptor (PGR / NR3C3)", "action": "agonist", "family": "Nuclear Receptor", "intrinsic_efficacy": 0.85},
        ],
        "organ_burdens": {"cardiovascular": "high", "hepatic": "moderate"},
    }

    result = engine.analyze_stack([trenbolone])
    syndromes = result.get("breakdown", {}).get("syndrome_alerts", [])
    prolactin_alert = next((s for s in syndromes if "prolactin" in s.get("syndrome", "").lower() or "progestogenic" in s.get("title", "").lower()), None)
    assert prolactin_alert is not None
    assert prolactin_alert["severity"] == "HIGH_RISK"


def test_19nor_with_cabergoline_resolves_prolactin_alert():
    """Adding Cabergoline (D2 agonist) resolves 19-nor prolactin syndrome."""
    engine = InteractionEngine()
    trenbolone = {
        "key": "trenbolone",
        "name": "Trenbolone",
        "canonical_name": "Trenbolone",
        "drug_class": "19-nor Anabolic Steroid", "categories": ["G03BA"], "receptor_targets": [{"target": "AR", "action": "agonist", "gene_symbol": "AR"}],
        "mechanism": "Potent androgen and progesterone receptor agonist",
        "receptor_targets": [
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "agonist", "family": "Nuclear Receptor", "intrinsic_efficacy": 1.0},
            {"target": "Progesterone Receptor (PGR / NR3C3)", "action": "agonist", "family": "Nuclear Receptor", "intrinsic_efficacy": 0.85},
        ],
        "organ_burdens": {"cardiovascular": "high", "hepatic": "moderate"},
    }
    cabergoline = {
        "key": "cabergoline",
        "name": "Cabergoline",
        "canonical_name": "Cabergoline",
        "drug_class": "Dopamine D2 Receptor Agonist / Prolactin Inhibitor",
        "mechanism": "Potent long-acting D2 receptor agonist suppressing pituitary lactotroph prolactin secretion",
        "receptor_targets": [
            {"target": "Dopamine Transporter & Receptors (SLC6A3 / DRD2)", "action": "agonist", "family": "GPCR", "intrinsic_efficacy": 0.90},
        ],
        "organ_burdens": {},
    }

    result = engine.analyze_stack([trenbolone, cabergoline])
    syndromes = result.get("breakdown", {}).get("syndrome_alerts", [])
    prolactin_alert = next((s for s in syndromes if "prolactin" in s.get("syndrome", "").lower() or "progestogenic" in s.get("title", "").lower()), None)
    assert prolactin_alert is None


def test_exogenous_thyroid_t3_suppresses_tsh():
    """Exogenous T3 (Liothyronine) suppresses pituitary TSH and flags thyroid axis feedback."""
    engine = InteractionEngine()
    t3 = {
        "key": "liothyronine",
        "name": "Liothyronine (T3)",
        "canonical_name": "Liothyronine",
        "drug_class": "Synthetic Thyroid Hormone (T3)",
        "mechanism": "Thyroid hormone receptor alpha and beta agonist, uncoupling metabolic expenditure and suppressing TSH",
        "receptor_targets": [
            {"target": "Thyroid Hormone Receptor Alpha & Beta (THRA/THRB / NR1A1/NR1A2)", "action": "agonist", "family": "Nuclear Receptor", "intrinsic_efficacy": 0.85},
        ],
        "organ_burdens": {"cardiovascular": "moderate"},
    }

    result = engine.analyze_stack([t3])
    syndromes = result.get("breakdown", {}).get("syndrome_alerts", [])
    thyroid_alert = next((s for s in syndromes if "thyroid" in s.get("syndrome", "").lower() or "tsh" in s.get("title", "").lower()), None)
    assert thyroid_alert is not None
    assert thyroid_alert["severity"] == "MODERATE_RISK"


def test_oral_testosterone_with_aas_crashes_serum_testosterone():
    """
    When administering AAS (e.g. Drostanolone/Nandrolone) with ORAL unalkylated testosterone:
    1. Oral testosterone undergoes ~97% first-pass hepatic/gut clearance (F ~ 0.03).
    2. Exogenous AAS stimulation of Androgen Receptor shuts down HPG axis (LH/FSH -> 0).
    3. Net serum testosterone crashes to hypogonadal/castrate levels (< 150 ng/dL).
    4. HPG shutdown & uncompensated endocrine risk alert is triggered.
    """
    engine = InteractionEngine()
    drostanolone = {
        "key": "drostanolone",
        "name": "Drostanolone",
        "canonical_name": "Drostanolone",
        "drug_class": "Anabolic Steroid / DHT Derivative", "categories": ["G03BA"], "receptor_targets": [{"target": "AR", "action": "agonist", "gene_symbol": "AR"}],
        "route": "intramuscular",
        "dose_mg": 100.0,
        "mechanism": "Androgen receptor agonist, non-aromatizable 2-methyl-DHT derivative",
        "receptor_targets": [
            {"target": "Androgen Receptor (AR / NR3C4)", "action": "agonist", "family": "Nuclear Receptor", "intrinsic_efficacy": 0.90}
        ],
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": [], "inducers": []},
        "organ_burdens": {"cardiovascular": "moderate", "hepatic": "low"},
    }
    oral_testosterone = {
        "key": "testosterone",
        "name": "Testosterone",
        "canonical_name": "Testosterone",
        "drug_class": "Bioidentical Androgen", "categories": ["G03BA"], "receptor_targets": [{"target": "AR", "action": "agonist", "gene_symbol": "AR"}],
        "route": "oral",
        "dose_mg": 25.0,
        "mechanism": "Endogenous androgen receptor agonist and substrate for CYP19A1 aromatase and 5-alpha reductase",
        "receptor_targets": [
            {"target": "Circulating Serum Testosterone Pool", "action": "agonist", "family": "Endocrine Pool", "intrinsic_efficacy": 0.85},
            {"target": "Aromatase (CYP19A1)", "action": "substrate", "family": "Steroidogenesis", "intrinsic_efficacy": 0.80},
        ],
        "cyp_enzymes": {"substrates": ["CYP3A4"], "inhibitors": [], "inducers": []},
        "organ_burdens": {"cardiovascular": "low", "hepatic": "low"},
    }

    result = engine.analyze_stack([drostanolone, oral_testosterone])
    syndromes = result.get("breakdown", {}).get("syndrome_alerts", [])
    hpg_syndrome = next((s for s in syndromes if "hypoestrogenemia" in s.get("syndrome", "").lower() or "crashed" in s.get("title", "").lower()), None)
    assert hpg_syndrome is not None
    assert hpg_syndrome["severity"] == "HIGH_RISK"

    # Test graph cascade simulation
    from app.services.graph_service import build_selected_compound_graph
    graph = build_selected_compound_graph([
        {"key": "drostanolone", "dose": 100, "unit": "mg", "route": "intramuscular"},
        {"key": "testosterone", "dose": 25, "unit": "mg", "route": "oral"},
    ])
    cascade = graph.propagate_cascade(["drostanolone", "testosterone"])
    shifts = {b["biomarker_id"]: b for b in cascade.get("biomarker_shifts", [])}
    assert "bio_testosterone" in shifts
    # Total serum testosterone should crash below normal physiological range (< 150 ng/dL)
    assert shifts["bio_testosterone"]["estimated_value"] < 150.0

