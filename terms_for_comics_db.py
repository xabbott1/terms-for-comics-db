#!/usr/bin/env python3
"""Terms for Comics DB - a simple 6-box scratch pad for comic-related terms."""

import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk


APP_TITLE = "Terms for Comics DB"
BOX_COUNT = 6
GRID_COLS = 3
GRID_ROWS = 2
AUTOSAVE_MS = 3 * 60 * 1000  # 3 minutes
FILENAMES = [f"{i}.txt" for i in range(1, BOX_COUNT + 1)]


def candidate_storage_dirs():
    """Return storage directories in fallback priority order."""
    dirs = []
    # 1. Primary: ~/.config/comicterms/
    dirs.append(Path.home() / ".config" / "comicterms")
    # 2. Fallback 1: comicterms/ in the same directory as the program/script
    # When bundled (e.g. PyInstaller --onefile), use the executable's directory.
    if getattr(sys, "frozen", False):
        try:
            program_dir = Path(sys.executable).resolve().parent
        except OSError:
            program_dir = Path.cwd()
    else:
        try:
            program_dir = Path(__file__).resolve().parent
        except NameError:
            program_dir = Path.cwd()
    dirs.append(program_dir / "comicterms")
    # 3. Fallback 2: ~/Desktop/comicterms/
    dirs.append(Path.home() / "Desktop" / "comicterms")
    # 4. Fallback 3: <tempdir>/comicterms/
    dirs.append(Path(tempfile.gettempdir()) / "comicterms")
    return dirs


def is_dir_writable(directory: Path) -> bool:
    """Check whether a directory can be created and written to."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_probe_tmp"
        with open(probe, "w", encoding="utf-8") as f:
            f.write("probe")
        try:
            probe.unlink()
        except OSError:
            pass
        return True
    except OSError:
        return False


def atomic_write_text(path: Path, text: str) -> None:
    """Write text to path atomically (best effort on POSIX)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        # If replace failed, try to clean up the temp file.
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass


class TermsApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.text_widgets = []
        self.active_dir = None  # type: Path | None
        self.last_saved = [""] * BOX_COUNT
        self._autosave_job = None
        self._closing = False
        self.always_on_top = tk.BooleanVar(master=self.root, value=False)

        self._build_ui()

        # Startup: select first writable location if possible and load from it.
        self.active_dir = self._find_initial_writable_dir()
        if self.active_dir is not None:
            loaded = self._load_from_dir(self.active_dir)
            self._set_all_texts(loaded)
            self.last_saved = list(loaded)
        else:
            self.last_saved = [""] * BOX_COUNT

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._schedule_autosave()

    def _build_ui(self):
        # Row 0: controls, Rows 1-2: text boxes
        self.root.grid_rowconfigure(0, weight=0)
        for r in range(1, GRID_ROWS + 1):
            self.root.grid_rowconfigure(r, weight=1)
        for c in range(GRID_COLS):
            self.root.grid_columnconfigure(c, weight=1)

        controls = ttk.Frame(self.root, padding=(4, 4, 4, 0))
        controls.grid(row=0, column=0, columnspan=GRID_COLS, sticky="ew")
        topmost_check = ttk.Checkbutton(
            controls,
            text="Always on top",
            variable=self.always_on_top,
            command=self._toggle_always_on_top,
        )
        topmost_check.grid(row=0, column=0, sticky="w")

        for idx in range(BOX_COUNT):
            row = (idx // GRID_COLS) + 1
            col = idx % GRID_COLS
            cell = ttk.Frame(self.root, padding=4)
            cell.grid(row=row, column=col, sticky="nsew")
            cell.grid_rowconfigure(1, weight=1)
            cell.grid_columnconfigure(0, weight=1)

            copy_btn = ttk.Button(
                cell,
                text="Copy",
                command=lambda i=idx: self.copy_box(i),
            )
            copy_btn.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))

            text = tk.Text(
                cell,
                wrap="word",
                undo=True,
                width=30,
                height=10,
            )
            text.grid(row=1, column=0, sticky="nsew")

            scroll = ttk.Scrollbar(cell, orient="vertical", command=text.yview)
            scroll.grid(row=1, column=1, sticky="ns")
            text.configure(yscrollcommand=scroll.set)

            self.text_widgets.append(text)

        # Reasonable default size; user can resize freely.
        self.root.minsize(600, 400)

    def _get_all_texts(self):
        return [w.get("1.0", "end-1c") for w in self.text_widgets]

    def _set_all_texts(self, texts):
        for w, t in zip(self.text_widgets, texts):
            w.delete("1.0", "end")
            if t:
                w.insert("1.0", t)

    def copy_box(self, idx: int):
        text = self.text_widgets[idx].get("1.0", "end-1c")
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            # Keep clipboard content available after widget interactions.
            self.root.update_idletasks()
        except tk.TclError:
            # Clipboard unavailable; ignore silently (app remains usable).
            pass

    def _toggle_always_on_top(self):
        try:
            self.root.attributes("-topmost", self.always_on_top.get())
        except tk.TclError:
            # Some platforms/window managers may not support -topmost.
            self.always_on_top.set(False)

    def _find_initial_writable_dir(self):
        for d in candidate_storage_dirs():
            if is_dir_writable(d):
                return d
        return None

    def _load_from_dir(self, directory: Path):
        texts = []
        for name in FILENAMES:
            path = directory / name
            try:
                if path.is_file():
                    texts.append(path.read_text(encoding="utf-8"))
                else:
                    texts.append("")
            except OSError:
                texts.append("")
        # Ensure correct length
        if len(texts) < BOX_COUNT:
            texts.extend([""] * (BOX_COUNT - len(texts)))
        return texts[:BOX_COUNT]

    def _save_to_dir(self, directory: Path, texts) -> bool:
        """Attempt to save all boxes to directory. Return True on success."""
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        try:
            for name, text in zip(FILENAMES, texts):
                atomic_write_text(directory / name, text)
            return True
        except OSError:
            return False

    def _attempt_save(self, texts):
        """
        Try saving to active dir, then fall back through the chain.
        Returns (success, saved_dir_or_None).
        If all locations fail, returns (False, None).
        """
        candidates = candidate_storage_dirs()
        start_index = 0
        if self.active_dir is not None:
            try:
                # If active dir is in candidates, try from it onward.
                resolved_active = self.active_dir.resolve()
                for i, c in enumerate(candidates):
                    try:
                        if c.resolve() == resolved_active:
                            start_index = i
                            break
                    except OSError:
                        continue
            except OSError:
                start_index = 0

        # Try from start_index onward, and if that doesn't include earlier ones
        # in a meaningful way we've already covered the active location.
        # If no active dir, this naturally starts at 0.
        ordered = candidates[start_index:] + candidates[:start_index]

        # But prefer not to retry the same path twice in weird cases; keep order unique.
        seen = set()
        unique_ordered = []
        for d in ordered:
            key = str(d)
            if key not in seen:
                seen.add(key)
                unique_ordered.append(d)

        for d in unique_ordered:
            if not is_dir_writable(d):
                continue
            if self._save_to_dir(d, texts):
                return True, d
        return False, None

    def save_if_changed(self, force: bool = False, allow_exit_on_total_failure: bool = True) -> bool:
        """
        Save if changed (or if forced). On total save failure (including temp),
        close the program if allow_exit_on_total_failure is True.
        Returns True if save succeeded or was not needed.
        """
        if self._closing and not force:
            # During closing we may call with force; avoid duplicate logic issues.
            pass

        texts = self._get_all_texts()
        if not force and texts == self.last_saved:
            return True

        success, saved_dir = self._attempt_save(texts)
        if success:
            self.active_dir = saved_dir
            self.last_saved = list(texts)
            return True

        # All locations failed (including temp): close the program as specified.
        if allow_exit_on_total_failure:
            self._force_exit()
        return False

    def _schedule_autosave(self):
        if self._closing:
            return
        self._autosave_job = self.root.after(AUTOSAVE_MS, self._autosave_tick)

    def _autosave_tick(self):
        self._autosave_job = None
        if self._closing:
            return
        # Autosave: if all locations fail, app will close per spec.
        self.save_if_changed(force=False, allow_exit_on_total_failure=True)
        if not self._closing:
            self._schedule_autosave()

    def _cancel_autosave(self):
        if self._autosave_job is not None:
            try:
                self.root.after_cancel(self._autosave_job)
            except tk.TclError:
                pass
            self._autosave_job = None

    def _force_exit(self):
        if self._closing:
            return
        self._closing = True
        self._cancel_autosave()
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        # Ensure process exits if destroy doesn't end mainloop promptly.
        raise SystemExit(0)

    def on_close(self):
        if self._closing:
            return
        self._closing = True
        self._cancel_autosave()
        # Final save attempt on close; if total failure, save_if_changed will exit.
        self.save_if_changed(force=True, allow_exit_on_total_failure=True)
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def main():
    root = tk.Tk()
    # Use themed widgets where available for a more native look.
    try:
        style = ttk.Style()
        # Keep default theme; just ensure ttk is initialized.
        _ = style.theme_use()
    except tk.TclError:
        pass
    app = TermsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
