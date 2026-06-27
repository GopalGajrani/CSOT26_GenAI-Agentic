"""
Research Desk — Week 3 Project
===============================
Class hierarchy:
  Agent       — brain: chat(), _run_loop(), dispatch(), sessions
  REPLAgent   — terminal REPL + one-shot CLI
  TUIAgent    — Textual UI (in tui.py)

Usage:
  python agent.py                              # REPLAgent.run()
  python agent.py "What is quantum computing?" # REPLAgent.run_once()
  python agent.py --tui                        # TUIAgent.run()
  python agent.py --session abc123 "continue"
"""

import os
import sys
import json
import glob as glob_module
import fnmatch
from openai import OpenAI
from dotenv import load_dotenv
from nanoid import generate
from datetime import datetime,timezone


script_location = os.path.dirname(os.path.abspath(__file__)) 
week_4_parent = os.path.dirname(script_location)      
WORKSPACE_ROOT = os.path.join(week_4_parent, "project")
MAX_ITERATIONS = 10
MAX_READ_CHARS = 12_000
env_file_path = os.path.join(WORKSPACE_ROOT, ".env")
load_dotenv(dotenv_path=env_file_path)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)
MODEL = "openrouter/free"


script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)


from tools.files import FILE_SCHEMA, FILE_REGISTRY
from tools.plan import PLAN_SCHEMA, PLAN_REGISTRY
from tools.exec import EXEC_SCHEMA, EXEC_REGISTRY
from tools.search import SEARCH_SCHEMA,SEARCH_REGISTRY

ALL_TOOLS_SCHEMA = FILE_SCHEMA + EXEC_SCHEMA + PLAN_SCHEMA +SEARCH_SCHEMA
ALL_TOOLS_REGISTRY = {**FILE_REGISTRY, **PLAN_REGISTRY, **SEARCH_REGISTRY,**EXEC_REGISTRY}




class Agent:
    def __init__(self, workspace: str = ".", session_id: str | None = None):
        self.workspace = WORKSPACE_ROOT   
        # TODO: session_id, load messages

        self.tool_registry = ALL_TOOLS_REGISTRY
        self.schema = ALL_TOOLS_SCHEMA

        self.session_id=session_id or generate(size=8)

        session_data=self.load_session(self.session_id)
        self.messages=session_data.get("messages",[])


        

        pass
    def save_session(self, title: str = "Untitled") -> None:
        """Write session JSON to .agent/sessions/{id}.json"""
        # Create the folder path safely inside your workspace root
        folder = os.path.join(self.workspace, ".agent", "sessions")
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, f"{self.session_id}.json")
        
        session_dict = {
            "id": self.session_id,
            "title": title,
            "updated_at": f"{datetime.now(timezone.utc)}",
            "messages": self.messages, 
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps(session_dict, indent=2))
        return None            
    # pass

    def load_session(self, session_id: str) -> dict:
        """Load and return session dict including messages list."""

        folder = os.path.join(self.workspace, ".agent", "sessions")
        filepath = os.path.join(folder, f"{session_id}.json")
        system_msg = {"role": "system", "content": build_system_prompt()}

        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    session_dict = json.load(f)

                msgs = session_dict.get("messages", [])
                # Always refresh system prompt — existing sessions may have a stale one
                if msgs and msgs[0].get("role") == "system":
                    msgs[0] = system_msg          # replace old system prompt
                else:
                    msgs.insert(0, system_msg)    # inject if missing entirely
                session_dict["messages"] = msgs
                return session_dict
            except Exception as e:
                return {"error": str(e), "messages": [system_msg]}

        # Fresh session — no file yet
        return {
            "id": session_id,
            "title": "Untitled",
            "messages": [system_msg],
        }
    def _generate_title(self) -> str:
        """Call the LLM to generate a short 3-5 word title based on the conversation."""
        prompt = "Please read the messages above and propose a very short, 3-5 word title for this conversation. Reply with ONLY the title and nothing else."
        temp_messages = self.messages + [{"role": "user", "content": prompt}]
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=temp_messages,
                max_tokens=20
            )
            title = response.choices[0].message.content.strip().strip('"\'')
            return title if title else "Untitled"
        except Exception:
            return "Untitled"

    def chat(self, user_message: str) -> str:
        self.messages.append({"role":"user","content":user_message})

        try:
            answer = self._run_loop()
            return answer
        finally:
            # Auto-title on the first real exchange
            if len(self.messages) >= 3:
                session_data = self.load_session(self.session_id)
                current_title = session_data.get("title", "Untitled")
                if current_title == "Untitled":
                    current_title = self._generate_title()
                self.save_session(title=current_title)
            else:
                self.save_session(title="Untitled")

    def run_once(self, prompt: str) -> str:
        return self.chat(prompt)

    def _run_loop(self) -> str:
        iterations = 0
        while iterations < MAX_ITERATIONS:
            iterations += 1
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=self.messages,
                    tools=self.schema,
                    tool_choice="auto"
                )
                
                if not response or not getattr(response, "choices", None):
                    return f"[AGENT ERROR]: The API returned an empty or invalid response. Please try again or check your API credits. Raw response: {response}"
                    
                response_message = response.choices[0].message
                
            except Exception as e:
                return f"[AGENT ERROR]: The OpenAI API call failed: {str(e)}"

            # Build the assistant message dict
            msg_dict = {
                "role": "assistant",
                "content": response_message.content or ""
            }

            if response_message.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in response_message.tool_calls
                ]

            self.messages.append(msg_dict)

            # If NO tool calls → model is done, return the final answer
            if not response_message.tool_calls:
                current_todos = ALL_TOOLS_REGISTRY['get_todos']()
                
                # FIX: use t['status'] instead of current_todos['status']
                incomplete = [t for t in current_todos if t.get('status') != 'completed']

                if len(incomplete) == 0:
                    return f'[AGENT] : {response_message.content}'
                else:
                    self.messages.append({
                        "role":"user",
                        "content":(
                            "SYSTEM WARNING: You tried to stop, but your todo list is not finished. "
                            "You must either complete the pending tasks, or mark them as 'blocked' if you cannot proceed."
                               
                        )
                    })
                    continue


            # Otherwise, dispatch each tool call
            for tc in response_message.tool_calls:
                # print(response_message.tool_calls)
                self._emit("tool_call", name=tc.function.name)
                result_str = self.dispatch(tc)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str
                })

        return "[Agent] Reached maximum iterations without a final answer."

    def dispatch(self, tool_call) -> str:
        # TODO: route to file tools, return JSON string
        
        name=tool_call.function.name
        try:
            
            args=json.loads(tool_call.function.arguments)
        except:
            return json.dumps({"error":f"invalid json arguments"})
        if name in self.tool_registry:
            try:
                result = self.tool_registry[name](**args)
                if isinstance(result, str):
                    if result.startswith("Error"):
                        return json.dumps({"tool_error": result})
                    return result
                return json.dumps(result)
            except Exception as e:
                return json.dumps({"tool_error": f"Tool execution crashed: {str(e)}"})
        else:
            return json.dumps({"tool_error": "no such tool found in tool_registry"})

    def _emit(self, event: str, **data) -> None:
        """Override in REPLAgent/TUIAgent for tool logging."""
        pass


class REPLAgent(Agent):
    """Terminal REPL + one-shot CLI."""

    def run(self) -> None:
        print(f"Research Desk [{self.session_id}] — /quit to exit")
        while True:
            try:
                user_input = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user_input or user_input in ("/quit", "/exit"):
                print("\n[System] Asking agent to save final notes before exiting...")
                self.chat("We are ending the session now. Please quickly summarize what we discussed and use your write_file tool to save it into the notes/ folder.")
                print("[System] Goodbye!")
                break
                
            if user_input == "/sessions":
                folder = os.path.join(self.workspace, ".agent", "sessions")
                if not os.path.exists(folder):
                    print("No sessions found.")
                else:
                    sessions = glob_module.glob(os.path.join(folder, "*.json"))
                    print(f"Found {len(sessions)} sessions:")
                    for s in sessions:
                        try:
                            with open(s, "r", encoding="utf-8") as f:
                                data = json.load(f)
                                print(f" - {data.get('id')}: {data.get('title')}")
                        except:
                            pass
                print()
                continue
                
            if user_input.startswith("/resume "):
                new_id = user_input.split(" ", 1)[1].strip()
                print(f"[System] Resuming session {new_id}...")
                session_data = self.load_session(new_id)
                self.session_id = new_id
                self.messages = session_data.get("messages", [])
                print("[System] Session restored.\n")
                continue

            print(self.chat(user_input))
            print()

    def _emit(self, event: str, **data) -> None:
        if event == "tool_call":
            print(f"  [tool] {data.get('name')}", file=sys.stderr)


def build_system_prompt() -> str:
    # First, try to load AGENTS.md from the target-repo project
    target_agents_path = os.path.join(WORKSPACE_ROOT, "target_repo", "AGENTS.md")
    if os.path.exists(target_agents_path):
        with open(target_agents_path, "r") as f:
            return f.read()
            
    # Fallback to the workspace root if not in target_repo
    agents_path = os.path.join(WORKSPACE_ROOT, "AGENTS.md")
    if os.path.exists(agents_path):
        with open(agents_path, "r") as f:
            return f.read()
            
    return (
        "You are an elite research file agent. Use your tools responsibly.\n"
        "Session files are stored as JSON at: .agent/sessions/<session_id>.json\n"
        "To read a session by ID, call read_file with path '.agent/sessions/<id>.json'.\n"
        "Always use list_files to discover files before reading them."
    )

def main():
    session_id = None
    tui_mode = False

    # Check if the user wants to run the Textual UI
    if "--tui" in sys.argv:
        tui_mode = True
        sys.argv.remove("--tui")

    # Support:  python agent.py --session <id>
    if "--session" in sys.argv:
        idx = sys.argv.index("--session")
        if idx + 1 < len(sys.argv):
            session_id = sys.argv[idx + 1]
            sys.argv = sys.argv[:idx] + sys.argv[idx + 2:]  # strip flag + value

    # If the user passed a one-shot prompt (e.g. python agent.py "hello")
    if len(sys.argv) > 1:                          
        agent = REPLAgent(session_id=session_id)
        print(agent.run_once(" ".join(sys.argv[1:])))
        return

    # Otherwise, launch either the TUI or the standard REPL terminal
    if tui_mode:
        from tui import TUIAgent
        app = TUIAgent(session_id=session_id)
        app.run()
    else:
        agent = REPLAgent(session_id=session_id)
        agent.run()


if __name__ == "__main__":
    main()
