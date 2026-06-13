"""
ResearchBot: Week 2 Project Starter
======================================
This file currently makes a basic single-turn call to OpenRouter.
Your job is to evolve it into a full research agent with:
  - Web search and web fetch tools (using OpenAI SDK tool calling)
  - An agent loop that iterates until the model stops requesting tools
  - A Textual TUI with a chat panel and a tool activity log
  - Keyboard shortcuts: Ctrl+L (clear display), Ctrl+K (clear history), Ctrl+Q (quit),
    and at least one more of your choice

Start by getting this file working, then add tools, then add the TUI.
Don't try to build everything at once.
"""

import os
import asyncio
from openai import OpenAI
from dotenv import load_dotenv
import requests
from markdownify import markdownify
import trafilatura
import json
from mcp import ClientSession
from mcp.client.sse import sse_client

load_dotenv()

search_tool = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current information. Use this when the user asks "
            "about recent events, specific facts, or anything you are uncertain about. "
            "Returns a list of search results with titles, URLs, and snippets."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific and targeted.",
                }
            },
            "required": ["query"],
        },
    },
}

fetch_tool = {
    "type": "function",
    "function": {
        "name": "web_fetch",
        "description": (
            "Fetch and read the full content of a web page. Use this after web_search "
            "to read a specific result in detail. Prefer this for documentation, articles, "
            "and pages where the snippet is not enough."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to fetch, including https://",
                }
            },
            "required": ["url"],
        },
    },
}


SERPER_API_KEY = os.environ["SERPER_API_KEY"]

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

MODEL = "openrouter/free"




def web_fetch(url: str) -> str:
    """Fetch the content of a URL and return it as text."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return (f"Error fetching {url} :",e)

def fetch_clean(url: str) -> str:
    html = web_fetch(url)
    text = trafilatura.extract(html, include_comments=False, include_tables=True)
    return text or ""

    
MAX_CHARS = 8000

def fetch_for_agent(url: str) -> str:
    content = fetch_clean(url)
    if len(content) > MAX_CHARS:
        content = content[:MAX_CHARS] + "\n\n[...truncated]"
    return content

def smart_fetch(url: str) -> str:
    from urllib.parse import urlparse
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    try:
        resp = requests.get(f"{base}/llms.txt", timeout=5)
        if resp.status_code == 200:
            return f"[llms.txt found]\n\n{resp.text}\n\n---\nOriginal URL: {url}"
    except Exception:
        pass

    return fetch_for_agent(url)

def call_model(messages: list[dict], tools: list) -> any:
    """Send the messages history and tools list to OpenRouter."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
    )
    return response.choices[0].message



def web_search(query: str, num_results: int = 5) -> list[dict]:
    """Search the web. Returns a list of {title, link, snippet} dicts."""
    response = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num": num_results},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("organic", []):
        results.append({
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        })
    return json.dumps(results)



# 1. Notice the 'async' keyword addition here
async def run_agent(user_message: str, max_iterations: int = 15) -> str:
    """The agent loop: dynamically merges local web tools and remote AlphaXiv tools."""
    
    ALPHAXIV_MCP_URL = "https://api.alphaxiv.org/mcp/v1"
    
    # 2. Establish the SSE network transport connection
    async with sse_client(ALPHAXIV_MCP_URL) as (read, write):
        async with ClientSession(read, write) as alphaxiv_session:
            # Synchronize state with the remote server
            await alphaxiv_session.initialize()
            
            # 3. Dynamic Tool Discovery: Fetch available tools from AlphaXiv
            mcp_tools_data = await alphaxiv_session.list_tools()
            
            # 4. Construct the combined tool list schema for OpenRouter
            tools_list = [search_tool, fetch_tool]  # Your local definitions
            
            # Dynamically transform and append AlphaXiv tools into OpenAI formatting
            for mcp_tool in mcp_tools_data.tools:
                tools_list.append({
                    "type": "function",
                    "function": {
                        "name": mcp_tool.name,
                        "description": mcp_tool.description,
                        "parameters": mcp_tool.inputSchema,
                    }
                })

            # 5. Initialize the chat history array
            messages = [
                {
                    "role": "system", 
                    "content": (
                        "You are an expert research agent. Answer the user's question accurately. "
                        "Use the web_search tool to find broad internet information, smart_fetch to read standard pages, "
                        "and your AlphaXiv tools (discover_papers, get_paper_content) for formal academic research documents. "
                        "Always cite your sources and URLs."
                    )
                },
                {"role": "user", "content": user_message},
            ]
            
            print(f"\n[User Query]: {user_message}\n" + "="*50)
            
            # 6. Core execution loop
            for i in range(max_iterations):
                print(f"\n[Iteration {i+1}] Calling model...")
                
                # Execute your model call helper
                message = call_model(messages, tools_list)
                messages.append(message)
                
                if not message.tool_calls:
                    print("\n[Final Answer]:")
                    return message.content or ""
                
                # 7. Enhanced Dual-Type Routing Dispatcher
                for tool_call in message.tool_calls:    
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    print(f" -> Model requested tool: {name}({args})")
                    
                    # --- Route Branch A: Local Python Functions ---
                    if name == "web_search":
                        result = web_search(args.get("query", ""))
                    elif name == "web_fetch":
                        result = smart_fetch(args.get("url", ""))
                    
                    # --- Route Branch B: Remote AlphaXiv MCP Delegation ---
                    elif name in [t.name for t in mcp_tools_data.tools]:
                        print(f" -> Routing '{name}' to remote AlphaXiv MCP Server...")
                        # Await the execution over the open socket stream channel
                        mcp_result = await alphaxiv_session.call_tool(name, args)
                        result = mcp_result.content[0].text if mcp_result.content else ""
                    
                    else:
                        result = f"Error: Tool {name} not recognized."
                    
                    print(f" -> Tool execution completed (Result length: {len(result)} chars)")
                    
                    # Append the text content outcome back to the model history
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
                    
            return "Error: Reached maximum iterations without a final answer."



if __name__ == "__main__":
    # Target an academic or hybrid research query to test tool blending
    query = "Search for recent papers on low-rank adaptation methods and check their implementations."    

    # Run your updated async pipeline loop safely
    ans = asyncio.run(run_agent(query))
    print(ans)