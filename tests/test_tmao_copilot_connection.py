import pytest
from app.services.catalog_service import CatalogService
from app.services.copilot_agent import CopilotAgent
from app.services.stack_intent_engine import StackIntentEngine
from app.services.interaction_engine import InteractionEngine


def test_catalog_fuzzy_matching_resolves_alison_to_allicin():
    """Verifies that fuzzy/phonetic near-misses like 'alison' resolve dynamically to 'allicin'."""
    catalog = CatalogService()
    comp = catalog.get_compound("alison", auto_enrich=False)
    assert comp is not None, "Fuzzy match for 'alison' failed to resolve"
    assert comp.get("key") == "allicin"
    assert "Allicin" in comp.get("name", "")


def test_catalog_find_compounds_by_target():
    """Verifies dynamic first-principles reverse lookup of target inhibitors."""
    catalog = CatalogService()
    inhibitors = catalog.find_compounds_by_target(
        "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)",
        action="inhibitor"
    )
    assert len(inhibitors) > 0
    keys = [c["key"] for c in inhibitors]
    assert "allicin" in keys


def test_copilot_extract_entities_from_messages():
    """Verifies that Copilot extracts compound keys, biomarkers (e.g. bio_tmao), and targets from user messages."""
    messages = [
        {"role": "user", "content": "When I have oral l-carnitine in my stack how do I lower TMAO or should I take alison?"}
    ]
    extracted = CopilotAgent.extract_entities_from_messages(messages)
    assert "l_carnitine" in extracted or "allicin" in extracted
    assert "bio_tmao" in extracted or "allicin" in extracted


def test_copilot_get_evidence_based_recommendations_for_oral_carnitine():
    """Verifies that oral L-carnitine triggers an evidence-based recommendation for Allicin from first principles."""
    compounds = [
        {
            "key": "l_carnitine",
            "name": "L-Carnitine",
            "dose_mg": 1000.0,
            "route": "oral",
            "receptor_targets": [
                {
                    "target": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)",
                    "action": "substrate",
                    "family": "Microbial Cleavage",
                    "is_microbial": True,
                },
                {
                    "target": "Carnitine Palmitoyltransferase (CPT1A / CPT2)",
                    "action": "agonist",
                    "family": "Mitochondrial Fatty Acid Transport",
                },
            ]
        }
    ]
    recs = CopilotAgent.get_evidence_based_recommendations(
        compounds=compounds,
        biometrics={"blood_pressure": 120, "alt_u_l": 25}
    )
    rec_keys = [r["key"] for r in recs]
    assert "allicin" in rec_keys, f"Expected 'allicin' in recommendations, got: {rec_keys}"
    
    alli_rec = next(r for r in recs if r["key"] == "allicin")
    assert "TMA-Lyase" in alli_rec["target"] or "CntA" in alli_rec["target"] or "Gut Microbiota" in alli_rec["target"]
    assert "TMAO" in alli_rec["clinical_purpose"] or "TMA" in alli_rec["clinical_purpose"]


def test_stack_intent_engine_detects_tmao_therapeutic_gap():
    """Verifies that StackIntentEngine detects the uncompensated microbial TMAO conversion gap."""
    compounds = [
        {
            "key": "l_carnitine",
            "name": "L-Carnitine",
            "dose_mg": 1000.0,
            "route": "oral",
            "receptor_targets": [
                {
                    "target": "Gut Microbiota Carnitine TMA-Lyase (CntA/CntB / yeaW/yeaX)",
                    "action": "substrate",
                }
            ]
        }
    ]
    res = StackIntentEngine.analyze(
        compounds=compounds,
        biometrics={},
    )
    gaps = res.get("therapeutic_gaps", [])
    tma_gaps = [g for g in gaps if "TMAO" in g.get("axis", "") or "Microbial" in g.get("axis", "")]
    assert len(tma_gaps) > 0, "Expected a Gastrointestinal / Microbial TMAO Axis gap"
    assert any("allicin" in s for s in tma_gaps[0].get("cofactor_search_terms", []))


def test_copilot_synthesize_deterministic_fallback_for_tmao():
    """Verifies that fallback synthesis for lowering TMAO returns Allicin guidance and action card."""
    md, action_card = CopilotAgent.synthesize_deterministic_fallback_response(
        user_query="How do I lower TMAO when taking oral L-carnitine?",
        persona="consultant",
        stack_list=["l_carnitine:1000mg:oral"],
        biometrics={},
    )
    assert "Allicin" in md
    assert "CntA/CntB" in md or "TMA-Lyase" in md or "TMA" in md
    assert action_card is not None
    assert any(item.get("key") == "allicin" for item in action_card.get("add", []))


def test_oral_carnitine_does_not_falsely_trigger_p5p_or_19nor():
    """Verifies that oral L-carnitine (dietary supplement) does NOT falsely trigger 19-nor prolactin gaps or P-5-P."""
    compounds = [
        {
            "key": "l_carnitine",
            "name": "L-Carnitine",
            "dose_mg": 1000.0,
            "route": "oral",
            "drug_class": "Dietary Supplement / Chemical Compound",
        }
    ]
    features = StackIntentEngine._extract_pharmacological_features(compounds)
    assert not features["has_19nor_progestogenic"], "L-carnitine should not trigger 19-nor flag"
    assert not features["has_androgens"], "L-carnitine should not trigger androgen flag"
    
    intent_res = StackIntentEngine.analyze(compounds=compounds, biometrics={})
    gaps = intent_res.get("therapeutic_gaps", [])
    assert not any("prolactin" in str(g).lower() for g in gaps), "No prolactin gap should be present"
    assert not any("p5p" in str(g).lower() for g in gaps), "No P-5-P recommendation should be present"

    recs = CopilotAgent.get_evidence_based_recommendations(compounds=compounds, biometrics={})
    rec_keys = [r["key"] for r in recs]
    assert "p5p" not in rec_keys, "P-5-P must not be recommended when only L-carnitine is in the stack"
    assert "allicin" in rec_keys, "Allicin should be recommended for oral L-carnitine"

