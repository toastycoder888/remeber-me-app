"""
Remember Me - desktop app with multiple notes (like Apple Notes) and a To-Do list.

Everything is saved to a file in your home folder, so it is still there
after you close the app or turn your computer off.
"""

import json
import time
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

DATA_FILE = Path.home() / "remember_me_data.json"
SAVE_DELAY_MS = 800  # notes save shortly after you stop typing


def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        messagebox.showerror("Save failed", f"Could not save your data:\n{e}")


def make_note(body=""):
    return {"id": uuid.uuid4().hex, "body": body, "modified": time.time()}


def note_title(note):
    """Like Apple Notes: the title is the first line of the note."""
    for line in note["body"].splitlines():
        if line.strip():
            line = line.strip()
            return line if len(line) <= 28 else line[:27] + "\u2026"
    return "New Note"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Remember Me")
        self.geometry("720x520")
        self.minsize(520, 380)

        self.data = load_data()
        self.data.setdefault("todos", [])
        self.migrate_notes()

        self.current_id = None
        self.visible_ids = []
        self.save_job = None

        # ---- Header ----
        self.greeting = tk.Label(self, text="", font=("Helvetica", 16, "bold"))
        self.greeting.pack(pady=(12, 0))
        self.info = tk.Label(self, text="", font=("Helvetica", 9))
        self.info.pack(pady=(0, 6))

        # ---- Tabs ----
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self.build_notes_tab(tabs)
        self.build_todo_tab(tabs)

        # ---- Footer ----
        footer = tk.Frame(self)
        footer.pack(pady=(0, 10))
        tk.Button(footer, text="Change my name", command=self.change_name).pack(side="left", padx=4)
        tk.Button(footer, text="Forget everything", command=self.forget_all).pack(side="left", padx=4)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        if not self.data.get("name"):
            self.ask_name()
        self.data["launch_count"] = self.data.get("launch_count", 0) + 1
        save_data(self.data)
        self.refresh_labels()

    # ---------- Notes ----------
    def migrate_notes(self):
        """Bring over the single note from older versions, and make sure one note exists."""
        old = self.data.pop("notes", None)
        self.data.setdefault("note_items", [])
        if old and old.strip() and not self.data["note_items"]:
            self.data["note_items"].append(make_note(old))
        if not self.data["note_items"]:
            self.data["note_items"].append(make_note())

    def find_note(self, note_id):
        for n in self.data["note_items"]:
            if n["id"] == note_id:
                return n
        return None

    def build_notes_tab(self, tabs):
        frame = tk.Frame(tabs)
        tabs.add(frame, text="Notes")

        panes = tk.PanedWindow(frame, orient="horizontal", sashrelief="raised")
        panes.pack(fill="both", expand=True, padx=6, pady=6)

        # Left side: list of notes
        left = tk.Frame(panes)
        panes.add(left, minsize=150, width=200)

        top = tk.Frame(left)
        top.pack(fill="x", pady=(0, 4))
        tk.Button(top, text="+ New note", command=self.new_note).pack(side="left", padx=(0, 4))
        tk.Button(top, text="Delete", command=self.delete_note).pack(side="left")

        list_frame = tk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        lscroll = tk.Scrollbar(list_frame)
        lscroll.pack(side="right", fill="y")
        self.note_list = tk.Listbox(
            list_frame, yscrollcommand=lscroll.set, activestyle="none",
            exportselection=False, font=("Helvetica", 11),
        )
        self.note_list.pack(side="left", fill="both", expand=True)
        lscroll.config(command=self.note_list.yview)
        self.note_list.bind("<<ListboxSelect>>", self.on_select_note)

        # Right side: editor
        right = tk.Frame(panes)
        panes.add(right, minsize=250)
        rscroll = tk.Scrollbar(right)
        rscroll.pack(side="right", fill="y")
        self.editor = tk.Text(right, wrap="word", yscrollcommand=rscroll.set, undo=True)
        self.editor.pack(side="left", fill="both", expand=True)
        rscroll.config(command=self.editor.yview)
        self.editor.bind("<KeyRelease>", self.on_typing)

        # Start on the most recently edited note
        first = max(self.data["note_items"], key=lambda n: n["modified"])
        self.load_note(first["id"])
        self.refresh_note_list()

    def refresh_note_list(self):
        notes = sorted(self.data["note_items"], key=lambda n: n["modified"], reverse=True)
        self.visible_ids = [n["id"] for n in notes]
        self.note_list.delete(0, "end")
        for n in notes:
            self.note_list.insert("end", note_title(n))
        if self.current_id in self.visible_ids:
            idx = self.visible_ids.index(self.current_id)
            self.note_list.selection_set(idx)
            self.note_list.see(idx)

    def load_note(self, note_id):
        note = self.find_note(note_id)
        if note is None:
            return
        self.current_id = note_id
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", note["body"])
        self.editor.edit_reset()

    def save_current(self):
        if self.save_job:
            self.after_cancel(self.save_job)
            self.save_job = None
        note = self.find_note(self.current_id)
        if note is None:
            return
        body = self.editor.get("1.0", "end-1c")
        if body != note["body"]:
            note["body"] = body
            note["modified"] = time.time()
            save_data(self.data)
            self.refresh_note_list()

    def on_typing(self, _event=None):
        if self.save_job:
            self.after_cancel(self.save_job)
        self.save_job = self.after(SAVE_DELAY_MS, self.save_current)

    def on_select_note(self, _event=None):
        sel = self.note_list.curselection()
        if not sel:
            return
        new_id = self.visible_ids[sel[0]]
        if new_id == self.current_id:
            return
        self.save_current()
        self.load_note(new_id)

    def new_note(self):
        self.save_current()
        note = make_note()
        self.data["note_items"].append(note)
        save_data(self.data)
        self.load_note(note["id"])
        self.refresh_note_list()
        self.editor.focus_set()

    def delete_note(self):
        note = self.find_note(self.current_id)
        if note is None:
            return
        if not messagebox.askyesno("Delete note?", f"Delete \"{note_title(note)}\"? This can't be undone."):
            return
        if self.save_job:
            self.after_cancel(self.save_job)
            self.save_job = None
        self.data["note_items"].remove(note)
        if not self.data["note_items"]:
            self.data["note_items"].append(make_note())
        save_data(self.data)
        first = max(self.data["note_items"], key=lambda n: n["modified"])
        self.load_note(first["id"])
        self.refresh_note_list()

    # ---------- To-do tab ----------
    def build_todo_tab(self, tabs):
        frame = tk.Frame(tabs)
        tabs.add(frame, text="To-Do")

        add_row = tk.Frame(frame)
        add_row.pack(fill="x", padx=8, pady=(8, 4))
        self.todo_entry = tk.Entry(add_row)
        self.todo_entry.pack(side="left", fill="x", expand=True)
        self.todo_entry.bind("<Return>", lambda e: self.add_todo())
        tk.Button(add_row, text="Add", command=self.add_todo).pack(side="left", padx=(6, 0))

        list_frame = tk.Frame(frame)
        list_frame.pack(fill="both", expand=True, padx=8, pady=4)
        scroll = tk.Scrollbar(list_frame)
        scroll.pack(side="right", fill="y")
        self.todo_list = tk.Listbox(
            list_frame, yscrollcommand=scroll.set, activestyle="none",
            selectmode="browse", exportselection=False, font=("Helvetica", 11),
        )
        self.todo_list.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.todo_list.yview)
        self.todo_list.bind("<Double-Button-1>", lambda e: self.toggle_todo())

        btns = tk.Frame(frame)
        btns.pack(pady=(4, 8))
        tk.Button(btns, text="Done / Undo", command=self.toggle_todo).pack(side="left", padx=3)
        tk.Button(btns, text="Delete", command=self.delete_todo).pack(side="left", padx=3)
        tk.Button(btns, text="Clear completed", command=self.clear_completed).pack(side="left", padx=3)

        self.refresh_todos()

    def refresh_todos(self):
        self.todo_list.delete(0, "end")
        for i, item in enumerate(self.data["todos"]):
            mark = "\u2611" if item["done"] else "\u2610"
            self.todo_list.insert("end", f"{mark}  {item['text']}")
            if item["done"]:
                self.todo_list.itemconfig(i, fg="gray")

    def selected_todo(self):
        sel = self.todo_list.curselection()
        return sel[0] if sel else None

    def add_todo(self):
        text = self.todo_entry.get().strip()
        if not text:
            return
        self.data["todos"].append({"text": text, "done": False})
        self.todo_entry.delete(0, "end")
        save_data(self.data)
        self.refresh_todos()

    def toggle_todo(self):
        i = self.selected_todo()
        if i is None:
            return
        self.data["todos"][i]["done"] = not self.data["todos"][i]["done"]
        save_data(self.data)
        self.refresh_todos()
        self.todo_list.selection_set(i)

    def delete_todo(self):
        i = self.selected_todo()
        if i is None:
            return
        del self.data["todos"][i]
        save_data(self.data)
        self.refresh_todos()

    def clear_completed(self):
        self.data["todos"] = [t for t in self.data["todos"] if not t["done"]]
        save_data(self.data)
        self.refresh_todos()

    # ---------- Name / general ----------
    def ask_name(self):
        name = simpledialog.askstring("Welcome!", "What's your name?", parent=self)
        if name and name.strip():
            self.data["name"] = name.strip()
            save_data(self.data)

    def change_name(self):
        self.ask_name()
        self.refresh_labels()

    def refresh_labels(self):
        name = self.data.get("name")
        self.greeting.config(text=f"Welcome back, {name}!" if name else "Hello, stranger!")
        n = self.data.get("launch_count", 0)
        self.info.config(text=f"Opened {n} time{'s' if n != 1 else ''}")

    def forget_all(self):
        if not messagebox.askyesno("Forget everything?", "This deletes your name, all notes and to-dos. Continue?"):
            return
        if self.save_job:
            self.after_cancel(self.save_job)
            self.save_job = None
        self.data = {"todos": []}
        self.migrate_notes()
        if DATA_FILE.exists():
            DATA_FILE.unlink()
        self.ask_name()
        self.data["launch_count"] = 1
        save_data(self.data)
        self.load_note(self.data["note_items"][0]["id"])
        self.refresh_note_list()
        self.refresh_todos()
        self.refresh_labels()

    def on_close(self):
        self.save_current()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
