import os
import shlex
import subprocess

# -----------------------------------------------------------------------
# Approval bridge — lives here so no extra file is needed.
# The TUI overrides _approval_callback via register_approval_callback().
# REPL uses the default which just calls print() + input().
# -----------------------------------------------------------------------
def _default_ask(warning: str, prompt: str) -> bool:
    print(warning)
    while True:
        try:
            choice = input(f"{prompt} [y/n]: ").strip().lower()
            if choice == 'y':
                return True
            elif choice == 'n':
                return False
            else:
                print("Please enter 'y' or 'n'.")
        except (EOFError, KeyboardInterrupt):
            return False

_approval_callback = _default_ask

def ask_approval(warning: str, prompt: str = "Approve?") -> bool:
    """Call whichever approval handler is currently registered."""
    return _approval_callback(warning, prompt)

def register_approval_callback(fn) -> None:
    """Override the approval handler. Called by TUIAgent at startup."""
    global _approval_callback
    _approval_callback = fn

# -----------------------------------------------------------------------

WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))
TIMEOUT_DEFAULT = 10
MAX_OUTPUT_CHARS = 8_000

# Known-safe: run immediately once the path check passes.
READ_ONLY_PREFIXES = (
    "grep", "find", "ls", "cat", "head", "tail", "wc",
    "git log", "git diff", "git status", "git blame", "git show",
    "pytest", "python -m pytest", "ruff", "flake8", "mypy",
)

# Known-destructive: always ask, even if they'd otherwise look harmless.
DESTRUCTIVE_PATTERNS = (
    "rm ", "mv ", ">", ">>", "git commit", "git push", "git checkout --",
    "pip install", "npm install", "curl ", "sudo ", "chmod ",
)

def paths_within_sandbox(command: str, workspace_root: str) -> bool:
    """
    Token-level check: no path-looking argument in `command` may resolve
    outside `workspace_root`.

    This is a heuristic, not a guarantee — see Lesson 1's caveat about
    pipes and command substitution. Still worth doing.
    """
    # TODO: shlex.split(command); for tokens that look like paths, resolve
    # them against workspace_root and reject if they escape it.
    try:
        args=shlex.split(command,comments=True,posix=True)
    except:
        return False
    
    abs_path=os.path.realpath(workspace_root)
    for token in args:
        if '/' in token or '//' in token or  token.startswith('.'):
            token_path=os.path.join(abs_path,token)
            resolved_tkn_path=os.path.abspath(token_path)
            if os.path.commonpath([resolved_tkn_path,abs_path])!=abs_path:
                return False
    return True 
    # _ = (command, workspace_root)
    # pass


def classify_command(command: str) -> str:
    """
    Return "read_only" if `command` matches a known-safe prefix and no
    destructive pattern, otherwise "ask".

    Default to "ask" for anything unclassified — see Lesson 1.
    """
    # TODO: implement
    try:
        args=shlex.split(command,comments=True)
    except:
        return "ask"
    
    if not args:
        return "ask"
        
    for p in DESTRUCTIVE_PATTERNS:
        if p in command:
            return "ask"
            
    is_safe = False
    
    # 1. Simple prefix match
    if args[0] in READ_ONLY_PREFIXES:
        is_safe = True
        
    # 2. Handle "git -C path log"
    if args[0] == "git":
        if "log" in args or "diff" in args or "status" in args or "show" in args or "blame" in args:
            is_safe = True
            
    # 3. Handle "python -m pytest"
    if args[0] == "python" and "-m" in args and "pytest" in args:
        is_safe = True
        
    if not is_safe:
        return "ask"
        
    for token in args:
        if ";" in token or "|" in token or ">" in token or "&" in token:
            return "ask"
            
    return "read_only"
    pass

def truncate(content):
    if len(content) >MAX_OUTPUT_CHARS:
        return(content[:MAX_OUTPUT_CHARS] + "\n .....[OUTPUT TRUNCATED......")
        
    else:
        return content
def was_truncate(content):
    if len(truncate(content))==len(content):
        return False
    return True 


def run_command(command: str, cwd: str = WORKSPACE_ROOT, timeout: int = TIMEOUT_DEFAULT) -> dict:
    """
    Run a shell command, sandboxed to `cwd`.

    Behavior:
      - reject immediately if paths_within_sandbox() fails
      - if classify_command() == "read_only": execute right away
      - otherwise: print the command + a clear warning, input() for y/n,
        and block (return {"error": ...}) if the human declines
      - always: capture stdout/stderr/exit_code, truncate long output,
        and enforce `timeout`
    """
    # TODO: implement using subprocess.run(..., shell=True, cwd=cwd,
    # timeout=timeout, capture_output=True, text=True)
    
    if not paths_within_sandbox(command,cwd):
        return ({"error":f"Security violation: Target directory '{cwd}' is outside the sandbox."})
    if classify_command(command) != "read_only":
        approved = ask_approval(
            warning=f"\n[Agent] wants to run a DESTRUCTIVE command:\n  $ {command}\nThis may modify files in your directory!",
            prompt="Approve this command?"
        )
        if not approved:
            return {"error": "Command rejected by user."}
    try:
        
        
        result=subprocess.run(command,capture_output=True,text=True,shell=True,cwd=cwd,timeout=timeout)

        output=truncate(result.stdout)
        error=result.stderr

        return{
            "stdout":truncate(output),
            "stderr":truncate(error),
            "exit_code":result.returncode,
            "is_truncated":was_truncate(output) and was_truncate(error)
        }

    except subprocess.CalledProcessError as e:
        return {"exit_code":e.returncode,"stderr":e.stderr}
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout} seconds."}
    except Exception as e:
        return {"error":f"and unexpected error occured : {e}"}

    # _ = (command, cwd, timeout)
    pass


EXEC_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command in the workspace and return its output. "
                "Use this to search (grep/find), inspect history (git log/diff), "
                "run tests, or make a change. Read-only commands run immediately. "
                "Anything that writes, deletes, or installs will pause and ask the "
                "human operator for approval — expect that pause, it's not a failure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": f"Seconds before the command is killed. Default {TIMEOUT_DEFAULT}.",
                    },
                },
                "required": ["command"],
            },
        },
    }
]

EXEC_REGISTRY={
    "run_command":run_command,
}