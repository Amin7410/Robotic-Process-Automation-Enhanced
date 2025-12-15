# gui/main_window.py
import sys
import tkinter as tk
from tkinter import ttk, Menu
from tkinter import messagebox, simpledialog
import logging
import os
from gui.key_recorder import GlobalKeyboardHookManager 
from typing import TYPE_CHECKING, Any, Optional, List, Callable, Dict, Tuple

if TYPE_CHECKING:
    from gui.job_list import JobList
    from gui.trigger_list import TriggerList
    from gui.shared_condition_list import SharedConditionList
    from gui.shape_template_list import ShapeTemplateList
    from gui.ai_brain_management_tab import AIBrainManagementTab
    from gui.job_edit import JobEdit
    from gui.trigger_edit import TriggerEdit
    from core.job_manager import JobManager
    from utils.image_storage import ImageStorage
    from core.trigger import Trigger
    from core.condition import Condition


logger = logging.getLogger(__name__)

_GuiFramesImported = False
try:
    from gui.job_list import JobList
    from gui.job_edit import JobEdit
    from gui.trigger_list import TriggerList
    from gui.trigger_edit import TriggerEdit
    from gui.shared_condition_list import SharedConditionList
    from gui.shared_condition_edit_window import SharedConditionEditWindow
    from gui.shape_template_list import ShapeTemplateList
    from gui.shape_template_editor import ShapeTemplateEditor
    from gui.ai_brain_management_tab import AIBrainManagementTab
    _GuiFramesImported = True
except ImportError as e:
     _GuiFramesImported = False
     class JobList(ttk.Frame): # type: ignore
         def __init__(self, m: tk.Misc, jm: Any, jecb: Optional[Callable[[Optional[str]],None]]=None): super().__init__(m)
         def refresh_job_list(self) -> None:pass
         def _start_periodic_update(self) -> None: pass
         def _stop_periodic_update(self) -> None: pass
     class JobEdit(ttk.Frame): pass # type: ignore
     class TriggerList(ttk.Frame): # type: ignore
         def __init__(self, m: tk.Misc, jm: Any, tecb: Optional[Callable[[Optional[str]],None]]=None): super().__init__(m)
         def refresh_trigger_list(self) -> None:pass
         def _start_periodic_update(self) -> None: pass
         def _stop_periodic_update(self) -> None: pass
     class TriggerEdit(ttk.Frame): pass # type: ignore
     class SharedConditionList(ttk.Frame): # type: ignore
         def __init__(self, m: tk.Misc, jm: Any, cecb: Optional[Callable[[Optional[str]],None]]=None): super().__init__(m)
         def refresh_condition_list(self) -> None: pass
     class SharedConditionEditWindow(tk.Toplevel): pass # type: ignore
     class ShapeTemplateList(ttk.Frame): # type: ignore
         def __init__(self, m: tk.Misc, jm: Any, stecb: Optional[Callable[[Optional[str]],None]]=None): super().__init__(m)
         def refresh_template_list(self) -> None: pass
     class ShapeTemplateEditor(tk.Toplevel): pass # type: ignore
     class AIBrainManagementTab(ttk.Frame): 
        def __init__(self, m: tk.Misc, jm: Any): super().__init__(m); ttk.Label(self, text="AI Brain Tab N/A").pack()
        def refresh_ai_brain_view(self) -> None: pass
        def _start_periodic_update(self) -> None: pass
        def _stop_periodic_update(self) -> None: pass
        def set_callbacks(self, trigger_edit_cb: Any, shared_condition_edit_cb: Any) -> None: pass


try:
    from core.job_manager import JobManager, DEFAULT_PROFILE_NAME
    _JobManagerImported = True
except ImportError:
    JobManager = type("JobManager", (), {"get_current_profile_name": lambda s: "dummy", "list_available_profiles": lambda s: [], "config_loader": type("DummyCfg", (), {"profile_exists": lambda s, p: False})(), "observer": None, "condition_manager": None, "create_profile":lambda s,n,sw=False: False, "delete_profile":lambda s,n: False, "load_profile":lambda s,n,f=False: False, "get_shape_template_display_names": lambda s: {}, "set_ai_brain_mode": lambda s, e: None, "get_trigger": lambda s, tn: None, "enable_trigger": lambda s, tn, es: None, "delete_trigger": lambda s, tn: None, "get_shared_condition_by_id": lambda s,cid: None, "update_shared_condition": lambda s,cid,data:False, "add_shared_condition": lambda s,co: False, "handle_global_key_hook_state_change": lambda s, b: None}) # type: ignore
    DEFAULT_PROFILE_NAME = "default"
    _JobManagerImported = False
try:
    from utils.image_storage import ImageStorage
    _ImageStorageImported = True
except ImportError:
    ImageStorage = type("ImageStorage", (), {}) # type: ignore
    _ImageStorageImported = False

try:
    from core.trigger import Trigger
    from core.condition import Condition
    _CoreClassesHintImported = True
except ImportError:
     Trigger = type("Trigger", (), {}) # type: ignore
     Condition = type("Condition", (), {}) # type: ignore
     _CoreClassesHintImported = False


class SelectProfileDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, profile_list: List[str], title: str ="Select Profile to Delete"):
        super().__init__(parent)
        self.title(title); self.selected_profile: Optional[str] = None; self.profile_list = profile_list
        self.transient(parent); self.grab_set(); self.resizable(False, False)
        if hasattr(parent, 'winfo_exists') and parent.winfo_exists():
            parent.update_idletasks(); parent_x = parent.winfo_rootx(); parent_y = parent.winfo_rooty(); parent_w = parent.winfo_width(); parent_h = parent.winfo_height()
            self.update_idletasks(); dialog_w = self.winfo_reqwidth() + 40; dialog_h = self.winfo_reqheight() + 20
            pos_x = parent_x + (parent_w // 2) - (dialog_w // 2); pos_y = parent_y + (parent_h // 2) - (dialog_h // 2)
            self.geometry(f"+{pos_x}+{pos_y}")
        main_frame = ttk.Frame(self, padding="10"); main_frame.pack(fill="both", expand=True)
        ttk.Label(main_frame, text="Select the profile you want to delete:").pack(pady=(0, 5))
        list_frame = ttk.Frame(main_frame); list_frame.pack(fill="x", expand=True, pady=5)
        list_frame.grid_columnconfigure(0, weight=1); list_frame.grid_rowconfigure(0, weight=1)
        self.listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, exportselection=False, height=max(5, min(10, len(profile_list))))
        list_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview); self.listbox.configure(yscrollcommand=list_scrollbar.set)
        self.listbox.grid(row=0, column=0, sticky="nsew"); list_scrollbar.grid(row=0, column=1, sticky="ns")
        for profile in self.profile_list: self.listbox.insert(tk.END, profile)
        if self.profile_list: self.listbox.selection_set(0); self.listbox.activate(0)
        button_frame = ttk.Frame(main_frame); button_frame.pack(pady=(10, 0))
        delete_state = tk.NORMAL if self.profile_list else tk.DISABLED
        self.delete_button = ttk.Button(button_frame, text="Delete Selected", command=self._on_delete, state=delete_state); self.delete_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self._on_cancel); self.cancel_button.pack(side=tk.LEFT, padx=5)
        self.listbox.bind("<Double-1>", lambda e: self._on_delete()); self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        if self.listbox: self.listbox.focus_set()
    def _on_delete(self) -> None:
        selected_indices = self.listbox.curselection()
        if selected_indices: self.selected_profile = self.listbox.get(selected_indices[0]); self.destroy()
        else: messagebox.showwarning("No Selection", "Please select a profile from the list.", parent=self)
    def _on_cancel(self) -> None: self.selected_profile = None; self.destroy()


class MainWindow(ttk.Frame):
    master: tk.Tk
    job_manager: 'JobManager'  # type: ignore
    image_storage: 'ImageStorage'  # type: ignore
    menu_bar: Menu; profiles_menu: Menu; current_profile_var: tk.StringVar
    notebook: ttk.Notebook
    job_list_frame: Optional['JobList']
    job_edit_frame: Optional['JobEdit']
    trigger_list_frame: Optional['TriggerList']
    trigger_edit_frame: Optional['TriggerEdit']
    shape_template_list_frame: Optional['ShapeTemplateList']
    shared_condition_list_frame: Optional['SharedConditionList']
    ai_brain_management_frame: Optional['AIBrainManagementTab']
    status_bar_var: tk.StringVar; status_bar: ttk.Label
    ai_brain_enabled_var: tk.BooleanVar; ai_brain_toggle_button: ttk.Checkbutton

    def __init__(self, master: tk.Tk, job_manager: 'JobManager', image_storage: 'ImageStorage') -> None:  # type: ignore
        super().__init__(master)
        self.master = master
        self.job_manager = job_manager 
        self.image_storage = image_storage

        if not (_GuiFramesImported and _JobManagerImported and _ImageStorageImported and self.job_manager):
            logger.critical("MainWindow: Critical components missing or JobManager not initialized. Cannot create UI.")
            messagebox.showerror("Fatal Error", "Application cannot start due to missing critical components. Check logs.")
            if hasattr(self.master, 'destroy'): self.master.after(10, self.master.destroy)
            return

        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(0, weight=1)
        self.menu_bar = Menu(self.master); self.master.config(menu=self.menu_bar)
        file_menu = Menu(self.menu_bar, tearoff=0); self.menu_bar.add_cascade(label="File", menu=file_menu); file_menu.add_command(label="Exit", command=self._confirm_exit)
        self.profiles_menu = Menu(self.menu_bar, tearoff=0); self.menu_bar.add_cascade(label="Profiles", menu=self.profiles_menu); self._build_profiles_menu()
        tools_menu = Menu(self.menu_bar, tearoff=0); self.menu_bar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Create New Drawing Template...", command=self._open_shape_template_editor_for_new)
        tools_menu.add_command(label="Shared Condition Manager...", command=self._open_shared_condition_manager_tab)
        
        self.notebook = ttk.Notebook(self); self.notebook.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.job_list_frame = None; self.job_edit_frame = None; self.trigger_list_frame = None
        self.trigger_edit_frame = None; self.shape_template_list_frame = None; self.shared_condition_list_frame = None
        self.ai_brain_management_frame = None

        # Initialize tabs
        try: 
            if callable(JobList): self.job_list_frame = JobList(self.notebook, self.job_manager, job_edit_callback=self._show_job_edit)
            if self.job_list_frame: self.notebook.add(self.job_list_frame, text=" Job List ")
        except Exception as e: self._add_error_tab("Job List (Error)", f"Error loading Job List:\n{e}")
        
        try:
            if callable(ShapeTemplateList): self.shape_template_list_frame = ShapeTemplateList(self.notebook, self.job_manager, shape_template_edit_callback=self._show_shape_template_edit)
            if self.shape_template_list_frame: self.notebook.add(self.shape_template_list_frame, text=" Drawing Templates ")
        except Exception as e: self._add_error_tab("Drawing Templates (Error)", f"Error loading Drawing Templates:\n{e}")
        
        try:
            if callable(SharedConditionList): self.shared_condition_list_frame = SharedConditionList(self.notebook, self.job_manager, condition_edit_callback=self._show_shared_condition_edit)
            if self.shared_condition_list_frame: self.notebook.add(self.shared_condition_list_frame, text=" Shared Conditions ")
        except Exception as e: self._add_error_tab("Shared Conditions (Error)", f"Error loading Shared Conditions:\n{e}")
        
        try:
            if callable(AIBrainManagementTab): 
                self.ai_brain_management_frame = AIBrainManagementTab(self.notebook, self.job_manager)
                if self.ai_brain_management_frame and hasattr(self.ai_brain_management_frame, 'set_callbacks'):
                    self.ai_brain_management_frame.set_callbacks(trigger_edit_cb=self._show_trigger_edit, shared_condition_edit_cb=self._show_shared_condition_edit)
                if self.ai_brain_management_frame: self.notebook.add(self.ai_brain_management_frame, text=" AI Brain ")
        except ImportError: self._add_error_tab("AI Brain (Error)", "AI Brain UI component not found.")
        except Exception as e: self._add_error_tab("AI Brain (Error)", f"Error loading AI Brain tab:\n{e}")

        try: 
            if callable(TriggerList): self.trigger_list_frame = TriggerList(self.notebook, self.job_manager, trigger_edit_callback=self._show_trigger_edit)
            if self.trigger_list_frame: self.notebook.add(self.trigger_list_frame, text=" Triggers ")
        except Exception as e: self._add_error_tab("Triggers (Error)", f"Error loading Trigger List:\n{e}")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        status_frame = ttk.Frame(self); status_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0,5)); status_frame.grid_columnconfigure(0, weight=1)
        self.status_bar_var = tk.StringVar(); self.status_bar = ttk.Label(status_frame, textvariable=self.status_bar_var, relief=tk.SUNKEN, anchor=tk.W, padding=(5,2)); self.status_bar.grid(row=0, column=0, sticky="ew")
        self.ai_brain_enabled_var = tk.BooleanVar(value=False)
        self.ai_brain_toggle_button = ttk.Checkbutton(status_frame, text="AI Brain Active", variable=self.ai_brain_enabled_var, command=self._toggle_ai_brain_global_mode, style="Toolbutton")
        self.ai_brain_toggle_button.grid(row=0, column=1, padx=(10, 5))
        self._sync_ai_brain_button_from_manager_state(); self._update_status_bar()

        if self.job_manager and hasattr(self.job_manager, 'handle_global_key_hook_state_change') and callable(self.job_manager.handle_global_key_hook_state_change):
            GlobalKeyboardHookManager.add_hook_state_listener(
                self.job_manager.handle_global_key_hook_state_change
            )
            logger.info("MainWindow: Registered JobManager hook state listener.")
        else:
            logger.error("MainWindow: JobManager or its hook state handler is not available. Hotkey conflicts may occur with KeyRecorder.")

    def _add_error_tab(self, tab_name: str, error_message: str) -> None:
        try: 
            error_tab = ttk.Frame(self.notebook)
            ttk.Label(error_tab, text=error_message, foreground="red", wraplength=400).pack(padx=20, pady=20)
            self.notebook.add(error_tab, text=f" {tab_name} ")
        except Exception as e:
            logger.error(f"Failed to add error tab '{tab_name}': {e}")

    def _update_status_bar(self) -> None:
        try:
            if self.job_manager: self.status_bar_var.set(f" Current Profile: {self.job_manager.get_current_profile_name()} ")
            else: self.status_bar_var.set(" Error: JobManager unavailable ")
        except Exception as e: 
            self.status_bar_var.set(" Error getting profile ")
            logger.error(f"Error updating status bar: {e}")

    def _sync_ai_brain_button_from_manager_state(self) -> None:
        if hasattr(self, 'ai_brain_toggle_button') and self.ai_brain_toggle_button.winfo_exists():
            if self.job_manager and self.job_manager.observer and hasattr(self.job_manager.observer, 'ai_brain_mode_enabled'):
                try:
                    current_ai_mode_state = self.job_manager.observer.ai_brain_mode_enabled
                    self.ai_brain_enabled_var.set(current_ai_mode_state)
                    self.ai_brain_toggle_button.config(state=tk.NORMAL)
                except Exception as e: 
                    self.ai_brain_enabled_var.set(False)
                    self.ai_brain_toggle_button.config(state=tk.DISABLED)
                    logger.error(f"Error syncing AI brain button: {e}")
            else: 
                self.ai_brain_enabled_var.set(False)
                self.ai_brain_toggle_button.config(state=tk.DISABLED)

    def _build_profiles_menu(self) -> None:
        if not hasattr(self, 'profiles_menu') or not self.profiles_menu.winfo_exists(): return
        self.profiles_menu.delete(0, tk.END)
        self.profiles_menu.add_command(label="New Profile...", command=self._create_new_profile)
        self.profiles_menu.add_command(label="Delete Profile...", command=self._delete_profile)
        self.profiles_menu.add_separator()
        
        current_profile_name = DEFAULT_PROFILE_NAME
        available_profiles = []
        if self.job_manager:
            try:
                current_profile_name = self.job_manager.get_current_profile_name()
                available_profiles = self.job_manager.list_available_profiles()
            except Exception as e:
                logger.error(f"Error accessing profile info from JobManager: {e}")
        
        self.current_profile_var = tk.StringVar(value=current_profile_name)
        
        if not available_profiles:
            self.profiles_menu.add_command(label="(No profiles found)", state=tk.DISABLED)
            if self.job_manager and hasattr(self.job_manager, 'config_loader') and \
               self.job_manager.config_loader and \
               not self.job_manager.config_loader.profile_exists(DEFAULT_PROFILE_NAME):
                 if hasattr(self.job_manager, 'create_profile'):
                     try:
                         self.job_manager.create_profile(DEFAULT_PROFILE_NAME, switch_to_it=False)
                         if hasattr(self.job_manager, 'list_available_profiles'):
                            available_profiles = self.job_manager.list_available_profiles()

                     except Exception as e_create:
                         logger.error(f"Error auto-creating default profile: {e_create}")

        if available_profiles:
            for profile_name_iter in available_profiles:
                self.profiles_menu.add_radiobutton(
                    label=profile_name_iter, 
                    variable=self.current_profile_var, 
                    value=profile_name_iter, 
                    command=lambda name=profile_name_iter: self._switch_profile(name)
                )
        elif not self.profiles_menu.index(tk.END): 
            self.profiles_menu.add_command(label="(Default profile error)", state=tk.DISABLED)


    def _refresh_ui_after_profile_change(self) -> None:
        self._build_profiles_menu()
        self._update_status_bar()
        self._sync_ai_brain_button_from_manager_state()

        tabs_to_refresh_methods = {
            self.job_list_frame: 'refresh_job_list',
            self.trigger_list_frame: 'refresh_trigger_list',
            self.shape_template_list_frame: 'refresh_template_list',
            self.shared_condition_list_frame: 'refresh_condition_list',
            self.ai_brain_management_frame: 'refresh_ai_brain_view'
        }
        for frame, method_name in tabs_to_refresh_methods.items():
            if frame and hasattr(frame, method_name) and callable(getattr(frame, method_name)):
                try:
                    getattr(frame, method_name)()
                except Exception as e:
                    logger.error(f"Error calling {method_name} on {frame.__class__.__name__}: {e}")

        target_tab_frame = self.job_list_frame
        if target_tab_frame and hasattr(target_tab_frame, 'winfo_exists') and target_tab_frame.winfo_exists():
             try:
                 for i, tab_id in enumerate(self.notebook.tabs()):
                     if self.notebook.winfo_exists() and self.notebook.tabs() and self.notebook.nametowidget(tab_id) == target_tab_frame:
                         self.notebook.select(i)
                         break
             except Exception as e:
                 logger.error(f"Error selecting default tab: {e}")

    def _switch_profile(self, profile_name: str) -> None:
        if not self.job_manager: return
        current = self.job_manager.get_current_profile_name()
        if profile_name == current: return
        
        logger.info(f"Switching to profile: {profile_name}")
        self._close_all_edit_frames()
        success = False
        try:
            success = self.job_manager.load_profile(profile_name, force_reload=True) # Force reload is good here
        except Exception as e:
            logger.error(f"Exception during load_profile for '{profile_name}': {e}", exc_info=True)
            messagebox.showerror("Profile Load Error", f"Could not load profile '{profile_name}'.\nError: {e}", parent=self.master)
            if hasattr(self, 'current_profile_var'): self.current_profile_var.set(current) # Revert radio button
            return

        if success:
            self._refresh_ui_after_profile_change()
        else:
            messagebox.showerror("Profile Error", f"Could not load profile '{profile_name}'. Check logs for details.", parent=self.master)
            if hasattr(self, 'current_profile_var'): self.current_profile_var.set(current)

    def _create_new_profile(self) -> None:
        if not self.job_manager: return
        new_name = simpledialog.askstring("New Profile", "Enter name for the new profile:", parent=self.master)
        if new_name and new_name.strip():
            new_name = new_name.strip()
            if not all(c.isalnum() or c in ('_', '-') for c in new_name): 
                messagebox.showerror("Invalid Name", "Profile name can only contain letters, numbers, underscores, and hyphens.", parent=self.master)
                return
            if self.job_manager.config_loader and self.job_manager.config_loader.profile_exists(new_name): 
                messagebox.showwarning("Profile Exists", f"A profile named '{new_name}' already exists.", parent=self.master)
                return
            
            self._close_all_edit_frames()
            try:
                if self.job_manager.create_profile(new_name, switch_to_it=True):
                    messagebox.showinfo("Profile Created", f"Profile '{new_name}' created and activated.", parent=self.master)
                    self._refresh_ui_after_profile_change()
                else:
                    messagebox.showerror("Creation Error", f"Failed to create profile '{new_name}'.", parent=self.master)
            except Exception as e:
                logger.error(f"Exception during create_profile for '{new_name}': {e}", exc_info=True)
                messagebox.showerror("Creation Error", f"Error creating profile '{new_name}': {e}", parent=self.master)

        elif new_name is not None:
            messagebox.showwarning("Input Error", "Profile name cannot be empty.", parent=self.master)

    def _delete_profile(self) -> None:
        if not self.job_manager: return
        try:
            profiles = self.job_manager.list_available_profiles()
            current_profile = self.job_manager.get_current_profile_name()
        except Exception as e:
            logger.error(f"Error getting profile list for deletion: {e}")
            messagebox.showerror("Error", "Could not retrieve profile list.", parent=self.master)
            return

        deletable_profiles = [p for p in profiles if p != current_profile and p != DEFAULT_PROFILE_NAME]
        if not deletable_profiles:
            messagebox.showinfo("Delete Profile", "No other profiles available for deletion. Cannot delete the current or default profile.", parent=self.master)
            return
        
        dialog = SelectProfileDialog(self.master, deletable_profiles, title="Delete Profile")
        profile_to_delete = dialog.selected_profile 
        
        if profile_to_delete:
            if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to permanently delete the profile '{profile_to_delete}'?", icon='warning', parent=self.master):
                self._close_all_edit_frames()
                try:
                    if self.job_manager.delete_profile(profile_to_delete):
                        messagebox.showinfo("Profile Deleted", f"Profile '{profile_to_delete}' deleted.", parent=self.master)
                        self._refresh_ui_after_profile_change() 
                    else:
                        messagebox.showerror("Deletion Error", f"Failed to delete profile '{profile_to_delete}'. Check logs.", parent=self.master)
                except Exception as e:
                    logger.error(f"Exception during delete_profile for '{profile_to_delete}': {e}", exc_info=True)
                    messagebox.showerror("Deletion Error", f"Error deleting profile '{profile_to_delete}': {e}", parent=self.master)


    def _show_job_edit(self, job_name: Optional[str] = None) -> None:
        self._close_all_edit_frames(exclude="job")
        if not (_GuiFramesImported and 'JobEdit' in globals() and callable(JobEdit)): 
            messagebox.showerror("Error", "Job editing UI unavailable.", parent=self.master)
            return
        try: 
            self.job_edit_frame = JobEdit(self.notebook, self.job_manager, job_name=job_name, close_callback=self._show_default_list_view, image_storage=self.image_storage)
            tab_text = f" Edit Job: {job_name if job_name else 'New Job'} "
            self._add_or_select_edit_tab(self.job_edit_frame, tab_text)
        except Exception as e: 
            messagebox.showerror("Error", f"Failed to open job editor:\n{e}", parent=self.master)
            logger.error(f"Error opening job editor for '{job_name}': {e}", exc_info=True)
            self._close_job_edit_frame()

    def _show_trigger_edit(self, trigger_name: Optional[str] = None) -> None:
        self._close_all_edit_frames(exclude="trigger")
        if not (_GuiFramesImported and 'TriggerEdit' in globals() and callable(TriggerEdit)): 
            messagebox.showerror("Error", "Trigger editing UI unavailable.", parent=self.master)
            return
        try: 
            self.trigger_edit_frame = TriggerEdit(self.notebook, self.job_manager, trigger_name=trigger_name, close_callback=self._show_default_list_view, image_storage=self.image_storage)
            tab_text = f" Edit Trigger: {trigger_name if trigger_name else 'New Trigger'} "
            self._add_or_select_edit_tab(self.trigger_edit_frame, tab_text)
        except Exception as e: 
            messagebox.showerror("Error", f"Failed to open trigger editor:\n{e}", parent=self.master)
            logger.error(f"Error opening trigger editor for '{trigger_name}': {e}", exc_info=True)
            self._close_trigger_edit_frame()

    def _show_shape_template_edit(self, template_name: Optional[str] = None) -> None:
        self._close_all_edit_frames() 
        if not (_GuiFramesImported and 'ShapeTemplateEditor' in globals() and callable(ShapeTemplateEditor)): 
            messagebox.showerror("Error", "Shape Template editor UI unavailable.", parent=self.master)
            return
        try: 
            editor = ShapeTemplateEditor(self.master, self.job_manager, self.image_storage, template_name_to_edit=template_name, on_close_callback=self._on_shape_template_editor_closed)
        except Exception as e: 
            messagebox.showerror("Error", f"Failed to open Shape Template editor:\n{e}", parent=self.master)
            logger.error(f"Error opening shape template editor for '{template_name}': {e}", exc_info=True)


    def _on_shape_template_editor_closed(self) -> None:
        if self.shape_template_list_frame and hasattr(self.shape_template_list_frame, 'refresh_template_list'):
            try: self.shape_template_list_frame.refresh_template_list()
            except Exception as e: logger.error(f"Error refreshing shape template list after editor close: {e}")


    def _show_shared_condition_edit(self, condition_id: Optional[str] = None) -> None:
        self._close_all_edit_frames() 
        if not (_GuiFramesImported and 'SharedConditionEditWindow' in globals() and callable(SharedConditionEditWindow)): 
            messagebox.showerror("Error", "Shared Condition editor UI unavailable.", parent=self.master)
            return
        try: 
            editor = SharedConditionEditWindow(self.master, self.job_manager, self.image_storage, condition_to_edit_id=condition_id, on_close_callback=self._on_shared_condition_editor_closed)
        except Exception as e: 
            messagebox.showerror("Error", f"Failed to open Shared Condition editor:\n{e}", parent=self.master)
            logger.error(f"Error opening shared condition editor for ID '{condition_id}': {e}", exc_info=True)

    def _on_shared_condition_editor_closed(self) -> None:
        if self.shared_condition_list_frame and hasattr(self.shared_condition_list_frame, 'refresh_condition_list'):
            try: self.shared_condition_list_frame.refresh_condition_list()
            except Exception as e: logger.error(f"Error refreshing shared condition list after editor close: {e}")
        
        if self.ai_brain_management_frame and hasattr(self.ai_brain_management_frame, 'refresh_ai_brain_view'):
            try: getattr(self.ai_brain_management_frame, 'refresh_ai_brain_view')()
            except Exception as e: logger.error(f"Error refreshing AI brain view after shared condition editor close: {e}")


    def _add_or_select_edit_tab(self, frame_instance: ttk.Frame, tab_text: str) -> None:
        if not (frame_instance and hasattr(frame_instance, 'winfo_exists') and frame_instance.winfo_exists()):
            logger.error(f"Attempted to add/select an invalid frame instance for tab '{tab_text}'.")
            return
        try:
            existing_tab_id = None
            if self.notebook.winfo_exists() and self.notebook.tabs():
                for tab_id_iter in self.notebook.tabs():
                    try:
                        if self.notebook.nametowidget(tab_id_iter) == frame_instance:
                            existing_tab_id = tab_id_iter
                            break
                    except tk.TclError:
                        continue 
            
            if existing_tab_id:
                self.notebook.select(existing_tab_id)
            else:
                self.notebook.add(frame_instance, text=tab_text)
                self.notebook.select(self.notebook.tabs()[-1]) 
        except tk.TclError as e:
            logger.error(f"TclError adding or selecting edit tab '{tab_text}': {e}. Frame might have been destroyed.", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error adding or selecting edit tab '{tab_text}': {e}", exc_info=True)

    def _show_default_list_view(self) -> None:
        self._close_all_edit_frames()
        list_frames_to_refresh_methods = [
            (self.job_list_frame, 'refresh_job_list'),
            (self.trigger_list_frame, 'refresh_trigger_list'),
            (self.shape_template_list_frame, 'refresh_template_list'),
            (self.shared_condition_list_frame, 'refresh_condition_list'),
            (self.ai_brain_management_frame, 'refresh_ai_brain_view')
        ]
        for frame, method_name in list_frames_to_refresh_methods:
            if frame and hasattr(frame, method_name) and callable(getattr(frame, method_name)):
                try: getattr(frame, method_name)()
                except Exception as e: logger.error(f"Error calling {method_name} on {frame.__class__.__name__} during show_default_list_view: {e}")

        target_frame = self.job_list_frame
        if target_frame and hasattr(target_frame, 'winfo_exists') and target_frame.winfo_exists():
             try:
                 for i, tab_id in enumerate(self.notebook.tabs()):
                     if self.notebook.winfo_exists() and self.notebook.tabs() and self.notebook.nametowidget(tab_id) == target_frame:
                         self.notebook.select(i)
                         break
             except Exception as e:
                 logger.error(f"Error selecting default list view tab: {e}")

    def _close_job_edit_frame(self) -> None:
        if self.job_edit_frame and self.job_edit_frame.winfo_exists():
            try: 
                self.notebook.forget(self.job_edit_frame)
                self.job_edit_frame.destroy()
            except Exception as e: logger.error(f"Error closing job edit frame: {e}")
        self.job_edit_frame = None

    def _close_trigger_edit_frame(self) -> None:
        if self.trigger_edit_frame and self.trigger_edit_frame.winfo_exists():
            try: 
                self.notebook.forget(self.trigger_edit_frame)
                self.trigger_edit_frame.destroy()
            except Exception as e: logger.error(f"Error closing trigger edit frame: {e}")
        self.trigger_edit_frame = None

    def _close_all_edit_frames(self, exclude: Optional[str] = None) -> None:
        if exclude != "job": self._close_job_edit_frame()
        if exclude != "trigger": self._close_trigger_edit_frame()

    def _on_tab_changed(self, event: Optional[tk.Event]) -> None:
        selected_tab_widget = None
        try:
            selected_tab_id = self.notebook.select()
            if selected_tab_id and self.notebook.winfo_exists() and self.notebook.tabs():
                 selected_tab_widget = self.notebook.nametowidget(selected_tab_id)
        except tk.TclError:
            logger.warning("TclError getting selected tab in _on_tab_changed, widget might be destroyed.")
            return
        except Exception as e:
            logger.error(f"Error getting selected tab in _on_tab_changed: {e}")
            return

        list_frames_with_updates: List[Tuple[Optional[ttk.Frame], str]] = [
            (self.job_list_frame, "JobList"), 
            (self.trigger_list_frame, "TriggerList"), 
            (self.shared_condition_list_frame, "SharedConditionList"), 
            (self.shape_template_list_frame, "ShapeTemplateList"), 
            (self.ai_brain_management_frame, "AIBrainManagementTab")
        ]
        
        for frame, name in list_frames_with_updates:
            if frame and hasattr(frame, 'winfo_exists') and frame.winfo_exists():
                is_selected = (selected_tab_widget == frame)
                
                start_method_name = '_start_periodic_update'
                stop_method_name = '_stop_periodic_update'
                refresh_method_name = None 

                if name == "AIBrainManagementTab": 
                    refresh_method_name = 'refresh_ai_brain_view'
                
                try:
                    if hasattr(frame, start_method_name) and hasattr(frame, stop_method_name):
                        if is_selected:
                            if callable(getattr(frame, start_method_name)): getattr(frame, start_method_name)()
                            if refresh_method_name and callable(getattr(frame, refresh_method_name)):
                                getattr(frame, refresh_method_name)() 
                        else:
                            if callable(getattr(frame, stop_method_name)): getattr(frame, stop_method_name)()
                    elif is_selected and refresh_method_name and hasattr(frame, refresh_method_name) and callable(getattr(frame, refresh_method_name)):
                        getattr(frame, refresh_method_name)()
                except Exception as e_tab_cb:
                    logger.error(f"Error in tab change callback for {name}: {e_tab_cb}")


    def _toggle_ai_brain_global_mode(self) -> None:
        if self.job_manager:
            new_ai_mode_state = self.ai_brain_enabled_var.get()
            try: 
                self.job_manager.set_ai_brain_mode(new_ai_mode_state)
                logger.info(f"AI Brain global mode toggled to {new_ai_mode_state} by UI.")
            except Exception as e: 
                messagebox.showerror("Error", f"Failed to toggle AI Brain mode: {e}", parent=self)
                if hasattr(self, 'ai_brain_enabled_var'): self.ai_brain_enabled_var.set(not new_ai_mode_state) # Revert UI
                logger.error(f"Error toggling AI Brain mode via UI: {e}")
        else: 
            self.ai_brain_enabled_var.set(False)
            if hasattr(self, 'ai_brain_toggle_button'): self.ai_brain_toggle_button.config(state=tk.DISABLED)


    def _confirm_exit(self) -> None:
         if self.job_manager and hasattr(self.job_manager, 'handle_global_key_hook_state_change') and callable(self.job_manager.handle_global_key_hook_state_change):
             GlobalKeyboardHookManager.remove_hook_state_listener(
                 self.job_manager.handle_global_key_hook_state_change
             )
             logger.info("MainWindow: Unregistered JobManager hook state listener before exit.")

         if hasattr(self.master, '_main_app_on_closing_handler') and callable(self.master._main_app_on_closing_handler): # type: ignore
             self.master._main_app_on_closing_handler() # type: ignore
         elif hasattr(self.master, 'destroy') and callable(self.master.destroy): # Fallback
             self.master.destroy()
         else: 
            sys.exit(0)


    def destroy(self) -> None:
            logger.debug("MainWindow: Destroying...")
            list_frames_with_updates: List[Optional[ttk.Frame]] = [
                self.job_list_frame, 
                self.trigger_list_frame, 
                self.shared_condition_list_frame, 
                self.shape_template_list_frame, 
                self.ai_brain_management_frame
            ]
            for frame in list_frames_with_updates:
                if frame and hasattr(frame, '_stop_periodic_update') and callable(getattr(frame, '_stop_periodic_update')):
                    try:
                        getattr(frame, '_stop_periodic_update')()
                    except Exception as e:
                        logger.warning(f"Error stopping periodic update for {frame.__class__.__name__} during destroy: {e}")

            if self.job_manager and hasattr(self.job_manager, 'handle_global_key_hook_state_change') and callable(self.job_manager.handle_global_key_hook_state_change):
                GlobalKeyboardHookManager.remove_hook_state_listener(
                    self.job_manager.handle_global_key_hook_state_change
                ) 
            
            super().destroy()
            logger.info("MainWindow destroyed.")

    def _open_shape_template_editor_for_new(self) -> None:
        if not (_GuiFramesImported and _JobManagerImported and _ImageStorageImported and self.job_manager and self.image_storage and 'ShapeTemplateEditor' in globals() and callable(ShapeTemplateEditor)): 
            messagebox.showerror("Error", "Required components are missing or not initialized.", parent=self.master)
            return
        try: 
            editor = ShapeTemplateEditor(self.master, self.job_manager, self.image_storage, template_name_to_edit=None, on_close_callback=self._on_shape_template_editor_closed)
        except Exception as e: 
            messagebox.showerror("Error", f"Could not open Drawing Template Editor:\n{e}", parent=self.master)
            logger.error(f"Error opening new shape template editor: {e}", exc_info=True)


    def _open_shared_condition_manager_tab(self) -> None:
        target_frame = self.shared_condition_list_frame
        if target_frame and hasattr(target_frame, 'winfo_exists') and target_frame.winfo_exists():
             try:
                 for i, tab_id in enumerate(self.notebook.tabs()):
                     if self.notebook.winfo_exists() and self.notebook.tabs() and self.notebook.nametowidget(tab_id) == target_frame:
                         self.notebook.select(i)
                         logger.debug("Switched to Shared Conditions tab.")
                         return
                 logger.warning("Shared Conditions tab not found in notebook.")
             except Exception as e:
                 logger.error(f"Error switching to Shared Conditions tab: {e}")
        else:
            logger.warning("Shared Conditions list frame does not exist or is not available.")
