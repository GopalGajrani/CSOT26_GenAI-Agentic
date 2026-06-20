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


script_location = os.path.dirname(os.path.abspath(__file__)) # .../week_3/builds
week_3_parent = os.path.dirname(script_location)
WORKSPACE_ROOT = os.path.join(week_3_parent, "project")
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
from tools.papers import PAPER_SCHEMA, PAPER_REGISTRY
from tools.web import WEB_SCHEMA, WEB_REGISTRY


ALL_TOOLS_SCHEMA = FILE_SCHEMA + PAPER_SCHEMA + WEB_SCHEMA
ALL_TOOLS_REGISTRY = {**FILE_REGISTRY, **PAPER_REGISTRY, **WEB_REGISTRY}




class Agent:
    """Core agent: loop, tools, sessions. No UI."""

    def __init__(self, workspace: str = ".", session_id: str | None = None):
        self.workspace = WORKSPACE_ROOT   # always locked to week_3/project/
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
            return(f"Session saved successfully to .agent/sessions/{self.session_id}.json")            
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
    def chat(self, user_message: str) -> str:
        # TODO: append user msg, _run_loop(), save session, return answer
        self.messages.append({"role":"user","content":user_message})

        answer=self._run_loop()
        self.save_session(title=user_message[:5])
        return answer
        
        pass

    def run_once(self, prompt: str) -> str:
        return self.chat(prompt)

    def _run_loop(self) -> str:
        iterations = 0
        while iterations < MAX_ITERATIONS:
            iterations += 1
            response = client.chat.completions.create(
                model=MODEL,
                messages=self.messages,
                tools=self.schema,
                tool_choice="auto"
            )

            response_message = response.choices[0].message

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
                return response_message.content or "[Agent] Finished task"

            # Otherwise, dispatch each tool call
            for tc in response_message.tool_calls:
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
                result=self.tool_registry[name](**args)
                if isinstance(result, str):
                    return result
                
                return json.dumps(result)
            except:
                return json.dumps({"error":"tool execution failed"})
        else:
            return json.dumps("no such tool found in tool_Registry")
        # pass

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
                
                # Send a hidden prompt to force the agent to save notes
                self.chat("We are ending the session now. Please quickly summarize what we discussed and use your write_file tool to save it into the notes/ folder.")
                
                print("[System] Goodbye!")


                break
            print(self.chat(user_input))
            print()

    def _emit(self, event: str, **data) -> None:
        if event == "tool_call":
            print(f"  [tool] {data.get('name')}", file=sys.stderr)


def build_system_prompt() -> str:
    agents_path = os.path.join(WORKSPACE_ROOT, "AGENTS.md")
    try:
        with open(agents_path, "r") as f:
            return f.read()
    except FileNotFoundError:
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
