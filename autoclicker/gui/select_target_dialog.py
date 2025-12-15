# gui/select_target_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

class SelectTargetDialog(tk.Toplevel):
    def __init__(self, parent, target_list: List[str], dialog_title: str = "Select Target", prompt: str = "Select an item:"):
        super().__init__(parent)
        self.title(dialog_title)
        self.target_list = target_list
        self.selected_target: Optional[str] = None 

        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.update_idletasks() 
        parent.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()

        req_w = self.winfo_reqwidth()
        req_h = self.winfo_reqheight()
        list_height = max(5, min(15, len(target_list))) 
        dialog_width = max(300, req_w + 60)
        dialog_height = req_h + (list_height * 18) + 100 

        pos_x = parent_x + (parent_w // 2) - (dialog_width // 2)
        pos_y = parent_y + (parent_h // 2) - (dialog_height // 2)
        self.geometry(f"{dialog_width}x{dialog_height}+{pos_x}+{pos_y}")
        self.minsize(dialog_width, dialog_height) 

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)
        main_frame.rowconfigure(1, weight=1) 
        main_frame.columnconfigure(0, weight=1) 

        ttk.Label(main_frame, text=prompt).grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="w")

        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, exportselection=False, height=list_height)
        list_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=list_scrollbar.set)

        self.listbox.grid(row=0, column=0, sticky="nsew")
        list_scrollbar.grid(row=0, column=1, sticky="ns")

        if not self.target_list:
            self.listbox.insert(tk.END, "(No available targets)")
            self.listbox.config(state=tk.DISABLED)
        else:
            for item in self.target_list:
                self.listbox.insert(tk.END, item)
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self.listbox.see(0)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky="e")

        ok_state = tk.NORMAL if self.target_list else tk.DISABLED
        self.ok_button = ttk.Button(button_frame, text="OK", command=self._on_ok, state=ok_state)
        self.ok_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self._on_cancel)
        self.cancel_button.pack(side=tk.LEFT, padx=5)

        self.listbox.bind("<Double-1>", lambda e: self._on_ok() if self.target_list else None)
        self.bind("<Return>", lambda e: self._on_ok() if self.target_list else None) 
        self.bind("<Escape>", lambda e: self._on_cancel()) 
        self.protocol("WM_DELETE_WINDOW", self._on_cancel) 

        self.listbox.focus_set()

    def _on_ok(self):
        """Xử lý khi nhấn OK."""
        selected_indices = self.listbox.curselection()
        if selected_indices:
            self.selected_target = self.listbox.get(selected_indices[0])
            logger.debug(f"Target selected in dialog: {self.selected_target}")
            self.destroy()
        else:
            if self.target_list:
                messagebox.showwarning("No Selection", "Please select an item from the list.", parent=self)
            else:
                 self.destroy()


    def _on_cancel(self):
        """Xử lý khi nhấn Cancel hoặc đóng cửa sổ."""
        self.selected_target = None 
        self.destroy()
