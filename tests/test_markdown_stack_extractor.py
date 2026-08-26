import pytest
from app.services.markdown_protocol_parser import MarkdownProtocolParser
from app.services.catalog_service import CatalogService


def test_parse_user_exact_example():
    """
    Test extracting the exact user reported response:
    - Testosterone cypionate 175 mg IM Mon/Thu
    - Creatine 5 g + beta-alanine 3.2 g AM
    - Telmisartan 20 mg AM
    - Pitavastatin 1 mg PM
    """
    text = """
Targeted Synergies & Co-Factors:

Testosterone cypionate 175 mg IM Mon/Thu: stable AR occupancy; split dosing reduces Cmax/trough swings vs weekly.

Creatine 5 g + beta-alanine 3.2 g AM: PCr resynthesis and carnosine H+ buffering for high-threshold training.

Telmisartan 20 mg AM: AT1 blockade/PPARγ partial agonism protects renal microcirculation and insulin sensitivity.

Pitavastatin 1 mg PM: HMGCR inhibition timed to nocturnal hepatic cholesterol synthesis; minimal CYP3A4 conflict.
"""
    result = MarkdownProtocolParser.extract_from_text(text)
    assert result is not None
    assert "add" in result
    adds = result["add"]
    assert len(adds) == 5

    add_map = {a["key"]: a for a in adds}
    assert "testosterone_cypionate" in add_map
    assert add_map["testosterone_cypionate"]["dose"] == 175
    assert add_map["testosterone_cypionate"]["unit"] == "mg"
    assert add_map["testosterone_cypionate"]["route"] == "intramuscular"
    assert "mon" in add_map["testosterone_cypionate"]["timing"].lower() or "twice weekly" in add_map["testosterone_cypionate"]["timing"].lower()

    assert "creatine" in add_map
    assert add_map["creatine"]["dose"] == 5000
    assert add_map["creatine"]["unit"] == "mg"
    assert add_map["creatine"]["timing"] == "morning"

    assert "beta_alanine" in add_map
    assert add_map["beta_alanine"]["dose"] == 3200
    assert add_map["beta_alanine"]["unit"] == "mg"
    assert add_map["beta_alanine"]["timing"] == "morning"

    assert "telmisartan" in add_map
    assert add_map["telmisartan"]["dose"] == 20
    assert add_map["telmisartan"]["unit"] == "mg"
    assert add_map["telmisartan"]["timing"] == "morning"

    assert "pitavastatin" in add_map
    assert add_map["pitavastatin"]["dose"] == 1
    assert add_map["pitavastatin"]["unit"] == "mg"
    assert add_map["pitavastatin"]["timing"] == "bedtime"

    # Verify that unmentioned blueprint compounds (L-Carnitine, Citrus Bergamot, Anastrozole) are NOT in the card
    assert "l_carnitine" not in add_map
    assert "citrus_bergamot" not in add_map
    assert "anastrozole" not in add_map


def test_parse_table_and_depot():
    """
    Test extraction from Circadian Schedule Table and Depot Injection header.
    """
    text = """
### Depot Injections (Weekly / Split Protocol)
- **Testosterone Cypionate**: 175 mg IM Twice Weekly (Mon / Thu) — Nuclear AR occupancy

### Daily Circadian Schedule Table
| Window | Compound | Dose & Route | Pharmacokinetic & Chronobiological Rationale |
| Morning | Creatine Monohydrate | 5000 mg oral | Phosphocreatine shuttle |
| Morning | Beta-Alanine | 3200 mg oral | Carnosine buffer |
| Morning | Telmisartan | 20 mg oral | Renal microcirculation |
| Bedtime | Pitavastatin | 1 mg oral | Nighttime HMGCR inhibition |
"""
    result = MarkdownProtocolParser.extract_from_text(text)
    assert result is not None
    adds = result["add"]
    assert len(adds) == 5
    keys = {a["key"] for a in adds}
    assert keys == {"testosterone_cypionate", "creatine", "beta_alanine", "telmisartan", "pitavastatin"}


def test_parse_conversational_mutations():
    """
    Test extraction from multi-turn conversational directives.
    """
    text = """
I have adjusted your protocol based on your request:
- **Add**: Telmisartan 20 mg oral daily in the morning
- **Titrate**: Testosterone Cypionate from 150 mg to 200 mg IM Twice Weekly
- **Remove**: Caffeine
"""
    result = MarkdownProtocolParser.extract_from_text(text)
    assert result is not None
    assert len(result["add"]) == 1
    assert result["add"][0]["key"] == "telmisartan"

    assert len(result["modify"]) == 1
    assert result["modify"][0]["key"] == "testosterone_cypionate"
    assert result["modify"][0]["dose"] == 200

    assert len(result["remove"]) == 1
    assert "caffeine" in result["remove"]


def test_parse_code_fenced_json():
    """
    Test extraction from code-fenced json block.
    """
    text = """
Here is the proposed protocol:
```json
{
  "action_card": "stack_diff",
  "add": [
    {"key": "telmisartan", "name": "Telmisartan", "dose": 40, "unit": "mg", "timing": "morning", "route": "oral"}
  ],
  "modify": [],
  "remove": []
}
```
"""
    result = MarkdownProtocolParser.extract_from_text(text)
    assert result is not None
    assert len(result["add"]) == 1
    assert result["add"][0]["key"] == "telmisartan"
    assert result["add"][0]["dose"] == 40


def test_reconcile_card_with_text():
    """
    Test reconciling an action card containing a default 7-compound blueprint
    against markdown text specifying only 5 compounds (including Pitavastatin).
    """
    blueprint_card = {
        "action_card": "stack_diff",
        "add": [
            {"key": "testosterone_cypionate", "name": "Testosterone Cypionate", "dose": 175, "unit": "mg", "timing": "Twice Weekly (Mon / Thu)", "route": "intramuscular"},
            {"key": "creatine", "name": "Creatine Monohydrate", "dose": 5000, "unit": "mg", "timing": "morning", "route": "oral"},
            {"key": "beta_alanine", "name": "Beta-Alanine", "dose": 3200, "unit": "mg", "timing": "morning", "route": "oral"},
            {"key": "l_carnitine", "name": "L-Carnitine L-Tartrate", "dose": 2000, "unit": "mg", "timing": "morning", "route": "oral"},
            {"key": "citrus_bergamot", "name": "Citrus Bergamot", "dose": 500, "unit": "mg", "timing": "morning", "route": "oral"},
            {"key": "telmisartan", "name": "Telmisartan", "dose": 20, "unit": "mg", "timing": "morning", "route": "oral"},
            {"key": "anastrozole", "name": "Anastrozole", "dose": 500, "unit": "μg", "timing": "morning", "route": "oral"},
        ],
        "modify": [],
        "remove": [],
    }

    model_text = """
Targeted Synergies & Co-Factors:

Testosterone cypionate 175 mg IM Mon/Thu: stable AR occupancy; split dosing reduces Cmax/trough swings vs weekly.

Creatine 5 g + beta-alanine 3.2 g AM: PCr resynthesis and carnosine H+ buffering for high-threshold training.

Telmisartan 20 mg AM: AT1 blockade/PPARγ partial agonism protects renal microcirculation and insulin sensitivity.

Pitavastatin 1 mg PM: HMGCR inhibition timed to nocturnal hepatic cholesterol synthesis; minimal CYP3A4 conflict.
"""

    reconciled = MarkdownProtocolParser.reconcile_card_with_text(blueprint_card, model_text)
    assert reconciled is not None
    adds = reconciled["add"]
    add_keys = {a["key"] for a in adds}
    assert add_keys == {"testosterone_cypionate", "creatine", "beta_alanine", "telmisartan", "pitavastatin"}
    assert "l_carnitine" not in add_keys
    assert "citrus_bergamot" not in add_keys
    assert "anastrozole" not in add_keys
