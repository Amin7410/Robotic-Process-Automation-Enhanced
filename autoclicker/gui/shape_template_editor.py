# gui/shape_template_editor.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
import copy
import json
from typing import List, Tuple, Dict, Optional, Any, Callable

logger = logging.getLogger(__name__)

_EDITOR_DEPS_IMPORTED = False
try:
    from gui.drawing_capture_window import DrawingCaptureWindow
    from core.job_manager import JobManager 
    from utils.image_storage import ImageStorage
    from utils.drawing_utils import convert_drawing_to_actions, parse_json_strokes_data
    _EDITOR_DEPS_IMPORTED = True
except ImportError as e:
    logger.error(f"ShapeTemplateEditor: Missing core dependencies: {e}")
    _EDITOR_DEPS_IMPORTED = False
    class DrawingCaptureWindow(object): 
        def __init__(self, master, callback):
            logger.error("Dummy DrawingCaptureWindow called.")
            if callable(callback):
                dummy_master_for_after = master
                if not (hasattr(master, 'after') and callable(master.after)):
                    logger.warning("ShapeTemplateEditor Dummy DrawingCaptureWindow: master is not a Tk widget, creating temporary for 'after'.")
                    temp_root = tk.Tk()
                    temp_root.withdraw() 
                    dummy_master_for_after = temp_root
                    dummy_master_for_after.after(30, temp_root.destroy)

                dummy_master_for_after.after(10, lambda: callback(None))


    class JobManager:
        def get_shape_template_data(self, name): return None
        def add_shape_template(self, name, data): pass
        def update_shape_template(self, name, data): pass
        def delete_shape_template(self, name): pass
    class ImageStorage: pass
    def convert_drawing_to_actions(strokes, params): return []
    def parse_json_strokes_data(json_str): return None


class ShapeTemplateEditor(tk.Toplevel):
    def __init__(self, master: tk.Tk | tk.Toplevel,
                 job_manager: JobManager,
                 image_storage: ImageStorage, 
                 template_name_to_edit: Optional[str] = None,
                 on_close_callback: Optional[Callable[[], None]] = None):
        super().__init__(master)

        if not _EDITOR_DEPS_IMPORTED:
            messagebox.showerror("Initialization Error", "ShapeTemplateEditor cannot start due to missing core components.", parent=master)
            self.after(10, self.destroy)
            return

        self.job_manager = job_manager
        self.image_storage = image_storage 
        self.original_template_name = template_name_to_edit
        self.on_close_callback = on_close_callback
        self.current_template_data: Dict[str, Any] = self._load_or_create_template_data()

        self.title(f"Edit Drawing Template: {template_name_to_edit}" if template_name_to_edit else "Create New Drawing Template")
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._setup_ui()
        self._populate_ui_from_data()

        self.update_idletasks()
        min_w = max(self.winfo_reqwidth(), 600)
        min_h = max(self.winfo_reqheight(), 550)
        self.minsize(min_w, min_h)
        self.geometry(f"{min_w}x{min_h}")

        if master and master.winfo_exists():
            master.update_idletasks()
            master_x = master.winfo_rootx()
            master_y = master.winfo_rooty()
            master_w = master.winfo_width()
            master_h = master.winfo_height()
            win_w = self.winfo_width()
            win_h = self.winfo_height()
            x = master_x + (master_w - win_w) // 2
            y = master_y + (master_h - win_h) // 2
            self.geometry(f"+{x}+{y}")

        if hasattr(self, 'template_name_entry') and self.template_name_entry: 
            self.template_name_entry.focus_set()

    def _load_or_create_template_data(self) -> Dict[str, Any]:
        if self.original_template_name:
            try:
                template_dict = self.job_manager.get_shape_template_data(self.original_template_name)
                if template_dict:
                    template_dict.setdefault("drawing_data", {"strokes": [], "parameters": {}})
                    template_dict["drawing_data"].setdefault("strokes", [])
                    template_dict["drawing_data"].setdefault("parameters", {})
                    template_dict["drawing_data"]["parameters"].setdefault("draw_speed_factor", 1.0)
                    template_dict["drawing_data"]["parameters"].setdefault("delay_between_strokes_ms", 50)
                    template_dict.setdefault("actions", [])
                    return copy.deepcopy(template_dict)
                else:
                    logger.warning(f"Template '{self.original_template_name}' not found, creating new structure.")
            except Exception as e:
                logger.error(f"Error loading template '{self.original_template_name}': {e}", exc_info=True)
                messagebox.showerror("Load Error", f"Could not load template: {e}", parent=self.master)
        return {
            "template_name": "", "display_name": "", "description": "",
            "drawing_data": {"strokes": [], "parameters": {"draw_speed_factor": 1.0, "delay_between_strokes_ms": 50}},
            "actions": []
        }

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) 

        info_frame = ttk.LabelFrame(self, text="Template Information", padding=10)
        info_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        info_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(info_frame, text="Internal Name:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.template_name_entry = ttk.Entry(info_frame, width=40)
        self.template_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(info_frame, text="(Unique, no spaces/special chars)").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, text="Display Name:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.display_name_entry = ttk.Entry(info_frame, width=40)
        self.display_name_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
        ttk.Label(info_frame, text="Description:").grid(row=2, column=0, sticky="nw", padx=5, pady=2)
        self.description_text = tk.Text(info_frame, height=2, width=40, wrap="word")
        self.description_text.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
        desc_scroll = ttk.Scrollbar(info_frame, orient="vertical", command=self.description_text.yview)
        desc_scroll.grid(row=2, column=3, sticky="ns", pady=2, padx=(0,5))
        self.description_text.config(yscrollcommand=desc_scroll.set)

        drawing_main_frame = ttk.LabelFrame(self, text="Drawing Definition", padding=10)
        drawing_main_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        drawing_main_frame.grid_columnconfigure(0, weight=1)
        drawing_main_frame.grid_rowconfigure(1, weight=1)

        draw_controls_frame = ttk.Frame(drawing_main_frame)
        draw_controls_frame.grid(row=0, column=0, sticky="ew", pady=(0,5))
        self.define_drawing_button = ttk.Button(draw_controls_frame, text="Define/Redefine Drawing Path", command=self._start_drawing_definition)
        self.define_drawing_button.pack(side=tk.LEFT, padx=5)
        self.clear_drawing_button = ttk.Button(draw_controls_frame, text="Clear Drawing Data", command=self._clear_drawing_data)
        self.clear_drawing_button.pack(side=tk.LEFT, padx=5)

        strokes_display_frame = ttk.LabelFrame(drawing_main_frame, text="Captured Strokes (Read-only JSON Preview)", padding=5)
        strokes_display_frame.grid(row=1, column=0, sticky="nsew", pady=(5,0))
        strokes_display_frame.grid_rowconfigure(0, weight=1)
        strokes_display_frame.grid_columnconfigure(0, weight=1)
        self.strokes_text_area = tk.Text(strokes_display_frame, height=8, width=50, wrap="none", state="disabled", relief="sunken", borderwidth=1, font=("Courier New", 9))
        strokes_x_scroll = ttk.Scrollbar(strokes_display_frame, orient="horizontal", command=self.strokes_text_area.xview)
        strokes_y_scroll = ttk.Scrollbar(strokes_display_frame, orient="vertical", command=self.strokes_text_area.yview)
        self.strokes_text_area.config(xscrollcommand=strokes_x_scroll.set, yscrollcommand=strokes_y_scroll.set)
        self.strokes_text_area.grid(row=0, column=0, sticky="nsew")
        strokes_y_scroll.grid(row=0, column=1, sticky="ns", pady=(0,2), padx=(0,2)) # Thêm padding cho scrollbar
        strokes_x_scroll.grid(row=1, column=0, sticky="ew", padx=(0,2), pady=(0,2))

        ai_input_frame = ttk.LabelFrame(drawing_main_frame, text="AI / Manual Data Input (JSON Strokes List)", padding=5)
        ai_input_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ai_input_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(ai_input_frame, text="Paste Data Here:").grid(row=0, column=0, sticky="nw", padx=5, pady=2) 
        self.ai_data_text_area = tk.Text(ai_input_frame, height=6, width=50, wrap="word", font=("Courier New", 9))
        ai_data_text_scroll = ttk.Scrollbar(ai_input_frame, orient="vertical", command=self.ai_data_text_area.yview)
        self.ai_data_text_area.config(yscrollcommand=ai_data_text_scroll.set)
        self.ai_data_text_area.grid(row=0, column=1, sticky="nsew", padx=5, pady=2) 
        ai_data_text_scroll.grid(row=0, column=2, sticky="ns", pady=2) 
        self.process_ai_data_button = ttk.Button(ai_input_frame, text="Process Pasted Data", command=self._process_pasted_ai_data)
        self.process_ai_data_button.grid(row=1, column=1, sticky="e", padx=5, pady=5) 


        params_frame = ttk.LabelFrame(drawing_main_frame, text="Drawing Parameters (Used for Action Generation)", padding=5)
        params_frame.grid(row=3, column=0, sticky="ew", pady=(5,0))
        params_frame.grid_columnconfigure(1, weight=0) 
        params_frame.grid_columnconfigure(3, weight=1) 
        ttk.Label(params_frame, text="Speed Factor:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        vcmd_float_positive = self.register(lambda P: P == "" or (P.count('.') <= 1 and P.replace('.', '', 1).isdigit() and float(P) > 0) if P and P != "." else True)
        self.speed_factor_entry = ttk.Entry(params_frame, width=10, validate="key", validatecommand=(vcmd_float_positive, '%P'))
        self.speed_factor_entry.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(params_frame, text="(e.g., 1.0=normal, 0.5=slower, 2.0=faster)").grid(row=0, column=2, columnspan=2, sticky="w", padx=5, pady=2)
        ttk.Label(params_frame, text="Delay Between Strokes (ms):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        vcmd_int_non_negative = self.register(lambda P: P == "" or (P.isdigit() and int(P) >= 0) if P else True)
        self.delay_strokes_entry = ttk.Entry(params_frame, width=10, validate="key", validatecommand=(vcmd_int_non_negative, '%P'))
        self.delay_strokes_entry.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(params_frame, text="(Delay after each stroke completes)").grid(row=1, column=2, columnspan=2, sticky="w", padx=5, pady=2)


        main_buttons_frame = ttk.Frame(self)
        main_buttons_frame.grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.save_button = ttk.Button(main_buttons_frame, text="Save Template", command=self._on_save)
        self.save_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = ttk.Button(main_buttons_frame, text="Cancel", command=self._on_cancel)
        self.cancel_button.pack(side=tk.LEFT, padx=5)

    def _populate_ui_from_data(self) -> None:
        if not hasattr(self, 'current_template_data') or not self.current_template_data:
            logger.error("ShapeTemplateEditor: current_template_data is not initialized. Cannot populate UI.")
            return

        self.template_name_entry.delete(0, tk.END)
        self.template_name_entry.insert(0, self.current_template_data.get("template_name", ""))
        if self.original_template_name:
            self.template_name_entry.config(state="readonly")

        self.display_name_entry.delete(0, tk.END)
        self.display_name_entry.insert(0, self.current_template_data.get("display_name", ""))

        self.description_text.delete("1.0", tk.END)
        self.description_text.insert("1.0", self.current_template_data.get("description", ""))

        drawing_data = self.current_template_data.get("drawing_data", {})
        draw_params = drawing_data.get("parameters", {})
        self.speed_factor_entry.delete(0, tk.END)
        self.speed_factor_entry.insert(0, str(draw_params.get("draw_speed_factor", 1.0)))
        self.delay_strokes_entry.delete(0, tk.END)
        self.delay_strokes_entry.insert(0, str(draw_params.get("delay_between_strokes_ms", 50)))

        self._update_strokes_display()

    def _update_strokes_display(self) -> None:
        self.strokes_text_area.config(state="normal")
        self.strokes_text_area.delete("1.0", tk.END)
        strokes_data = self.current_template_data.get("drawing_data", {}).get("strokes", [])
        if strokes_data:
            try:
                json_text = json.dumps(strokes_data, indent=2)
                self.strokes_text_area.insert(tk.END, json_text)
            except Exception as e:
                logger.error(f"Error formatting strokes as JSON for display: {e}")
                self.strokes_text_area.insert(tk.END, f"Error displaying strokes data: {e}")
        else:
            self.strokes_text_area.insert(tk.END, "(No drawing path defined yet. Click 'Define/Redefine Drawing Path' or paste JSON data.)")
        self.strokes_text_area.config(state="disabled")

    def _start_drawing_definition(self) -> None:
      
        logger.info("ShapeTemplateEditor: Initiating drawing capture process.")
        
        DrawingCaptureWindow(self, self._on_drawing_captured) 

    def _on_drawing_captured(self, captured_strokes_data: Optional[List[List[Dict[str, int]]]]) -> None:

        if captured_strokes_data:
            self.current_template_data.setdefault("drawing_data", {})
            self.current_template_data["drawing_data"]["strokes"] = captured_strokes_data
            self._update_strokes_display()
            messagebox.showinfo("Drawing Captured", f"{len(captured_strokes_data)} stroke(s) have been defined.", parent=self)
        else:
            messagebox.showinfo("Drawing Definition", "Drawing definition was cancelled or no path was created.", parent=self)

    def _clear_drawing_data(self) -> None:
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all currently defined drawing strokes for this template? This will also clear any auto-generated actions.", parent=self):
            self.current_template_data.setdefault("drawing_data", {})
            self.current_template_data["drawing_data"]["strokes"] = []
            self.current_template_data["actions"] = [] 
            self._update_strokes_display()
            self.ai_data_text_area.delete("1.0", tk.END) 

    def _process_pasted_ai_data(self) -> None:
        pasted_data_str = self.ai_data_text_area.get("1.0", tk.END).strip()

        if not pasted_data_str:
            messagebox.showwarning("No Data", "Please paste data into the text area.", parent=self)
            return

        parsed_strokes: Optional[List[List[Dict[str, int]]]] = None
        try:
            if not _EDITOR_DEPS_IMPORTED:
                raise ImportError("Drawing utilities (including JSON parser) are not available.")
            parsed_strokes = parse_json_strokes_data(pasted_data_str) 
        except ValueError as e:
            messagebox.showerror("Processing Error", f"Could not process pasted JSON data:\n{e}", parent=self)
            return
        except ImportError as e:
            messagebox.showerror("Internal Error", f"A required component for processing is missing: {e}", parent=self)
            return
        except Exception as e:
            messagebox.showerror("Unexpected Error", f"An error occurred while processing data: {e}", parent=self)
            return

        if parsed_strokes is not None:
            if messagebox.askyesno("Confirm Overwrite",
                                   "This will overwrite any existing drawing path and auto-generated actions. Are you sure?",
                                   parent=self):
                self.current_template_data.setdefault("drawing_data", {})
                self.current_template_data["drawing_data"]["strokes"] = parsed_strokes
                self.current_template_data["actions"] = [] 
                self._update_strokes_display()
                self.ai_data_text_area.delete("1.0", tk.END) 
                messagebox.showinfo("Success", "Drawing data processed and updated from pasted input.", parent=self)
        else:
            messagebox.showerror("Processing Error", "Failed to parse strokes data correctly. No changes made.", parent=self)


    def _on_save(self) -> None:
        if not self.job_manager:
            messagebox.showerror("Error", "JobManager is not available. Cannot save.", parent=self)
            return

        template_name = self.template_name_entry.get().strip()
        display_name = self.display_name_entry.get().strip()
        description = self.description_text.get("1.0", tk.END).strip()

        if not template_name:
            messagebox.showerror("Input Error", "Internal Template Name cannot be empty.", parent=self)
            if self.template_name_entry and self.template_name_entry.winfo_exists(): self.template_name_entry.focus_set()
            return
        if not all(c.isalnum() or c in ('_', '-') for c in template_name):
            messagebox.showerror("Input Error", "Internal Template Name can only contain letters, numbers, underscores, and hyphens.", parent=self)
            if self.template_name_entry and self.template_name_entry.winfo_exists(): self.template_name_entry.focus_set()
            return
        if not display_name:
            messagebox.showerror("Input Error", "Display Name cannot be empty.", parent=self)
            if self.display_name_entry and self.display_name_entry.winfo_exists(): self.display_name_entry.focus_set()
            return

        if not self.original_template_name and self.job_manager.get_shape_template_data(template_name):
            messagebox.showerror("Name Exists", f"A template with the internal name '{template_name}' already exists.", parent=self)
            if self.template_name_entry and self.template_name_entry.winfo_exists(): self.template_name_entry.focus_set()
            return
        if self.original_template_name and template_name != self.original_template_name and \
           self.job_manager.get_shape_template_data(template_name):
            messagebox.showerror("Name Exists", f"Cannot rename to '{template_name}', a template with that internal name already exists.", parent=self)
            if self.template_name_entry and self.template_name_entry.winfo_exists(): self.template_name_entry.focus_set()
            return

        try:
            speed_factor_str = self.speed_factor_entry.get().strip()
            speed_factor = float(speed_factor_str) if speed_factor_str else 1.0
            if speed_factor <= 0: raise ValueError("Speed Factor must be positive.")
        except ValueError:
            messagebox.showerror("Input Error", "Invalid Speed Factor. Must be a positive number.", parent=self)
            if self.speed_factor_entry and self.speed_factor_entry.winfo_exists(): self.speed_factor_entry.focus_set()
            return

        try:
            delay_strokes_ms_str = self.delay_strokes_entry.get().strip()
            delay_strokes_ms = int(delay_strokes_ms_str) if delay_strokes_ms_str else 50
            if delay_strokes_ms < 0: raise ValueError("Delay Between Strokes must be non-negative.")
        except ValueError:
            messagebox.showerror("Input Error", "Invalid Delay Between Strokes. Must be a non-negative integer.", parent=self)
            if self.delay_strokes_entry and self.delay_strokes_entry.winfo_exists(): self.delay_strokes_entry.focus_set()
            return

        self.current_template_data["template_name"] = template_name
        self.current_template_data["display_name"] = display_name
        self.current_template_data["description"] = description
        self.current_template_data.setdefault("drawing_data", {"strokes": [], "parameters": {}})
        self.current_template_data["drawing_data"].setdefault("parameters", {})
        self.current_template_data["drawing_data"]["parameters"]["draw_speed_factor"] = speed_factor
        self.current_template_data["drawing_data"]["parameters"]["delay_between_strokes_ms"] = delay_strokes_ms

        strokes = self.current_template_data.get("drawing_data", {}).get("strokes", [])
        if not strokes: 
            messagebox.showwarning("No Drawing", "No drawing path has been defined for this template. Please define one or cancel.", parent=self)
            return

        drawing_params_for_conversion = self.current_template_data.get("drawing_data", {}).get("parameters", {})
        try:
            if not _EDITOR_DEPS_IMPORTED: 
                 raise ImportError("Drawing utilities (convert_drawing_to_actions) are not available.")
            generated_actions_list_of_dicts = convert_drawing_to_actions(strokes, drawing_params_for_conversion)
            self.current_template_data["actions"] = generated_actions_list_of_dicts
        except ImportError as e:
            messagebox.showerror("Internal Error", f"A required component for action generation is missing: {e}", parent=self)
            return
        except Exception as e:
            messagebox.showerror("Conversion Error", f"Failed to convert drawing path to actions:\n{e}", parent=self)
            return

        try:
            if self.original_template_name and self.original_template_name != template_name:

                self.job_manager.delete_shape_template(self.original_template_name)
                self.job_manager.add_shape_template(template_name, self.current_template_data)
            elif self.original_template_name:
                self.job_manager.update_shape_template(template_name, self.current_template_data)
            else: 
                self.job_manager.add_shape_template(template_name, self.current_template_data)

            messagebox.showinfo("Save Successful", f"Shape Template '{display_name}' saved successfully.", parent=self.master) # Thông báo trên master của Toplevel
            self._close_editor()
        except ValueError as ve:
            messagebox.showerror("Save Error", str(ve), parent=self)
        except Exception as e:
            logger.error(f"Unexpected error saving shape template '{template_name}': {e}", exc_info=True)
            messagebox.showerror("Save Error", f"An unexpected error occurred while saving:\n{e}", parent=self)


    def _on_cancel(self) -> None:
        self._close_editor()

    def _close_editor(self) -> None:
        if self.on_close_callback:
            try:
                self.on_close_callback()
            except Exception as e:
                logger.warning(f"Error in ShapeTemplateEditor on_close_callback: {e}")
        self.destroy()

    def destroy(self) -> None:
        display_name_for_log = "N/A"
        if hasattr(self, 'current_template_data') and isinstance(self.current_template_data, dict):
            display_name_for_log = self.current_template_data.get('display_name', 'N/A')
        
        logger.debug(f"Destroying ShapeTemplateEditor for '{display_name_for_log}'.")
        super().destroy()
