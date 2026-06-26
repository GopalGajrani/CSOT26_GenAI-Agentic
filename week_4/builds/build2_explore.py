"""
Build 2: Finding Code (grep + AST Outline)
=============================================
Two tools for finding the right place in a codebase you've never seen:
search file contents by pattern, and get a structural outline of a
single file without reading the whole thing.

Tasks:
  1. resolve_path(path) -> str | None
  2. grep(pattern, path=".", case_sensitive=False, max_results=50) -> dict
  3. list_definitions(path) -> dict   — AST-aware: list every function/class
     declared in a Python file, with line numbers
  4. Wire grep + list_definitions into TOOLS

Real-world reference for #3: Aider's repo map does this across an entire
multi-language repo using tree-sitter "tag" queries (see
https://aider.chat/2023/10/22/repomap.html and the implementation at
https://github.com/Aider-AI/aider/blob/main/aider/repomap.py), then ranks
files by reference count with PageRank. That's the bonus-tier "repo map"
challenge (see the README) — list_definitions here is the Python-only,
stdlib-`ast`-based version, scoped to one file at a time. See
https://docs.python.org/3/library/ast.html for the module reference;
every `ast.FunctionDef`/`ast.AsyncFunctionDef`/`ast.ClassDef` node carries
`.name`, `.lineno`, and `.end_lineno` once parsed.

Test this against a real external repo, not this file's own directory —
clone something like https://github.com/pallets/flask into ../target_repo
and point WORKSPACE_ROOT at it before running the demo below.

Run directly: grep for a common pattern, then outline the first match.
"""

import ast
import os
import re

WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))
MAX_GREP_RESULTS = 50
EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def resolve_path(path: str) -> str | None:
    """Resolve `path` inside WORKSPACE_ROOT; return None if it escapes."""
    # TODO: implement (same idea as Week 3's resolve_path)

    fullpath=os.path.abspath(os.path.join(WORKSPACE_ROOT,path))
    if os.path.commonpath([WORKSPACE_ROOT, fullpath]) != WORKSPACE_ROOT:
        return None 
    return fullpath    

def grep(
    pattern: str,
    path: str = ".",
    case_sensitive: bool = False,
    max_results: int = MAX_GREP_RESULTS,
) -> dict:
    """
    Search file contents for `pattern` under `path`.

    Return: {"matches": [{"file": ..., "line": ..., "text": ...}, ...],
             "truncated": bool, "total_matches": int}

    Skip EXCLUDE_DIRS and obviously binary files. Cap at `max_results`
    but report the true total even when truncated — see Lesson 1/3.
    """
   
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern '{pattern}': {e}")

    matches = []
    total_matches = 0

    files_to_search = []
    if os.path.isfile(path):
        files_to_search.append(path)
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                files_to_search.append(os.path.join(root, file))
    else:
        
        return {"matches": [], "truncated": False, "total_matches": 0}

    for filepath in files_to_search:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if regex.search(line):
                        total_matches += 1
                        if len(matches) < max_results:
                            matches.append({
                                "file": filepath,
                                "line": line_num,
                                "text": line.rstrip('\n') 
                            })
        except UnicodeDecodeError:
            pass
        except OSError:
            pass

    return {
        "matches": matches,
        "truncated": total_matches > max_results,
        "total_matches": total_matches
    }


def list_definitions(path: str) -> dict:
    """
    Parse a Python file with `ast` and return every function/class it
    declares, in source order, with line numbers — a structural outline
    without reading the file's full body.

    Return: {"definitions": [
                {"kind": "function" | "async function" | "class" | "method",
                 "name": ...,
                 "line": ...,        # ast node.lineno
                 "end_line": ...},   # ast node.end_lineno
                ...
             ]}
    or {"error": ...} on a path outside the sandbox, a missing file, or
    a SyntaxError from ast.parse (e.g. the file isn't valid Python).

    Walk ast.parse(source).body for top-level FunctionDef/AsyncFunctionDef/
    ClassDef; for each ClassDef, also walk its .body for methods (kind
    "method" instead of "function") so callers can see structure without
    a second tool call.
    """
    resolved_path = resolve_path(path)
    if resolved_path is None:
        return {"error": f"Path escapes the workspace sandbox: {path}"}

    try:
        with open(resolved_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except FileNotFoundError:
        return {"error": f"File not found: {path}"}
    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"error": f"SyntaxError: {e.msg} on line {e.lineno}"}

    definitions = []
    
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            definitions.append({
                "kind": "function",
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno)
            })
            
        elif isinstance(node, ast.AsyncFunctionDef):
            definitions.append({
                "kind": "async function",
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno)
            })
            
        elif isinstance(node, ast.ClassDef):
            definitions.append({
                "kind": "class",
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno)
            })
            
            for subnode in node.body:
                if isinstance(subnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    definitions.append({
                        "kind": "method",
                        "name": subnode.name,
                        "line": subnode.lineno,
                        "end_line": getattr(subnode, "end_lineno", subnode.lineno)
                    })

    return {"definitions": definitions}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": (
                "Search file contents for a pattern across the workspace. "
                "Use this before read_file when you don't already know which "
                "file you need."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Text or regex to search for."},
                    "path": {"type": "string", "description": "Subdirectory to search, default workspace root."},
                    "case_sensitive": {"type": "boolean", "description": "Default false."},
                    "max_results": {
                        "type": "integer",
                        "description": f"Cap on matches returned. Default {MAX_GREP_RESULTS}.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_definitions",
            "description": (
                "List the functions and classes declared in a Python file, "
                "with line numbers, without reading the whole file. Use this "
                "right after grep to decide which match is worth reading in "
                "full with read_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to a Python file."},
                },
                "required": ["path"],
            },
        },
    },
]


if __name__ == "__main__":
    print("Searching for top-level function definitions ('def '):")
    result = grep("def ", max_results=10)
    print(result)

    if result and result.get("matches"):
        first_file = result["matches"][0]["file"]
        print(f"\nOutline of {first_file}:")
        print(list_definitions(first_file))
