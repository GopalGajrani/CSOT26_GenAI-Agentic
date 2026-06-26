import json
import os
from typing import List, Dict, Any

# 1. Storage Choice: JSON file for persistence across restarts
TODO_FILE = ".agent/todos.json"

def _load_todos() -> List[Dict[str, Any]]:
    """Helper to load the current todo list from disk."""
    if not os.path.exists(TODO_FILE):
        return []
    with open(TODO_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def _save_todos(todos: List[Dict[str, Any]]) -> None:
    """Helper to save the todo list to disk."""
    os.makedirs(os.path.dirname(TODO_FILE), exist_ok=True)
    with open(TODO_FILE, "w", encoding="utf-8") as f:
        json.dump(todos, f, indent=2)

def add_todos(todos: List[Dict[str, str]]) -> str:
    """
    Add one or more new todos to the list.
    """
    current_todos = _load_todos()
    
    for item in todos:
        if "title" not in item or "description" not in item or "verification" not in item:
            raise ValueError("Each todo must have a 'title', 'description', and 'verification' method.")
        
        new_todo = {
            "id": len(current_todos) + 1,
            "title": item["title"],
            "description": item["description"],
            "verification": item["verification"],
            "status": "pending",
            "evidence": None
        }
        current_todos.append(new_todo)
        
    _save_todos(current_todos)
    return f"Successfully added {len(todos)} todos."

def get_todos(status_filter: str = None) -> List[Dict[str, Any]]:
    """
    Return the current list of todos.
    """
    todos = _load_todos()
    if status_filter:
        todos = [t for t in todos if t["status"] == status_filter]
    return todos

def mark_todo(todo_id: int, status: str, evidence: str = None) -> str:
    """
    Update a todo's status. 
    Strict requirement: 'completed' status requires concrete 'evidence'.
    """
    valid_statuses = {"pending", "in_progress", "blocked", "completed"}
    if status not in valid_statuses:
        raise ValueError(f"Status must be one of: {valid_statuses}")

    if status == "completed" and not evidence:
        raise ValueError(
            "STRICT ENFORCEMENT: You cannot mark a task 'completed' without providing "
            "'evidence' of your verification method passing."
        )

    todos = _load_todos()
    for todo in todos:
        if todo["id"] == todo_id:
            todo["status"] = status
            if evidence:
                todo["evidence"] = evidence
            _save_todos(todos)
            return f"Todo {todo_id} marked as {status}."
            
    raise ValueError(f"Todo with id {todo_id} not found.")

# 4. Write the TOOLS schema for the LLM
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_todos",
            "description": "Add new tasks to your execution plan. Use this when you determine a new step is required. You must define exactly how you will verify the step is completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Short name for the task (e.g. 'Setup database')"},
                                "description": {"type": "string", "description": "Detailed explanation of what needs to be done"},
                                "verification": {"type": "string", "description": "A concrete, checkable way to know this is done (e.g. 'Run pytest tests/test_db.py and get exit code 0')"}
                            },
                            "required": ["title", "description", "verification"]
                        }
                    }
                },
                "required": ["todos"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_todos",
            "description": "Retrieve the current todo list to check your progress or review the plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string", 
                        "description": "Optional. Filter by 'pending', 'in_progress', 'blocked', or 'completed'."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mark_todo",
            "description": "Update the status of a specific task. To mark a task as 'completed', you MUST provide the 'evidence' parameter proving it is done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "todo_id": {"type": "integer", "description": "The ID of the task to update"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "blocked", "completed"]},
                    "evidence": {"type": "string", "description": "Required if status is 'completed'. Paste the terminal output, test results, or specific proof that the verification method passed."}
                },
                "required": ["todo_id", "status"]
            }
        }
    }
]
