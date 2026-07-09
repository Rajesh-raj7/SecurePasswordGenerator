"""
gui.py
======
Tkinter GUI for the Secure Password Generator.

Layout
------
A single main window with:
    - Header (title + theme switch)
    - Tabbed sections: Password | Passphrase / PIN / Wi-Fi | History | Stats
    - Output field(s), Generate / Copy / Save / QR buttons
    - A strength meter (canvas-based progress bar) + entropy/crack-time labels
    - A status bar at the bottom for confirmations and errors

This module intentionally keeps all business logic in generator.py /
strength.py / settings.py / history.py -- the GUI only wires user input to
those modules and renders the results.
"""

from __future__ import annotations

import csv
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from generator import PasswordGenerator, PasswordOptions, GeneratorError
from strength import analyze_password
from settings import SettingsManager
from history import HistoryManager, HistoryEntry

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False

try:
    import qrcode
    from PIL import Image, ImageTk
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False


# ---------------------------------------------------------------------------
# Theme definitions
# ---------------------------------------------------------------------------

THEMES = {
    "dark": {
        "bg": "#1e1f29", "fg": "#f5f6fa", "panel": "#2a2c3a",
        "accent": "#7c5cff", "accent_dark": "#5c3fd6", "entry_bg": "#11121a",
        "success": "#3ddc97", "warning": "#ffb454", "danger": "#ff6b6b",
        "muted": "#9a9cb5",
    },
    "light": {
        "bg": "#f4f5fb", "fg": "#1e1f29", "panel": "#ffffff",
        "accent": "#5c3fd6", "accent_dark": "#4630a8", "entry_bg": "#eceefc",
        "success": "#1ba97a", "warning": "#c47f11", "danger": "#d1453b",
        "muted": "#5a5c73",
    },
}

STRENGTH_COLORS = {
    "Weak": "#ff6b6b", "Medium": "#ffb454", "Strong": "#3ddc97",
    "Very Strong": "#22c55e",
}


class PasswordApp:
    """Top-level application controller and window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Secure Password Generator")
        self.root.geometry("760x620")
        self.root.minsize(680, 560)

        self.settings = SettingsManager()
        self.history = HistoryManager()
        self.generator = PasswordGenerator()

        self.theme_name = self.settings.get("theme", "dark")
        self.theme = THEMES[self.theme_name]

        self.last_generated: list[str] = []

        self._build_style()
        self._build_layout()
        self._apply_theme()
        self.set_status("Ready.")

    # ------------------------------------------------------------------
    # Style / theme
    # ------------------------------------------------------------------

    def _build_style(self) -> None:
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

    def _apply_theme(self) -> None:
        t = self.theme
        self.root.configure(bg=t["bg"])
        self.style.configure("TFrame", background=t["bg"])
        self.style.configure("Panel.TFrame", background=t["panel"])
        self.style.configure("TLabel", background=t["bg"], foreground=t["fg"],
                              font=("Segoe UI", 10))
        self.style.configure("Panel.TLabel", background=t["panel"], foreground=t["fg"])
        self.style.configure("Header.TLabel", background=t["bg"], foreground=t["fg"],
                              font=("Segoe UI", 18, "bold"))
        self.style.configure("Muted.TLabel", background=t["panel"], foreground=t["muted"],
                              font=("Segoe UI", 9))
        self.style.configure("TCheckbutton", background=t["panel"], foreground=t["fg"])
        self.style.configure("TNotebook", background=t["bg"], borderwidth=0)
        self.style.configure("TNotebook.Tab", padding=(14, 8), font=("Segoe UI", 10))
        self.style.configure("Accent.TButton", background=t["accent"], foreground="#ffffff",
                              font=("Segoe UI", 10, "bold"), padding=8)
        self.style.map("Accent.TButton", background=[("active", t["accent_dark"])])
        self.style.configure("Secondary.TButton", padding=6)
        self.style.configure("Horizontal.TScale", background=t["panel"])

        self.output_entry.configure(bg=t["entry_bg"], fg=t["fg"],
                                     insertbackground=t["fg"])
        self.status_bar.configure(bg=t["panel"], fg=t["muted"])
        self._redraw_strength_meter()

    def toggle_theme(self) -> None:
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.theme = THEMES[self.theme_name]
        self.settings.update(theme=self.theme_name)
        self._apply_theme()
        self.set_status(f"Switched to {self.theme_name} theme.")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        # Header
        header = ttk.Frame(self.root, padding=(16, 14, 16, 4))
        header.pack(fill="x")
        ttk.Label(header, text="🔐 Secure Password Generator", style="Header.TLabel").pack(side="left")
        theme_btn = ttk.Button(header, text="🌓 Toggle Theme", command=self.toggle_theme,
                                style="Secondary.TButton")
        theme_btn.pack(side="right")

        # Notebook (tabs)
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=16, pady=8)

        self.tab_password = ttk.Frame(notebook, padding=14)
        self.tab_extra = ttk.Frame(notebook, padding=14)
        self.tab_history = ttk.Frame(notebook, padding=14)
        self.tab_stats = ttk.Frame(notebook, padding=14)

        notebook.add(self.tab_password, text="Password")
        notebook.add(self.tab_extra, text="Passphrase / PIN / Wi-Fi")
        notebook.add(self.tab_history, text="History")
        notebook.add(self.tab_stats, text="Statistics")

        self._build_password_tab(self.tab_password)
        self._build_extra_tab(self.tab_extra)
        self._build_history_tab(self.tab_history)
        self._build_stats_tab(self.tab_stats)

        # Status bar
        self.status_bar = tk.Label(self.root, text="", anchor="w", padx=16, pady=6,
                                    font=("Segoe UI", 9))
        self.status_bar.pack(fill="x", side="bottom")

    # ------------------------------------------------------------------
    # Password tab
    # ------------------------------------------------------------------

    def _build_password_tab(self, parent: ttk.Frame) -> None:
        # Output field
        out_frame = ttk.Frame(parent)
        out_frame.pack(fill="x", pady=(0, 10))
        self.output_entry = tk.Text(out_frame, height=4, wrap="word",
                                     font=("Consolas", 13), relief="flat", padx=10, pady=8)
        self.output_entry.pack(fill="x")
        self.output_entry.configure(state="disabled")

        # Strength meter
        strength_frame = ttk.Frame(parent)
        strength_frame.pack(fill="x", pady=(0, 10))
        self.strength_canvas = tk.Canvas(strength_frame, height=14, highlightthickness=0)
        self.strength_canvas.pack(fill="x")
        self.strength_label = ttk.Label(strength_frame, text="Strength: -", font=("Segoe UI", 10, "bold"))
        self.strength_label.pack(anchor="w", pady=(4, 0))
        self.entropy_label = ttk.Label(strength_frame, text="", style="Muted.TLabel")
        self.entropy_label.pack(anchor="w")

        # Options panel
        options = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        options.pack(fill="x", pady=(0, 10))

        s = self.settings

        # Length slider
        len_row = ttk.Frame(options, style="Panel.TFrame")
        len_row.pack(fill="x", pady=(0, 6))
        ttk.Label(len_row, text="Length:", style="Panel.TLabel").pack(side="left")
        self.length_var = tk.IntVar(value=s.get("length", 16))
        self.length_value_label = ttk.Label(len_row, text=str(self.length_var.get()),
                                             style="Panel.TLabel", font=("Segoe UI", 10, "bold"))
        self.length_value_label.pack(side="right")
        self.length_scale = ttk.Scale(len_row, from_=4, to=128, orient="horizontal",
                                       variable=self.length_var, command=self._on_length_change)
        self.length_scale.pack(side="left", fill="x", expand=True, padx=10)

        # Checkboxes grid
        cb_frame = ttk.Frame(options, style="Panel.TFrame")
        cb_frame.pack(fill="x", pady=(4, 6))

        self.var_upper = tk.BooleanVar(value=s.get("use_upper", True))
        self.var_lower = tk.BooleanVar(value=s.get("use_lower", True))
        self.var_digits = tk.BooleanVar(value=s.get("use_digits", True))
        self.var_symbols = tk.BooleanVar(value=s.get("use_symbols", True))
        self.var_excl_similar = tk.BooleanVar(value=s.get("exclude_similar", False))
        self.var_excl_ambiguous = tk.BooleanVar(value=s.get("exclude_ambiguous", False))
        self.var_no_repeat = tk.BooleanVar(value=s.get("no_repeat", False))

        checks = [
            ("Uppercase (A-Z)", self.var_upper),
            ("Lowercase (a-z)", self.var_lower),
            ("Numbers (0-9)", self.var_digits),
            ("Symbols (!@#$...)", self.var_symbols),
            ("Exclude similar (O,0,I,l,1)", self.var_excl_similar),
            ("Exclude ambiguous symbols", self.var_excl_ambiguous),
            ("No repeated characters", self.var_no_repeat),
        ]
        for i, (label, var) in enumerate(checks):
            cb = ttk.Checkbutton(cb_frame, text=label, variable=var, style="TCheckbutton")
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 20), pady=3)

        # Count row
        count_row = ttk.Frame(options, style="Panel.TFrame")
        count_row.pack(fill="x", pady=(8, 0))
        ttk.Label(count_row, text="How many passwords:", style="Panel.TLabel").pack(side="left")
        self.count_var = tk.IntVar(value=s.get("count", 1))
        count_spin = ttk.Spinbox(count_row, from_=1, to=20, textvariable=self.count_var, width=5)
        count_spin.pack(side="left", padx=10)

        # Buttons row
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_row, text="⚡ Generate", style="Accent.TButton",
                   command=self.on_generate).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="📋 Copy", style="Secondary.TButton",
                   command=self.on_copy).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="💾 Save to History", style="Secondary.TButton",
                   command=self.on_save).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="🔳 Show QR", style="Secondary.TButton",
                   command=self.on_show_qr).pack(side="left")

    def _on_length_change(self, _value: str) -> None:
        self.length_value_label.configure(text=str(int(float(self.length_var.get()))))

    # ------------------------------------------------------------------
    # Extra generators tab
    # ------------------------------------------------------------------

    def _build_extra_tab(self, parent: ttk.Frame) -> None:
        # Passphrase
        pp = ttk.LabelFrame(parent, text="Passphrase (correct-horse-battery-staple)", padding=12)
        pp.pack(fill="x", pady=(0, 12))
        row = ttk.Frame(pp)
        row.pack(fill="x")
        ttk.Label(row, text="Words:").pack(side="left")
        self.passphrase_words = tk.IntVar(value=4)
        ttk.Spinbox(row, from_=3, to=10, textvariable=self.passphrase_words, width=5).pack(side="left", padx=8)
        ttk.Button(row, text="Generate Passphrase", command=self.on_generate_passphrase).pack(side="left", padx=8)
        self.passphrase_output = ttk.Label(pp, text="", font=("Consolas", 12, "bold"))
        self.passphrase_output.pack(anchor="w", pady=(8, 0))

        # PIN
        pin = ttk.LabelFrame(parent, text="PIN Generator", padding=12)
        pin.pack(fill="x", pady=(0, 12))
        row2 = ttk.Frame(pin)
        row2.pack(fill="x")
        ttk.Label(row2, text="Digits:").pack(side="left")
        self.pin_length = tk.IntVar(value=6)
        ttk.Spinbox(row2, from_=3, to=12, textvariable=self.pin_length, width=5).pack(side="left", padx=8)
        ttk.Button(row2, text="Generate PIN", command=self.on_generate_pin).pack(side="left", padx=8)
        self.pin_output = ttk.Label(pin, text="", font=("Consolas", 12, "bold"))
        self.pin_output.pack(anchor="w", pady=(8, 0))

        # Pronounceable
        pron = ttk.LabelFrame(parent, text="Pronounceable / Memorable Password", padding=12)
        pron.pack(fill="x", pady=(0, 12))
        row3 = ttk.Frame(pron)
        row3.pack(fill="x")
        ttk.Button(row3, text="Generate Pronounceable", command=self.on_generate_pronounceable).pack(side="left")
        self.pron_output = ttk.Label(pron, text="", font=("Consolas", 12, "bold"))
        self.pron_output.pack(anchor="w", pady=(8, 0))

        # Wi-Fi + Username
        misc = ttk.LabelFrame(parent, text="Wi-Fi Password & Username", padding=12)
        misc.pack(fill="x")
        row4 = ttk.Frame(misc)
        row4.pack(fill="x")
        ttk.Button(row4, text="Generate Wi-Fi Password", command=self.on_generate_wifi).pack(side="left", padx=(0, 8))
        ttk.Button(row4, text="Generate Username", command=self.on_generate_username).pack(side="left")
        self.misc_output = ttk.Label(misc, text="", font=("Consolas", 12, "bold"))
        self.misc_output.pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------------
    # History tab
    # ------------------------------------------------------------------

    def _build_history_tab(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 8))
        enc_text = "🔒 Encrypted at rest" if self.history.encrypted else "⚠ Unencrypted (install 'cryptography' for encryption)"
        ttk.Label(top, text=enc_text, style="Muted.TLabel").pack(side="left")
        ttk.Button(top, text="Export TXT", command=self.on_export_txt).pack(side="right", padx=(6, 0))
        ttk.Button(top, text="Export CSV", command=self.on_export_csv).pack(side="right", padx=(6, 0))
        ttk.Button(top, text="🗑 Clear History", command=self.on_clear_history).pack(side="right", padx=(6, 0))

        columns = ("password", "created_at", "rating", "kind")
        self.history_tree = ttk.Treeview(parent, columns=columns, show="headings", height=16)
        for col, width in zip(columns, (240, 160, 100, 90)):
            self.history_tree.heading(col, text=col.replace("_", " ").title())
            self.history_tree.column(col, width=width)
        self.history_tree.pack(fill="both", expand=True)
        self._refresh_history_view()

    def _refresh_history_view(self) -> None:
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)
        for e in reversed(self.history.all()):
            self.history_tree.insert("", "end", values=(e.password, e.created_at, e.rating, e.kind))

    # ------------------------------------------------------------------
    # Stats tab
    # ------------------------------------------------------------------

    def _build_stats_tab(self, parent: ttk.Frame) -> None:
        self.stats_label = ttk.Label(parent, text="", font=("Segoe UI", 11), justify="left")
        self.stats_label.pack(anchor="nw")
        ttk.Button(parent, text="🔄 Refresh Statistics", command=self.on_refresh_stats).pack(anchor="w", pady=12)
        self.on_refresh_stats()

    def on_refresh_stats(self) -> None:
        stats = self.history.stats()
        if stats.get("count", 0) == 0:
            self.stats_label.configure(text="No history yet. Generate and save some passwords first.")
            return
        text = (
            f"Total saved:        {stats['count']}\n"
            f"Average entropy:    {stats['average_entropy_bits']} bits\n"
            f"Weak:               {stats['weak']}\n"
            f"Medium:             {stats['medium']}\n"
            f"Strong:             {stats['strong']}\n"
            f"Very Strong:        {stats['very_strong']}\n"
        )
        self.stats_label.configure(text=text)

    # ------------------------------------------------------------------
    # Actions: main password generation
    # ------------------------------------------------------------------

    def _current_options(self) -> PasswordOptions:
        return PasswordOptions(
            length=int(self.length_var.get()),
            use_upper=self.var_upper.get(),
            use_lower=self.var_lower.get(),
            use_digits=self.var_digits.get(),
            use_symbols=self.var_symbols.get(),
            exclude_similar=self.var_excl_similar.get(),
            exclude_ambiguous=self.var_excl_ambiguous.get(),
            no_repeat=self.var_no_repeat.get(),
            count=int(self.count_var.get()),
        )

    def on_generate(self) -> None:
        opts = self._current_options()
        try:
            passwords = self.generator.generate_many(opts)
        except GeneratorError as e:
            messagebox.showerror("Invalid options", str(e))
            self.set_status(f"Error: {e}")
            return

        self.last_generated = passwords
        self._set_output_text("\n".join(passwords))

        # Strength meter reflects the first password generated
        result = analyze_password(passwords[0])
        self._update_strength_display(result)

        self.settings.update(
            length=opts.length, use_upper=opts.use_upper, use_lower=opts.use_lower,
            use_digits=opts.use_digits, use_symbols=opts.use_symbols,
            exclude_similar=opts.exclude_similar, exclude_ambiguous=opts.exclude_ambiguous,
            no_repeat=opts.no_repeat, count=opts.count,
        )
        self.set_status(f"Generated {len(passwords)} password(s).")

    def _set_output_text(self, text: str) -> None:
        self.output_entry.configure(state="normal")
        self.output_entry.delete("1.0", "end")
        self.output_entry.insert("1.0", text)
        self.output_entry.configure(state="disabled")

    def _update_strength_display(self, result) -> None:
        self.strength_label.configure(
            text=f"Strength: {result.rating}  ({result.entropy_bits} bits of entropy)")
        self.entropy_label.configure(
            text=(f"Estimated crack time — offline attack: {result.crack_time_offline} | "
                  f"online (rate-limited) attack: {result.crack_time_online}"))
        self._redraw_strength_meter(result.score_percent, result.rating)

    def _redraw_strength_meter(self, percent: int = 0, rating: str = "") -> None:
        c = self.strength_canvas
        c.delete("all")
        width = c.winfo_width() or 600
        height = 14
        t = self.theme
        c.configure(bg=t["panel"])
        c.create_rectangle(0, 0, width, height, fill=t["entry_bg"], outline="")
        color = STRENGTH_COLORS.get(rating, t["accent"])
        fill_width = int(width * percent / 100)
        if fill_width > 0:
            c.create_rectangle(0, 0, fill_width, height, fill=color, outline="")

    # ------------------------------------------------------------------
    # Actions: clipboard / save / QR
    # ------------------------------------------------------------------

    def _first_output_line(self) -> str:
        text = self.output_entry.get("1.0", "end").strip()
        return text.split("\n")[0] if text else ""

    def on_copy(self) -> None:
        text = self._first_output_line()
        if not text:
            self.set_status("Nothing to copy yet -- generate a password first.")
            return
        if CLIPBOARD_AVAILABLE:
            pyperclip.copy(text)
            self.set_status("✅ Copied to clipboard.")
        else:
            # Fallback: Tk's own clipboard, always available with Tkinter.
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.set_status("✅ Copied to clipboard (Tk fallback -- install 'pyperclip' for full support).")

    def on_save(self) -> None:
        text = self.output_entry.get("1.0", "end").strip()
        if not text:
            self.set_status("Nothing to save yet -- generate a password first.")
            return
        entries = []
        for line in text.split("\n"):
            if not line.strip():
                continue
            result = analyze_password(line)
            entries.append(HistoryEntry.new(line, result.rating, result.entropy_bits))
        self.history.add_many(entries)
        self._refresh_history_view()
        self.on_refresh_stats()
        self.set_status(f"💾 Saved {len(entries)} password(s) to history.")

    def on_show_qr(self) -> None:
        text = self._first_output_line()
        if not text:
            self.set_status("Nothing to encode yet -- generate a password first.")
            return
        if not QR_AVAILABLE:
            messagebox.showinfo(
                "QR code unavailable",
                "Install the 'qrcode' and 'Pillow' packages to enable QR export:\n\n"
                "pip install qrcode[pil]",
            )
            return

        img = qrcode.make(text)
        win = tk.Toplevel(self.root)
        win.title("Password QR Code")
        win.configure(bg=self.theme["bg"])
        tk_img = ImageTk.PhotoImage(img.resize((260, 260)))
        label = tk.Label(win, image=tk_img, bg=self.theme["bg"])
        label.image = tk_img  # keep a reference
        label.pack(padx=16, pady=16)
        ttk.Label(win, text="Scan to transfer this password to another device.",
                  style="Muted.TLabel" if False else "TLabel").pack(pady=(0, 12))

    # ------------------------------------------------------------------
    # Actions: extra generators
    # ------------------------------------------------------------------

    def on_generate_passphrase(self) -> None:
        try:
            value = self.generator.generate_passphrase(word_count=int(self.passphrase_words.get()))
        except GeneratorError as e:
            messagebox.showerror("Invalid options", str(e))
            return
        self.passphrase_output.configure(text=value)
        self.set_status("Generated a passphrase.")

    def on_generate_pin(self) -> None:
        try:
            value = self.generator.generate_pin(length=int(self.pin_length.get()))
        except GeneratorError as e:
            messagebox.showerror("Invalid options", str(e))
            return
        self.pin_output.configure(text=value)
        self.set_status("Generated a PIN.")

    def on_generate_pronounceable(self) -> None:
        value = self.generator.generate_pronounceable(length=10)
        self.pron_output.configure(text=value)
        self.set_status("Generated a pronounceable password.")

    def on_generate_wifi(self) -> None:
        value = self.generator.generate_wifi_password()
        self.misc_output.configure(text=f"Wi-Fi: {value}")
        self.set_status("Generated a Wi-Fi password.")

    def on_generate_username(self) -> None:
        value = self.generator.generate_username()
        self.misc_output.configure(text=f"Username: {value}")
        self.set_status("Generated a username.")

    # ------------------------------------------------------------------
    # Actions: history
    # ------------------------------------------------------------------

    def on_clear_history(self) -> None:
        if not self.history.all():
            self.set_status("History is already empty.")
            return
        if messagebox.askyesno("Clear history", "Delete all saved password history? This cannot be undone."):
            self.history.clear()
            self._refresh_history_view()
            self.on_refresh_stats()
            self.set_status("🗑 History cleared.")

    def on_export_txt(self) -> None:
        if not self.history.all():
            self.set_status("No history to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Text file", "*.txt")])
        if not path:
            return
        self.history.export_txt(Path(path))
        self.set_status(f"Exported history to {path}")

    def on_export_csv(self) -> None:
        if not self.history.all():
            self.set_status("No history to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        self.history.export_csv(Path(path))
        self.set_status(f"Exported history to {path}")

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def set_status(self, message: str) -> None:
        self.status_bar.configure(text=message)


def run() -> None:
    root = tk.Tk()
    app = PasswordApp(root)
    root.mainloop()


if __name__ == "__main__":
    run()
