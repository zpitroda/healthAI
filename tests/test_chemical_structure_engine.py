import pytest
from app.services.chemical_structure_engine import ChemicalStructureEngine, is_17a_alkylated, is_19nor_steroid, is_aromatizable_androgen

def test_parse_smiles_invalid():
    assert ChemicalStructureEngine.parse_smiles(None) is None
    assert ChemicalStructureEngine.parse_smiles("") is None
    assert ChemicalStructureEngine.parse_smiles("   ") is None

def test_parse_smiles_simple():
    atoms = ChemicalStructureEngine.parse_smiles("CCO")
    assert len(atoms) == 3
    assert atoms[0]["symbol"] == "C"
    assert atoms[1]["symbol"] == "C"
    assert atoms[2]["symbol"] == "O"

def test_find_rings():
    # Cyclohexane C1CCCCC1
    atoms = ChemicalStructureEngine.parse_smiles("C1CCCCC1")
    rings = ChemicalStructureEngine.find_rings(atoms)
    assert len(rings) == 1
    assert len(rings[0]) == 6

def test_analyze_structure_testosterone():
    # Testosterone (not 17a-alkylated, not 19-nor, aromatizable, not 5a-reduced)
    # SMILES: CC12CCC3C(C1CCC2O)CCC4=CC(=O)CCC34C
    smiles = "CC12CCC3C(C1CCC2O)CCC4=CC(=O)CCC34C"
    analysis = ChemicalStructureEngine.analyze_structure(smiles)
    
    assert analysis["is_steroid"] is True
    assert analysis["is_c17_alkylated"] is False
    assert analysis["is_19_nor"] is False
    assert analysis["is_aromatizable"] is True
    assert analysis["is_conjugated_triene"] is False
    assert analysis["is_5alpha_reduced"] is False

def test_analyze_structure_trenbolone():
    # Trenbolone (19-nor, conjugated triene, not aromatizable)
    # SMILES: C12CCC3C(C1CCC2O)C=CC4=CC(=O)CCC34
    smiles = "C12CCC3C(C1CCC2O)C=CC4=CC(=O)CCC34"
    analysis = ChemicalStructureEngine.analyze_structure(smiles)
    
    assert analysis["is_steroid"] is True
    assert analysis["is_19_nor"] is True
    assert analysis["is_aromatizable"] is False

def test_is_17a_alkylated():
    # Helper wrappers
    # Mock compound missing smiles, but with drug_class
    compound = {"drug_class": "17aa"}
    assert is_17a_alkylated(compound) is False
    
    compound2 = {"categories": ["17alpha-alkylated"]}
    assert is_17a_alkylated(compound2) is True
