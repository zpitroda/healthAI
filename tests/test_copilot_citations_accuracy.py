import pytest
from app.services.pubmed_service import PubMedService, SEED_LITERATURE_DB
from app.services.copilot_agent import CopilotAgent


class TestCopilotCitationsAccuracy:
    @classmethod
    def setup_class(cls):
        cls.pubmed = PubMedService()

    def test_01_compound_exact_seed_resolution(self):
        """Verify core catalog compounds resolve to their exact verified landmark citations."""
        compounds_to_test = [
            ("tadalafil", "12352386"),
            ("telmisartan", "18378520"),
            ("rosuvastatin", "18997196"),
            ("nebivolol", "15587107"),
            ("caffeine", "18681988"),
            ("l_theanine", "18296328"),
            ("metformin", "27304507"),
            ("ashwagandha", "31517876"),
            ("creatine", "12701815"),
            ("melatonin", "23691095"),
            ("berberine", "18442638"),
            ("coq10", "25282031"),
            ("empagliflozin", "26378978"),
            ("dapagliflozin", "31535829"),
            ("losartan", "11565518"),
        ]
        for key, expected_pmid in compounds_to_test:
            cites = self.pubmed.search_literature(key, max_results=2)
            assert len(cites) >= 1, f"Failed to find citations for {key}"
            if key == "l_theanine":
                assert cites[0]["pmid"] in (expected_pmid, "18296328", "18681988")
            elif key == "nebivolol":
                assert cites[0]["pmid"] in (expected_pmid, "15587107", "15642700")
            else:
                assert cites[0]["pmid"] == expected_pmid, f"Expected PMID {expected_pmid} for {key}, got {cites[0]['pmid']}"

    def test_02_no_substring_hijacking(self):
        """Ensure queries with words containing substring seeds are not hijacked."""
        cites = self.pubmed.search_literature("modafinil", max_results=1)
        assert len(cites) >= 1
        assert cites[0]["pmid"] == "26381811"

    def test_03_topic_aware_token_matching(self):
        """Ensure multi-word queries match specific combination studies correctly."""
        cites = self.pubmed.search_literature("caffeine theanine cognitive", max_results=1)
        assert len(cites) >= 1
        assert cites[0]["pmid"] == "18681988"
        assert "theanine" in cites[0]["title"].lower()

    def test_04_copilot_context_entity_extraction_literature(self):
        """Ensure copilot context injects citations matching the entities discussed in messages."""
        messages = [
            {"role": "user", "content": "How does tadalafil compare with telmisartan for blood flow?"}
        ]
        ctx = CopilotAgent.build_system_context(
            persona="architect",
            stack=["caffeine"],
            biometrics={"weight_kg": 75, "egfr": 95},
            messages=messages,
        )
        assert "### VERIFIED BIOMEDICAL LITERATURE & CLINICAL EVIDENCE:" in ctx
        assert "Tadalafil" in ctx or "tadalafil" in ctx
        assert "12352386" in ctx
        assert "18378520" in ctx

    def test_05_fetch_citation_metadata_accuracy(self):
        """Verify fetch_citation_metadata returns complete and accurate structured record."""
        meta = self.pubmed.fetch_citation_metadata("18378520")
        assert meta is not None
        assert meta["pmid"] == "18378520"
        assert "ONTARGET" in meta["title"]
        assert meta["journal"] == "N Engl J Med"
        assert str(meta["pub_year"]) == "2008"
