# gui/job_list.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
import time

_CoreClassesImported = False
try:
    from core.job import Job
    from core.job_run_condition import JobRunCondition, InfiniteRunCondition, CountRunCondition, TimeRunCondition
    from core.job_manager import JobManager
    _CoreClassesImported = True
    logger = logging.getLogger(__name__)
    logger.debug("JobList: Core classes imported successfully.")
except ImportError:
    logger = logging.getLogger(__name__)
    logger.critical("JobList: FATAL ERROR loading core classes.")
    _CoreClassesImported = False
    class Job:
        def __init__(self, name="Dummy", hotkey="", stop_key="", enabled=True, run_condition=None, actions=None):
            self.name=name; self.hotkey=hotkey; self.stop_key=stop_key; self.enabled=enabled;
            self.run_condition=run_condition or type("DummyRunCond", (), {"type": "dummy"})()
            self.running=False; self.actions = actions or []
        def __str__(self): return f"DummyJob({self.name})"
    class JobRunCondition: type="dummy"
    class InfiniteRunCondition(JobRunCondition): TYPE = "infinite"
    class CountRunCondition(JobRunCondition): TYPE = "count";
    def __init__(self,p=None): self.params=p or {}
    class TimeRunCondition(JobRunCondition): TYPE = "time";
    def __init__(self,p=None): self.params=p or {}
    JobManager = type("JobManager", (), {})


logger = logging.getLogger(__name__)

class JobList(ttk.Frame):

    def __init__(self, master, job_manager: JobManager, job_edit_callback=None): # type: ignore
        logger.debug("JobList __init__ called")
        super().__init__(master)

        if not _CoreClassesImported:
            ttk.Label(self, text="Error: Core classes missing. Job List unavailable.", foreground="red").pack(padx=20,pady=20)
            logger.error("JobList initialized in limited state due to missing core class imports.")
            self.job_manager = None
            self._periodic_update_id = None
            return

        if not isinstance(job_manager, JobManager):
            ttk.Label(self, text="Error: Invalid JobManager provided.", foreground="red").pack(padx=20,pady=20)
            logger.error("JobList received an invalid JobManager instance.")
            self.job_manager = None
            self._periodic_update_id = None
            return

        self.job_manager = job_manager
        self.job_edit_callback = job_edit_callback
        self._periodic_update_id: str | None = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        columns = ("Name", "Mode", "Status", "Enabled", "Hotkey", "Stopkey", "Actions")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")

        col_configs = [
            ("Name", "Job Name", tk.W, True),
            ("Mode", "Run Mode", tk.W, False),
            ("Status", "Status", tk.CENTER, False),
            ("Enabled", "Enabled", tk.CENTER, False),
            ("Hotkey", "Hotkey", tk.W, False),
            ("Stopkey", "Stop Key", tk.W, False),
            ("Actions", "# Actions", tk.CENTER, False)
        ]
        for col_name, text, anchor, stretch in col_configs:
            self.tree.heading(col_name, text=text, anchor=anchor)

        col_widths = {"Name":220, "Mode":130, "Status":80, "Enabled":70, "Hotkey":100, "Stopkey":100, "Actions":70}
        for col, width in col_widths.items():
            stretch_val = tk.YES if col == "Name" else tk.NO
            anchor_val = tk.W if col not in ["Status", "Enabled", "Actions"] else tk.CENTER
            self.tree.column(col, width=width, minwidth=max(50, width // 2), anchor=anchor_val, stretch=stretch_val)

        self.tree.grid(row=0, column=0, padx=(5,0), pady=5, sticky="nsew")

        tree_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        tree_scrollbar.grid(row=0, column=1, sticky='ns', pady=5, padx=(0,5))
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

        button_row_frame = ttk.Frame(self)
        button_row_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=(5,10), sticky="ew")
        button_row_frame.grid_columnconfigure(0, weight=1)

        btn_config = [
            ("Add Job", self._add_job, 1),
            ("Edit Job", self._edit_selected_job, 2),
            ("Delete Job", self._delete_selected_job, 3),
            ("Enable/Disable", self._toggle_enable_selected_job, 4),
            ("Start/Stop Job", self._toggle_run_selected_job, 5)
        ]

        self.add_job_button = ttk.Button(button_row_frame, text="Add Job", command=self._add_job)
        self.add_job_button.grid(row=0, column=1, padx=3, sticky="e")
        self.edit_job_button = ttk.Button(button_row_frame, text="Edit Job", command=self._edit_selected_job)
        self.edit_job_button.grid(row=0, column=2, padx=3, sticky="e")
        self.delete_job_button = ttk.Button(button_row_frame, text="Delete Job", command=self._delete_selected_job)
        self.delete_job_button.grid(row=0, column=3, padx=3, sticky="e")
        self.enable_job_button = ttk.Button(button_row_frame, text="Enable/Disable", command=self._toggle_enable_selected_job)
        self.enable_job_button.grid(row=0, column=4, padx=3, sticky="e")
        self.run_job_button = ttk.Button(button_row_frame, text="Start/Stop Job", command=self._toggle_run_selected_job)
        self.run_job_button.grid(row=0, column=5, padx=3, sticky="e")


        self.tree.tag_configure('disabled', foreground='grey')
        try: self.tree.tag_configure('running', foreground='#006400', font=('TkDefaultFont', -12, 'bold'))
        except tk.TclError: self.tree.tag_configure('running', foreground='#006400')

        self.tree.bind("<Double-1>", lambda e: self._edit_selected_job())
        self.tree.bind('<<TreeviewSelect>>', self._on_job_select)
        self.bind("<Visibility>", self._on_visibility)
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)

        self._populate_jobs_list()
        self._update_job_buttons_state() 

        if self.winfo_ismapped():
            self._start_periodic_update()

        logger.debug("JobList UI built and initial population complete.")

    def _format_run_condition_text(self, condition: JobRunCondition | None) -> str:
        if not _CoreClassesImported or not isinstance(condition, JobRunCondition): return "Unknown"
        try:
            if condition.type == InfiniteRunCondition.TYPE: return "Infinite"
            elif condition.type == CountRunCondition.TYPE:
                count_val = condition.params.get('count', '?')
                count_str = '?'
                try: count_str = str(int(count_val))
                except (ValueError, TypeError): pass
                return f"Run {count_str} times"
            elif condition.type == TimeRunCondition.TYPE:
                dur_val = condition.params.get('duration', '?')
                dur_str = '?'
                try:
                    dur_f = float(dur_val)
                    if dur_f >= 60 and dur_f % 60 == 0: dur_str = f"{int(dur_f/60)}m"
                    elif dur_f >= 60: dur_str = f"{dur_f/60:.1f}m"
                    else: dur_str = f"{dur_f:.1f}s"
                except (ValueError, TypeError): dur_str = f"{dur_val}s"
                return f"Run for {dur_str}"
            return condition.type.replace("_", " ").title() if condition.type else "N/A"
        except Exception as e:
            logger.error(f"Error formatting run condition ({getattr(condition, 'type', '?')}): {e}")
            return "Error"

    def _populate_jobs_list(self):
        if not self.job_manager:
            logger.warning("Cannot populate job list: JobManager is not available.")
            try:
                 for item in self.tree.get_children(): self.tree.delete(item)
            except tk.TclError: pass
            return

        selected_job_names = self.get_selected_job_names()
        logger.debug(f"Populating job list for profile '{self.job_manager.get_current_profile_name()}'...")

        try:
            for item in self.tree.get_children():
                self.tree.delete(item)

            all_job_names = sorted(self.job_manager.get_all_jobs())

            if not all_job_names:
                logger.debug("No jobs found in the current profile.")
                return

            for job_name in all_job_names:
                job = self.job_manager.get_job(job_name)
                if not isinstance(job, Job):
                    logger.warning(f"Skipping invalid job object found for name '{job_name}'.")
                    continue

                run_cond_text = self._format_run_condition_text(job.run_condition)
                status_text = "Running" if self.job_manager.is_job_running(job_name) else "Stopped"
                enabled_text = "Yes" if job.enabled else "No"
                hotkey_text = job.hotkey or "-"
                stopkey_text = job.stop_key or "-"
                actions_count = len(job.actions) if isinstance(job.actions, list) else 0

                tags = []
                if not job.enabled: tags.append('disabled')
                if self.job_manager.is_job_running(job_name): tags.append('running')

                self.tree.insert("", tk.END, iid=job_name,
                                   values=(job_name, run_cond_text, status_text, enabled_text, hotkey_text, stopkey_text, actions_count),
                                   tags=tuple(tags))

            if selected_job_names:
                items_to_select = [name for name in selected_job_names if self.tree.exists(name)]
                if items_to_select:
                    self.tree.selection_set(items_to_select)
                    self.tree.focus(items_to_select[0])

        except tk.TclError: logger.warning("TclError during _populate_jobs_list (Treeview might be gone)")
        except Exception as e: logger.error(f"Error in _populate_jobs_list: {e}", exc_info=True)

    def _update_job_row(self, job_name: str):
        if not self.job_manager or not self.winfo_exists() or not self.tree.exists(job_name):
             return

        try:
            job = self.job_manager.get_job(job_name)
            if not isinstance(job, Job):
                logger.warning(f"Job '{job_name}' disappeared from manager? Removing from list.")
                if self.tree.exists(job_name): self.tree.delete(job_name)
                return

            run_cond_text = self._format_run_condition_text(job.run_condition)
            is_running = self.job_manager.is_job_running(job_name)
            status_text = "Running" if is_running else "Stopped"
            enabled_text = "Yes" if job.enabled else "No"
            hotkey_text = job.hotkey or "-"
            stopkey_text = job.stop_key or "-"
            actions_count = len(job.actions) if isinstance(job.actions, list) else 0
            new_values = (job_name, run_cond_text, status_text, enabled_text, hotkey_text, stopkey_text, actions_count)

            current_tags = set(self.tree.item(job_name, 'tags'))
            new_tags = set()
            if not job.enabled: new_tags.add('disabled')
            if is_running: new_tags.add('running')

            current_values_tuple = tuple(map(str, self.tree.item(job_name, 'values')))
            new_values_tuple = tuple(map(str, new_values))

            needs_update = False
            if current_values_tuple != new_values_tuple:
                self.tree.item(job_name, values=new_values)
                needs_update = True
            if current_tags != new_tags:
                self.tree.item(job_name, tags=list(new_tags))
                needs_update = True

        except tk.TclError: pass
        except Exception as e: logger.error(f"Error updating row for '{job_name}': {e}", exc_info=True)

    def _update_all_job_statuses(self):
        if not self.winfo_exists() or not self.winfo_viewable() or not self.job_manager:
            return

        try:
            current_tree_jobs = set(self.tree.get_children())
            manager_jobs = set(self.job_manager.get_all_jobs())

            to_remove = current_tree_jobs - manager_jobs
            to_add = manager_jobs - current_tree_jobs

            if to_remove or to_add:
                logger.info(f"Job list structure changed (Added: {len(to_add)}, Removed: {len(to_remove)}). Repopulating tree.")
                self._populate_jobs_list()
            else:
                for job_name in manager_jobs:
                    self._update_job_row(job_name)
        except tk.TclError: pass
        except Exception as e: logger.error(f"Error in _update_all_job_statuses: {e}", exc_info=True)

    def get_selected_job_names(self) -> list[str]:
        try:
            selected_items = self.tree.selection()
            return list(selected_items) if selected_items else []
        except tk.TclError:
            return []

    def get_selected_job_name(self) -> str | None:
        selected_names = self.get_selected_job_names()
        return selected_names[0] if len(selected_names) == 1 else None

    def _on_visibility(self, event=None):
        if self.winfo_exists() and self.winfo_viewable():
            logger.debug("JobList received <Visibility> event (visible). Starting updates.")
            self._update_all_job_statuses()
            self._start_periodic_update()
        else:
            logger.debug("JobList received <Visibility> event (not visible). Stopping updates.")
            self._stop_periodic_update()

    def _on_map(self, event=None):
        if self.winfo_exists():
            logger.debug("JobList received <Map> event. Starting updates.")
            self._update_all_job_statuses()
            self._start_periodic_update()

    def _on_unmap(self, event=None):
        logger.debug("JobList received <Unmap> event. Stopping updates.")
        self._stop_periodic_update()

    def _add_job(self):
        if not self.job_manager: return
        job_name = simpledialog.askstring("New Job", "Enter Name for New Job:", parent=self)
        if job_name and job_name.strip():
            job_name = job_name.strip()
            try:
                new_job = self.job_manager.create_job(job_name)
                if new_job:
                     self._populate_jobs_list()
                     self._select_job_by_name(new_job.name)
                     if self.job_edit_callback:
                         logger.info(f"Opening editor for newly created job '{new_job.name}'")
                         self.job_edit_callback(new_job.name)
                else:
                     logger.warning("JobManager.create_job succeeded but returned None?")
            except ValueError as e: messagebox.showerror("Creation Error", str(e), parent=self)
            except Exception as e: messagebox.showerror("Error", f"Failed to create job: {e}", parent=self); logger.error("Job creation failed", exc_info=True)
        elif job_name is not None:
            messagebox.showwarning("Input Error", "Job name cannot be empty.", parent=self)

    def _select_job_by_name(self, job_name: str):
         try:
             if self.tree.exists(job_name):
                  self.tree.selection_set([job_name]) # Select only this one
                  self.tree.focus(job_name)
                  self.tree.see(job_name)
         except tk.TclError: pass

    def _edit_selected_job(self):
        selected_names = self.get_selected_job_names()
        if len(selected_names) != 1:
            messagebox.showwarning("Selection Error", "Please select exactly one job to edit.", parent=self)
            return
        job_name = selected_names[0]

        if job_name and self.job_edit_callback:
            logger.info(f"Requesting edit for job: {job_name}")
            try: self.job_edit_callback(job_name)
            except Exception as e: messagebox.showerror("Error", f"Could not open editor: {e}", parent=self); logger.error("Error calling job_edit_callback", exc_info=True)
        elif not job_name: messagebox.showwarning("No Selection", "Please select a job to edit.", parent=self)
        elif not self.job_edit_callback: messagebox.showerror("Configuration Error", "Edit function not available.", parent=self)

    def _delete_selected_job(self):
        selected_names = self.get_selected_job_names()
        if not selected_names:
            messagebox.showwarning("No Selection", "Please select at least one job to delete.", parent=self)
            return
        if not self.job_manager: return

        count = len(selected_names)
        job_list_str = "\n - ".join(selected_names[:5])
        if count > 5: job_list_str += "\n - ..."
        msg = f"Are you sure you want to permanently delete {count} selected job(s)?\n\n{job_list_str}\n\nThis action cannot be undone."

        if messagebox.askyesno("Confirm Deletion", msg, icon='warning', parent=self):
            deleted_count = 0
            errors = []
            for job_name in selected_names:
                try:
                    logger.info(f"Attempting deletion of job: {job_name}")
                    self.job_manager.delete_job(job_name)
                    if self.tree.exists(job_name):
                        self.tree.delete(job_name)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting job '{job_name}': {e}", exc_info=True)
                    errors.append(f"'{job_name}': {e}")

            logger.info(f"Finished bulk job deletion. Deleted: {deleted_count}/{count}.")
            if errors:
                messagebox.showerror("Deletion Error", f"Errors occurred during deletion:\n" + "\n".join(errors[:3]) + ("\n..." if len(errors)>3 else ""), parent=self)
            self.tree.selection_set([])
            self.tree.focus("")
            self._update_job_buttons_state() 

    def _toggle_enable_selected_job(self):
        selected_names = self.get_selected_job_names()
        if not selected_names:
            messagebox.showwarning("No Selection", "Please select at least one job to enable/disable.", parent=self)
            return
        if not self.job_manager: return

        target_state = True
        all_currently_enabled = True
        for name in selected_names:
            job = self.job_manager.get_job(name)
            if job and not job.enabled:
                target_state = True
                all_currently_enabled = False
                break
        if all_currently_enabled:
            target_state = False

        action_verb = "Enabling" if target_state else "Disabling"
        logger.info(f"{action_verb} {len(selected_names)} selected jobs.")

        errors = []
        updated_count = 0
        for job_name in selected_names:
            try:
                self.job_manager.enable_job(job_name, target_state)
                self._update_job_row(job_name)
                updated_count += 1
            except Exception as e:
                logger.error(f"Error toggling enable for job '{job_name}': {e}", exc_info=True)
                errors.append(f"'{job_name}': {e}")
                if self.tree.exists(job_name): self._update_job_row(job_name)

        logger.info(f"Finished toggling enable. Updated: {updated_count}/{len(selected_names)}.")
        if errors:
            messagebox.showerror("Toggle Enable Error", f"Errors occurred:\n" + "\n".join(errors[:3]) + ("\n..." if len(errors)>3 else ""), parent=self)

    def _toggle_run_selected_job(self):
        selected_names = self.get_selected_job_names()
        if len(selected_names) != 1:
            messagebox.showwarning("Selection Error", "Please select exactly one job to start or stop.", parent=self)
            return

        job_name = selected_names[0]
        if not job_name or not self.job_manager: return
        try:
            logger.info(f"Toggling run state for job '{job_name}'")
            self.job_manager.toggle_job(job_name)
            self._update_job_row(job_name)
        except ValueError as e:
             messagebox.showwarning("Toggle Run Failed", str(e), parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle run state: {e}", parent=self)
            logger.error(f"Error toggling run state for '{job_name}'", exc_info=True)
            if self.tree.exists(job_name): self._update_job_row(job_name)


    def _on_job_select(self, event=None):
        self._update_job_buttons_state()

    def _update_job_buttons_state(self):
        selected_count = len(self.get_selected_job_names())

        edit_state = tk.NORMAL if selected_count == 1 else tk.DISABLED
        delete_state = tk.NORMAL if selected_count > 0 else tk.DISABLED
        enable_state = tk.NORMAL if selected_count > 0 else tk.DISABLED
        run_state = tk.NORMAL if selected_count == 1 else tk.DISABLED

        if hasattr(self, 'edit_job_button'): self.edit_job_button.config(state=edit_state)
        if hasattr(self, 'delete_job_button'): self.delete_job_button.config(state=delete_state)
        if hasattr(self, 'enable_job_button'): self.enable_job_button.config(state=enable_state)
        if hasattr(self, 'run_job_button'): self.run_job_button.config(state=run_state)
        if hasattr(self, 'add_job_button'): self.add_job_button.config(state=tk.NORMAL)


    def _start_periodic_update(self):
        if not self.winfo_exists(): return
        if self._periodic_update_id is None:
             logger.debug("Starting periodic update for JobList.")
             self._perform_periodic_update()

    def _stop_periodic_update(self):
        if self._periodic_update_id is not None:
            logger.debug("Stopping periodic update for JobList.")
            try:
                self.after_cancel(self._periodic_update_id)
            except tk.TclError: pass
            except Exception as e: logger.warning(f"Error cancelling after job: {e}")
            self._periodic_update_id = None

    def _perform_periodic_update(self):
        if not self.winfo_exists() or not self.winfo_viewable() or not self.job_manager:
            logger.debug("Periodic update stopping: widget not visible/exists or no manager.")
            self._periodic_update_id = None
            return

        self._update_all_job_statuses()

        update_interval_ms = 500
        try:
             self._periodic_update_id = self.after(update_interval_ms, self._perform_periodic_update)
        except tk.TclError:
            logger.warning("Failed to reschedule periodic update (widget likely destroyed).")
            self._periodic_update_id = None

    def refresh_job_list(self):
        logger.info("Refreshing job list display on demand.")
        self._populate_jobs_list()
        self._update_job_buttons_state() 

    def destroy(self):
         logger.debug("Destroying JobList frame.")
         self._stop_periodic_update()
         super().destroy()
