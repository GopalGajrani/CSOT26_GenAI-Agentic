import os
import asyncio
import json
import webbrowser
import datetime
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
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Input, RichLog

load_dotenv()

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
        self.tokens = None
        self.client_info = None
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


class ResearchApp(App):
    """A clean, straightforward full-screen TUI for the Perplexity Research Agent."""

    TITLE = "Perplexity Engine TUI"
    SUB_TITLE = f"Active Model: {MODEL}"
    
    CSS = """
    Screen {
        layout: vertical;
    }

    RichLog {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
        background: #1a1a1a;
    }

    Input {
        dock: bottom;
        height: 3;
    }
    """

    
    BINDINGS = [
        Binding("ctrl+l", "clear_display", "Clear Display"),
        Binding("ctrl+k", "clear_history", "Clear History"),
        Binding("ctrl+s", "save_chat", "Save Chat"),
        Binding("ctrl+q", "quit", "Quit"),
        # Binding("ctrl+r","force_reauth","Re-authenticate")
    ]

    def __init__(self):
        super().__init__()
        # Store full session text logging strings for file dump support
        self.session_log = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="log", wrap=True, markup=True, highlight=True)
        yield Input(placeholder="Type a research query and press Enter...")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write("[bold green]Research Engine Initialized.[/bold green] Type your question below.")
        self.query_one(Input).focus()



    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Process input entries cleanly via native async workers."""
        query_text = event.value.strip()
        if not query_text:
            return

        event.input.clear()

        log = self.query_one("#log", RichLog)
        log.write(f"\n[bold cyan][You][/bold cyan] {query_text}")
        self.session_log.append(f"[You]: {query_text}")

        # Update input block visibility states
        event.input.disabled = True
        event.input.placeholder = "Searching web & analyzing sources..."

        # thread=False assigns this async routine to Textual's core event loop
        self.run_worker(self._async_agent_runner(query_text, event.input, log), thread=False)

    async def _async_agent_runner(self, query: str, input_widget: Input, log: RichLog) -> None:
        """Executes the complete core search loop asynchronously."""
        log.write("[dim]Agent is thinking & fetching tools...[/dim]")
        
        try:
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
                                    "The current year is 2026. Use this as your true baseline when answering questions about recent events or temporal facts. " 
                                    "Use web_search to find information, web_fetch to read standard pages, "
                                    "and your specific AlphaXiv tools (discover_papers, get_paper_content) for formal academic engineering and research documents. "
                                    "Always cite your sources, paper titles, and URLs explicitly."
                                )
                            },
                            {"role": "user", "content": query},
                        ]

                        final_answer = "Error: Reached maximum iterations without a final answer."
                        
                        
                        for i in range(10):
                            # Running synchronous completions executor safely inside async wrappers
                            message = await asyncio.to_thread(call_model, messages, tools_list)
                            messages.append(message)

                            if not message.tool_calls:
                                final_answer = message.content or ""
                                break

                            for tool_call in message.tool_calls:    
                                name = tool_call.function.name
                                args = json.loads(tool_call.function.arguments)
                                
                                log.write(f"[dim]Running tool call:[/] [yellow]{name}[/yellow]...")

                                if name == "web_search":
                                    result = await asyncio.to_thread(web_search, args.get("query", ""))
                                elif name == "web_fetch":
                                    result = await asyncio.to_thread(smart_fetch, args.get("url", ""))
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

                        # Output final resolved response to terminal viewport
                        log.write(f"[bold magenta][Agent][/bold magenta] {final_answer}\n")
                        self.session_log.append(f"[Agent]: {final_answer}")

        except Exception as e:
            log.write(f"[bold red]System Error encountered:[/] {str(e)}\n")
        finally:
            # Re-enable inputs
            input_widget.disabled = False
            input_widget.placeholder = "Type a research query and press Enter..."
            input_widget.focus()


    def action_clear_display(self) -> None:
        """Clear visible terminal screen rows."""
        self.query_one("#log", RichLog).clear()

    def action_clear_history(self) -> None:
        """Perform system session file state flush."""
        self.session_log.clear()
        log = self.query_one("#log", RichLog)
        log.clear()
        log.write("[bold yellow]Session context trace reset cleanly. New research instance ready.[/bold yellow]\n")

    def action_save_chat(self) -> None:
        """Save history arrays down to text documents safely."""
        log = self.query_one("#log", RichLog)
        if not self.session_log:
            log.write("[bold yellow]System:[/] No active message interactions to save yet.\n")
            return
        try:
            filename = f"research_history_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                for log_line in self.session_log:
                    f.write(f"{log_line}\n\n")
            log.write(f"[bold green]Research log saved successfully to {filename}[/bold green]\n")
        except Exception as e:
            log.write(f"[bold red]Failed to write text capture dump file:[/] {str(e)}\n")

if __name__ == "__main__":
    ResearchApp().run()