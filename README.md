# Achieve Lab

This repo has two study helpers:

- **Nawras** ([`nawras/`](nawras/)): tell it what you're learning or drop in a PDF,
  then ask it to teach you, make study guides and quizzes, or help you teach it.
  Runs on claude.ai: https://claude.ai/artifact/FRavbedDN3mMP6xoUvXzSd
- **Achieve Coach** (below): a desktop hint helper for reading assignments.

## Achieve Coach

A small desktop helper for reading assignments like Achieve3000. Press a hotkey
and it takes a screenshot of the question you're on. Claude then explains:

- **What it's asking**, in plain words
- **Where to look** in the article for the evidence
- **Tricky words** in the question or answer choices
- **A strategy** for that type of question

It **doesn't give you the answer**. After you pick one, type it in with your
reason and click **Check my thinking**. Claude tells you whether your reasoning
matches the text, or sends you back to the evidence. You can also paste in a
written response to get feedback on it, or ask a follow-up question about the
same screen.

## Setup

1. Install **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/).
   On Windows, tick "Add Python to PATH" during install. Tkinter comes with it.
   On Linux, also install your distro's Tk package (e.g. `sudo apt install python3-tk`).
2. Get a Claude API key at [console.anthropic.com](https://console.anthropic.com/).
   API use is billed per request. A hint costs a few cents at most.
3. Install and run:

   ```bash
   cd Achieve-lab
   python -m venv .venv
   # Windows:      .venv\Scripts\activate
   # macOS/Linux:  source .venv/bin/activate
   pip install -r requirements.txt
   python -m achieve_coach
   ```

4. The first time you click **Get hint**, it asks for your API key. The key is
   saved to `~/.achieve-coach/config.json`. If the `ANTHROPIC_API_KEY`
   environment variable is set, it's used instead.

## Using it

1. Open a question in your assignment.
2. Press **Ctrl+Shift+H**, or click **Get hint**. The coach window hides for a
   moment so it isn't in the screenshot.
3. Read the hints, reread the part of the article it points to, and pick your answer.
4. Type your answer **and why** (for example, *"B, because paragraph 3 says the
   town ran out of water"*), then click **Check my thinking**.

## Permissions

- **macOS:** System Settings → Privacy & Security. Allow your terminal (or
  Python) under **Screen Recording** for screenshots, and under
  **Accessibility** / **Input Monitoring** for the global hotkey.
- **Linux on Wayland:** global hotkeys and screenshots may be blocked. Use the
  **Get hint** button, or log into an X11 session.
- **Windows:** no extra setup.

## Settings

Edit `~/.achieve-coach/config.json`:

| Key | Default | What it does |
|---|---|---|
| `model` | `claude-opus-5-5` | Claude model to use. `claude-haiku-5-5` is much cheaper and faster. |
| `effort` | `medium` | How hard Claude thinks: `low`, `medium` or `high`. |
| `hotkey` | `<ctrl>+<shift>+h` | Global hotkey ([pynput format](https://pynput.readthedocs.io/en/latest/keyboard.html#global-hotkeys)). |
| `monitor` | `1` | Which screen to capture (1 = primary). |
| `always_on_top` | `true` | Keep the coach window above other windows. |

If Claude declines a request, it's automatically retried on a fallback model
(the API's server-side `fallbacks` option).

## Development

```bash
pip install pytest
python -m pytest tests
```

The tests use a fake Claude client, so they need no API key or network.
