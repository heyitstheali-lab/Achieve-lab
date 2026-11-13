"""Tkinter window: press the hotkey, get hints about the question on screen."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from typing import Callable, Iterator

import anthropic

from . import config, screen
from .coach import Coach, CoachSettings, friendly_error

MIN_REASON_CHARS = 15
HIDE_BEFORE_CAPTURE_MS = 300


def pretty_hotkey(hotkey: str) -> str:
    return "+".join(p.strip("<>").capitalize() for p in hotkey.split("+"))


class App:
    def __init__(self, root: tk.Tk, cfg: config.Config):
        self.root = root
        self.cfg = cfg
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.coach: Coach | None = None
        self.hotkey_listener = None

        root.title("Achieve Coach")
        root.geometry("460x640")
        root.minsize(360, 420)
        root.attributes("-topmost", cfg.always_on_top)

        self._build_ui()
        self._make_coach()
        self._start_hotkey()
        self.root.after(50, self._drain_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI ----------

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        self.hint_btn = ttk.Button(
            top,
            text=f"Get hint ({pretty_hotkey(self.cfg.hotkey)})",
            command=self.request_hint,
        )
        self.hint_btn.pack(side="left")
        ttk.Button(top, text="Settings", command=self.open_settings).pack(side="right")
        self.topmost_var = tk.BooleanVar(value=self.cfg.always_on_top)
        ttk.Checkbutton(
            top, text="On top", variable=self.topmost_var, command=self._toggle_topmost
        ).pack(side="right", padx=6)

        self.output = scrolledtext.ScrolledText(
            self.root, wrap="word", font=("Segoe UI", 11), state="disabled", height=20
        )
        self.output.pack(fill="both", expand=True, **pad)
        self._set_output(
            "Open a question in your reading assignment, then press "
            f"{pretty_hotkey(self.cfg.hotkey)} or click Get hint.\n\n"
            "I'll explain what the question is asking and where to find the "
            "evidence. You pick the answer, then type it below with your reason "
            "and I'll check your thinking."
        )

        ttk.Label(
            self.root,
            text="Your answer + why (or your written response, or a question):",
        ).pack(anchor="w", padx=8)
        self.input = tk.Text(self.root, height=4, wrap="word", font=("Segoe UI", 11))
        self.input.pack(fill="x", **pad)

        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", **pad)
        self.check_btn = ttk.Button(bottom, text="Check my thinking", command=self.check_thinking)
        self.check_btn.pack(side="left")
        self.ask_btn = ttk.Button(bottom, text="Ask a question", command=self.ask_question)
        self.ask_btn.pack(side="left", padx=6)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status, foreground="gray").pack(
            anchor="w", padx=8, pady=(0, 6)
        )

    def _set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("end", text)
        self.output.configure(state="disabled")

    def _append_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _set_busy(self, busy: bool, status: str) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for btn in (self.hint_btn, self.check_btn, self.ask_btn):
            btn.configure(state=state)
        self.status.set(status)

    def _toggle_topmost(self) -> None:
        self.cfg.always_on_top = self.topmost_var.get()
        self.root.attributes("-topmost", self.cfg.always_on_top)
        config.save(self.cfg)

    # ---------- Actions ----------

    def request_hint(self) -> None:
        if self.busy or not self._ensure_coach():
            return
        self._set_busy(True, "Taking screenshot...")
        # Hide our window so it isn't in the screenshot.
        self.root.withdraw()
        self.root.after(HIDE_BEFORE_CAPTURE_MS, self._capture_and_send)

    def _capture_and_send(self) -> None:
        try:
            png = screen.capture_png(self.cfg.monitor)
        except Exception as exc:  # screen capture can fail on some systems
            self._set_busy(False, "Screenshot failed")
            messagebox.showerror("Achieve Coach", f"Couldn't take a screenshot:\n{exc}")
            return
        finally:
            self.root.deiconify()
            self.root.attributes("-topmost", self.cfg.always_on_top)

        self._set_output("")
        self._run(lambda: self.coach.new_question(png), "Reading your screen...")

    def check_thinking(self) -> None:
        text = self.input.get("1.0", "end").strip()
        if not self._ready_for_followup(text):
            return
        if len(text) < MIN_REASON_CHARS:
            messagebox.showinfo(
                "Achieve Coach",
                "Add a reason! Type the answer you picked AND why you picked it, "
                'e.g. "B, because paragraph 3 says the town ran out of water."',
            )
            return
        self._send_followup(text, lambda: self.coach.check_thinking(text))

    def ask_question(self) -> None:
        text = self.input.get("1.0", "end").strip()
        if not self._ready_for_followup(text):
            return
        self._send_followup(text, lambda: self.coach.ask(text))

    def _ready_for_followup(self, text: str) -> bool:
        if self.busy or not self._ensure_coach():
            return False
        if not text:
            return False
        if not self.coach.has_question:
            messagebox.showinfo("Achieve Coach", "Get a hint on a question first.")
            return False
        return True

    def _send_followup(self, text: str, fn: Callable[[], Iterator[str]]) -> None:
        self.input.delete("1.0", "end")
        self._append_output(f"\n\n──────────\nYou: {text}\n\n")
        self._run(fn, "Thinking...")

    def _run(self, fn: Callable[[], Iterator[str]], status: str) -> None:
        """Run a streaming Claude call on a worker thread."""
        self._set_busy(True, status)

        def worker() -> None:
            try:
                for chunk in fn():
                    self.events.put(("text", chunk))
                self.events.put(("done", None))
            except Exception as exc:
                self.events.put(("error", friendly_error(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _drain_events(self) -> None:
        """Tkinter isn't thread-safe: apply worker results on the UI thread."""
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "text":
                    self._append_output(payload)
                elif kind == "done":
                    self._set_busy(False, "Ready")
                elif kind == "error":
                    self._append_output(f"\n\n⚠ {payload}")
                    self._set_busy(False, "Error")
                elif kind == "hotkey":
                    self.request_hint()
        except queue.Empty:
            pass
        self.root.after(50, self._drain_events)

    # ---------- Setup ----------

    def _make_coach(self) -> None:
        key = self.cfg.effective_api_key()
        if not key:
            self.coach = None
            return
        client = anthropic.Anthropic(api_key=key)
        self.coach = Coach(
            client=client,
            settings=CoachSettings(model=self.cfg.model, effort=self.cfg.effort),
        )

    def _ensure_coach(self) -> bool:
        if self.coach is None:
            self.open_settings(first_run=True)
        return self.coach is not None

    def open_settings(self, first_run: bool = False) -> None:
        prompt = "Paste your Claude API key (from console.anthropic.com):"
        if first_run:
            prompt = "You need a Claude API key first.\n\n" + prompt
        key = simpledialog.askstring(
            "Achieve Coach settings",
            prompt,
            initialvalue=self.cfg.api_key,
            show="•",
            parent=self.root,
        )
        if key is None:
            return
        self.cfg.api_key = key.strip()
        config.save(self.cfg)
        self._make_coach()
        self.status.set("API key saved" if self.coach else "No API key set")

    def _start_hotkey(self) -> None:
        try:
            from pynput import keyboard
        except Exception as exc:  # pynput can't load on some setups (e.g. Wayland)
            self.status.set(f"Hotkey unavailable ({exc.__class__.__name__}); use the button")
            return
        try:
            self.hotkey_listener = keyboard.GlobalHotKeys(
                {self.cfg.hotkey: lambda: self.events.put(("hotkey", None))}
            )
            self.hotkey_listener.start()
        except Exception as exc:
            self.status.set(f"Hotkey unavailable: {exc}; use the button")

    def _on_close(self) -> None:
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
        self.root.destroy()


def main() -> None:
    cfg = config.load()
    root = tk.Tk()
    try:
        ttk.Style(root).theme_use("clam")
    except tk.TclError:
        pass
    App(root, cfg)
    root.mainloop()


if __name__ == "__main__":
    main()
