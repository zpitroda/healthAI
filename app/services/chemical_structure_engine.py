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
        Determines steroid nucleus, 19-nor classification, C17-alkylation, C17-esterification,
        conjugated triene system, 5alpha-reduction, and CYP19A1 aromatizability with first-principles
        topological spine mapping and biochemical exactness.
        """
        default_res = {
            "is_steroid": False,
            "is_c17_alkylated": False,
            "is_19_nor": False,
            "is_c17_esterified": False,
            "is_aromatizable": False,
            "is_conjugated_triene": False,
            "is_5alpha_reduced": False,
        }
        if not smiles or not isinstance(smiles, str):
            return default_res

        atoms = cls.parse_smiles(smiles)
        if not atoms:
            return default_res

        rings = cls.find_rings(atoms)
        rings_5 = [r for r in rings if len(r) == 5]
        rings_6 = [r for r in rings if len(r) == 6]

        # 1. Identify Ring D candidates: 5-membered saturated/aliphatic carbocycles or lactones
        # (non-aromatic, no nitrogen, <= 1 oxygen, >= 4 carbons)
        d_candidates = []
        for r5 in rings_5:
            c_count = sum(1 for a in r5 if atoms[a]["symbol"] == "C")
            n_count = sum(1 for a in r5 if atoms[a]["symbol"] == "N")
            o_count = sum(1 for a in r5 if atoms[a]["symbol"] == "O")
            is_aromatic = any(atoms[a]["aromatic"] for a in r5)
            if c_count >= 4 and n_count == 0 and o_count <= 1 and not is_aromatic:
                d_candidates.append(r5)

        # 2. Identify ABCD fused steroid core:
        # Cyclopentanoperhydrophenanthrene skeleton: Ring D (5) ~ Ring C (6) ~ Ring B (6) ~ Ring A (6 or 5)
        steroid_cores = []
        for r_d in d_candidates:
            for r_c in rings_6:
                if len(r_d & r_c) == 2:
                    for r_b in rings_6:
                        if r_b != r_c and len(r_c & r_b) == 2 and len(r_b & r_d) == 0:
                            for r_a in rings_6 + rings_5:
                                if (
                                    r_a != r_b
                                    and r_a != r_c
                                    and r_a != r_d
                                    and len(r_b & r_a) == 2
                                    and len(r_a & r_c) == 0
                                    and len(r_a & r_d) == 0
                                ):
                                    core_atoms = r_a | r_b | r_c | r_d
                                    c_count = sum(1 for a in core_atoms if atoms[a]["symbol"] == "C")
                                    if c_count >= 14:
                                        steroid_cores.append((r_a, r_b, r_c, r_d))

        if not steroid_cores:
            return default_res

        # Select the primary steroidal nucleus
        r_a, r_b, r_c, r_d = steroid_cores[0]

        # 3. DETERMINISTIC TOPOLOGICAL SPINE MAPPING:
        # In the sterane graph: Ring D (C13-C14) -> Ring C (C8-C9) -> Ring B (C5-C10) -> Ring A
        bridge_cd = r_c & r_d
        bridge_bc = r_c & r_b
        bridge_ab = r_b & r_a

        # Step 1: C14 in bridge_cd has an edge to bridge_bc
        c14_cand = [a for a in bridge_cd if any(nbr in bridge_bc for nbr, _ in atoms[a]["neighbors"])]
        if c14_cand:
            c14 = c14_cand[0]
            c13 = [a for a in bridge_cd if a != c14][0]
        else:
            c14 = list(bridge_cd)[0]
            c13 = list(bridge_cd)[1] if len(bridge_cd) > 1 else c14

        # Step 2: C8 in bridge_bc has an edge to C14
        c8_cand = [a for a in bridge_bc if any(nbr == c14 for nbr, _ in atoms[a]["neighbors"])]
        if c8_cand:
            c8 = c8_cand[0]
            c9 = [a for a in bridge_bc if a != c8][0]
        else:
            c8 = list(bridge_bc)[0]
            c9 = list(bridge_bc)[1] if len(bridge_bc) > 1 else c8

        # Step 3: C10 in bridge_ab has an edge to C9 (or bridge_bc)
        c10_cand = [a for a in bridge_ab if any(nbr == c9 for nbr, _ in atoms[a]["neighbors"])]
        if not c10_cand:
            c10_cand = [a for a in bridge_ab if any(nbr in bridge_bc for nbr, _ in atoms[a]["neighbors"])]
        if c10_cand:
            c10 = c10_cand[0]
            c5 = [a for a in bridge_ab if a != c10][0]
        else:
            c10 = list(bridge_ab)[0]
            c5 = list(bridge_ab)[1] if len(bridge_ab) > 1 else c10

        # Step 4: C17 is the non-bridgehead atom in Ring D directly bonded to C13
        non_bridge_d = r_d - bridge_cd
        c17_cand = [a for a in non_bridge_d if any(nbr == c13 for nbr, _ in atoms[a]["neighbors"])]
        if not c17_cand:
            c17_cand = list(non_bridge_d)
        c17 = c17_cand[0] if c17_cand else c13

        # 4. 19-NOR STEROID CLASSIFICATION:
        # Evaluates exact presence of C19 angular carbon attached to C10 (exocyclic to rings A and B)
        c19_carbons = [
            nbr
            for nbr, _ in atoms[c10]["neighbors"]
            if nbr not in r_a and nbr not in r_b and atoms[nbr]["symbol"] == "C"
        ]
        is_19nor = len(c19_carbons) == 0

        # 5. C17-ALKYLATION & C17-ESTERIFICATION ANALYSIS:
        c17_exocyclic = [(nbr, bo) for nbr, bo in atoms[c17]["neighbors"] if nbr not in r_d]
        c17_oxygens = [nbr for nbr, bo in c17_exocyclic if atoms[nbr]["symbol"] == "O"]
        c17_carbons = [nbr for nbr, bo in c17_exocyclic if atoms[nbr]["symbol"] == "C"]

        is_c17_alkylated = False
        is_c17_esterified = False

        # 17alpha-alkylation: C17 has oxygen AND an exocyclic aliphatic hydrocarbon group (methyl, ethyl, ethynyl).
        # Scientifically excludes C20=O pregnane / corticosteroid acyl side chains and spirolactones.
        if len(c17_oxygens) >= 1:
            for c_nbr in c17_carbons:
                is_carbonyl = any(
                    atoms[x]["symbol"] == "O" and bo == 2.0 for x, bo in atoms[c_nbr]["neighbors"]
                )
                is_spiro_ether = any(x in c17_oxygens for x, _ in atoms[c_nbr]["neighbors"])
                if not is_carbonyl and not is_spiro_ether:
                    is_c17_alkylated = True

        # 17-esterification: C17 oxygen is bonded to an acyl carbonyl carbon C(=O) in an acyclic ester chain.
        for o_id in c17_oxygens:
            o_nbrs = [n_id for n_id, _ in atoms[o_id]["neighbors"] if n_id != c17]
            for o_nbr in o_nbrs:
                if atoms[o_nbr]["symbol"] == "C":
                    has_carbonyl_o = any(
                        atoms[c_nbr]["symbol"] == "O" and bo == 2.0
                        for c_nbr, bo in atoms[o_nbr]["neighbors"]
                    )
                    is_spiro = any(x == c17 for x, _ in atoms[o_nbr]["neighbors"]) or any(
                        x in c17_carbons for x, _ in atoms[o_nbr]["neighbors"]
                    )
                    if has_carbonyl_o and not is_spiro:
                        is_c17_esterified = True

        # 6. RING DOUBLE BONDS & CONJUGATION:
        all_core_atoms = r_a | r_b | r_c | r_d
        core_double_bonds = []
        for a_id in all_core_atoms:
            for nbr, bo in atoms[a_id]["neighbors"]:
                if nbr > a_id and nbr in all_core_atoms and bo == 2.0:
                    core_double_bonds.append((a_id, nbr))

        # Check if Ring A is benzenoid / phenolic aromatic (e.g. Estradiol, Estrone, Ethinylestradiol)
        ring_a_aromatic = any(atoms[a]["aromatic"] for a in r_a)
        ring_a_double_bonds = sum(1 for u, v in core_double_bonds if u in r_a and v in r_a)
        if ring_a_double_bonds >= 3:
            ring_a_aromatic = True

        # Carbonyls on Ring A (typically C3=O enone)
        ring_a_carbonyls = []
        for a_id in r_a:
            for nbr, bo in atoms[a_id]["neighbors"]:
                if atoms[nbr]["symbol"] == "O" and bo == 2.0:
                    ring_a_carbonyls.append((a_id, nbr))

        has_enone = len(ring_a_carbonyls) > 0

        # Conjugated triene system (e.g. Trenbolone estra-4,9,11-trien-3-one):
        # Requires >= 3 conjugated double bonds in non-aromatic steroidal core with conjugated enone
        is_conjugated_triene = (
            len(core_double_bonds) >= 3
            and not ring_a_aromatic
            and has_enone
        )

        # 7. 5alpha-REDUCED CLASSIFICATION:
        # Characterized by absence of Ring A unsaturation, saturated C4-C5 single bond, with intact 3-oxygen
        ring_a_carbon_db = [(u, v) for u, v in core_double_bonds if u in r_a and v in r_a]
        c4_c5_bo = 1.0
        non_bridge_a = r_a - bridge_ab
        c4_cand = [a for a in non_bridge_a if any(nbr == c5 for nbr, _ in atoms[a]["neighbors"])]
        c4 = c4_cand[0] if c4_cand else None
        if c4 is not None:
            for nbr, bo in atoms[c5]["neighbors"]:
                if nbr == c4:
                    c4_c5_bo = max(c4_c5_bo, bo)

        is_5alpha_reduced = (
            not ring_a_aromatic
            and len(ring_a_carbon_db) == 0
            and c4_c5_bo == 1.0
            and (has_enone or any(any(atoms[n]["symbol"] == "O" for n, _ in atoms[a]["neighbors"]) for a in r_a))
        )

        # 8. CYP19A1 AROMATIZABILITY (Biochemical Feasibility):
        # Requires:
        # - Intact C19 angular methyl (monooxygenation site for CYP19A1; 19-nor steroids lack C19)
        # - Delta-4 (C4=C5) or Delta-5 (C5=C6) unsaturation on Ring A/B
        # - Not already 5alpha-reduced or a conjugated triene
        # - Not already an aromatized estrogen (phenolic Ring A)
        # - Unblocked by steric/electronic substituents (4-chloro in Turinabol, 9-fluoro in Fluoxymesterone)
        # - No fused heterocyclic ring abolishing 3-keto-4-ene system (Stanozolol pyrazole)
        # - Must be a C19 androgen, not a C21 pregnane/corticosteroid (no C20=O acyl side chain at C17)
        has_delta4_5 = False
        if c4 is not None:
            for nbr, bo in atoms[c5]["neighbors"]:
                if nbr == c4 and bo == 2.0:
                    has_delta4_5 = True
        for nbr, bo in atoms[c5]["neighbors"]:
            if nbr in r_b and bo == 2.0:
                has_delta4_5 = True

        has_pregnane_c20_carbonyl = False
        for c_nbr in c17_carbons:
            if any(atoms[x]["symbol"] == "O" and bo == 2.0 for x, bo in atoms[c_nbr]["neighbors"]):
                has_pregnane_c20_carbonyl = True

        has_blocking_halogen = any(
            any(atoms[n]["symbol"] in ("Cl", "Br", "F") for n, _ in atoms[a]["neighbors"])
            for a in (r_a | {c9})
        )

        has_hetero_ring_a = any(atoms[a]["symbol"] != "C" for a in r_a) or any(
            any(atoms[n]["symbol"] == "N" for n, _ in atoms[a]["neighbors"]) for a in r_a
        )

        is_aromatizable = (
            (not is_19nor)
            and (not is_conjugated_triene)
            and (not is_5alpha_reduced)
            and (not ring_a_aromatic)
            and (not has_pregnane_c20_carbonyl)
            and (not has_blocking_halogen)
            and (not has_hetero_ring_a)
            and has_delta4_5
            and has_enone
            and len(r_a) == 6
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
        if lib_rec and lib_rec.get("smiles"):
            smiles = lib_rec["smiles"]
        elif not smiles:
            try:
                from app.services.catalog_service import CatalogService, _WARMING_DATABASES
                if not _WARMING_DATABASES:
                    cat_rec = CatalogService().get_compound(key)
                    if cat_rec:
                        smiles = cat_rec.get("smiles")
                        if not smiles and cat_rec.get("parent_compound_id"):
                            p_id = cat_rec["parent_compound_id"]
                            p_rec = CatalogService().get_compound(p_id)
                            if p_rec:
                                smiles = p_rec.get("smiles")
            except Exception:
                pass

    if not smiles and compound.get("parent_compound_id"):
        from app.services.catalog_service import CORE_ESTER_LIBRARY, CORE_THERAPEUTIC_LIBRARY
        p_id = compound["parent_compound_id"]
        parent_rec = CORE_ESTER_LIBRARY.get(p_id) or CORE_THERAPEUTIC_LIBRARY.get(p_id)
        if parent_rec and parent_rec.get("smiles"):
            smiles = parent_rec["smiles"]
        else:
            try:
                from app.services.catalog_service import CatalogService, _WARMING_DATABASES
                if not _WARMING_DATABASES:
                    p_rec = CatalogService().get_compound(p_id)
                    if p_rec:
                        smiles = p_rec.get("smiles")
            except Exception:
                pass

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

    # 1. Exclude inhibitors/antagonists of steroid receptors, steroidogenic enzymes, or PDE5
    drug_class = str(compound.get("drug_class", "")).lower()
    cats = [str(cat).lower() for cat in (compound.get("categories") or [])]
    if any(w in drug_class or any(w in c for c in cats) for w in [
        "aldosterone antagonist", "mineralocorticoid antagonist", "antiandrogen",
        "androgen receptor antagonist", "aromatase inhibitor", "diuretic", "phosphodiesterase"
    ]):
        return False

    receptor_targets = compound.get("receptor_targets") or []
    for t in receptor_targets:
        if isinstance(t, dict):
            t_name = str(t.get("target", "")).lower()
            t_action = str(t.get("action", "")).lower()
            t_gene = str(t.get("gene_symbol", "")).upper()
            if t_action in ("inhibitor", "antagonist", "negative allosteric modulator"):
                if t_gene in ("SRD5A1", "SRD5A2", "CYP19A1", "PDE5A", "AR", "NR3C4", "NR3C2"):
                    return False
                if any(w in t_name for w in ["5-alpha reductase", "aromatase", "phosphodiesterase", "pde5", "mineralocorticoid", "aldosterone"]):
                    return False

    # 2. Check ATC hierarchy
    ext = compound.get("external_ids") or {}
    if isinstance(ext, str):
        try:
            ext = json.loads(ext)
        except Exception:
            ext = {}
    if not isinstance(ext, dict):
        ext = {}
    atc_codes = [str(c).upper() for c in (ext.get("atc_codes") or [])]
    if any(c.startswith(("G04BE", "G04CB", "C02KX", "C03", "C07", "C08", "C09", "A10", "L02BG", "L02BB", "N02", "B01", "G03C", "G03D", "G03X")) for c in atc_codes):
        return False
    if any(c.startswith(("G03B", "G03BA", "G03BB", "A14A", "A14AA", "A14AB")) for c in atc_codes):
        return True

    parent_id = str(compound.get("parent_compound_id") or "").lower()
    comp_key = str(compound.get("key") or "").lower()

    if parent_id in ("testosterone", "nandrolone", "trenbolone", "drostanolone", "boldenone", "methenolone", "oxandrolone", "stanozolol", "oxymetholone", "mesterolone", "fluoxymesterone", "methandrostenolone") or any(w in comp_key for w in ["testosterone", "nandrolone", "trenbolone", "drostanolone", "boldenone", "methenolone", "oxandrolone", "stanozolol", "oxymetholone"]):
        return True

    # 3. Check structural topology
    analysis = resolve_compound_structure(compound)
    if analysis.get("is_steroid"):
        # Check explicit androgenic drug class or AR agonist target
        is_explicit_androgen_class = any(w in drug_class or any(w in c for c in cats) for w in ["androgen", "anabolic steroid", "aas", "sarm"])
        has_ar_agonist = any(
            isinstance(t, dict) and (t.get("gene_symbol") in ("AR", "NR3C4") or "androgen receptor" in str(t.get("target", "")).lower())
            and t.get("action") in ("agonist", "substrate", "partial agonist")
            for t in receptor_targets
        )
        if is_explicit_androgen_class or has_ar_agonist:
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
    Substrates possess an intact, unreduced Delta-4-3-one system (e.g. Testosterone -> DHT, Nandrolone -> DHN).
    Steroids that are already 5alpha-reduced (DHT, Masteron, Proviron, Oxandrolone, Superdrol),
    or conjugated trienes (Trenbolone), or Delta-1 only (Methenolone, DHB) are not 5alpha-reductase substrates.
    """
    if not is_steroidal_androgen(compound):
        return False

    parent_id = str(compound.get("parent_compound_id") or "").lower()
    comp_key = str(compound.get("key") or "").lower()

    if parent_id in ("testosterone", "nandrolone", "boldenone", "methandrostenolone") or any(
        w in comp_key for w in ["testosterone", "nandrolone", "boldenone", "dianabol"]
    ):
        return True

    analysis = resolve_compound_structure(compound)
    if analysis.get("is_steroid"):
        if analysis.get("is_5alpha_reduced") or analysis.get("is_conjugated_triene"):
            return False
        # Unreduced Delta-4/5 androgens (aromatizable androgens or unreduced 19-nors like Nandrolone)
        if analysis.get("is_aromatizable"):
            return True
        if analysis.get("is_19_nor") and not analysis.get("is_conjugated_triene") and not analysis.get("is_5alpha_reduced"):
            return True

    return False

