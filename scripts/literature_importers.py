#!/usr/bin/env python3
"""
Literature Importers
--------------------
Batch import script that pulls compound relationship data from three curated 
biomedical databases (STITCH, CTD, DrugBank) and writes them into the HealthAI Neo4j graph database.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.knowledge_graph.graph_db import get_graph_database
from app.knowledge_graph.models import EdgeType

logger = logging.getLogger("healthai.literature_importers")


class STITCHImporter:
    """
    STITCH REST API Importer.
    Queries chemical-protein interactions per compound.
    """
    def __init__(self, gdb: Any):
        self.gdb = gdb
        self.base_url = "http://stitch.embl.de/api/json/interactionsList"

    def run(self, compounds: List[str]) -> int:
        """Run STITCH importer for a list of compounds."""
        edges_added = 0
        logger.info(f"Starting STITCH import for {len(compounds)} compounds.")
        
        for compound in compounds:
            params = {
                "identifiers": compound,
                "species": "9606",  # Human
                "limit": "50"
            }
            try:
                # Rate limit
                time.sleep(1.0)
                logger.info(f"[STITCH] Fetching data for {compound}...")
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(self.base_url, params=params)
                    if response.status_code != 200:
                        logger.warning(f"[STITCH] Failed to fetch {compound}, status {response.status_code}")
                        continue
                        
                    data = response.json()
                    
                    compound_id = compound.lower().replace(" ", "_").replace("-", "_")
                    
                    for item in data:
                        score = float(item.get("score", 0))
                        escore = float(item.get("escore", 0))
                        dscore = float(item.get("dscore", 0))
                        tscore = float(item.get("tscore", 0))
                        target_name = item.get("preferredName_B", "Unknown")
                        target_id = item.get("stringId_B", target_name)
                        
                        confidence = score / 1000.0
                        
                        evidence_parts = []
                        if escore > 0: evidence_parts.append("experimental")
                        if dscore > 0: evidence_parts.append("database")
                        if tscore > 0: evidence_parts.append("textmining")
                        evidence_level = ",".join(evidence_parts) if evidence_parts else "inferred"
                        
                        description = "STITCH interaction"
                        
                        # Create/merge target node
                        self.gdb.execute_cypher(
                            'MERGE (e:EntityNode:TargetNode {id: $id}) SET e.label = $label, e.node_type = $nt',
                            {'id': target_id, 'label': target_name, 'nt': 'target'}
                        )
                        
                        # Create relationship
                        self.gdb.execute_cypher(
                            'MATCH (a:EntityNode {id: $src}), (b:EntityNode {id: $tgt}) '
                            'MERGE (a)-[r:CURATED_ASSOCIATION]->(b) '
                            'SET r.confidence = $conf, r.evidence_level = $ev, r.source_db = $source_db, r.description = $desc',
                            {
                                'src': compound_id, 
                                'tgt': target_id, 
                                'conf': confidence, 
                                'ev': evidence_level, 
                                'source_db': 'STITCH', 
                                'desc': description
                            }
                        )
                        edges_added += 1
                        
                        # Fallback mock update
                        if getattr(self.gdb, "driver", None) is None:
                            self.gdb._mock_nodes[target_id] = {'id': target_id, 'label': target_name, 'node_type': 'target'}
                            self.gdb._mock_edges.append({
                                'source': compound_id,
                                'target': target_id,
                                'type': 'CURATED_ASSOCIATION',
                                'confidence': confidence,
                                'evidence_level': evidence_level,
                                'source_db': 'STITCH',
                                'description': description
                            })
                            
            except Exception as e:
                logger.warning(f"[STITCH] Error for {compound}: {e}")
                
        return edges_added


class CTDImporter:
    """
    CTD REST API Importer.
    Queries curated chemical-gene interactions.
    """
    def __init__(self, gdb: Any):
        self.gdb = gdb
        self.base_url = "https://ctdbase.org/tools/batchQuery.go"

    def run(self, compounds: List[str]) -> int:
        """Run CTD importer for a list of compounds."""
        edges_added = 0
        logger.info(f"Starting CTD import for {len(compounds)} compounds.")
        
        for compound in compounds:
            params = {
                "inputType": "chem",
                "inputTerms": compound,
                "report": "genes_curated",
                "format": "tsv"
            }
            try:
                # Rate limit
                time.sleep(2.0)
                logger.info(f"[CTD] Fetching data for {compound}...")
                with httpx.Client(timeout=15.0) as client:
                    response = client.post(self.base_url, data=params)
                    if response.status_code != 200:
                        logger.warning(f"[CTD] Failed to fetch {compound}, status {response.status_code}")
                        continue
                        
                    lines = response.text.split("\n")
                    compound_id = compound.lower().replace(" ", "_").replace("-", "_")
                    
                    for line in lines:
                        if not line.strip() or line.startswith("#"):
                            continue
                            
                        parts = line.split("\t")
                        if len(parts) >= 9:
                            gene_symbol = parts[3]
                            interaction = parts[8]
                            pmids = parts[10] if len(parts) >= 11 else ""
                            pmid_list = [p.strip() for p in pmids.split("|") if p.strip()]
                            
                            target_id = gene_symbol
                            
                            # Create/merge target node
                            self.gdb.execute_cypher(
                                'MERGE (e:EntityNode:TargetNode {id: $id}) SET e.label = $label, e.node_type = $nt',
                                {'id': target_id, 'label': gene_symbol, 'nt': 'target'}
                            )
                            
                            # Create relationship
                            self.gdb.execute_cypher(
                                'MATCH (a:EntityNode {id: $src}), (b:EntityNode {id: $tgt}) '
                                'MERGE (a)-[r:CURATED_ASSOCIATION]->(b) '
                                'SET r.confidence = $conf, r.evidence_level = $ev, r.pmids = $pmids, r.source_db = $source_db, r.description = $desc',
                                {
                                    'src': compound_id, 
                                    'tgt': target_id, 
                                    'conf': 0.8, 
                                    'ev': 'curated_database', 
                                    'pmids': pmid_list,
                                    'source_db': 'CTD', 
                                    'desc': interaction
                                }
                            )
                            edges_added += 1
                            
                            # Fallback mock update
                            if getattr(self.gdb, "driver", None) is None:
                                self.gdb._mock_nodes[target_id] = {'id': target_id, 'label': gene_symbol, 'node_type': 'target'}
                                self.gdb._mock_edges.append({
                                    'source': compound_id,
                                    'target': target_id,
                                    'type': 'CURATED_ASSOCIATION',
                                    'confidence': 0.8,
                                    'evidence_level': 'curated_database',
                                    'pmids': pmid_list,
                                    'source_db': 'CTD',
                                    'description': interaction
                                })
                                
            except Exception as e:
                logger.warning(f"[CTD] Error for {compound}: {e}")
                
        return edges_added


class DrugBankImporter:
    """
    DrugBank Importer.
    Downloads dataset from Kaggle, parses XML/CSV, extracts compound-compound interactions.
    """
    def __init__(self, gdb: Any):
        self.gdb = gdb
        self.kaggle_url = "https://www.kaggle.com/api/v1/datasets/download/devildev89/drug-bank-5110"

    def _normalize_name(self, name: str) -> str:
        """Normalize compound name to match node IDs."""
        return name.lower().replace(" ", "_").replace("-", "_")

    def run(self, compounds: List[str]) -> int:
        """Run DrugBank importer by downloading from Kaggle and parsing."""
        edges_added = 0
        logger.info(f"Starting DrugBank import for {len(compounds)} compounds.")
        
        compound_set = {self._normalize_name(c) for c in compounds}
        
        temp_dir = tempfile.mkdtemp(prefix="drugbank_")
        zip_path = os.path.join(temp_dir, "drugbank.zip")
        
        try:
            logger.info("Downloading DrugBank dataset from Kaggle...")
            with httpx.Client(follow_redirects=True, timeout=120.0) as client:
                response = client.get(self.kaggle_url)
                if response.status_code != 200:
                    logger.warning(f"[DrugBank] Failed to download dataset, status {response.status_code}. Kaggle auth may be required.")
                    return 0
                    
                with open(zip_path, "wb") as f:
                    f.write(response.content)
                    
            logger.info("Extracting dataset...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                
            files = os.listdir(temp_dir)
            for file in files:
                if file.endswith(".xml"):
                    logger.info(f"Parsing XML file: {file}")
                    xml_path = os.path.join(temp_dir, file)
                    edges_added += self._parse_xml(xml_path, compound_set)
                elif file.endswith(".csv"):
                    logger.info(f"Parsing CSV file: {file}")
                    # Could add CSV parser if needed
                    pass
                    
        except Exception as e:
            logger.warning(f"[DrugBank] Error: {e}")
        finally:
            logger.info("Cleaning up temp files...")
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        return edges_added

    def _parse_xml(self, xml_path: str, compound_set: set) -> int:
        """Iteratively parse large XML to find drug interactions."""
        edges_added = 0
        try:
            for event, elem in ET.iterparse(xml_path, events=("end",)):
                tag = elem.tag.split('}', 1)[1] if '}' in elem.tag else elem.tag
                
                if tag == 'drug':
                    name_elem = elem.find("{http://www.drugbank.ca}name")
                    if name_elem is None:
                        name_elem = elem.find("name")
                        
                    if name_elem is not None and name_elem.text:
                        drug_name = self._normalize_name(name_elem.text)
                        
                        if drug_name in compound_set:
                            interactions_elem = elem.find("{http://www.drugbank.ca}drug-interactions")
                            if interactions_elem is None:
                                interactions_elem = elem.find("drug-interactions")
                                
                            if interactions_elem is not None:
                                for interaction in interactions_elem:
                                    int_name_elem = interaction.find("{http://www.drugbank.ca}name")
                                    if int_name_elem is None:
                                        int_name_elem = interaction.find("name")
                                        
                                    desc_elem = interaction.find("{http://www.drugbank.ca}description")
                                    if desc_elem is None:
                                        desc_elem = interaction.find("description")
                                        
                                    if int_name_elem is not None and int_name_elem.text and desc_elem is not None and desc_elem.text:
                                        target_drug = self._normalize_name(int_name_elem.text)
                                        
                                        if target_drug in compound_set:
                                            desc = desc_elem.text
                                            desc_lower = desc.lower()
                                            
                                            edge_type = EdgeType.CONTRAINDICATED_WITH.value if "contraindicate" in desc_lower or "adverse" in desc_lower or "toxicity" in desc_lower else EdgeType.SYNERGIZES_WITH.value
                                            
                                            self.gdb.execute_cypher(
                                                f'MATCH (a:EntityNode {{id: $src}}), (b:EntityNode {{id: $tgt}}) '
                                                f'MERGE (a)-[r:{edge_type}]->(b) '
                                                f'SET r.confidence = $conf, r.evidence_level = $ev, r.source_db = $source_db, r.description = $desc',
                                                {
                                                    'src': drug_name, 
                                                    'tgt': target_drug, 
                                                    'conf': 0.9, 
                                                    'ev': 'curated_database', 
                                                    'source_db': 'DrugBank', 
                                                    'desc': desc
                                                }
                                            )
                                            edges_added += 1
                                            
                                            if getattr(self.gdb, "driver", None) is None:
                                                self.gdb._mock_edges.append({
                                                    'source': drug_name,
                                                    'target': target_drug,
                                                    'type': edge_type,
                                                    'confidence': 0.9,
                                                    'evidence_level': 'curated_database',
                                                    'source_db': 'DrugBank',
                                                    'description': desc
                                                })
                    elem.clear()
        except Exception as e:
            logger.warning(f"[DrugBank] XML parsing error: {e}")
            
        return edges_added


def run_all_imports(compounds: List[str], graph_db: Any, run_stitch: bool = True, run_ctd: bool = True, run_drugbank: bool = True) -> Dict[str, int]:
    """Run specified importers and return a summary of edges added."""
    counts = {"stitch_edges": 0, "ctd_edges": 0, "drugbank_edges": 0}
    
    if run_stitch:
        importer = STITCHImporter(graph_db)
        counts["stitch_edges"] = importer.run(compounds)
        
    if run_ctd:
        importer = CTDImporter(graph_db)
        counts["ctd_edges"] = importer.run(compounds)
        
    if run_drugbank:
        importer = DrugBankImporter(graph_db)
        counts["drugbank_edges"] = importer.run(compounds)
        
    return counts


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    parser = argparse.ArgumentParser(description="Batch import script for STITCH, CTD, and DrugBank.")
    parser.add_argument("--stitch", action="store_true", help="Run STITCH importer")
    parser.add_argument("--ctd", action="store_true", help="Run CTD importer")
    parser.add_argument("--drugbank", action="store_true", help="Run DrugBank importer")
    parser.add_argument("--all", action="store_true", help="Run all importers (default if none specified)")
    parser.add_argument("--db", default=None, help="Database path (unused here but matches enrich_database.py)")
    parser.add_argument("--compounds-file", default=os.path.join(ROOT, "seed_compounds.txt"), help="Path to seed compounds file")
    parser.add_argument("--dry-run", action="store_true", help="Preview run without writing (mock graph db)")
    args = parser.parse_args()
    
    do_stitch = args.stitch
    do_ctd = args.ctd
    do_drugbank = args.drugbank
    
    if not (do_stitch or do_ctd or do_drugbank):
        do_stitch = do_ctd = do_drugbank = True
    elif args.all:
        do_stitch = do_ctd = do_drugbank = True

    compounds_list = []
    if os.path.exists(args.compounds_file):
        with open(args.compounds_file, "r", encoding="utf-8") as f:
            compounds_list = [line.strip() for line in f if line.strip()]
    else:
        logger.error(f"Compounds file not found: {args.compounds_file}")
        sys.exit(1)
        
    print(f"[Import] Loaded {len(compounds_list)} compounds.")
    
    gdb = get_graph_database()
    
    if args.dry_run:
        print("[Import] Dry run enabled. Disabling Neo4j driver connection.")
        gdb.close()
        
    results = run_all_imports(compounds_list, gdb, do_stitch, do_ctd, do_drugbank)
    
    print("\n[Import Complete] Import Summary:")
    print(f"  * STITCH edges added:   {results['stitch_edges']}")
    print(f"  * CTD edges added:      {results['ctd_edges']}")
    print(f"  * DrugBank edges added: {results['drugbank_edges']}")
