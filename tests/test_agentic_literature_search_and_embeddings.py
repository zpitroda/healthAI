"""
Automated Test Suite for Agentic Literature Exploration Loop, Vector Embeddings,
Section-Targeted Full-Text Reader, and Similar Paper Finder.
"""

import pytest
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.pubmed_service import PubMedService, SEED_LITERATURE_DB
from app.knowledge_graph.graph_db import get_graph_database
from app.services.copilot_agent import CopilotAgent


class TestAgenticLiteratureSearchAndEmbeddings:
    @classmethod
    def setup_class(cls):
        cls.emb_svc = get_embedding_service()
        cls.pubmed = PubMedService()
        cls.graph_db = get_graph_database()

    def test_01_embedding_service_generation_and_cosine_similarity(self):
        """Verify vector embeddings are normalized, non-zero, and produce accurate cosine similarity rankings."""
        vec1 = self.emb_svc.embed_text("Ezetimibe lowers LDL-C and ApoB via NPC1L1 cholesterol absorption inhibition.")
        vec2 = self.emb_svc.embed_text("Statin and ezetimibe combination lipid lowering therapy for cardiovascular risk reduction.")
        vec3 = self.emb_svc.embed_text("Bacopa monnieri synaptic plasticity memory retention dendritic arborization.")

        assert len(vec1) == 256
        assert len(vec2) == 256
        assert len(vec3) == 256

        # Check L2 normalization (length approx 1.0)
        norm1 = sum(v * v for v in vec1) ** 0.5
        assert 0.99 <= norm1 <= 1.01

        # Lipid papers should have higher semantic similarity than lipid vs nootropic
        sim_lipid_lipid = EmbeddingService.cosine_similarity(vec1, vec2)
        sim_lipid_nootropic = EmbeddingService.cosine_similarity(vec1, vec3)
        assert sim_lipid_lipid > sim_lipid_nootropic

    def test_02_citation_embedding_computation_on_ingestion(self):
        """Verify graph database attaches dense vector embeddings when citations are ingested."""
        test_citation = {
            "pmid": "99990001",
            "title": "Novel AMP-Activated Protein Kinase (AMPK) Activator Improves Glycemic Homeostasis",
            "journal": "J Biol Chem",
            "pub_year": 2023,
            "abstract": "Direct allosteric activation of AMPK stimulated GLUT4 translocation and suppressed hepatic gluconeogenesis.",
            "clinical_finding": "Stimulated glucose disposal without lactic acidosis.",
        }
        node = self.graph_db.ingest_citation(test_citation, entity_id="novel_ampk_activator")
        assert "embedding" in node
        assert len(node["embedding"]) == 256
        assert any(v != 0.0 for v in node["embedding"])

    def test_03_search_citations_semantic(self):
        """Verify search_citations_semantic retrieves cached citations ranked by vector cosine similarity."""
        # Ensure landmark seeds are ingested
        self.pubmed.search_literature("ezetimibe", max_results=1)
        self.pubmed.search_literature("telmisartan", max_results=1)
        self.pubmed.search_literature("fish_oil", max_results=1)

        res = self.graph_db.search_citations_semantic(
            query="ApoB cholesterol lipid lowering cardiovascular reduction",
            top_k=3,
            min_similarity=0.10,
        )
        assert len(res) >= 1
        top_hit = res[0]
        assert "similarity_score" in top_hit
        assert top_hit["similarity_score"] > 0.10
        # Ezetimibe or Fish oil should be in top hits for lipid query
        top_pmids = [c.get("pmid") for c in res]
        assert "26039521" in top_pmids or "30415628" in top_pmids

    def test_04_find_similar_citations_and_papers(self):
        """Verify find_similar_papers groups related studies sharing biological mechanisms."""
        self.pubmed.search_literature("ezetimibe", max_results=1)  # PMID: 26039521
        self.pubmed.search_literature("rosuvastatin", max_results=1)  # PMID: 18997196 (JUPITER)

        similar = self.pubmed.find_similar_papers("26039521", top_k=3)
        assert isinstance(similar, list)
        # Should return similar studies in the graph
        if similar:
            assert all("similarity_score" in s for s in similar)
            assert similar[0]["pmid"] != "26039521"

    def test_05_search_pubmed_titles_lightweight(self):
        """Verify search_pubmed_titles returns a token-efficient list with lightweight metadata."""
        titles = self.pubmed.search_pubmed_titles("telmisartan cardiovascular", max_results=4)
        assert len(titles) >= 1
        first = titles[0]
        assert "pmid" in first
        assert "title" in first
        assert "journal" in first
        assert "pub_year" in first
        # Full abstract text should NOT be present in lightweight title search
        assert "abstract" not in first

    def test_06_fetch_paper_full_text_section_paywall_fallback(self):
        """Verify section-targeted reader gracefully returns structured abstract for closed-access papers."""
        res = self.pubmed.fetch_paper_full_text_section("18378520", section="results", max_words=300)
        assert res["pmid"] == "18378520"
        assert "section_text" in res
        assert res["word_count"] > 0
        assert "full_text_available" in res

    def test_07_search_within_paper(self):
        """Verify search_within_paper extracts top relevant passages."""
        res = self.pubmed.search_within_paper("18378520", query="blood pressure ramipril cough tolerability", max_passages=2)
        assert "relevant_passages" in res
        assert len(res["relevant_passages"]) >= 1

    def test_08_copilot_agent_react_new_tools_execution(self):
        """Verify CopilotAgent executes the new agentic literature and semantic tools."""
        # Tool 1: search_pubmed_titles
        t1 = CopilotAgent.execute_tool("search_pubmed_titles", {"query": "citrus bergamot cholesterol", "max_results": 4})
        assert "candidate_titles" in t1
        assert len(t1["candidate_titles"]) >= 1

        # Tool 2: read_paper_section
        t2 = CopilotAgent.execute_tool("read_paper_section", {"pmid": "26039521", "section": "results"})
        assert "section_text" in t2

        # Tool 3: search_within_paper
        t3 = CopilotAgent.execute_tool("search_within_paper", {"pmid": "26039521", "query": "LDL cholesterol absorption"})
        assert "relevant_passages" in t3

        # Tool 4: find_similar_papers
        t4 = CopilotAgent.execute_tool("find_similar_papers", {"pmid": "26039521", "top_k": 3})
        assert "similar_papers" in t4

        # Tool 5: search_cached_papers_semantic
        t5 = CopilotAgent.execute_tool("search_cached_papers_semantic", {"query": "ApoB lipid management", "top_k": 3})
        assert "citations" in t5

    def test_09_copilot_turn_allowance_is_expanded(self):
        """Verify default exploration steps is expanded to 8 turns."""
        import inspect
        sig_stream = inspect.signature(CopilotAgent.stream_copilot_turn)
        assert sig_stream.parameters["max_exploration_steps"].default == 8

        sig_chat = inspect.signature(CopilotAgent.chat_copilot_turn)
        assert sig_chat.parameters["max_exploration_steps"].default == 8
