from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx
from pydantic import BaseModel, ConfigDict

from app.knowledge_graph.models import BaseNode, EdgeData, EdgeType


class BiologicalGraph:
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_node(self, node: BaseNode | Dict[str, Any]) -> None:
        if isinstance(node, BaseNode):
            self.graph.add_node(node.node_id, **node.model_dump())
        elif isinstance(node, dict):
            node_id = str(node.get("node_id") or node.get("id") or "unknown_node")
            self.graph.add_node(node_id, **node)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType | str,
        edge_data: EdgeData | Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        type_str = edge_type.value if isinstance(edge_type, EdgeType) else str(edge_type)
        payload = {"edge_type": type_str}

        if edge_data is not None:
            if isinstance(edge_data, EdgeData):
                payload.update(edge_data.model_dump(exclude_none=True))
            elif isinstance(edge_data, dict):
                payload.update(edge_data)

        payload.update(kwargs)
        if "vector_magnitude" not in payload:
            payload["vector_magnitude"] = 1.0

        self.graph.add_edge(source_id, target_id, **payload)

    def get_node(self, node_id: str) -> Dict[str, Any]:
        return self.graph.nodes[node_id]

    def neighbors(self, node_id: str) -> List[str]:
        return list(self.graph.successors(node_id))

    def predecessors(self, node_id: str) -> List[str]:
        return list(self.graph.predecessors(node_id))

    def path_exists(self, source_id: str, target_id: str) -> bool:
        return nx.has_path(self.graph, source_id, target_id)

    def subgraph_from_node(self, node_id: str, max_depth: int = 2) -> "BiologicalGraph":
        if node_id not in self.graph:
            raise KeyError(f"Node '{node_id}' does not exist in the graph.")

        visited = {node_id}
        frontier = [node_id]
        depth_map = {node_id: 0}

        for _ in range(max_depth):
            next_frontier = []
            for current in frontier:
                for neighbor in self.graph.successors(current):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        depth_map[neighbor] = depth_map[current] + 1
                        next_frontier.append(neighbor)
                for predecessor in self.graph.predecessors(current):
                    if predecessor not in visited:
                        visited.add(predecessor)
                        depth_map[predecessor] = depth_map[current] + 1
                        next_frontier.append(predecessor)
            frontier = next_frontier
            if not frontier:
                break

        subgraph = BiologicalGraph()
        subgraph.graph.add_nodes_from((node, self.graph.nodes[node].copy()) for node in visited)
        subgraph.graph.add_edges_from(
            (source, target, self.graph.edges[source, target].copy())
            for source, target in self.graph.edges
            if source in visited and target in visited
        )

        return subgraph

    def propagate_cascade(
        self,
        start_node_ids: List[str] | str,
        max_depth: int = 5,
        affinity_decay: bool = True,
    ) -> Dict[str, Any]:
        """
        Dynamically traverses directed cascade paths starting from input compounds/ligands,
        multiplying signed directional vectors along paths (Sign(path) = ∏ sign(edge)),
        and computing predicted biomarker shifts, pathway activations, and phenotype probabilities.
        """
        starts = [start_node_ids] if isinstance(start_node_ids, str) else list(start_node_ids)
        valid_starts = [n for n in starts if n in self.graph]

        if not valid_starts:
            return {
                "activated_pathways": [],
                "biomarker_shifts": [],
                "phenotypes": [],
                "cascade_traces": [],
                "summary": "No active knowledge graph nodes found for the requested entities.",
            }

        # Track cumulative impacts
        biomarker_impacts: Dict[str, float] = {}
        pathway_impacts: Dict[str, float] = {}
        phenotype_impacts: Dict[str, float] = {}
        traces: List[Dict[str, Any]] = []

        for start in valid_starts:
            # Depth-limited DFS for all reachable paths
            stack: List[Tuple[str, List[str], float, List[Dict[str, Any]]]] = [(start, [start], 1.0, [])]

            while stack:
                curr, path, cum_mag, edge_trail = stack.pop()
                curr_data = self.graph.nodes[curr]
                curr_type = curr_data.get("node_type", "")

                # Record impacts based on node type
                if curr_type == "signaling_pathway":
                    pathway_impacts[curr] = max(-1.0, min(1.0, pathway_impacts.get(curr, 0.0) + cum_mag))
                elif curr_type == "biomarker":
                    biomarker_impacts[curr] = max(-1.0, min(1.0, biomarker_impacts.get(curr, 0.0) + cum_mag))
                elif curr_type == "phenotype":
                    phenotype_impacts[curr] = max(-1.0, min(1.0, phenotype_impacts.get(curr, 0.0) + cum_mag))

                    # Completed cascade trace to phenotype
                    traces.append({
                        "origin": start,
                        "origin_label": self.graph.nodes[start].get("label", start),
                        "endpoint": curr,
                        "endpoint_label": curr_data.get("label", curr),
                        "endpoint_type": curr_type,
                        "net_vector": round(cum_mag, 3),
                        "path": path,
                        "path_labels": [self.graph.nodes[p].get("label", p) for p in path],
                        "edge_types": [e.get("edge_type") for e in edge_trail],
                    })

                if len(path) > max_depth:
                    continue

                for succ in self.graph.successors(curr):
                    if succ in path:  # Prevent cycles
                        continue

                    edge_attrs = self.graph.edges[curr, succ]
                    edge_mag = float(edge_attrs.get("vector_magnitude", 1.0))
                    edge_type = str(edge_attrs.get("edge_type", ""))

                    # Directional sign modulation based on edge semantics
                    sign_mult = 1.0
                    if any(t in edge_type for t in ["INHIBIT", "ANTAGONIZ", "BLOCK", "REPRESS", "MITIGAT"]):
                        sign_mult = -1.0
                    elif any(t in edge_type for t in ["AGONIZ", "ACTIVAT", "INDUCE", "DRIVE", "CATALYZ", "YIELD"]):
                        sign_mult = 1.0

                    next_mag = cum_mag * (edge_mag if sign_mult > 0 else -abs(edge_mag))

                    # Attenuate by affinity if present
                    if affinity_decay and "affinity_ki" in edge_attrs:
                        ki = float(edge_attrs["affinity_ki"])
                        # Micro-molar scale decay
                        attenuation = max(0.2, min(1.0, 1.0 / (1.0 + (ki / 10.0))))
                        next_mag *= attenuation

                    new_trail = list(edge_trail) + [edge_attrs]
                    stack.append((succ, list(path) + [succ], next_mag, new_trail))

        # Format results
        formatted_biomarkers = []
        for bio_id, net_mag in sorted(biomarker_impacts.items(), key=lambda x: abs(x[1]), reverse=True):
            bio_data = self.graph.nodes[bio_id]
            direction = "INCREASE" if net_mag > 0.05 else ("DECREASE" if net_mag < -0.05 else "NEUTRAL")
            arrow = "↑" if net_mag > 0.05 else ("↓" if net_mag < -0.05 else "→")
            label = bio_data.get("label", bio_id)
            formatted_biomarkers.append({
                "biomarker_id": bio_id,
                "label": label,
                "name": label,
                "net_shift": round(net_mag, 3),
                "direction": direction,
                "arrow": arrow,
                "unit": bio_data.get("unit", "units"),
                "biomarker_panel": bio_data.get("biomarker_panel", "General"),
                "safe_range": f"{bio_data.get('safe_lower_bound', 0)} - {bio_data.get('safe_upper_bound', 100)}",
            })

        formatted_pathways = []
        for path_id, net_mag in sorted(pathway_impacts.items(), key=lambda x: abs(x[1]), reverse=True):
            pdata = self.graph.nodes[path_id]
            status = "UPREGULATED" if net_mag > 0.05 else ("DOWNREGULATED" if net_mag < -0.05 else "MODULATED")
            label = pdata.get("label", path_id)
            formatted_pathways.append({
                "pathway_id": path_id,
                "label": label,
                "name": label,
                "net_activation": round(net_mag, 3),
                "status": status,
                "database": pdata.get("pathway_database", "Reactome"),
            })

        formatted_phenotypes = []
        for pheno_id, net_mag in sorted(phenotype_impacts.items(), key=lambda x: abs(x[1]), reverse=True):
            pdata = self.graph.nodes[pheno_id]
            outcome_type = pdata.get("phenotype_category", "clinical_outcome")
            label = pdata.get("label", pheno_id)
            formatted_phenotypes.append({
                "phenotype_id": pheno_id,
                "label": label,
                "name": label,
                "net_score": round(net_mag, 3),
                "category": outcome_type,
                "severity": pdata.get("severity", "moderate"),
                "description": pdata.get("description", ""),
            })

        summary = (
            f"Cascade simulation across {len(valid_starts)} origin entity(ies) mapped "
            f"{len(formatted_pathways)} intracellular pathway(s), {len(formatted_biomarkers)} clinical biomarker shift(s), "
            f"and {len(formatted_phenotypes)} downstream phenotype outcome(s)."
        )

        return {
            "activated_pathways": formatted_pathways,
            "biomarker_shifts": formatted_biomarkers,
            "phenotypes": formatted_phenotypes,
            "cascade_traces": traces[:25],
            "summary": summary,
        }

    def summarize(self) -> Dict[str, Any]:
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_types": sorted({data.get("node_type", "unknown") for _, data in self.graph.nodes(data=True)}),
        }
