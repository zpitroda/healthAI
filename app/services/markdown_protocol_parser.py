from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.catalog_service import CatalogService
from app.services.dosing_service import infer_compound_route_and_frequency, get_default_compound_dose

logger = logging.getLogger("healthai.markdown_protocol_parser")


class MarkdownProtocolParser:
    """
    Intelligent NLP and structured parser that extracts compound protocol definitions,
    dosages, circadian timing, routes, and stack mutations directly from AI Copilot markdown text.
    """

    @classmethod
    def extract_cumulative_proposals_from_history(
        cls,
        messages: Optional[List[Dict[str, Any]]] = None,
        base_stack: Optional[List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scans previous assistant messages in the conversation history and extracts
        unapplied proposed compound recommendations that are not yet part of the active workbench stack.
        """
        if not messages or len(messages) <= 1:
            return []

        base_keys: Set[str] = set()
        for s in (base_stack or []):
            if isinstance(s, dict):
                k = str(s.get("key") or s.get("name") or "").strip().lower()
            else:
                k = str(s).strip().lower()
            if k:
                base_keys.add(k)

        # Check prior assistant messages (excluding the last message if user just sent one, or earlier assistant turns)
        assistant_msgs = [m for m in messages[:-1] if m.get("role") == "assistant"]
        if not assistant_msgs and messages and messages[-1].get("role") == "assistant":
            assistant_msgs = [m for m in messages[:-1] if m.get("role") == "assistant"]

        if not assistant_msgs:
            return []

        catalog = CatalogService()
        proposed_compounds_map: Dict[str, Dict[str, Any]] = {}
        removed_keys: Set[str] = set()

        for msg in assistant_msgs:
            content = str(msg.get("content", "")).strip()
            if not content:
                continue

            # 1. Check for action card XML/JSON blocks
            card_matches = re.findall(
                r'<action_card(?:\s+type=[\'"]?([^\'">\s]+)[\'"]?)?\s*>(.*?)(?:</action_card>|$)',
                content,
                re.DOTALL | re.IGNORECASE,
            )
            parsed_any_card = False
            for cm in card_matches:
                body = cm[1].strip()
                card_data = cls._extract_first_json_object(body)
                if card_data and isinstance(card_data, dict):
                    parsed_any_card = True
                    for add_item in (card_data.get("add") or card_data.get("additions") or []):
                        if isinstance(add_item, dict):
                            raw_k = str(add_item.get("key") or add_item.get("name") or "").strip().lower()
                            comp_rec = cls._resolve_compound(raw_k, catalog)
                            k = comp_rec["key"] if comp_rec else raw_k.replace(" ", "_")
                            if k and k not in base_keys:
                                item_copy = dict(add_item)
                                item_copy["key"] = k
                                if comp_rec and not item_copy.get("name"):
                                    item_copy["name"] = comp_rec.get("name")
                                proposed_compounds_map[k] = item_copy
                                removed_keys.discard(k)

                    for mod_item in (card_data.get("modify") or card_data.get("modifications") or []):
                        if isinstance(mod_item, dict):
                            raw_k = str(mod_item.get("key") or mod_item.get("name") or "").strip().lower()
                            comp_rec = cls._resolve_compound(raw_k, catalog)
                            k = comp_rec["key"] if comp_rec else raw_k.replace(" ", "_")
                            if k in proposed_compounds_map:
                                proposed_compounds_map[k].update(mod_item)

                    for rem_item in (card_data.get("remove") or card_data.get("removals") or []):
                        rem_k = str(rem_item.get("key") if isinstance(rem_item, dict) else rem_item).strip().lower()
                        comp_rec = cls._resolve_compound(rem_k, catalog)
                        k = comp_rec["key"] if comp_rec else rem_k.replace(" ", "_")
                        proposed_compounds_map.pop(k, None)
                        removed_keys.add(k)

            # 2. If no explicit action card in this message, extract from text
            if not parsed_any_card:
                extracted = cls.extract_from_text(content, base_stack=base_stack)
                if extracted:
                    for add_item in extracted.get("add", []):
                        k = str(add_item.get("key", "")).lower()
                        if k and k not in base_keys:
                            proposed_compounds_map[k] = add_item
                            removed_keys.discard(k)
                    for mod_item in extracted.get("modify", []):
                        k = str(mod_item.get("key", "")).lower()
                        if k in proposed_compounds_map:
                            proposed_compounds_map[k].update(mod_item)
                    for rem_k in extracted.get("remove", []):
                        k = str(rem_k).lower()
                        proposed_compounds_map.pop(k, None)
                        removed_keys.add(k)

        return list(proposed_compounds_map.values())

    @classmethod
    def extract_from_text(
        cls,
        text: str,
        base_stack: Optional[List[Any]] = None,
        biometrics: Optional[Dict[str, Any]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Main extraction entrypoint: scans markdown text for:
        1. Embedded XML <action_card> blocks (including unclosed tags or flexible attributes)
        2. Markdown code-fenced JSON stack diff blocks
        3. Circadian schedule tables (| Window | Compound | Dose & Route | Rationale |)
        4. Depot injection sections & bullet lists
        5. Targeted Synergies & Co-Factors bullet lines (including paired 'Compound A + Compound B')
        6. Conversational mutation directives (Add, Titrate, Remove)
        
        Returns a validated stack_diff action card dict if compounds were detected, or None.
        """
        if not text or not text.strip():
            return None

        catalog = CatalogService()
        biometrics = biometrics or {}

        # ---------------------------------------------------------------------
        # 1. Check for explicit <action_card> tags (complete or unclosed)
        # ---------------------------------------------------------------------
        action_card_match = re.search(
            r'<action_card(?:\s+type=[\'"]?([^\'">\s]+)[\'"]?)?\s*>(.*?)(?:</action_card>|$)',
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if action_card_match:
            card_body = action_card_match.group(2).strip()
            parsed_json = cls._extract_first_json_object(card_body)
            if parsed_json and isinstance(parsed_json, dict) and ("add" in parsed_json or "modify" in parsed_json or "remove" in parsed_json or "action_card" in parsed_json):
                from app.services.action_card_validator import ActionCardValidator
                sanitized, _ = ActionCardValidator.validate_and_sanitize_card(
                    card_type="stack_diff",
                    payload=parsed_json,
                    current_stack=base_stack,
                    biometrics=biometrics,
                )
                if messages:
                    prev_proposals = cls.extract_cumulative_proposals_from_history(messages, base_stack)
                    if prev_proposals:
                        current_adds = list(sanitized.get("add") or [])
                        seen = {str(a.get("key", "")).lower() for a in current_adds if a.get("key")}
                        current_rems = {str(r).lower() for r in (sanitized.get("remove") or [])}
                        for prev_p in prev_proposals:
                            pk = str(prev_p.get("key", "")).lower()
                            if pk and pk not in seen and pk not in current_rems:
                                seen.add(pk)
                                current_adds.append(prev_p)
                        sanitized["add"] = current_adds
                        sanitized, _ = ActionCardValidator.validate_and_sanitize_card(
                            card_type="stack_diff",
                            payload=sanitized,
                            current_stack=base_stack,
                            biometrics=biometrics,
                        )
                if sanitized.get("add") or sanitized.get("modify") or sanitized.get("remove"):
                    return sanitized

        # ---------------------------------------------------------------------
        # 2. Check for markdown code-fenced JSON blocks containing stack diffs
        # ---------------------------------------------------------------------
        for json_fence in re.findall(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text, re.IGNORECASE):
            try:
                data = json.loads(json_fence)
                if isinstance(data, dict) and ("add" in data or "modify" in data or "remove" in data or data.get("action_card") == "stack_diff"):
                    from app.services.action_card_validator import ActionCardValidator
                    sanitized, _ = ActionCardValidator.validate_and_sanitize_card(
                        card_type="stack_diff",
                        payload=data,
                        current_stack=base_stack,
                        biometrics=biometrics,
                    )
                    if messages:
                        prev_proposals = cls.extract_cumulative_proposals_from_history(messages, base_stack)
                        if prev_proposals:
                            current_adds = list(sanitized.get("add") or [])
                            seen = {str(a.get("key", "")).lower() for a in current_adds if a.get("key")}
                            current_rems = {str(r).lower() for r in (sanitized.get("remove") or [])}
                            for prev_p in prev_proposals:
                                pk = str(prev_p.get("key", "")).lower()
                                if pk and pk not in seen and pk not in current_rems:
                                    seen.add(pk)
                                    current_adds.append(prev_p)
                            sanitized["add"] = current_adds
                            sanitized, _ = ActionCardValidator.validate_and_sanitize_card(
                                card_type="stack_diff",
                                payload=sanitized,
                                current_stack=base_stack,
                                biometrics=biometrics,
                            )
                    if sanitized.get("add") or sanitized.get("modify") or sanitized.get("remove"):
                        return sanitized
            except Exception:
                pass

        # ---------------------------------------------------------------------
        # 3. Dynamic Text & Table Extraction
        # ---------------------------------------------------------------------
        extracted_additions: List[Dict[str, Any]] = []
        extracted_modifications: List[Dict[str, Any]] = []
        extracted_removals: List[str] = []
        seen_keys: Set[str] = set()

        # Step 3a: Extract explicit mutation directives (Add, Titrate/Modify, Remove)
        mutation_items = cls._extract_conversational_mutations(text, catalog)
        for m in mutation_items.get("add", []):
            if m["key"] not in seen_keys:
                seen_keys.add(m["key"])
                extracted_additions.append(m)
        for m in mutation_items.get("modify", []):
            extracted_modifications.append(m)
            seen_keys.add(m["key"])
        for r in mutation_items.get("remove", []):
            extracted_removals.append(r)

        # Step 3b: Extract Daily Circadian Schedule Tables
        table_compounds = cls._extract_from_schedule_tables(text, catalog)
        for c in table_compounds:
            if c["key"] not in seen_keys:
                seen_keys.add(c["key"])
                extracted_additions.append(c)

        # Step 3c: Extract Depot Injections
        depot_compounds = cls._extract_depot_injections(text, catalog)
        for c in depot_compounds:
            if c["key"] not in seen_keys:
                seen_keys.add(c["key"])
                extracted_additions.append(c)

        # Step 3d: Extract Targeted Synergies & Co-Factors / Protocol Bullets
        synergy_compounds = cls._extract_targeted_synergies(text, catalog)
        for c in synergy_compounds:
            if c["key"] not in seen_keys:
                seen_keys.add(c["key"])
                extracted_additions.append(c)

        # Step 3e: Incorporate unapplied previous proposals from conversation history if not explicitly removed
        if messages:
            prev_proposals = cls.extract_cumulative_proposals_from_history(messages, base_stack)
            if prev_proposals:
                removals_set = {str(r.get("key") if isinstance(r, dict) else r).strip().lower() for r in extracted_removals}
                for prev_p in prev_proposals:
                    k = str(prev_p.get("key", "")).lower()
                    if k and k not in seen_keys and k not in removals_set:
                        seen_keys.add(k)
                        extracted_additions.append(prev_p)

        if not extracted_additions and not extracted_modifications and not extracted_removals:
            return None

        raw_payload = {
            "action_card": "stack_diff",
            "add": extracted_additions,
            "modify": extracted_modifications,
            "remove": extracted_removals,
        }

        from app.services.action_card_validator import ActionCardValidator
        sanitized_payload, _ = ActionCardValidator.validate_and_sanitize_card(
            card_type="stack_diff",
            payload=raw_payload,
            current_stack=base_stack,
            biometrics=biometrics,
        )
        return sanitized_payload

    @classmethod
    def reconcile_card_with_text(
        cls,
        card_payload: Dict[str, Any],
        text: str,
        base_stack: Optional[List[Any]] = None,
        biometrics: Optional[Dict[str, Any]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Reconciles an action card against the model's markdown text and conversation history.
        Ensures that:
        1. All compounds mentioned in the text are present in the action card with matching dose & timing.
        2. Extraneous default blueprint compounds that were omitted by the model are pruned.
        3. If the user is refining an unapplied proposed stack across multi-turn chat, previous recommendations
           are preserved and merged with new additions.
        """
        if not isinstance(card_payload, dict):
            return card_payload

        catalog = CatalogService()
        text_extracted = cls.extract_from_text(text, base_stack, biometrics, messages=None)
        if not text_extracted and not messages:
            return card_payload

        text_add_keys = {str(a.get("key", "")).lower(): a for a in text_extracted.get("add", []) if a.get("key")} if text_extracted else {}

        # Reconcile additions
        existing_adds = card_payload.get("add") or card_payload.get("additions") or []
        reconciled_adds: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        # 1. Preserve and prioritize compounds explicitly extracted from the model's text
        for k, text_entry in text_add_keys.items():
            if k not in seen:
                seen.add(k)
                reconciled_adds.append(text_entry)

        # 2. If the text only described an incremental change (e.g. adding 1 compound to an existing stack),
        # keep other valid card entries that don't conflict.
        is_full_protocol_text = len(text_add_keys) >= 3 or ("schedule" in text.lower() and "|" in text)
        if not is_full_protocol_text:
            for a in existing_adds:
                k = str(a.get("key", "")).lower()
                if k and k not in seen:
                    seen.add(k)
                    reconciled_adds.append(a)

        # 3. Incorporate unapplied previous recommendations from conversation history
        if messages:
            prev_proposals = cls.extract_cumulative_proposals_from_history(messages, base_stack)
            if prev_proposals:
                current_removals = card_payload.get("remove") or card_payload.get("removals") or (text_extracted.get("remove") if text_extracted else [])
                removals_set = {str(r.get("key") if isinstance(r, dict) else r).strip().lower() for r in current_removals}
                for prev_p in prev_proposals:
                    k = str(prev_p.get("key", "")).lower()
                    if k and k not in seen and k not in removals_set:
                        seen.add(k)
                        reconciled_adds.append(prev_p)

        reconciled_payload = {
            "action_card": "stack_diff",
            "add": reconciled_adds,
            "modify": card_payload.get("modify") or (text_extracted.get("modify") if text_extracted else []) or [],
            "remove": card_payload.get("remove") or (text_extracted.get("remove") if text_extracted else []) or [],
        }

        from app.services.action_card_validator import ActionCardValidator
        sanitized, _ = ActionCardValidator.validate_and_sanitize_card(
            card_type="stack_diff",
            payload=reconciled_payload,
            current_stack=base_stack,
            biometrics=biometrics,
        )
        return sanitized

    # -------------------------------------------------------------------------
    # Internal Extraction Parsers
    # -------------------------------------------------------------------------

    @classmethod
    def _extract_from_schedule_tables(cls, text: str, catalog: CatalogService) -> List[Dict[str, Any]]:
        """
        Parses standard Daily Circadian Schedule Tables:
        | Window | Compound | Dose & Route | Pharmacokinetic Rationale |
        """
        results: List[Dict[str, Any]] = []
        
        for line in text.splitlines():
            line_s = line.strip()
            if not (line_s.startswith("|") and line_s.endswith("|")):
                continue

            cols = [c.strip() for c in line_s.split("|")[1:-1]]
            if len(cols) < 3:
                continue

            col1 = cols[0]
            col2 = cols[1]
            col3 = cols[2]

            col1_low = col1.lower().strip()
            col2_low = col2.lower().strip()

            # Skip header or divider rows
            if col1_low in ("window", "timing", "time", "circadian window", "administration window") or col2_low in ("compound", "agent", "supplement", "drug", "medication") or "---" in col1 or "---" in col2:
                continue

            timing_str = cls._normalize_timing(col1)
            raw_name = re.sub(r'[*_`]', '', col2).strip()
            dose_route_str = col3

            comp_rec = cls._resolve_compound(raw_name, catalog)
            if not comp_rec:
                continue

            c_key = comp_rec["key"]
            dose_val, dose_unit = cls._parse_dose_and_unit(dose_route_str, comp_rec)
            route = cls._parse_route(dose_route_str, comp_rec)
            freq = "daily"

            results.append({
                "key": c_key,
                "name": comp_rec.get("name") or c_key.replace("_", " ").title(),
                "dose": dose_val,
                "unit": dose_unit,
                "timing": timing_str,
                "route": route,
                "frequency": freq,
            })

        return results

    @classmethod
    def _extract_depot_injections(cls, text: str, catalog: CatalogService) -> List[Dict[str, Any]]:
        """
        Parses Depot Injections section, e.g.:
        ### Depot Injections (Weekly / Split Protocol)
        - **Testosterone Cypionate**: 175 mg IM Twice Weekly (Mon / Thu)
        """
        results: List[Dict[str, Any]] = []
        depot_section_match = re.search(
            r'(?:###?\s*(?:Depot\s+Injections|Injectable\s+Protocol|Weekly\s+Protocol|Depot\s+Administration)[\s\S]*?)(?:###|$)',
            text,
            re.IGNORECASE,
        )
        if not depot_section_match:
            return results

        depot_text = depot_section_match.group(0)
        lines = depot_text.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str.startswith(("-", "*", "•", "1.", "2.", "3.", "4.")):
                continue

            parsed_items = cls._parse_compound_line(line_str, catalog, default_route="intramuscular", default_timing="Twice Weekly (Mon / Thu)")
            results.extend(parsed_items)

        return results

    @classmethod
    def _extract_targeted_synergies(cls, text: str, catalog: CatalogService) -> List[Dict[str, Any]]:
        """
        Parses bullet lines from 'Targeted Synergies & Co-Factors' or general markdown protocol bullets:
        - Testosterone cypionate 175 mg IM Mon/Thu: stable AR occupancy...
        - Creatine 5 g + beta-alanine 3.2 g AM: PCr resynthesis...
        - Telmisartan 20 mg AM: AT1 blockade...
        - Pitavastatin 1 mg PM: HMGCR inhibition...
        """
        results: List[Dict[str, Any]] = []
        
        synergy_section_match = re.search(
            r'(?:###?\s*(?:\d+\.\s*)?(?:Targeted\s+Synergies|Protocol\s+Schedule|Core\s+Stack|Recommended\s+Protocol|Synergistic\s+Co-Factors)[\s\S]*?)(?:###|\n\n\n|$)',
            text,
            re.IGNORECASE,
        )
        search_text = synergy_section_match.group(0) if synergy_section_match else text

        for line in search_text.splitlines():
            line_str = line.strip()
            line_clean = re.sub(r'^(?:[-*•]|\d+\.)\s*', '', line_str).strip()
            if not line_clean or line_clean.startswith("#") or line_clean.startswith("|"):
                continue

            if not re.search(r'\b\d+(?:\.\d+)?\s*(?:mg|mcg|μg|ug|g|iu|u|ml)\b', line_clean, re.IGNORECASE):
                continue

            if any(ignore in line_clean.lower() for ignore in ["blood pressure", "resting bp", "egfr", "alt 2", "body fat", "body weight"]):
                if not any(c in line_clean.lower() for c in ["telmisartan", "nebivolol", "candesartan", "losartan", "tudca", "nac"]):
                    continue

            parsed_items = cls._parse_compound_line(line_clean, catalog)
            results.extend(parsed_items)

        return results

    @classmethod
    def _extract_conversational_mutations(cls, text: str, catalog: CatalogService) -> Dict[str, List[Any]]:
        """
        Detects conversational protocol adjustments:
        - **Add**: Telmisartan 20 mg oral daily (Morning)
        - **Titrate / Modify**: Testosterone Cypionate to 200 mg
        - **Remove / Discontinue**: Caffeine
        """
        additions: List[Dict[str, Any]] = []
        modifications: List[Dict[str, Any]] = []
        removals: List[str] = []

        lines = text.splitlines()
        for line in lines:
            line_str = line.strip()
            # Check Add
            add_match = re.search(r'(?:^\s*(?:[-*•]|\d+\.)?\s*(?:\+|⚡)?\s*(?:\*\*)?ADD(?:\*\*)?:?\s*)(.*)', line_str, re.IGNORECASE)
            if add_match:
                content = add_match.group(1).strip()
                parsed = cls._parse_compound_line(content, catalog)
                additions.extend(parsed)
                continue

            # Check Titrate / Modify
            mod_match = re.search(r'(?:^\s*(?:[-*•]|\d+\.)?\s*(?:~)?\s*(?:\*\*)?(?:TITRATE|MODIFY|ADJUST)(?:\*\*)?:?\s*)(.*)', line_str, re.IGNORECASE)
            if mod_match:
                content = mod_match.group(1).strip()
                parsed = cls._parse_compound_line(content, catalog)
                modifications.extend(parsed)
                continue

            # Check Remove
            rem_match = re.search(r'(?:^\s*(?:[-*•]|\d+\.)?\s*(?:-)?\s*(?:\*\*)?(?:REMOVE|DISCONTINUE|DROP|ELIMINATE)(?:\*\*)?:?\s*)(.*)', line_str, re.IGNORECASE)
            if rem_match:
                content = rem_match.group(1).strip()
                rec = cls._resolve_compound(content, catalog)
                if rec:
                    removals.append(rec["key"])
                else:
                    words = re.findall(r'[a-zA-Z0-9_\-]+', content)
                    if words:
                        removals.append(words[0].lower())
                continue

        return {"add": additions, "modify": modifications, "remove": removals}

    @classmethod
    def _parse_compound_line(
        cls,
        line: str,
        catalog: CatalogService,
        default_route: str = "oral",
        default_timing: str = "morning",
    ) -> List[Dict[str, Any]]:
        """
        Parses a single compound statement or compound pair line.
        """
        results: List[Dict[str, Any]] = []

        colon_parts = line.split(":", 1)
        spec_portion = colon_parts[0].strip()
        rationale_portion = colon_parts[1].strip() if len(colon_parts) > 1 else ""

        # Check for multi-compound pairs joined by '+' or ' & ' or ' and '
        segments = re.split(r'\s+(?:\+|\&|\band\b)\s+', spec_portion)

        line_timing = cls._extract_timing_from_string(spec_portion) or default_timing
        line_route = cls._extract_route_from_string(spec_portion) or default_route

        for seg in segments:
            seg_clean = seg.strip()
            if not seg_clean:
                continue

            comp_rec, dose_val, dose_unit, seg_route, seg_timing = cls._parse_single_compound_spec(seg_clean, catalog)
            if not comp_rec:
                continue

            c_key = comp_rec["key"]
            final_route = seg_route or line_route or comp_rec.get("route") or "oral"
            final_timing = seg_timing or line_timing

            inf_route, inf_freq = infer_compound_route_and_frequency(c_key)
            if "mon" in str(final_timing).lower() or "twice weekly" in str(final_timing).lower():
                final_freq = "twice weekly"
            elif "weekly" in str(final_timing).lower():
                final_freq = "weekly"
            else:
                final_freq = inf_freq or "daily"

            results.append({
                "key": c_key,
                "name": comp_rec.get("name") or c_key.replace("_", " ").title(),
                "dose": dose_val,
                "unit": dose_unit,
                "timing": final_timing,
                "route": final_route,
                "frequency": final_freq,
                "rationale": rationale_portion[:150] if rationale_portion else "",
            })

        return results

    @classmethod
    def _parse_single_compound_spec(
        cls,
        segment: str,
        catalog: CatalogService,
    ) -> Tuple[Optional[Dict[str, Any]], float, str, Optional[str], Optional[str]]:
        """
        Parses a single compound spec into: (record, dose_val, dose_unit, route, timing)
        """
        # Check for target titrated dose e.g. 'from 150 mg to 200 mg' or '150mg -> 200mg'
        to_match = re.search(r'(?:(?:\bto\b)|➔|->)\s*(\d+(?:\.\d+)?)\s*(mg|mcg|μg|ug|g|iu|u|ml)\b', segment, re.IGNORECASE)
        if to_match:
            dm = to_match
        else:
            dm = re.search(r'(\d+(?:\.\d+)?)\s*(mg|mcg|μg|ug|g|iu|u|ml)\b', segment, re.IGNORECASE)

        dose_val = 100.0
        dose_unit = "mg"

        if dm:
            raw_num = float(dm.group(1))
            raw_unit = dm.group(2).lower()
            if raw_unit == "g":
                dose_val = raw_num * 1000.0
                dose_unit = "mg"
            elif raw_unit in ("mcg", "ug"):
                dose_val = raw_num
                dose_unit = "μg"
            else:
                dose_val = raw_num
                dose_unit = raw_unit

        route = cls._extract_route_from_string(segment)
        timing = cls._extract_timing_from_string(segment)

        # Remove dose, route, timing keywords to isolate compound name
        name_candidate = segment
        if dm:
            name_candidate = name_candidate[:dm.start()] + " " + name_candidate[dm.end():]

        name_candidate = re.sub(
            r'\b(?:oral|im|subq|intramuscular|subcutaneous|sublingual|topical|transdermal|am|pm|mon/thu|mon|thu|morning|bedtime|evening|daily|twice weekly|split|from|to)\b',
            ' ',
            name_candidate,
            flags=re.IGNORECASE,
        )
        name_candidate = re.sub(r'[*_`\(\)\[\]➔\->]', ' ', name_candidate).strip()
        name_candidate = re.sub(r'\s+', ' ', name_candidate).strip()

        comp_rec = cls._resolve_compound(name_candidate, catalog)
        if not comp_rec:
            comp_rec = cls._resolve_compound(segment, catalog)

        if comp_rec and not dm:
            def_spec = get_default_compound_dose(comp_rec["key"])
            dose_val = float(def_spec.get("dose_mg", 100.0))
            dose_unit = def_spec.get("dose_unit", "mg")

        if isinstance(dose_val, float) and dose_val == int(dose_val):
            dose_val = int(dose_val)

        return comp_rec, dose_val, dose_unit, route, timing

    @classmethod
    def _resolve_compound(cls, query: str, catalog: CatalogService) -> Optional[Dict[str, Any]]:
        """Resolves a raw compound string against CatalogService using canonical and fuzzy synonym lookup."""
        q_clean = query.strip().lower()
        if not q_clean or len(q_clean) < 2:
            return None

        # 1. Direct match
        rec = catalog.get_compound(q_clean, auto_enrich=False) or catalog.find_by_synonym(q_clean)
        if rec:
            return rec

        # 2. Filter stop words & route/timing keywords
        stop_words = {
            'from', 'to', 'mg', 'mcg', 'ug', 'g', 'oral', 'im', 'subq', 'intramuscular', 'subcutaneous',
            'daily', 'weekly', 'twice', 'day', 'days', 'in', 'the', 'morning', 'bedtime', 'evening',
            'am', 'pm', 'with', 'dinner', 'breakfast', 'lunch', 'and', 'for', 'split', 'depot',
            'protocol', 'table', 'schedule', 'window', 'dose', 'route'
        }
        words = [w for w in re.findall(r'[a-z0-9]+', q_clean) if len(w) >= 2 and w not in stop_words and not w.isdigit()]

        # 3. Check n-grams from longest (3-words, 2-words) down to 1-word
        for n in range(min(3, len(words)), 0, -1):
            for i in range(len(words) - n + 1):
                ngram = '_'.join(words[i : i + n])
                ngram_space = ' '.join(words[i : i + n])
                rec = (
                    catalog.get_compound(ngram, auto_enrich=False)
                    or catalog.find_by_synonym(ngram)
                    or catalog.find_by_synonym(ngram_space)
                )
                if rec:
                    return rec

        return None

    @classmethod
    def _parse_dose_and_unit(cls, text: str, comp_rec: Dict[str, Any]) -> Tuple[float, str]:
        dm = re.search(r'(\d+(?:\.\d+)?)\s*(mg|mcg|μg|ug|g|iu|u|ml)\b', text, re.IGNORECASE)
        if dm:
            val = float(dm.group(1))
            unit = dm.group(2).lower()
            if unit == "g":
                val *= 1000.0
                unit = "mg"
            elif unit in ("mcg", "ug"):
                unit = "μg"
            if val == int(val):
                val = int(val)
            return val, unit

        def_spec = get_default_compound_dose(comp_rec.get("key", ""))
        return float(def_spec.get("dose_mg", 100.0)), def_spec.get("dose_unit", "mg")

    @classmethod
    def _parse_route(cls, text: str, comp_rec: Dict[str, Any]) -> str:
        route = cls._extract_route_from_string(text)
        if route:
            return route
        inf_route, _ = infer_compound_route_and_frequency(comp_rec.get("key", ""))
        return inf_route or comp_rec.get("route") or "oral"

    @classmethod
    def _extract_route_from_string(cls, text: str) -> Optional[str]:
        rm = re.search(r'\b(oral|im|subq|intramuscular|subcutaneous|sublingual|topical|transdermal)\b', text, re.IGNORECASE)
        if rm:
            r = rm.group(1).lower()
            if r == "im":
                return "intramuscular"
            if r == "subq":
                return "subcutaneous"
            return r
        return None

    @classmethod
    def _extract_timing_from_string(cls, text: str) -> Optional[str]:
        t_low = text.lower()
        if any(w in t_low for w in ["mon/thu", "mon / thu", "mon and thu", "twice weekly"]):
            return "Twice Weekly (Mon / Thu)"
        if any(w in t_low for w in ["bedtime", "pm", "night", "nocturnal", "with dinner", "evening"]):
            return "bedtime"
        if any(w in t_low for w in ["midday", "afternoon", "with lunch"]):
            return "midday"
        if any(w in t_low for w in ["pre-workout", "preworkout"]):
            return "pre-workout"
        if any(w in t_low for w in ["morning", "am", "with breakfast"]):
            return "morning"
        return None

    @classmethod
    def _normalize_timing(cls, raw_timing: str) -> str:
        extracted = cls._extract_timing_from_string(raw_timing)
        return extracted or raw_timing.strip().lower()

    @classmethod
    def _extract_first_json_object(cls, text: str) -> Optional[Dict[str, Any]]:
        """Attempts to parse the first JSON object from a string even if followed by trailing text."""
        try:
            return json.loads(text)
        except Exception:
            pass

        start_idx = text.find("{")
        if start_idx == -1:
            return None

        bracket_depth = 0
        in_string = False
        escape_char = False

        for i in range(start_idx, len(text)):
            char = text[i]
            if escape_char:
                escape_char = False
                continue
            if char == "\\":
                escape_char = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char == "{":
                    bracket_depth += 1
                elif char == "}":
                    bracket_depth -= 1
                    if bracket_depth == 0:
                        candidate = text[start_idx : i + 1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            return None
        return None
