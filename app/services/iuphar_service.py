from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional
import httpx
from cachetools import LRUCache

from app.services.live_enrichment import get_shared_http_client

logger = logging.getLogger("healthai.iuphar_service")

_IUPHAR_CACHE: LRUCache = LRUCache(maxsize=1500)
_IUPHAR_LOCK = threading.Lock()
IUPHAR_CACHE_TTL_SECONDS = 3600.0 * 24  # 24 hours


class IUPHARService:
    """
    International Union of Basic and Clinical Pharmacology (IUPHAR / BPS)
    Guide to PHARMACOLOGY REST Client.
    Specialized authoritative curation of:
    - Peptide ligands and endogenous hormones
    - GPCR receptor targets & quantitative binding affinities
    - International regulatory approval statuses (FDA, EMA)
    """

    def __init__(self, timeout_seconds: float = 3.0, client: Optional[httpx.Client] = None):
        self.timeout = timeout_seconds
        self._custom_client = client

    def _client(self) -> httpx.Client:
        if self._custom_client and not self._custom_client.is_closed:
            return self._custom_client
        return get_shared_http_client(self.timeout)

    def fetch_peptide_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """Searches IUPHAR Guide to PHARMACOLOGY for a peptide or ligand."""
        clean_name = str(name or "").strip().lower()
        if not clean_name:
            return None

        with _IUPHAR_LOCK:
            if clean_name in _IUPHAR_CACHE:
                cached, t_cached = _IUPHAR_CACHE[clean_name]
                if time.time() - t_cached < IUPHAR_CACHE_TTL_SECONDS:
                    return dict(cached) if cached else None
                _IUPHAR_CACHE.pop(clean_name, None)

        client = self._client()
        result: Optional[Dict[str, Any]] = None

        try:
            url = "https://www.guidetopharmacology.org/services/ligands"
            resp = client.get(url, params={"name": clean_name})
            if resp.status_code == 200:
                ligands = resp.json()
                if ligands and isinstance(ligands, list):
                    l_data = ligands[0]
                    ligand_id = l_data.get("ligandId")
                    ligand_type = str(l_data.get("type") or "").strip()
                    approval = str(l_data.get("approvalSource") or "")

                    profile: Dict[str, Any] = {
                        "ligand_id": ligand_id,
                        "name": l_data.get("name", clean_name).title(),
                        "ligand_type": ligand_type,
                        "inn": l_data.get("inn"),
                        "approval_source": approval,
                        "is_approved": bool(l_data.get("approved")),
                        "is_peptide": ligand_type.lower() == "peptide",
                        "source": "IUPHAR / BPS Guide to PHARMACOLOGY",
                        "targets": [],
                    }

                    # Fetch interactions with short timeout
                    try:
                        inter_url = f"https://www.guidetopharmacology.org/services/interactions"
                        inter_resp = client.get(inter_url, params={"ligandId": ligand_id})
                        if inter_resp.status_code == 200:
                            interactions = inter_resp.json()
                            for it in (interactions or [])[:5]:
                                tgt_name = it.get("targetName")
                                pchembl = it.get("affinityParameter")
                                aff_val = it.get("affinity")
                                if tgt_name:
                                    profile["targets"].append({
                                        "target": tgt_name,
                                        "action": str(it.get("type") or "agonist").lower(),
                                        "affinity_parameter": pchembl,
                                        "affinity_value": aff_val,
                                    })
                    except Exception as ex:
                        logger.debug("IUPHAR interaction lookup timed out or failed for %s: %s", ligand_id, ex)

                    result = profile
        except Exception as e:
            logger.debug("IUPHAR ligand search failed for %s: %s", clean_name, e)

        with _IUPHAR_LOCK:
            _IUPHAR_CACHE[clean_name] = (result, time.time())

        return result


_GLOBAL_IUPHAR: Optional[IUPHARService] = None


def get_iuphar_service() -> IUPHARService:
    global _GLOBAL_IUPHAR
    if _GLOBAL_IUPHAR is None:
        _GLOBAL_IUPHAR = IUPHARService()
    return _GLOBAL_IUPHAR
