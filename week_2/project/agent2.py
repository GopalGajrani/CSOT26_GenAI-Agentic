import os
import asyncio
import json
import webbrowser
import sys
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import trafilatura
import httpx
from openai import OpenAI
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

load_dotenv()

# Global Configurations
ALPHAXIV_MCP_URL = "https://api.alphaxiv.org/mcp/v1"
REDIRECT_URI = "http://localhost:8765/callback"
TOKEN_FILE = ".alphaxiv_tokens.json"

SERPER_API_KEY = os.environ["SERPER_API_KEY"]

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

MODEL = "openrouter/free"


search_tool = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current information. Use this when the user asks "
            "about recent events, specific facts, or general broad internet topics. "
            "Returns a list of search results with titles, URLs, and snippets."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The specific search query.",
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
            "Fetch and read the full content of a standard web page. Use this after web_search "
            "to read a specific documentation page, article, or general website layout in detail."
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


class FileTokenStorage(TokenStorage):
    def __init__(self):
        self.tokens: OAuthToken | None = None
        self.client_info: OAuthClientInformationFull | None = None
        if os.path.exists(TOKEN_FILE):
            try:
                data = json.loads(open(TOKEN_FILE).read())
                if data.get("tokens"):
                    self.tokens = OAuthToken(**data["tokens"])
                if data.get("client_info"):
                    self.client_info = OAuthClientInformationFull(**data["client_info"])
            except Exception:
                pass

    def _save(self):
        data = {}
        if self.tokens:
            data["tokens"] = self.tokens.model_dump(mode="json")
        if self.client_info:
            data["client_info"] = self.client_info.model_dump(mode="json")
        open(TOKEN_FILE, "w").write(json.dumps(data, indent=2))

    async def get_tokens(self) -> OAuthToken | None:
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self.tokens = tokens
        self._save()

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self.client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self.client_info = client_info
        self._save()

async def open_browser(auth_url: str) -> None:
    print(f"Opening browser for login...\nIf it doesn't open: {auth_url}\n")
    webbrowser.open(auth_url)

async def wait_for_callback() -> tuple[str, str | None]:
    code = state = None
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal code, state
            params = parse_qs(urlparse(self.path).query)
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorized. You can close this tab.</h1>")
        def log_message(self, *args):
            pass 

    print(f"Waiting for callback on {REDIRECT_URI} ...")
    server = HTTPServer(("localhost", 8765), Handler)
    server.timeout = 120
    server.handle_request()
    server.server_close()

    if not code:
        raise RuntimeError("OAuth callback received no authorization code.")
    return code, state


def web_fetch(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"

def fetch_clean(url: str) -> str:
    html = web_fetch(url)
    if html.startswith("Error"):
        return html
    text = trafilatura.extract(html, include_comments=False, include_tables=True)
    return text or ""

MAX_CHARS = 8000

def fetch_for_agent(url: str) -> str:
    content = fetch_clean(url)
    if len(content) > MAX_CHARS:
        content = content[:MAX_CHARS] + "\n\n[...truncated due to token limits]"
    return content

def smart_fetch(url: str) -> str:
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    try:
        resp = requests.get(f"{base}/llms.txt", timeout=5)
        if resp.status_code == 200:
            return f"[llms.txt found]\n\n{resp.text}\n\n---\nOriginal URL: {url}"
    except Exception:
        pass
    return fetch_for_agent(url)

def web_search(query: str, num_results: int = 5) -> str:
    try:
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
    except Exception as e:
        return f"Error executing web search: {str(e)}"

def call_model(messages: list[dict], tools: list) -> any:
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
    )
    return response.choices[0].message



async def run_agent(user_message: str, max_iterations: int = 10) -> str:
    storage = FileTokenStorage()
    
    auth = OAuthClientProvider(
        server_url=ALPHAXIV_MCP_URL,
        client_metadata=OAuthClientMetadata(
            client_name="AlphaXiv Search CLI",
            redirect_uris=[REDIRECT_URI],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="read",
        ),
        storage=storage,
        redirect_handler=open_browser,
        callback_handler=wait_for_callback,
    )

    async with httpx.AsyncClient(auth=auth, follow_redirects=True, timeout=60) as http:
        async with streamable_http_client(ALPHAXIV_MCP_URL, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as alphaxiv_session:
                await alphaxiv_session.initialize()

       
                mcp_tools_data = await alphaxiv_session.list_tools()

                tools_list = [search_tool, fetch_tool]
                for mcp_tool in mcp_tools_data.tools:
                    tools_list.append({
                        "type": "function",
                        "function": {
                            "name": mcp_tool.name,
                            "description": mcp_tool.description,
                            "parameters": mcp_tool.inputSchema,
                        },
                    })

                messages = [
                    {
                        "role": "system", 
                        "content": (
                            "You are an expert research agent. Answer the user's question accurately. "
                            "Use web_search to find information, web_fetch to read standard pages, "
                            "and your specific AlphaXiv tools (discover_papers, get_paper_content) for formal academic engineering and research documents. "
                            "Always cite your sources, paper titles, and URLs explicitly."
                        )
                    },
                    {"role": "user", "content": user_message},
                ]

                for i in range(max_iterations):
                    message = call_model(messages, tools_list)
                    messages.append(message)

                    if not message.tool_calls:
                        return message.content or ""

                    for tool_call in message.tool_calls:    
                        name = tool_call.function.name
                        args = json.loads(tool_call.function.arguments)
                        
                        
                        if name == "web_search":
                            result = web_search(args.get("query", ""))
                        elif name == "web_fetch":
                            result = smart_fetch(args.get("url", ""))
                        
                        elif name in [t.name for t in mcp_tools_data.tools]:
                            mcp_result = await alphaxiv_session.call_tool(name, args)
                            result = mcp_result.content[0].text if mcp_result.content else ""
                        else:
                            result = f"Error: Tool {name} not found."
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result
                        })

                return "Error: Reached maximum iterations without a final answer."

if __name__ == "__main__":

    query = "Tell me in detail about what Neuro Evolution Algorithm is and what are its real use case ."    
    ans = asyncio.run(run_agent(query))
    print(ans)