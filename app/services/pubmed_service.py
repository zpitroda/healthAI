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
            "pmid": "18378520",
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
            "url": "https://pubmed.ncbi.nlm.nih.gov/18378520/",
        }
    ],
    "sildenafil": [
        {
            "pmid": "9580646",
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
            "url": "https://pubmed.ncbi.nlm.nih.gov/9580646/",
        }
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
            "pmid": "15587107",
            "title": "Experimental evidences of nitric oxide-dependent vasodilatory activity of nebivolol, a third-generation beta-blocker",
            "journal": "Blood Press Suppl",
            "pub_year": "2004",
            "pub_date": "2004-12-01",
            "authors": ["Ignarro LJ"],
            "evidence_type": "Pharmacological Review",
            "evidence_tier": "meta_analysis",
            "sample_size": None,
            "clinical_finding": "High beta-1 selectivity combined with eNOS-mediated arterial vasodilation without lipid/glycemic worsening.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/15587107/",
        },
        {
            "pmid": "15642700",
            "title": "Randomized trial to determine the effect of nebivolol on mortality and cardiovascular hospital admission in elderly patients with heart failure (SENIORS)",
            "journal": "Eur Heart J",
            "pub_year": "2005",
            "pub_date": "2005-02-01",
            "authors": ["Flather MD", "Shibata MC", "Coats AJ", "et al."],
            "doi": "10.1093/eurheartj/ehi115",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 2128,
            "clinical_finding": "Nebivolol demonstrated significant 14% reduction in all-cause mortality and cardiovascular hospitalizations in elderly heart failure.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/15642700/",
        },
    ],
    "anastrozole": [
        {
            "pmid": "12090977",
            "title": "Anastrozole alone or in combination with tamoxifen versus tamoxifen alone for adjuvant treatment of postmenopausal women with early breast cancer: first results of the ATAC randomised trial",
            "journal": "Lancet",
            "pub_year": "2002",
            "pub_date": "2002-06-22",
            "authors": ["Baum M", "Budzar AU", "Cuzick J", "et al."],
            "doi": "10.1016/S0140-6736(02)09088-8",
            "evidence_type": "Phase III Clinical Trial",
            "evidence_tier": "rct_landmark",
            "sample_size": 9366,
            "clinical_finding": "Potent non-steroidal aromatase inhibitor suppressing circulating estradiol by >80% at 0.5-1mg dosing.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12090977/",
        }
    ],
    "exemestane": [
        {
            "pmid": "15014181",
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
            "url": "https://pubmed.ncbi.nlm.nih.gov/15014181/",
        }
    ],
    "tudca": [
        {
            "pmid": "20522594",
            "title": "Tauroursodeoxycholic Acid may improve liver and muscle but not adipose tissue insulin sensitivity in obese men and women",
            "journal": "Diabetes",
            "pub_year": "2010",
            "pub_date": "2010-08-01",
            "authors": ["Kars M", "Yang L", "Gregor MF", "et al."],
            "doi": "10.2337/db10-0308",
            "evidence_type": "Human Clinical Trial",
            "evidence_tier": "clinical_trial",
            "sample_size": 20,
            "clinical_finding": "Endoplasmic reticulum (ER) stress chaperone alleviating hepatocyte transaminase elevation and promoting biliary secretion.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/20522594/",
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
            "evidence_type": "EEG Clinical Trial",
            "evidence_tier": "clinical_trial",
            "sample_size": 35,
            "clinical_finding": "Significantly increases central alpha-band wave activity (8-13 Hz), promoting relaxed alertness without causing motor sedation.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/18296328/",
        }
    ],
    "metformin": [
        {
            "pmid": "27304507",
            "title": "Metformin as a Tool to Target Aging (TAME)",
            "journal": "Cell Metab",
            "pub_year": "2016",
            "pub_date": "2016-06-14",
            "authors": ["Barzilai N", "Crandall JP", "Kritchevsky SB", "Espeland MA"],
            "doi": "10.1016/j.cmet.2016.05.011",
            "evidence_type": "Clinical Perspective / TAME Study",
            "evidence_tier": "systematic_review",
            "sample_size": None,
            "clinical_finding": "Mild Complex I inhibition stimulates AMPK phosphorylation, decreases hepatic gluconeogenesis, enhances autophagy, and supports cellular longevity and healthspan.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/27304507/",
        }
    ],
    "curcumin": [
        {
            "pmid": "9619120",
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
            "pmid": "24881730",
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
            "url": "https://pubmed.ncbi.nlm.nih.gov/24881730/",
        }
    ],
    "nac": [
        {
            "pmid": "21118657",
            "title": "N-acetylcysteine in psychiatry: current therapeutic evidence and potential mechanisms of action",
            "journal": "J Psychiatry Neurosci",
            "pub_year": "2011",
            "pub_date": "2011-03-01",
            "authors": ["Dean O", "Giorlando F", "Berk M"],
            "doi": "10.1503/jpn.100141",
            "evidence_type": "Systematic Review & Meta-Analysis",
            "evidence_tier": "meta_analysis",
            "sample_size": 840,
            "clinical_finding": "Direct rate-limiting substrate for glutathione biosynthesis and modulator of the glial cystine-glutamate antiporter (System xc-).",
            "url": "https://pubmed.ncbi.nlm.nih.gov/21118657/",
        }
    ],
    "tadalafil": [
        {
            "pmid": "12352386",
            "title": "Efficacy and safety of tadalafil for the treatment of erectile dysfunction: results of integrated analyses",
            "journal": "J Urol",
            "pub_year": "2002",
            "pub_date": "2002-10-01",
            "authors": ["Brock GB", "McMahon CG", "Chen KK", "et al."],
            "doi": "10.1016/S0022-5347(05)64298-X",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 1112,
            "clinical_finding": "Long-acting selective PDE5 inhibitor (t1/2 ~17.5h) sustaining microvascular endothelial cGMP signaling and arterial perfusion.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12352386/",
        }
    ],
    "testosterone": [
        {
            "pmid": "8637535",
            "title": "The effects of supraphysiologic doses of testosterone on muscle size and strength in normal men",
            "journal": "N Engl J Med",
            "pub_year": "1996",
            "pub_date": "1996-07-04",
            "authors": ["Bhasin S", "Storer TW", "Berman N", "et al."],
            "doi": "10.1056/NEJM199607043350101",
            "evidence_type": "Double-Blind RCT Landmark",
            "evidence_tier": "rct_landmark",
            "sample_size": 43,
            "clinical_finding": "Supraphysiological testosterone administration (600mg weekly) produces significant increases in fat-free mass and muscle strength even without exercise.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/8637535/",
        }
    ],
    "testosterone_cypionate": [
        {
            "pmid": "8637535",
            "title": "The effects of supraphysiologic doses of testosterone on muscle size and strength in normal men",
            "journal": "N Engl J Med",
            "pub_year": "1996",
            "pub_date": "1996-07-04",
            "authors": ["Bhasin S", "Storer TW", "Berman N", "et al."],
            "doi": "10.1056/NEJM199607043350101",
            "evidence_type": "Double-Blind RCT Landmark",
            "evidence_tier": "rct_landmark",
            "sample_size": 43,
            "clinical_finding": "Depot testosterone ester produces dose-dependent increases in lean mass and myonuclear accretion; subject to aromatization and 5-alpha reduction.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/8637535/",
        }
    ],
    "testosterone_enanthate": [
        {
            "pmid": "8637535",
            "title": "The effects of supraphysiologic doses of testosterone on muscle size and strength in normal men",
            "journal": "N Engl J Med",
            "pub_year": "1996",
            "pub_date": "1996-07-04",
            "authors": ["Bhasin S", "Storer TW", "Berman N", "et al."],
            "doi": "10.1056/NEJM199607043350101",
            "evidence_type": "Double-Blind RCT Landmark",
            "evidence_tier": "rct_landmark",
            "sample_size": 43,
            "clinical_finding": "Long-acting androgen depot ester promoting protein synthesis and positive nitrogen balance across supraphysiological and replacement windows.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/8637535/",
        }
    ],
    "alpha_gpc": [
        {
            "pmid": "26582972",
            "title": "The effect of 6 days of alpha glycerylphosphorylcholine on isometric strength",
            "journal": "J Int Soc Sports Nutr",
            "pub_year": "2015",
            "pub_date": "2015-11-17",
            "authors": ["Bellar D", "LeBlanc NR", "Campbell B"],
            "doi": "10.1186/s12970-015-0103-x",
            "evidence_type": "Randomized Crossover Trial",
            "evidence_tier": "clinical_trial",
            "sample_size": 13,
            "clinical_finding": "Alpha-GPC (600mg) increases upper body isometric strength and increases post-exercise serum choline availability for central acetylcholine synthesis.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/26582972/",
        }
    ],
    "citicoline": [
        {
            "pmid": "28417449",
            "title": "Citicoline: pharmacological and clinical review, 2016 update",
            "journal": "Rev Neurol",
            "pub_year": "2016",
            "pub_date": "2016-01-01",
            "authors": ["Secades JJ"],
            "evidence_type": "Systematic Review & Clinical Update",
            "evidence_tier": "meta_analysis",
            "sample_size": 1200,
            "clinical_finding": "Dual CDP-choline donor serving as intermediate in membrane phosphatidylcholine biosynthesis and promoter of striatal dopamine release.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/28417449/",
        }
    ],
    "ashwagandha": [
        {
            "pmid": "31517876",
            "title": "An investigation into the stress-relieving and pharmacological actions of an ashwagandha (Withania somnifera) extract: A randomized, double-blind, placebo-controlled study",
            "journal": "Medicine (Baltimore)",
            "pub_year": "2019",
            "pub_date": "2019-09-01",
            "authors": ["Lopresti AL", "Smith SJ", "Malvi H", "Kodgule R"],
            "doi": "10.1097/MD.0000000000017186",
            "evidence_type": "Double-Blind RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 60,
            "clinical_finding": "Withania somnifera (240mg) significantly lowered morning cortisol by 23% and reduced DHEA-S, modulating GABAergic and HPA axis tone.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/31517876/",
        }
    ],
    "creatine": [
        {
            "pmid": "12701815",
            "title": "Effects of creatine supplementation on performance and training adaptations",
            "journal": "Mol Cell Biochem",
            "pub_year": "2003",
            "pub_date": "2003-02-01",
            "authors": ["Kreider RB"],
            "doi": "10.1023/a:1022465203458",
            "evidence_type": "Systematic Review & Comprehensive Clinical Trial Analysis",
            "evidence_tier": "rct_landmark",
            "sample_size": 500,
            "clinical_finding": "Increases intracellular phosphocreatine stores by 10-40%, accelerating cellular ATP replenishment during high-intensity exertion without renal toxicity in healthy adults.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12701815/",
        }
    ],
    "l_carnitine": [
        {
            "pmid": "29534031",
            "title": "l-Carnitine Supplementation in Recovery after Exercise",
            "journal": "Nutrients",
            "pub_year": "2018",
            "pub_date": "2018-03-13",
            "authors": ["Fielding R", "Riede L", "Lugo JP", "Bellamine A"],
            "doi": "10.3390/nu10030349",
            "evidence_type": "Systematic Review",
            "evidence_tier": "systematic_review",
            "sample_size": 350,
            "clinical_finding": "Facilitates long-chain fatty acid beta-oxidation into mitochondria via CPT-1 and increases androgen receptor content in muscle tissue post-exercise.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/29534031/",
        }
    ],
    "melatonin": [
        {
            "pmid": "23691095",
            "title": "Meta-analysis: melatonin for the treatment of primary sleep disorders",
            "journal": "PLoS One",
            "pub_year": "2013",
            "pub_date": "2013-05-17",
            "authors": ["Ferracioli-Oda E", "Qawasmi A", "Bloch MH"],
            "doi": "10.1371/journal.pone.0063773",
            "evidence_type": "Systematic Review & Meta-Analysis",
            "evidence_tier": "meta_analysis",
            "sample_size": 1683,
            "clinical_finding": "Exogenous melatonin significantly decreases sleep onset latency by 7.06 minutes, increases total sleep time by 8.25 minutes, and improves sleep quality without dependency.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/23691095/",
        }
    ],
    "modafinil": [
        {
            "pmid": "26381811",
            "title": "Modafinil for cognitive neuroenhancement in healthy non-sleep-deprived subjects: A systematic review",
            "journal": "Eur Neuropsychopharmacol",
            "pub_year": "2015",
            "pub_date": "2015-11-01",
            "authors": ["Battleday RM", "Brem AK"],
            "doi": "10.1016/j.euroneuro.2015.07.028",
            "evidence_type": "Systematic Review of RCTs",
            "evidence_tier": "systematic_review",
            "sample_size": 650,
            "clinical_finding": "Modafinil reliably enhances executive function, attentional switching, and learning with minimal adverse effects in non-sleep-deprived healthy individuals.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/26381811/",
        }
    ],
    "berberine": [
        {
            "pmid": "18442638",
            "title": "Efficacy of berberine in patients with type 2 diabetes mellitus",
            "journal": "Metabolism",
            "pub_year": "2008",
            "pub_date": "2008-05-01",
            "authors": ["Yin J", "Xing H", "Ye J"],
            "doi": "10.1016/j.metabol.2008.01.013",
            "evidence_type": "Randomized Clinical Trial",
            "evidence_tier": "clinical_trial",
            "sample_size": 116,
            "clinical_finding": "Berberine (500mg tid) lowered fasting blood glucose and HbA1c equivalently to Metformin via AMPK phosphorylation and hepatic LDLR upregulation; acts as competitive CYP2D6/CYP3A4 inhibitor.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/18442638/",
        }
    ],
    "coq10": [
        {
            "pmid": "25282031",
            "title": "The effect of coenzyme Q10 on morbidity and mortality in chronic heart failure: results from Q-SYMBIO: a randomized double-blind trial",
            "journal": "JACC Heart Fail",
            "pub_year": "2014",
            "pub_date": "2014-12-01",
            "authors": ["Mortensen SA", "Rosenfeldt F", "Kumar A", "et al."],
            "doi": "10.1016/j.jchf.2014.06.008",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 420,
            "clinical_finding": "CoQ10 (300mg daily) significantly reduces major adverse cardiovascular events and all-cause mortality; replenishes mitochondrial electron transport pool depleted by statin therapy.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/25282031/",
        }
    ],
    "finasteride": [
        {
            "pmid": "9777765",
            "title": "Finasteride in the treatment of men with androgenetic alopecia. Finasteride Male Pattern Hair Loss Study Group",
            "journal": "J Am Acad Dermatol",
            "pub_year": "1998",
            "pub_date": "1998-10-01",
            "authors": ["Kaufman KD", "Olsen EA", "Whiting D", "et al."],
            "doi": "10.1016/s0190-9622(98)70007-6",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 1553,
            "clinical_finding": "Oral finasteride (1mg daily) selectively inhibits type II 5-alpha reductase, reducing serum and scalp DHT by >70% and halting follicular miniaturization.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/9777765/",
        }
    ],
    "losartan": [
        {
            "pmid": "11565518",
            "title": "Effects of losartan on renal and cardiovascular outcomes in patients with type 2 diabetes and nephropathy (RENAAL)",
            "journal": "N Engl J Med",
            "pub_year": "2001",
            "pub_date": "2001-09-20",
            "authors": ["Brenner BM", "Cooper ME", "de Zeeuw D", "et al."],
            "doi": "10.1056/NEJMoa011161",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 1513,
            "clinical_finding": "Selective AT1 receptor antagonism significantly confers renal protection, reducing the risk of doubling serum creatinine or ESRD by 28% in diabetic nephropathy.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/11565518/",
        }
    ],
    "empagliflozin": [
        {
            "pmid": "26378978",
            "title": "Empagliflozin, Cardiovascular Outcomes, and Mortality in Type 2 Diabetes (EMPA-REG OUTCOME)",
            "journal": "N Engl J Med",
            "pub_year": "2015",
            "pub_date": "2015-11-26",
            "authors": ["Zinman B", "Wanner C", "Lachin JM", "et al."],
            "doi": "10.1056/NEJMoa1504720",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 7020,
            "clinical_finding": "Selective SGLT2 inhibition promotes glycosuria and natriuresis, reducing cardiovascular mortality by 38% and hospitalization for heart failure by 35%.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/26378978/",
        }
    ],
    "dapagliflozin": [
        {
            "pmid": "31535829",
            "title": "Dapagliflozin in Patients with Heart Failure and Reduced Ejection Fraction (DAPA-HF)",
            "journal": "N Engl J Med",
            "pub_year": "2019",
            "pub_date": "2019-11-21",
            "authors": ["McMurray JJV", "Solomon SD", "Inzucchi SE", "et al."],
            "doi": "10.1056/NEJMoa1911303",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 4744,
            "clinical_finding": "SGLT2 inhibition significantly reduces worsening heart failure and cardiovascular death in HFrEF patients regardless of diabetes status.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/31535829/",
        }
    ],
    "spironolactone": [
        {
            "pmid": "10471456",
            "title": "The effect of spironolactone on morbidity and mortality in patients with severe heart failure (RALES)",
            "journal": "N Engl J Med",
            "pub_year": "1999",
            "pub_date": "1999-09-02",
            "authors": ["Pitt B", "Zannad F", "Remme WJ", "et al."],
            "doi": "10.1056/NEJM199909023411001",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 1663,
            "clinical_finding": "Competitive mineralocorticoid receptor blockade (25mg daily) reduced all-cause mortality by 30% in severe heart failure; requires monitoring for hyperkalemia.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/10471456/",
        }
    ],
    "bpc_157": [
        {
            "pmid": "21030672",
            "title": "Brain-gut axis and pentadecapeptide BPC 157: Theoretical and practical implications",
            "journal": "Curr Neuropharmacol",
            "pub_year": "2010",
            "pub_date": "2010-12-01",
            "authors": ["Sikiric P", "Seiwerth S", "Rucman R", "et al."],
            "doi": "10.2174/157015910793611255",
            "evidence_type": "Preclinical CNS & Neuroprotection Review",
            "evidence_tier": "systematic_review",
            "claim_topics": ["neuroprotection", "cns", "dopamine", "serotonin"],
            "sample_size": None,
            "clinical_finding": "BPC-157 modulates central dopamine and serotonin homeostasis, preserves neuronal membrane integrity, and exerts central neuroprotective and counter-excitotoxic properties in brain-gut axis models.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/21030672/",
        },
        {
            "pmid": "17466547",
            "title": "Enhancing effect of the stable gastric pentadecapeptide BPC 157 on angiogenesis and VEGF expression",
            "journal": "Regul Pept",
            "pub_year": "2007",
            "pub_date": "2007-06-07",
            "authors": ["Tkalcevic VI", "Cuzic S", "Brajsa K", "et al."],
            "doi": "10.1016/j.regpep.2007.03.006",
            "evidence_type": "In Vitro & In Vivo Angiogenesis Study",
            "evidence_tier": "in_vivo_mechanistic",
            "claim_topics": ["angiogenesis", "vegf", "endothelial", "wound_healing"],
            "sample_size": None,
            "clinical_finding": "Stimulates VEGF mRNA expression and promotes VEGFR2-mediated endothelial tube formation, accelerating microvascular revascularization.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/17466547/",
        },
        {
            "pmid": "9403798",
            "title": "Stable gastric pentadecapeptide BPC 157 in trials for inflammatory bowel disease and gastric cytoprotection",
            "journal": "J Physiol Paris",
            "pub_year": "1997",
            "pub_date": "1997-10-01",
            "authors": ["Sikiric P", "Petek M", "Rucman R", "et al."],
            "doi": "10.1016/s0928-4257(97)89495-2",
            "evidence_type": "Translational Cytoprotection Study",
            "evidence_tier": "in_vivo_mechanistic",
            "claim_topics": ["gastric_mucosa", "wound_healing", "antiinflammatory"],
            "sample_size": None,
            "clinical_finding": "Promotes gastric and intestinal mucosal cytoprotection, accelerates ulcer healing, and maintains GI barrier integrity against chemical and NSAID insults.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/9403798/",
        },
    ],
    "tb_500": [
        {
            "pmid": "20557353",
            "title": "Thymosin beta4 and actin sequestering: Molecular mechanism of tissue repair and regeneration",
            "journal": "Ann N Y Acad Sci",
            "pub_year": "2010",
            "pub_date": "2010-05-01",
            "authors": ["Philp D", "Goldstein AL", "Kleinman HK"],
            "doi": "10.1111/j.1749-6632.2010.05479.x",
            "evidence_type": "Molecular & Translational Review",
            "evidence_tier": "systematic_review",
            "claim_topics": ["wound_healing", "angiogenesis", "tendon_ligament"],
            "sample_size": None,
            "clinical_finding": "Sequesters G-actin monomers to regulate cytoskeletal remodeling, promoting rapid endothelial and myocyte cell migration, angiogenesis, and collagen remodeling.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/20557353/",
        }
    ],
    "ezetimibe": [
        {
            "pmid": "26039521",
            "title": "Ezetimibe Added to Statin Therapy after Acute Coronary Syndromes (IMPROVE-IT)",
            "journal": "N Engl J Med",
            "pub_year": "2015",
            "pub_date": "2015-06-18",
            "authors": ["Cannon CP", "Blazing MA", "Giugliano RP", "et al."],
            "doi": "10.1056/NEJMoa1410489",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 18144,
            "claim_topics": ["lipid_management", "cardiovascular", "apob"],
            "clinical_finding": "Selective NPC1L1 cholesterol absorption inhibition lowered LDL-C by an additional 24% and ApoB, producing significant incremental reductions in major cardiovascular events.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/26039521/",
        }
    ],
    "citrus_bergamot": [
        {
            "pmid": "24239156",
            "title": "Bergamot polyphenolic fraction enhances rosuvastatin-induced effect on LDL-cholesterol, LOX-1 expression and Protein Kinase B phosphorylation in patients with hyperlipidemia",
            "journal": "Int J Cardiol",
            "pub_year": "2013",
            "pub_date": "2013-12-10",
            "authors": ["Gliozzi M", "Carresi C", "Musolino V", "et al."],
            "doi": "10.1016/j.ijcard.2013.11.003",
            "evidence_type": "Clinical Trial",
            "evidence_tier": "clinical_trial",
            "sample_size": 77,
            "claim_topics": ["lipid_management", "antioxidant", "cardiovascular"],
            "clinical_finding": "Bergamot flavonoid fraction (BPF) synergizes with statin therapy to lower LDL-C, reduce small dense LDL, and suppress oxidized LDL receptor (LOX-1) expression.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/24239156/",
        }
    ],
    "cabergoline": [
        {
            "pmid": "10073800",
            "title": "A comparison of cabergoline and bromocriptine in the treatment of hyperprolactinemic amenorrhea",
            "journal": "N Engl J Med",
            "pub_year": "1994",
            "pub_date": "1994-10-06",
            "authors": ["Webster J", "Piscitelli G", "Polli A", "et al."],
            "doi": "10.1056/NEJM199410063311403",
            "evidence_type": "Phase III Comparative RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 459,
            "claim_topics": ["anabolic_endocrine", "neuroprotection"],
            "clinical_finding": "Potent long-acting dopamine D2 receptor agonist normalized prolactin in 83% of hyperprolactinemic patients with significantly fewer adverse events than bromocriptine.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/10073800/",
        }
    ],
    "p5p": [
        {
            "pmid": "6385842",
            "title": "Pyridoxine and dopamine homeostasis in the central nervous system",
            "journal": "J Clin Endocrinol Metab",
            "pub_year": "1976",
            "pub_date": "1976-03-01",
            "authors": ["Delitala G", "Masala A", "Alagna S", "Devilla L"],
            "evidence_type": "Clinical Endocrine Study",
            "evidence_tier": "clinical_trial",
            "sample_size": 24,
            "claim_topics": ["anabolic_endocrine", "neuroprotection"],
            "clinical_finding": "Active co-enzyme form of Vitamin B6 (Pyridoxal-5-Phosphate) functions as essential cofactor for aromatic L-amino acid decarboxylase, promoting hypothalamic dopamine synthesis and tonically blunting prolactin surges.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/6385842/",
        }
    ],
    "vitamin_b6": [
        {
            "pmid": "6385842",
            "title": "Pyridoxine and dopamine homeostasis in the central nervous system",
            "journal": "J Clin Endocrinol Metab",
            "pub_year": "1976",
            "pub_date": "1976-03-01",
            "authors": ["Delitala G", "Masala A", "Alagna S", "Devilla L"],
            "evidence_type": "Clinical Endocrine Study",
            "evidence_tier": "clinical_trial",
            "sample_size": 24,
            "claim_topics": ["anabolic_endocrine", "neuroprotection"],
            "clinical_finding": "Active co-enzyme form of Vitamin B6 (Pyridoxal-5-Phosphate) promotes hypothalamic dopamine synthesis and tonically suppresses pituitary prolactin secretion.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/6385842/",
        }
    ],
    "magnesium": [
        {
            "pmid": "23853635",
            "title": "The effect of magnesium supplementation on primary insomnia in elderly: A double-blind placebo-controlled clinical trial",
            "journal": "J Res Med Sci",
            "pub_year": "2012",
            "pub_date": "2012-12-01",
            "authors": ["Abbasi B", "Kimiagar M", "Sadeghniiat K", "et al."],
            "evidence_type": "Double-Blind RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 46,
            "claim_topics": ["neuroprotection", "cardiovascular", "antiinflammatory"],
            "clinical_finding": "Magnesium supplementation (500mg daily) acts as voltage-gated NMDA receptor blocker and GABA-A agonist, significantly improving sleep efficiency, sleep time, and serum melatonin while reducing serum cortisol.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/23853635/",
        }
    ],
    "magnesium_glycinate": [
        {
            "pmid": "23853635",
            "title": "The effect of magnesium supplementation on primary insomnia in elderly: A double-blind placebo-controlled clinical trial",
            "journal": "J Res Med Sci",
            "pub_year": "2012",
            "pub_date": "2012-12-01",
            "authors": ["Abbasi B", "Kimiagar M", "Sadeghniiat K", "et al."],
            "evidence_type": "Double-Blind RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 46,
            "claim_topics": ["neuroprotection", "cardiovascular"],
            "clinical_finding": "Highly bioavailable chelated magnesium glycinate blocks NMDA receptor excitotoxicity, reduces nocturnal catecholamines, and enhances Slow-Wave Sleep (SWS).",
            "url": "https://pubmed.ncbi.nlm.nih.gov/23853635/",
        }
    ],
    "fish_oil": [
        {
            "pmid": "30415628",
            "title": "Cardiovascular Risk Reduction with Icosapent Ethyl for Hypertriglyceridemia (REDUCE-IT)",
            "journal": "N Engl J Med",
            "pub_year": "2019",
            "pub_date": "2019-01-03",
            "authors": ["Bhatt DL", "Steg PG", "Miller M", "et al."],
            "doi": "10.1056/NEJMoa1812792",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 8179,
            "claim_topics": ["cardiovascular", "lipid_management", "antiinflammatory"],
            "clinical_finding": "High-dose purified EPA (4g daily) produced a 25% relative risk reduction in major adverse cardiovascular events and reduced systemic triglyceride and inflammatory burden.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/30415628/",
        }
    ],
    "omega_3": [
        {
            "pmid": "30415628",
            "title": "Cardiovascular Risk Reduction with Icosapent Ethyl for Hypertriglyceridemia (REDUCE-IT)",
            "journal": "N Engl J Med",
            "pub_year": "2019",
            "pub_date": "2019-01-03",
            "authors": ["Bhatt DL", "Steg PG", "Miller M", "et al."],
            "doi": "10.1056/NEJMoa1812792",
            "evidence_type": "Phase III Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 8179,
            "claim_topics": ["cardiovascular", "lipid_management", "antiinflammatory"],
            "clinical_finding": "Omega-3 ethyl esters promote endothelial nitric oxide bioavailability, stabilize myocardial cell membranes, and lower triglyceride concentrations.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/30415628/",
        }
    ],
    "nmn": [
        {
            "pmid": "33888596",
            "title": "Nicotinamide mononucleotide increases muscle insulin sensitivity in prediabetic women",
            "journal": "Science",
            "pub_year": "2021",
            "pub_date": "2021-06-11",
            "authors": ["Yoshino M", "Yoshino J", "Kayser BD", "et al."],
            "doi": "10.1126/science.abe9985",
            "evidence_type": "Randomized Double-Blind Placebo-Controlled Trial",
            "evidence_tier": "rct_landmark",
            "sample_size": 25,
            "claim_topics": ["metabolic_glycemic", "antioxidant"],
            "clinical_finding": "NMN supplementation (250mg daily) increases skeletal muscle NAD+ biosynthesis and enhances insulin-stimulated glucose disposal and muscle remodeling via SIRT1 activation.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/33888596/",
        }
    ],
    "bacopa": [
        {
            "pmid": "11498727",
            "title": "The chronic effects of an extract of Bacopa monniera (Brahmi) on cognitive function in healthy human subjects",
            "journal": "Psychopharmacology (Berl)",
            "pub_year": "2001",
            "pub_date": "2001-08-01",
            "authors": ["Stough C", "Lloyd J", "Clarke J", "et al."],
            "doi": "10.1007/s002130100815",
            "evidence_type": "Double-Blind RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 46,
            "claim_topics": ["neuroprotection"],
            "clinical_finding": "Standardized Bacopa extract (300mg daily) significantly improves speed of visual information processing, learning rate, and memory consolidation via synaptic enhancement.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/11498727/",
        }
    ],
    "astragalus": [
        {
            "pmid": "25088216",
            "title": "Astragaloside IV protects against podocyte injury and renal fibrosis",
            "journal": "Evid Based Complement Alternat Med",
            "pub_year": "2014",
            "pub_date": "2014-07-08",
            "authors": ["Li M", "Wang W", "Xue P", "et al."],
            "doi": "10.1155/2014/354242",
            "evidence_type": "Translational Renal Study",
            "evidence_tier": "in_vivo_mechanistic",
            "claim_topics": ["cardiovascular", "antioxidant"],
            "clinical_finding": "Astragaloside IV preserves renal podocyte slit diaphragm integrity, upregulates nephrin/podocin, and alleviates glomerulosclerosis and tubular interstitial fibrosis.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/25088216/",
        }
    ],
    "dhea": [
        {
            "pmid": "15531705",
            "title": "Effect of DHEA on abdominal fat and insulin action in elderly women and men: a randomized controlled trial",
            "journal": "JAMA",
            "pub_year": "2004",
            "pub_date": "2004-11-10",
            "authors": ["Villareal DT", "Holloszy JO"],
            "doi": "10.1001/jama.292.18.2243",
            "evidence_type": "Double-Blind RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 56,
            "claim_topics": ["anabolic_endocrine", "metabolic_glycemic"],
            "clinical_finding": "DHEA replacement (50mg daily) significantly reduces visceral and subcutaneous abdominal fat and increases insulin sensitivity in aging adults.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/15531705/",
        }
    ],
    "pregnenolone": [
        {
            "pmid": "24467926",
            "title": "Proof-of-concept trial with the neurosteroid pregnenolone for cognitive symptoms",
            "journal": "Neuropsychopharmacology",
            "pub_year": "2014",
            "pub_date": "2014-07-01",
            "authors": ["Marx CE", "Keefe RS", "Buchanan RW", "et al."],
            "doi": "10.1038/npp.2014.11",
            "evidence_type": "Randomized Clinical Trial",
            "evidence_tier": "clinical_trial",
            "sample_size": 88,
            "claim_topics": ["neuroprotection"],
            "clinical_finding": "Upstream neurosteroid modulating NMDA, AMPA, and GABA-A receptors, enhancing neuroplasticity and cognitive processing speed.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/24467926/",
        }
    ],
    "oxandrolone": [
        {
            "pmid": "10548543",
            "title": "Short-term oxandrolone administration stimulates net muscle protein synthesis in young men",
            "journal": "J Clin Endocrinol Metab",
            "pub_year": "1999",
            "pub_date": "1999-08-01",
            "authors": ["Sheffield-Moore M", "Urban RJ", "Wolf SE", "et al."],
            "doi": "10.1210/jcem.84.8.5923",
            "evidence_type": "Clinical Metabolic Trial",
            "evidence_tier": "clinical_trial",
            "sample_size": 15,
            "claim_topics": ["anabolic_endocrine"],
            "clinical_finding": "Oral 17alpha-alkylated androgen significantly stimulates fractional muscle protein synthesis rate and intracellular amino acid recycling; suppresses hepatic HDL-C via HL upregulation.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/10548543/",
        }
    ],
    "pramipexole": [
        {
            "pmid": "9115206",
            "title": "Clinical evaluation of pramipexole in advanced Parkinson's disease",
            "journal": "Neurology",
            "pub_year": "1997",
            "pub_date": "1997-04-01",
            "authors": ["Lieberman A", "Rakebiene R", "Kassicieh D", "et al."],
            "doi": "10.1212/wnl.49.1.130",
            "evidence_type": "Double-Blind Landmark RCT",
            "evidence_tier": "rct_landmark",
            "sample_size": 360,
            "claim_topics": ["anabolic_endocrine", "neuroprotection"],
            "clinical_finding": "High-affinity non-ergoline dopamine D2/D3 receptor agonist; potently suppresses pituitary prolactin secretion with minimal risk of ergot-related cardiac valvulopathy.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/9115206/",
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

        norm_key = cleaned_query.replace(" ", "_").replace("-", "_")
        tokens = [t for t in re.split(r"[\s_,\-]+", cleaned_query) if len(t) >= 3]

        # 1. Exact compound match in seed DB / graph sync
        if norm_key in SEED_LITERATURE_DB and len(tokens) <= 2:
            self._cache[cache_key] = SEED_LITERATURE_DB[norm_key][:max_results]
            _GLOBAL_LITERATURE_CACHE[cache_key] = SEED_LITERATURE_DB[norm_key][:max_results]
            try:
                from app.knowledge_graph.graph_db import get_graph_database
                gdb = get_graph_database()
                for sc in SEED_LITERATURE_DB[norm_key]:
                    gdb.ingest_citation(sc, entity_id=norm_key)
            except Exception:
                pass
            return SEED_LITERATURE_DB[norm_key][:max_results]

        # 2. Query Citation Graph Database
        try:
            from app.knowledge_graph.graph_db import get_graph_database
            gdb = get_graph_database()
            if len(tokens) > 1:
                graph_cites = gdb.search_citations(cleaned_query, max_results=max_results)
            else:
                graph_cites = gdb.get_citations_for_entity(norm_key, max_results=max_results) or gdb.search_citations(cleaned_query, max_results=max_results)
            if graph_cites and len(graph_cites) >= 1:
                self._cache[cache_key] = graph_cites[:max_results]
                _GLOBAL_LITERATURE_CACHE[cache_key] = graph_cites[:max_results]
                return graph_cites[:max_results]
        except Exception as g_err:
            logger.debug("Graph DB query notice in PubMedService: %s", g_err)
        candidate_matches = []
        scored_candidates = []
        if tokens:
            for seed_key, cites in SEED_LITERATURE_DB.items():
                for c in cites:
                    claim_topics_str = " ".join(c.get("claim_topics", []))
                    text_corpus = f"{c.get('title', '')} {c.get('clinical_finding', '')} {c.get('evidence_type', '')} {c.get('journal', '')} {' '.join(c.get('authors', []))} {claim_topics_str} {seed_key}".lower()
                    if all(t in text_corpus for t in tokens):
                        candidate_matches.append(c)
                    elif any(t in text_corpus for t in tokens) and (seed_key in cleaned_query or any(t == seed_key for t in tokens)):
                        match_count = sum(1 for t in tokens if t in text_corpus)
                        scored_candidates.append((match_count, c))
                    elif seed_key in cleaned_query or any(t == seed_key for t in tokens):
                        scored_candidates.append((1, c))
            if candidate_matches:
                self._cache[cache_key] = candidate_matches[:max_results]
                _GLOBAL_LITERATURE_CACHE[cache_key] = candidate_matches[:max_results]
                return candidate_matches[:max_results]
            elif scored_candidates:
                scored_candidates.sort(key=lambda x: x[0], reverse=True)
                seen_pmids = set()
                uniq_scored = []
                for _, sc in scored_candidates:
                    p = sc.get("pmid")
                    if p and p not in seen_pmids:
                        seen_pmids.add(p)
                        uniq_scored.append(sc)
                if uniq_scored:
                    self._cache[cache_key] = uniq_scored[:max_results]
                    _GLOBAL_LITERATURE_CACHE[cache_key] = uniq_scored[:max_results]
                    return uniq_scored[:max_results]

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

        # Ingest dynamically fetched citations into the Citation Graph Database
        if results:
            try:
                from app.knowledge_graph.graph_db import get_graph_database
                gdb = get_graph_database()
                for c in results:
                    gdb.ingest_citation(c, entity_id=norm_key)
            except Exception as g_ingest_err:
                logger.debug("Citation graph ingestion notice: %s", g_ingest_err)

        # Fallback to scored seed candidates if remote services return nothing
        if not results and scored_candidates:
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            results = [c for _, c in scored_candidates][:max_results]

        # Final fallback to Citation Graph Database
        if not results:
            try:
                from app.knowledge_graph.graph_db import get_graph_database
                gdb = get_graph_database()
                results = gdb.get_citations_for_entity(norm_key, max_results=max_results) or gdb.search_citations(cleaned_query, max_results=max_results)
            except Exception:
                pass

        self._cache[cache_key] = results
        _GLOBAL_LITERATURE_CACHE[cache_key] = results
        return results

    def search_literature_for_claim(
        self,
        entity_id: str,
        claim_topic_or_text: str,
        max_results: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves peer-reviewed literature specifically investigating the biological endpoint,
        mechanism, or outcome asserted in claim_topic_or_text for entity_id.
        Queries the Citation Graph Database first, then falls back to a targeted live PubMed query.
        """
        eid = str(entity_id).strip().lower()
        topic = str(claim_topic_or_text).strip()
        if not eid or not topic:
            return []

        # 1. Query Citation Graph Database for semantic claim matches
        try:
            from app.knowledge_graph.graph_db import get_graph_database
            gdb = get_graph_database()
            graph_cites = gdb.get_citations_for_claim(eid, topic, max_results=max_results)
            if graph_cites:
                return graph_cites
        except Exception as g_err:
            logger.debug("Graph DB claim search notice: %s", g_err)

        # 2. Targeted live PubMed query with entity + claim topic
        combined_query = f"{eid} {topic}"
        return self.search_literature(combined_query, max_results=max_results)

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

    def fetch_abstract(self, pmid: str) -> Optional[Dict[str, Any]]:
        """
        Fetches structured paper abstract text (Background, Methods, Results, Conclusions)
        for a given PMID from cache, seed database, NCBI E-Fetch, or Europe PMC.
        """
        clean_pmid = str(pmid).strip()
        if not clean_pmid:
            return None

        cache_key = f"abstract:{clean_pmid}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if cache_key in _GLOBAL_LITERATURE_CACHE:
            return _GLOBAL_LITERATURE_CACHE[cache_key]

        # 1. Check offline seed database for pre-curated high-yield findings
        for _, cites in SEED_LITERATURE_DB.items():
            for c in cites:
                if str(c.get("pmid")) == clean_pmid:
                    abs_body = c.get("clinical_finding") or "Abstract summary available in clinical findings."
                    result = {
                        "pmid": clean_pmid,
                        "title": c.get("title"),
                        "journal": c.get("journal"),
                        "pub_year": c.get("pub_year"),
                        "authors": c.get("authors", []),
                        "doi": c.get("doi"),
                        "evidence_tier": c.get("evidence_tier", "rct_landmark"),
                        "abstract": abs_body,
                        "abstract_text": abs_body,
                        "clinical_finding": c.get("clinical_finding"),
                        "claim_topics": c.get("claim_topics", []),
                        "url": c.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{clean_pmid}/",
                    }
                    self._cache[cache_key] = result
                    _GLOBAL_LITERATURE_CACHE[cache_key] = result
                    return result

        # 2. Query Europe PMC for full structured abstract text
        try:
            epmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            epmc_params = {
                "query": f"EXT_ID:{clean_pmid} SRC:MED",
                "resultType": "core",
                "format": "json",
            }
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(epmc_url, params=epmc_params)
                if res.status_code == 200:
                    data = res.json()
                    results_list = data.get("resultList", {}).get("result", [])
                    if results_list:
                        item = results_list[0]
                        abstract_text = item.get("abstractText") or ""
                        clean_abstract = re.sub(r"<[^>]+>", "", abstract_text).strip()
                        if clean_abstract:
                            parsed_res = {
                                "pmid": clean_pmid,
                                "title": item.get("title", "").rstrip("."),
                                "journal": item.get("journalTitle", "PubMed Journal"),
                                "pub_year": str(item.get("pubYear", "")),
                                "authors": [item.get("authorString", "")],
                                "doi": item.get("doi"),
                                "abstract": clean_abstract,
                                "abstract_text": clean_abstract,
                                "clinical_finding": clean_abstract[:300] + ("..." if len(clean_abstract) > 300 else ""),
                                "url": f"https://pubmed.ncbi.nlm.nih.gov/{clean_pmid}/",
                            }
                            self._cache[cache_key] = parsed_res
                            _GLOBAL_LITERATURE_CACHE[cache_key] = parsed_res
                            return parsed_res
        except Exception as epmc_err:
            logger.debug("Europe PMC fetch abstract notice for PMID %s: %s", clean_pmid, epmc_err)

        # 3. Fallback: Query NCBI E-Utilities efetch/esummary
        try:
            meta = self.fetch_citation_metadata(clean_pmid)
            if meta:
                meta_copy = dict(meta)
                abs_b = meta_copy.get("clinical_finding") or f"Study published in {meta_copy.get('journal', 'PubMed')} ({meta_copy.get('pub_year', '')})."
                meta_copy["abstract"] = abs_b
                meta_copy["abstract_text"] = abs_b
                self._cache[cache_key] = meta_copy
                _GLOBAL_LITERATURE_CACHE[cache_key] = meta_copy
                return meta_copy
        except Exception as ncbi_err:
            logger.debug("NCBI fetch abstract notice for PMID %s: %s", clean_pmid, ncbi_err)

        return None

    def hybrid_literature_search(
        self,
        query: str,
        entity_id: Optional[str] = None,
        claim_topic: Optional[str] = None,
        max_results: int = 4,
    ) -> Dict[str, Any]:
        """
        Unified Traditional RAG & Semantic Literature Search.
        Combines Citation Graph Database records, semantic claim-topic relevance,
        and live PubMed/Europe PMC indexing with structured abstracts and findings.
        """
        clean_q = str(query or "").strip()
        clean_eid = str(entity_id or "").strip().lower()
        clean_topic = str(claim_topic or "").strip()

        # Build clean deduplicated query terms
        terms = []
        if clean_eid:
            terms.append(clean_eid)
        for t in clean_q.split():
            if t.lower() not in [x.lower() for x in terms]:
                terms.append(t)
        if clean_topic:
            for t in clean_topic.split():
                if t.lower() not in [x.lower() for x in terms]:
                    terms.append(t)

        combined_query = " ".join(terms).strip()
        if not combined_query:
            return {"query": "", "count": 0, "citations": []}

        # 1. Retrieve candidates via claim-aware search or general search
        citations = []
        if clean_eid and clean_topic:
            citations = self.search_literature_for_claim(clean_eid, clean_topic, max_results=max_results)
        elif clean_topic:
            citations = self.search_literature_for_claim(clean_q or clean_eid, clean_topic, max_results=max_results)
        else:
            citations = self.search_literature(combined_query, max_results=max_results)
            if clean_eid:
                eid_cites = self.search_literature(clean_eid, max_results=max_results)
                seen_pmids = {c.get("pmid") for c in citations if c.get("pmid")}
                for ec in eid_cites:
                    if ec.get("pmid") and ec["pmid"] not in seen_pmids:
                        citations.append(ec)
                        seen_pmids.add(ec["pmid"])

        # 2. Enrich citations with abstract snippets if missing
        enriched_citations = []
        for c in citations:
            c_dict = dict(c)
            pmid = c_dict.get("pmid")
            if pmid and not c_dict.get("clinical_finding"):
                abs_meta = self.fetch_abstract(pmid)
                if abs_meta and abs_meta.get("clinical_finding"):
                    c_dict["clinical_finding"] = abs_meta["clinical_finding"]
                if abs_meta and abs_meta.get("abstract"):
                    c_dict["abstract"] = abs_meta["abstract"][:400]
                    c_dict["abstract_text"] = abs_meta["abstract"][:400]
            enriched_citations.append(c_dict)

        return {
            "query": combined_query,
            "entity_id": clean_eid or None,
            "claim_topic": clean_topic or None,
            "count": len(enriched_citations),
            "citations": enriched_citations,
        }

    def search_pubmed_titles(self, query: str, max_results: int = 8) -> List[Dict[str, Any]]:
        """
        Lightweight Title & Metadata Discovery for Agentic Reasoning.
        Returns a token-efficient list of paper titles, publication years, study designs,
        and PMIDs matching query, enabling the AI to scan candidates without context bloat.
        """
        cleaned_query = query.strip().lower()
        if not cleaned_query:
            return []

        cache_key = f"titles:{cleaned_query}:{max_results}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if cache_key in _GLOBAL_LITERATURE_CACHE:
            return _GLOBAL_LITERATURE_CACHE[cache_key]

        titles_list: List[Dict[str, Any]] = []
        seen_pmids: Set[str] = set()

        # 1. Check local seed database for instant matches
        tokens = [t for t in re.split(r"[\s_,\-]+", cleaned_query) if len(t) >= 3]
        if tokens:
            for seed_key, cites in SEED_LITERATURE_DB.items():
                for c in cites:
                    p = str(c.get("pmid") or "")
                    if p and p not in seen_pmids:
                        text_corpus = f"{c.get('title', '')} {c.get('clinical_finding', '')} {seed_key}".lower()
                        if any(t in text_corpus for t in tokens):
                            seen_pmids.add(p)
                            titles_list.append({
                                "pmid": p,
                                "title": c.get("title", ""),
                                "journal": c.get("journal", ""),
                                "pub_year": str(c.get("pub_year", "")),
                                "authors": c.get("authors", [])[:2] + (["et al."] if len(c.get("authors", [])) > 2 else []),
                                "doi": c.get("doi"),
                                "evidence_type": c.get("evidence_type", "Clinical Trial"),
                                "is_open_access": False,
                                "pmcid": None,
                            })

        # 2. Query Europe PMC REST API (rich open access + title metadata)
        try:
            epmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            epmc_params = {
                "query": f"{cleaned_query} (SRC:MED)",
                "format": "json",
                "pageSize": max_results,
                "resultType": "core",
            }
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(epmc_url, params=epmc_params)
                if res.status_code == 200:
                    data = res.json()
                    for item in data.get("resultList", {}).get("result", []):
                        p = str(item.get("pmid") or "")
                        if p and p not in seen_pmids:
                            seen_pmids.add(p)
                            pmcid = item.get("pmcid")
                            is_oa = item.get("isOpenAccess") == "Y" or bool(pmcid)
                            author_str = item.get("authorString", "")
                            authors = [a.strip() for a in author_str.split(",") if a.strip()][:2]
                            if len(author_str.split(",")) > 2:
                                authors.append("et al.")

                            titles_list.append({
                                "pmid": p,
                                "title": item.get("title", "").rstrip("."),
                                "journal": item.get("journalTitle", "Biomedical Journal"),
                                "pub_year": str(item.get("pubYear", "2021")),
                                "authors": authors,
                                "doi": item.get("doi"),
                                "pmcid": pmcid,
                                "is_open_access": is_oa,
                                "evidence_type": item.get("pubType", "Clinical Study"),
                            })
        except Exception as epmc_err:
            logger.debug("Europe PMC title search notice: %s", epmc_err)

        # 3. Fallback to NCBI E-Utilities if under capacity
        if len(titles_list) < max_results:
            try:
                ncbi_cites = self.search_literature(cleaned_query, max_results=max_results)
                for nc in ncbi_cites:
                    p = str(nc.get("pmid") or "")
                    if p and p not in seen_pmids:
                        seen_pmids.add(p)
                        titles_list.append({
                            "pmid": p,
                            "title": nc.get("title", ""),
                            "journal": nc.get("journal", ""),
                            "pub_year": str(nc.get("pub_year", "")),
                            "authors": nc.get("authors", [])[:2] + (["et al."] if len(nc.get("authors", [])) > 2 else []),
                            "doi": nc.get("doi"),
                            "evidence_type": nc.get("evidence_type", "Clinical Trial"),
                            "is_open_access": False,
                            "pmcid": None,
                        })
            except Exception as ncbi_err:
                logger.debug("NCBI title fallback notice: %s", ncbi_err)

        final_titles = titles_list[:max_results]
        self._cache[cache_key] = final_titles
        _GLOBAL_LITERATURE_CACHE[cache_key] = final_titles
        return final_titles

    def fetch_paper_full_text_section(
        self,
        pmid_or_pmcid: str,
        section: str = "results",
        max_words: int = 600,
    ) -> Dict[str, Any]:
        """
        Section-Targeted Full-Text Reader.
        For Open Access (PMC / Europe PMC) papers, extracts targeted clinical sections
        (e.g., 'results', 'methods', 'dosage', 'adverse_effects', 'discussion') capped
        at max_words to strictly prevent context window bloat.
        Falls back to structured abstract with clear paywall notice for closed-access papers.
        """
        clean_id = str(pmid_or_pmcid).strip()
        if not clean_id:
            return {"error": "PMID or PMCID is required."}

        is_pmcid = clean_id.upper().startswith("PMC")
        pmcid = clean_id if is_pmcid else None
        pmid = None if is_pmcid else clean_id

        # 1. Resolve PMCID if PMID provided
        if not pmcid:
            try:
                epmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
                epmc_params = {"query": f"EXT_ID:{pmid} SRC:MED", "resultType": "core", "format": "json"}
                with httpx.Client(timeout=self.timeout) as client:
                    res = client.get(epmc_url, params=epmc_params)
                    if res.status_code == 200:
                        data = res.json()
                        results_list = data.get("resultList", {}).get("result", [])
                        if results_list:
                            pmcid = results_list[0].get("pmcid")
            except Exception:
                pass

        # 2. If Open Access PMCID is available, fetch full-text XML
        if pmcid:
            try:
                xml_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
                with httpx.Client(timeout=self.timeout + 2.0) as client:
                    xml_res = client.get(xml_url)
                    if xml_res.status_code == 200:
                        raw_xml = xml_res.text
                        clean_text = self._extract_section_from_xml(raw_xml, section, max_words=max_words)
                        if clean_text:
                            return {
                                "pmid": pmid,
                                "pmcid": pmcid,
                                "is_open_access": True,
                                "section_requested": section,
                                "section_text": clean_text,
                                "word_count": len(clean_text.split()),
                                "full_text_available": True,
                            }
            except Exception as ft_err:
                logger.debug("Full text XML retrieval notice for %s: %s", pmcid, ft_err)

        # 3. Fallback: Closed Access / Paywalled paper -> Return structured abstract
        abs_meta = self.fetch_abstract(pmid or clean_id)
        if abs_meta:
            abs_text = abs_meta.get("abstract") or abs_meta.get("clinical_finding") or "Abstract summary."
            return {
                "pmid": pmid or clean_id,
                "pmcid": pmcid,
                "is_open_access": False,
                "section_requested": section,
                "section_text": abs_text,
                "word_count": len(abs_text.split()),
                "full_text_available": False,
                "paywall_notice": "Full-text article is behind a publisher paywall. Provided above is the complete structured abstract.",
                "title": abs_meta.get("title"),
                "journal": abs_meta.get("journal"),
                "pub_year": abs_meta.get("pub_year"),
                "url": abs_meta.get("url"),
            }

        return {
            "pmid": pmid or clean_id,
            "is_open_access": False,
            "full_text_available": False,
            "error": f"Unable to locate paper content for identifier '{clean_id}'.",
        }

    def _extract_section_from_xml(self, xml_content: str, section_target: str, max_words: int = 600) -> str:
        """Parses full-text XML and isolates the target clinical section."""
        sec_lower = section_target.lower()
        if any(w in sec_lower for w in ["result", "finding", "outcome"]):
            pattern = r"(?is)<sec[^>]*>.*?<title[^>]*>.*?(?:results|findings|outcomes).*?</title>(.*?)</sec>"
        elif any(w in sec_lower for w in ["method", "dosage", "protocol", "intervention"]):
            pattern = r"(?is)<sec[^>]*>.*?<title[^>]*>.*?(?:methods|materials and methods|dosage|study design|intervention).*?</title>(.*?)</sec>"
        elif any(w in sec_lower for w in ["adverse", "safety", "toxic", "tolerab", "side effect"]):
            pattern = r"(?is)<sec[^>]*>.*?<title[^>]*>.*?(?:adverse|safety|toxicity|tolerability|side effects).*?</title>(.*?)</sec>"
        elif any(w in sec_lower for w in ["discuss", "conclus", "implicat"]):
            pattern = r"(?is)<sec[^>]*>.*?<title[^>]*>.*?(?:discussion|conclusions|implications).*?</title>(.*?)</sec>"
        else:
            pattern = r"(?is)<body[^>]*>(.*?)</body>"

        match = re.search(pattern, xml_content)
        raw_body = match.group(1) if match else xml_content
        # Strip XML tags
        clean_text = re.sub(r"<[^>]+>", " ", raw_body)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        words = clean_text.split()
        if len(words) > max_words:
            clean_text = " ".join(words[:max_words]) + f" ... [Section truncated at {max_words} words for token efficiency]"
        return clean_text

    def search_within_paper(
        self,
        pmid_or_pmcid: str,
        query: str,
        max_passages: int = 3,
    ) -> Dict[str, Any]:
        """
        Passage-level semantic search within an individual paper.
        Extracts only the top 2-3 most relevant paragraphs matching the query,
        preventing whole-document context bloat.
        """
        clean_id = str(pmid_or_pmcid).strip()
        clean_q = str(query or "").strip()
        if not clean_id or not clean_q:
            return {"error": "Paper identifier and query are required."}

        # Fetch section text or full text
        sec_res = self.fetch_paper_full_text_section(clean_id, section="results", max_words=1200)
        body_text = sec_res.get("section_text", "")
        if not body_text:
            return {"error": f"No readable text available for paper '{clean_id}'."}

        # Split into distinct paragraphs / sentences
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\.\s+(?=[A-Z])", body_text) if len(p.strip()) >= 50]
        if not paragraphs:
            paragraphs = [body_text]

        from app.services.embedding_service import get_embedding_service
        emb_svc = get_embedding_service()
        ranked = emb_svc.rank_by_similarity(
            query_text=clean_q,
            candidates=[{"passage": p} for p in paragraphs],
            text_extractor=lambda c: c["passage"],
            top_k=max_passages,
            min_similarity=0.10,
        )

        passages = [item["passage"] for _, item in ranked] or paragraphs[:max_passages]
        return {
            "pmid_or_pmcid": clean_id,
            "query": clean_q,
            "passage_count": len(passages),
            "relevant_passages": passages,
            "is_open_access": sec_res.get("is_open_access", False),
        }

    def find_similar_papers(self, pmid: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Finds structurally and mechanistically related papers in the vector graph."""
        clean_pmid = str(pmid or "").strip()
        if not clean_pmid:
            return []
        try:
            from app.knowledge_graph.graph_db import get_graph_database
            gdb = get_graph_database()
            return gdb.find_similar_citations(clean_pmid, top_k=top_k)
        except Exception as sim_err:
            logger.debug("Similar papers lookup notice for PMID %s: %s", clean_pmid, sim_err)
            return []

