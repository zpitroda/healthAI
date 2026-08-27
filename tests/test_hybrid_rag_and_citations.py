import pytest
from app.services.pubmed_service import PubMedService, SEED_LITERATURE_DB
from app.services.copilot_agent import CopilotAgent
from app.services.stack_intent_engine import StackIntentEngine, SCRATCH_GOAL_BLUEPRINTS
from app.knowledge_graph.graph_db import get_graph_database


class TestHybridRagAndCitations:
    @classmethod
    def setup_class(cls):
        cls.pubmed = PubMedService()
        cls.graph_db = get_graph_database()

    def test_01_expanded_landmark_seeds(self):
        """Verify newly expanded landmark seeds resolve correctly."""
        expanded_seeds = [
            ("ezetimibe", "26039521"),
            ("citrus_bergamot", "24239156"),
            ("cabergoline", "10073800"),
            ("p5p", "6385842"),
            ("magnesium", "23853635"),
            ("fish_oil", "30415628"),
            ("nmn", "33888596"),
            ("bacopa", "11498727"),
            ("dhea", "15531705"),
            ("pregnenolone", "24467926"),
            ("oxandrolone", "10548543"),
            ("pramipexole", "9115206"),
        ]
        for key, expected_pmid in expanded_seeds:
            cites = self.pubmed.search_literature(key, max_results=1)
            assert len(cites) >= 1, f"Missing citation for {key}"
            assert cites[0]["pmid"] == expected_pmid, f"Expected PMID {expected_pmid} for {key}, got {cites[0]['pmid']}"

    def test_02_fetch_abstract(self):
        """Verify fetch_abstract returns structured abstract and publication metadata."""
        abstract_data = self.pubmed.fetch_abstract("26039521")
        assert abstract_data is not None
        assert abstract_data["pmid"] == "26039521"
        assert "IMPROVE-IT" in abstract_data["title"] or "Ezetimibe" in abstract_data["title"]
        assert abstract_data["abstract_text"] is not None
        assert len(abstract_data["abstract_text"]) > 20
        assert abstract_data["journal"] == "N Engl J Med"

    def test_03_hybrid_literature_search_service(self):
        """Verify hybrid_literature_search combines keyword matching and claim topics."""
        res = self.pubmed.hybrid_literature_search("ezetimibe ldl cardiovascular", entity_id="ezetimibe", max_results=3)
        assert res["count"] >= 1
        cites = res["citations"]
        assert any(c["pmid"] == "26039521" for c in cites)
        assert res["entity_id"] == "ezetimibe"

    def test_04_graph_db_search_hybrid_graph_and_literature(self):
        """Verify unified search_hybrid_graph_and_literature merges GraphRAG and literature search."""
        res = self.graph_db.search_hybrid_graph_and_literature(
            query="telmisartan cardiovascular nephroprotection",
            entity_ids=["telmisartan"],
            max_results=3,
        )
        assert res["query"] == "telmisartan cardiovascular nephroprotection"
        assert "telmisartan" in res["entity_ids"]
        assert res["citation_count"] >= 1
        assert any(c["pmid"] == "18378520" for c in res["citations_found"])
        assert "pkpd_profiles" in res

    def test_05_scratch_goal_blueprints_have_citations(self):
        """Verify all 8 goal taxonomy blueprints have verified PMIDs and citation strings."""
        for goal_id, blueprint in SCRATCH_GOAL_BLUEPRINTS.items():
            core = blueprint.get("core_compounds", [])
            ancillaries = blueprint.get("ancillaries", [])
            all_comps = core + ancillaries
            assert len(all_comps) > 0, f"Blueprint {goal_id} has no compounds"
            for c in all_comps:
                assert "pmid" in c and c["pmid"], f"Compound {c.get('key')} in blueprint {goal_id} missing PMID"
                assert "citation_str" in c and c["citation_str"], f"Compound {c.get('key')} in blueprint {goal_id} missing citation_str"

    def test_06_build_scratch_stack_proposal_citations(self):
        """Verify StackIntentEngine.build_scratch_stack_proposal attaches citations to output compounds."""
        proposal = StackIntentEngine.build_scratch_stack_proposal(
            goal_id="cognitive_focus",
            biometrics={"weight_kg": 80, "egfr": 100},
            preferences={"risk_tolerance": "balanced"},
        )
        assert proposal["goal_id"] == "cognitive_focus"
        comps = proposal["compounds"]
        assert len(comps) >= 3
        for c in comps:
            assert c.get("pmid") is not None, f"Compound {c['name']} missing PMID"
            assert c.get("citation_str") is not None, f"Compound {c['name']} missing citation_str"

    def test_07_candidate_recommendations_have_citations(self):
        """Verify get_evidence_based_recommendations returns candidate co-factors with attached PMIDs."""
        recs = CopilotAgent.get_evidence_based_recommendations(
            compounds=[{"key": "testosterone", "dose_mg": 200, "route": "intramuscular"}],
            biometrics={"weight_kg": 85, "egfr": 90, "alt_u_l": 30},
            protocol_goal="anabolic_physique",
        )
        assert len(recs) >= 1
        with_pmid = [r for r in recs if r.get("pmid")]
        assert len(with_pmid) >= 1, "Expected at least one candidate recommendation with a verified PMID"

    def test_08_copilot_react_tools_literature(self):
        """Verify CopilotAgent.execute_tool handles fetch_paper_abstract and hybrid_rag_search."""
        res_abstract = CopilotAgent.execute_tool("fetch_paper_abstract", {"pmid": "18378520"})
        assert "pmid" in res_abstract
        assert res_abstract["pmid"] == "18378520"
        assert "abstract_text" in res_abstract

        res_hybrid = CopilotAgent.execute_tool(
            "hybrid_rag_search",
            {"query": "citrus bergamot lipids", "entity_ids": ["citrus_bergamot"], "max_results": 2}
        )
        assert "citations_found" in res_hybrid
        assert res_hybrid["citation_count"] >= 1

    def test_09_copilot_system_context_candidate_citations(self):
        """Verify CopilotAgent.build_system_context injects verified candidate studies."""
        ctx = CopilotAgent.build_system_context(
            persona="architect",
            stack=["testosterone"],
            biometrics={"weight_kg": 80, "egfr": 95},
            protocol_goal="anabolic_physique",
            messages=[{"role": "user", "content": "How do I protect my lipids on cycle?"}],
        )
        assert "### VERIFIED BIOMEDICAL LITERATURE & CLINICAL EVIDENCE:" in ctx
        assert "### EVIDENCE-BASED CANDIDATE ADJACENCIES & CO-FACTORS (GRAPH-DERIVED):" in ctx
        assert "Verified Study:" in ctx or "PMID:" in ctx

    def test_10_deterministic_protocol_markdown_citations(self):
        """Verify format_deterministic_protocol_markdown renders PMIDs and citations."""
        proposal = StackIntentEngine.build_scratch_stack_proposal(
            goal_id="longevity_autophagy",
            biometrics={"weight_kg": 70, "egfr": 95},
        )
        md = CopilotAgent.format_deterministic_protocol_markdown(proposal, persona="architect")
        assert "PMID:" in md
        assert "Berberine" in md
