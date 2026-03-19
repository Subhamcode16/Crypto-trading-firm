# 🧠 AI Development & Debugging Learnings

**Date Added:** March 15, 2026
**Context:** During the launch phase, the backend crashed repeatedly due to a cascading series of seemingly unrelated errors. These notes serve as strict development rules for future bot iterations to avoid getting stuck in loops.

---

## 1. PowerShell Encoding (`secrets.env` Corruption)
**The Mistake:**
Appending an API key using PowerShell's `echo "KEY=VAL" >> secrets.env` command.

**The Reality:**
PowerShell defaults to `UTF-16 LE` encoding for output redirection. This silently injects "null bytes" (`\x00`) between every character in the file. Python's `open()` and `python-dotenv` cannot parse this natively, causing a fatal `ValueError: embedded null character` exception during app startup.

**The Rule:**
- **NEVER** use `echo >>` in PowerShell to modify `.env` or configuration files.
- Always use Python scripts (`with open("secrets.env", "a", encoding="utf-8")`) to safely append to sensitive files, or manually edit them.

---

## 2. Telegram Bot Architecture (Async vs. Sync)
**The Mistake:**
Calling `self.bot.send_message(...)` synchronously inside the `python-telegram-bot` v20+ library.

**The Reality:**
Versions 20+ of the Telegram library are strictly `await`-based (`async def`). Calling an async method without `await` inside a standard synchronous thread (like our APScheduler jobs or Flask/FastAPI routes) results in a silent failure and triggers `RuntimeWarning: coroutine was never awaited`. The message is never sent.

**The Rule:**
- The backend trading loop is predominantly **synchronous**.
- To fire Telegram messages safely from synchronous code, wrap the call in a dedicated event loop runner:
  ```python
  def _run_async(self, coro):
      try:
          loop = asyncio.get_event_loop()
      except RuntimeError:
          loop = asyncio.new_event_loop()
          asyncio.set_event_loop(loop)
      if loop.is_running():
         # Thread-safe fallback implementation
         ...
      else:
          return loop.run_until_complete(coro)
  ```

---

## 3. Class Method Gaps vs. Usage
**The Mistake:**
Binding a job in `main.py` like `self.scheduler.add_custom_job(...)` without fully implementing the method in `scheduler.py`.

**The Reality:**
This causes an `AttributeError` during the very last stage of startup, causing the system to panic and gracefully shut down the bot. 

**The Rule:**
- **Always** grep the target class implementation before calling a "convenient" method name. Just because `add_researcher_job` exists doesn't mean `add_custom_job` inherently does.

---

## 4. Fundamental Imports in LLM Handlers
**The Mistake:**
Creating complex agent modules (`agent_7_risk_manager.py`, `ai_scorer.py`) but forgetting to import basic python packages (`import logging`, `import json`).

**The Reality:**
When `main.py` executes `from src.agents import ...`, Python reads the file top-to-bottom. If `logger = logging.getLogger(__name__)` executes before `import logging` is present, it throws a fatal `NameError` that crashes the entire application on boot.

**The Rule:**
- Standard library imports (`logging`, `json`, `dataclasses`, `typing`) must **always** be explicitly defined at the absolute top of every new class file. Avoid relying on global or implicitly inherited imports.

---

## 5. Anthropic & HTTPX Dependency Desync
**The Mistake:**
Running an out-of-date Anthropic SDK version alongside an incompatible `httpx` underlying library.

**The Reality:**
This creates an obscure standard library error like `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`. This happens because Anthropic's `_base_client.py` tries to pass `proxies=` to `httpx.Client`, which was deprecated/removed/renamed in the installed version of HTTPX.

**The Rule:**
- If the Anthropic SDK throws an obscure HTTP/networking error on initialization, **immediately** force-upgrade both packages together to restore equilibrium:
  `uv pip install -U anthropic httpx` (or `python -m pip install -U anthropic httpx`).
