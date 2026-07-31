"""
Lightweight in-app help viewer: renders HELP.md (Markdown) into a read-only
scrolled tk.Text window. No external dependencies — a minimal line-based
Markdown-to-Text-tag renderer covering headings, bold, inline code, lists,
blockquotes, horizontal rules, fenced code blocks and GitHub pipe tables.
"""
import tkinter as tk
from tkinter import scrolledtext
import re

# Markdown inline link: [text](target) -> keep only the readable text.
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")


class HelpViewer(tk.Toplevel):
    """A scrollable, read-only window that displays a Markdown help document."""

    def __init__(self, parent, markdown_text: str, title: str = "帮助"):
        super().__init__(parent)
        self.title(title)
        self.geometry("760x600")
        self.minsize(480, 360)
        self.transient(parent)

        self.text = scrolledtext.ScrolledText(self, wrap="word",
                                              font=("Microsoft YaHei UI", 10),
                                              padx=14, pady=12,
                                              relief="flat", bg="white")
        self.text.pack(fill="both", expand=True)

        self._define_tags()
        self._render(markdown_text)
        self.text.config(state="disabled")

        # Close shortcuts
        self.bind("<Escape>", lambda e: self.destroy())

    def _define_tags(self):
        t = self.text
        t.tag_configure("h1", font=("Microsoft YaHei UI", 18, "bold"),
                        spacing1=6, spacing3=6)
        t.tag_configure("h2", font=("Microsoft YaHei UI", 14, "bold"),
                        foreground="#1a5fb4", spacing1=10, spacing3=4)
        t.tag_configure("h3", font=("Microsoft YaHei UI", 11, "bold"),
                        spacing1=8, spacing3=2)
        t.tag_configure("bold", font=("Microsoft YaHei UI", 10, "bold"))
        t.tag_configure("code", font=("Consolas", 9), background="#f0f0f0")
        t.tag_configure("codeblock", font=("Consolas", 9), background="#f5f5f5",
                        lmargin1=16, lmargin2=16)
        t.tag_configure("quote", foreground="#666666", lmargin1=16, lmargin2=16)
        t.tag_configure("hr", foreground="#999999")
        t.tag_configure("table", font=("Consolas", 9))
        t.tag_configure("list", lmargin1=20, lmargin2=20)
        t.tag_configure("normal", spacing3=2)

    # ---- Markdown -> Text rendering ----

    def _render(self, md: str):
        lines = md.splitlines()
        i = 0
        in_code = False
        while i < len(lines):
            raw = lines[i]
            line = raw.rstrip("\n")
            stripped = line.strip()

            # Fenced code block toggle
            if stripped.startswith("```"):
                in_code = not in_code
                i += 1
                continue
            if in_code:
                self._insert(line + "\n", "codeblock")
                i += 1
                continue

            # Blank line -> small gap
            if not stripped:
                self._insert("\n", "normal")
                i += 1
                continue

            # Horizontal rule
            if stripped in ("---", "***", "___"):
                self._insert("─" * 60 + "\n", "hr")
                i += 1
                continue

            # Headings
            if stripped.startswith("### "):
                self._insert_inline(stripped[4:], "h3")
                self._insert("\n")
                i += 1
                continue
            if stripped.startswith("## "):
                self._insert_inline(stripped[3:], "h2")
                self._insert("\n")
                i += 1
                continue
            if stripped.startswith("# "):
                self._insert_inline(stripped[2:], "h1")
                self._insert("\n")
                i += 1
                continue

            # Blockquote
            if stripped.startswith(">"):
                content = stripped.lstrip(">").strip()
                self._insert_inline(content, "quote")
                self._insert("\n")
                i += 1
                continue

            # GitHub pipe table row
            if stripped.startswith("|") and stripped.endswith("|"):
                # Skip separator rows like |---|---|
                if set(stripped) <= set("|-: "):
                    i += 1
                    continue
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                row = "  ".join(f"{c:<14}" for c in cells)
                self._insert(row.rstrip() + "\n", "table")
                i += 1
                continue

            # Bulleted list
            if stripped.startswith("- ") or stripped.startswith("* "):
                self._insert("• ", "list")
                self._insert_inline(stripped[2:], "list")
                self._insert("\n")
                i += 1
                continue

            # Normal paragraph
            self._insert_inline(stripped, "normal")
            self._insert("\n")
            i += 1

    def _insert(self, text: str, tag: str = None):
        if tag:
            self.text.insert("end", text, tag)
        else:
            self.text.insert("end", text)

    def _insert_inline(self, text: str, base_tag: str = None):
        """Insert text handling **bold**, `code` and [links](url) inline spans."""
        # Strip Markdown link syntax, keeping only the readable link text.
        # (All links in HELP.md are internal #anchors with no jump target in a
        # plain Text widget, so the target is discarded.)
        text = _LINK_RE.sub(r"\1", text)
        i = 0
        buf = ""
        mode = None  # None | 'bold' | 'code'

        def flush():
            nonlocal buf
            if not buf:
                return
            if mode == 'bold':
                self.text.insert("end", buf, ("bold",) if not base_tag else (base_tag, "bold"))
            elif mode == 'code':
                self.text.insert("end", buf, ("code",) if not base_tag else (base_tag, "code"))
            elif base_tag:
                self.text.insert("end", buf, base_tag)
            else:
                self.text.insert("end", buf)
            buf = ""

        while i < len(text):
            if text.startswith("**", i):
                flush()
                mode = None if mode == 'bold' else 'bold'
                i += 2
            elif text[i] == "`":
                flush()
                mode = None if mode == 'code' else 'code'
                i += 1
            else:
                buf += text[i]
                i += 1
        flush()


def show_help(parent, markdown_text: str, title: str = "帮助"):
    """Open the help viewer (reuses an existing open window if any)."""
    existing = getattr(parent, "_help_window", None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        existing.focus_set()
        return existing
    win = HelpViewer(parent, markdown_text, title)
    parent._help_window = win
    return win
