"""
Build 2: Agent + REPLAgent
===========================
Agent = brain (loop, tools, sessions). REPLAgent = terminal UI.

Before running:
  mkdir -p notes

Tasks:
  1. Agent — chat(), run_once(), _run_loop(), dispatch(), _emit(), session I/O
  2. REPLAgent(Agent) — run() interactive loop
  3. resolve_path, read_file, write_file, list_files, edit_file
  4. main() — one-shot: python build2_agent_class.py "hello"

TUIAgent comes in the project (tui.py). No Textual imports here.
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


# --- File tools ---

def resolve_path(path: str) -> str:
    fullpath=os.path.join(WORKSPACE_ROOT,path)
    if not fullpath.startswith(WORKSPACE_ROOT):
        raise ValueError("Path escapes workspace")
    return fullpath      

    pass


def read_file(path: str, start_line: int = 1, read_lines: int = 200,original:bool=False) -> dict:
    try:
        if_path=resolve_path(path)
        with open(if_path,"r") as f :
            content=f.readlines()
        indexed_content=[]
        for i in range(len(content)):
            indexed_content.append(f"{i+1} : {content[i]}")
        
        
        if original :           #if we just want the content without indexing 
            return{
                "total_lines":len(content),
                "content":content
            }
        
        content_dict={
            "total_lines":len(content),
            "content":indexed_content[start_line-1:start_line+read_lines-1],
        }

        return content_dict

    except Exception as e:
        return {"error : ":str(e)}

    # pass



def write_file(path: str, content: str) -> dict:
    try:
        is_path=resolve_path(path)
        os.makedirs(os.path.dirname(is_path),exist_ok=True)
        with open(is_path,"w") as f:
            f.write(content)
        return {"status :":"success","message:":"Content written successfully "}
    except Exception as e:
        return {"error :":str(e)}
    
    # pass


def edit_file(
    path: str,
    operation: str,
    start_line: int,
    end_line: int | None = None,
    content: str | None = None,
) -> dict:
    try:
        # if_path=resolve_path(path)
        #readfile first before editing 
        file_read=read_file(path,start_line,end_line-start_line,True)
        if "error" in file_read:
            return {"status": "error", "message": file_read["error"]}
        
        lines=file_read['content']

        start_idx=start_line-1
        end_idx=end_line-1 if end_line is not None else start_idx

        if start_idx < 0 or end_idx > len(lines):
            return {"status": "error", "message": "either of start_line or end_line out of range "}

        safe_content=content if content is not None else ""
        if  not safe_content.endswith('\n'):
            safe_content+='\n'
        op=operation.lower().strip()
        if op=="insert":
            #inserting at start index
            lines.insert(start_idx,safe_content)
        elif op=="replace":
            lines[start_idx:end_idx+1]=safe_content
        elif op=="delete":
            del lines[start_idx:end_idx+1]
        else:
            return {"status":"error","message":f"currently i am not trained for {op} operation"}
        
        resolved = resolve_path(path)
        with open(resolved, "w") as f:
            f.writelines(lines)
        return {"status":"success","message":"edited file successfully"}

    except Exception as e:
        return {"error :":str(e)}

    # pass


def list_files(path: str = ".", pattern: str = "*") -> dict:
    try:
        target_path = resolve_path(path)
        matched = []
        # os.walk traverses ALL subdirectories including hidden ones (e.g. .agent/)
        # glob(**) silently skips hidden dirs, so we use os.walk + fnmatch instead
        for dirpath, dirnames, filenames in os.walk(target_path):
            for filename in filenames:
                if fnmatch.fnmatch(filename, pattern):
                    full_path = os.path.join(dirpath, filename)
                    matched.append(os.path.relpath(full_path, WORKSPACE_ROOT))
        return {"files": matched}
    except Exception as e:
        return {"error": str(e)}
    # pass



TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "resolve_path",
            "description": (
                            "checks if the given path is in the workspace root"
                            "proceed if and only if the path doesn't escapes workspace_root"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to check if in workspace_rootor not",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write content to a file on disk. Creates the file if it does not exist. "
                "Call this when the user asks you to save, write, or create a file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to write to, e.g. 'output.txt'",
                    },
                    "content": {
                        "type": "string",
                        "description": "The text content to write into the file",
                    },
                },
                "required": ["path", "content"],
            }
        }
    },

    {
        "type":"function",
        "function":{
            "name":"read_file",
            "description":(
                "Reads the lines of a file from a start line."
            ),
            "parameters":{
                "type":"object",
                "properties":{
                    "path":{
                        "type":"string",
                        "description":"the file path to read, "
                    },
                    "start_line":{
                        "type":"integer",
                        "description":"read the entire file and then add content in the return dict from this line",
                        "default":1,
                    },

                    "read_lines":{
                        "type":"integer",
                        "description":"add this many number of lines starting from start_line and add to return dict for key content",
                        "default":200
                    },

                    "original":{
                        "type":"boolean",
                        "description":"tell how do want you content to be, true tells the content to be written without line number prefix and false tells to write line number as a prefix",
                        "default":False,
                    },
                },
                "required":["path"]
            },
            
        },
    },
{
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files in a specified directory path that match a given glob pattern. "
                "Use this tool to discover existing notes, look up available files, or inspect "
                "the project directory structure before reading or editing files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "The relative directory path to search within. Defaults to '.' "
                            "representing the workspace root directory."
                        ),
                        "default": "."
                    },
                    "pattern": {
                        "type": "string",
                        "description": (
                            "A standard unix glob pattern string to filter files by name or extension "
                            "(e.g., '*' for all files, '*.json' for all the session history files,'*.md' for markdown notes, 'notes/*' for files inside a subfolder)."
                        ),
                        "default": "*"
                    }
                },
                "required": []
            },
        },
    },

{
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "edit or modify a specific line range within an existing file. "
                "Use this tool to update specific code segments, fix lines, or insert text notes "
                "without rewriting the entire file structure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative path of the file you want to edit."
                    },
                    "operation": {
                        "type": "string",
                        "description": "The type of edit action to perform. Currently supports: 'insert'.",
                        "enum": ["insert"]
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "The 1-indexed line number where the editing operation begins."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": (
                            "The 1-indexed line number where the operation ends. "
                            "If not provided, it defaults to None and infers bounds based on start_line."
                        ),
                        "default": None
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "The text string content to write into the file at the target line block. "
                            "A newline character '\\n' will automatically be appended if missing."
                        ),
                        "default": None
                    }
                },
                "required": ["path", "operation", "start_line"]  
            }
        }
    }
]  


tool_registry={
    "read_file":read_file,
    "write_file":write_file,
    "edit_file":edit_file,
    "resolve_path":resolve_path,
    "list_files":list_files
}


class Agent:
    """Core agent: loop, tools, sessions. No UI."""

    def __init__(self, workspace: str = ".", session_id: str | None = None):
        self.workspace = os.path.abspath(workspace)
        # TODO: session_id, load messages
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
            # 👉 FIX: Read directly from the class state memory array variable
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
        
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    session_dict = json.load(f)
                    return session_dict  
            except Exception as e:
                # Fallback dictionary if file reading fails
                return {"error": str(e), "messages": []}
        
        # If no file exists, return a fresh session structure dictionary
        return {
            "id": session_id,
            "title": "Untitled",
            "messages": [{"role": "system", "content": build_system_prompt()}]
        }   
    def chat(self, user_message: str) -> str:
        # TODO: append user msg, _run_loop(), save session, return answer
        self.messages.append({"role":"user","content":user_message})

        answer=self._run_loop()
        self.save_session(title=user_message[:10])
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
                tools=TOOLS,
                tool_choice="auto"
            )

            response_message = response.choices[0].message

            # Build the assistant message dict
            msg_dict = {
                "role": "assistant",
                "content": response_message.content
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
                return response_message.content or "[Agent] No response."

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
        if name in tool_registry:
            try:
                result=tool_registry[name](**args)
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
                break
            print(self.chat(user_input))
            print()

    def _emit(self, event: str, **data) -> None:
        if event == "tool_call":
            print(f"  [tool] {data.get('name')}", file=sys.stderr)


def build_system_prompt() -> str:
    return "You are an elite research file agent. Use your tools responsibly."
    pass


def main():
    agent = REPLAgent()
    if len(sys.argv) > 1:
        print(agent.run_once(" ".join(sys.argv[1:])))
        return
    agent.run()


if __name__ == "__main__":
    main()
