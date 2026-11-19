# Nawras

A study buddy that runs on claude.ai: https://claude.ai/artifact/FRavbedDN3mMP6xoUvXzSd

Tell Nawras what you're learning, or drop in a PDF (or a .txt or .md file). Then
ask things like:

- "Hey Nawras, help me with this"
- "Hey Nawras, make me a study guide about this"
- "Hey Nawras, how do I add this to this?"
- "Hey Nawras, make me a quiz like that" (gives you a quiz you can click through)
- "Hey Nawras, help me teach this to someone else" (gives you a mini lesson plan)

How it works:

- It uses your own Claude account through the page, so you don't need an API key.
  The first time you ask something, Claude asks you to allow it.
- **Voice:** tap the mic, say "Hey Nawras, …", then tap the mic again to send.
  This works in Chrome-based browsers and the Claude desktop app. **Listen** on a
  reply reads it out loud.
- **Scanned PDFs** (no text inside) are sent as page images, up to 6 pages.
  They're only kept while the tab is open.
- **Continue in Claude** opens a new chat in the Claude app with Nawras set up
  for your topic. Attach your PDF again there.
- Your topics and chats are saved in your browser, so you can pick up where you
  left off.

`nawras.html` is the page source. To change it, edit the file and republish it
as an artifact with the `sample`, `dictation` and `tts` capabilities.
