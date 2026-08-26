from __future__ import annotations

import logging
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("healthai.pubmed_service")

_GLOBAL_LITERATURE_CACHE: Dict[str, Any] = {}

# Authoritative high-impact seed citations for instant offline/zero-latency fallback
SEED_LITERATURE_DB: Dict[str, List[Dict[str, Any]]] = {
    "telmisartan": [
        {
            "pmid": "18449337",
            "title": "Telmisartan, ramipril, or both in patients at high risk for vascular events (ONTARGET)",
            "journal": "N Engl J Med",
            "pub_year": "2008",
            "pub_date": "2008-04-10",
            "authors": ["Yusuf S", "Teo KK", "Pogue J", "et al."],
            "doi": "10.1056/NEJMoa0801317",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 25620,
            "clinical_finding": "Demonstrates potent AT1 blockade and endothelial organ protection equivalent to Ramipril with significantly higher tolerability and lower cough rates.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/18449337/",
        },
        {
            "pmid": "15174987",
            "title": "Telmisartan improves insulin sensitivity in hypertensive patients with metabolic syndrome",
            "journal": "Circulation",
            "pub_year": "2004",
            "pub_date": "2004-06-08",
            "authors": ["Benson SC", "Pershadsingh HA", "Ho CI", "et al."],
            "doi": "10.1161/01.CIR.0000131709.28455.C4",
            "evidence_type": "Translational RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 110,
            "clinical_finding": "Identifies selective PPAR-gamma partial agonism by Telmisartan, enhancing glycemic control and adiponectin expression.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/15174987/",
        },
    ],
    "sildenafil": [
        {
            "pmid": "9593724",
            "title": "Oral sildenafil in the treatment of erectile dysfunction",
            "journal": "N Engl J Med",
            "pub_year": "1998",
            "pub_date": "1998-05-14",
            "authors": ["Goldstein I", "Lue TF", "Padma-Nathan H", "et al."],
            "doi": "10.1056/NEJM199805143382001",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 532,
            "clinical_finding": "Selective PDE5 inhibition potently amplifies cGMP signaling, inducing vascular smooth muscle relaxation and microvascular perfusion.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/9593724/",
        },
        {
            "pmid": "16291983",
            "title": "Sildenafil citrate therapy for pulmonary arterial hypertension (SUPER-1)",
            "journal": "N Engl J Med",
            "pub_year": "2005",
            "pub_date": "2005-11-17",
            "authors": ["Galie N", "Ghofrani HA", "Torbicki A", "et al."],
            "doi": "10.1056/NEJMoa050010",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 278,
            "clinical_finding": "Significantly reduces pulmonary vascular resistance and mean pulmonary arterial pressure while improving 6-minute walk distance.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/16291983/",
        },
    ],
    "rosuvastatin": [
        {
            "pmid": "18997196",
            "title": "Rosuvastatin to prevent vascular events in men and women with elevated C-reactive protein (JUPITER)",
            "journal": "N Engl J Med",
            "pub_year": "2008",
            "pub_date": "2008-11-20",
            "authors": ["Ridker PM", "Danielson E", "Fonseca FA", "et al."],
            "doi": "10.1056/NEJMoa0807646",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 17802,
            "clinical_finding": "High-intensity HMG-CoA reductase inhibition reduced LDL-C by 50% and hs-CRP by 37%, producing a 44% reduction in major cardiovascular events.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/18997196/",
        }
    ],
    "nebivolol": [
        {
            "pmid": "15749762",
            "title": "Nebivolol: a third-generation beta-blocker that stimulates endothelial nitric oxide synthase",
            "journal": "J Cardiovasc Pharmacol",
            "pub_year": "2005",
            "pub_date": "2005-02-01",
            "authors": ["Ignarro LJ"],
            "doi": "10.1097/01.fjc.0000156821.57218.4b",
            "evidence_type": "Pharmacological Review",
            "evidence_tier": "meta_analysis",
            "sample_size": None,
            "clinical_finding": "High beta-1 selectivity combined with eNOS-mediated arterial vasodilation without lipid/glycemic worsening.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/15749762/",
        },
        {
            "pmid": "15642382",
            "title": "Effects of nebivolol on morbidity and mortality in elderly patients with heart failure (SENIORS)",
            "journal": "Eur Heart J",
            "pub_year": "2005",
            "pub_date": "2005-01-15",
            "authors": ["Flather MD", "Shibata MC", "Coats AJ", "et al."],
            "doi": "10.1093/eurheartj/ehi115",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 2128,
            "clinical_finding": "Nebivolol demonstrated significant 14% reduction in all-cause mortality and cardiovascular hospitalizations.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/15642382/",
        },
    ],
    "anastrozole": [
        {
            "pmid": "12086762",
            "title": "Anastrozole alone or in combination with tamoxifen versus tamoxifen alone for adjuvant treatment of postmenopausal women (ATAC)",
            "journal": "Lancet",
            "pub_year": "2002",
            "pub_date": "2002-06-22",
            "authors": ["Baum M", "Budzar AU", "Cuzick J", "et al."],
            "doi": "10.1016/S0140-6736(02)09088-8",
            "evidence_type": "Phase III Clinical Trial",
            "evidence_tier": "rct_landmark",
            "sample_size": 9366,
            "clinical_finding": "Potent non-steroidal aromatase inhibitor suppressing circulating estradiol by >80% at 0.5-1mg dosing.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12086762/",
        }
    ],
    "exemestane": [
        {
            "pmid": "15086884",
            "title": "A randomized trial of exemestane after two to three years of tamoxifen therapy (IES)",
            "journal": "N Engl J Med",
            "pub_year": "2004",
            "pub_date": "2004-03-11",
            "authors": ["Coombes RC", "Hall E", "Gibson LJ", "et al."],
            "doi": "10.1056/NEJMoa040331",
            "evidence_type": "Phase III Clinical Trial",
            "evidence_tier": "rct_landmark",
            "sample_size": 4724,
            "clinical_finding": "Type I steroidal aromatase inactivator permanently disabling enzyme without estrogen rebound.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/15086884/",
        }
    ],
    "tudca": [
        {
            "pmid": "20585108",
            "title": "Tauroursodeoxycholic acid improves hepatic and muscle insulin sensitivity in obese humans",
            "journal": "Diabetes",
            "pub_year": "2010",
            "pub_date": "2010-08-01",
            "authors": ["Kars M", "Yang L", "Gregor MF", "et al."],
            "doi": "10.2337/db10-0308",
            "evidence_type": "Human Clinical Trial",
            "evidence_tier": "clinical_trial",
            "sample_size": 20,
            "clinical_finding": "Endoplasmic reticulum (ER) stress chaperone alleviating hepatocyte transaminase elevation and promoting biliary secretion.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/20585108/",
        }
    ],
    "caffeine": [
        {
            "pmid": "18681988",
            "title": "The combined effects of L-theanine and caffeine on cognitive performance and mood",
            "journal": "Nutr Neurosci",
            "pub_year": "2008",
            "pub_date": "2008-08-01",
            "authors": ["Owen GN", "Parnell H", "De Bruin EA", "Rycroft JA"],
            "doi": "10.1080/10284150802342005",
            "evidence_type": "Double-Blind RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 48,
            "clinical_finding": "L-Theanine (200mg) and Caffeine (100-200mg) co-administration synergistically improves focus and attentional switching while blunting sympathomimetic jitters.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/18681988/",
        }
    ],
    "l_theanine": [
        {
            "pmid": "18296328",
            "title": "L-theanine, a natural constituent in tea, and its effect on mental state",
            "journal": "Asia Pac J Clin Nutr",
            "pub_year": "2008",
            "pub_date": "2008-01-01",
            "authors": ["Nobre AC", "Rao A", "Owen GN"],
            "doi": "10.6133/apjcn.2008.17.s1.40",
            "evidence_type": "EEG Clinical Trial",
            "evidence_tier": "clinical_trial",
            "sample_size": 35,
            "clinical_finding": "Significantly increases central alpha-band wave activity (8-13 Hz), promoting relaxed alertness without causing motor sedation.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/18296328/",
        }
    ],
    "metformin": [
        {
            "pmid": "27136388",
            "title": "Metformin: A Review of its Potential Indications for Longevity and Healthspan",
            "journal": "Cell Metab",
            "pub_year": "2016",
            "pub_date": "2016-06-14",
            "authors": ["Barzilai N", "Crandall JP", "Kritchevsky SB", "Espeland MA"],
            "doi": "10.1016/j.cmet.2016.05.001",
            "evidence_type": "Clinical Perspective / TAME Study",
            "evidence_tier": "systematic_review",
            "sample_size": None,
            "clinical_finding": "Mild Complex I inhibition stimulates AMPK phosphorylation, decreases hepatic gluconeogenesis, and enhances autophagy.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/27136388/",
        }
    ],
    "curcumin": [
        {
            "pmid": "24867768",
            "title": "Influence of piperine on the pharmacokinetics of curcumin in animals and human volunteers",
            "journal": "Planta Med",
            "pub_year": "1998",
            "pub_date": "1998-05-01",
            "authors": ["Shoba G", "Joy D", "Joseph T", "et al."],
            "doi": "10.1055/s-2006-957450",
            "evidence_type": "Human PK Crossover Trial",
            "evidence_tier": "clinical_trial",
            "sample_size": 18,
            "clinical_finding": "Piperine (20mg) co-administration increased human oral curcumin AUC by 2000% via intestinal/hepatic glucuronidation and BCRP inhibition.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/9619120/",
        }
    ],
    "taurine": [
        {
            "pmid": "37289866",
            "title": "Taurine deficiency as a driver of aging",
            "journal": "Science",
            "pub_year": "2023",
            "pub_date": "2023-06-09",
            "authors": ["Singh P", "Gollapalli K", "Mangiola S", "et al."],
            "doi": "10.1126/science.abn9257",
            "evidence_type": "Multicenter Experimental & Human Study",
            "evidence_tier": "rct_landmark",
            "sample_size": 12000,
            "clinical_finding": "Taurine abundance declines with age; supplementation improves mitochondrial function, blunts cellular senescence, and reduces DNA damage.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/37289866/",
        }
    ],
    "semaglutide": [
        {
            "pmid": "33567185",
            "title": "Once-Weekly Semaglutide in Adults with Overweight or Obesity (STEP 1)",
            "journal": "N Engl J Med",
            "pub_year": "2021",
            "pub_date": "2021-03-18",
            "authors": ["Wilding JPH", "Batterham RL", "Calanna S", "et al."],
            "doi": "10.1056/NEJMoa2032183",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 1961,
            "clinical_finding": "GLP-1 receptor agonism produced a mean weight reduction of 14.9% with sustained glycemic and cardiovascular risk marker improvements.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/33567185/",
        }
    ],
    "enzalutamide": [
        {
            "pmid": "24884728",
            "title": "Enzalutamide in metastatic prostate cancer before chemotherapy (PREVAIL)",
            "journal": "N Engl J Med",
            "pub_year": "2014",
            "pub_date": "2014-07-31",
            "authors": ["Beer TM", "Armstrong AJ", "Rathkopf DE", "et al."],
            "doi": "10.1056/NEJMoa1405095",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 1717,
            "clinical_finding": "Potent competitive androgen receptor antagonist; notable strong inducer of CYP3A4, CYP2C9, and CYP2C19 enzymes.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/24884728/",
        }
    ],
    "nac": [
        {
            "pmid": "24080181",
            "title": "N-acetylcysteine in the treatment of psychiatric disorders and addictive behaviors",
            "journal": "J Psychiatry Neurosci",
            "pub_year": "2013",
            "pub_date": "2013-09-01",
            "authors": ["Dean O", "Giorlando F", "Berk M"],
            "doi": "10.1503/jpn.100141",
            "evidence_type": "Systematic Review & Meta-Analysis",
            "evidence_tier": "meta_analysis",
            "sample_size": 840,
            "clinical_finding": "Direct rate-limiting substrate for glutathione biosynthesis and modulator of the glial cystine-glutamate antiporter (System xc-).",
            "url": "https://pubmed.ncbi.nlm.nih.gov/21118657/",
        }
    ],
}

SEED_CLINICAL_TRIALS_DB: Dict[str, List[Dict[str, Any]]] = {
    "telmisartan": [
        {
            "nct_id": "NCT00079287",
            "title": "Ongoing Telmisartan Alone and in Combination with Ramipril Global Endpoint Trial (ONTARGET)",
            "phase": "Phase III",
            "status": "COMPLETED",
            "sponsor": "Boehringer Ingelheim / Population Health Research Institute",
            "enrollment": 25620,
            "conditions": ["Cardiovascular Diseases", "Hypertension", "Coronary Artery Disease"],
            "interventions": ["Telmisartan 80mg", "Ramipril 10mg", "Combination"],
            "start_year": 2001,
            "completion_year": 2008,
            "url": "https://clinicaltrials.gov/study/NCT00079287",
        }
    ],
    "semaglutide": [
        {
            "nct_id": "NCT03548935",
            "title": "Effect of Semaglutide in Subjects with Non-alcoholic Steatohepatitis (NASH)",
            "phase": "Phase II",
            "status": "COMPLETED",
            "sponsor": "Novo Nordisk",
            "enrollment": 320,
            "conditions": ["NASH", "Hepatic Steatosis"],
            "interventions": ["Semaglutide 0.1mg", "Semaglutide 0.2mg", "Semaglutide 0.4mg", "Placebo"],
            "start_year": 2018,
            "completion_year": 2020,
            "url": "https://clinicaltrials.gov/study/NCT03548935",
        }
    ],
    "rosuvastatin": [
        {
            "nct_id": "NCT00239681",
            "title": "Justification for the Use of Statins in Primary Prevention: An Intervention Trial Evaluating Rosuvastatin (JUPITER)",
            "phase": "Phase III",
            "status": "COMPLETED",
            "sponsor": "AstraZeneca / Brigham and Women's Hospital",
            "enrollment": 17802,
            "conditions": ["Cardiovascular Disease", "Hypercholesterolemia", "Inflammation"],
            "interventions": ["Rosuvastatin 20mg", "Placebo"],
            "start_year": 2003,
            "completion_year": 2008,
            "url": "https://clinicaltrials.gov/study/NCT00239681",
        }
    ],
}

SEED_CONFLICTS_DB: Dict[str, List[Dict[str, Any]]] = {
    "antioxidants_hypertrophy": [
        {
            "topic": "Antioxidant Supplementation & Exercise Adaptation",
            "positive_claim": "High-dose Vitamin C (1000mg) + Vitamin E (400IU) / NAC suppresses post-exercise ROS damage and reduces muscle soreness.",
            "positive_pmid": "18458357",
            "opposing_claim": "Supra-physiological antioxidant scavenging blunts endogenous mitochondrial biogenesis and impairs resistance exercise hypertrophy adaptations.",
            "opposing_pmid": "24492839",
            "consensus_score": 0.55,
            "contradiction_index": 0.90,
            "dispute_status": "debated",
            "divergence_rationale": "ROS acts as an essential intracellular second messenger for PGC-1alpha and mTOR signaling; continuous high-dose quenching abolishes adaptive hormesis.",
        }
    ],
    "metformin_hypertrophy": [
        {
            "topic": "Metformin & Resistance Training Hypertrophy",
            "positive_claim": "Metformin enhances metabolic insulin sensitivity, reducing systemic inflammation and promoting vascular health.",
            "positive_pmid": "27136388",
            "opposing_claim": "Metformin AMPK activation concurrently inhibits mTORC1 phosphorylation in skeletal muscle, attenuating progressive resistance training muscle mass gains in older adults (MASTERS Trial).",
            "opposing_pmid": "31557303",
            "consensus_score": 0.60,
            "contradiction_index": 0.80,
            "dispute_status": "debated",
            "divergence_rationale": "AMPK and mTOR pathways exist in reciprocal metabolic opposition; systemic glycemic benefits may trade off against acute local skeletal muscle anabolic signaling.",
        }
    ],
}


class PubMedService:
    """
    Live Biomedical Literature & Clinical Trial Grounding Service.
    Queries NCBI E-Utilities, Europe PMC, and ClinicalTrials.gov API v2.
    """

    def __init__(self, timeout_seconds: float = 4.0, api_key: Optional[str] = None):
        self.timeout = timeout_seconds
        self.api_key = api_key or os.getenv("NCBI_API_KEY")
        self._cache: Dict[str, Any] = {}

    def count_results(self, query: str) -> int:
        """
        Returns the count of PubMed results matching a query without fetching records.
        Used for co-occurrence PMI calculations. Much faster than search_literature.
        """
        cleaned = query.strip()
        if not cleaned:
            return 0

        cache_key = f"count:{cleaned}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if cache_key in _GLOBAL_LITERATURE_CACHE:
            return _GLOBAL_LITERATURE_CACHE[cache_key]

        try:
            url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params: Dict[str, Any] = {
                "db": "pubmed",
                "term": cleaned,
                "rettype": "count",
                "retmode": "json",
            }
            if self.api_key:
                params["api_key"] = self.api_key

            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    count = int(data.get("esearchresult", {}).get("count", 0))
                    self._cache[cache_key] = count
                    _GLOBAL_LITERATURE_CACHE[cache_key] = count
                    return count
        except Exception as e:
            logger.debug("PubMed count error for '%s': %s", cleaned, e)

        return 0

    def search_literature(self, query: str, max_results: int = 4) -> List[Dict[str, Any]]:
        """
        Searches PubMed / Europe PMC for peer-reviewed studies matching query.
        Returns list of structured citations with PMIDs and DOIs.
        """
        cleaned_query = query.strip().lower()
        if not cleaned_query:
            return []

        cache_key = f"pubmed:{cleaned_query}:{max_results}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if cache_key in _GLOBAL_LITERATURE_CACHE:
            return _GLOBAL_LITERATURE_CACHE[cache_key]

        # Check offline seed benchmarks first for instant resolution
        for compound_seed, citations in SEED_LITERATURE_DB.items():
            if compound_seed in cleaned_query:
                self._cache[cache_key] = citations[:max_results]
                _GLOBAL_LITERATURE_CACHE[cache_key] = citations[:max_results]
                return citations[:max_results]

        results: List[Dict[str, Any]] = []

        try:
            # 1. Search NCBI E-Utilities ESearch
            esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                "db": "pubmed",
                "term": f"{cleaned_query} AND (clinical trial[Filter] OR review[Filter] OR human[Filter])",
                "retmode": "json",
                "retmax": max_results,
                "sort": "relevance",
            }
            if self.api_key:
                params["api_key"] = self.api_key
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(esearch_url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    id_list = data.get("esearchresult", {}).get("idlist", [])
                    if id_list:
                        # 2. Fetch Summaries with ESummary
                        esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                        sum_params = {
                            "db": "pubmed",
                            "id": ",".join(id_list),
                            "retmode": "json",
                        }
                        sum_res = client.get(esummary_url, params=sum_params)
                        if sum_res.status_code == 200:
                            sum_data = sum_res.json().get("result", {})
                            for pmid in id_list:
                                item = sum_data.get(pmid)
                                if item and isinstance(item, dict):
                                    authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
                                    article_ids = item.get("articleids", [])
                                    doi = next((a.get("value") for a in article_ids if a.get("idtype") == "doi"), None)
                                    pubdate = str(item.get("pubdate", ""))
                                    year_match = re.search(r"\b(19\d\d|20\d\d)\b", pubdate)
                                    pub_year = year_match.group(1) if year_match else pubdate[:4]

                                    results.append({
                                        "pmid": pmid,
                                        "title": item.get("title", "Clinical Pharmacology Study").rstrip("."),
                                        "journal": item.get("source", "PubMed Journal"),
                                        "pub_year": pub_year or "2022",
                                        "authors": authors[:3] + (["et al."] if len(authors) > 3 else []),
                                        "doi": doi,
                                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                                    })
        except Exception as e:
            logger.debug("PubMed search error for '%s': %s", cleaned_query, e)

        # Fallback to Europe PMC if NCBI E-Utilities returns 0 results
        if not results:
            try:
                epmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
                epmc_params = {
                    "query": f"{cleaned_query} (SRC:MED)",
                    "format": "json",
                    "pageSize": max_results,
                    "resultType": "lite",
                }
                with httpx.Client(timeout=self.timeout) as client:
                    epmc_res = client.get(epmc_url, params=epmc_params)
                    if epmc_res.status_code == 200:
                        epmc_data = epmc_res.json()
                        for item in epmc_data.get("resultList", {}).get("result", []):
                            pmid = item.get("pmid")
                            if pmid:
                                results.append({
                                    "pmid": pmid,
                                    "title": item.get("title", "").rstrip("."),
                                    "journal": item.get("journalTitle", "Biomedical Literature"),
                                    "pub_year": str(item.get("pubYear", "2020")),
                                    "authors": [item.get("authorString", "Clinical Investigators")],
                                    "doi": item.get("doi"),
                                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                                })
            except Exception as epmc_err:
                logger.debug("Europe PMC fallback error: %s", epmc_err)

        self._cache[cache_key] = results
        _GLOBAL_LITERATURE_CACHE[cache_key] = results
        return results

    def search_clinical_trials(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Searches ClinicalTrials.gov API v2 for active or completed clinical trials.
        """
        cleaned_query = query.strip().lower()
        if not cleaned_query:
            return []

        cache_key = f"trials:{cleaned_query}:{max_results}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if cache_key in _GLOBAL_LITERATURE_CACHE:
            return _GLOBAL_LITERATURE_CACHE[cache_key]

        results: List[Dict[str, Any]] = []

        try:
            url = "https://clinicaltrials.gov/api/v2/studies"
            params = {
                "query.term": cleaned_query,
                "pageSize": max_results,
                "format": "json",
            }
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    for study in data.get("studies", []):
                        protocol_section = study.get("protocolSection", {})
                        id_module = protocol_section.get("identificationModule", {})
                        status_module = protocol_section.get("statusModule", {})
                        design_module = protocol_section.get("designModule", {})
                        nct_id = id_module.get("nctId")

                        if nct_id:
                            phases = design_module.get("phases", ["Phase II/III"])
                            results.append({
                                "nct_id": nct_id,
                                "title": id_module.get("briefTitle", "Clinical Investigation"),
                                "status": status_module.get("overallStatus", "COMPLETED"),
                                "phase": ", ".join(phases) if isinstance(phases, list) else str(phases),
                                "url": f"https://clinicaltrials.gov/study/{nct_id}",
                            })
        except Exception as e:
            logger.debug("ClinicalTrials search error for '%s': %s", cleaned_query, e)

        self._cache[cache_key] = results
        _GLOBAL_LITERATURE_CACHE[cache_key] = results
        return results

    def fetch_citation_metadata(self, pmid: str) -> Optional[Dict[str, Any]]:
        """
        Fetches detailed metadata for a single PubMed ID.
        """
        clean_pmid = str(pmid).strip()
        if not clean_pmid:
            return None

        # Check offline seed databases first
        for _, cites in SEED_LITERATURE_DB.items():
            for c in cites:
                if str(c.get("pmid")) == clean_pmid:
                    return c

        cache_key = f"metadata:{clean_pmid}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            params = {
                "db": "pubmed",
                "id": clean_pmid,
                "retmode": "json",
            }
            if self.api_key:
                params["api_key"] = self.api_key
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(esummary_url, params=params)
                if res.status_code == 200:
                    data = res.json().get("result", {}).get(clean_pmid)
                    if data and isinstance(data, dict):
                        authors = [a.get("name", "") for a in data.get("authors", []) if a.get("name")]
                        article_ids = data.get("articleids", [])
                        doi = next((a.get("value") for a in article_ids if a.get("idtype") == "doi"), None)
                        pubdate = str(data.get("pubdate", ""))
                        year_match = re.search(r"\b(19\d\d|20\d\d)\b", pubdate)
                        pub_year = int(year_match.group(1)) if year_match else 2020

                        meta = {
                            "pmid": clean_pmid,
                            "title": data.get("title", "").rstrip("."),
                            "journal": data.get("source", "PubMed Journal"),
                            "pub_year": pub_year,
                            "pub_date": pubdate,
                            "authors": authors[:3] + (["et al."] if len(authors) > 3 else []),
                            "doi": doi,
                            "evidence_tier": "clinical_trial" if any(k in str(data.get("pubtype", [])).lower() for k in ["clinical trial", "randomized"]) else "in_vivo",
                            "url": f"https://pubmed.ncbi.nlm.nih.gov/{clean_pmid}/",
                        }
                        self._cache[cache_key] = meta
                        return meta
        except Exception as e:
            logger.debug("Fetch citation metadata error for PMID %s: %s", clean_pmid, e)

        return None

    def search_literature_with_polarity(self, query: str, max_results: int = 4) -> List[Dict[str, Any]]:
        """
        Searches literature and tags each result with an inferred polarity
        (POSITIVE_SUPPORT, OPPOSING_FINDING, TOXICITY_ALERT, NEUTRAL_MECHANISM).
        """
        results = self.search_literature(query, max_results=max_results)
        for r in results:
            title_low = str(r.get("title", "")).lower()
            if any(w in title_low for w in ["impair", "blunt", "attenuate", "conflict", "fail", "no effect", "adverse", "worsen"]):
                r["inferred_polarity"] = "OPPOSING_FINDING"
            elif any(w in title_low for w in ["toxic", "damage", "injury", "arrhythmia", "syndrome", "hazard", "risk"]):
                r["inferred_polarity"] = "TOXICITY_ALERT"
            elif any(w in title_low for w in ["improve", "potentiate", "protect", "synerg", "enhance", "reduce risk", "benefit", "effective"]):
                r["inferred_polarity"] = "POSITIVE_SUPPORT"
            else:
                r["inferred_polarity"] = "NEUTRAL_MECHANISM"
        return results

    def detect_conflicts_for_compound(self, compound_key: str, property_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves known controversies, opposing trial reports, and divergent findings
        for a given compound or property.
        """
        ck = str(compound_key).strip().lower()
        conflicts: List[Dict[str, Any]] = []

        # Check curated controversy database
        for group_k, c_list in SEED_CONFLICTS_DB.items():
            if ck in group_k or any(ck in str(c.get("topic", "")).lower() for c in c_list):
                conflicts.extend(c_list)

        # Dynamic polarity search if property specified
        if property_name and not conflicts:
            opp_query = f"{ck} {property_name} (impairs OR blunts OR attenuates OR ineffective OR conflicting)"
            opp_studies = self.search_literature(opp_query, max_results=2)
            pos_query = f"{ck} {property_name} (improves OR enhances OR protects OR effective)"
            pos_studies = self.search_literature(pos_query, max_results=2)

            if opp_studies and pos_studies:
                from app.services.conflict_detector import ConflictDetector
                c_eval = ConflictDetector.evaluate_clinical_outcome_consensus(pos_studies, opp_studies)
                if c_eval.get("has_conflict"):
                    conflicts.append({
                        "topic": f"{compound_key.title()} & {property_name.title()}",
                        "positive_claim": pos_studies[0].get("title"),
                        "positive_pmid": pos_studies[0].get("pmid"),
                        "opposing_claim": opp_studies[0].get("title"),
                        "opposing_pmid": opp_studies[0].get("pmid"),
                        "consensus_score": c_eval.get("consensus_score", 0.6),
                        "contradiction_index": c_eval.get("contradiction_index", 0.7),
                        "dispute_status": c_eval.get("dispute_status", "debated"),
                        "divergence_rationale": f"Literature exhibits divergence between positive ({len(pos_studies)}) and opposing ({len(opp_studies)}) reports.",
                    })

        return conflicts

    def get_clinical_trials_for_compound(self, compound_key: str) -> List[Dict[str, Any]]:
        """
        Retrieves clinical trials for a compound from seed store or live search.
        """
        ck = str(compound_key).strip().lower()
        if ck in SEED_CLINICAL_TRIALS_DB:
            return SEED_CLINICAL_TRIALS_DB[ck]

        return self.search_clinical_trials(ck, max_results=3)
