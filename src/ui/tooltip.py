"""
Tooltip helper for Tkinter widgets
"""
import tkinter as tk


class ToolTip:
    """Show a small hover tooltip after a short delay."""

    def __init__(self, widget, text, delay=500, wraplength=260):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        self._tip = None
        self._after_id = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        except Exception:
            return
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tip,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("Microsoft YaHei", 9),
            wraplength=self.wraplength,
            padx=6,
            pady=4,
        )
        label.pack()
        self._tip = tip

    def _hide(self, event=None):
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


def attach_tooltip(widget, text, **kwargs):
    """Attach a tooltip to a widget and return the ToolTip instance."""
    return ToolTip(widget, text, **kwargs)
