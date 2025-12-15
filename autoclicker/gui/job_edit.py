# gui/job_edit.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
import copy
import os
from typing import Optional, Dict, List, Any, Callable

logger = logging.getLogger(__name__)

_CoreClassesImported = False
try:
    from core.job import Job
    from core.job_run_condition import JobRunCondition, create_job_run_condition
    from core.action import Action, create_action
    _CoreClassesImported = True
except ImportError:
    logger.critical("FATAL ERROR: Core classes (Job, Action, JobRunCondition) could not be imported in JobEdit.")
    _CoreClassesImported = False
    class Job:
        def __init__(self, name, actions=None, hotkey="", stop_key="", enabled=True, run_condition=None, params=None): # Added params
            self.name=name
            self.actions=actions or []
            self.hotkey=hotkey
            self.stop_key=stop_key
            self.enabled=enabled
            self.run_condition=run_condition or (create_job_run_condition(None) if 'create_job_run_condition' in globals() else None)
            self.running=False
            self.params = params or {}
        def to_dict(self): return {
            "name": self.name,
            "actions": [a.to_dict() for a in self.actions if hasattr(a,'to_dict')],
            "hotkey": self.hotkey,
            "stop_key": self.stop_key,
            "enabled": self.enabled,
            "run_condition": self.run_condition.to_dict() if hasattr(self.run_condition, 'to_dict') else None,
            "params": self.params 
            }
    class Action:
        def __init__(self, type="dummy", params=None, condition_id=None, next_action_index_if_condition_met=None, next_action_index_if_condition_not_met=None, is_absolute=False): # Added is_absolute
            self.type=type
            self.params=params or {}
            self.condition_id=condition_id
            self.next_action_index_if_condition_met=next_action_index_if_condition_met
            self.next_action_index_if_condition_not_met=next_action_index_if_condition_not_met
            self.is_absolute = is_absolute 
        def to_dict(self): return {
            "type": self.type,
            "params": self.params,
            "condition_id": self.condition_id,
            "next_action_index_if_condition_met": self.next_action_index_if_condition_met,
            "next_action_index_if_condition_not_met": self.next_action_index_if_condition_not_met,
            "is_absolute": self.is_absolute 
            }
    class JobRunCondition: pass
    def create_job_run_condition(data): return JobRunCondition()
    def create_action(data):
        return Action(data.get("type","dummy"),
                      data.get("params",{}),
                      data.get("condition_id"),
                      data.get("next_action_index_if_condition_met"),
                      data.get("next_action_index_if_condition_not_met"),
                      data.get("is_absolute", False)
                      )


_GuiComponentsImported = False
try:
    from gui.job_run_condition_settings import JobRunConditionSettings
    from gui.action_edit_window import ActionEditWindow
    from gui.key_recorder import KeyRecorder
    from gui.select_target_dialog import SelectTargetDialog
    _GuiComponentsImported = True
except ImportError:
    logger.error("Could not import GUI components for JobEdit. Editing limited.")
    _GuiComponentsImported = False
    class JobRunConditionSettings(ttk.Frame):
        def __init__(self,m,i=None):super().__init__(m); ttk.Label(self,text="JRC Settings N/A").pack()
        def get_settings(self):return {"type":"infinite","params":{}}
        def set_settings(self, data): pass 
    class ActionEditWindow(tk.Toplevel):
        def __init__(self,m,action_data: Dict[str, Any],save_callback: Callable[[Dict[str, Any]], None],job_manager: Any,image_storage: Optional[Any] = None):super().__init__(m); ttk.Label(self,text="AEW N/A").pack(); self.after(100,self.destroy)
    from gui.key_recorder import KeyRecorder
    class SelectTargetDialog(tk.Toplevel):
        def __init__(self, parent, target_list, dialog_title, prompt): super().__init__(parent); ttk.Label(self, text="SelectTargetDialog N/A").pack(); self.selected_target = None; self.after(100, self.destroy)


_ImageStorageImported = False
try:
    from utils.image_storage import ImageStorage
    _ImageStorageImported = True
except ImportError:
    logger.warning("ImageStorage import failed for JobEdit.")
    _ImageStorageImported = False
    class ImageStorage: pass


logger = logging.getLogger(__name__)
DRAG_THRESHOLD = 5

class JobEdit(ttk.Frame):
    def __init__(self, master, job_manager, job_name: str = None, close_callback=None, image_storage: Optional[ImageStorage] = None):
        super().__init__(master)
        if not _CoreClassesImported or not _GuiComponentsImported:
            messagebox.showerror("Initialization Error", "JobEdit cannot start due to missing core or GUI components.", parent=master)
            if close_callback: close_callback()
            self.after(10, self.destroy)
            return

        self.job_manager = job_manager
        self.original_job_name = job_name
        self.close_callback = close_callback
        self.image_storage = image_storage
        self.job: Optional[Job] = None
        self.is_dragging = False

        try:
            if self.original_job_name:
                job_to_edit = self.job_manager.get_job(self.original_job_name)
                if not job_to_edit: raise ValueError(f"Job '{self.original_job_name}' not found.")
                self.job = copy.deepcopy(job_to_edit)
                logger.info(f"JobEdit initialized for editing job: '{self.job.name}'.")
            else:
                self.job = Job(name="New Job", params={"delay_between_runs_s": 0.01}) # Add default params
                logger.info("JobEdit initialized for creating a new job.")
            if not isinstance(self.job, Job): raise TypeError("Failed to load or create Job object.")
        except Exception as e:
            logger.error(f"Error initializing JobEdit with job '{job_name}': {e}", exc_info=True)
            messagebox.showerror("Job Load Error", f"Could not load job '{job_name}':\n{e}", parent=master)
            if self.close_callback: self.close_callback()
            self.after(10, self.destroy)
            return

        style = ttk.Style()
        style.configure("Selected.TFrame", background="lightblue", borderwidth=1, relief=tk.SOLID)
        style.configure("TFrame", borderwidth=1, relief=tk.FLAT)


        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)

        props_frame = ttk.LabelFrame(self, text="Job Properties", padding="5")
        props_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=(10,5), sticky="ew")
        props_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(props_frame, text="Job Name:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.name_entry = ttk.Entry(props_frame)
        self.name_entry.insert(0, self.job.name)
        self.name_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(props_frame, text="Hotkey:").grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
        self.hotkey_recorder = KeyRecorder(props_frame, initial_key=self.job.hotkey)
        self.hotkey_recorder.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(props_frame, text="Stop Key:").grid(row=2, column=0, padx=5, pady=2, sticky=tk.W)
        self.stopkey_recorder = KeyRecorder(props_frame, initial_key=self.job.stop_key)
        self.stopkey_recorder.grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        run_cond_frame = ttk.LabelFrame(self, text="Job Run Condition", padding="5")
        run_cond_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        run_cond_frame.grid_columnconfigure(0, weight=1)
        initial_rc_data = self.job.run_condition.to_dict() if self.job.run_condition and hasattr(self.job.run_condition, 'to_dict') else {"type":"infinite","params":{}}
        self.run_condition_settings = JobRunConditionSettings(run_cond_frame, initial_condition_data=initial_rc_data)
        self.run_condition_settings.grid(row=0, column=0, sticky="ew")

        job_params_frame = ttk.LabelFrame(self, text="Job Parameters", padding="5")
        job_params_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        job_params_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(job_params_frame, text="Delay Between Runs (s):").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.vcmd_float_non_negative = self.register(lambda P: P == "" or (P.count('.') <= 1 and P.replace('.', '', 1).isdigit() and float(P) >= 0) if P and P != "." else True)
        self.delay_between_runs_entry = ttk.Entry(job_params_frame, width=10, validate="key", validatecommand=(self.vcmd_float_non_negative, '%P'))
        delay_val = self.job.params.get("delay_between_runs_s", 0.01)
        self.delay_between_runs_entry.insert(0, str(delay_val if delay_val is not None else 0.01))
        self.delay_between_runs_entry.grid(row=0, column=1, padx=5, pady=2, sticky="w")


        ttk.Label(self, text="Actions:").grid(row=3, column=0, padx=5, pady=(10,2), sticky=tk.SW)

        actions_area_frame = ttk.Frame(self)
        actions_area_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=5) 
        actions_area_frame.grid_columnconfigure(1, weight=1)
        actions_area_frame.grid_rowconfigure(0, weight=1)

        action_buttons_frame = ttk.Frame(actions_area_frame)
        action_buttons_frame.grid(row=0, column=0, padx=(0,5), pady=0, sticky="ns")
        self.add_action_button = ttk.Button(action_buttons_frame, text="Add Action", command=self._add_action_ui, width=12)
        self.add_action_button.pack(side=tk.TOP, fill="x", pady=2)
        self.add_drawing_block_button = ttk.Button(action_buttons_frame, text="Add Drawing", command=self._add_drawing_block_ui, width=12)
        self.add_drawing_block_button.pack(side=tk.TOP, fill="x", pady=2)
        self.edit_action_button = ttk.Button(action_buttons_frame, text="Edit Action", command=self._edit_selected_action, width=12)
        self.edit_action_button.pack(side=tk.TOP, fill="x", pady=2)
        self.delete_action_button = ttk.Button(action_buttons_frame, text="Delete Action", command=self._delete_selected_action, width=12)
        self.delete_action_button.pack(side=tk.TOP, fill="x", pady=2)
        self.copy_button = ttk.Button(action_buttons_frame, text="Copy Action", command=self._copy_selected_action, width=12)
        self.copy_button.pack(side=tk.TOP, fill="x", pady=2)
        self.paste_button = ttk.Button(action_buttons_frame, text="Paste After", command=self._paste_action_after, width=12)
        self.paste_button.pack(side=tk.TOP, fill="x", pady=2)

        self.actions_list_frame = ttk.Frame(actions_area_frame)
        self.actions_list_frame.grid(row=0, column=1, sticky="nsew")
        self.actions_list_frame.grid_rowconfigure(0, weight=1)
        self.actions_list_frame.grid_columnconfigure(0, weight=1)
        self.action_canvas = tk.Canvas(self.actions_list_frame, highlightthickness=0, borderwidth=1, relief="sunken")
        self.action_scrollbar = ttk.Scrollbar(self.actions_list_frame, orient="vertical", command=self.action_canvas.yview)
        self.scrollable_actions_frame = ttk.Frame(self.action_canvas)
        self._scrollable_frame_window_id = self.action_canvas.create_window((0, 0), window=self.scrollable_actions_frame, anchor="nw")
        self.action_canvas.configure(yscrollcommand=self.action_scrollbar.set)
        self.scrollable_actions_frame.bind("<Configure>", self._on_scrollable_frame_configure)
        self.action_canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_mouse_wheel(self.action_canvas)
        self._bind_mouse_wheel(self.scrollable_actions_frame)
        self.action_canvas.grid(row=0, column=0, sticky="nsew")
        self.action_scrollbar.grid(row=0, column=1, sticky="ns")

        self._selected_action_indices: set[int] = set()
        self._last_single_selected_index: int = -1
        self._drag_data = {"widget": None, "start_y": 0, "source_index": -1, "indicator": None}
        self._copied_action_data: Optional[Dict[str, Any]] = None

        self.action_context_menu = tk.Menu(self, tearoff=0)
        self._build_action_context_menu()

        button_row_frame = ttk.Frame(self)
        button_row_frame.grid(row=5, column=0, columnspan=2, padx=5, pady=(10,10), sticky="e") # Adjusted row
        self.save_button = ttk.Button(button_row_frame, text="Save Job", command=self._save_job)
        self.save_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = ttk.Button(button_row_frame, text="Cancel", command=self._cancel)
        self.cancel_button.pack(side=tk.LEFT, padx=5)

        self._populate_actions_ui()
        self._update_action_buttons_state()
        self.update_idletasks()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        canvas_width = self.action_canvas.winfo_width()
        if hasattr(self,'_scrollable_frame_window_id') and self._scrollable_frame_window_id:
            if canvas_width > 1:
                self.action_canvas.itemconfigure(self._scrollable_frame_window_id, width=canvas_width)
        self.action_canvas.after_idle(self._update_scroll_region)

    def _on_scrollable_frame_configure(self, event: tk.Event) -> None:
        self.action_canvas.after_idle(self._update_scroll_region)

    def _update_scroll_region(self) -> None:
        if hasattr(self,'action_canvas') and self.action_canvas.winfo_exists() and \
           hasattr(self,'scrollable_actions_frame') and self.scrollable_actions_frame.winfo_exists():
            self.scrollable_actions_frame.update_idletasks()
            content_height = self.scrollable_actions_frame.winfo_reqheight()
            canvas_width = self.action_canvas.winfo_width()
            self.action_canvas.configure(scrollregion=(0, 0, canvas_width, max(1, content_height)))

    def _bind_mouse_wheel(self, widget: tk.Widget) -> None:
        if widget and widget.winfo_exists():
            try:
                widget.bind("<MouseWheel>", self._on_mousewheel, add='+')
                widget.bind("<Button-4>", self._on_mousewheel, add='+')
                widget.bind("<Button-5>", self._on_mousewheel, add='+')
            except tk.TclError:
                pass

    def _unbind_mouse_wheel(self, widget: tk.Widget) -> None:
        if widget and widget.winfo_exists():
            try:
                widget.unbind("<MouseWheel>")
                widget.unbind("<Button-4>")
                widget.unbind("<Button-5>")
            except tk.TclError:
                pass

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        target_canvas = self.action_canvas
        if hasattr(target_canvas, 'winfo_exists') and target_canvas.winfo_exists():
            try:
                scroll_direction = 0
                if event.num == 5 or event.delta < 0:
                    scroll_direction = 1
                elif event.num == 4 or event.delta > 0:
                    scroll_direction = -1
                if scroll_direction != 0:
                    target_canvas.yview_scroll(scroll_direction, "units")
                    return "break"
            except tk.TclError:
                pass
            except Exception as e:
                logger.error(f"JobEdit Error in _on_mousewheel: {e}", exc_info=True)
        return None

    def _populate_actions_ui(self) -> None:
        if hasattr(self, 'scrollable_actions_frame') and self.scrollable_actions_frame.winfo_exists():
            for widget in list(self.scrollable_actions_frame.winfo_children()):
                self._unbind_mouse_wheel(widget)
                widget.destroy()
        else:
            if hasattr(self, 'action_canvas') and self.action_canvas.winfo_exists():
                self.action_canvas.after_idle(self._update_scroll_region)
            return

        self._clear_drag_indicator()

        if not self.job or not isinstance(self.job.actions, list):
            if hasattr(self, 'scrollable_actions_frame') and self.scrollable_actions_frame.winfo_exists():
                ttk.Label(self.scrollable_actions_frame, text="Error loading actions or no actions defined.", foreground="red").pack(pady=10)
            if hasattr(self, 'scrollable_actions_frame') and self.scrollable_actions_frame.winfo_exists():
                self.scrollable_actions_frame.update_idletasks()
            if hasattr(self, 'action_canvas') and self.action_canvas.winfo_exists():
                self.action_canvas.after_idle(self._update_scroll_region)
            return

        for i, action_obj in enumerate(self.job.actions):
            if not isinstance(action_obj, Action):
                continue

            action_row_frame = ttk.Frame(self.scrollable_actions_frame, padding=(5,3), borderwidth=1, style="TFrame")
            action_row_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(1,0))
            action_row_frame.action_index = i
            summary = self._get_action_summary(action_obj, i)
            action_label = ttk.Label(action_row_frame, text=summary, anchor="w", cursor="hand2")
            action_label.pack(side=tk.LEFT, fill="x", expand=True, padx=(0,5))

            for widget in [action_row_frame, action_label]:
                widget.bind("<ButtonPress-1>", lambda e, idx=i: self._on_drag_start(e, idx))
                widget.bind("<B1-Motion>", self._on_drag_motion)
                widget.bind("<ButtonRelease-1>", lambda e, idx=i: self._handle_action_release(e, idx))
                widget.bind("<Button-3>", lambda e, idx=i: self._show_action_context_menu(e, idx))
                widget.bind("<Button-2>", lambda e, idx=i: self._show_action_context_menu(e, idx))
                self._bind_mouse_wheel(widget)

        self._update_selection_appearance()

        if hasattr(self, 'scrollable_actions_frame') and self.scrollable_actions_frame.winfo_exists():
            self.scrollable_actions_frame.update_idletasks()

        if hasattr(self, 'action_canvas') and self.action_canvas.winfo_exists():
            self.action_canvas.after_idle(self._update_scroll_region)

    def _get_action_summary(self, action: Action, index: int) -> str:
        if not isinstance(action, Action): return f"{index+1}. Invalid Action"
        summary_parts = []

        action_type_display = action.type.replace("_", " ").title()
        summary = f"{index+1}. {action_type_display}"

        params = action.params if isinstance(action.params, dict) else {}

        if action.type == 'click':
            summary_parts.extend([f"X:{params.get('x','?')},Y:{params.get('y','?')}", f"{str(params.get('button','left')).capitalize()}", f"{params.get('click_type','single')}"])
        elif action.type == 'press_key':
            summary_parts.append(f"Key: {params.get('key','?')}")
        elif action.type == 'wait':
            summary_parts.append(f"{params.get('duration','1.0')}s")
        elif action.type == 'move_mouse':
            summary_parts.extend([f"To X:{params.get('x','?')},Y:{params.get('y','?')}", f"Dur:{params.get('duration','0.1')}s"])
        elif action.type == 'drag':
            summary_parts.extend([f"From X:{params.get('x','?')},Y:{params.get('y','?')}", f"To X:{params.get('swipe_x','?')},Y:{params.get('swipe_y','?')}", f"Btn:{params.get('button','left')}"])
        elif action.type == 'scroll':
            summary_parts.extend([f"Amt:{params.get('scroll_amount','?')}", f"Dir:{params.get('direction','vert')}"])
        elif action.type in ['key_down', 'key_up']:
            summary_parts.append(f"{action.type.split('_')[1].capitalize()}: {params.get('key','?')}")
        elif action.type == 'text_entry':
            text = str(params.get('text',''))
            summary_parts.append(f"Text: '{text[:15]}{'...' if len(text)>15 else ''}'")
        elif action.type == 'modified_key_stroke':
            summary_parts.extend([f"Mod: {params.get('modifier','?')}", f"Main: {params.get('main_key','?')}" ])

        delay_before = params.get('delay_before', 0.0)
        if isinstance(delay_before, (int, float)) and delay_before > 0:
             summary_parts.append(f"PreDelay:{delay_before}s")

        if summary_parts:
            summary += f" ({', '.join(p for p in summary_parts if p)})"

        condition_display = ""
        if action.condition_id and self.job_manager:
            cond_obj = self.job_manager.get_shared_condition_by_id(action.condition_id)
            if cond_obj:
                condition_display = f"If: {cond_obj.name[:20]}{'...' if len(cond_obj.name)>20 else ''} ({cond_obj.type[:15]})"
            else:
                condition_display = f"If: ID '{action.condition_id[:8]}...' (Not Found)"

        jump_info = []
        if action.next_action_index_if_condition_met is not None:
            jump_info.append(f"Met -> Act {action.next_action_index_if_condition_met+1}")
        if action.next_action_index_if_condition_not_met is not None:
            jump_info.append(f"NotMet -> Act {action.next_action_index_if_condition_not_met+1}")

        flow_control_display = ""
        if jump_info:
            flow_control_display = f"Then: ({'; '.join(jump_info)})"

        absolute_indicator = ""
        if hasattr(action, 'is_absolute') and action.is_absolute:
            absolute_indicator = " [ABS]"


        final_summary = summary

        flow_parts = []
        if condition_display: flow_parts.append(condition_display)
        if flow_control_display: flow_parts.append(flow_control_display)

        if flow_parts:
            final_summary += " [" + " | ".join(flow_parts) + "]"

        final_summary += absolute_indicator

        return final_summary

    def _update_selection_appearance(self) -> None:
        all_frames = self._get_action_row_frames()
        for i, frame in enumerate(all_frames):
            if frame.winfo_exists():
                if i in self._selected_action_indices:
                    frame.configure(style="Selected.TFrame")
                else:
                    frame.configure(style="TFrame")

    def get_selected_action_indices(self) -> List[int]:
        return sorted(list(self._selected_action_indices))

    def _get_action_row_frames(self) -> List[ttk.Frame]:
        if hasattr(self,'scrollable_actions_frame') and self.scrollable_actions_frame.winfo_exists():
            return [w for w in self.scrollable_actions_frame.winfo_children() if isinstance(w, ttk.Frame) and hasattr(w, 'action_index')]
        return []

    def _build_action_context_menu(self) -> None:
        self.action_context_menu.add_command(label="Edit", command=self._edit_selected_action)
        self.action_context_menu.add_command(label="Copy", command=self._copy_selected_action)
        self.action_context_menu.add_command(label="Paste After Selected", command=self._paste_action_after)
        self.action_context_menu.add_command(label="Paste at End", command=self._paste_action_at_end)
        self.action_context_menu.add_separator()
        self.action_context_menu.add_command(label="Delete", command=self._delete_selected_action)

    def _show_action_context_menu(self, event: tk.Event, index: int) -> None:
        if index not in self._selected_action_indices:
            self._selected_action_indices.clear()
            self._selected_action_indices.add(index)
            self._last_single_selected_index = index
            self._update_selection_appearance()
            self._update_action_buttons_state()

        selected_count = len(self._selected_action_indices)
        paste_state = tk.NORMAL if self._copied_action_data else tk.DISABLED
        edit_state = tk.NORMAL if selected_count == 1 else tk.DISABLED
        copy_state = tk.NORMAL if selected_count == 1 else tk.DISABLED
        delete_state = tk.NORMAL if selected_count > 0 else tk.DISABLED
        paste_after_state = tk.NORMAL if self._copied_action_data and selected_count == 1 else tk.DISABLED

        self.action_context_menu.entryconfig("Edit", state=edit_state)
        self.action_context_menu.entryconfig("Copy", state=copy_state)
        self.action_context_menu.entryconfig("Paste After Selected", state=paste_after_state)
        self.action_context_menu.entryconfig("Paste at End", state=paste_state)
        self.action_context_menu.entryconfig("Delete", state=delete_state)
        try:
            self.action_context_menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            pass
        finally:
            if hasattr(self.action_context_menu, 'grab_release'):
                self.action_context_menu.grab_release()

    def _add_action_ui(self) -> None:
        if not _GuiComponentsImported:
            messagebox.showerror("Error", "Action editing UI components are not available.", parent=self)
            return

        default_action_data = {
            "type": "click",
            "params": {},
            "condition_id": None,
            "next_action_index_if_condition_met": None,
            "next_action_index_if_condition_not_met": None,
            "is_absolute": False
        }
        ActionEditWindow(
            self.winfo_toplevel(),
            action_data=default_action_data,
            save_callback=self._save_new_action_callback,
            job_manager=self.job_manager,
            image_storage=self.image_storage
        )

    def _save_new_action_callback(self, new_action_data: Optional[Dict[str, Any]]) -> None:
        if new_action_data is None:
            return
        if not _CoreClassesImported:
            messagebox.showerror("Error", "Cannot save new action: Core classes (Action) are not available.", parent=self)
            return
        if not self.job: return

        try:
            new_action_obj = create_action(new_action_data)
            if not isinstance(new_action_obj, Action):
                raise ValueError("Failed to create a valid Action object from the provided data.")
            if not isinstance(self.job.actions, list):
                self.job.actions = []
            self.job.actions.append(new_action_obj)
            new_action_index = len(self.job.actions) - 1
            self._selected_action_indices.clear()
            self._selected_action_indices.add(new_action_index)
            self._last_single_selected_index = new_action_index
            self._populate_actions_ui()
        except Exception as e:
            logger.error(f"JobEdit: Failed to process and add new action: {e}", exc_info=True)
            messagebox.showerror("Error Adding Action", f"Failed to add the new action to the job:\n{e}", parent=self)

    def _edit_selected_action(self) -> None:
        selected_indices = self.get_selected_action_indices()
        if len(selected_indices) != 1:
            messagebox.showwarning("Selection Error", "Please select exactly one action to edit.", parent=self)
            return
        idx = selected_indices[0]

        if not (self.job and isinstance(self.job.actions, list) and \
                0 <= idx < len(self.job.actions) and isinstance(self.job.actions[idx], Action)):
            messagebox.showerror("Error", "Invalid action selection.", parent=self)
            self._selected_action_indices.clear()
            self._last_single_selected_index = -1
            self._populate_actions_ui()
            return

        if not _GuiComponentsImported:
            messagebox.showerror("Error", "Action editing UI components are not available.", parent=self)
            return

        try:
            action_to_edit = self.job.actions[idx]
            action_data_for_edit = copy.deepcopy(action_to_edit.to_dict())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to prepare action data for editing:\n{e}", parent=self)
            logger.error("Error preparing action data for edit", exc_info=True)
            return

        ActionEditWindow(
            self.winfo_toplevel(),
            action_data=action_data_for_edit,
            save_callback=lambda updated_data: self._save_edited_action_callback(idx, updated_data),
            job_manager=self.job_manager,
            image_storage=self.image_storage
        )

    def _save_edited_action_callback(self, index: int, updated_action_data: Optional[Dict[str, Any]]) -> None:
        if updated_action_data is None:
            return
        if not self.job or not isinstance(self.job.actions, list) or not (0 <= index < len(self.job.actions)):
            messagebox.showerror("Internal Error", "Action index is out of sync or job data is invalid.", parent=self)
            self._selected_action_indices.clear()
            self._last_single_selected_index = -1
            self._populate_actions_ui()
            return
        if not _CoreClassesImported:
            messagebox.showerror("Error", "Cannot save edited action: Core classes (Action) are not available.", parent=self)
            return

        try:
            updated_action_obj = create_action(updated_action_data)
            if not isinstance(updated_action_obj, Action):
                raise ValueError("Failed to create a valid Action object from the updated data.")
            self.job.actions[index] = updated_action_obj
            self._selected_action_indices = {index}
            self._last_single_selected_index = index
            self._populate_actions_ui()
        except Exception as e:
            logger.error(f"JobEdit: Failed to process and update action at index {index}: {e}", exc_info=True)
            messagebox.showerror("Error Updating Action", f"Failed to update the action in the job:\n{e}", parent=self)

    def _delete_selected_action(self) -> None:
        selected_indices = self.get_selected_action_indices()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Select at least one action to delete.", parent=self)
            return
        if not self.job or not isinstance(self.job.actions, list): return

        count = len(selected_indices)
        msg = f"Are you sure you want to permanently delete {count} selected action(s)?"

        if messagebox.askyesno("Confirm Deletion", msg, icon='warning', parent=self):
            deleted_count = 0
            errors = []
            indices_to_delete = sorted(selected_indices, reverse=True)

            for idx in indices_to_delete:
                try:
                    if 0 <= idx < len(self.job.actions):
                        del self.job.actions[idx]
                        deleted_count += 1
                    else:
                        errors.append(f"Index {idx+1} out of bounds.")
                except Exception as e:
                    errors.append(f"Action {idx+1}: {e}")

            self._selected_action_indices.clear()
            self._last_single_selected_index = -1
            self._populate_actions_ui()
            if errors:
                messagebox.showerror("Deletion Error", f"Errors occurred:\n" + "\n".join(errors[:3]) + ("\n..." if len(errors)>3 else ""), parent=self)

    def _copy_selected_action(self) -> None:
        selected_indices = self.get_selected_action_indices()
        if len(selected_indices) != 1:
            messagebox.showwarning("Selection Error", "Please select exactly one action to copy.", parent=self)
            return
        idx = selected_indices[0]
        if not self.job or not isinstance(self.job.actions, list) or idx >= len(self.job.actions) or not isinstance(self.job.actions[idx], Action):
            messagebox.showerror("Error", "Invalid selection.", parent=self)
            self._populate_actions_ui()
            return
        try:
            self._copied_action_data = copy.deepcopy(self.job.actions[idx].to_dict())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy: {e}", parent=self)
            self._copied_action_data = None
        self._update_action_buttons_state()

    def _paste_action_after(self) -> None:
        insert_index = len(self.job.actions) if not self.job or not self.job.actions else len(self.job.actions)
        selected_indices = self.get_selected_action_indices()
        if selected_indices:
            insert_index = max(selected_indices) + 1
        elif self._last_single_selected_index != -1 and self.job and 0 <= self._last_single_selected_index < len(self.job.actions) :
            insert_index = self._last_single_selected_index + 1
        self._paste_action(insert_index)

    def _paste_action_at_end(self) -> None:
        insert_index = len(self.job.actions) if self.job and isinstance(self.job.actions, list) else 0
        self._paste_action(insert_index)

    def _paste_action(self, insert_index: int) -> None:
        if not self._copied_action_data:
            messagebox.showwarning("Nothing Copied", "No action copied.", parent=self)
            return
        if not self.job: return
        if not isinstance(self.job.actions, list):
            self.job.actions = []
        insert_index = max(0, min(insert_index, len(self.job.actions)))
        if not _CoreClassesImported:
            messagebox.showerror("Error", "Cannot paste: Core N/A.", parent=self)
            return
        try:
            new_action_obj = create_action(self._copied_action_data)
            self.job.actions.insert(insert_index, new_action_obj)
            self._selected_action_indices.clear()
            self._selected_action_indices.add(insert_index)
            self._last_single_selected_index = insert_index
            self._populate_actions_ui()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to paste: {e}", parent=self)

    def _on_drag_start(self, event: tk.Event, index: int) -> None:
        if len(self._selected_action_indices) > 1:
            return

        widget = event.widget
        target_frame_widget = None
        while widget and widget != self.scrollable_actions_frame :
            if hasattr(widget, 'action_index') and widget.action_index == index:
                target_frame_widget = widget
                break
            widget = widget.master

        if not target_frame_widget or not target_frame_widget.winfo_exists():
            return

        self._selected_action_indices = {index}
        self._last_single_selected_index = index
        self._update_selection_appearance()

        self._drag_data = {"widget": target_frame_widget, "start_y": event.y_root, "source_index": index, "indicator": None}
        self.is_dragging = True
        target_frame_widget.configure(relief=tk.RAISED, borderwidth=2)
        target_frame_widget.config(cursor="fleur")
        if hasattr(target_frame_widget, 'winfo_children'):
            for child in target_frame_widget.winfo_children():
                child.config(cursor="fleur")

    def _on_drag_motion(self, event: tk.Event) -> None:
        if not self.is_dragging or not self._drag_data.get("widget"): return
        if not hasattr(self, 'action_canvas') or not self.action_canvas.winfo_exists(): return

        mouse_y_canvas = event.y_root - self.action_canvas.winfo_rooty()
        mouse_y_frame = self.action_canvas.canvasy(mouse_y_canvas)
        target_index = self._get_index_from_y_in_frame(mouse_y_frame)
        self._draw_drag_indicator(target_index)

        canvas_h = self.action_canvas.winfo_height()
        margin = 30
        speed = 1
        current_yview = self.action_canvas.yview()

        if mouse_y_canvas < margin and current_yview and current_yview[0] > 0:
            self.action_canvas.yview_scroll(-speed,"units")
            self._draw_drag_indicator(self._get_index_from_y_in_frame(self.action_canvas.canvasy(mouse_y_canvas)))
        elif mouse_y_canvas > canvas_h - margin and current_yview and current_yview[1] < 1.0:
            self.action_canvas.yview_scroll(speed,"units")
            self._draw_drag_indicator(self._get_index_from_y_in_frame(self.action_canvas.canvasy(mouse_y_canvas)))

    def _handle_action_release(self, event: tk.Event, index: int) -> None:
        dragged_widget = self._drag_data.get("widget")
        drag_dist = abs(event.y_root - self._drag_data.get("start_y", event.y_root)) if self.is_dragging else 0

        was_dragging_before_release = self.is_dragging

        if self.is_dragging:
            self.is_dragging = False
            if dragged_widget is not None and drag_dist > DRAG_THRESHOLD:
                self._on_drag_end(event)
            else:
                self._on_action_click(event, index)
        elif not was_dragging_before_release:
             self._on_action_click(event, index)


        self._clear_drag_state()

    def _on_action_click(self, event: tk.Event, index: int) -> None:
        ctrl_pressed = (event.state & 0x0004) != 0
        shift_pressed = (event.state & 0x0001) != 0

        if ctrl_pressed:
            if index in self._selected_action_indices:
                self._selected_action_indices.remove(index)
            else:
                self._selected_action_indices.add(index)
            self._last_single_selected_index = index
        elif shift_pressed and self._last_single_selected_index != -1:
            start = min(self._last_single_selected_index, index)
            end = max(self._last_single_selected_index, index)
            self._selected_action_indices.clear()
            for i in range(start, end + 1):
                self._selected_action_indices.add(i)
        else:
            self._selected_action_indices.clear()
            self._selected_action_indices.add(index)
            self._last_single_selected_index = index

        self._update_selection_appearance()
        self._update_action_buttons_state()

    def _on_drag_end(self, event: tk.Event) -> None:
        dragged_widget = self._drag_data.get("widget")
        source_idx = self._drag_data.get("source_index", -1)
        if not self.job or not isinstance(self.job.actions, list) or not hasattr(self, 'action_canvas') or not self.action_canvas.winfo_exists(): return

        mouse_y_frame = self.action_canvas.canvasy(event.y_root - self.action_canvas.winfo_rooty())
        self._clear_drag_indicator()
        if not dragged_widget or source_idx == -1: return

        target_idx = self._get_index_from_y_in_frame(mouse_y_frame)

        actual_target_idx = target_idx
        if source_idx < target_idx :
             actual_target_idx = max(0, target_idx -1)

        actual_target_idx = max(0, min(actual_target_idx, len(self.job.actions)))

        if source_idx != actual_target_idx and 0 <= source_idx < len(self.job.actions):
            try:
                moved_action = self.job.actions.pop(source_idx)
                if actual_target_idx > len(self.job.actions):
                    self.job.actions.append(moved_action)
                    actual_target_idx = len(self.job.actions) -1
                else:
                    self.job.actions.insert(actual_target_idx, moved_action)

                self._selected_action_indices = {actual_target_idx}
                self._last_single_selected_index = actual_target_idx
                self._populate_actions_ui()
            except Exception as e:
                messagebox.showerror("Drag Error", f"Move failed: {e}", parent=self)
                self._populate_actions_ui()

    def _get_index_from_y_in_frame(self, y_in_frame: float) -> int:
        all_frames = self._get_action_row_frames()
        if not all_frames: return 0
        for i, child_frame in enumerate(all_frames):
            if child_frame.winfo_exists():
                if y_in_frame < child_frame.winfo_y() + child_frame.winfo_height() / 2:
                    return i
        return len(all_frames)

    def _draw_drag_indicator(self, target_index: int) -> None:
        self._clear_drag_indicator()
        if not hasattr(self, 'action_canvas') or not self.action_canvas.winfo_exists(): return

        all_frames = self._get_action_row_frames()
        canvas_w = self.action_canvas.winfo_width()
        line_y_frame = 1.0

        if not all_frames or target_index == 0:
            if all_frames and all_frames[0].winfo_exists():
                line_y_frame = float(all_frames[0].winfo_y() - 1)
            else:
                line_y_frame = 1.0
        elif target_index >= len(all_frames):
            if all_frames and all_frames[-1].winfo_exists():
                line_y_frame = float(all_frames[-1].winfo_y() + all_frames[-1].winfo_height() + 1)
            else:
                line_y_frame = 1.0
        elif all_frames[target_index].winfo_exists():
            line_y_frame = float(all_frames[target_index].winfo_y() - 1)

        line_y_frame = max(0.0, line_y_frame)

        try:
             line_y_canvas = self.action_canvas.canvasy(line_y_frame)
             if self._drag_data:
                 self._drag_data["indicator"] = self.action_canvas.create_line(0, line_y_canvas, canvas_w, line_y_canvas, fill="deepskyblue", width=2, tags="drag_indicator")
        except tk.TclError:
            return

    def _clear_drag_indicator(self) -> None:
        if hasattr(self,'action_canvas') and self.action_canvas.winfo_exists():
            self.action_canvas.delete("drag_indicator")
        if self._drag_data and "indicator" in self._drag_data:
            self._drag_data["indicator"] = None

    def _clear_drag_state(self) -> None:
        dragged_widget = self._drag_data.get("widget")
        source_idx = self._drag_data.get("source_index", -1)
        if dragged_widget and dragged_widget.winfo_exists():
            is_selected = (source_idx in self._selected_action_indices)
            style = "Selected.TFrame" if is_selected else "TFrame"
            relief_val = tk.SOLID if is_selected else tk.FLAT

            current_relief = dragged_widget.cget("relief")
            current_style = dragged_widget.cget("style")

            if current_relief != str(relief_val):
                 dragged_widget.configure(relief=relief_val)
            if current_style != style:
                 dragged_widget.configure(style=style)

            dragged_widget.configure(borderwidth=1)
            dragged_widget.config(cursor="")
            if hasattr(dragged_widget, 'winfo_children'):
                for child in dragged_widget.winfo_children():
                    child.config(cursor="")
        self._drag_data = {"widget": None, "start_y": 0, "source_index": -1, "indicator": None}
        self.is_dragging = False
        self._update_action_buttons_state()

    def _save_job(self) -> None:
        if not self.job: return
        new_name = self.name_entry.get().strip()
        new_hotkey = self.hotkey_recorder.get_key()
        new_stopkey = self.stopkey_recorder.get_key()

        if not hasattr(self,'run_condition_settings') or not hasattr(self.run_condition_settings,'get_settings'):
            messagebox.showerror("Error","Run Condition UI N/A.",parent=self)
            return
        try:
            new_rc_data = self.run_condition_settings.get_settings()
        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid run condition: {e}", parent=self)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Error getting run condition: {e}", parent=self)
            return

        try:
            delay_str = self.delay_between_runs_entry.get().strip()
            new_delay_between_runs = float(delay_str) if delay_str else 0.01
            if new_delay_between_runs < 0:
                raise ValueError("Delay Between Runs cannot be negative.")
        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid Delay Between Runs: {e}", parent=self)
            if hasattr(self, 'delay_between_runs_entry'): self.delay_between_runs_entry.focus_set()
            return

        if not new_name:
            messagebox.showerror("Input Error", "Job name cannot be empty.", parent=self)
            return
        if new_hotkey and new_hotkey == new_stopkey:
            messagebox.showwarning("Key Conflict", "Hotkey and Stopkey are the same. This might cause unexpected behavior.", parent=self)

        orig_name_before_update = self.job.name
        self.job.name = new_name
        self.job.hotkey = new_hotkey
        self.job.stop_key = new_stopkey
        self.job.run_condition = create_job_run_condition(new_rc_data) if _CoreClassesImported else None
        if not isinstance(self.job.params, dict): self.job.params = {}
        self.job.params["delay_between_runs_s"] = new_delay_between_runs


        try:
            if self.original_job_name and self.original_job_name != new_name:
                self.job_manager.update_job(self.original_job_name, self.job)
            elif self.original_job_name and self.original_job_name == new_name:
                self.job_manager.update_job(self.original_job_name, self.job)
            else:
                self.job_manager.add_job(self.job)
            self.original_job_name = self.job.name
            if self.close_callback:
                self.close_callback()
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Save Error", str(e), parent=self)
            self.job.name = orig_name_before_update
        except Exception as e:
            messagebox.showerror("Save Error", f"Unexpected save error: {e}", parent=self)
            self.job.name = orig_name_before_update

    def _cancel(self) -> None:
        if self.close_callback:
            self.close_callback()
        self.destroy()

    def _update_action_buttons_state(self) -> None:
        selected_count = len(self._selected_action_indices)
        edit_state = tk.NORMAL if selected_count == 1 else tk.DISABLED
        delete_state = tk.NORMAL if selected_count > 0 else tk.DISABLED
        copy_state = tk.NORMAL if selected_count == 1 else tk.DISABLED
        paste_state = tk.NORMAL if self._copied_action_data else tk.DISABLED

        if hasattr(self, 'edit_action_button'): self.edit_action_button.config(state=edit_state)
        if hasattr(self, 'delete_action_button'): self.delete_action_button.config(state=delete_state)
        if hasattr(self, 'copy_button'): self.copy_button.config(state=copy_state)
        if hasattr(self, 'paste_button'): self.paste_button.config(state=paste_state)
        if hasattr(self, 'add_action_button'): self.add_action_button.config(state=tk.NORMAL)
        if hasattr(self, 'add_drawing_block_button'): self.add_drawing_block_button.config(state=tk.NORMAL)

    def destroy(self) -> None:
        job_name_to_log = "N/A"
        if self.job and hasattr(self.job, 'name'):
             job_name_to_log = self.job.name

        logger.debug(f"Destroying JobEdit for '{job_name_to_log}'.")
        if hasattr(self,'hotkey_recorder') and self.hotkey_recorder.winfo_exists():
            try: self.hotkey_recorder.destroy()
            except Exception: pass
        if hasattr(self,'stopkey_recorder') and self.stopkey_recorder.winfo_exists():
            try: self.stopkey_recorder.destroy()
            except Exception: pass
        if hasattr(self, 'action_canvas') and self.action_canvas and self.action_canvas.winfo_exists():
            self._unbind_mouse_wheel(self.action_canvas)
        if hasattr(self, 'scrollable_actions_frame') and self.scrollable_actions_frame and self.scrollable_actions_frame.winfo_exists():
            self._unbind_mouse_wheel(self.scrollable_actions_frame)
            for child_frame in list(self.scrollable_actions_frame.winfo_children()):
                if isinstance(child_frame, ttk.Frame):
                    for widget_in_row in list(child_frame.winfo_children()):
                        try:
                            widget_in_row.unbind_all("<ButtonPress-1>")
                            widget_in_row.unbind_all("<B1-Motion>")
                            widget_in_row.unbind_all("<ButtonRelease-1>")
                            widget_in_row.unbind_all("<Button-3>")
                            widget_in_row.unbind_all("<Button-2>")
                        except Exception: pass
                    try:
                        child_frame.unbind_all("<ButtonPress-1>")
                        child_frame.unbind_all("<B1-Motion>")
                        child_frame.unbind_all("<ButtonRelease-1>")
                        child_frame.unbind_all("<Button-3>")
                        child_frame.unbind_all("<Button-2>")
                    except Exception: pass
        super().destroy()

    def _add_drawing_block_ui(self) -> None:
        if not self.job_manager:
            messagebox.showerror("Error", "JobManager is not available.", parent=self)
            return
        if not _GuiComponentsImported:
            messagebox.showerror("Error", "Selection dialog UI is not available.", parent=self)
            return

        try:
            available_templates_map: Dict[str, str] = self.job_manager.get_shape_template_display_names()
            if not available_templates_map:
                messagebox.showinfo("No Drawings", "No pre-defined drawings (Shape Templates) found in the current profile.\nPlease create some first using the Shape Template Editor.", parent=self)
                return

            display_names_to_show = sorted(list(available_templates_map.values()), key=lambda s: s.lower())

            dialog = SelectTargetDialog(
                self.winfo_toplevel(),
                target_list=display_names_to_show,
                dialog_title="Select Drawing Block",
                prompt="Select a drawing to add to the job:"
            )
            self.winfo_toplevel().wait_window(dialog)

            selected_display_name = dialog.selected_target

            if selected_display_name:
                selected_internal_name: Optional[str] = None
                for internal_name, display_name_in_map in available_templates_map.items():
                    if display_name_in_map == selected_display_name:
                        selected_internal_name = internal_name
                        break

                if selected_internal_name:
                    self._insert_drawing_block_actions(selected_internal_name)
                else:
                    logger.error(f"Critical error: Could not find internal name for selected display name '{selected_display_name}'. Map was: {available_templates_map}")
                    messagebox.showerror("Internal Error", "Could not map selected drawing back to its internal data. Please report this issue.", parent=self)
        except Exception as e:
            logger.error(f"Error in _add_drawing_block_ui: {e}", exc_info=True)
            messagebox.showerror("Error", f"Could not add drawing block: {e}", parent=self)

    def _insert_drawing_block_actions(self, template_internal_name: str) -> None:
        if not self.job or not self.job_manager:
            return

        try:
            template_data = self.job_manager.get_shape_template_data(template_internal_name)
            if not template_data:
                messagebox.showerror("Error", f"Could not load data for drawing template '{template_internal_name}'.", parent=self)
                return

            actions_to_insert_dicts: Optional[List[Dict[str, Any]]] = template_data.get("actions")
            if not actions_to_insert_dicts or not isinstance(actions_to_insert_dicts, list):
                messagebox.showinfo("Info", f"The selected drawing template '{template_data.get('display_name', template_internal_name)}' has no actions defined or actions data is invalid.", parent=self)
                return

            actions_objects_to_insert: List[Action] = []
            if not _CoreClassesImported:
                messagebox.showerror("Core Error", "Cannot create action objects: Core components (Action class) are missing.", parent=self)
                return

            for i, action_dict in enumerate(actions_to_insert_dicts):
                if not isinstance(action_dict, dict):
                    continue
                try:
                    action_data_for_creation = copy.deepcopy(action_dict)
                    action_data_for_creation.setdefault("is_absolute", False)

                    action_obj = create_action(action_data_for_creation)
                    actions_objects_to_insert.append(action_obj)
                except Exception as e:
                    logger.error(f"Error creating Action object from dict for template '{template_internal_name}', action data: {action_dict}. Error: {e}", exc_info=True)
                    messagebox.showerror("Action Creation Error", f"Failed to process an action from the drawing template:\n{e}\n\nThe template might be corrupted or incompatible.", parent=self)
                    return

            if not actions_objects_to_insert:
                messagebox.showinfo("Info", f"No valid actions could be processed from the drawing template '{template_data.get('display_name', template_internal_name)}'.", parent=self)
                return

            insert_at_index: int
            selected_indices = self.get_selected_action_indices()
            if selected_indices:
                insert_at_index = max(selected_indices) + 1
            elif self._last_single_selected_index != -1 and 0 <= self._last_single_selected_index < len(self.job.actions):
                insert_at_index = self._last_single_selected_index + 1
            else:
                insert_at_index = len(self.job.actions)

            if not isinstance(self.job.actions, list):
                self.job.actions = []
                insert_at_index = 0

            for i, action_obj_to_insert in enumerate(actions_objects_to_insert):
                self.job.actions.insert(insert_at_index + i, action_obj_to_insert)

            self._populate_actions_ui()
            newly_added_indices = list(range(insert_at_index, insert_at_index + len(actions_objects_to_insert)))
            if newly_added_indices:
                self.action_canvas.after_idle(lambda: self._select_and_focus_actions(newly_added_indices))

        except Exception as e:
            logger.error(f"Error inserting drawing block actions for template '{template_internal_name}': {e}", exc_info=True)
            messagebox.showerror("Insertion Error", f"An unexpected error occurred while inserting drawing actions:\n{e}", parent=self)

    def _select_and_focus_actions(self, indices_to_select: List[int]) -> None:
        if not hasattr(self, 'scrollable_actions_frame') or not self.scrollable_actions_frame.winfo_exists():
            return
        if not indices_to_select:
            return

        all_action_row_frames = self._get_action_row_frames()
        valid_indices_to_select_in_ui = [idx for idx in indices_to_select if 0 <= idx < len(all_action_row_frames)]

        if not valid_indices_to_select_in_ui:
            self._selected_action_indices.clear()
            self._last_single_selected_index = -1
            self._update_selection_appearance()
            self._update_action_buttons_state()
            return

        self._selected_action_indices = set(valid_indices_to_select_in_ui)
        self._last_single_selected_index = valid_indices_to_select_in_ui[-1]

        self._update_selection_appearance()
        self._update_action_buttons_state()

        try:
            first_new_widget = all_action_row_frames[valid_indices_to_select_in_ui[0]]
            if first_new_widget.winfo_exists():
                self.scrollable_actions_frame.update_idletasks()
                widget_y = first_new_widget.winfo_y()
                frame_height = self.scrollable_actions_frame.winfo_height()
                if frame_height > 0:
                    fraction = widget_y / frame_height
                    self.action_canvas.yview_moveto(fraction)
        except Exception as e:
            logger.warning(f"Could not scroll to newly added actions: {e}")
