from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("healthai.live_enrichment")


class LiveEnrichmentService:
    """
    Live Online Biomedical & Pharmacological Enrichment Service.
    Queries authoritative public open APIs to automatically enrich compounds without hardcoding:
    1. OpenFDA API (DailyMed SPL structured drug labels):
       - Established Pharmacologic Class (pharm_class_epc)
       - Mechanism of Action (pharm_class_moa)
       - Physiologic Effect (pharm_class_pe)
       - Boxed Warnings, Warnings & Precautions, Drug Interactions
    2. ChEMBL REST API (EMBL-EBI):
       - Molecular targets (Receptors, Enzymes, Transporters) with UniProt IDs
       - Pharmacological action types (ANTAGONIST, AGONIST, INHIBITOR, PAM, NAM)
       - Quantitative binding affinities (Ki, IC50, Kd in nM)
    3. NLM RxNorm & Med-RT API (NIH):
       - RxCUI normalization
       - WHO ATC hierarchy classifications
    """

    def __init__(self, timeout_seconds: float = 6.0):
        self.timeout = timeout_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}

    def fetch_openfda(self, query_name: str) -> Dict[str, Any]:
        """Fetch FDA label metadata, pharmacologic classes, and warnings from openFDA API."""
        cleaned_name = query_name.strip().lower()
        if not cleaned_name:
            return {}

        cache_key = f"openfda:{cleaned_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result: Dict[str, Any] = {
            "pharm_class_epc": [],
            "pharm_class_moa": [],
            "pharm_class_pe": [],
            "boxed_warning": None,
            "warnings": [],
            "contraindications": [],
            "drug_interactions": [],
            "atc_codes": [],
        }

        try:
            url = "https://api.fda.gov/drug/label.json"
            # Search by generic name, brand name, or substance name
            search_query = f'openfda.generic_name:"{cleaned_name}"+OR+openfda.brand_name:"{cleaned_name}"+OR+openfda.substance_name:"{cleaned_name}"'
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params={"search": search_query, "limit": 1})
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        label = results[0]
                        openfda_info = label.get("openfda", {})

                        result["pharm_class_epc"] = openfda_info.get("pharm_class_epc", [])
                        result["pharm_class_moa"] = openfda_info.get("pharm_class_moa", [])
                        result["pharm_class_pe"] = openfda_info.get("pharm_class_pe", [])
                        result["atc_codes"] = openfda_info.get("atc_codes", [])

                        # Extract boxed warnings
                        if label.get("boxed_warning"):
                            bw = label["boxed_warning"]
                            result["boxed_warning"] = " ".join(bw) if isinstance(bw, list) else str(bw)

                        # Extract warnings and precautions
                        if label.get("warnings_and_precautions"):
                            wp = label["warnings_and_precautions"]
                            result["warnings"] = wp if isinstance(wp, list) else [str(wp)]
                        elif label.get("warnings"):
                            w = label["warnings"]
                            result["warnings"] = w if isinstance(w, list) else [str(w)]

                        # Extract contraindications
                        if label.get("contraindications"):
                            ci = label["contraindications"]
                            result["contraindications"] = ci if isinstance(ci, list) else [str(ci)]

                        # Extract drug interactions
                        if label.get("drug_interactions"):
                            di = label["drug_interactions"]
                            result["drug_interactions"] = di if isinstance(di, list) else [str(di)]
        except Exception as e:
            logger.debug("OpenFDA query for %s encountered error: %s", cleaned_name, e)

        self._cache[cache_key] = result
        return result

    def fetch_chembl(self, query_name: str, chembl_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch molecular mechanisms, targets, and action types from ChEMBL REST API."""
        cleaned_name = query_name.strip().lower()
        if not cleaned_name and not chembl_id:
            return {}

        cache_key = f"chembl:{chembl_id or cleaned_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result: Dict[str, Any] = {
            "chembl_id": chembl_id,
            "mechanisms": [],
            "receptor_targets": [],
            "drug_class": None,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                target_chembl_id = chembl_id

                # If no chembl_id, search by molecule name
                if not target_chembl_id:
                    search_url = "https://www.ebi.ac.uk/chembl/api/data/molecule/search"
                    resp = client.get(search_url, params={"q": cleaned_name, "format": "json"})
                    if resp.status_code == 200:
                        molecules = resp.json().get("molecules", [])
                        if molecules:
                            target_chembl_id = molecules[0].get("molecule_chembl_id")
                            result["chembl_id"] = target_chembl_id

                # Fetch mechanism of action
                if target_chembl_id:
                    mech_url = "https://www.ebi.ac.uk/chembl/api/data/mechanism.json"
                    m_resp = client.get(mech_url, params={"molecule_chembl_id": target_chembl_id})
                    if m_resp.status_code == 200:
                        mechanisms = m_resp.json().get("mechanisms", [])
                        result["mechanisms"] = mechanisms

                        for m in mechanisms:
                            t_name = m.get("target_name") or m.get("mechanism_of_action") or "Unknown Target"
                            action = (m.get("action_type") or "MODULATOR").lower()
                            t_chembl = m.get("target_chembl_id")

                            result["receptor_targets"].append({
                                "target": t_name,
                                "action": action,
                                "family": "ChEMBL Mechanism",
                                "target_id": t_chembl,
                            })
        except Exception as e:
            logger.debug("ChEMBL query for %s encountered error: %s", query_name, e)

        self._cache[cache_key] = result
        return result

    def fetch_rxnorm_atc(self, query_name: str) -> List[str]:
        """Fetch WHO ATC hierarchy classifications from NLM RxNorm / Med-RT API."""
        cleaned_name = query_name.strip().lower()
        if not cleaned_name:
            return []

        cache_key = f"rxnorm_atc:{cleaned_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        atc_classes: List[str] = []

        try:
            with httpx.Client(timeout=self.timeout) as client:
                rxcui_url = "https://rxnav.nlm.nih.gov/REST/rxcui.json"
                resp = client.get(rxcui_url, params={"name": cleaned_name}, headers={"Accept": "application/json"})
                if resp.status_code == 200:
                    id_group = resp.json().get("idGroup", {})
                    rxcui_list = id_group.get("rxnormId", [])
                    if rxcui_list:
                        rxcui = rxcui_list[0]
                        class_url = f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json"
                        c_resp = client.get(class_url, params={"rxcui": rxcui, "relaSource": "ATC"}, headers={"Accept": "application/json"})
                        if c_resp.status_code == 200:
                            drug_info_list = c_resp.json().get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", [])
                            for item in drug_info_list:
                                c_name = item.get("rxclassMinConceptItem", {}).get("className")
                                if c_name and c_name not in atc_classes:
                                    atc_classes.append(c_name)
        except Exception as e:
            logger.debug("RxNorm query for %s encountered error: %s", cleaned_name, e)

        self._cache[cache_key] = atc_classes
        return atc_classes

    def enrich_compound(self, compound_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriches a compound dictionary with live FDA, ChEMBL, and RxNorm data.
        Does NOT overwrite existing high-confidence fields, but fills in missing ontology classes.
        """
        name = compound_dict.get("name") or compound_dict.get("key") or ""
        chembl_id = compound_dict.get("canonical_key") or compound_dict.get("inchikey")

        # 1. Fetch OpenFDA Label data
        fda_data = self.fetch_openfda(name)

        # 2. Fetch ChEMBL Targets
        chembl_data = self.fetch_chembl(name, chembl_id if (chembl_id and chembl_id.startswith("CHEMBL")) else None)

        # 3. Fetch RxNorm ATC Classes
        atc_classes = self.fetch_rxnorm_atc(name)

        # Merge results into compound copy
        enriched = dict(compound_dict)

        # Enrich Categories & ATC
        existing_categories = list(enriched.get("categories", []))
        for epc in fda_data.get("pharm_class_epc", []):
            if epc not in existing_categories:
                existing_categories.append(epc)
        for atc in atc_classes:
            if atc not in existing_categories:
                existing_categories.append(atc)
        enriched["categories"] = existing_categories

        # Enrich Receptor Targets
        from app.services.graph_service import _normalize_target_node_id
        existing_targets = list(enriched.get("receptor_targets", []))
        existing_target_names = {_normalize_target_node_id(t.get("target", "")) for t in existing_targets if isinstance(t, dict)}
        for ct in chembl_data.get("receptor_targets", []):
            norm_name = _normalize_target_node_id(ct.get("target", ""))
            if norm_name not in existing_target_names:
                existing_targets.append(ct)
                existing_target_names.add(norm_name)
        enriched["receptor_targets"] = existing_targets

        # Enrich Warnings & Boxed Warnings
        if not enriched.get("boxed_warning") and fda_data.get("boxed_warning"):
            enriched["boxed_warning"] = fda_data["boxed_warning"]

        if not enriched.get("warnings") and fda_data.get("warnings"):
            enriched["warnings"] = fda_data["warnings"]

        if not enriched.get("contraindications") and fda_data.get("contraindications"):
            enriched["contraindications"] = fda_data["contraindications"]

        if not enriched.get("interactions") and fda_data.get("drug_interactions"):
            enriched["interactions"] = fda_data["drug_interactions"]

        # Attach raw ontology metadata
        metadata = dict(enriched.get("metadata", {}))
        metadata["online_enrichment"] = {
            "pharm_class_epc": fda_data.get("pharm_class_epc", []),
            "pharm_class_moa": fda_data.get("pharm_class_moa", []),
            "pharm_class_pe": fda_data.get("pharm_class_pe", []),
            "atc_classes": atc_classes,
            "chembl_mechanisms": chembl_data.get("mechanisms", []),
        }
        enriched["metadata"] = metadata

        # Structured Quantitative PK/PD Benchmark & Assay Enrichment
        from app.services.pkpd_enricher import PKPDEnricher
        enriched = PKPDEnricher(timeout_seconds=self.timeout).enrich_compound_pkpd(enriched)

        return enriched
