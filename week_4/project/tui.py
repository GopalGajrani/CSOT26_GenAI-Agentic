"""
TUIAgent — full-screen Textual UI inheriting from Agent.

Usage:
  python agent.py --tui

Tasks:
  1. class TUIAgent(App, Agent) — override _emit() for tool log panel
  2. class ResearchDeskApp(App) — layout, input, key bindings
  3. on_input_submitted -> worker -> self.chat() (inherited from Agent)
  4. Ctrl+L / Ctrl+K / Ctrl+Q from Week 2

Thread-safe approval bridge:
  - Background tool threads call ask_approval() from tools/approval.py
  - TUI registers a custom callback that:
      1. Displays the warning in the RichLog via call_from_thread()
      2. Blocks the background thread using threading.Event
      3. on_input_submitted() intercepts the next y/n answer,
         unblocks the thread and passes the result back.
"""

import sys
import threading
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, RichLog, Input
from textual import work

# Import your existing Agent logic! No need to rewrite anything.
from agent import Agent
from tools.exec import register_approval_callback


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
    #approval_label {
        dock: bottom;
        height: 1;
        background: $warning;
        color: $text;
        text-align: center;
        display: none;
    }
    """

    BINDINGS = [
        ("ctrl+l", "clear_display", "Clear Display"),
        ("ctrl+h", "clear_history", "Clear History"),
        ("ctrl+0", "quit_app", "Quit"),
    ]

    def __init__(self, session_id=None):
        # Initialize both parent classes!
        App.__init__(self)
        Agent.__init__(self, session_id=session_id)

        # --- Thread-safe approval bridge state ---
        # When truthy, the next user input is treated as a y/n answer.
        self._awaiting_approval: bool = False
        # The Event that blocks the background tool thread until user responds.
        self._approval_event: threading.Event = threading.Event()
        # The answer the main thread writes; the background thread reads.
        self._approval_result: bool = False

        # Register OUR callback so all tools route through us instead of input()
        register_approval_callback(self._tui_ask_approval)

    # ------------------------------------------------------------------
    # Approval bridge — called from background tool threads
    # ------------------------------------------------------------------
    def _tui_ask_approval(self, warning: str, prompt: str = "Approve?") -> bool:
        """
        Thread-safe replacement for input()-based approval.
        Called by tools in a background thread. Blocks until the user
        types 'y' or 'n' into the TUI's Input widget.
        """
        # Reset the event so we block correctly
        self._approval_event.clear()
        self._approval_result = False

        # Signal to on_input_submitted that the next message is a y/n answer
        self._awaiting_approval = True

        # Safely update the UI from this background thread
        self.call_from_thread(self._show_approval_prompt, warning, prompt)

        # Block this background thread until on_input_submitted() releases it
        self._approval_event.wait()

        return self._approval_result

    def _show_approval_prompt(self, warning: str, prompt: str) -> None:
        """Runs on the main Textual thread to update the RichLog."""
        log = self.query_one(RichLog)
        log.write(f"\n⚠️  [bold yellow]APPROVAL REQUIRED[/bold yellow]")
        log.write(warning)
        log.write(f"[bold]Type 'y' to approve or 'n' to reject:[/bold]")
        # Update input placeholder to make it obvious
        inp = self.query_one(Input)
        inp.placeholder = f"Type 'y' or 'n'..."

    def _restore_input_placeholder(self) -> None:
        """Restore the normal placeholder after approval is done."""
        inp = self.query_one(Input)
        inp.placeholder = "Ask the Research Desk... (or type /quit)"

    # ------------------------------------------------------------------
    # Textual lifecycle
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        yield RichLog(id="chat_log", wrap=True, highlight=True, markup=True)
        yield Input(placeholder="Ask the Research Desk... (or type /quit)", id="user_input")
        yield Footer()

    def on_mount(self) -> None:
        """Run when the app starts."""
        log = self.query_one(RichLog)
        log.write(f"Research Desk [{self.session_id}] started!")
        log.write("Type your research request below. Press 'ctrl+h' to clear history, 'ctrl+l' to clear display, or 'ctrl+0' to safely quit.")
        log.write("-" * 50)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when the user hits Enter in the Input box."""
        user_input = event.value.strip()
        if not user_input:
            return

        input_widget = self.query_one(Input)
        log = self.query_one(RichLog)

        # Clear the input box immediately
        input_widget.value = ""

        # ---------------------------------------------------------------
        # APPROVAL INTERCEPT: if a background thread is waiting for y/n,
        # handle it here on the main thread before doing anything else.
        # ---------------------------------------------------------------
        if self._awaiting_approval:
            choice = user_input.lower()
            if choice == 'y':
                log.write("[green]✓ Approved[/green]")
                self._approval_result = True
            elif choice == 'n':
                log.write("[red]✗ Rejected[/red]")
                self._approval_result = False
            else:
                log.write("[yellow]Please type 'y' or 'n'.[/yellow]")
                return  # Don't release the event, keep waiting

            # Restore normal placeholder and clear the flag
            self._awaiting_approval = False
            self.call_from_thread(self._restore_input_placeholder) if False else self._restore_input_placeholder()
            # Unblock the waiting background thread
            self._approval_event.set()
            return
        # ---------------------------------------------------------------

        # Check for quit commands
        if user_input in ("/quit", "/exit"):
            self.action_quit_app()
            return

        # Display the user's prompt in the log
        log.write(f"\n> {user_input}")

        # Fire off the worker thread to talk to the AI (prevents the UI from freezing!)
        self.process_chat(user_input)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_quit_app(self) -> None:
        """Triggered by the 'q' binding or typing /quit."""
        # Disable the input box so the user can't type while it saves
        self.query_one(Input).disabled = True
        self.process_quit()

    def action_clear_history(self) -> None:
        """Wipes the in-memory conversation history (starts fresh)."""
        self.messages = [self.messages[0]]  # keep only the system prompt!
        self.query_one(RichLog).write("[System] Conversation history cleared.")

    def action_clear_display(self) -> None:
        """Clears the visible chat log panel."""
        self.query_one(RichLog).clear()

    # ------------------------------------------------------------------
    # Workers (background threads)
    # ------------------------------------------------------------------
    @work(exclusive=True, thread=True)
    def process_chat(self, user_input: str) -> None:
        """Runs in a background thread to prevent UI freezing."""
        log = self.query_one(RichLog)

        # Override _emit so tool calls are logged to the TUI
        original_emit = self._emit

        def tui_emit(event: str, **data):
            if event == "tool_call":
                self.call_from_thread(log.write, f"  [tool] {data.get('name')}")

        self._emit = tui_emit

        try:
            answer = self.chat(user_input)
            self.call_from_thread(log.write, f"[Agent]: {answer}")
        except Exception as e:
            self.call_from_thread(log.write, f"[Error]: {str(e)}")
        finally:
            self._emit = original_emit

    @work(exclusive=True, thread=True)
    def process_quit(self) -> None:
        """Runs the final save hidden prompt before shutting down."""
        log = self.query_one(RichLog)
        self.call_from_thread(log.write, "\n[System] Asking agent to save final notes before exiting...")

        try:
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