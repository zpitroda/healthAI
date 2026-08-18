from __future__ import annotations

from app.knowledge_graph.graph import BiologicalGraph
from app.knowledge_graph.models import (
    BiomarkerNode,
    CompoundNode,
    EdgeData,
    EdgeType,
    EnzymeNode,
    PhenotypeNode,
    ReactionNode,
    ReceptorNode,
)


def build_testosterone_alopecia_graph() -> BiologicalGraph:
    graph = BiologicalGraph()

    testosterone_enanthate = CompoundNode(
        node_id="testosterone_enanthate",
        label="Testosterone Enanthate",
        smiles="CC(=O)O[C@H](CC)C(=O)O",
        logP=2.4,
        molecular_weight=400.6,
        base_half_life=4.5,
    )
    esterase = EnzymeNode(node_id="esterase", label="Esterase")
    cleavage_reaction = ReactionNode(node_id="cleavage_reaction", label="Cleavage Reaction")
    testosterone = CompoundNode(
        node_id="testosterone",
        label="Testosterone",
        smiles="CC12CCC(=O)C=C1CCC1C2CCC2(C)C(O)CCC12",
        logP=3.3,
        molecular_weight=288.4,
        base_half_life=10.0,
    )
    reduction_reaction = ReactionNode(node_id="reduction_reaction", label="Reduction Reaction")
    five_alpha_reductase = EnzymeNode(node_id="5_alpha_reductase", label="5-alpha Reductase")
    dht = CompoundNode(
        node_id="dht",
        label="DHT",
        smiles="CC12CCC3C(C1CCC2O)CCC4CC(CCC34C)O",
        logP=4.1,
        molecular_weight=290.4,
        base_half_life=8.0,
    )
    androgen_receptor = ReceptorNode(node_id="androgen_receptor", label="Androgen Receptor")
    alopecia = PhenotypeNode(node_id="alopecia", label="Alopecia")
    finasteride = CompoundNode(
        node_id="finasteride",
        label="Finasteride",
        smiles="CC(C)(C)NC(=O)C1CC2CCC1C2CC(=O)N",
        logP=3.8,
        molecular_weight=372.5,
        base_half_life=6.0,
    )
    aromatase = EnzymeNode(node_id="aromatase", label="Aromatase (CYP19A1)")
    aromatization_reaction = ReactionNode(node_id="aromatization_reaction", label="Aromatization Reaction")
    estradiol = CompoundNode(
        node_id="estradiol",
        label="17-Beta Estradiol",
        smiles="CC12CCC3C(C1CCC2O)CCC4=C3C=CC(=C4)O",
        logP=4.0,
        molecular_weight=272.4,
        base_half_life=13.0,
    )
    estrogen_receptor = ReceptorNode(node_id="estrogen_receptor", label="Estrogen Receptor (ER-Alpha/Beta)")
    gynecomastia = PhenotypeNode(node_id="gynecomastia", label="Gynecomastia / Fluid Retention")
    anastrozole = CompoundNode(
        node_id="anastrozole",
        label="Anastrozole",
        smiles="CC(C)(C#N)C1=CC(=CC(=C1)CN2C=NC=N2)C(C)(C)C#N",
        logP=2.2,
        molecular_weight=293.4,
        base_half_life=48.0,
    )

    nodes = [
        testosterone_enanthate,
        esterase,
        cleavage_reaction,
        testosterone,
        reduction_reaction,
        five_alpha_reductase,
        dht,
        androgen_receptor,
        alopecia,
        finasteride,
        aromatase,
        aromatization_reaction,
        estradiol,
        estrogen_receptor,
        gynecomastia,
        anastrozole,
    ]
    for node in nodes:
        graph.add_node(node)

    graph.add_edge(
        "testosterone_enanthate",
        "cleavage_reaction",
        EdgeType.REACTANT_IN,
        EdgeData(vector_magnitude=1.0),
    )
    graph.add_edge(
        "esterase",
        "cleavage_reaction",
        EdgeType.CATALYZES,
        EdgeData(vector_magnitude=1.0),
    )
    graph.add_edge(
        "cleavage_reaction",
        "testosterone",
        EdgeType.YIELDS,
        EdgeData(vector_magnitude=1.0),
    )
    graph.add_edge(
        "testosterone",
        "reduction_reaction",
        EdgeType.REACTANT_IN,
        EdgeData(vector_magnitude=1.0),
    )
    graph.add_edge(
        "5_alpha_reductase",
        "reduction_reaction",
        EdgeType.CATALYZES,
        EdgeData(vector_magnitude=1.0),
    )
    graph.add_edge(
        "reduction_reaction",
        "dht",
        EdgeType.YIELDS,
        EdgeData(vector_magnitude=1.0),
    )
    graph.add_edge(
        "dht",
        "androgen_receptor",
        EdgeType.AGONIZES,
        EdgeData(affinity_ki=0.2, vector_magnitude=1.0),
    )
    graph.add_edge(
        "androgen_receptor",
        "alopecia",
        EdgeType.DRIVES_PHENOTYPE,
        EdgeData(vector_magnitude=0.9),
    )
    graph.add_edge(
        "finasteride",
        "5_alpha_reductase",
        EdgeType.INHIBITS_ENZYME,
        EdgeData(inhibition_ic50=0.005, inhibition_type="competitive", vector_magnitude=-1.0),
    )

    # Estrogenic Branch
    graph.add_edge(
        "testosterone",
        "aromatization_reaction",
        EdgeType.REACTANT_IN,
        EdgeData(vector_magnitude=1.0),
    )
    graph.add_edge(
        "aromatase",
        "aromatization_reaction",
        EdgeType.CATALYZES,
        EdgeData(vector_magnitude=1.0),
    )
    graph.add_edge(
        "aromatization_reaction",
        "estradiol",
        EdgeType.YIELDS,
        EdgeData(vector_magnitude=1.0),
    )
    graph.add_edge(
        "estradiol",
        "estrogen_receptor",
        EdgeType.AGONIZES,
        EdgeData(affinity_ki=0.1, vector_magnitude=1.0),
    )
    graph.add_edge(
        "estrogen_receptor",
        "gynecomastia",
        EdgeType.DRIVES_PHENOTYPE,
        EdgeData(vector_magnitude=0.85),
    )
    graph.add_edge(
        "anastrozole",
        "aromatase",
        EdgeType.INHIBITS_ENZYME,
        EdgeData(inhibition_ic50=0.0002, inhibition_type="competitive", vector_magnitude=-1.0),
    )

    return graph
