from __future__ import annotations

import concurrent.futures
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional, Set
import httpx
from cachetools import LRUCache

from app.services.live_enrichment import get_shared_http_client

logger = logging.getLogger("healthai.rxnorm_decomposer")

_DECOMPOSER_CACHE: LRUCache = LRUCache(maxsize=2000)
_DECOMPOSER_LOCK = threading.Lock()
DECOMPOSER_TTL_SECONDS = 3600.0 * 24  # 24 hours

KNOWN_SALTS = [
    "hydrochloride", "hcl", "hydrobromide", "hbr", "maleate", "succinate",
    "sulfate", "tartrate", "phosphate", "sodium", "potassium", "calcium",
    "mesylate", "acetate", "citrate", "nitrate", "fumarate", "gluconate",
    "besylate", "tosylate", "valerate", "propionate", "dipropionate", "dihydrate",
    "monohydrate", "trihydrate", "sesquihydrate",
]


def _normalize_key(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    return cleaned.strip("_")


def _clean_base_substance(substance_name: str) -> str:
    """Strips counter-ions, salt forms, and FDA 4-letter biosimilar suffixes to isolate the active pharmacological moiety."""
    clean = substance_name.strip()
    # Strip FDA 4-letter biosimilar suffix (e.g. -pmph, -adaz, -bwwd)
    clean = re.sub(r"-[a-z]{4}\b", "", clean, flags=re.IGNORECASE).strip()
    words = clean.split()
    kept = [w for w in words if w.lower() not in KNOWN_SALTS]
    result = " ".join(kept).strip()
    return result.title() if result else clean.title()


class RxNormGraphDecomposer:
    """
    Authoritative Multi-Ingredient Combination Decomposition Service.
    Integrates two authoritative federal biomedical registries:
    1. NLM RxNorm Relational Concept Graph:
       Traverses `has_ingredient` (tty=IN) and `has_precise_ingredient` (tty=PIN)
    2. FDA DailyMed SPL Structured Substance Registry:
       Extracts verified `substance_name` and `generic_name` lists for multi-active commercial brands
       (e.g., DayQuil, NyQuil, Excedrin, Entresto, Suboxone, Adderall).
    """

    def __init__(self, timeout_seconds: float = 7.5, client: Optional[httpx.Client] = None):
        self.timeout = timeout_seconds
        self._custom_client = client

    def _client(self) -> httpx.Client:
        if self._custom_client and not self._custom_client.is_closed:
            return self._custom_client
        return get_shared_http_client(self.timeout)

    def get_ingredients_for_rxcui(self, rxcui: str) -> List[Dict[str, Any]]:
        """Queries RxNav related graph for active ingredients (tty=IN or PIN)."""
        if not rxcui:
            return []

        client = self._client()
        ingredients: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()

        try:
            url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/related.json"
            resp = client.get(url, params={"tty": "IN"})
            if resp.status_code == 200:
                data = resp.json()
                groups = data.get("relatedGroup", {}).get("conceptGroup", [])
                for grp in groups:
                    tty = grp.get("tty")
                    for prop in grp.get("conceptProperties", []):
                        raw_name = prop.get("name")
                        cui = prop.get("rxcui")
                        if not raw_name:
                            continue
                        base_name = _clean_base_substance(raw_name)
                        k = _normalize_key(base_name)
                        if k in seen_keys:
                            continue
                        seen_keys.add(k)
                        ingredients.append({
                            "name": base_name,
                            "canonical_name": base_name,
                            "key": k,
                            "rxcui": str(cui or ""),
                            "tty": tty,
                        })

            # If no IN found, check PIN fallback
            if not ingredients:
                resp = client.get(url, params={"tty": "PIN"})
                if resp.status_code == 200:
                    data = resp.json()
                    groups = data.get("relatedGroup", {}).get("conceptGroup", [])
                    for grp in groups:
                        tty = grp.get("tty")
                        for prop in grp.get("conceptProperties", []):
                            raw_name = prop.get("name")
                            cui = prop.get("rxcui")
                            if not raw_name:
                                continue
                            base_name = _clean_base_substance(raw_name)
                            k = _normalize_key(base_name)
                            if k in seen_keys:
                                continue
                            seen_keys.add(k)
                            ingredients.append({
                                "name": base_name,
                                "canonical_name": base_name,
                                "key": k,
                                "rxcui": str(cui or ""),
                                "tty": tty,
                            })
        except Exception as e:
            logger.debug("Failed to resolve RxNorm ingredients for RxCUI %s: %s", rxcui, e)

        return ingredients

    def _decompose_via_openfda(self, brand_name: str) -> List[Dict[str, Any]]:
        """Fallback to FDA DailyMed structured substance list for branded OTC/Rx combinations."""
        client = self._client()
        ingredients: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()
        clean_b = brand_name.strip().lower()
        q_tokens = [t for t in re.findall(r"[a-z0-9]+", clean_b) if t]
        if not q_tokens:
            return []

        try:
            url = "https://api.fda.gov/drug/label.json"
            query_str = f'openfda.brand_name:"{brand_name}"'
            resp = client.get(url, params={"search": query_str, "limit": 5})
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                for r in results:
                    openfda_data = r.get("openfda", {})
                    # Verify brand name fidelity: the query must match the brand name root
                    b_names = [b.lower().strip() for b in openfda_data.get("brand_name", [])]
                    brand_matched = False
                    for b in b_names:
                        b_tokens = [t for t in re.findall(r"[a-z0-9]+", b) if t]
                        if not b_tokens:
                            continue
                        if b_tokens[:len(q_tokens)] == q_tokens or (len(b_tokens) > 1 and b_tokens[1:1+len(q_tokens)] == q_tokens):
                            brand_matched = True
                            break
                        if clean_b in b and any(w in b for w in ["cold", "flu", "cough", "sinus", "relief", "pm", "am", "day", "night", "plus", "extra"]):
                            brand_matched = True
                            break
                    if not brand_matched:
                        continue

                    # 1. Inspect structured substance_name list
                    substances = openfda_data.get("substance_name", [])
                    if len(substances) > 1:
                        # Guard: If query is an active ingredient/chemical name, reject if substances completely exclude query
                        substances_lower = " ".join(substances).lower()
                        if any(q in ["ghk", "peptide", "growth", "acid"] for q in q_tokens) and not any(q in substances_lower for q in q_tokens):
                            continue

                        for s in substances:
                            base = _clean_base_substance(s)
                            k = _normalize_key(base)
                            if k not in seen_keys:
                                seen_keys.add(k)
                                ingredients.append({
                                    "name": base,
                                    "canonical_name": base,
                                    "key": k,
                                    "source": "OpenFDA substance_name",
                                })
                        if len(ingredients) > 1:
                            return ingredients

                    # 2. Inspect generic_name comma/slash-separated list
                    generics = openfda_data.get("generic_name", [])
                    for g in generics:
                        parts = re.split(r",|\band\b|/|;", g, flags=re.IGNORECASE)
                        if len(parts) > 1:
                            for p in parts:
                                base = _clean_base_substance(p)
                                k = _normalize_key(base)
                                if k and k not in seen_keys and len(k) >= 3:
                                    seen_keys.add(k)
                                    ingredients.append({
                                        "name": base,
                                        "canonical_name": base,
                                        "key": k,
                                        "source": "OpenFDA generic_name",
                                    })
                            if len(ingredients) > 1:
                                return ingredients
        except Exception as e:
            logger.debug("OpenFDA decomposition fallback error for %s: %s", brand_name, e)

        return ingredients

    def decompose_product(self, brand_or_term: str) -> Dict[str, Any]:
        """
        Takes a brand name, clinical drug string, or RxCUI and inspects
        whether it represents a multi-active combination product.
        """
        clean_query = brand_or_term.strip()
        if not clean_query:
            return {"is_combination": False, "ingredients": []}

        cache_key = clean_query.lower()
        with _DECOMPOSER_LOCK:
            if cache_key in _DECOMPOSER_CACHE:
                cached, t_cached = _DECOMPOSER_CACHE[cache_key]
                if time.time() - t_cached < DECOMPOSER_TTL_SECONDS:
                    return dict(cached)
                _DECOMPOSER_CACHE.pop(cache_key, None)

        client = self._client()
        result: Dict[str, Any] = {
            "is_combination": False,
            "query": clean_query,
            "brand_name": clean_query.title(),
            "rxcui": None,
            "ingredient_count": 1,
            "ingredients": [],
        }

        try:
            # 1. Numeric query: direct RxCUI
            if clean_query.isdigit():
                ingreds = self.get_ingredients_for_rxcui(clean_query)
                if len(ingreds) > 1:
                    result["is_combination"] = True
                    result["rxcui"] = clean_query
                    result["ingredient_count"] = len(ingreds)
                    result["ingredients"] = ingreds
                elif len(ingreds) == 1:
                    result["rxcui"] = clean_query
                    result["ingredients"] = ingreds
            else:
                # 2. Query RxNorm approximateTerm to find primary clinical concept RxCUIs
                url = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json"
                resp = client.get(url, params={"term": clean_query, "maxEntries": 8})
                if resp.status_code == 200:
                    candidates = resp.json().get("approximateGroup", {}).get("candidate", [])
                    best_combo_ingredients: List[Dict[str, Any]] = []
                    matched_rxcui = None

                    valid_rxcuis = [str(cand.get("rxcui")) for cand in candidates if cand.get("rxcui")]
                    if valid_rxcuis:
                        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(valid_rxcuis), 6)) as cand_exec:
                            futures = {cand_exec.submit(self.get_ingredients_for_rxcui, rxcui): rxcui for rxcui in valid_rxcuis}
                            for fut in concurrent.futures.as_completed(futures):
                                rxcui = futures[fut]
                                try:
                                    ingreds = fut.result()
                                    if len(ingreds) > len(best_combo_ingredients):
                                        best_combo_ingredients = ingreds
                                        matched_rxcui = rxcui
                                except Exception as ce:
                                    logger.debug("Failed candidate ingredient lookup for %s: %s", rxcui, ce)

                    if len(best_combo_ingredients) > 1:
                        result["is_combination"] = True
                        result["rxcui"] = matched_rxcui
                        result["ingredient_count"] = len(best_combo_ingredients)
                        result["ingredients"] = best_combo_ingredients
                    elif best_combo_ingredients:
                        result["rxcui"] = matched_rxcui
                        result["ingredients"] = best_combo_ingredients

                # 3. Only fall back to OpenFDA DailyMed SPL if RxNorm found NO ingredients at all
                # If RxNorm found a single valid active ingredient (len == 1), it is confirmed to be a single drug!
                if not result["is_combination"] and not result.get("ingredients"):
                    fda_ingreds = self._decompose_via_openfda(clean_query)
                    if len(fda_ingreds) > 1:
                        result["is_combination"] = True
                        result["ingredient_count"] = len(fda_ingreds)
                        result["ingredients"] = fda_ingreds

        except Exception as e:
            logger.debug("Error during combination decomposition for %s: %s", clean_query, e)

        with _DECOMPOSER_LOCK:
            _DECOMPOSER_CACHE[cache_key] = (result, time.time())

        return result


_GLOBAL_DECOMPOSER: Optional[RxNormGraphDecomposer] = None


def get_rxnorm_decomposer() -> RxNormGraphDecomposer:
    global _GLOBAL_DECOMPOSER
    if _GLOBAL_DECOMPOSER is None:
        _GLOBAL_DECOMPOSER = RxNormGraphDecomposer()
    return _GLOBAL_DECOMPOSER
