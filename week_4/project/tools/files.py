"""
Sandboxed file tools — see week_3/2_agent_class.md

Implement:
  - resolve_path
  - read_file(path, start_line=1, read_lines=200)  — numbered lines, has_more
  - write_file(path, content)
  - edit_file(path, operation, start_line, end_line?, content?)  — replace | delete | append
  - list_files(path, pattern)
"""

# TODO: implement — see Build 2

import os
import fnmatch
from tools.exec import ask_approval
script_location = os.path.dirname(os.path.abspath(__file__)) # .../week_3/project/tools
WORKSPACE_ROOT = os.path.dirname(script_location)     #week_3/project



def resolve_path(path: str) -> str:
    if path.startswith("project/"):
        path = path[len("project/"):]
    elif path.startswith("project\\"):
        path = path[len("project\\"):]
    fullpath=os.path.abspath(os.path.join(WORKSPACE_ROOT,path))
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
                "content":content,
                "has_more": (start_line + read_lines - 1) < len(content),
            }
        
        content_dict={
            "total_lines":len(content),
            "content":indexed_content[start_line-1:start_line+read_lines-1],
            "has_more": (start_line + read_lines - 1) < len(content),
        }

        return content_dict

    except Exception as e:
        return {"error":str(e)}

    # pass



def write_file(path: str, content: str) -> dict:
    try:
        is_path=resolve_path(path)


        if os.path.exists(is_path):
            #this because while saving notes if there already exists a file with same name so to differentiate the two
            base, ext = os.path.splitext(is_path)
            counter = 1
            while os.path.exists(f"{base} ({counter}){ext}"):
                counter += 1
            is_path = f"{base} ({counter}){ext}"
        
        print(f"\n[Agent] wants to create/write file: {is_path}")
        approved = ask_approval(
            warning=f"[Agent] wants to create/write file: {is_path}",
            prompt="Approve file creation?"
        )
        if not approved:
            return {"status": "rejected", "message": "The user rejected creating this file."}

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
    end_line: int=200,
    content: str | None = None,
) -> dict:
    try:
        # if_path=resolve_path(path)
        #readfile first before editing 
        # read_file already covers resolve_path
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
        new_lines = safe_content.splitlines(keepends=True)
        # for difference view
        before_lines = lines[start_idx:end_idx+1] if op != "append" else []

        if op=="insert":
            #inserting at start index
            lines.insert(start_idx,safe_content)
        elif op=="replace":
            lines[start_idx:end_idx+1]=new_lines
        elif op=="delete":
            del lines[start_idx:end_idx+1]
        elif op=="append":
            lines.extend(new_lines)
        else:
            return {"status":"error","message":f"unknown operation '{op}'. Use: replace, delete, append, insert"}
         

        # Build a simple diff preview to show what changed
        diff_lines = []
        for line in before_lines:
            diff_lines.append(f"- {line.rstrip()}")
        for line in new_lines:
            diff_lines.append(f"+ {line.rstrip()}")
        diff_preview = "\n".join(diff_lines) if diff_lines else "(no diff — append or delete)"

        # Pause and ask for human approval before applying the destructive edit
        approved = ask_approval(
            warning=f"[Agent] wants to '{op}' in {path} (lines {start_line}-{end_line}):\n{diff_preview}",
            prompt="Approve this edit?"
        )
        if not approved:
            return {"status": "rejected", "message": "The user rejected this file edit."}

        # write the changes in the original file 
        resolved = resolve_path(path)
        with open(resolved, "w") as f:
            f.writelines(lines)

        return {
            "status": "success",
            "message": f"'{op}' applied to lines {start_line}–{end_line}",
            "diff": diff_preview
        }

    except Exception as e:
        return {"error":str(e)}

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



FILE_SCHEMA= [
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
                        "enum": ["insert","replace","delete"]
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


FILE_REGISTRY={
    "read_file":read_file,
    "write_file":write_file,
    "edit_file":edit_file,
    "resolve_path":resolve_path,
    "list_files":list_files
}
