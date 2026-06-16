"""
Build 1: Session Store
========================
Save and resume conversations on disk. Load AGENTS.md into the system prompt.

Tasks:
  1. create_session() -> session_id
  2. save_session(session_id, messages, title?)
  3. load_session(session_id) -> {id, title, messages, ...}
  4. list_sessions() -> [{id, title, updated_at}, ...]
  5. build_system_prompt() -> base + AGENTS.md contents

Run twice: save a session in run 1, load it in run 2 and confirm messages restored.
"""

import json
import os
# import uuid
from nanoid import generate
from datetime import datetime, timezone

SESSIONS_DIR = ".agent/sessions"
AGENTS_PATHS = ("AGENTS.md", ".agent/AGENTS.md")

BASE_PROMPT = "You are Research Desk, a helpful research assistant."


def create_session() -> str:
    """Return a new 8-char hex session ID."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    # TODO: initiate a new, empty session with a unique ID
    session_id=generate(size=8)
    return session_id
    # pass


def save_session(session_id: str, messages: list, title: str = "Untitled") -> None:
    """Write session JSON to .agent/sessions/{id}.json"""
    # TODO: implement
    with open(f".agent/sessions/{session_id}.json","w") as f:
        session_dict={
            "id":session_id,
            "title":title,
            "updated_at":f"{datetime.now(timezone.utc)}",
            "messages":messages,
                       
        }
        f.write(json.dumps(session_dict))
    return(f"Session saved successfully to .agent/sessions/{session_id}.json")            
    # pass


def load_session(session_id: str) -> dict:

    """Load and return session dict including messages list."""
    # TODO: implement
    with open(f".agent/sessions/{session_id}.json","r") as f:
        session_dict=json.load(f)
    return session_dict
    pass


def list_sessions() -> list[dict]:
    """Return sessions sorted by updated_at descending."""
    session_list=[]
    for file in os.listdir(".agent/sessions"):
        file_path=os.path.join(".agent/sessions",file)
        with open(file_path,"r") as f:
            try:
                dict_file=(json.load(f))
                session_detail={
                    "id":dict_file["id"],
                    "title":dict_file['title'],
                    'updated_at':dict_file['updated_at'],
                }
                session_list.append(session_detail)
            except json.JSONDecodeError:
                pass
    session_list=sorted(session_list,key=lambda x:x["updated_at"],reverse=True)

    # TODO: implement
    return session_list
    # pass


def build_system_prompt() -> str:
    """Base prompt + AGENTS.md if it exists."""
    # TODO: implement
    for path in AGENTS_PATHS:
        if os.path.exists(path):
            with open(path,"r") as f:
                content=f.read()
            final_str=BASE_PROMPT+content
            return final_str
    
    return BASE_PROMPT
    # pass


if __name__ == "__main__":
    sid = create_session()
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": "What is a surface code?"},
        {"role": "assistant", "content": "A surface code is a type of quantum error correcting code."},
    ]
    save_session(sid, messages, title="Quantum error correction")
    print(f"Saved session: {sid}")
    print(f"All sessions: {list_sessions()}")
    print(f"Loaded: {load_session(sid)['title']}")
