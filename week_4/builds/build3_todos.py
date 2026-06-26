"""
Build 3: Todo Tools
======================
A todo list the model maintains itself — what it's planning to do, what
it's actually done, and how it'll know each item really worked.

This build is intentionally less prescriptive than Builds 1 and 2. You
decide the exact shape of a todo and how the list is stored — in memory,
in a dict, in a JSON file under .agent/, however you like. The one hard
requirement, from Lesson 2: every todo needs a short title, a
description, and a verification method — some concrete, checkable way
to know the item is actually done ("run pytest tests/test_auth.py and
confirm exit code 0"), not just a status flag the model sets on its own
say-so.

Tasks (design these yourself — the signatures below are a starting
point, not a contract you have to match):
  1. add_todos(...)  — add one or more todos to the list
  2. get_todos(...)  — return the current list, however you choose to
     filter or shape it
  3. mark_todo(...)  — update a todo's status
  4. Once you've settled on a shape, write the TOOLS schema yourself
     and wire it into the agent loop's stop condition (Lesson 2) — the
     loop shouldn't consider itself done while a todo is incomplete.

Questions to resolve before you write code — there's no single right
answer, but you should be able to defend whatever you pick:
  - What does "status" need to express? pending/in_progress/completed
    is Lesson 2's minimum — is that enough once verification enters
    the picture, or do you need something like "blocked" too?
  - Should mark_todo require evidence (e.g. a command's exit code)
    before it'll accept "completed," and refuse otherwise? Lesson 2's
    "Completed Should Mean Verified, Not Just Claimed" argues yes —
    decide how strict to make that in code.
  - Where does the list live, and what survives a resumed session
    (Week 3)? A module-level list won't survive a process restart;
    is that good enough for this build, or do you need it on disk?
  - Should add_todos take one todo or a whole plan at once? (Lesson 2's
    todo_write always sends the full current list back — you don't
    have to copy that design, but know why it might matter.)

Run directly once you've implemented something real: add a couple of
todos, mark one in_progress, try to mark it completed without evidence
and see whether your own rules let that happen, then get_todos() and
confirm the list reflects what you'd expect.
"""

# TODO: pick your own storage. A plain list/dict at module scope is fine
# to start; revisit once you decide whether todos need to survive a
# resumed session.

# implement the following: add_todos, get_todos, mark_todo


# TODO: once the functions above have a settled shape, write the TOOLS
# schema for add_todos / get_todos / mark_todo yourself. Lesson 6 has
# the guidance on what makes a tool description the model actually
# follows — apply it here instead of copying Lesson 2's example verbatim.


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

if __name__ == "__main__":
    
    # TODO: exercise add_todos / get_todos / mark_todo once they're real,
    # including the case where you try to mark something completed
    # without evidence — does your code stop you, or let it through?
    if os.path.exists(TODO_FILE):
        os.remove(TODO_FILE)

    print("--- 1. Testing add_todos ---")
    add_todos([{
        "title": "Write unit tests",
        "description": "Write tests for the auth module",
        "verification": "run `pytest test_auth.py` and confirm 100% pass rate"
    }])
    print(get_todos('pending'))

    print("\n--- 2. Marking in_progress ---")
    print(mark_todo(1, "in_progress"))
    
    print("\n--- 3. Testing STRICT verification constraint (Should Fail) ---")
    try:
        mark_todo(1, "completed")
    except ValueError as e:
        print(f"EXPECTED ERROR CAUGHT: {e}")

    print("\n--- 4. Marking completed with evidence (Should Succeed) ---")
    print(mark_todo(1, "completed", evidence="Terminal output: 5 passed in 0.12s. Exit code 0."))
    
    print("\n--- 5. Final State ---")
    print(get_todos())

