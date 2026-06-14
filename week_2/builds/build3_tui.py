"""
Build 3: Extend Your Week 1 Chatbot into a TUI
===============================================
Take the multi-turn chatbot you built in Week 1 and give it a full-screen terminal UI
using Textual. The chat logic stays the same; you're just changing the interface.

Requirements:
  - A scrollable chat log that shows conversation history
  - An input box at the bottom for the user to type
  - Keyboard shortcuts:
      Ctrl+L  →  clear the chat display (not the conversation history)
      Ctrl+K  →  compact: clear conversation history too (fresh start)
      Ctrl+Q  →  quit the application
  - Messages displayed with clear role labels: [You] and [Agent]
  - The UI must not freeze while waiting for an API response

Stretch goals:
  - Show the model name and token count in the Header or Footer
  - Add a Ctrl+S binding to save the conversation to a text file
  - Display a "thinking..." indicator while the API call is in progress
"""

import os
import datetime
from openai import OpenAI
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Input, RichLog

load_dotenv()


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)

MODEL = "openrouter/free"
MAX_HISTORY_TURNS = 20   # keep last N user+assistant pairs



def call_model(messages: list[dict]) -> tuple[str, int]:
    """
    Send the full messages list to the model and return the assistant's reply text and tokens used.
    This is a blocking call. It must run in a worker thread in the TUI.
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )
    reply = response.choices[0].message.content or ""
    tokens = response.usage.total_tokens if response.usage else 0
    return reply, tokens


def trim_history(messages: list[dict], max_turns: int) -> list[dict]:
    """
    Keep the system message and only the last `max_turns` user/assistant pairs.

    messages[0] is assumed to be the system message.
    Drop oldest pairs from messages[1:] when over the limit.
    A 'pair' is one user message + one assistant message = 2 entries.
    """
    if len(messages) <= 1:
        return messages
    
    system_message = messages[0]
    history = messages[1:]
    
    # 1 turn = 1 user + 1 assistant message = 2 entries
    limit = max_turns * 2
    if len(history) > limit:
        history = history[-limit:]
        
    return [system_message] + history


# TUI Implementation

class ChatApp(App):
    """A full-screen terminal chatbot UI."""

    TITLE = "Week 2 Chatbot TUI"
    SUB_TITLE = f"Model: {MODEL} | Tokens: 0"
    
    CSS = """
    Screen {
        layout: vertical;
    }

    RichLog {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
        background: #1e1e1e;
    }

    Input {
        dock: bottom;
        height: 3;
    }
    """

    BINDINGS = [
        Binding("ctrl+l", "clear_display", "Clear display"),
        Binding("ctrl+k", "clear_history", "Clear history"),
        Binding("ctrl+s", "save_chat", "Save chat"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.messages: list[dict] = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        self.total_tokens = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="log", wrap=True, markup=True, highlight=True)
        yield Input(placeholder="Type a message and press Enter...")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write("[bold green]Chat started.[/bold green] Ctrl+Q to quit, Ctrl+L to clear display, Ctrl+K for fresh start, Ctrl+S to save.\n")
        self.query_one(Input).focus()


    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Called when the user presses Enter."""
        user_text = event.value.strip()
        if not user_text:
            return

        # Clear text input safely right away
        event.input.clear()

        log = self.query_one("#log", RichLog)
        log.write(f"[bold cyan][You][/bold cyan] {user_text}")

        # Append user message to history array and trim old context
        self.messages.append({"role": "user", "content": user_text})
        self.messages = trim_history(self.messages, MAX_HISTORY_TURNS)

        # Disable input field and update text placeholder
        event.input.disabled = True
        event.input.placeholder = "Thinking..."

        # Run the API call inside a background worker thread to keep interface responsive
        self.run_worker(lambda:self._get_response(event.input), thread=True)

    def _get_response(self, input_widget: Input) -> None:
        """
        Fetch the model response and update the UI securely.
        Runs synchronously inside a dedicated background thread worker.
        """
        log = self.query_one("#log", RichLog)
        
        # Display the thinking structural prompt line safely from the worker thread
        self.call_from_thread(log.write, "[dim]Agent is thinking...[/dim]")
        
        try:
            # Blocking network operation executing inside worker environment
            reply, tokens = call_model(self.messages)
            
            # Commit reply states to thread memory
            self.messages.append({"role": "assistant", "content": reply})
            self.total_tokens += tokens
            
            # Safely push visual subtitle and log mutations back onto the UI loop
            def update_ui_success():
                self.sub_title = f"Model: {MODEL} | Tokens: {self.total_tokens}"
                log.write(f"[bold magenta][Agent][/bold magenta] {reply}\n")
                
            self.call_from_thread(update_ui_success)

        except Exception as e:
            # Revert tracking arrays safely if something went wrong
            if self.messages and self.messages[-1]["role"] == "user":
                self.messages.pop()
            self.call_from_thread(log.write, f"[bold red]Error calling API: {str(e)}[/bold red]\n")
            
        finally:
            # Restore inputs control back to terminal screens safely
            def restore_input():
                input_widget.disabled = False
                input_widget.placeholder = "Type a message and press Enter..."
                input_widget.focus()
                
            self.call_from_thread(restore_input)



    def action_clear_display(self) -> None:
        """Clear the visible log layout window without wiping active API history contexts."""
        self.query_one("#log", RichLog).clear()

    def action_clear_history(self) -> None:
        """Reset operational structures completely for a brand new fresh chat start."""
        self.messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        self.total_tokens = 0
        self.sub_title = f"Model: {MODEL} | Tokens: 0"
        
        log = self.query_one("#log", RichLog)
        log.clear()
        log.write("[bold yellow]History cleared. Fresh session started.[/bold yellow]\n")

    def action_save_chat(self) -> None:
        """Save text files tracking exact conversation context traces."""
        log = self.query_one("#log", RichLog)
        try:
            filename = f"chat_history_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                for msg in self.messages:
                    role = msg["role"].upper()
                    content = msg["content"]
                    f.write(f"[{role}]: {content}\n\n")
            log.write(f"[bold green]Conversation saved successfully to {filename}[/bold green]\n")
        except Exception as e:
            log.write(f"[bold red]Failed to save conversation log: {str(e)}[/bold red]\n")


if __name__ == "__main__":
    ChatApp().run()