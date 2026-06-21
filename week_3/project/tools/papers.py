"""
Paper search and read tools — Hugging Face Papers API (arXiv index).

Implement:
  - paper_search(query, limit) -> {papers: [{arxiv_id, title, abstract, url}, ...]}
  - read_paper(arxiv_id) -> {title, abstract, content, url, ...}

API docs: week_3/3_paper_tools.md
"""


# TODO: implement — see Build 2
import requests
import os
script_location = os.path.dirname(os.path.abspath(__file__)) # .../week_3/project/tools
WORKSPACE_ROOT = os.path.dirname(script_location)  #.../week_3/project
# WORKSPACE_ROOT = os.path.join(week_3_parent, "project")

env_file_path = os.path.join(WORKSPACE_ROOT, ".env")

from dotenv import load_dotenv

load_dotenv(dotenv_path=env_file_path)

my_token=os.environ.get("HF_TOKEN")
from tools.web import smart_fetch, web_search as _web_search

PAPER_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "paper_search",
            "description": (
                "Search for academic research papers on Hugging Face Daily Papers. "
                "Use this tool to find relevant papers, discover concepts, and obtain Arxiv IDs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search term topic or title fragments to look up (e.g., 'large language models')."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "The maximum number of paper results to return.",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_paper",
            "description": (
                "Fetch full details of a specific paper, including title, publication date, authors, "
                "and raw markdown document body content text using an Arxiv ID string."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "arxiv_id": {
                        "type": "string",
                        "description": "The structured Arxiv ID identifier extracted from search results (e.g., '2108.07732')."
                    }
                },
                "required": ["arxiv_id"]
            }
        }
    }
]

def search_paper(query:str,limit:int=5):
    url="https://huggingface.co/api/papers/search"
    query_params={
        "q":query,
        "limit":limit
    }
    
    headers={
    "Authorisation":f"Bearer {my_token}"
    }
    response=requests.get(url,params=query_params,headers=headers)

    if response.status_code==200:
        return response.json()
    else:
        # HuggingFace search failed — fall back to web_search on arXiv
        fallback_query = f"site:arxiv.org {query}"
        fallback_results = _web_search(fallback_query, num_results=5)
        return {"source": "web_search_fallback", "results": fallback_results}
# results = search_paper(query="large language models", limit=3)


# for idx, paper in enumerate(results, start=1):
#     print(f"\nResult {idx}:")
#     print(f"Title: {paper.get('title', 'Unknown Title')}")
#     print(f"Arxiv ID: {paper.get('paper',{}).get('id','NA')}")


def read_paper(arxiv_id:str):
    
    normalised_id=arxiv_id.split('/')[-1]
    # print(normalised_id)
    url=f"https://huggingface.co/api/papers/{normalised_id}"

    try:
        metadata=requests.get(url)
        metadata.raise_for_status()
        paper_content=metadata.json()
        title=paper_content.get('title','unkown')
        date=paper_content.get('publishedAt','unknown_date')
        # author=paper_content.get('author',"Unknown")
        # print(author)
        # print(paper_content)
        # Assuming your dictionary is stored in a variable named 'paper_data' 
        author_names = [author.get('name') for author in paper_content.get('authors', [])]

        # print(author_names)
    except Exception as e:
        title='unkown'
        date='unkown_date'
        author_names = []
    
    
    
    
    md_url=f"https://huggingface.co/papers/{normalised_id}.md"

    try:
        response=requests.get(md_url)
        
        response.raise_for_status()
        paper_content=response.text
        
        
    except Exception as e:
        arxiv_url = f"https://arxiv.org/abs/{normalised_id}"
        paper_content = smart_fetch(arxiv_url)
        if not paper_content:
            import json
            return json.dumps({
                "error": "404 and no fallback",
                "suggestion": f"Try specific arXiv URL {arxiv_url}"
            })
    MAX_CHARS = 12000
    if len(paper_content) > MAX_CHARS:
        paper_content = paper_content[:MAX_CHARS] + "\n\n[...truncated due to token limits]"
        
    author_str = '\n'.join(author_names)
    import json
    return json.dumps({
        "title": title,
        "date": date,
        "authors": author_str,
        "url": md_url,
        "content": paper_content
    })# text = read_paper("2108.07732")
# print(text)

PAPER_REGISTRY={
    "paper_search":search_paper,
    "read_paper":read_paper,
}

