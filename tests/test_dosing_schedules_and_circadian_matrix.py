import pytest
from app.services.action_card_validator import ActionCardValidator
from app.services.catalog_service import CatalogService
from app.services.dosing_service import (
    normalize_dosing_frequency,
    get_frequency_multiplier,
    get_frequency_interval_hours,
    infer_compound_route_and_frequency,
)
from app.services.markdown_protocol_parser import MarkdownProtocolParser
from app.services.stack_intent_engine import StackIntentEngine


class TestDosingSchedulesAndCircadianMatrix:
    """Validates flexible dosing schedules across Copilot parsing, validation, and rendering."""

    def test_dosing_service_frequency_normalization(self):
        assert normalize_dosing_frequency("every_other_day") == "every_other_day"
        assert normalize_dosing_frequency("eod") == "every_other_day"
        assert normalize_dosing_frequency("qod") == "every_other_day"
        assert normalize_dosing_frequency("Every Other Day") == "every_other_day"

        assert normalize_dosing_frequency("three_times_weekly") == "three_times_weekly"
        assert normalize_dosing_frequency("3x_weekly") == "three_times_weekly"
        assert normalize_dosing_frequency("3x/week") == "three_times_weekly"
        assert normalize_dosing_frequency("tiw") == "three_times_weekly"
        assert normalize_dosing_frequency("Mon/Wed/Fri") == "three_times_weekly"

        assert normalize_dosing_frequency("twice_weekly") == "twice_weekly"
        assert normalize_dosing_frequency("mon/thu") == "twice_weekly"
        assert normalize_dosing_frequency("biw") == "twice_weekly"

        assert normalize_dosing_frequency("weekly") == "weekly"
        assert normalize_dosing_frequency("qw") == "weekly"

        assert normalize_dosing_frequency("as_needed") == "as_needed"
        assert normalize_dosing_frequency("prn") == "as_needed"

    def test_dosing_service_multipliers(self):
        assert get_frequency_multiplier("every_other_day") == 0.5
        assert round(get_frequency_multiplier("three_times_weekly"), 4) == round(3.0 / 7.0, 4)
        assert round(get_frequency_multiplier("twice_weekly"), 4) == round(2.0 / 7.0, 4)
        assert round(get_frequency_multiplier("weekly"), 4) == round(1.0 / 7.0, 4)

        assert get_frequency_interval_hours("every_other_day") == 48.0
        assert get_frequency_interval_hours("three_times_weekly") == 56.0
        assert get_frequency_interval_hours("twice_weekly") == 84.0
        assert get_frequency_interval_hours("weekly") == 168.0

    def test_infer_compound_route_and_frequency_trenbolone_acetate(self):
        route, freq = infer_compound_route_and_frequency("trenbolone_acetate")
        assert route == "intramuscular"
        assert freq == "every_other_day"

    def test_action_card_validator_trenbolone_acetate_eod(self):
        raw_card = {
            "add": [
                {
                    "id": "trenbolone_acetate",
                    "name": "Trenbolone Acetate",
                    "dose": 100,
                    "unit": "mg",
                    "route": "intramuscular",
                    "frequency": "every_other_day",
                    "timing": "Every Other Day (EOD)",
                }
            ]
        }
        res, _ = ActionCardValidator.validate_and_sanitize_card("stack_diff", raw_card, current_stack=[])
        assert res is not None
        sanitized = res["add"][0]
        assert sanitized["key"] == "trenbolone_acetate"
        assert sanitized["dose"] == 100.0
        assert sanitized["unit"] == "mg"
        assert sanitized["route"] == "intramuscular"
        assert sanitized["frequency"] == "every_other_day"
        assert sanitized["timing"] == "Every Other Day (EOD)"

    def test_action_card_validator_preserves_interval_schedules(self):
        raw_card = {
            "add": [
                {
                    "key": "anastrozole",
                    "dose": 0.5,
                    "unit": "mg",
                    "route": "oral",
                    "frequency": "three_times_weekly",
                    "timing": "Three Times Weekly (Mon / Wed / Fri)",
                },
                {
                    "key": "tadalafil",
                    "dose": 5,
                    "unit": "mg",
                    "route": "oral",
                    "frequency": "daily",
                    "timing": "Morning",
                },
                {
                    "key": "sildenafil",
                    "dose": 50,
                    "unit": "mg",
                    "route": "oral",
                    "frequency": "as_needed",
                    "timing": "As Needed (PRN)",
                },
            ]
        }
        res, _ = ActionCardValidator.validate_and_sanitize_card("stack_diff", raw_card, current_stack=[])
        assert res is not None
        items = {item["key"]: item for item in res["add"]}

        assert items["anastrozole"]["frequency"] == "three_times_weekly"
        assert items["anastrozole"]["timing"] == "Three Times Weekly (Mon / Wed / Fri)"

        assert items["tadalafil"]["frequency"] == "daily"
        assert items["tadalafil"]["timing"] == "Morning"

        assert items["sildenafil"]["frequency"] == "as_needed"
        assert items["sildenafil"]["timing"] == "As Needed (PRN)"

    def test_markdown_parser_extracts_eod_and_flexible_schedules(self):
        md_text = """
### Recommended Protocol
- Trenbolone Acetate 100 mg IM EOD: short-acting 19-nor androgen [PMID: 29179383]
- Anastrozole 0.5 mg Oral 3x/week: aromatase inhibition
- Semaglutide 0.5 mg SubQ Weekly: GLP-1 agonism
- Telmisartan 40 mg Oral Morning: AT1 receptor blockade
"""
        parsed = MarkdownProtocolParser.extract_from_text(md_text)
        items = {c["key"]: c for c in parsed.get("add", [])}

        assert "trenbolone_acetate" in items
        assert items["trenbolone_acetate"]["dose"] == 100
        assert items["trenbolone_acetate"]["unit"] == "mg"
        assert items["trenbolone_acetate"]["route"] == "intramuscular"
        assert items["trenbolone_acetate"]["frequency"] == "every_other_day"
        assert "Every Other Day" in items["trenbolone_acetate"]["timing"]

        assert "anastrozole" in items
        assert items["anastrozole"]["frequency"] == "three_times_weekly"
        assert "Three Times Weekly" in items["anastrozole"]["timing"]

        assert "semaglutide" in items
        assert items["semaglutide"]["frequency"] == "weekly"

        assert "telmisartan" in items
        assert items["telmisartan"]["frequency"] == "daily"
        assert items["telmisartan"]["timing"] == "morning"

    def test_stack_intent_engine_user_requested_tren_ace_eod(self):
        proposal = StackIntentEngine.build_scratch_stack_proposal(
            goal_id="anabolic_physique",
            requested_compounds=["trenbolone_acetate:100mg:every_other_day:intramuscular"],
        )
        compounds = {c["key"]: c for c in proposal.get("compounds", [])}
        assert "trenbolone_acetate" in compounds
        tren = compounds["trenbolone_acetate"]
        assert tren["dose"] == 100
        assert tren["unit"] == "mg"
        assert tren["route"] == "intramuscular"
        assert tren["frequency"] == "every_other_day"
        assert "Every Other Day" in tren["timing"]
