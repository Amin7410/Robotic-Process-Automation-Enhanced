import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
from typing import TYPE_CHECKING, List, Optional, Callable

if TYPE_CHECKING:
    from core.job_manager import JobManager
    from gui.shape_template_editor import ShapeTemplateEditor 

logger = logging.getLogger(__name__)

class ShapeTemplateList(ttk.Frame):
    def __init__(self, master, job_manager: 'JobManager',
                 shape_template_edit_callback: Callable[[Optional[str]], None]):
        super().__init__(master)
        self.job_manager = job_manager
        self.shape_template_edit_callback = shape_template_edit_callback

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        columns = ("display_name", "internal_name", "description", "num_strokes", "num_actions")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse") 

        col_configs = [
            ("display_name", "Display Name", tk.W, True),
            ("internal_name", "Internal Name", tk.W, True),
            ("description", "Description", tk.W, True),
            ("num_strokes", "#Strokes", tk.CENTER, False),
            ("num_actions", "#Gen. Actions", tk.CENTER, False),
        ]
        for col_name, text, anchor, stretch in col_configs:
            self.tree.heading(col_name, text=text, anchor=anchor)

        col_widths = {"display_name": 200, "internal_name": 150, "description": 250, "num_strokes": 80, "num_actions": 100}
        for col, width in col_widths.items():
            stretch_val = tk.YES if col in ["display_name", "internal_name", "description"] else tk.NO
            self.tree.column(col, width=width, minwidth=max(50, width // 2), anchor=tk.W if stretch_val else tk.CENTER, stretch=stretch_val)

        self.tree.grid(row=0, column=0, padx=(5,0), pady=5, sticky="nsew")
        tree_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        tree_scrollbar.grid(row=0, column=1, sticky='ns', pady=5, padx=(0,5))
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

        button_row_frame = ttk.Frame(self)
        button_row_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=(5,10), sticky="ew")
        button_row_frame.grid_columnconfigure(0, weight=1) 

        self.add_button = ttk.Button(button_row_frame, text="Add New Template", command=self._add_template)
        self.add_button.grid(row=0, column=1, padx=3, sticky="e")
        self.edit_button = ttk.Button(button_row_frame, text="Edit Selected", command=self._edit_selected_template)
        self.edit_button.grid(row=0, column=2, padx=3, sticky="e")
        self.delete_button = ttk.Button(button_row_frame, text="Delete Selected", command=self._delete_selected_template)
        self.delete_button.grid(row=0, column=3, padx=3, sticky="e")

        self.tree.bind("<Double-1>", lambda e: self._edit_selected_template())
        self.tree.bind('<<TreeviewSelect>>', self._on_template_select)

        self._populate_template_list()
        self._update_buttons_state()

    def _populate_template_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not self.job_manager: return

        template_names = self.job_manager.list_shape_templates() 
        for internal_name in sorted(template_names):
            template_data = self.job_manager.get_shape_template_data(internal_name)
            if template_data:
                display_name = template_data.get("display_name", internal_name)
                description = template_data.get("description", "")
                num_strokes = len(template_data.get("drawing_data", {}).get("strokes", []))
                num_actions = len(template_data.get("actions", []))

                self.tree.insert("", tk.END, iid=internal_name,
                                   values=(display_name, internal_name, description, num_strokes, num_actions))
        self._update_buttons_state()


    def get_selected_template_internal_name(self) -> Optional[str]:
        selected_items = self.tree.selection() 
        return selected_items[0] if selected_items else None

    def _on_template_select(self, event=None):
        self._update_buttons_state()

    def _update_buttons_state(self):
        selected_name = self.get_selected_template_internal_name()
        edit_state = tk.NORMAL if selected_name else tk.DISABLED
        delete_state = tk.NORMAL if selected_name else tk.DISABLED
        self.edit_button.config(state=edit_state)
        self.delete_button.config(state=delete_state)
        self.add_button.config(state=tk.NORMAL)

    def _add_template(self):
        if self.shape_template_edit_callback:
            self.shape_template_edit_callback(None) 

    def _edit_selected_template(self):
        selected_name = self.get_selected_template_internal_name()
        if selected_name and self.shape_template_edit_callback:
            self.shape_template_edit_callback(selected_name)
        elif not selected_name:
             messagebox.showwarning("No Selection", "Please select a template to edit.", parent=self)


    def _delete_selected_template(self):
        selected_name = self.get_selected_template_internal_name()
        if not selected_name:
            messagebox.showwarning("No Selection", "Please select a template to delete.", parent=self)
            return

        template_data = self.job_manager.get_shape_template_data(selected_name)
        display_name_for_confirm = template_data.get("display_name", selected_name) if template_data else selected_name

        if messagebox.askyesno("Confirm Delete",
                               f"Are you sure you want to permanently delete the template '{display_name_for_confirm}'?",
                               icon='warning', parent=self):
            try:
                self.job_manager.delete_shape_template(selected_name)
                self._populate_template_list() 
                logger.info(f"Shape template '{selected_name}' deleted.")
            except Exception as e:
                logger.error(f"Error deleting shape template '{selected_name}': {e}", exc_info=True)
                messagebox.showerror("Delete Error", f"Failed to delete template: {e}", parent=self)

    def refresh_template_list(self):
        logger.info("Refreshing shape template list display.")
        self._populate_template_list()
