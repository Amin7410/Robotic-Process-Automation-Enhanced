# gui/trigger_list.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
import time
from typing import TYPE_CHECKING, List, Optional 

_CoreClassesImported = False
try:
    from core.trigger import Trigger, TriggerAction
    from core.job_manager import JobManager
    _CoreClassesImported = True
    logger = logging.getLogger(__name__)
    logger.debug("TriggerList: Core classes imported successfully.")
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.critical(f"TriggerList: FATAL ERROR loading core classes: {e}")
    _CoreClassesImported = False
    class Trigger:
        def __init__(self, name="DummyTrigger", enabled=True, actions=None, conditions=None, interval=0.5, logic="AND"):
            self.name = name; self.enabled = enabled;
            self.actions = actions if isinstance(actions, list) else []
            self.conditions=conditions or []; self.check_interval_seconds=interval; self.condition_logic=logic; self.last_triggered_time = 0.0
        def __str__(self): return f"DummyTrigger({self.name})"
    class TriggerAction: pass
    JobManager = type("JobManager", (), {})

logger = logging.getLogger(__name__)

class TriggerList(ttk.Frame):

    def __init__(self, master, job_manager: 'JobManager', trigger_edit_callback=None): # type: ignore
        logger.debug("TriggerList __init__ called")
        super().__init__(master)

        if not _CoreClassesImported:
            ttk.Label(self, text="Error: Core classes missing. Trigger List unavailable.", foreground="red").pack(padx=20, pady=20)
            logger.error("TriggerList initialized in limited state due to missing core class imports.")
            self.job_manager: 'JobManager' | None = None # type: ignore
            self.trigger_edit_callback = None
            return

        if not isinstance(job_manager, JobManager):
            ttk.Label(self, text="Error: Invalid JobManager provided.", foreground="red").pack(padx=20,pady=20)
            logger.error("TriggerList received an invalid JobManager instance.")
            self.job_manager = None
            self.trigger_edit_callback = None
            return

        self.job_manager = job_manager
        self.trigger_edit_callback = trigger_edit_callback

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        columns = ("Name", "Conditions", "Action", "Interval", "Enabled")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended") # Changed selectmode

        col_configs = [
            ("Name", "Trigger Name", tk.W, True),
            ("Conditions", "Conditions Summary", tk.W, True),
            ("Action", "Action(s) Summary", tk.W, False),
            ("Interval", "Check Interval (s)", tk.E, False),
            ("Enabled", "Enabled", tk.CENTER, False),
        ]
        for col_name, text, anchor, stretch in col_configs:
            self.tree.heading(col_name, text=text, anchor=anchor)

        col_widths = {"Name": 180, "Conditions": 300, "Action": 200, "Interval": 100, "Enabled": 70}
        for col, width in col_widths.items():
            stretch_val = tk.YES if col in ["Name", "Conditions"] else tk.NO
            anchor_val = tk.W
            if col == "Enabled": anchor_val = tk.CENTER
            if col == "Interval": anchor_val = tk.E
            self.tree.column(col, width=width, minwidth=max(50, width // 2), anchor=anchor_val, stretch=stretch_val)

        self.tree.grid(row=0, column=0, padx=(5,0), pady=5, sticky="nsew")

        tree_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        tree_scrollbar.grid(row=0, column=1, sticky='ns', pady=5, padx=(0,5))
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

        button_row_frame = ttk.Frame(self)
        button_row_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=(5,10), sticky="ew")
        button_row_frame.grid_columnconfigure(0, weight=1)

        self.add_trigger_button = ttk.Button(button_row_frame, text="Add Trigger", command=self._add_trigger)
        self.add_trigger_button.grid(row=0, column=1, padx=3, sticky="e")
        self.edit_trigger_button = ttk.Button(button_row_frame, text="Edit Trigger", command=self._edit_selected_trigger)
        self.edit_trigger_button.grid(row=0, column=2, padx=3, sticky="e")
        self.delete_trigger_button = ttk.Button(button_row_frame, text="Delete Trigger", command=self._delete_selected_trigger)
        self.delete_trigger_button.grid(row=0, column=3, padx=3, sticky="e")
        self.enable_trigger_button = ttk.Button(button_row_frame, text="Enable/Disable", command=self._toggle_enable_selected_trigger)
        self.enable_trigger_button.grid(row=0, column=4, padx=3, sticky="e")

        self.tree.tag_configure('disabled', foreground='grey')

        self.tree.bind("<Double-1>", lambda e: self._edit_selected_trigger())
        self.tree.bind('<<TreeviewSelect>>', self._on_trigger_select)

        self._populate_triggers_list()
        self._update_trigger_buttons_state() 

        logger.debug("TriggerList UI built and initial population complete.")

    def _format_condition_summary(self, trigger: Trigger) -> str:
        if not trigger or not hasattr(trigger, 'conditions') or not trigger.conditions:
            return "(No Conditions)"
        try:
            max_cond_summary = 3
            summary_parts = []
            for i, cond in enumerate(trigger.conditions):
                if i >= max_cond_summary:
                    summary_parts.append("...")
                    break
                try:
                     cond_str = str(cond)
                     max_len = 40
                     summary_parts.append(f"({cond_str[:max_len]}{'...' if len(cond_str)>max_len else ''})")
                except:
                     summary_parts.append(f"({getattr(cond, 'type', '?')})")

            logic = f" {trigger.condition_logic} " if len(summary_parts) > 1 else ""
            return logic.join(summary_parts)
        except Exception as e:
            logger.error(f"Error formatting conditions for trigger '{trigger.name}': {e}")
            return "(Error)"

    def _format_action_summary(self, trigger: Trigger) -> str:
        if not trigger or not hasattr(trigger, 'actions') or not trigger.actions:
            return "(No Action)"
        elif len(trigger.actions) == 1:
            try:
                return str(trigger.actions[0])
            except Exception as e:
                logger.warning(f"Error formatting single action for trigger '{trigger.name}': {e}")
                action_obj = trigger.actions[0]
                return f"{getattr(action_obj, 'action_type', '?')}: '{getattr(action_obj, 'target', '?')}'"
        else:
            action_strs = []
            max_actions_to_show = 2
            for i, action in enumerate(trigger.actions):
                if i >= max_actions_to_show:
                    action_strs.append("...")
                    break
                try:
                    action_strs.append(str(action))
                except:
                    action_strs.append("(Error)")
            return "; ".join(action_strs)

    def _populate_triggers_list(self):
        if not self.job_manager:
            logger.warning("Cannot populate trigger list: JobManager is not available.")
            try:
                 for item in self.tree.get_children(): self.tree.delete(item)
            except tk.TclError: pass
            return

        selected_trigger_names = self.get_selected_trigger_names()
        logger.debug(f"Populating trigger list for profile '{self.job_manager.get_current_profile_name()}'...")

        try:
            for item in self.tree.get_children():
                self.tree.delete(item)

            all_trigger_names = sorted(self.job_manager.get_all_triggers())

            if not all_trigger_names:
                logger.debug("No triggers found in the current profile.")
                return

            for trigger_name in all_trigger_names:
                trigger = self.job_manager.get_trigger(trigger_name)
                if not isinstance(trigger, Trigger):
                    logger.warning(f"Skipping invalid trigger object found for name '{trigger_name}'.")
                    continue

                cond_summary = self._format_condition_summary(trigger)
                action_summary = self._format_action_summary(trigger)
                interval_text = f"{getattr(trigger, 'check_interval_seconds', '?'):.2f}"
                enabled_text = "Yes" if getattr(trigger, 'enabled', False) else "No"

                tags = []
                if not getattr(trigger, 'enabled', True): tags.append('disabled')

                self.tree.insert("", tk.END, iid=trigger_name,
                                   values=(trigger_name, cond_summary, action_summary, interval_text, enabled_text),
                                   tags=tuple(tags))

            if selected_trigger_names:
                items_to_select = [name for name in selected_trigger_names if self.tree.exists(name)]
                if items_to_select:
                    self.tree.selection_set(items_to_select)
                    self.tree.focus(items_to_select[0])

        except tk.TclError: logger.warning("TclError during _populate_triggers_list (Treeview might be gone)")
        except AttributeError as ae:
            logger.error(f"AttributeError populating trigger list: {ae}", exc_info=True)
            self.tree.insert("", tk.END, values=("Error populating list. Check logs.", "", "", "", ""))
        except Exception as e: logger.error(f"Error in _populate_triggers_list: {e}", exc_info=True)


    def get_selected_trigger_names(self) -> list[str]:
        try:
            selected_items = self.tree.selection()
            return list(selected_items) if selected_items else []
        except tk.TclError:
            return []

    def get_selected_trigger_name(self) -> str | None:
        selected_names = self.get_selected_trigger_names()
        return selected_names[0] if len(selected_names) == 1 else None

    def _add_trigger(self):
        if not self.job_manager: return
        if self.trigger_edit_callback:
            logger.info("Requesting add new trigger via callback.")
            try:
                self.trigger_edit_callback(None)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open trigger editor: {e}", parent=self)
                logger.error("Error calling trigger_edit_callback for add", exc_info=True)
        else:
            messagebox.showerror("Configuration Error", "Trigger editing function not available.", parent=self)

    def _edit_selected_trigger(self):
        selected_names = self.get_selected_trigger_names()
        if len(selected_names) != 1:
             messagebox.showwarning("Selection Error", "Please select exactly one trigger to edit.", parent=self)
             return
        trigger_name = selected_names[0]

        if trigger_name and self.trigger_edit_callback:
            logger.info(f"Requesting edit for trigger: {trigger_name}")
            try:
                self.trigger_edit_callback(trigger_name)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open trigger editor: {e}", parent=self)
                logger.error(f"Error calling trigger_edit_callback for edit '{trigger_name}'", exc_info=True)
        elif not trigger_name:
            messagebox.showwarning("No Selection", "Please select a trigger to edit.", parent=self)
        elif not self.trigger_edit_callback:
            messagebox.showerror("Configuration Error", "Trigger editing function not available.", parent=self)

    def _delete_selected_trigger(self):
        selected_names = self.get_selected_trigger_names()
        if not selected_names:
             messagebox.showwarning("No Selection", "Please select at least one trigger to delete.", parent=self)
             return
        if not self.job_manager: return

        count = len(selected_names)
        trigger_list_str = "\n - ".join(selected_names[:5])
        if count > 5: trigger_list_str += "\n - ..."
        msg = f"Are you sure you want to permanently delete {count} selected trigger(s)?\n\n{trigger_list_str}\n\nThis action cannot be undone."

        if messagebox.askyesno("Confirm Deletion", msg, icon='warning', parent=self):
            deleted_count = 0
            errors = []
            for trigger_name in selected_names:
                try:
                    logger.info(f"Attempting deletion of trigger: {trigger_name}")
                    if self.job_manager.delete_trigger(trigger_name):
                        deleted_count += 1
                 
                except Exception as e:
                    logger.error(f"Error deleting trigger '{trigger_name}': {e}", exc_info=True)
                    errors.append(f"'{trigger_name}': {e}")

            logger.info(f"Finished bulk trigger deletion. Deleted: {deleted_count}/{count}.")
            if errors:
                messagebox.showerror("Deletion Error", f"Errors occurred during deletion:\n" + "\n".join(errors[:3]) + ("\n..." if len(errors)>3 else ""), parent=self)
        
            self.refresh_trigger_list()

    def _toggle_enable_selected_trigger(self):
        selected_names = self.get_selected_trigger_names()
        if not selected_names:
             messagebox.showwarning("No Selection", "Please select at least one trigger to enable/disable.", parent=self)
             return
        if not self.job_manager: return

        target_state = True
        all_currently_enabled = True
        for name in selected_names:
             trigger = self.job_manager.get_trigger(name)
             if trigger and not trigger.enabled:
                 target_state = True
                 all_currently_enabled = False
                 break
        if all_currently_enabled:
             target_state = False

        action_verb = "Enabling" if target_state else "Disabling"
        logger.info(f"{action_verb} {len(selected_names)} selected triggers.")

        errors = []
        updated_count = 0
        for trigger_name in selected_names:
             try:
                 self.job_manager.enable_trigger(trigger_name, target_state)
                 updated_trigger = self.job_manager.get_trigger(trigger_name)
                 if updated_trigger and self.tree.exists(trigger_name):
                     enabled_text = "Yes" if updated_trigger.enabled else "No"
                     tags = [] if updated_trigger.enabled else ['disabled']
                     self.tree.set(trigger_name, column="Enabled", value=enabled_text)
                     self.tree.item(trigger_name, tags=tuple(tags))
                 updated_count += 1
             except Exception as e:
                 logger.error(f"Error toggling enable for trigger '{trigger_name}': {e}", exc_info=True)
                 errors.append(f"'{trigger_name}': {e}")
                 if self.tree.exists(trigger_name):
                      try:
                           updated_trigger_after_error = self.job_manager.get_trigger(trigger_name)
                           if updated_trigger_after_error:
                                enabled_text = "Yes" if updated_trigger_after_error.enabled else "No"
                                tags = [] if updated_trigger_after_error.enabled else ['disabled']
                                self.tree.set(trigger_name, column="Enabled", value=enabled_text)
                                self.tree.item(trigger_name, tags=tuple(tags))
                      except Exception as inner_e:
                           logger.error(f"Error refreshing trigger row '{trigger_name}' after error: {inner_e}")


        logger.info(f"Finished toggling trigger enable. Updated: {updated_count}/{len(selected_names)}.")
        if errors:
             messagebox.showerror("Toggle Enable Error", f"Errors occurred:\n" + "\n".join(errors[:3]) + ("\n..." if len(errors)>3 else ""), parent=self)

    def _on_trigger_select(self, event=None):
        self._update_trigger_buttons_state()

    def _update_trigger_buttons_state(self):
        selected_count = len(self.get_selected_trigger_names())

        edit_state = tk.NORMAL if selected_count == 1 else tk.DISABLED
        delete_state = tk.NORMAL if selected_count > 0 else tk.DISABLED
        enable_state = tk.NORMAL if selected_count > 0 else tk.DISABLED

        if hasattr(self, 'edit_trigger_button'): self.edit_trigger_button.config(state=edit_state)
        if hasattr(self, 'delete_trigger_button'): self.delete_trigger_button.config(state=delete_state)
        if hasattr(self, 'enable_trigger_button'): self.enable_trigger_button.config(state=enable_state)
        if hasattr(self, 'add_trigger_button'): self.add_trigger_button.config(state=tk.NORMAL)

    def refresh_trigger_list(self):
        logger.info("Refreshing trigger list display on demand.")
        self._populate_triggers_list()
        self._update_trigger_buttons_state() 

    def destroy(self):
         logger.debug("Destroying TriggerList frame.")
         super().destroy()
