# gui/trigger_edit.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
import copy
import os
from typing import TYPE_CHECKING, Optional, List, Callable, Dict, Any

logger = logging.getLogger(__name__)

_CoreClassesImported = False
try:
    from core.trigger import Trigger, TriggerAction
    from core.condition import Condition, create_condition, NoneCondition
    from core.job_manager import JobManager
    _CoreClassesImported = True
except ImportError as e:
    _CoreClassesImported = False
    class Condition: id: Optional[str]; name: Optional[str]; type: str; is_monitored_by_ai_brain: bool # type: ignore
    def __init__(self, type_val:str="dummy_cond", params_val:Optional[Dict[str,Any]]=None, id_val:Optional[str]=None, name_val:Optional[str]=None, is_monitored:bool=False) -> None: self.type=type_val; self.id=id_val; self.name=name_val; self.is_monitored_by_ai_brain=is_monitored
    def to_dict(self) -> Dict[str,Any]: return {"id":self.id, "name":self.name, "type":self.type, "params":{}, "is_monitored_by_ai_brain":self.is_monitored_by_ai_brain}
    def create_condition(d: Dict[str,Any]) -> Optional[Condition]: return Condition(str(d.get("type")), d.get("params"), d.get("id"), d.get("name"), bool(d.get("is_monitored_by_ai_brain",False))) if isinstance(d, dict) else None
    class NoneCondition(Condition): TYPE="none"; # type: ignore
    def __init__(self,p:Optional[Dict[str,Any]]=None, id:Optional[str]=None, name:Optional[str]=None, is_monitored_by_ai_brain:bool=False) -> None: super().__init__("none",p,id,name,False)

    class TriggerAction:
        START_JOB="start_job"; STOP_JOB="stop_job"; PAUSE_JOB="pause_job"; RESUME_JOB="resume_job"; SWITCH_PROFILE="switch_profile"
        VALID_ACTIONS=[START_JOB, STOP_JOB, PAUSE_JOB, RESUME_JOB, SWITCH_PROFILE]
        action_type: str; target: str
        def __init__(self, action_type: str, target: Optional[str]) -> None: self.action_type = action_type; self.target = target.strip() if isinstance(target, str) else ""
        def to_dict(self) -> Dict[str,str]: return {"action_type": self.action_type, "target": self.target}
        @classmethod
        def from_dict(cls, data: Dict[str,Any]) -> 'TriggerAction': return cls(str(data.get("action_type")), data.get("target"))
        def __str__(self) -> str:
            target_display = self.target
            if self.action_type == self.STOP_JOB and self.target.lower() == "all": target_display = "All Running Jobs"
            elif not self.target:
                if self.action_type in [self.START_JOB, self.STOP_JOB, self.PAUSE_JOB, self.RESUME_JOB, self.SWITCH_PROFILE]: target_display = "(No Target Selected)"
                else: target_display = "(N/A)"
            return f"{self.action_type.replace('_', ' ').title()}: '{target_display}'"

    class Trigger:
        LOGIC_AND="AND"; LOGIC_OR="OR"; VALID_LOGICS=["AND","OR"]
        name:str; conditions: List[Condition]; actions: List[TriggerAction]; enabled:bool; check_interval_seconds:float; condition_logic:str; is_ai_trigger: bool
        def __init__(self, name:str, conditions: List[Condition], actions: Optional[List[TriggerAction]] = None, enabled:bool=True, interval:float=0.5, logic:str="AND", is_ai_trigger:bool=False) -> None:
            self.name=name; self.conditions=conditions or []; self.actions=actions if isinstance(actions,list) else []; self.enabled=enabled; self.check_interval_seconds=interval; self.condition_logic=logic; self.is_ai_trigger = is_ai_trigger
        def to_dict(self) -> Dict[str,Any]: return {"name": self.name, "conditions": [c.to_dict() for c in self.conditions if hasattr(c, 'to_dict')], "actions": [a.to_dict() for a in self.actions if hasattr(a,'to_dict')], "enabled":self.enabled, "check_interval_seconds":self.check_interval_seconds, "condition_logic":self.condition_logic, "is_ai_trigger": self.is_ai_trigger}
        @classmethod
        def from_dict(cls, data: Dict[str,Any]) -> 'Trigger':
            conds_data = data.get("conditions", [])
            acts_data = data.get("actions", [])
            conds = []
            if isinstance(conds_data, list):
                 conds = [obj for cd in conds_data if isinstance(cd, dict) and (obj := create_condition(cd)) is not None] # type: ignore
            acts = [TriggerAction.from_dict(ad) for ad in acts_data if isinstance(ad, dict)]
            return cls(str(data.get("name")), conds, acts, bool(data.get("enabled",True)), float(data.get("check_interval_seconds",0.5)), str(data.get("condition_logic","AND")), bool(data.get("is_ai_trigger",False))) # type: ignore
    class JobManager: # type: ignore
        def get_all_jobs(self) -> List[str]: return ["job_a", "job_b"]
        def list_available_profiles(self) -> List[str]: return ["profile1", "profile2"]
        def get_current_profile_name(self) -> str: return "profile1"
        def get_shared_condition_by_id(self, cond_id: str) -> Optional[Condition]:
            if cond_id == "monitored_cond_1": return Condition(id_val="monitored_cond_1", name_val="Monitored Cond 1", type_val="image_on_screen", is_monitored=True) # type: ignore
            return None
        def get_condition_display_map_for_ui(self) -> Dict[str, str]: return {"shared_cond_id_1": "Shared Cond 1 (TypeX)", "monitored_cond_1": "Monitored Cond 1 (Image)"}
        def add_trigger(self, trigger: Any) -> None: pass
        def update_trigger(self, old_name: str, trigger: Any) -> None: pass


_GuiComponentsImported = False
try:
    from gui.condition_settings import ConditionSettings
    from gui.select_target_dialog import SelectTargetDialog
    _GuiComponentsImported = True
except ImportError as e:
    _GuiComponentsImported = False
    class ConditionSettings(ttk.Frame): # type: ignore
        def __init__(self,m: tk.Misc ,condition_data:Optional[Dict[str,Any]]=None,image_storage:Any=None, exclude_types:Optional[List[str]]=None):super().__init__(m)
        def get_settings(self) -> Dict[str,Any]:return {"type":"none","params":{}}
        def set_settings(self,d: Dict[str,Any]) -> None: pass
        def destroy(self) -> None: super().destroy()
    class SelectTargetDialog(tk.Toplevel): # type: ignore
         selected_target: Optional[str]
         def __init__(self, parent: tk.Misc, target_list: List[str], dialog_title:str="", prompt:str=""): super().__init__(parent); self.selected_target=None; self.after(10, self.destroy)

try:
    from utils.image_storage import ImageStorage # type: ignore
    _ImageStorageImported = True
except ImportError:
    ImageStorage = type("ImageStorage", (), {}) # type: ignore
    _ImageStorageImported = False


class EditActionDialog(tk.Toplevel):
    job_manager: 'JobManager'; save_callback: Callable[[Dict[str, Any]], None]; current_action_data: Dict[str, Any]
    _selected_target_name: str; action_type_var: tk.StringVar; action_type_combo: ttk.Combobox
    target_display_var: tk.StringVar; target_display_entry: ttk.Entry; select_target_button: ttk.Button
    def __init__(self, parent: tk.Misc, current_action_data: Optional[Dict[str, Any]], job_manager: 'JobManager', save_callback: Callable[[Dict[str, Any]], None]) -> None: # type: ignore
        super().__init__(parent); self.transient(parent); self.grab_set(); self.resizable(False, False)
        self.job_manager = job_manager; self.save_callback = save_callback
        self.current_action_data = copy.deepcopy(current_action_data) if current_action_data else {"action_type": TriggerAction.START_JOB, "target": ""}
        self._selected_target_name = self.current_action_data.get("target", ""); self.title("Edit Trigger Action" if current_action_data else "Add Trigger Action")
        main_frame = ttk.Frame(self, padding=15); main_frame.pack(fill=tk.BOTH, expand=True); main_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(main_frame, text="Action Type:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.action_type_var = tk.StringVar(value=self.current_action_data.get("action_type", TriggerAction.START_JOB)); self.action_type_combo = ttk.Combobox(main_frame, textvariable=self.action_type_var, values=TriggerAction.VALID_ACTIONS, state="readonly", width=25); self.action_type_combo.grid(row=0, column=1, columnspan=2, sticky='ew', padx=5, pady=5); self.action_type_combo.bind("<<ComboboxSelected>>", self._on_type_changed_in_dialog)
        ttk.Label(main_frame, text="Target:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.target_display_var = tk.StringVar(value=self._selected_target_name or "(None Selected)"); self.target_display_entry = ttk.Entry(main_frame, textvariable=self.target_display_var, width=35, state='readonly'); self.target_display_entry.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        self.select_target_button = ttk.Button(main_frame, text="Select...", command=self._open_select_target_dialog_in_dialog, width=9); self.select_target_button.grid(row=1, column=2, sticky='e', padx=(5,0), pady=5)
        btn_frame = ttk.Frame(main_frame); btn_frame.grid(row=2, column=0, columnspan=3, pady=(15,0), sticky='e'); ttk.Button(btn_frame, text="Save Action", command=self._save).pack(side=tk.LEFT, padx=5); ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        self._update_target_button_state_in_dialog(); self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks(); parent_x = parent.winfo_rootx(); parent_y = parent.winfo_rooty(); parent_w = parent.winfo_width(); parent_h = parent.winfo_height(); dialog_w = self.winfo_reqwidth(); dialog_h = self.winfo_reqheight(); pos_x = parent_x + (parent_w // 2) - (dialog_w // 2); pos_y = parent_y + (parent_h // 2) - (dialog_h // 2); self.geometry(f"+{pos_x}+{pos_y}"); self.action_type_combo.focus_set()
    def _on_type_changed_in_dialog(self, event:Optional[tk.Event]=None) -> None: self._selected_target_name = ""; self._update_target_button_state_in_dialog()
    def _update_target_button_state_in_dialog(self) -> None:
        action_type = self.action_type_var.get(); needs_target = action_type in [TriggerAction.START_JOB, TriggerAction.STOP_JOB, TriggerAction.PAUSE_JOB, TriggerAction.RESUME_JOB, TriggerAction.SWITCH_PROFILE]; self.select_target_button.config(state=tk.NORMAL if needs_target else tk.DISABLED) # type: ignore
        display_text = (self._selected_target_name or "(None Selected)") if needs_target else "(N/A for this action)"; self.target_display_var.set(display_text)
        if not needs_target: self._selected_target_name = ""
    def _open_select_target_dialog_in_dialog(self) -> None:
        action_type = self.action_type_var.get(); target_list: List[str] = []; title = "Select Target"; prompt = "Select item:"
        if not self.job_manager: return
        try:
            if action_type in [TriggerAction.START_JOB, TriggerAction.STOP_JOB, TriggerAction.PAUSE_JOB, TriggerAction.RESUME_JOB]: target_list = sorted(self.job_manager.get_all_jobs()); title="Select Job"; prompt="Select Job:"; _ = action_type == TriggerAction.STOP_JOB and target_list.insert(0, "all") # type: ignore
            elif action_type == TriggerAction.SWITCH_PROFILE: all_profiles = self.job_manager.list_available_profiles(); current_profile = self.job_manager.get_current_profile_name(); target_list = sorted([p for p in all_profiles if p != current_profile]); title="Select Profile"; prompt="Select Profile:" # type: ignore
            else: return
            if not target_list: messagebox.showinfo("Info", f"No available targets for '{action_type}'.", parent=self); return
        except Exception as e: messagebox.showerror("Error", f"Could not retrieve target list:\n{e}", parent=self); return
        dialog = SelectTargetDialog(self, target_list, title, prompt); self.wait_window(dialog) # type: ignore
        if dialog.selected_target is not None: self._selected_target_name = dialog.selected_target; self.target_display_var.set(self._selected_target_name)
    def _save(self) -> None:
        action_type = self.action_type_var.get(); target = self._selected_target_name.strip()
        needs_target = action_type in [TriggerAction.START_JOB, TriggerAction.STOP_JOB, TriggerAction.PAUSE_JOB, TriggerAction.RESUME_JOB, TriggerAction.SWITCH_PROFILE]; is_target_valid = bool(target) or (action_type == TriggerAction.STOP_JOB and target.lower() == "all") # type: ignore
        if needs_target and not is_target_valid: messagebox.showerror("Input Error", f"A valid target must be selected for action type '{action_type}'.", parent=self); self.lift(); return
        if not needs_target: target = ""
        try: _ = TriggerAction(action_type, target); self.save_callback({"action_type": action_type, "target": target}); self.destroy()
        except ValueError as e: messagebox.showerror("Validation Error", str(e), parent=self); self.lift()
        except Exception as e: messagebox.showerror("Error", f"Could not save action:\n{e}", parent=self); self.lift()


class TriggerEdit(ttk.Frame):
    job_manager: 'JobManager'; original_trigger_name: Optional[str]; close_callback: Optional[Callable[[], None]]; image_storage: Optional['ImageStorage']; trigger: Trigger # type: ignore
    _condition_edit_window: Optional[tk.Toplevel]; _action_edit_dialog: Optional[EditActionDialog]
    name_entry: ttk.Entry; logic_var: tk.StringVar; interval_entry: ttk.Entry; enabled_var: tk.BooleanVar; is_ai_trigger_var: tk.BooleanVar
    condition_listbox: tk.Listbox; action_listbox: tk.Listbox; cond_frame: ttk.LabelFrame
    add_cond_button: ttk.Button; edit_cond_button: ttk.Button; delete_cond_button: ttk.Button
    add_action_button: ttk.Button; edit_action_button: ttk.Button; delete_action_button: ttk.Button
    save_button: ttk.Button; cancel_button: ttk.Button

    def __init__(self, master: tk.Misc, job_manager: 'JobManager', trigger_name: Optional[str] = None, # type: ignore
                 close_callback: Optional[Callable[[],None]] = None, image_storage: Optional['ImageStorage'] = None) -> None: # type: ignore
        super().__init__(master)
        if not _CoreClassesImported or not _GuiComponentsImported or not job_manager:
            if close_callback: close_callback()
            if hasattr(self, 'after'): self.after(10, self.destroy)
            return

        self.job_manager = job_manager; self.original_trigger_name = trigger_name; self.close_callback = close_callback; self.image_storage = image_storage
        self.trigger = None ; self._condition_edit_window = None; self._action_edit_dialog = None # type: ignore

        try:
            if self.original_trigger_name:
                trigger_to_edit = self.job_manager.get_trigger(self.original_trigger_name)
                if not trigger_to_edit: raise ValueError(f"Trigger '{self.original_trigger_name}' not found.")
                self.trigger = Trigger.from_dict(trigger_to_edit.to_dict()) # type: ignore
            else: self.trigger = Trigger(name="New Trigger", conditions=[], actions=[], is_ai_trigger=False) 
            if not isinstance(self.trigger, Trigger): raise TypeError("Failed to load or create Trigger object.") # type: ignore
        except Exception as e:
            messagebox.showerror("Trigger Load Error", f"Could not load or initialize trigger '{trigger_name}':\n{e}", parent=master)
            if self.close_callback: self.close_callback()
            if hasattr(self, 'after'): self.after(10, self.destroy)
            return

        self.grid_columnconfigure(0, weight=1); self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(1, weight=1)
        props_frame = ttk.LabelFrame(self, text="Trigger Properties", padding="5"); props_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=(10,5), sticky="ew"); props_frame.grid_columnconfigure(1, weight=1); props_row = 0
        ttk.Label(props_frame, text="Trigger Name:").grid(row=props_row, column=0, padx=5, pady=2, sticky=tk.W); self.name_entry = ttk.Entry(props_frame); self.name_entry.insert(0, self.trigger.name); self.name_entry.grid(row=props_row, column=1, columnspan=3, padx=5, pady=2, sticky="ew"); props_row += 1
        
        self.is_ai_trigger_var = tk.BooleanVar(value=self.trigger.is_ai_trigger)
        ai_trigger_check = ttk.Checkbutton(props_frame, text="AI Brain Trigger (Uses Monitored Condition States)", variable=self.is_ai_trigger_var, command=self._on_ai_trigger_toggle)
        ai_trigger_check.grid(row=props_row, column=0, columnspan=4, padx=5, pady=2, sticky="w"); props_row += 1

        ttk.Label(props_frame, text="Condition Logic:").grid(row=props_row, column=0, padx=5, pady=2, sticky=tk.W); self.logic_var = tk.StringVar(value=self.trigger.condition_logic)
        logic_and_radio = ttk.Radiobutton(props_frame, text="ALL met (AND)", variable=self.logic_var, value=Trigger.LOGIC_AND); logic_or_radio = ttk.Radiobutton(props_frame, text="ANY met (OR)", variable=self.logic_var, value=Trigger.LOGIC_OR) # type: ignore
        logic_and_radio.grid(row=props_row, column=1, padx=5, pady=1, sticky="w"); logic_or_radio.grid(row=props_row, column=2, padx=5, pady=1, sticky="w"); props_row += 1
        ttk.Label(props_frame, text="Check Interval (s):").grid(row=props_row, column=0, padx=5, pady=2, sticky=tk.W)
        vcmd_float = self.register(lambda P: P == "" or (P.count('.') <= 1 and P.replace('.', '', 1).isdigit() and float(P) >= 0.1) if P and P != "." else True)
        self.interval_entry = ttk.Entry(props_frame, width=8, validate="key", validatecommand=(vcmd_float, '%P')); self.interval_entry.insert(0, f"{self.trigger.check_interval_seconds:.2f}"); self.interval_entry.grid(row=props_row, column=1, padx=5, pady=2, sticky="w")
        self.enabled_var = tk.BooleanVar(value=self.trigger.enabled); enabled_check = ttk.Checkbutton(props_frame, text="Enabled", variable=self.enabled_var); enabled_check.grid(row=props_row, column=2, columnspan=2, padx=5, pady=2, sticky="w"); props_row += 1

        self.cond_frame = ttk.LabelFrame(self, text="Conditions", padding="5"); self.cond_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.cond_frame.grid_rowconfigure(0, weight=1); self.cond_frame.grid_columnconfigure(1, weight=1)
        cond_button_frame = ttk.Frame(self.cond_frame); cond_button_frame.grid(row=0, column=0, padx=(0,5), pady=0, sticky="ns")
        self.add_cond_button = ttk.Button(cond_button_frame, text="Add", command=self._add_condition, width=8); self.add_cond_button.pack(side=tk.TOP, fill="x", pady=2)
        self.edit_cond_button = ttk.Button(cond_button_frame, text="Edit", command=self._edit_selected_condition, width=8); self.edit_cond_button.pack(side=tk.TOP, fill="x", pady=2)
        self.delete_cond_button = ttk.Button(cond_button_frame, text="Del", command=self._delete_selected_condition, width=8); self.delete_cond_button.pack(side=tk.TOP, fill="x", pady=2)
        self.condition_listbox = tk.Listbox(self.cond_frame, selectmode=tk.EXTENDED, exportselection=False, height=8); self.condition_listbox.grid(row=0, column=1, sticky="nsew", pady=(0,5))
        cond_scrollbar = ttk.Scrollbar(self.cond_frame, orient="vertical", command=self.condition_listbox.yview); cond_scrollbar.grid(row=0, column=2, sticky="ns", pady=(0,5)); self.condition_listbox.configure(yscrollcommand=cond_scrollbar.set)
        self.condition_listbox.bind('<<ListboxSelect>>', self._on_condition_select); self.condition_listbox.bind("<Double-1>", lambda e: self._edit_selected_condition())

        action_frame = ttk.LabelFrame(self, text="Actions (What to do?)", padding="5"); action_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
        action_frame.grid_rowconfigure(0, weight=1); action_frame.grid_columnconfigure(1, weight=1)
        action_button_frame = ttk.Frame(action_frame); action_button_frame.grid(row=0, column=0, padx=(0,5), pady=0, sticky="ns")
        self.add_action_button = ttk.Button(action_button_frame, text="Add", command=self._add_action, width=8); self.add_action_button.pack(side=tk.TOP, fill="x", pady=2)
        self.edit_action_button = ttk.Button(action_button_frame, text="Edit", command=self._edit_selected_action, width=8); self.edit_action_button.pack(side=tk.TOP, fill="x", pady=2)
        self.delete_action_button = ttk.Button(action_button_frame, text="Del", command=self._delete_selected_action, width=8); self.delete_action_button.pack(side=tk.TOP, fill="x", pady=2)
        self.action_listbox = tk.Listbox(action_frame, selectmode=tk.EXTENDED, exportselection=False, width=50, height=8); self.action_listbox.grid(row=0, column=1, sticky="nsew", pady=(0,5))
        action_scrollbar = ttk.Scrollbar(action_frame, orient="vertical", command=self.action_listbox.yview); action_scrollbar.grid(row=0, column=2, sticky="ns", pady=(0,5)); self.action_listbox.configure(yscrollcommand=action_scrollbar.set)
        self.action_listbox.bind('<<ListboxSelect>>', self._on_action_select); self.action_listbox.bind("<Double-1>", lambda e: self._edit_selected_action())

        button_row_frame = ttk.Frame(self); button_row_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=(10,10), sticky="e")
        self.save_button = ttk.Button(button_row_frame, text="Save Trigger", command=self._save_trigger); self.save_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = ttk.Button(button_row_frame, text="Cancel", command=self._cancel); self.cancel_button.pack(side=tk.LEFT, padx=5)
        self._populate_conditions_listbox(); self._populate_actions_listbox(); self._update_condition_buttons_state(); self._update_action_buttons_state()
        self._on_ai_trigger_toggle(); self.update_idletasks()

    def _on_ai_trigger_toggle(self) -> None:
        is_ai = self.is_ai_trigger_var.get()
        if hasattr(self, 'cond_frame') and self.cond_frame.winfo_exists():
            if is_ai: self.cond_frame.config(text="AI Conditions (Select Monitored Shared Conditions)")
            else: self.cond_frame.config(text="Conditions (When to trigger?)")
        if self.trigger and hasattr(self.trigger, 'conditions') and isinstance(self.trigger.conditions, list):
            if messagebox.askyesno("Confirm Mode Change",
                                   "Changing trigger type will clear existing conditions for this trigger.\nDo you want to continue?",
                                   parent=self, icon='warning'):
                self.trigger.conditions.clear()
            else:   
                self.is_ai_trigger_var.set(not is_ai)
                if hasattr(self, 'cond_frame') and self.cond_frame.winfo_exists():
                    if not is_ai: self.cond_frame.config(text="AI Conditions (Select Monitored Shared Conditions)")
                    else: self.cond_frame.config(text="Conditions (When to trigger?)")
                return 

        self._populate_conditions_listbox()

    def get_selected_condition_indices(self) -> List[int]: return list(self.condition_listbox.curselection())
    def get_selected_action_indices(self) -> List[int]: return list(self.action_listbox.curselection())

    def _populate_conditions_listbox(self) -> None:
        self.condition_listbox.delete(0, tk.END)
        is_ai_mode = self.is_ai_trigger_var.get()
        
        if not self.trigger or not self.trigger.conditions:
            default_text = "(Click 'Add' to select Monitored Shared Conditions)" if is_ai_mode else "(No conditions added yet)"
            self.condition_listbox.insert(tk.END, default_text); self.condition_listbox.itemconfig(tk.END, {'fg': 'grey'});
        else:
            for i, condition_obj in enumerate(self.trigger.conditions):
                display_text = f"{i+1}. (Error displaying condition)"
                try:
                    cond_str = str(condition_obj); max_len = 80
                    if is_ai_mode and self.job_manager and hasattr(condition_obj, 'id') and isinstance(condition_obj.id, str):
                        shared_cond = self.job_manager.get_shared_condition_by_id(condition_obj.id) # type: ignore
                        if shared_cond and hasattr(shared_cond, 'name') and hasattr(shared_cond, 'type'):
                             cond_str = f"State of: {shared_cond.name} ({shared_cond.type})"
                             if not (hasattr(shared_cond, 'is_monitored_by_ai_brain') and shared_cond.is_monitored_by_ai_brain):
                                 cond_str += " [WARNING: Not Monitored by AI!]"
                        else: cond_str = f"Ref ID: {condition_obj.id} (Shared Condition Not Found or Invalid)"
                    display_text = f"{i+1}. {cond_str[:max_len]}{'...' if len(cond_str) > max_len else ''}"
                except Exception: pass
                self.condition_listbox.insert(tk.END, display_text)
        self._update_condition_buttons_state()

    def _on_condition_select(self, event:Optional[tk.Event]=None) -> None: self._update_condition_buttons_state()
    def _update_condition_buttons_state(self) -> None:
        selected_count = len(self.condition_listbox.curselection())
        edit_state = tk.NORMAL if selected_count == 1 else tk.DISABLED
        delete_state = tk.NORMAL if selected_count > 0 else tk.DISABLED
        if hasattr(self, 'edit_cond_button'): self.edit_cond_button.config(state=edit_state)
        if hasattr(self, 'delete_cond_button'): self.delete_cond_button.config(state=delete_state)
        if hasattr(self, 'add_cond_button'): self.add_cond_button.config(state=tk.NORMAL)

    def _add_condition(self) -> None:
        is_ai = self.is_ai_trigger_var.get()
        if is_ai:
            if self.job_manager:
                shared_cond_map = self.job_manager.get_condition_display_map_for_ui() # type: ignore
                monitored_shared_conds: Dict[str,str] = {
                    id_val: name for id_val, name in shared_cond_map.items()
                    if (cond_obj := self.job_manager.get_shared_condition_by_id(id_val)) and hasattr(cond_obj, 'is_monitored_by_ai_brain') and cond_obj.is_monitored_by_ai_brain # type: ignore
                }
                if not monitored_shared_conds: messagebox.showinfo("AI Trigger Condition", "No Shared Conditions are 'Monitored by AI Brain'.\nConfigure them in 'Shared Conditions' tab, then mark them for AI monitoring via 'AI Brain' tab.", parent=self); return
                sorted_display_names = sorted(list(monitored_shared_conds.values()), key=lambda s: s.lower())
                dialog = SelectTargetDialog(self.winfo_toplevel(), sorted_display_names, "Select Monitored Condition for AI Trigger", "This AI Trigger will check the state of:") # type: ignore
                self.winfo_toplevel().wait_window(dialog)
                if dialog.selected_target:
                    selected_display_name = dialog.selected_target; selected_id: Optional[str] = None
                    for id_val, disp_name in monitored_shared_conds.items():
                        if disp_name == selected_display_name: selected_id = id_val; break
                    if selected_id:
                        shared_cond_obj = self.job_manager.get_shared_condition_by_id(selected_id) # type: ignore
                        if shared_cond_obj and hasattr(shared_cond_obj, 'to_dict'):
                            condition_data_to_store = shared_cond_obj.to_dict()
                            self._save_edited_condition(None, condition_data_to_store)
            else: messagebox.showerror("Error", "JobManager not available.", parent=self); return
        else:
            default_condition_data = {"type": getattr(NoneCondition, 'TYPE', 'none'), "params": {}} # type: ignore
            self._open_condition_editor_window(None, default_condition_data)

    def _edit_selected_condition(self) -> None:
        selected_indices = self.get_selected_condition_indices()
        if len(selected_indices) != 1: messagebox.showwarning("Selection Error", "Please select exactly one condition to change/edit.", parent=self); return
        idx = selected_indices[0]
        if not self.trigger or idx >= len(self.trigger.conditions): messagebox.showerror("Error", "Invalid condition selection.", parent=self); return
        is_ai = self.is_ai_trigger_var.get()
        condition_to_edit_or_replace = self.trigger.conditions[idx]
        if is_ai:
            if self.job_manager:
                shared_cond_map = self.job_manager.get_condition_display_map_for_ui() # type: ignore
                monitored_shared_conds: Dict[str,str] = {
                    id_val: name for id_val, name in shared_cond_map.items()
                    if (cond_obj := self.job_manager.get_shared_condition_by_id(id_val)) and hasattr(cond_obj, 'is_monitored_by_ai_brain') and cond_obj.is_monitored_by_ai_brain # type: ignore
                }
                if not monitored_shared_conds: messagebox.showinfo("AI Trigger Condition", "No Shared Conditions are 'Monitored by AI Brain'.", parent=self); return
                sorted_display_names = sorted(list(monitored_shared_conds.values()), key=lambda s: s.lower())
                current_selected_display: Optional[str] = None
                if hasattr(condition_to_edit_or_replace, 'id') and condition_to_edit_or_replace.id in monitored_shared_conds: current_selected_display = monitored_shared_conds[condition_to_edit_or_replace.id]
                dialog = SelectTargetDialog(self.winfo_toplevel(), sorted_display_names, "Change Monitored Condition Reference", "Change to check state of:"); # type: ignore
                if current_selected_display and current_selected_display in sorted_display_names:
                    try: dialog.listbox.selection_set(sorted_display_names.index(current_selected_display)) # type: ignore
                    except tk.TclError: pass
                self.winfo_toplevel().wait_window(dialog)
                if dialog.selected_target:
                    selected_display_name = dialog.selected_target; new_selected_id: Optional[str] = None
                    for id_val, disp_name in monitored_shared_conds.items():
                        if disp_name == selected_display_name: new_selected_id = id_val; break
                    if new_selected_id:
                        shared_cond_obj = self.job_manager.get_shared_condition_by_id(new_selected_id) # type: ignore
                        if shared_cond_obj and hasattr(shared_cond_obj, 'to_dict'): self._save_edited_condition(idx, shared_cond_obj.to_dict())
            else: messagebox.showerror("Error", "JobManager not available.", parent=self); return
        else:
            try: condition_data_for_edit = condition_to_edit_or_replace.to_dict(); self._open_condition_editor_window(idx, condition_data_for_edit)
            except Exception as e: messagebox.showerror("Error", f"Failed to prepare condition for editing:\n{e}", parent=self)

    def _open_condition_editor_window(self, index: Optional[int], condition_data: Dict[str, Any]) -> None:
        if not _GuiComponentsImported: messagebox.showerror("Error", "Condition settings UI unavailable.", parent=self); return
        if self._condition_edit_window and self._condition_edit_window.winfo_exists():
            try: self._condition_edit_window.destroy()
            except Exception: pass
        editor_title = "Edit Regular Condition" if index is not None else "Add New Regular Condition"
        self._condition_edit_window = tk.Toplevel(self.winfo_toplevel()); self._condition_edit_window.title(editor_title)
        try: self._condition_edit_window.transient(self.winfo_toplevel())
        except tk.TclError: pass
        self._condition_edit_window.grab_set(); self._condition_edit_window.resizable(True, True); self._condition_edit_window.grid_columnconfigure(0, weight=1); self._condition_edit_window.grid_rowconfigure(0, weight=1)
        try:
            cs_frame = ConditionSettings(self._condition_edit_window, condition_data=condition_data, image_storage=self.image_storage, exclude_types=[]) # type: ignore
            cs_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        except Exception as e: messagebox.showerror("UI Error", f"Failed to open condition settings:\n{e}", parent=self._condition_edit_window if self._condition_edit_window else self); self._condition_edit_window.destroy(); return # type: ignore
        btn_frame = ttk.Frame(self._condition_edit_window); btn_frame.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="e")
        def save_cond_wrap() -> None:
            try: upd_data = cs_frame.get_settings(); self._save_edited_condition(index, upd_data); self._condition_edit_window.destroy() # type: ignore
            except ValueError as e_val: messagebox.showerror("Input Error", f"Invalid condition settings:\n{e_val}", parent=self._condition_edit_window if self._condition_edit_window else self); self._condition_edit_window.lift() # type: ignore
            except Exception as e_exc: messagebox.showerror("Error", f"Failed to save condition:\n{e_exc}", parent=self._condition_edit_window if self._condition_edit_window else self); self._condition_edit_window.lift() # type: ignore
        save_btn = ttk.Button(btn_frame, text="Save Condition", command=save_cond_wrap); save_btn.pack(side=tk.LEFT, padx=5); cancel_btn = ttk.Button(btn_frame, text="Cancel", command=lambda: self._condition_edit_window.destroy() if self._condition_edit_window else None); cancel_btn.pack(side=tk.LEFT, padx=5);
        if self._condition_edit_window: self._condition_edit_window.update_idletasks(); min_w = max(self._condition_edit_window.winfo_reqwidth(), 500); min_h = max(self._condition_edit_window.winfo_reqheight(), 550); self._condition_edit_window.minsize(min_w, min_h); self._condition_edit_window.protocol("WM_DELETE_WINDOW", lambda: self._condition_edit_window.destroy() if self._condition_edit_window else None)

    def _save_edited_condition(self, index: Optional[int], updated_condition_data: Dict[str, Any]) -> None:
        if not self.trigger or not isinstance(updated_condition_data, dict): return
        try:
            new_condition_obj = create_condition(updated_condition_data)
            if not isinstance(new_condition_obj, Condition): raise ValueError("Failed to create valid Condition object.") # type: ignore
            
            is_ai_mode = self.is_ai_trigger_var.get()
            if is_ai_mode and not new_condition_obj.is_monitored_by_ai_brain: # type: ignore
                 if not messagebox.askyesno("AI Trigger Warning", f"Condition '{new_condition_obj.name}' (ID: {new_condition_obj.id}) is not marked as 'Monitored by AI Brain'.\nAI Triggers rely on these for their state.\nAdd it to this AI Trigger anyway?", parent=self): return

            if index is None: self.trigger.conditions.append(new_condition_obj); new_idx = len(self.trigger.conditions) - 1
            else:
                if 0 <= index < len(self.trigger.conditions): self.trigger.conditions[index] = new_condition_obj; new_idx = index
                else: raise IndexError("Condition index out of bounds.")
            self._populate_conditions_listbox()
            if 0 <= new_idx < self.condition_listbox.size(): self.condition_listbox.selection_clear(0, tk.END); self.condition_listbox.selection_set(new_idx); self.condition_listbox.activate(new_idx); self.condition_listbox.see(new_idx)
            self._update_condition_buttons_state()
        except Exception as e: messagebox.showerror("Error", f"Failed to save condition internally:\n{e}", parent=self)

    def _delete_selected_condition(self) -> None:
        selected_indices = self.get_selected_condition_indices()
        if not selected_indices: messagebox.showwarning("No Selection", "Select condition(s) to delete.", parent=self); return
        if not self.trigger or not isinstance(self.trigger.conditions, list): return
        count = len(selected_indices); msg = f"Delete {count} selected condition(s)?"
        if messagebox.askyesno("Confirm Deletion", msg, icon='warning', parent=self):
            errors: List[str] = []; indices_to_delete = sorted(selected_indices, reverse=True)
            for idx in indices_to_delete:
                try:
                    if 0 <= idx < len(self.trigger.conditions): del self.trigger.conditions[idx]
                    else: errors.append(f"Index {idx+1} invalid.")
                except Exception as e: errors.append(f"Condition {idx+1}: {e}")
            self._populate_conditions_listbox()
            if errors: messagebox.showerror("Deletion Error", f"Errors:\n" + "\n".join(errors[:3]) + ("..." if len(errors)>3 else ""), parent=self)

    def _populate_actions_listbox(self) -> None:
        self.action_listbox.delete(0, tk.END)
        if not self.trigger or not self.trigger.actions: self.action_listbox.insert(tk.END, "(No actions added yet)"); self.action_listbox.itemconfig(tk.END, {'fg': 'grey'});
        else:
            for i, action in enumerate(self.trigger.actions):
                display_text = f"{i+1}. (Error display)"; 
                try: action_str = str(action); max_len = 60; display_text = f"{i+1}. {action_str[:max_len]}{'...' if len(action_str) > max_len else ''}"
                except Exception: pass; self.action_listbox.insert(tk.END, display_text)
        self._update_action_buttons_state()

    def _on_action_select(self, event:Optional[tk.Event]=None) -> None: self._update_action_buttons_state()
    def _update_action_buttons_state(self) -> None:
        selected_count = len(self.action_listbox.curselection()); edit_state = tk.NORMAL if selected_count == 1 else tk.DISABLED; delete_state = tk.NORMAL if selected_count > 0 else tk.DISABLED
        if hasattr(self, 'edit_action_button'): self.edit_action_button.config(state=edit_state)
        if hasattr(self, 'delete_action_button'): self.delete_action_button.config(state=delete_state)
        if hasattr(self, 'add_action_button'): self.add_action_button.config(state=tk.NORMAL)

    def _add_action(self) -> None:
        if self._action_edit_dialog and self._action_edit_dialog.winfo_exists():
             try: self._action_edit_dialog.lift(); self._action_edit_dialog.focus_force()
             except tk.TclError: self._action_edit_dialog = None; return
             return
        try: self._action_edit_dialog = EditActionDialog(self.winfo_toplevel(), None, self.job_manager, lambda new_action_data: self._save_edited_action(None, new_action_data)) # type: ignore
        except Exception as e: messagebox.showerror("UI Error", f"Could not open action editor:\n{e}", parent=self)

    def _edit_selected_action(self) -> None:
        selected_indices = self.get_selected_action_indices()
        if len(selected_indices) != 1: messagebox.showwarning("Selection Error", "Select one action to edit.", parent=self); return
        idx = selected_indices[0]
        if not self.trigger or not (0 <= idx < len(self.trigger.actions)): messagebox.showerror("Error", "Invalid action selection.", parent=self); self._populate_actions_listbox(); return
        if self._action_edit_dialog and self._action_edit_dialog.winfo_exists():
             try: self._action_edit_dialog.lift(); self._action_edit_dialog.focus_force()
             except tk.TclError: self._action_edit_dialog = None; return
             return
        try:
            action_to_edit = self.trigger.actions[idx]; action_data_for_edit = action_to_edit.to_dict()
            self._action_edit_dialog = EditActionDialog(self.winfo_toplevel(), action_data_for_edit, self.job_manager, lambda updated_action_data: self._save_edited_action(idx, updated_action_data)) # type: ignore
        except Exception as e: messagebox.showerror("Error", f"Failed to prepare action for editing:\n{e}", parent=self)

    def _save_edited_action(self, index: Optional[int], action_data: Dict[str, Any]) -> None:
        if not self.trigger: return
        try:
            action_obj = TriggerAction.from_dict(action_data); new_idx = -1 # type: ignore
            if index is None: self.trigger.actions.append(action_obj); new_idx = len(self.trigger.actions) - 1
            else:
                if 0 <= index < len(self.trigger.actions): self.trigger.actions[index] = action_obj; new_idx = index
                else: raise IndexError("Action index out of bounds.")
            self._populate_actions_listbox()
            if 0 <= new_idx < self.action_listbox.size(): self.action_listbox.selection_clear(0, tk.END); self.action_listbox.selection_set(new_idx); self.action_listbox.activate(new_idx); self.action_listbox.see(new_idx)
            self._update_action_buttons_state()
        except (ValueError, IndexError) as e: messagebox.showerror("Action Save Error", str(e), parent=self if not (self._action_edit_dialog and self._action_edit_dialog.winfo_exists()) else self._action_edit_dialog);_ = (self._action_edit_dialog and self._action_edit_dialog.winfo_exists() and self._action_edit_dialog.lift()) # type: ignore
        except Exception as e: messagebox.showerror("Error", f"Could not save action internally:\n{e}", parent=self if not (self._action_edit_dialog and self._action_edit_dialog.winfo_exists()) else self._action_edit_dialog);_ = (self._action_edit_dialog and self._action_edit_dialog.winfo_exists() and self._action_edit_dialog.lift()) # type: ignore

    def _delete_selected_action(self) -> None:
        selected_indices = self.get_selected_action_indices()
        if not selected_indices: messagebox.showwarning("No Selection", "Select action(s) to delete.", parent=self); return
        if not self.trigger or not isinstance(self.trigger.actions, list): return
        count = len(selected_indices); msg = f"Delete {count} selected action(s)?"
        if messagebox.askyesno("Confirm Deletion", msg, icon='warning', parent=self):
            errors: List[str] = []; indices_to_delete = sorted(selected_indices, reverse=True)
            for idx in indices_to_delete:
                try:
                    if 0 <= idx < len(self.trigger.actions): del self.trigger.actions[idx]
                    else: errors.append(f"Index {idx+1} invalid.")
                except Exception as e: errors.append(f"Action {idx+1}: {e}")
            self._populate_actions_listbox()
            if errors: messagebox.showerror("Deletion Error", f"Errors:\n" + "\n".join(errors[:3]) + ("..." if len(errors)>3 else ""), parent=self)

    def _save_trigger(self) -> None:
        if not self.trigger or not self.job_manager : return
        try:
            new_name = self.name_entry.get().strip(); new_logic = self.logic_var.get(); new_interval_str = self.interval_entry.get().strip(); new_enabled = self.enabled_var.get(); new_is_ai_trigger = self.is_ai_trigger_var.get()
            if not new_name: raise ValueError("Trigger name cannot be empty.")
            try: new_interval = float(new_interval_str) if new_interval_str else 0.5; _ = new_interval < 0.1 and (_ for _ in ()).throw(ValueError("Check Interval must be >= 0.1 seconds")) # type: ignore
            except ValueError as e_int: raise ValueError(f"Invalid Check Interval value: '{new_interval_str}'") from e_int
            for i, action in enumerate(self.trigger.actions):
                 if not isinstance(action, TriggerAction): raise ValueError(f"Internal error: Item at action index {i} is not a TriggerAction.") # type: ignore
                 action_requires_target = action.action_type in [TriggerAction.START_JOB, TriggerAction.STOP_JOB, TriggerAction.PAUSE_JOB, TriggerAction.RESUME_JOB, TriggerAction.SWITCH_PROFILE]; is_target_valid = bool(action.target) or (action.action_type == TriggerAction.STOP_JOB and action.target.lower() == "all") # type: ignore
                 if action_requires_target and not is_target_valid: raise ValueError(f"Action #{i+1} ({str(action)}) requires a valid target.")
            self.trigger.name = new_name; self.trigger.condition_logic = new_logic; self.trigger.enabled = new_enabled; self.trigger.check_interval_seconds = new_interval; self.trigger.is_ai_trigger = new_is_ai_trigger
            if self.original_trigger_name: self.job_manager.update_trigger(self.original_trigger_name, self.trigger) # type: ignore
            else: self.job_manager.add_trigger(self.trigger) # type: ignore
            if self.close_callback: self.close_callback()
            self.destroy()
        except ValueError as e: messagebox.showerror("Input Error", str(e), parent=self)
        except Exception as e: messagebox.showerror("Save Error", f"An unexpected error occurred:\n{e}", parent=self)

    def _cancel(self) -> None:
        if self.close_callback: self.close_callback()
        self.destroy()

    def destroy(self) -> None:
        trigger_name_for_log = "N/A";_ = (self.trigger and hasattr(self.trigger, 'name') and (trigger_name_for_log := self.trigger.name)) # type: ignore
        if self._condition_edit_window and self._condition_edit_window.winfo_exists():
             try: self._condition_edit_window.destroy()
             except Exception: pass
        if self._action_edit_dialog and self._action_edit_dialog.winfo_exists():
             try: self._action_edit_dialog.destroy()
             except Exception: pass
        super().destroy()
