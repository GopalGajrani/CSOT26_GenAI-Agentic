"""
TUIAgent — full-screen Textual UI inheriting from Agent.

Usage:
  python agent.py --tui

Tasks:
  1. class TUIAgent(Agent) — override _emit() for tool log panel
  2. class ResearchDeskApp(App) — layout, input, key bindings
  3. on_input_submitted -> worker -> self.chat() (inherited from Agent)
  4. Ctrl+L / Ctrl+K / Ctrl+Q from Week 2
"""

import sys
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, RichLog, Input
from textual import work

# Import your existing Agent logic! No need to rewrite anything.
from agent import Agent

class TUIAgent(App, Agent):
    """A Textual User Interface for the Research Desk Agent."""

    CSS = """
    Input {
        dock: bottom;
        margin: 1;
    }
    RichLog {
        height: 1fr;
        border: solid green;
        margin: 1;
    }
    """

    BINDINGS = [
        ("ctrl+l", "clear_display", "Clear Display"),
        ("ctrl+k", "clear_history", "Clear History"),
        ("ctrl+q", "quit", "Quit"),
        
    ]
    def __init__(self, session_id=None):
        # Initialize both parent classes!
        App.__init__(self)
        Agent.__init__(self, session_id=session_id)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        yield RichLog(id="chat_log", wrap=True, highlight=True)
        yield Input(placeholder="Ask the Research Desk... (or type /quit)", id="user_input")
        yield Footer()

    def on_mount(self) -> None:
        """Run when the app starts."""
        log = self.query_one(RichLog)
        log.write(f"Research Desk [{self.session_id}] started!")
        log.write("Type your research request below. Press 'd' for dark mode, or 'q' to safely quit.")
        log.write("-" * 50)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when the user hits Enter in the Input box."""
        user_input = event.value.strip()
        if not user_input:
            return

        input_widget = self.query_one(Input)
        log = self.query_one(RichLog)

        # Clear the input box immediately so the user can type the next thing
        input_widget.value = ""

        # Check for quit commands
        if user_input in ("/quit", "/exit"):
            self.action_quit_app()
            return

        # Display the user's prompt in the log
        log.write(f"\n> {user_input}")
        
        # Fire off the worker thread to talk to the AI (prevents the UI from freezing!)
        self.process_chat(user_input)

    def action_quit_app(self) -> None:
        """Triggered by the 'q' binding or typing /quit."""
        # Disable the input box so the user can't type while it saves
        self.query_one(Input).disabled = True
        self.process_quit()

    @work(exclusive=True, thread=True)
    def process_chat(self, user_input: str) -> None:
        """Runs in a background thread to prevent UI freezing."""
        log = self.query_one(RichLog)

        # We override our own _emit function so we can catch tool calls
        # and print them to the Textual RichLog instead of the raw terminal!
        original_emit = self._emit

        def tui_emit(event: str, **data):
            if event == "tool_call":
                # call_from_thread safely updates the UI from this background thread
                self.call_from_thread(log.write, f"  [tool] {data.get('name')}")

        self._emit = tui_emit

        try:
            # We inherited this chat() function directly from Agent!
            answer = self.chat(user_input)
            self.call_from_thread(log.write, f"[Agent]: {answer}")
        except Exception as e:
            self.call_from_thread(log.write, f"[Error]: {str(e)}")
        finally:
            # Always restore the original emit function when done
            self._emit = original_emit

    @work(exclusive=True, thread=True)
    def process_quit(self) -> None:
        """Runs the final save hidden prompt before shutting down."""
        log = self.query_one(RichLog)
        self.call_from_thread(log.write, "\n[System] Asking agent to save final notes before exiting...")
        
        try:
            # The exact same hidden prompt we used in REPLAgent
            self.chat(
                "We are ending the session now. Please write a highly detailed bulleted summary "
                "covering EVERYTHING we discussed in this entire session. Use the write_file tool "
                "to save this comprehensive summary into the notes/ folder."
            )
            self.call_from_thread(log.write, "[System] Notes saved. Goodbye!")
        except Exception:
            pass
            
        # Finally, close the Textual app
        self.call_from_thread(self.exit)

if __name__ == "__main__":
    app = TUIAgent()
    app.run()