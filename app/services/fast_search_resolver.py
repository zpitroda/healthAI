from __future__ import annotations

import concurrent.futures
import copy
import logging
import re
import threading
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from cachetools import LRUCache

from app.services.live_enrichment import get_shared_http_client
from app.services.modality_resolver import get_modality_resolver, SubstanceModality
from app.services.rxnorm_graph_decomposer import get_rxnorm_decomposer
from app.services.botanical_resolver import get_botanical_resolver

logger = logging.getLogger("healthai.fast_search_resolver")

# Thread-safe in-memory caches
_EXTERNAL_CANDIDATES_CACHE: LRUCache = LRUCache(maxsize=2000)
_NEGATIVE_CACHE: LRUCache = LRUCache(maxsize=2000)
_RXNORM_INGRED_CACHE: LRUCache = LRUCache(maxsize=1000)
_RESOLVER_LOCK = threading.RLock()

NEGATIVE_CACHE_TTL_SECONDS = 600.0   # 10 minutes
QUERY_CACHE_TTL_SECONDS = 1800.0      # 30 minutes

ELEMENT_SYMBOL_MAP = {
    "cu": "copper",
    "zn": "zinc",
    "fe": "iron",
    "mg": "magnesium",
    "ca": "calcium",
    "k": "potassium",
    "na": "sodium",
    "li": "lithium",
    "se": "selenium",
}


def _normalize_key(text: str) -> str:
    """Produces a clean alphanumeric underscore key for a compound."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    return cleaned.strip("_")


def _clean_rxnorm_name(raw_name: str) -> str:
    """Strips dosage forms, delivery mechanisms, and pill markers from RxNorm strings."""
    name = re.sub(r"\s+(?:Pill|Tablet|Capsule|Injection|Solution|Suspension|Topical|Cream|Ointment)\b.*", "", raw_name, flags=re.IGNORECASE)
    name = re.sub(r"\[.*?\]", "", name)
    name = re.sub(r"\s+\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|unit|units|%)\b.*", "", name, flags=re.IGNORECASE)
    return name.strip()


class FastSearchResolver:
    """
    High-Throughput Multi-Registry Typeahead & Search Resolver for Novel / Uncached Compounds.
    
    Concurrently queries authoritative biomedical registries (ChEMBL, PubChem, NLM RxNorm)
    with low network timeouts to provide instantaneous typeahead candidates for compounds
    not yet indexed or cached in the local catalog.
    """

    def __init__(self, timeout_seconds: float = 1.5, client: Optional[httpx.Client] = None):
        self.timeout = timeout_seconds
        self._custom_client = client

    def _client(self) -> httpx.Client:
        if self._custom_client and not self._custom_client.is_closed:
            return self._custom_client
        return get_shared_http_client(self.timeout)

    def is_negative_cached(self, query_norm: str, modality: Optional[str] = None) -> bool:
        """Checks if the query (optionally scoped by modality) is in the negative cache and still fresh."""
        mod_key = modality.strip().lower() if modality and modality.strip().lower() not in ("all", "", "none") else None
        cache_key = f"{query_norm}::{mod_key}" if mod_key else query_norm
        with _RESOLVER_LOCK:
            if cache_key in _NEGATIVE_CACHE:
                cached_time = _NEGATIVE_CACHE[cache_key]
                if time.time() - cached_time < NEGATIVE_CACHE_TTL_SECONDS:
                    return True
                _NEGATIVE_CACHE.pop(cache_key, None)
        return False

    def mark_negative_cache(self, query_norm: str, modality: Optional[str] = None) -> None:
        """Records an unresolvable query (optionally scoped by modality) in the negative cache."""
        mod_key = modality.strip().lower() if modality and modality.strip().lower() not in ("all", "", "none") else None
        cache_key = f"{query_norm}::{mod_key}" if mod_key else query_norm
        with _RESOLVER_LOCK:
            _NEGATIVE_CACHE[cache_key] = time.time()

    def _resolve_rxnorm_ingredient(self, rxcui: str) -> Optional[str]:
        """Resolves active ingredient name (tty=IN) for brand or clinical drug RxCUI."""
        if not rxcui:
            return None
        with _RESOLVER_LOCK:
            if rxcui in _RXNORM_INGRED_CACHE:
                return _RXNORM_INGRED_CACHE[rxcui]

        client = self._client()
        ingred_name: Optional[str] = None
        try:
            url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/related.json"
            resp = client.get(url, params={"tty": "IN"})
            if resp.status_code == 200:
                groups = resp.json().get("relatedGroup", {}).get("conceptGroup", [])
                for grp in groups:
                    props = grp.get("conceptProperties", [])
                    if props:
                        first_prop = props[0]
                        ingred_name = first_prop.get("name")
                        break
        except Exception as e:
            logger.debug("RxNorm ingredient resolution failed for %s: %s", rxcui, e)

        with _RESOLVER_LOCK:
            _RXNORM_INGRED_CACHE[rxcui] = ingred_name
        return ingred_name

    def query_chembl_prefix(self, query_str: str, limit: int = 4) -> List[Dict[str, Any]]:
        """Queries ChEMBL molecules using pref_name__istartswith filter."""
        client = self._client()
        candidates: List[Dict[str, Any]] = []
        try:
            url = "https://www.ebi.ac.uk/chembl/api/data/molecule.json"
            resp = client.get(
                url,
                params={"pref_name__istartswith": query_str.strip(), "limit": limit},
            )
            if resp.status_code == 200:
                molecules = resp.json().get("molecules", [])
                for m in molecules:
                    pref_name = m.get("pref_name")
                    if not pref_name:
                        continue
                    clean_name = str(pref_name).title()
                    chembl_id = m.get("molecule_chembl_id")
                    max_phase = m.get("max_phase")
                    phase_val: Optional[int] = None
                    if max_phase is not None:
                        try:
                            val = int(float(str(max_phase).strip()))
                            if val > 0:
                                phase_val = val
                        except (ValueError, TypeError, OverflowError):
                            phase_val = None
                    phase_str = f"Approved Drug (Phase {phase_val})" if phase_val else "Investigational Agent"
                    synonyms: List[str] = []
                    for s in (m.get("molecule_synonyms") or []):
                        if isinstance(s, dict) and s.get("molecule_synonym"):
                            synonyms.append(str(s["molecule_synonym"]))

                    candidates.append({
                        "key": _normalize_key(clean_name),
                        "name": clean_name,
                        "canonical_name": clean_name,
                        "drug_class": phase_str,
                        "synonyms": synonyms[:6],
                        "source_registry": "ChEMBL",
                        "source_tier": "online_registry",
                        "external_ids": {"chembl_id": chembl_id},
                        "is_external": True,
                    })
        except Exception as e:
            logger.debug("ChEMBL prefix query error for %s: %s", query_str, e)
        return candidates

    def query_pubchem_autocomplete(self, query_str: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Queries PubChem Compound Autocomplete API."""
        client = self._client()
        candidates: List[Dict[str, Any]] = []
        try:
            quoted = urllib.parse.quote(query_str.strip())
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/{quoted}/json"
            resp = client.get(url, params={"limit": limit + 2})
            if resp.status_code == 200:
                data = resp.json()
                terms = data.get("dictionary_terms", {}).get("compound", [])
                for term in terms:
                    cleaned_t = term.strip()
                    if not cleaned_t:
                        continue
                    # Skip overly long or complex systematic chemical IUPAC names or CAS registry numbers
                    if len(cleaned_t) > 45 or cleaned_t.count(",") >= 2 or cleaned_t.count("[") >= 2:
                        continue
                    if re.match(r"^\d+-\d+-\d+$", cleaned_t) or cleaned_t.isdigit():
                        continue
                    display_name = cleaned_t.title() if not cleaned_t.isupper() else cleaned_t
                    candidates.append({
                        "key": _normalize_key(cleaned_t),
                        "name": display_name,
                        "canonical_name": display_name,
                        "drug_class": "Therapeutic Agent / Compound Match",
                        "synonyms": [cleaned_t],
                        "source_registry": "PubChem",
                        "source_tier": "online_registry",
                        "is_external": True,
                    })
        except Exception as e:
            logger.debug("PubChem autocomplete query error for %s: %s", query_str, e)
        return candidates

    def query_rxnorm_approximate(self, query_str: str, limit: int = 4) -> List[Dict[str, Any]]:
        """Queries NLM RxNorm Approximate Term API and resolves brands to active ingredients."""
        client = self._client()
        candidates: List[Dict[str, Any]] = []
        try:
            url = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json"
            resp = client.get(url, params={"term": query_str.strip(), "maxEntries": limit + 2})
            if resp.status_code == 200:
                raw_cands = resp.json().get("approximateGroup", {}).get("candidate", [])
                seen_keys: Set[str] = set()
                for c in raw_cands:
                    raw_name = c.get("name")
                    rxcui = str(c.get("rxcui") or "")
                    if not raw_name and not rxcui:
                        continue

                    # Fast-path: use cleaned name directly if available, check cache for ingredient
                    ingred = _RXNORM_INGRED_CACHE.get(rxcui) if rxcui else None
                    base_name = _clean_rxnorm_name(raw_name) if raw_name else (ingred.title() if ingred else "")
                    if not base_name and rxcui:
                        ingred = self._resolve_rxnorm_ingredient(rxcui)
                        base_name = _clean_rxnorm_name(raw_name) if raw_name else (ingred.title() if ingred else "")
                    if not base_name:
                        continue

                    k = _normalize_key(ingred or base_name)
                    if k in seen_keys:
                        continue
                    seen_keys.add(k)

                    display_name = base_name.title()
                    canonical = ingred.title() if ingred else display_name
                    synonyms = [base_name] if ingred and base_name.lower() != ingred.lower() else []

                    candidates.append({
                        "key": k,
                        "name": display_name if not ingred or ingred.lower() == base_name.lower() else f"{canonical} ({display_name})",
                        "canonical_name": canonical,
                        "drug_class": "FDA Approved Rx / Clinical Drug",
                        "synonyms": synonyms,
                        "source_registry": "RxNorm",
                        "source_tier": "online_registry",
                        "external_ids": {"rxcui": rxcui} if rxcui else {},
                        "is_external": True,
                    })
        except Exception as e:
            logger.debug("RxNorm approximate query error for %s: %s", query_str, e)
        return candidates

    def _query_decomp_candidates(self, query_str: str) -> List[Dict[str, Any]]:
        """Wraps RxNorm decomposition product into standard candidate dicts."""
        candidates: List[Dict[str, Any]] = []
        try:
            combo_res = get_rxnorm_decomposer().decompose_product(query_str)
            if combo_res and combo_res.get("is_combination"):
                ingred_names = [i["name"] for i in combo_res.get("ingredients", [])]
                b_name = combo_res.get("brand_name", query_str.title())
                candidates.append({
                    "key": _normalize_key(b_name),
                    "name": f"{b_name} (Combo: {' + '.join(ingred_names[:3])})",
                    "canonical_name": b_name,
                    "drug_class": f"Clinical Combination Drug ({len(ingred_names)} Active Ingredients)",
                    "is_combination": True,
                    "modality": SubstanceModality.COMBINATION_DRUG.value,
                    "active_ingredients": combo_res.get("ingredients", []),
                    "source_registry": "RxNorm Graph / DailyMed",
                    "source_tier": "online_registry",
                    "is_external": True,
                })
        except Exception as e:
            logger.debug("Decomposition candidate query failed for %s: %s", query_str, e)
        return candidates

    def _query_botanical_candidates(self, query_str: str) -> List[Dict[str, Any]]:
        """Wraps botanical resolution into standard candidate dicts."""
        candidates: List[Dict[str, Any]] = []
        try:
            botanical_res = get_botanical_resolver().resolve_botanical(query_str)
            if botanical_res and botanical_res.get("is_botanical"):
                b_name = botanical_res.get("name", query_str.title())
                constituents = botanical_res.get("primary_constituents", [])
                const_str = " (" + ", ".join([c["name"] for c in constituents[:2]]) + ")" if constituents else ""
                candidates.append({
                    "key": _normalize_key(b_name),
                    "name": f"{query_str.title()} [{b_name}]{const_str}",
                    "canonical_name": b_name,
                    "drug_class": "Botanical / Phytochemical Complex",
                    "is_botanical": True,
                    "modality": SubstanceModality.BOTANICAL_NATURAL.value,
                    "primary_constituents": constituents,
                    "scope_note": botanical_res.get("scope_note"),
                    "source_registry": "NCBI MeSH / Taxonomy",
                    "source_tier": "online_registry",
                    "is_external": True,
                })
        except Exception as e:
            logger.debug("Botanical candidate query failed for %s: %s", query_str, e)
        return candidates

    def _candidate_matches_modality(self, cand: Dict[str, Any], target_modality: Optional[str]) -> bool:
        """Determines whether a candidate matches the requested target modality."""
        if not target_modality:
            return True
        target = target_modality.strip().lower()
        if target in ("all", "", "none"):
            return True

        cand_mod = str(cand.get("modality") or "").lower()
        drug_class = str(cand.get("drug_class") or "").lower()
        cand_name = str(cand.get("name") or "").lower()

        if target == SubstanceModality.PEPTIDE.value:
            return (
                cand_mod == SubstanceModality.PEPTIDE.value
                or cand.get("is_peptide") is True
                or "peptide" in drug_class
                or "glp-1" in drug_class
                or "ghrp" in drug_class
                or "ghrh" in drug_class
                or "somatostatin" in drug_class
            )
        elif target == SubstanceModality.BIOLOGIC_ANTIBODY.value:
            return (
                cand_mod == SubstanceModality.BIOLOGIC_ANTIBODY.value
                or cand.get("is_biologic") is True
                or "biologic" in drug_class
                or "antibody" in drug_class
                or "mab" in drug_class
                or "monoclonal" in drug_class
                or cand_name.endswith("mab")
            )
        elif target == SubstanceModality.BOTANICAL_NATURAL.value:
            return (
                cand_mod == SubstanceModality.BOTANICAL_NATURAL.value
                or cand.get("is_botanical") is True
                or "botanical" in drug_class
                or "herb" in drug_class
                or "phytochemical" in drug_class
                or "extract" in drug_class
            )
        elif target == SubstanceModality.COMBINATION_DRUG.value:
            return (
                cand_mod == SubstanceModality.COMBINATION_DRUG.value
                or cand.get("is_combination") is True
                or "combination" in drug_class
                or "combo" in cand_name
            )
        elif target == SubstanceModality.SMALL_MOLECULE.value:
            if cand_mod == SubstanceModality.SMALL_MOLECULE.value:
                return True
            if (
                cand.get("is_peptide")
                or cand.get("is_biologic")
                or cand.get("is_botanical")
                or cand.get("is_combination")
                or cand_mod in (
                    SubstanceModality.PEPTIDE.value,
                    SubstanceModality.BIOLOGIC_ANTIBODY.value,
                    SubstanceModality.BOTANICAL_NATURAL.value,
                    SubstanceModality.COMBINATION_DRUG.value,
                )
                or "peptide" in drug_class
                or "biologic" in drug_class
                or "antibody" in drug_class
                or "botanical" in drug_class
                or "combination" in drug_class
            ):
                return False
            return True

        return cand_mod == target

    def resolve_external_candidates(
        self,
        query_str: str,
        limit: int = 5,
        local_keys_or_names: Optional[Set[str]] = None,
        modality: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Concurrently queries ChEMBL, PubChem, RxNorm, Decomposition, and Botanical registries.
        Selectively prunes queries based on requested modality to save network round-trips.
        Returns deduplicated candidate cards filtered against local catalog keys.
        """
        q_clean = query_str.strip()
        if len(q_clean) < 3:
            return []

        mod_clean = modality.strip().lower() if modality and modality.strip().lower() not in ("all", "", "none") else None
        q_norm = _normalize_key(q_clean)
        cache_key = f"{q_norm}::{mod_clean}" if mod_clean else q_norm

        # Check negative cache
        if self.is_negative_cached(q_norm, mod_clean):
            return []

        # Check query cache
        with _RESOLVER_LOCK:
            if cache_key in _EXTERNAL_CANDIDATES_CACHE:
                cached_cands, timestamp = _EXTERNAL_CANDIDATES_CACHE[cache_key]
                if time.time() - timestamp < QUERY_CACHE_TTL_SECONDS:
                    filtered = [
                        copy.deepcopy(c) for c in cached_cands
                        if not local_keys_or_names or (c["key"] not in local_keys_or_names and _normalize_key(c["name"]) not in local_keys_or_names)
                    ]
                    return filtered[:limit]
                _EXTERNAL_CANDIDATES_CACHE.pop(cache_key, None)

        # Determine which registries to query based on requested modality
        run_chembl = mod_clean in (None, SubstanceModality.SMALL_MOLECULE.value, SubstanceModality.BIOLOGIC_ANTIBODY.value)
        run_pubchem = mod_clean in (None, SubstanceModality.SMALL_MOLECULE.value, SubstanceModality.PEPTIDE.value, SubstanceModality.BOTANICAL_NATURAL.value)
        run_rxnorm = mod_clean in (None, SubstanceModality.SMALL_MOLECULE.value, SubstanceModality.PEPTIDE.value, SubstanceModality.BIOLOGIC_ANTIBODY.value, SubstanceModality.COMBINATION_DRUG.value)
        run_decomp = mod_clean in (None, SubstanceModality.COMBINATION_DRUG.value)
        run_botanical = mod_clean in (None, SubstanceModality.BOTANICAL_NATURAL.value)

        # Parallel ingestion across active registries
        chembl_cands: List[Dict[str, Any]] = []
        pubchem_cands: List[Dict[str, Any]] = []
        rxnorm_cands: List[Dict[str, Any]] = []
        combo_cands: List[Dict[str, Any]] = []
        botanical_cands: List[Dict[str, Any]] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            fut_chembl = executor.submit(self.query_chembl_prefix, q_clean, limit=limit) if run_chembl else None
            fut_pubchem = executor.submit(self.query_pubchem_autocomplete, q_clean, limit=limit) if run_pubchem else None
            fut_rxnorm = executor.submit(self.query_rxnorm_approximate, q_clean, limit=limit) if run_rxnorm else None
            fut_decomp = executor.submit(self._query_decomp_candidates, q_clean) if run_decomp else None
            fut_botanical = executor.submit(self._query_botanical_candidates, q_clean) if run_botanical else None

            if fut_chembl:
                try:
                    chembl_cands = fut_chembl.result() or []
                except Exception:
                    chembl_cands = []
            if fut_pubchem:
                try:
                    pubchem_cands = fut_pubchem.result() or []
                except Exception:
                    pubchem_cands = []
            if fut_rxnorm:
                try:
                    rxnorm_cands = fut_rxnorm.result() or []
                except Exception:
                    rxnorm_cands = []
            if fut_decomp:
                try:
                    combo_cands = fut_decomp.result() or []
                except Exception:
                    combo_cands = []
            if fut_botanical:
                try:
                    botanical_cands = fut_botanical.result() or []
                except Exception:
                    botanical_cands = []

        # Combine, rank, and deduplicate candidates
        all_raw: List[Dict[str, Any]] = []
        all_raw.extend(combo_cands)
        all_raw.extend(botanical_cands)
        all_raw.extend(chembl_cands)
        all_raw.extend(rxnorm_cands)
        all_raw.extend(pubchem_cands)

        deduped: Dict[str, Dict[str, Any]] = {}
        for c in all_raw:
            k = c["key"]
            if k not in deduped:
                deduped[k] = c
            else:
                existing = deduped[k]
                # If existing is a combination product injected at high priority, but an authoritative single-ingredient
                # compound from PubChem/RxNorm has the exact same entity key, preserve both without shadowing the single entity
                if existing.get("is_combination") and not c.get("is_combination"):
                    existing["key"] = f"{existing['key']}_combo"
                    deduped[existing["key"]] = existing
                    deduped[k] = c
                    continue

                # Promote to clinical registry if current is only PubChem
                if existing.get("source_registry") == "PubChem" and c.get("source_registry") in ("ChEMBL", "RxNorm"):
                    existing["source_registry"] = c["source_registry"]
                    if c.get("drug_class") and "Approved" in c["drug_class"]:
                        existing["drug_class"] = c["drug_class"]
                # Merge synonyms and external_ids
                for s in c.get("synonyms", []):
                    if s not in existing.get("synonyms", []):
                        existing.setdefault("synonyms", []).append(s)
                existing.setdefault("external_ids", {}).update(c.get("external_ids", {}))

        # Score and classify candidates relative to query
        scored: List[Tuple[int, Dict[str, Any]]] = []
        mod_resolver = get_modality_resolver()

        for cand in deduped.values():
            if not cand.get("modality"):
                ext_ids = cand.get("external_ids", {})
                mod_class = mod_resolver.classify_substance(
                    cand.get("name", ""),
                    rxcui=ext_ids.get("rxcui"),
                    chembl_id=ext_ids.get("chembl_id"),
                    network_lookup=False,
                )
                cand["modality"] = mod_class["modality"].value if hasattr(mod_class["modality"], "value") else str(mod_class["modality"])
                if mod_class.get("is_biologic"):
                    cand["is_biologic"] = True
                    if "Biologic" not in cand.get("drug_class", ""):
                        cand["drug_class"] = f"Biologic / Monoclonal Antibody ({cand.get('drug_class') or 'Targeted'})"
                if mod_class.get("is_peptide"):
                    cand["is_peptide"] = True

            if not self._candidate_matches_modality(cand, mod_clean):
                continue

            score = self._score_candidate(cand, q_clean, q_norm)
            if score is not None:
                scored.append((score, cand))

        scored.sort(key=lambda x: (-x[0], len(x[1]["name"]), x[1]["name"]))
        sorted_candidates = [item[1] for item in scored]

        # Cache results or mark negative
        with _RESOLVER_LOCK:
            if sorted_candidates:
                _EXTERNAL_CANDIDATES_CACHE[cache_key] = (sorted_candidates, time.time())
            else:
                self.mark_negative_cache(q_norm, mod_clean)

        # Filter against local catalog keys/names
        final_results = [
            c for c in sorted_candidates
            if not local_keys_or_names or (c["key"] not in local_keys_or_names and _normalize_key(c["name"]) not in local_keys_or_names)
        ]

        return final_results[:limit]

    def _score_candidate(self, cand: Dict[str, Any], q_clean: str, q_norm: str) -> Optional[int]:
        """Calculates a relevance score for an external candidate or returns None if no overlap."""
        q_lower = q_clean.lower()
        name_lower = cand.get("name", "").lower()
        canon_lower = cand.get("canonical_name", "").lower()
        syns_lower = [s.lower() for s in cand.get("synonyms", [])]
        cand_k = cand.get("key", "").lower()

        norm_name = _normalize_key(name_lower)
        norm_canon = _normalize_key(canon_lower)
        norm_cand_k = _normalize_key(cand_k)
        norm_syns = [_normalize_key(s) for s in syns_lower]

        # Build query target variants, including elemental symbol expansions (e.g. 'cu' <-> 'copper')
        q_targets = {q_lower, q_norm}
        for sym, elem in ELEMENT_SYMBOL_MAP.items():
            if f"-{sym}" in q_lower or f" {sym}" in q_lower or f"_{sym}" in q_lower or q_lower.endswith(f"-{sym}"):
                alt = re.sub(rf"[-_ ]{sym}\b", f" {elem}", q_lower)
                q_targets.add(alt.strip())
                q_targets.add(_normalize_key(alt))
            elif elem in q_lower:
                alt = re.sub(rf"\b{elem}\b", sym, q_lower)
                q_targets.add(alt.strip())
                q_targets.add(_normalize_key(alt))

        cand_targets = {name_lower, canon_lower, cand_k, norm_name, norm_canon, norm_cand_k}
        cand_syn_targets = set(syns_lower) | set(norm_syns)

        score = None
        # 1. Exact match against query or its elemental symbol expansion
        if any(qt in cand_targets or qt in cand_syn_targets for qt in q_targets):
            score = 100
        # 2. Starts with query
        elif any(any(ct.startswith(qt) for ct in cand_targets) for qt in q_targets):
            score = 85
        # 3. Substring containment
        elif any(any(qt in ct for ct in cand_targets) for qt in q_targets):
            score = 65
        # 4. Synonym overlap
        elif any(any(st.startswith(qt) or qt in st for st in cand_syn_targets) for qt in q_targets):
            score = 60
        else:
            return None

        # Bonus for authoritative clinical/therapeutic registries
        if cand.get("source_registry") == "ChEMBL":
            score += 15
        elif cand.get("source_registry") == "RxNorm":
            score += 12

        # Bonus for clean concise drug names
        if len(name_lower.split()) <= 2:
            score += 5

        # Penalize chemical intermediate/metabolite noise
        if any(noise in name_lower for noise in ["intermediate", "metabolite", "impurity", "sidechain", "degradation", "retard", "phosphazene"]):
            score -= 45

        return score

    def stream_external_candidates(
        self,
        query_str: str,
        limit: int = 5,
        local_keys_or_names: Optional[Set[str]] = None,
        modality: Optional[str] = None,
    ):
        """
        Progressively queries ChEMBL, PubChem, RxNorm, Decomposition, and Botanical registries
        and yields candidate batches immediately as each individual source completes (via as_completed).
        Prunes external queries based on requested modality to save network round-trips.
        """
        import copy
        q_clean = query_str.strip()
        if len(q_clean) < 3:
            return

        mod_clean = modality.strip().lower() if modality and modality.strip().lower() not in ("all", "", "none") else None
        q_norm = _normalize_key(q_clean)
        cache_key = f"{q_norm}::{mod_clean}" if mod_clean else q_norm

        # Check negative cache
        if self.is_negative_cached(q_norm, mod_clean):
            return

        # Check query cache
        with _RESOLVER_LOCK:
            if cache_key in _EXTERNAL_CANDIDATES_CACHE:
                cached_cands, timestamp = _EXTERNAL_CANDIDATES_CACHE[cache_key]
                if time.time() - timestamp < QUERY_CACHE_TTL_SECONDS:
                    filtered = [
                        copy.deepcopy(c) for c in cached_cands
                        if not local_keys_or_names or (c["key"] not in local_keys_or_names and _normalize_key(c["name"]) not in local_keys_or_names)
                    ]
                    if filtered:
                        yield filtered[:limit]
                    return
                _EXTERNAL_CANDIDATES_CACHE.pop(cache_key, None)

        yielded_keys: Set[str] = set(local_keys_or_names or set())
        all_discovered: List[Dict[str, Any]] = []

        # Determine which registries to query based on requested modality
        run_chembl = mod_clean in (None, SubstanceModality.SMALL_MOLECULE.value, SubstanceModality.BIOLOGIC_ANTIBODY.value)
        run_pubchem = mod_clean in (None, SubstanceModality.SMALL_MOLECULE.value, SubstanceModality.PEPTIDE.value, SubstanceModality.BOTANICAL_NATURAL.value)
        run_rxnorm = mod_clean in (None, SubstanceModality.SMALL_MOLECULE.value, SubstanceModality.PEPTIDE.value, SubstanceModality.BIOLOGIC_ANTIBODY.value, SubstanceModality.COMBINATION_DRUG.value)
        run_decomp = mod_clean in (None, SubstanceModality.COMBINATION_DRUG.value)
        run_botanical = mod_clean in (None, SubstanceModality.BOTANICAL_NATURAL.value)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_src = {}
            if run_rxnorm:
                future_to_src[executor.submit(self.query_rxnorm_approximate, q_clean, limit=limit)] = "RxNorm"
            if run_pubchem:
                future_to_src[executor.submit(self.query_pubchem_autocomplete, q_clean, limit=limit)] = "PubChem"
            if run_chembl:
                future_to_src[executor.submit(self.query_chembl_prefix, q_clean, limit=limit)] = "ChEMBL"
            if run_decomp:
                future_to_src[executor.submit(self._query_decomp_candidates, q_clean)] = "Decomposer"
            if run_botanical:
                future_to_src[executor.submit(self._query_botanical_candidates, q_clean)] = "Botanical"

            for future in concurrent.futures.as_completed(future_to_src):
                src_name = future_to_src[future]
                try:
                    cands = future.result() or []
                except Exception as ex:
                    logger.debug("FastSearchResolver %s query failed during stream: %s", src_name, ex)
                    cands = []

                batch: List[Dict[str, Any]] = []
                for c in cands:
                    k = c.get("key", "")
                    norm_n = _normalize_key(c.get("name", ""))
                    if k in yielded_keys or norm_n in yielded_keys:
                        continue

                    if not c.get("modality"):
                        ext_ids = c.get("external_ids", {})
                        mod_class = get_modality_resolver().classify_substance(
                            c.get("name", ""),
                            rxcui=ext_ids.get("rxcui"),
                            chembl_id=ext_ids.get("chembl_id"),
                            network_lookup=False,
                        )
                        c["modality"] = mod_class["modality"].value if hasattr(mod_class["modality"], "value") else str(mod_class["modality"])
                        if mod_class.get("is_biologic"):
                            c["is_biologic"] = True
                        if mod_class.get("is_peptide"):
                            c["is_peptide"] = True

                    if not self._candidate_matches_modality(c, mod_clean):
                        continue

                    score = self._score_candidate(c, q_clean, q_norm)
                    if score is None:
                        continue

                    yielded_keys.add(k)
                    yielded_keys.add(norm_n)
                    batch.append(c)
                    all_discovered.append(c)

                if batch:
                    # Sort batch by score before yielding
                    batch.sort(key=lambda x: -(self._score_candidate(x, q_clean, q_norm) or 0))
                    yield batch

        # Update cache with all discovered candidates
        with _RESOLVER_LOCK:
            if all_discovered:
                _EXTERNAL_CANDIDATES_CACHE[cache_key] = (all_discovered, time.time())
            else:
                self.mark_negative_cache(q_norm, mod_clean)


_GLOBAL_FAST_SEARCH_RESOLVER: Optional[FastSearchResolver] = None
_GLOBAL_RESOLVER_LOCK = threading.Lock()


def get_fast_search_resolver() -> FastSearchResolver:
    """Returns a singleton instance of FastSearchResolver."""
    global _GLOBAL_FAST_SEARCH_RESOLVER
    if _GLOBAL_FAST_SEARCH_RESOLVER is None:
        with _GLOBAL_RESOLVER_LOCK:
            if _GLOBAL_FAST_SEARCH_RESOLVER is None:
                _GLOBAL_FAST_SEARCH_RESOLVER = FastSearchResolver()
    return _GLOBAL_FAST_SEARCH_RESOLVER
