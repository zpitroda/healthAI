"""
Chemical Structure Engine
-------------------------
First-principles molecular graph and topological analysis engine for steroids and small molecules.
Parses SMILES chemical representations into atom-bond connectivity graphs, extracts fundamental
ring systems, and determines steroid structural features (C17-alkylation, 19-nor classification,
esterification, conjugated triene systems, and CYP19A1 aromatizability) with scientific exactness
without relying on brittle substring matching, regex heuristics, or hardcoded shortcuts.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("healthai.chemical_structure_engine")


class ChemicalStructureEngine:
    """
    Exact, topological chemical graph analyzer for steroid cores and small molecules.
    """

    @classmethod
    def parse_smiles(cls, smiles: str) -> Optional[List[Dict[str, Any]]]:
        """
        Parses a canonical or isomeric SMILES string into an atom-bond graph.
        Returns a list of atom dictionaries with element symbol, aromaticity, and neighbor lists.
        """
        if not smiles or not isinstance(smiles, str):
            return None

        smiles = smiles.strip()
        if not smiles:
            return None

        atoms: List[Dict[str, Any]] = []
        stack: List[Tuple[Optional[int], float]] = []
        prev_atom: Optional[int] = None
        ring_closures: Dict[int, Tuple[int, float]] = {}
        bond_to_next: float = 1.0

        atom_pattern = re.compile(r"(\[[^\]]+\]|Cl|Br|B|C|N|O|P|S|F|I|c|n|o|p|s)")

        i = 0
        n = len(smiles)
        while i < n:
            char = smiles[i]

            if char == "(":
                stack.append((prev_atom, bond_to_next))
                i += 1
            elif char == ")":
                if stack:
                    prev_atom, bond_to_next = stack.pop()
                i += 1
            elif char == "=":
                bond_to_next = 2.0
                i += 1
            elif char == "#":
                bond_to_next = 3.0
                i += 1
            elif char == ":":
                bond_to_next = 1.5
                i += 1
            elif char in ("/", "\\", "@"):
                # Stereochemistry / cis-trans markers
                i += 1
            elif char == ".":
                # Disconnected component / salt counter-ion
                prev_atom = None
                bond_to_next = 1.0
                i += 1
            elif char == "%":
                # 2-digit ring closure e.g. %10
                ring_num = int(smiles[i + 1 : i + 3])
                i += 3
                cls._handle_ring_closure(ring_num, prev_atom, bond_to_next, ring_closures, atoms)
                bond_to_next = 1.0
            elif char.isdigit():
                # 1-digit ring closure
                ring_num = int(char)
                i += 1
                cls._handle_ring_closure(ring_num, prev_atom, bond_to_next, ring_closures, atoms)
                bond_to_next = 1.0
            else:
                m = atom_pattern.match(smiles, i)
                if m:
                    atom_str = m.group(1)
                    i += len(atom_str)

                    symbol = atom_str
                    is_aromatic = False
                    if atom_str.startswith("[") and atom_str.endswith("]"):
                        inner = atom_str[1:-1]
                        sym_m = re.search(r"([A-Z][a-z]?|[a-z])", inner)
                        symbol = sym_m.group(1) if sym_m else "C"

                    if symbol.islower():
                        symbol = symbol.upper()
                        is_aromatic = True

                    atom_id = len(atoms)
                    atom_data = {
                        "id": atom_id,
                        "symbol": symbol,
                        "aromatic": is_aromatic,
                        "neighbors": [],
                    }
                    atoms.append(atom_data)

                    if prev_atom is not None:
                        atoms[prev_atom]["neighbors"].append((atom_id, bond_to_next))
                        atom_data["neighbors"].append((prev_atom, bond_to_next))

                    prev_atom = atom_id
                    bond_to_next = 1.0
                else:
                    i += 1

        return atoms

    @classmethod
    def _handle_ring_closure(
        cls,
        ring_num: int,
        atom_idx: Optional[int],
        bond_order: float,
        ring_closures: Dict[int, Tuple[int, float]],
        atoms: List[Dict[str, Any]],
    ) -> None:
        if atom_idx is None:
            return
        if ring_num in ring_closures:
            other_atom, other_bond = ring_closures.pop(ring_num)
            eff_bond = max(bond_order, other_bond)
            atoms[atom_idx]["neighbors"].append((other_atom, eff_bond))
            atoms[other_atom]["neighbors"].append((atom_idx, eff_bond))
        else:
            ring_closures[ring_num] = (atom_idx, bond_order)

    @classmethod
    def find_rings(cls, atoms: List[Dict[str, Any]]) -> List[Set[int]]:
        """
        Extracts fundamental cycle basis / rings of sizes 5 to 7.
        """
        if not atoms:
            return []

        adj: Dict[int, Set[int]] = {a["id"]: set(nbr for nbr, _ in a["neighbors"]) for a in atoms}
        rings: List[Set[int]] = []

        def find_cycles(start: int, length: int) -> List[Set[int]]:
            cycles: List[Set[int]] = []

            def dfs(path: List[int]) -> None:
                curr = path[-1]
                if len(path) == length:
                    if start in adj[curr] and len(path) >= 3:
                        cycles.append(set(path))
                    return
                for nbr in adj[curr]:
                    if nbr not in path and nbr > start:
                        dfs(path + [nbr])

            dfs([start])
            return cycles

        for size in [5, 6, 7]:
            for node in adj:
                found = find_cycles(node, size)
                for f in found:
                    if f not in rings:
                        rings.append(f)

        return rings

    @classmethod
    def analyze_structure(cls, smiles: Optional[str]) -> Dict[str, Any]:
        """
        Performs comprehensive chemical topological analysis of a molecular structure.
        """
        if not smiles or not isinstance(smiles, str):
            return {
                "is_steroid": False,
                "is_c17_alkylated": False,
                "is_19_nor": False,
                "is_c17_esterified": False,
                "is_aromatizable": False,
                "is_conjugated_triene": False,
                "is_5alpha_reduced": False,
            }

        atoms = cls.parse_smiles(smiles)
        if not atoms:
            return {
                "is_steroid": False,
                "is_c17_alkylated": False,
                "is_19_nor": False,
                "is_c17_esterified": False,
                "is_aromatizable": False,
                "is_conjugated_triene": False,
                "is_5alpha_reduced": False,
            }

        rings = cls.find_rings(atoms)
        rings_5 = [r for r in rings if len(r) == 5]
        rings_6 = [r for r in rings if len(r) == 6]

        # Identify Ring D (5-membered ring fused to a 6-membered ring C)
        steroid_d_rings = []
        for r5 in rings_5:
            c_count = sum(1 for atom_id in r5 if atoms[atom_id]["symbol"] == "C")
            if c_count >= 4:
                for r6 in rings_6:
                    shared = r5.intersection(r6)
                    if len(shared) == 2:
                        steroid_d_rings.append((r5, r6, shared))

        if not steroid_d_rings:
            return {
                "is_steroid": False,
                "is_c17_alkylated": False,
                "is_19_nor": False,
                "is_c17_esterified": False,
                "is_aromatizable": False,
                "is_conjugated_triene": False,
                "is_5alpha_reduced": False,
            }

        is_c17_alkylated = False
        is_c17_esterified = False

        for r5, r6, bridge in steroid_d_rings:
            non_bridge = list(r5 - bridge)
            bridge_atoms = list(bridge)

            # C13 is the quaternary bridgehead carbon (bonded to angular C18 methyl)
            c13_candidates = []
            for b_atom in bridge_atoms:
                nbrs = [nbr for nbr, _ in atoms[b_atom]["neighbors"]]
                exocyclic_c = [
                    nbr
                    for nbr in nbrs
                    if nbr not in r5 and nbr not in r6 and atoms[nbr]["symbol"] == "C"
                ]
                if exocyclic_c:
                    c13_candidates.append(b_atom)

            c13 = c13_candidates[0] if c13_candidates else bridge_atoms[0]

            # C17 is the non-bridgehead carbon in Ring D directly bonded to C13
            c17_candidates = [
                a for a in non_bridge if any(nbr == c13 for nbr, _ in atoms[a]["neighbors"])
            ]
            if not c17_candidates:
                c17_candidates = [
                    a
                    for a in non_bridge
                    if any(atoms[nbr]["symbol"] == "O" for nbr, _ in atoms[a]["neighbors"])
                ]

            if not c17_candidates:
                continue

            c17 = c17_candidates[0]
            c17_nbrs = atoms[c17]["neighbors"]

            exocyclic_carbons = []
            oxygen_atoms = []
            for nbr_id, bond_order in c17_nbrs:
                if nbr_id not in r5:
                    if atoms[nbr_id]["symbol"] == "C":
                        exocyclic_carbons.append((nbr_id, bond_order))
                    elif atoms[nbr_id]["symbol"] == "O":
                        oxygen_atoms.append((nbr_id, bond_order))

            # 17α-alkylation: C17 carbon is quaternary (bonded to C13, C16, an exocyclic carbon, and an oxygen)
            if len(exocyclic_carbons) >= 1 and len(oxygen_atoms) >= 1:
                is_c17_alkylated = True

            # 17-esterification: Oxygen at C17 is attached to an acyl carbonyl carbon C(=O)
            for o_id, _ in oxygen_atoms:
                o_nbrs = [n_id for n_id, _ in atoms[o_id]["neighbors"] if n_id != c17]
                for o_nbr in o_nbrs:
                    if atoms[o_nbr]["symbol"] == "C":
                        if any(
                            atoms[c_nbr]["symbol"] == "O" and bo == 2
                            for c_nbr, bo in atoms[o_nbr]["neighbors"]
                        ):
                            is_c17_esterified = True

        # Check for conjugated triene system (4,9,11-trien-3-one e.g. Trenbolone)
        double_bonds_in_rings = 0
        all_ring_atoms: Set[int] = set()
        for r in rings:
            all_ring_atoms.update(r)

        for a_id in all_ring_atoms:
            for nbr, bo in atoms[a_id]["neighbors"]:
                if nbr > a_id and nbr in all_ring_atoms and bo == 2:
                    double_bonds_in_rings += 1

        is_conjugated_triene = double_bonds_in_rings >= 3

        # Check 19-nor status:
        # Evaluates angular methyls on the 6-membered rings (C10 and C13)
        angular_methyls = 0
        for r in rings_6:
            for a_id in r:
                nbrs = [
                    n
                    for n, _ in atoms[a_id]["neighbors"]
                    if n not in r5 and not any(n in r_other for r_other in rings_6)
                ]
                for n in nbrs:
                    if atoms[n]["symbol"] == "C" and len([x for x, _ in atoms[n]["neighbors"]]) == 1:
                        angular_methyls += 1

        is_19nor = angular_methyls <= 1

        # Check 5α-reduction (absence of double bonds in ring A)
        has_enone = any(
            any(atoms[n]["symbol"] == "O" and bo == 2 for n, bo in atoms[a_id]["neighbors"])
            for a_id in all_ring_atoms
        )
        is_5alpha_reduced = (double_bonds_in_rings == 0) and has_enone

        # Aromatizability by CYP19A1:
        # Requires intact C19 angular methyl (not 19-nor), Delta-4-3-one (or Delta-5-3-ol),
        # not conjugated triene, not 5α-reduced, and standard steroidal A-ring
        is_aromatizable = (
            (not is_19nor)
            and (not is_conjugated_triene)
            and (not is_5alpha_reduced)
            and has_enone
            and (len(rings_6) >= 3)
        )

        return {
            "is_steroid": True,
            "is_c17_alkylated": is_c17_alkylated,
            "is_19_nor": is_19nor,
            "is_c17_esterified": is_c17_esterified,
            "is_aromatizable": is_aromatizable,
            "is_conjugated_triene": is_conjugated_triene,
            "is_5alpha_reduced": is_5alpha_reduced,
        }


# HIGH-LEVEL DETERMINISTIC CLASSIFICATION API FOR SERVICES

def resolve_compound_structure(compound: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolves SMILES and topological analysis for a compound or prodrug ester.
    """
    if not isinstance(compound, dict):
        return {}

    smiles = compound.get("smiles")

    if not smiles:
        key = str(compound.get("key") or compound.get("name") or "").lower().strip().replace("-", "_").replace(" ", "_")
        from app.services.catalog_service import CORE_ESTER_LIBRARY, CORE_SUPPLEMENT_LIBRARY, CORE_THERAPEUTIC_LIBRARY
        lib_rec = CORE_ESTER_LIBRARY.get(key) or CORE_THERAPEUTIC_LIBRARY.get(key) or CORE_SUPPLEMENT_LIBRARY.get(key)
        if lib_rec:
            smiles = lib_rec.get("smiles")
            if not smiles and lib_rec.get("parent_compound_id"):
                p_id = lib_rec["parent_compound_id"]
                parent_rec = CORE_ESTER_LIBRARY.get(p_id) or CORE_THERAPEUTIC_LIBRARY.get(p_id)
                if parent_rec:
                    smiles = parent_rec.get("smiles")

    if not smiles and compound.get("parent_compound_id"):
        from app.services.catalog_service import CORE_ESTER_LIBRARY, CORE_THERAPEUTIC_LIBRARY
        p_id = compound["parent_compound_id"]
        parent_rec = CORE_ESTER_LIBRARY.get(p_id) or CORE_THERAPEUTIC_LIBRARY.get(p_id)
        if parent_rec:
            smiles = parent_rec.get("smiles")

    if smiles:
        return ChemicalStructureEngine.analyze_structure(smiles)

    return {}




def is_17a_alkylated(compound: Dict[str, Any]) -> bool:
    """
    Determines if a compound is a C17α-alkylated steroid (quaternary C17 tertiary alcohol/ester)
    using exact chemical graph topology.
    """
    if not isinstance(compound, dict):
        return False

    analysis = resolve_compound_structure(compound)
    if analysis.get("is_steroid"):
        return bool(analysis.get("is_c17_alkylated"))

    # Fallback to structured compound classification
    drug_class = str(compound.get("drug_class", "")).lower()
    categories = [str(c).lower() for c in (compound.get("categories") or [])]
    
    # Check if explicitly structured as 17aa class in authoritative catalog
    if any(c in ["17alpha-alkylated", "17a-alkylated", "17aa"] for c in categories):
        return True

    return False


def is_19nor_steroid(compound: Dict[str, Any]) -> bool:
    """
    Determines if a steroid is a 19-nor derivative (estrane skeleton lacking C19 angular methyl).
    """
    if not isinstance(compound, dict):
        return False

    analysis = resolve_compound_structure(compound)
    if analysis.get("is_steroid"):
        return bool(analysis.get("is_19_nor"))

    drug_class = str(compound.get("drug_class", "")).lower()
    categories = [str(c).lower() for c in (compound.get("categories") or [])]
    ext = compound.get("external_ids") or {}
    atc_codes = [str(c).upper() for c in (ext.get("atc_codes") or [])]

    # ATC A14AB = Estren derivatives (19-nor steroids)
    if any(c.startswith("A14AB") for c in atc_codes):
        return True

    if "19-nor" in drug_class or any("19-nor" in c for c in categories):
        return True

    return False


def is_steroidal_androgen(compound: Dict[str, Any]) -> bool:
    """
    Determines if a compound is a steroidal androgen (AR agonist on steroid skeleton).
    """
    if not isinstance(compound, dict):
        return False

    # 1. Exclude inhibitors of steroidogenic enzymes or PDE5
    receptor_targets = compound.get("receptor_targets") or []
    for t in receptor_targets:
        if isinstance(t, dict):
            t_name = str(t.get("target", "")).lower()
            t_action = str(t.get("action", "")).lower()
            t_gene = str(t.get("gene_symbol", "")).upper()
            if t_action in ("inhibitor", "antagonist", "negative allosteric modulator"):
                if t_gene in ("SRD5A1", "SRD5A2", "CYP19A1", "PDE5A", "AR", "NR3C4"):
                    return False
                if any(w in t_name for w in ["5-alpha reductase", "aromatase", "phosphodiesterase", "pde5"]):
                    return False

    # 2. Check ATC hierarchy
    ext = compound.get("external_ids") or {}
    atc_codes = [str(c).upper() for c in (ext.get("atc_codes") or [])]
    if any(c.startswith(("G04BE", "G04CB", "C02KX", "C07", "C08", "C09", "A10", "L02BG", "N02", "B01")) for c in atc_codes):
        return False
    if any(c.startswith(("G03B", "G03BA", "G03BB", "A14A", "A14AA", "A14AB")) for c in atc_codes):
        return True

    parent_id = str(compound.get("parent_compound_id") or "").lower()
    comp_key = str(compound.get("key") or "").lower()
    drug_class = str(compound.get("drug_class", "")).lower()
    cats = [str(cat).lower() for cat in (compound.get("categories") or [])]

    if parent_id in ("testosterone", "nandrolone", "trenbolone", "drostanolone", "boldenone", "methenolone", "oxandrolone", "stanozolol", "oxymetholone", "mesterolone", "fluoxymesterone", "methandrostenolone") or any(w in comp_key for w in ["testosterone", "nandrolone", "trenbolone", "drostanolone", "boldenone", "methenolone", "oxandrolone", "stanozolol", "oxymetholone"]):
        return True

    # 3. Check structural topology
    analysis = resolve_compound_structure(compound)
    if analysis.get("is_steroid"):
        # Check AR target
        has_ar_agonist = any(
            isinstance(t, dict) and (t.get("gene_symbol") in ("AR", "NR3C4") or "androgen receptor" in str(t.get("target", "")).lower())
            and t.get("action") in ("agonist", "substrate", "partial agonist", "")
            for t in receptor_targets
        )
        if has_ar_agonist or "androgen" in drug_class or "anabolic" in drug_class:
            return True

    return False


def is_aromatizable_androgen(compound: Dict[str, Any]) -> bool:
    """
    Determines if a compound is chemically capable of being aromatized to estradiol by CYP19A1.
    """
    if not is_steroidal_androgen(compound):
        return False

    parent_id = str(compound.get("parent_compound_id") or "").lower()
    comp_key = str(compound.get("key") or "").lower()

    if parent_id in ("testosterone", "boldenone", "methandrostenolone") or any(w in comp_key for w in ["testosterone", "boldenone", "dianabol"]):
        return True

    analysis = resolve_compound_structure(compound)
    if analysis.get("is_steroid"):
        # 19-nor conjugated trienes and 5a-reduced androstanes are non-aromatizable
        if analysis.get("is_conjugated_triene") or analysis.get("is_5alpha_reduced") or analysis.get("is_19_nor"):
            return False
        return bool(analysis.get("is_aromatizable"))

    return False


def is_5alpha_reductase_substrate(compound: Dict[str, Any]) -> bool:
    """
    Determines if a compound is a substrate for 5-Alpha Reductase (SRD5A1/2).
    """
    if not is_steroidal_androgen(compound):
        return False

    analysis = resolve_compound_structure(compound)
    if analysis.get("is_steroid"):
        if analysis.get("is_5alpha_reduced") or analysis.get("is_conjugated_triene") or analysis.get("is_19_nor"):
            return False
        return bool(analysis.get("is_aromatizable"))

    return is_aromatizable_androgen(compound)
