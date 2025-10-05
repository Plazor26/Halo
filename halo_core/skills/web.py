import os
import json
import asyncio
from typing import Union, List
import importlib
from pathlib import Path

# ───────────────────────────────────────────────────────────
# Utility: lazy import by dotted path with nice error traces
# ───────────────────────────────────────────────────────────
def _load_symbol(pathspec: str):
    """Load a symbol given 'pkg.mod.Class'. Returns (object or None, error_string_or_None)."""
    try:
        mod_path, sym = pathspec.rsplit(".", 1)
        mod = importlib.import_module(mod_path)
        return getattr(mod, sym, None), None
    except Exception as e:
        return None, f"{pathspec}: {e}"

def _first_present(candidates):
    """Try multiple dotted paths; return (obj, trace_list)."""
    trace = []
    for p in candidates:
        obj, err = _load_symbol(p)
        if obj is not None:
            trace.append(f"OK {p}")
            return obj, trace
        trace.append(f"FAIL {p} -> {err}")
    return None, trace

# ───────────────────────────────────────────────────────────
# Resolve Agent / Browser / LLM adapter across versions
# ───────────────────────────────────────────────────────────
_IMPORT_TRACE = []

# Agent
_Agent, tr = _first_present([
    "browser_use.Agent",
    "browser_use.agent.Agent",
    "browser_use.agent.agent.Agent",
])
_IMPORT_TRACE += tr

# Browser
_Browser, tr = _first_present([
    "browser_use.Browser",
    "browser_use.browser.Browser",
    "browser_use.browser.browser.Browser",
])
_IMPORT_TRACE += tr

# BrowserConfig (legacy/new, optional)
_BrowserConfig, tr = _first_present([
    "browser_use.BrowserConfig",
    "browser_use.browser.BrowserConfig",
    "browser_use.browser.browser.BrowserConfig",
])
_IMPORT_TRACE += tr

# BrowserProfile (compat layer in some versions)
_BrowserProfile, tr = _first_present([
    "browser_use.BrowserProfile",
    "browser_use.browser.BrowserProfile",
])
_IMPORT_TRACE += tr

# Ollama chat adapter (name & path differ by version)
_ChatOllama, tr = _first_present([
    "browser_use.ChatOllama",
    "browser_use.llm.ollama.ChatOllama",
    "browser_use.llms.ollama.ChatOllama",
    "browser_use.llms.ollama.Ollama",
])
_IMPORT_TRACE += tr

if _ChatOllama is None:
    # Fallback to OpenAI adapter
    _ChatOllama, tr2 = _first_present([
        "browser_use.llm.openai.ChatOpenAI",
        "browser_use.llms.openai.ChatOpenAI",
    ])
    _IMPORT_TRACE += tr2

# Final check (BrowserConfig optional)
if not (_Agent and _Browser and _ChatOllama):
    trace = "\n  ".join(_IMPORT_TRACE)
    raise RuntimeError(
        "browser_use import mismatch: missing required core classes (Agent/Browser/LLM).\n"
        "Fix:\n"
        "  pip install -U browser-use playwright\n"
        "  python -m playwright install chromium\n\n"
        f"Import attempts:\n  {trace}"
    )

Agent = _Agent
Browser = _Browser
BrowserConfig = _BrowserConfig
BrowserProfile = _BrowserProfile
ChatOllama = _ChatOllama

# ───────────────────────────────────────────────────────────
# 🌿 Environment & config
# ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2] if len(Path(__file__).resolve().parents) >= 2 else Path(__file__).resolve().parent
DEFAULT_ENV_PATHS = [
    Path(__file__).resolve().parent.parent / "configs" / ".env",
    PROJECT_ROOT / ".env",
]

def _maybe_load_env():
    # Try python-dotenv first
    for p in DEFAULT_ENV_PATHS:
        if p.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(p, override=False)
                return
            except Exception:
                pass
    # Minimal parser fallback (only KEY=VALUE lines)
    for p in DEFAULT_ENV_PATHS:
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k and (k not in os.environ):
                    os.environ[k] = v
            return
        except Exception:
            continue

_maybe_load_env()

# LLM / Ollama
OLLAMA_URL   = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("HALO_LLM_MODEL", "qwen2.5:7b")

# Browser behavior
HEADLESS     = os.getenv("HALO_BROWSER_HEADLESS", "1") != "0"  # "1"=headless on
WEB_DEBUG    = os.getenv("HALO_WEB_DEBUG", "0") == "1"

# Agent knobs
AGENT_MAX_STEPS = int(os.getenv("HALO_WEB_MAX_STEPS", "10"))
AGENT_MAX_ACTIONS_PER_STEP = int(os.getenv("HALO_WEB_MAX_ACTIONS_PER_STEP", "4"))

# DOM-first by default
USE_VISION = os.getenv("HALO_WEB_VISION", "0") == "1"

# Downloads directory (explicit so files don't vanish)
DEFAULT_DL_DIR = os.getenv("HALO_WEB_DOWNLOADS_DIR", str((PROJECT_ROOT / "downloads").resolve()))
DOWNLOADS_DIR = Path(DEFAULT_DL_DIR)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Session/profile & misc
PROXY_SERVER   = os.getenv("HALO_WEB_PROXY", "").strip() or None
USER_AGENT     = os.getenv("HALO_WEB_USER_AGENT", "").strip() or None

# Generic (Chromium/Chrome-style) persistent profile dir
USER_DATA_DIR  = os.getenv("HALO_WEB_USER_DATA_DIR", "").strip() or None

# Opera GX specific (your case)
OPERA_PROFILE_PATH = os.getenv("HALO_BROWSER_PROFILE_PATH", "").strip() or None
PROFILE_NAME       = os.getenv("HALO_BROWSER_PROFILE_NAME", "Default").strip()
BROWSER_CHANNEL    = os.getenv("HALO_BROWSER_CHANNEL", "").strip() or None  # usually leave empty for Opera
OPERA_EXECUTABLE   = os.getenv("HALO_BROWSER_EXECUTABLE_PATH", "").strip() or None

# Domain guardrails (optional)
ALLOWED_DOMAINS = [d.strip() for d in os.getenv("HALO_WEB_ALLOWED_DOMAINS", "").split(",") if d.strip()]
PROHIBITED_DOMAINS = [d.strip() for d in os.getenv("HALO_WEB_PROHIBITED_DOMAINS", "").split(",") if d.strip()]

# Search engine
SEARCH_ENGINE = os.getenv("HALO_WEB_SEARCH_ENGINE", "ddg").lower().strip()

# Action policy (for LLM loop guidance, not hard enforcement in code)
DEFAULT_WHITELIST = "go_to_url,extract_structured_data,click_element_by_index,scroll,wait"
DEFAULT_BLACKLIST = "execute_js,send_keys,input_text,replace_file_str,search"
ACTION_WHITELIST: List[str] = [a.strip() for a in os.getenv("HALO_WEB_ACTION_WHITELIST", DEFAULT_WHITELIST).split(",") if a.strip()]
ACTION_BLACKLIST: List[str] = [a.strip() for a in os.getenv("HALO_WEB_ACTION_BLACKLIST", DEFAULT_BLACKLIST).split(",") if a.strip()]
MAX_RESULT_LINKS = int(os.getenv("HALO_WEB_MAX_RESULT_LINKS", "10"))

# On Windows, Playwright + asyncio behaves best with Proactor
if os.name == "nt":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # type: ignore[attr-defined]
    except Exception:
        pass

# ───────────────────────────────────────────────────────────
# 🔧 Helpers
# ───────────────────────────────────────────────────────────
def _ensure_text(target: Union[str, dict, list, None]) -> str:
    """Coerce any target input into a single task string."""
    if target is None:
        return ""
    if isinstance(target, str):
        return target
    return json.dumps(target, ensure_ascii=False)

def _log(msg: str):
    if WEB_DEBUG:
        print(f"[WEB] {msg}")

def _ddg_url(query: str) -> str:
    return f"https://duckduckgo.com/?q={query.replace(' ', '+')}&ia=web"

def _actions_line(prefix: str, items: List[str]) -> str:
    return prefix + (", ".join(items) if items else "(none)")

def _build_llm_loop_task(user_task: str, force_search_open: str = "") -> str:
    """
    LLM-native perceive→decide→act loop, with DOM-first policy and clear action whitelist/blacklist.
    No deterministic scripting; the LLM chooses the sequence within allowed tools.
    """
    preface = []
    if force_search_open:
        preface.append(f"Open {force_search_open} first.")
    preface.append(
        "Perception–Decision–Action loop:\n"
        "1) PERCEIVE: Use DOM-based extraction to understand the current page.\n"
        "   - Prefer 'extract_structured_data' with extract_links=True when links matter.\n"
        "   - Read visible titles, snippets, and hrefs from result cards.\n"
        "2) DECIDE: Choose exactly ONE next action using the whitelist.\n"
        "   - If you are on a search results page, you are expected to navigate to a relevant external page early, not keep scrolling/typing.\n"
        "3) ACT: Perform that single action. Then observe again. Repeat until the goal is met.\n"
        "4) NEVER type summaries into the page. Summaries go only to the final result."
    )
    policy = [
        _actions_line("Allowed actions: ", ACTION_WHITELIST),
        _actions_line("Forbidden actions: ", ACTION_BLACKLIST),
        f"When extracting links, return up to {MAX_RESULT_LINKS} candidates and pick the best one by relevance to the task.",
        "Avoid interacting with inputs unless explicitly asked to fill a form (login/checkout).",
        "If a selector fails, try another reasonable selector. Do not fall back to execute_js.",
        "Prefer 'go_to_url' with a chosen href rather than synthetic clicks if clicking fails.",
        "Avoid unrelated sites; keep focus on the user task."
    ]
    constraints = [
        "Use only necessary actions. Avoid redundant steps.",
        "Prefer DOM extraction (visible text) over screenshots.",
        "Do NOT write to local files.",
        "If Google shows a CAPTCHA, prefer DuckDuckGo."
    ]
    return (
        user_task.strip() + "\n\n"
        + "\n".join(preface) + "\n\n"
        + "Policy:\n- " + "\n- ".join(policy) + "\n\n"
        + "Constraints:\n- " + "\n- ".join(constraints)
    )

async def _browser_task(task_text: str) -> str:
    """
    Core runner for browser-use Agent.
    Returns a final result string for logging only.
    """
    _log(f"Launching agent: headless={HEADLESS}, model={OLLAMA_MODEL}, base={OLLAMA_URL}, vision={USE_VISION}")

    # LLM init (support both signatures)
    try:
        llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_URL)
    except TypeError:
        llm = ChatOllama(model=OLLAMA_MODEL)

    # Build Browser with max compatibility
    browser = None

    # Preferred: BrowserConfig if available
    if BrowserConfig is not None:
        try:
            kwargs = dict(headless=HEADLESS)
            # Downloads / acceptance
            try:
                kwargs["downloads_path"] = str(DOWNLOADS_DIR)
                kwargs["accept_downloads"] = True
            except Exception:
                pass

            if PROXY_SERVER:
                try:
                    kwargs["proxy"] = {"server": PROXY_SERVER}
                except Exception:
                    pass
            if USER_AGENT:
                try:
                    kwargs["user_agent"] = USER_AGENT
                except Exception:
                    pass

            # Persistent session preference order:
            # 1) Opera GX profile (your case)
            # 2) Generic user_data_dir (if provided)
            if OPERA_PROFILE_PATH:
                try:
                    kwargs["user_data_dir"] = OPERA_PROFILE_PATH
                except Exception:
                    pass
                try:
                    kwargs["profile_name"] = PROFILE_NAME
                except Exception:
                    pass
                if OPERA_EXECUTABLE:
                    try:
                        kwargs["executable_path"] = OPERA_EXECUTABLE
                    except Exception:
                        pass
                if BROWSER_CHANNEL:
                    try:
                        kwargs["channel"] = BROWSER_CHANNEL
                    except Exception:
                        pass
            elif USER_DATA_DIR:
                try:
                    kwargs["user_data_dir"] = USER_DATA_DIR
                except Exception:
                    pass
                try:
                    kwargs["profile_name"] = PROFILE_NAME
                except Exception:
                    pass

            if ALLOWED_DOMAINS:
                try:
                    kwargs["allowed_domains"] = ALLOWED_DOMAINS
                except Exception:
                    pass
            if PROHIBITED_DOMAINS:
                try:
                    kwargs["prohibited_domains"] = PROHIBITED_DOMAINS
                except Exception:
                    pass

            browser = Browser(config=BrowserConfig(**kwargs))
        except Exception:
            browser = None

    if browser is None:
        # Newer versions: direct kwargs on Browser
        try:
            browser = Browser(headless=HEADLESS)
        except TypeError:
            # Legacy fallback via BrowserProfile
            if BrowserProfile is not None:
                try:
                    profile = BrowserProfile(headless=HEADLESS)
                    browser = Browser(browser_profile=profile)
                except Exception:
                    browser = Browser()
            else:
                browser = Browser()

    agent = Agent(
        task=task_text,
        llm=llm,
        browser=browser,
        use_vision=USE_VISION,
        max_actions_per_step=AGENT_MAX_ACTIONS_PER_STEP,
        max_steps=AGENT_MAX_STEPS,
    )

    _log(f"Agent task: {task_text}")
    history = await agent.run()

    try:
        result = history.final_result()
    except Exception:
        result = "done"

    _log(f"Agent final_result: {result}")
    return result

def _run_async_task(task_text: str) -> str:
    """
    Safe async runner that works whether an event loop exists or not.
    """
    try:
        return asyncio.run(_browser_task(task_text))
    except RuntimeError:
        _log("Existing event loop detected; creating a new loop for browser task.")
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_browser_task(task_text))
        finally:
            loop.close()

# ───────────────────────────────────────────────────────────
# 🌐 Skills (return None so LLM handles TTS)
# ───────────────────────────────────────────────────────────
def web_browse(target: Union[str, dict, list, None] = None):
    """
    Primary LLM-in-the-loop web automation.
    Example target:
      "Search 'monkeys', open Wikipedia, summarize the first paragraph."
    """
    task_text = _ensure_text(target).strip()
    if not task_text:
        _log("web_browse called with empty target; ignoring.")
        return None

    full_task = _build_llm_loop_task(task_text)

    try:
        result = _run_async_task(full_task)
        print(f"[WEB] Final result: {result}")
    except Exception as e:
        print(f"[WEB] Task failed: {e}")

    return None

def search_web(target: Union[str, dict, list, None] = None):
    """
    LLM-driven search skill (no deterministic scripting).
    - Opens DuckDuckGo results
    - Uses DOM extraction to perceive results
    - LLM chooses best link and action (navigate/scroll/extract), within the whitelist
    """
    q = _ensure_text(target).strip()
    if not q:
        _log("search_web with empty query; ignoring.")
        return None

    if SEARCH_ENGINE == "ddg":
        search_url = f"Open https://duckduckgo.com/?q={q.replace(' ', '+')}&ia=web first."
    else:
        search_url = f"Open https://duckduckgo.com/?q={q.replace(' ', '+')}&ia=web first."  # fallback

    task = (
        f"Goal: Find high-relevance information for: '{q}'. "
        f"Prefer external results that directly serve the user's intent.\n"
    )
    full_task = _build_llm_loop_task(task, force_search_open=search_url)
    try:
        result = _run_async_task(full_task)
        print(f"[WEB] Final result: {result}")
    except Exception as e:
        print(f"[WEB] Task failed: {e}")
    return None

def open_webpage(target: Union[str, dict, list, None] = None):
    """
    Opens a specific URL directly via agent (lets agent verify navigation) —
    but still allows the LLM to observe→decide next action (e.g., login, click).
    """
    url = _ensure_text(target).strip()
    if not url:
        _log("open_webpage with empty url; ignoring.")
        return None
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    task = f"Open {url} first. Then use the perceive→decide→act loop to achieve a minimal summary of the page purpose and main CTA."
    full_task = _build_llm_loop_task(task)
    try:
        result = _run_async_task(full_task)
        print(f"[WEB] Final result: {result}")
    except Exception as e:
        print(f"[WEB] Task failed: {e}")
    return None

def click_element(target: Union[str, dict, list, None] = None):
    """
    Click an element specified by a selector/description —
    LLM decides if a direct click or reading href+go_to_url is safer.
    """
    sel = _ensure_text(target).strip()
    if not sel:
        _log("click_element with empty selector; ignoring.")
        return None
    task = (
        f"On the current page, locate element by CSS selector: {sel}\n"
        f"If the element has an href and is not easily clickable, prefer to read href and 'go_to_url' instead.\n"
        f"Use only whitelisted actions."
    )
    full_task = _build_llm_loop_task(task)
    try:
        result = _run_async_task(full_task)
        print(f"[WEB] Final result: {result}")
    except Exception as e:
        print(f"[WEB] Task failed: {e}")
    return None

def extract_text(target: Union[str, dict, list, None] = None):
    """
    Extract visible text from a selector (defaults to body).
    Logs the result via history.final_result().
    """
    sel = _ensure_text(target).strip() or "body"
    task = f"Extract visible text from: {sel}. If too long, summarize key points for the user."
    full_task = _build_llm_loop_task(task)
    try:
        result = _run_async_task(full_task)
        print(f"[WEB] Final result: {result}")
    except Exception as e:
        print(f"[WEB] Task failed: {e}")
    return None

def summarize_page(target: Union[str, dict, list, None] = None):
    """
    Summarize the current page briefly.
    """
    task = "Summarize the current page in 3 bullet points."
    full_task = _build_llm_loop_task(task)
    try:
        result = _run_async_task(full_task)
        print(f"[WEB] Final result: {result}")
    except Exception as e:
        print(f"[WEB] Task failed: {e}")
    return None

# ───────────────────────────────────────────────────────────
# 🎯 Convenience: Amazon orders (LLM decides next)
# ───────────────────────────────────────────────────────────
def amazon_next_delivery():
    """
    Open Amazon Orders (order history). Requires persistent Opera GX/Chromium
    profile with an active Amazon session. LLM perceives and decides actions.
    """
    url = "https://www.amazon.com/gp/css/order-history"
    task = (
        f"Open {url} first.\n"
        f"Use the perceive→decide→act loop to find the next upcoming delivery. "
        f"If redirected to login, STOP and return 'Login required'. "
        f"Otherwise, return one line: '• <Item> — <status> — <ETA>' and then 'URL: <final>'"
    )
    full_task = _build_llm_loop_task(task)
    try:
        result = _run_async_task(full_task)
        print(f"[WEB] Final result: {result}")
    except Exception as e:
        print(f"[WEB] Task failed: {e}")
    return None
