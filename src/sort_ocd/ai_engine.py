"""
ai_engine.py — Unified multi-backend AI engine for sort_OCD.

Supports: Ollama (local) | OpenAI | Anthropic | Custom OpenAI-compatible endpoint.
Design: One AIEngine class, same interface regardless of backend.
Auto-detection: On first use, tries Ollama; if not running, gracefully skips AI.
No config required to start — sensible defaults handle everything.
"""

import json
import os
import base64
from typing import Any, Dict, List, Optional

from . import config as cfg


# ─── Response Helpers ─────────────────────────────────────────────────────────

def _format_response(data: Dict[str, Any], filename: str) -> Dict[str, str]:
    """Normalize AI response to a clean dict with guaranteed keys."""
    # Sanitize folder name: no slashes, no empties
    folder = str(data.get("folder", "Misc")).strip().replace("/", "-").replace("\\", "-")
    if not folder:
        folder = "Misc"
    return {
        "folder": folder,
        "filename": str(data.get("filename", filename)).strip() or filename,
        "summary": str(data.get("summary", "")).strip(),
        "rationale": str(data.get("rationale", "AI categorized based on content.")).strip(),
    }


def _error_response(filename: str, reason: str = "Analysis failed") -> Dict[str, str]:
    """Return a safe fallback response when AI fails."""
    return {
        "folder": "Uncategorized",
        "filename": filename,
        "summary": "",
        "rationale": reason,
    }


# ─── Text Extraction ──────────────────────────────────────────────────────────

def _extract_text(file_path: str, max_chars: int = 2000) -> str:
    """
    Extract readable text from a file for AI context.
    Supports: PDF, plain text, code, markdown, CSV, JSON.
    Silently returns empty string on any failure.
    """
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return ""

    ext = os.path.splitext(file_path)[1].lower()
    content = ""

    try:
        if ext == ".pdf":
            try:
                import PyPDF2
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        content += page.extract_text() or ""
                        if len(content) >= max_chars:
                            break
            except ImportError:
                pass
        elif ext in {".txt", ".md", ".csv", ".py", ".js", ".ts", ".json",
                     ".html", ".css", ".xml", ".yaml", ".yml", ".toml",
                     ".sh", ".bash", ".zsh", ".rs", ".go", ".java", ".cpp",
                     ".c", ".h", ".rb", ".php", ".swift", ".kt", ".r", ".sql"}:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
    except Exception:
        pass

    return content[:max_chars].strip()


# ─── Prompt Builder ───────────────────────────────────────────────────────────

def _build_prompt(filename: str, custom_rule: Optional[str] = None,
                  content_snippet: str = "") -> str:
    rule_section = ""
    if custom_rule:
        rule_section = f'\nUSER RULE (MUST follow): "{custom_rule}"\n'

    content_section = ""
    if content_snippet:
        content_section = f"\nFile content preview:\n---\n{content_snippet}\n---"

    return f"""You are a professional file organizer. Analyze the file below and output ONLY valid JSON.

JSON schema (all keys required):
{{
  "folder": "Short category name (1-3 words, no slashes)",
  "filename": "Clean descriptive filename (keep original extension)",
  "summary": "One sentence: what this file is about",
  "rationale": "One sentence: why you chose this folder"
}}
{rule_section}
Filename: {filename}{content_section}

Respond ONLY with the JSON object. No markdown, no explanation."""


# ─── AIEngine Class ───────────────────────────────────────────────────────────

class AIEngine:
    """
    Unified AI engine. Picks backend automatically or uses config.
    Usage:
        engine = AIEngine()
        result = engine.categorize("/path/to/file.pdf", rule="Put invoices in Finance")
        taxonomies = engine.suggest_taxonomy(["file1.pdf", "photo.jpg", ...])
    """

    def __init__(self) -> None:
        self._conf = cfg.load()
        self._backend = self._conf.get("ai_backend", "auto")
        self._resolved_backend: Optional[str] = None
        self._ollama_model: Optional[str] = None
        self._ollama_vision_model: Optional[str] = None

    # ── Backend Resolution ────────────────────────────────────────────────────

    def _resolve_backend(self) -> Optional[str]:
        """
        On first call, determine which backend to actually use.
        Returns backend name or None if nothing is available.
        """
        if self._resolved_backend is not None:
            return self._resolved_backend

        backend = self._backend

        if backend == "auto":
            # Try Ollama first (free, private)
            if self._try_ollama_init():
                self._resolved_backend = "ollama"
            elif self._conf.get("openai_api_key"):
                self._resolved_backend = "openai"
            elif self._conf.get("anthropic_api_key"):
                self._resolved_backend = "anthropic"
            else:
                self._resolved_backend = None  # No AI available
        elif backend == "ollama":
            self._try_ollama_init()
            self._resolved_backend = "ollama"
        else:
            self._resolved_backend = backend

        return self._resolved_backend

    def _try_ollama_init(self) -> bool:
        """Check Ollama connectivity and resolve model names. Returns True on success."""
        try:
            import ollama as _ollama
            _ollama.list()  # Will throw if server is down

            available = cfg.detect_ollama_models()
            conf_model = self._conf.get("ollama_model", "auto")
            conf_vision = self._conf.get("ollama_vision_model", "auto")

            self._ollama_model = (
                conf_model if conf_model != "auto"
                else cfg.pick_best_ollama_model(available)
            )
            self._ollama_vision_model = (
                conf_vision if conf_vision != "auto"
                else cfg.pick_best_vision_model(available)
            )

            return self._ollama_model is not None
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if any AI backend is reachable."""
        return self._resolve_backend() is not None

    def backend_info(self) -> str:
        """Human-readable description of the active backend."""
        b = self._resolve_backend()
        if b == "ollama":
            return f"Ollama ({self._ollama_model or 'unknown model'})"
        elif b == "openai":
            return f"OpenAI ({self._conf.get('openai_model', 'gpt-4o-mini')})"
        elif b == "anthropic":
            return f"Anthropic ({self._conf.get('anthropic_model', 'claude-3-haiku')})"
        elif b == "custom":
            return f"Custom endpoint ({self._conf.get('custom_endpoint', '?')})"
        return "No AI backend"

    # ── Core: Categorize File ─────────────────────────────────────────────────

    def categorize(self, file_path: str,
                   custom_rule: Optional[str] = None) -> Dict[str, str]:
        """
        Analyze a file and return categorization metadata.
        Falls back gracefully to Uncategorized if AI is unavailable.
        """
        filename = os.path.basename(file_path)
        backend = self._resolve_backend()

        if not backend:
            return _error_response(filename, "No AI backend available")

        # Build context
        ext = os.path.splitext(filename)[1].lower()
        is_image = ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
                            ".tiff", ".tif", ".heic", ".heif"}

        try:
            if backend == "ollama":
                return self._categorize_ollama(file_path, filename, is_image, custom_rule)
            elif backend == "openai":
                return self._categorize_openai(file_path, filename, is_image, custom_rule)
            elif backend == "anthropic":
                return self._categorize_anthropic(file_path, filename, is_image, custom_rule)
            elif backend == "custom":
                return self._categorize_custom(file_path, filename, custom_rule)
        except Exception as e:
            return _error_response(filename, f"AI error: {str(e)[:80]}")

        return _error_response(filename)

    # ── Ollama Backend ────────────────────────────────────────────────────────

    def _categorize_ollama(self, file_path: str, filename: str,
                           is_image: bool, rule: Optional[str]) -> Dict[str, str]:
        import ollama

        if is_image and self._ollama_vision_model:
            try:
                with open(file_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                prompt = _build_prompt(filename, rule)
                resp = ollama.chat(
                    model=self._ollama_vision_model,
                    messages=[{"role": "user", "content": prompt, "images": [img_b64]}],
                    format="json",
                )
                data = json.loads(resp["message"]["content"])
                return _format_response(data, filename)
            except Exception:
                pass  # Fall through to text model

        content = _extract_text(file_path) if not is_image else ""
        prompt = _build_prompt(filename, rule, content)
        resp = ollama.chat(
            model=self._ollama_model,
            messages=[{"role": "user", "content": prompt}],
            format="json",
        )
        data = json.loads(resp["message"]["content"])
        return _format_response(data, filename)

    # ── OpenAI Backend ────────────────────────────────────────────────────────

    def _categorize_openai(self, file_path: str, filename: str,
                           is_image: bool, rule: Optional[str]) -> Dict[str, str]:
        from openai import OpenAI
        client = OpenAI(api_key=self._conf.get("openai_api_key"))
        model = self._conf.get("openai_model", "gpt-4o-mini")

        if is_image:
            try:
                with open(file_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                ext = os.path.splitext(filename)[1].lower().lstrip(".")
                mime = f"image/{ext}" if ext in {"png", "jpg", "jpeg", "gif", "webp"} else "image/jpeg"
                prompt = _build_prompt(filename, rule)
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",  # vision-capable
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {
                                "url": f"data:{mime};base64,{img_b64}"
                            }},
                        ],
                    }],
                    response_format={"type": "json_object"},
                )
                data = json.loads(resp.choices[0].message.content)
                return _format_response(data, filename)
            except Exception:
                pass

        content = _extract_text(file_path)
        prompt = _build_prompt(filename, rule, content)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        return _format_response(data, filename)

    # ── Anthropic Backend ─────────────────────────────────────────────────────

    def _categorize_anthropic(self, file_path: str, filename: str,
                               is_image: bool, rule: Optional[str]) -> Dict[str, str]:
        import anthropic
        client = anthropic.Anthropic(api_key=self._conf.get("anthropic_api_key"))
        model = self._conf.get("anthropic_model", "claude-3-haiku-20240307")

        if is_image:
            try:
                with open(file_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                ext = os.path.splitext(filename)[1].lower().lstrip(".")
                media_type = f"image/{ext}" if ext in {"png", "jpg", "jpeg", "gif", "webp"} else "image/jpeg"
                if ext == "jpg":
                    media_type = "image/jpeg"
                prompt = _build_prompt(filename, rule)
                resp = client.messages.create(
                    model=model,
                    max_tokens=256,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": img_b64,
                            }},
                            {"type": "text", "text": prompt},
                        ],
                    }],
                )
                data = json.loads(resp.content[0].text)
                return _format_response(data, filename)
            except Exception:
                pass

        content = _extract_text(file_path)
        prompt = _build_prompt(filename, rule, content)
        resp = client.messages.create(
            model=model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(resp.content[0].text)
        return _format_response(data, filename)

    # ── Custom Endpoint Backend ───────────────────────────────────────────────

    def _categorize_custom(self, file_path: str, filename: str,
                            rule: Optional[str]) -> Dict[str, str]:
        """OpenAI-compatible custom endpoint (LM Studio, Codex CLI, Jan.ai, etc.)"""
        from openai import OpenAI
        client = OpenAI(
            api_key=self._conf.get("openai_api_key", "not-needed"),
            base_url=self._conf.get("custom_endpoint", "http://localhost:1234/v1"),
        )
        model = self._conf.get("custom_model", "local-model")
        content = _extract_text(file_path)
        prompt = _build_prompt(filename, rule, content)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content or "{}"
        # Try to extract JSON if model wrapped it in markdown
        if "```" in raw:
            import re
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            raw = match.group(1) if match else raw
        data = json.loads(raw)
        return _format_response(data, filename)

    # ── Taxonomy Suggestion ───────────────────────────────────────────────────

    def suggest_taxonomy(self, files_sample: List[str]) -> List[str]:
        """
        Given a sample of filenames, suggest 3 different organizational strategies.
        Falls back to sensible defaults if AI is unavailable.
        """
        default = ["By File Type", "By Project / Topic", "By Date Created"]
        backend = self._resolve_backend()
        if not backend:
            return default

        sample_text = "\n".join(files_sample[:30])
        prompt = f"""You are a file organization expert. Given this list of files, suggest exactly 3 different high-level strategies to organize them.

Files:
{sample_text}

Rules:
- Each strategy name must be under 6 words
- Make them genuinely different from each other
- Think about what would actually help the person find files

Output ONLY valid JSON: {{"taxonomies": ["Strategy 1", "Strategy 2", "Strategy 3"]}}"""

        try:
            if backend == "ollama":
                import ollama
                resp = ollama.chat(
                    model=self._ollama_model,
                    messages=[{"role": "user", "content": prompt}],
                    format="json",
                )
                data = json.loads(resp["message"]["content"])
            elif backend in ("openai", "custom"):
                from openai import OpenAI
                kwargs: Dict[str, Any] = {"api_key": self._conf.get("openai_api_key", "x")}
                if backend == "custom":
                    kwargs["base_url"] = self._conf.get("custom_endpoint")
                client = OpenAI(**kwargs)
                model_name = (
                    self._conf.get("custom_model", "local-model")
                    if backend == "custom"
                    else self._conf.get("openai_model", "gpt-4o-mini")
                )
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )
                data = json.loads(resp.choices[0].message.content)
            elif backend == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=self._conf.get("anthropic_api_key"))
                resp = client.messages.create(
                    model=self._conf.get("anthropic_model", "claude-3-haiku-20240307"),
                    max_tokens=256,
                    messages=[{"role": "user", "content": prompt}],
                )
                data = json.loads(resp.content[0].text)
            else:
                return default

            taxes = data.get("taxonomies", default)
            if not isinstance(taxes, list) or len(taxes) < 1:
                return default
            # Pad to 3 if needed
            while len(taxes) < 3:
                taxes.append(default[len(taxes)])
            return [str(t) for t in taxes[:3]]

        except Exception:
            return default
