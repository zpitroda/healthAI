import re

with open(r'l:\healthAI\app\knowledge_graph\graph_db.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace _graphrag_cache type
text = re.sub(
    r'_graphrag_cache: Dict\[Tuple\[Any, ...\], Dict\[str, Any\]\] = \{\}',
    r'_graphrag_cache: LRUCache = LRUCache(maxsize=1000)',
    text
)

# Add import
if 'from cachetools import LRUCache' not in text:
    text = text.replace('from neo4j import GraphDatabase, Driver', 'from neo4j import GraphDatabase, Driver\nfrom cachetools import LRUCache')

with open(r'l:\healthAI\app\knowledge_graph\graph_db.py', 'w', encoding='utf-8') as f:
    f.write(text)
