from __future__ import annotations

import logging
import re
import threading
import time
from enum import Enum
from typing import Any, Dict, List, Optional
import httpx
from cachetools import LRUCache

from app.services.live_enrichment import get_shared_http_client

logger = logging.getLogger("healthai.modality_resolver")


class SubstanceModality(str, Enum):
    SMALL_MOLECULE = "small_molecule"
    BIOLOGIC_ANTIBODY = "biologic_antibody"
    PEPTIDE = "peptide"
    COMBINATION_DRUG = "combination_drug"
    BOTANICAL_NATURAL = "botanical_natural"
    RADIOPHARMACEUTICAL = "radiopharmaceutical"
    CELL_GENE_THERAPY = "cell_gene_therapy"
    VACCINE = "vaccine"
    MINERAL_ELECTROLYTE = "mineral_electrolyte"
    UNKNOWN = "unknown"


_MODALITY_CACHE: LRUCache = LRUCache(maxsize=3000)
_MODALITY_LOCK = threading.Lock()
MODALITY_CACHE_TTL_SECONDS = 3600.0 * 12  # 12 hours


class ModalityResolver:
    """
    Deterministic Substance Modality & Classification Service.
    Queries authoritative biomedical registries:
    1. NCATS Global Substance Registration System (G-SRS / UNII API)
    2. NLM RxNorm Term Types & Ingredient Graph
    3. EMBL-EBI ChEMBL Molecule Types & Biotherapeutics
    4. OpenFDA DailyMed Established Pharmacologic Classes (EPC)
    """

    def __init__(self, timeout_seconds: float = 7.5, client: Optional[httpx.Client] = None):
        self.timeout = timeout_seconds
        self._custom_client = client

    def _client(self) -> httpx.Client:
        if self._custom_client and not self._custom_client.is_closed:
            return self._custom_client
        return get_shared_http_client(self.timeout)

    def classify_substance(
        self,
        name_or_key: str,
        rxcui: Optional[str] = None,
        chembl_id: Optional[str] = None,
        openfda_meta: Optional[Dict[str, Any]] = None,
        molecular_weight: Optional[float] = None,
        network_lookup: bool = True,
    ) -> Dict[str, Any]:
        """
        Deterministically classifies a substance into an authoritative SubstanceModality.
        When network_lookup=False (e.g. during live typeahead / candidate scoring), executes
        instant zero-latency heuristic classification (< 0.05ms) without remote network requests.
        """
        cleaned = str(name_or_key or "").strip().lower()
        if not cleaned:
            return {
                "modality": SubstanceModality.UNKNOWN,
                "confidence": 0.0,
                "evidence_source": "none",
                "details": {},
                "is_combination": False,
                "is_biologic": False,
                "is_peptide": False,
            }

        cache_key = f"{cleaned}:{rxcui or ''}:{chembl_id or ''}"
        with _MODALITY_LOCK:
            if cache_key in _MODALITY_CACHE:
                cached_res, t_cached = _MODALITY_CACHE[cache_key]
                if time.time() - t_cached < MODALITY_CACHE_TTL_SECONDS:
                    return dict(cached_res)
                _MODALITY_CACHE.pop(cache_key, None)

        result: Dict[str, Any] = {
            "modality": SubstanceModality.SMALL_MOLECULE,
            "confidence": 0.8,
            "evidence_source": "default",
            "details": {},
            "substance_class": "Chemical",
            "is_combination": False,
            "is_biologic": False,
            "is_peptide": False,
        }

        # 0a. Deterministic USAN / INN Stem Detection (International Nonproprietary Name rules)
        stem_matched = False
        if cleaned.endswith("mab") or any(cleaned.endswith(suffix) for suffix in ["-mab", "zumab", "ximab", "mumab", "-pmph", "-adaz", "-bwwd"]):
            result["modality"] = SubstanceModality.BIOLOGIC_ANTIBODY
            result["is_biologic"] = True
            result["evidence_source"] = "WHO INN / USAN Stem (-mab)"
            result["confidence"] = 1.0
            stem_matched = True
        elif cleaned.endswith("cept"):
            result["modality"] = SubstanceModality.BIOLOGIC_ANTIBODY
            result["is_biologic"] = True
            result["evidence_source"] = "WHO INN / USAN Stem (-cept)"
            result["confidence"] = 1.0
            stem_matched = True
        elif cleaned.endswith("tide") or cleaned.endswith("glutide"):
            result["modality"] = SubstanceModality.PEPTIDE
            result["is_peptide"] = True
            result["evidence_source"] = "WHO INN / USAN Stem (-tide)"
            result["confidence"] = 1.0
            stem_matched = True

        if stem_matched:
            with _MODALITY_LOCK:
                _MODALITY_CACHE[cache_key] = (result, time.time())
            return result

        # Check OpenFDA Established Pharmacologic Class (EPC) & MeSH
        epc_list = (openfda_meta or {}).get("pharm_class_epc", [])
        moa_list = (openfda_meta or {}).get("pharm_class_moa", [])
        all_classes = [str(c).lower() for c in (epc_list + moa_list)]

        for c in all_classes:
            if any(term in c for term in ["monoclonal antibody", "antibody-drug conjugate", "directed antibody"]):
                result["modality"] = SubstanceModality.BIOLOGIC_ANTIBODY
                result["is_biologic"] = True
                result["evidence_source"] = "OpenFDA EPC"
                result["confidence"] = 1.0
                break
            elif "vaccine" in c:
                result["modality"] = SubstanceModality.VACCINE
                result["evidence_source"] = "OpenFDA EPC"
                result["confidence"] = 1.0
                break
            elif "radiopharmaceutical" in c or "radioactive diagnostic" in c:
                result["modality"] = SubstanceModality.RADIOPHARMACEUTICAL
                result["evidence_source"] = "OpenFDA EPC"
                result["confidence"] = 1.0
                break
            elif any(term in c for term in ["cellular therapy", "gene therapy", "chimeric antigen receptor"]):
                result["modality"] = SubstanceModality.CELL_GENE_THERAPY
                result["evidence_source"] = "OpenFDA EPC"
                result["confidence"] = 1.0
                break

        # Fast heuristic checks if network lookup is disabled (used during live search typeahead)
        if not network_lookup:
            if any(term in cleaned for term in ["extract", "herb", "botanical", "phytochemical", "root", "leaf", "bark", "berry"]):
                result["modality"] = SubstanceModality.BOTANICAL_NATURAL
                result["is_botanical"] = True
                result["evidence_source"] = "Fast Botanical Keyword Heuristic"
                result["confidence"] = 0.9
            elif any(term in cleaned for term in [" + ", " / ", "combo", "combination"]):
                result["modality"] = SubstanceModality.COMBINATION_DRUG
                result["is_combination"] = True
                result["evidence_source"] = "Fast Combination Keyword Heuristic"
                result["confidence"] = 0.9
            elif molecular_weight and float(molecular_weight) > 10000:
                result["modality"] = SubstanceModality.BIOLOGIC_ANTIBODY
                result["is_biologic"] = True
                result["evidence_source"] = "Molecular Weight Heuristic (>10kDa)"
                result["confidence"] = 0.9
            elif molecular_weight and 1200 < float(molecular_weight) <= 10000:
                result["modality"] = SubstanceModality.PEPTIDE
                result["is_peptide"] = True
                result["evidence_source"] = "Molecular Weight Heuristic (Peptide Range)"
                result["confidence"] = 0.85
            return result

        client = self._client()

        # 0b. Deterministic Multi-Ingredient Combination Decomposition Check
        try:
            from app.services.rxnorm_graph_decomposer import RxNormGraphDecomposer
            decomposer = RxNormGraphDecomposer(client=client)
            decomp = decomposer.decompose_product(rxcui or cleaned)
            if decomp.get("is_combination"):
                result["modality"] = SubstanceModality.COMBINATION_DRUG
                result["is_combination"] = True
                result["evidence_source"] = "RxNorm / DailyMed Combination Graph"
                result["confidence"] = 1.0
                result["details"]["ingredients"] = decomp.get("ingredients", [])
                with _MODALITY_LOCK:
                    _MODALITY_CACHE[cache_key] = (result, time.time())
                return result
        except Exception as e:
            logger.debug("Decomposition check error in modality resolver for %s: %s", cleaned, e)

        # 0c. Deterministic Botanical & Phytochemical Complex Resolution (NCBI MeSH Tree B01)
        try:
            from app.services.botanical_resolver import BotanicalResolver
            bot_resolver = BotanicalResolver(timeout_seconds=self.timeout, client=client)
            bot_res = bot_resolver.resolve_botanical(cleaned)
            if bot_res and bot_res.get("is_botanical"):
                result["modality"] = SubstanceModality.BOTANICAL_NATURAL
                result["evidence_source"] = "NCBI MeSH Botanical Taxonomy (Tree B01)"
                result["confidence"] = 1.0
                result["details"]["botanical"] = bot_res
                with _MODALITY_LOCK:
                    _MODALITY_CACHE[cache_key] = (result, time.time())
                return result
        except Exception as e:
            logger.debug("Botanical check error in modality resolver for %s: %s", cleaned, e)

        # 1. Check OpenFDA Established Pharmacologic Class (EPC) & MeSH
        epc_list = (openfda_meta or {}).get("pharm_class_epc", [])
        moa_list = (openfda_meta or {}).get("pharm_class_moa", [])
        all_classes = [str(c).lower() for c in (epc_list + moa_list)]

        for c in all_classes:
            if any(term in c for term in ["monoclonal antibody", "antibody-drug conjugate", "directed antibody"]):
                result["modality"] = SubstanceModality.BIOLOGIC_ANTIBODY
                result["is_biologic"] = True
                result["evidence_source"] = "OpenFDA EPC"
                result["confidence"] = 1.0
                break
            elif "vaccine" in c:
                result["modality"] = SubstanceModality.VACCINE
                result["evidence_source"] = "OpenFDA EPC"
                result["confidence"] = 1.0
                break
            elif "radiopharmaceutical" in c or "radioactive diagnostic" in c:
                result["modality"] = SubstanceModality.RADIOPHARMACEUTICAL
                result["evidence_source"] = "OpenFDA EPC"
                result["confidence"] = 1.0
                break
            elif any(term in c for term in ["cellular therapy", "gene therapy", "chimeric antigen receptor"]):
                result["modality"] = SubstanceModality.CELL_GENE_THERAPY
                result["evidence_source"] = "OpenFDA EPC"
                result["confidence"] = 1.0
                break

        # 2. Check ChEMBL Molecule Record if known or queryable
        if result["confidence"] < 1.0 and chembl_id:
            try:
                url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/{chembl_id}.json"
                resp = client.get(url)
                if resp.status_code == 200:
                    m = resp.json()
                    m_type = str(m.get("molecule_type") or "").strip().lower()
                    biotherapeutic = bool(m.get("biotherapeutic"))
                    nat_product = bool(m.get("natural_product"))

                    if m_type in ("antibody", "protein") or biotherapeutic:
                        result["modality"] = SubstanceModality.BIOLOGIC_ANTIBODY
                        result["is_biologic"] = True
                        result["evidence_source"] = "ChEMBL Molecule Type"
                        result["confidence"] = 1.0
                    elif nat_product and m_type == "small molecule":
                        result["details"]["is_natural_product"] = True
            except Exception as e:
                logger.debug("ChEMBL modality lookup error for %s: %s", chembl_id, e)

        # 3. Query NCATS Global Substance Registration System (G-SRS) by Name
        if result["confidence"] < 1.0:
            try:
                url = "https://gsrs.ncats.nih.gov/api/v1/substances/search"
                resp = client.get(url, params={"q": f'root_names_name:"{cleaned}"', "top": 1})
                if resp.status_code == 200:
                    data = resp.json()
                    substances = data.get("content", [])
                    if substances:
                        sub = substances[0]
                        s_class = str(sub.get("substanceClass") or "").strip().lower()
                        result["substance_class"] = s_class.title()

                        if s_class == "protein":
                            mw = molecular_weight or sub.get("protein", {}).get("molecularWeight")
                            if mw and float(mw) < 10000:
                                result["modality"] = SubstanceModality.PEPTIDE
                                result["is_peptide"] = True
                            else:
                                result["modality"] = SubstanceModality.BIOLOGIC_ANTIBODY
                                result["is_biologic"] = True
                            result["evidence_source"] = "NCATS G-SRS"
                            result["confidence"] = 1.0
                        elif s_class == "structurallydiverse":
                            result["modality"] = SubstanceModality.BOTANICAL_NATURAL
                            result["evidence_source"] = "NCATS G-SRS (Structurally Diverse)"
                            result["confidence"] = 0.95
                        elif s_class == "nucleicacid":
                            result["modality"] = SubstanceModality.PEPTIDE  # Oligonucleotide branch
                            result["is_peptide"] = True
                            result["evidence_source"] = "NCATS G-SRS (Nucleic Acid)"
                            result["confidence"] = 1.0
                        elif s_class == "polymer":
                            result["modality"] = SubstanceModality.MINERAL_ELECTROLYTE
                            result["evidence_source"] = "NCATS G-SRS (Polymer)"
                            result["confidence"] = 0.9
            except Exception as e:
                logger.debug("G-SRS modality query failed for %s: %s", cleaned, e)

        # 4. Check Molecular Weight bounds if available
        if result["confidence"] < 1.0 and molecular_weight is not None:
            mw = float(molecular_weight)
            if mw > 10000.0:
                result["modality"] = SubstanceModality.BIOLOGIC_ANTIBODY
                result["is_biologic"] = True
                result["evidence_source"] = "Molecular Weight (>10kDa)"
                result["confidence"] = 0.85
            elif 500.0 < mw <= 10000.0 and result.get("is_peptide"):
                result["modality"] = SubstanceModality.PEPTIDE
                result["is_peptide"] = True
                result["evidence_source"] = "Peptide Molecular Weight"
                result["confidence"] = 0.85

        with _MODALITY_LOCK:
            _MODALITY_CACHE[cache_key] = (result, time.time())

        return result


_GLOBAL_MODALITY_RESOLVER: Optional[ModalityResolver] = None


def get_modality_resolver() -> ModalityResolver:
    global _GLOBAL_MODALITY_RESOLVER
    if _GLOBAL_MODALITY_RESOLVER is None:
        _GLOBAL_MODALITY_RESOLVER = ModalityResolver()
    return _GLOBAL_MODALITY_RESOLVER
