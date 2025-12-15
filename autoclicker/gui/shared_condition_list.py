# gui/shared_condition_list.py
import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import TYPE_CHECKING, List, Optional, Callable

if TYPE_CHECKING:
    from core.job_manager import JobManager
    from core.condition import Condition

logger = logging.getLogger(__name__)

class SharedConditionList(ttk.Frame):
    def __init__(self, master, job_manager: 'JobManager',
                 condition_edit_callback: Callable[[Optional[str]], None]):
        super().__init__(master)
        self.job_manager = job_manager
        self.condition_edit_callback = condition_edit_callback

        if not self.job_manager:
            logger.error("SharedConditionList initialized without a valid JobManager.")
            ttk.Label(self, text="Error: JobManager not available.", foreground="red").pack(padx=20, pady=20)
            return

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        columns = ("name", "id", "type", "params_summary")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")

        col_configs = [
            ("name", "Condition Name", tk.W, True),
            ("id", "ID (Unique)", tk.W, False),
            ("type", "Type", tk.W, False),
            ("params_summary", "Parameters Summary", tk.W, True),
        ]
        for col_name, text, anchor, stretch in col_configs:
            self.tree.heading(col_name, text=text, anchor=anchor)

        col_widths = {"name": 200, "id": 220, "type": 150, "params_summary": 300}
        for col, width in col_widths.items():
            stretch_val = tk.YES if col in ["name", "params_summary"] else tk.NO
            anchor_val = tk.W
            self.tree.column(col, width=width, minwidth=max(50, width // 2), anchor=anchor_val, stretch=stretch_val)

        self.tree.grid(row=0, column=0, padx=(5,0), pady=5, sticky="nsew")
        tree_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        tree_scrollbar.grid(row=0, column=1, sticky='ns', pady=5, padx=(0,5))
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

        button_row_frame = ttk.Frame(self)
        button_row_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=(5,10), sticky="ew")
        button_row_frame.grid_columnconfigure(0, weight=1)

        self.add_button = ttk.Button(button_row_frame, text="Add New Condition", command=self._add_condition)
        self.add_button.grid(row=0, column=1, padx=3, sticky="e")
        self.edit_button = ttk.Button(button_row_frame, text="Edit Selected", command=self._edit_selected_condition)
        self.edit_button.grid(row=0, column=2, padx=3, sticky="e")
        self.delete_button = ttk.Button(button_row_frame, text="Delete Selected", command=self._delete_selected_condition)
        self.delete_button.grid(row=0, column=3, padx=3, sticky="e")

        self.tree.bind("<Double-1>", lambda e: self._edit_selected_condition())
        self.tree.bind('<<TreeviewSelect>>', self._on_condition_select)

        self.refresh_condition_list()
        logger.debug("SharedConditionList UI built.")

    def _get_params_summary(self, condition: 'Condition') -> str:
        if not condition or not hasattr(condition, 'params') or not isinstance(condition.params, dict):
            return ""
        
        summary_parts = []
        params_to_show = 3
        
        for key, value in condition.params.items():
            if len(summary_parts) >= params_to_show * 2:
                summary_parts.append("...")
                break
            
            value_str = str(value)
            max_val_len = 25
            if len(value_str) > max_val_len:
                value_str = value_str[:max_val_len-3] + "..."
            
            summary_parts.append(f"{key}: {value_str}")
            
        return ", ".join(summary_parts) if summary_parts else "(No specific params)"

    def refresh_condition_list(self):
        logger.debug("SharedConditionList: Refreshing condition list.")
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not self.job_manager or not self.job_manager.condition_manager:
            logger.warning("SharedConditionList: JobManager or ConditionManager not available for refresh.")
            return

        try:
            conditions: List['Condition'] = sorted(
                self.job_manager.condition_manager.get_all_shared_conditions(),
                key=lambda c: c.name.lower()
            )

            if not conditions:
                logger.debug("SharedConditionList: No shared conditions found to display.")
                self.tree.insert("", tk.END, values=("(No shared conditions defined)", "", "", ""))
                if self.tree.get_children(): 
                    self.tree.item(self.tree.get_children()[0], tags=('disabled',))


            for cond_obj in conditions:
                if not (cond_obj and hasattr(cond_obj, 'id') and hasattr(cond_obj, 'name') and hasattr(cond_obj, 'type')):
                    logger.warning(f"Skipping invalid condition object during refresh: {cond_obj}")
                    continue

                params_summary = self._get_params_summary(cond_obj)
                
                self.tree.insert("", tk.END, iid=cond_obj.id,
                                   values=(cond_obj.name, cond_obj.id, cond_obj.type, params_summary))
        except Exception as e:
            logger.error(f"Error populating shared condition list: {e}", exc_info=True)
            self.tree.insert("", tk.END, values=("Error loading conditions. Check logs.", "", "", ""))
            if self.tree.get_children(): 
                 self.tree.item(self.tree.get_children()[0], tags=('disabled',))


        self._update_buttons_state()

    def get_selected_condition_id(self) -> Optional[str]:
        selected_items = self.tree.selection()
        return selected_items[0] if selected_items else None

    def _on_condition_select(self, event=None):
        self._update_buttons_state()

    def _update_buttons_state(self):
        selected_id = self.get_selected_condition_id()
        edit_state = tk.NORMAL if selected_id else tk.DISABLED
        delete_state = tk.NORMAL if selected_id else tk.DISABLED

        if hasattr(self, 'edit_button'): self.edit_button.config(state=edit_state)
        if hasattr(self, 'delete_button'): self.delete_button.config(state=delete_state)
        if hasattr(self, 'add_button'): self.add_button.config(state=tk.NORMAL)

    def _add_condition(self):
        if self.condition_edit_callback:
            logger.info("SharedConditionList: Requesting to add new shared condition.")
            self.condition_edit_callback(None)

    def _edit_selected_condition(self):
        selected_id = self.get_selected_condition_id()
        if selected_id and self.condition_edit_callback:
            logger.info(f"SharedConditionList: Requesting to edit shared condition ID: {selected_id}")
            self.condition_edit_callback(selected_id)
        elif not selected_id:
             messagebox.showwarning("No Selection", "Please select a shared condition to edit.", parent=self)

    def _delete_selected_condition(self):
        selected_id = self.get_selected_condition_id()
        if not selected_id:
            messagebox.showwarning("No Selection", "Please select a shared condition to delete.", parent=self)
            return

        if not self.job_manager: return

        condition_to_delete = self.job_manager.get_shared_condition_by_id(selected_id)
        name_for_confirm = condition_to_delete.name if condition_to_delete and hasattr(condition_to_delete, 'name') else selected_id


        try:
            if messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to permanently delete the shared condition '{name_for_confirm}'?\n"
                                   "This may affect Actions or Triggers currently using it.",
                                   icon='warning', parent=self):
                
                if self.job_manager.delete_shared_condition(selected_id):
                    self.refresh_condition_list()
                    logger.info(f"Shared condition '{name_for_confirm}' (ID: {selected_id}) deleted.")
        except ValueError as ve:
            messagebox.showerror("Deletion Failed", str(ve), parent=self)
        except Exception as e:
            logger.error(f"Error deleting shared condition ID '{selected_id}': {e}", exc_info=True)
            messagebox.showerror("Delete Error", f"Failed to delete shared condition: {e}", parent=self)
        finally:
            self._update_buttons_state()

    def _start_periodic_update(self):
        pass

    def _stop_periodic_update(self):
        pass

    def destroy(self):
         logger.debug("Destroying SharedConditionList frame.")
         super().destroy()
