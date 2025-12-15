# core/job_manager.py
import json
import os
import keyboard 
import threading
import logging
import copy
import time
from typing import Dict, List, Optional, Any, TYPE_CHECKING, Callable 

if TYPE_CHECKING:
    from core.condition import Condition
    from utils.image_storage import ImageStorage 
    from utils.config_loader import ConfigLoader 

logger = logging.getLogger(__name__)

_CoreClassesImported = False
try:
    from core.job_run_condition import create_job_run_condition, JobRunCondition
    from core.job import Job, Action
    from core.job_executor import JobExecutor
    from core.trigger import Trigger, TriggerAction
    from core.observer import Observer 
    from core.condition_manager import ConditionManager
    from core.condition import Condition
    _CoreClassesImported = True
except ImportError as e:
    logger.critical(f"FATAL ERROR loading core classes in JobManager: {e}")
    _CoreClassesImported = False
    class Job:
        name: str; actions: List[Any]; hotkey: str; stop_key: str; enabled: bool; run_condition: Any; running: bool; params: Dict[str,Any]
        def __init__(self, name: str, actions: Optional[List[Any]]=None, hotkey: str="", stop_key: str ="", enabled: bool =True, run_condition: Any=None, job_params: Optional[Dict[str,Any]]=None) -> None: self.name=name; self.actions=actions or []; self.hotkey=hotkey; self.stop_key=stop_key; self.enabled=enabled; self.run_condition=run_condition; self.running=False; self.params = job_params or {}
        @classmethod
        def from_dict(cls, data: Dict[str,Any]) -> 'Job': return cls(data.get("name","DummyJob")) # type: ignore
        def to_dict(self) -> Dict[str,Any]: return {"name": self.name}
    class Action: condition_id: Optional[str] = None; type: str = "dummy"
    class JobExecutor:
        def __init__(self, job: Job, stop_event: Any, image_storage: Any =None, condition_manager: Any =None) -> None: pass
        def start(self) -> None: pass
        def stop(self, wait: bool =True, timeout: float =5.0) -> None: pass
    class JobRunCondition: pass
    def create_job_run_condition(d: Any) -> Any: return None
    class Trigger:
        name:str; enabled:bool; actions: List[Any]; conditions: List[Any]; check_interval_seconds:float; condition_logic:str; is_ai_trigger: bool
        def __init__(self, name:str, conditions:Optional[List[Any]]=None, actions:Optional[List[Any]]=None, enabled:bool=True, interval:float=0.5, logic:str="AND", is_ai_trigger:bool=False) -> None: self.name=name; self.enabled=enabled; self.actions=actions or []; self.conditions=conditions or []; self.check_interval_seconds=interval; self.condition_logic=logic; self.is_ai_trigger=is_ai_trigger
        @classmethod
        def from_dict(cls,d: Dict[str,Any]) -> 'Trigger': return cls(d.get("name","DummyTrigger"), is_ai_trigger=d.get("is_ai_trigger",False)) # type: ignore
        def to_dict(self) -> Dict[str,Any]: return {"name": self.name, "is_ai_trigger": self.is_ai_trigger}
    class TriggerAction: pass
    class Observer:
        running: bool; is_globally_enabled: bool; ai_brain_mode_enabled: bool
        def __init__(self, jm: Any, i: Any) -> None: self.running=False; self.is_globally_enabled = False; self.ai_brain_mode_enabled = False
        def load_triggers(self, t: List[Trigger]) -> None: pass
        def start(self) -> None: self.running=True
        def stop(self, wait:bool =True, timeout:float =0) -> None: self.running=False
        def set_global_enable(self, enabled: bool) -> None: self.is_globally_enabled = enabled
        def set_ai_brain_mode_enable(self, enabled: bool) -> None: self.ai_brain_mode_enabled = enabled
    class ConditionManager:
        shared_conditions: Dict[str, Any]
        def __init__(self) -> None: self.shared_conditions = {}
        def load_shared_conditions(self, data_list: List[Dict[str,Any]]) -> None: pass
        def clear_all_shared_conditions(self) -> None: pass
        def get_serializable_data(self) -> List[Dict[str,Any]]: return []
        def get_all_shared_conditions_summary(self) -> Dict[str, Dict[str,str]]: return {}
        def get_condition_display_map(self) -> Dict[str,str]: return {}
        def get_shared_condition_by_id(self,id_str:str) -> Optional[Any]: return None
        def add_or_update_shared_condition(self, c_obj: Any) -> bool: return False
        def update_shared_condition_from_data(self, id_str:str, data: Dict[str,Any]) -> bool: return False
        def delete_shared_condition(self, id_str:str) -> bool: return False
        def is_condition_id_in_use(self, id_str:str, jobs: List[Job]) -> bool: return False
    class Condition: id: str; name: str; type: str; is_monitored_by_ai_brain: bool

try:
    from utils.config_loader import ConfigLoader, DEFAULT_PROFILE_NAME
    from utils.image_storage import ImageStorage
    _UtilsImported = True
except ImportError as e:
     _UtilsImported = False
     class ConfigLoader:
          def profile_exists(self,p:str) -> bool: return False
          def create_profile(self,p:str,switch_to_it:bool=False) -> None: pass
          def load_profile(self,p:str) -> Dict[str,Any]: return {"jobs": {}, "triggers": {}, "shape_templates": {}, "shared_conditions": []}
          def save_profile(self,p:str,d: Dict[str,Any]) -> None: pass
          def list_profiles(self) -> List[str]: return []
          def delete_profile(self,p:str) -> bool: return False
     class ImageStorage: pass 
     DEFAULT_PROFILE_NAME = "default"


class JobManager:
    config_loader: 'ConfigLoader'
    _image_storage: 'ImageStorage'
    jobs: Dict[str, Job]
    triggers: Dict[str, Trigger] 
    shape_templates: Dict[str, Dict[str, Any]]
    condition_manager: ConditionManager
    current_profile_name: str
    running_executors: Dict[str, JobExecutor]
    _executor_stop_events: Dict[str, threading.Event]
    lock: threading.RLock
    _bound_hotkeys: Dict[str, str]  
    _bound_stopkeys: Dict[str, str] 
    _keyboard_hook_active: bool    
    observer: Optional[Observer]
    _is_globally_recording_keys: bool 


    def __init__(self, config_loader: 'ConfigLoader', image_storage: 'ImageStorage') -> None: # type: ignore
        if not _CoreClassesImported or not _UtilsImported:
            raise ImportError("JobManager failed to initialize due to missing dependencies (Core or Utils).")

        if not isinstance(config_loader, ConfigLoader): # type: ignore
             raise TypeError("JobManager requires a ConfigLoader instance.")

        self.config_loader = config_loader
        self._image_storage = image_storage
        self.jobs = {}
        self.triggers = {}
        self.shape_templates = {}
        self.condition_manager = ConditionManager()
        self.current_profile_name = DEFAULT_PROFILE_NAME
        self.running_executors = {}
        self._executor_stop_events = {}
        self.lock = threading.RLock()
        self._bound_hotkeys = {}
        self._bound_stopkeys = {}
        self._keyboard_hook_active = False 
        self._is_globally_recording_keys = False 
        self.observer = Observer(self, self._image_storage) if _CoreClassesImported and Observer else None # type: ignore

        try:
            self.load_profile(self.current_profile_name, force_reload=True) 
            if not self.config_loader.profile_exists(DEFAULT_PROFILE_NAME):
                self.create_profile(DEFAULT_PROFILE_NAME, switch_to_it=False) 
            self.start_observer()
        except Exception as e:
            logger.error(f"Error during JobManager initialization (profile load/observer start): {e}", exc_info=True)


    def start_observer(self) -> None:
        if self.observer and not self.observer.running:
             try:
                 self.observer.start()
                 logger.info("Observer started.")
             except Exception as e:
                  logger.error(f"Failed to start Observer: {e}", exc_info=True)
        elif not self.observer:
             logger.warning("Attempted to start Observer, but it's not initialized.")

    def stop_observer(self, wait: bool = True, timeout: float = 3.0) -> None:
        if self.observer and self.observer.running:
             try:
                 self.observer.stop(wait=wait, timeout=timeout)
                 logger.info("Observer stopped.")
             except Exception as e:
                 logger.error(f"Failed to stop Observer: {e}", exc_info=True)
        elif self.observer and not self.observer.running:
             logger.debug("Observer already stopped.")

    def set_ai_brain_mode(self, enabled: bool) -> None:
        if self.observer:
            try:
                self.observer.set_ai_brain_mode_enable(enabled)
                logger.info(f"AI Brain mode set to: {enabled}")
            except Exception as e:
                logger.error(f"Failed to set AI Brain mode: {e}", exc_info=True)

    def get_current_profile_name(self) -> str:
        return self.current_profile_name

    def list_available_profiles(self) -> List[str]:
        try:
            return self.config_loader.list_profiles()
        except Exception as e:
            logger.error(f"Failed to list available profiles: {e}", exc_info=True)
            return []

    def load_profile(self, profile_name: str, force_reload: bool = False) -> bool:
        if not isinstance(profile_name, str) or not profile_name.strip():
            logger.warning("Load profile: Invalid profile name provided.")
            return False
        profile_name = profile_name.strip()
        
        is_already_loaded_and_not_forced = (
            not force_reload and profile_name == self.current_profile_name and
            (self.jobs or self.triggers or self.shape_templates or self.condition_manager.shared_conditions)
        )
        if is_already_loaded_and_not_forced:
            logger.debug(f"Profile '{profile_name}' is already loaded and not forced to reload.")
            return True

        logger.info(f"Loading profile: '{profile_name}' (Force reload: {force_reload})")
        with self.lock:
            self.stop_all_running_jobs(wait=True, timeout=5.0)
            if self.observer: self.observer.set_global_enable(False) 
            self.stop_observer(wait=True, timeout=3.0)
            
            self._cleanup_bindings_internal() 

            profile_data: Dict[str,Any] = {}
            try:
                profile_data = self.config_loader.load_profile(profile_name)
            except Exception as e:
                logger.error(f"Failed to load profile data for '{profile_name}': {e}", exc_info=True)
                self.current_profile_name = DEFAULT_PROFILE_NAME
                if self.config_loader.profile_exists(DEFAULT_PROFILE_NAME):
                    profile_data = self.config_loader.load_profile(DEFAULT_PROFILE_NAME)
                else: 
                    self.create_profile(DEFAULT_PROFILE_NAME, switch_to_it=False) 
                    profile_data = self.config_loader.load_profile(DEFAULT_PROFILE_NAME) 

            loaded_jobs_data = profile_data.get("jobs", {}); loaded_triggers_data = profile_data.get("triggers", {})
            loaded_shape_templates_data = profile_data.get("shape_templates", {}); loaded_shared_conditions_data = profile_data.get("shared_conditions", [])

            if not isinstance(loaded_jobs_data, dict): loaded_jobs_data = {}; logger.warning("Jobs data was not a dict, reset.")
            if not isinstance(loaded_triggers_data, dict): loaded_triggers_data = {}; logger.warning("Triggers data was not a dict, reset.")
            if not isinstance(loaded_shape_templates_data, dict): loaded_shape_templates_data = {}; logger.warning("Shape templates data was not a dict, reset.")
            if not isinstance(loaded_shared_conditions_data, list): loaded_shared_conditions_data = []; logger.warning("Shared conditions data was not a list, reset.")

            new_jobs: Dict[str, Job] = {}
            if _CoreClassesImported:
                for job_name_key, job_data_val in loaded_jobs_data.items():
                    if not (isinstance(job_name_key, str) and job_name_key.strip() and isinstance(job_data_val, dict)): continue
                    try: job = Job.from_dict(job_data_val); job.name = job_name_key; new_jobs[job_name_key] = job # type: ignore
                    except Exception as e_job: logger.error(f"Error creating job '{job_name_key}' from data: {e_job}", exc_info=True)
            
            new_triggers: Dict[str, Trigger] = {}
            if _CoreClassesImported:
                for trigger_name_key, trigger_data_val in loaded_triggers_data.items():
                    if not (isinstance(trigger_name_key, str) and trigger_name_key.strip() and isinstance(trigger_data_val, dict)): continue
                    try: trigger = Trigger.from_dict(trigger_data_val); trigger.name = trigger_name_key; new_triggers[trigger_name_key] = trigger # type: ignore
                    except Exception as e_trig: logger.error(f"Error creating trigger '{trigger_name_key}' from data: {e_trig}", exc_info=True)
            
            self.jobs = new_jobs; self.triggers = new_triggers; self.shape_templates = loaded_shape_templates_data
            self.current_profile_name = profile_name 
            if self.condition_manager: self.condition_manager.load_shared_conditions(loaded_shared_conditions_data)

            if self.observer:
                 self.observer.load_triggers(list(self.triggers.values()))
                 self.start_observer()
            
            if not self._is_globally_recording_keys: 
                 self._bind_all_keys()
            else:
                logger.info(f"JobManager: Skipped binding keys after profile load, as global key recording is active.")

            logger.info(f"Profile '{profile_name}' loaded successfully.")
            return True

    def save_current_profile(self) -> None:
        profile_to_save = self.current_profile_name
        if not profile_to_save or not isinstance(profile_to_save, str) or not profile_to_save.strip():
            logger.error("Save profile: Invalid current profile name.")
            return
        with self.lock:
            try:
                current_jobs_data = {name: job.to_dict() for name, job in self.jobs.items() if isinstance(job, Job)}
                current_triggers_data = {name: trigger.to_dict() for name, trigger in self.triggers.items() if isinstance(trigger, Trigger)}
                current_shape_templates_data = copy.deepcopy(self.shape_templates)
                current_shared_conditions_data: List[Dict[str, Any]] = []
                if self.condition_manager: current_shared_conditions_data = self.condition_manager.get_serializable_data()
                
                profile_data_to_save = {
                    "jobs": current_jobs_data, "triggers": current_triggers_data,
                    "shape_templates": current_shape_templates_data, "shared_conditions": current_shared_conditions_data
                }
                self.config_loader.save_profile(profile_to_save, profile_data_to_save)
                logger.info(f"Profile '{profile_to_save}' saved successfully.")
            except Exception as e:
                logger.error(f"Failed to save profile '{profile_to_save}': {e}", exc_info=True)

    def create_profile(self, profile_name: str, switch_to_it: bool = True) -> bool:
        if not isinstance(profile_name, str) or not profile_name.strip():
            logger.warning("Create profile: Invalid profile name.")
            return False
        profile_name = profile_name.strip()
        if self.config_loader.profile_exists(profile_name):
            logger.warning(f"Profile '{profile_name}' already exists. Creation skipped.")
            return False
        try:
            empty_profile_data = {"jobs": {}, "triggers": {}, "shape_templates": {}, "shared_conditions": []}
            self.config_loader.save_profile(profile_name, empty_profile_data) 
            logger.info(f"Profile '{profile_name}' created.")
            if switch_to_it:
                self.load_profile(profile_name, force_reload=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create profile '{profile_name}': {e}", exc_info=True)
            return False

    def delete_profile(self, profile_name: str) -> bool:
         if not isinstance(profile_name, str) or not profile_name.strip():
             logger.warning("Delete profile: Invalid profile name.")
             return False
         profile_name = profile_name.strip()
         if profile_name == DEFAULT_PROFILE_NAME:
             logger.warning("Cannot delete the default profile.")
             return False
         if profile_name == self.current_profile_name:
             logger.warning("Cannot delete the currently active profile. Switch profiles first.")
             return False
         
         try:
             if self.config_loader.delete_profile(profile_name):
                 logger.info(f"Profile '{profile_name}' deleted.")
                 return True
             else:
                 logger.warning(f"Failed to delete profile '{profile_name}' (config_loader returned False).")
                 return False
         except Exception as e:
             logger.error(f"Error deleting profile '{profile_name}': {e}", exc_info=True)
             return False

    def create_job(self, name: str) -> Optional[Job]:
        with self.lock:
            if not isinstance(name, str) or not name.strip(): raise ValueError("Job name cannot be empty.")
            name = name.strip()
            if name in self.jobs: raise ValueError(f"Job '{name}' already exists in profile '{self.current_profile_name}'.")
            if not _CoreClassesImported: return None
            new_job = Job(name) # type: ignore
            self.jobs[name] = new_job
            self.save_current_profile()
            if new_job.enabled and not self._is_globally_recording_keys: self._bind_job_keys(new_job)
            logger.info(f"Job '{name}' created.")
            return new_job

    def add_job(self, job: Job) -> None:
        with self.lock:
            if not isinstance(job, Job): raise TypeError("Must provide a Job object.") # type: ignore
            name = job.name.strip()
            if not name: raise ValueError("Job name cannot be empty.")
            if name in self.jobs: raise ValueError(f"Job '{name}' already exists. Use update_job.")
            self.jobs[name] = job
            self.save_current_profile()
            if job.enabled and not self._is_globally_recording_keys: self._bind_job_keys(job)
            logger.info(f"Job '{name}' added.")


    def get_job(self, name: str) -> Optional[Job]:
        with self.lock: return self.jobs.get(name)

    def update_job(self, original_name: str, updated_job: Job) -> None:
        if not isinstance(updated_job, Job): raise TypeError("Updated job must be a Job object.") # type: ignore
        original_name = original_name.strip()
        if not original_name: raise ValueError("Original job name cannot be empty.")
        
        with self.lock:
            if original_name not in self.jobs: raise ValueError(f"Job '{original_name}' not found for update.")
            
            new_name = updated_job.name.strip()
            if not new_name: raise ValueError("Updated job name cannot be empty.")
            
            if new_name != original_name and new_name in self.jobs:
                raise ValueError(f"Cannot rename job to '{new_name}': A job with that name already exists.")

            is_running = self.is_job_running(original_name)
            if is_running: self.stop_job(original_name, wait=True)
            
            old_job_ref = self.jobs.get(original_name)
            if old_job_ref and not self._is_globally_recording_keys: self._unbind_job_keys(old_job_ref)
            
            if original_name != new_name: del self.jobs[original_name]
            self.jobs[new_name] = updated_job
            
            if updated_job.enabled and not self._is_globally_recording_keys: self._bind_job_keys(updated_job)
            self.save_current_profile()
            
            if is_running and updated_job.enabled: self.start_job(new_name) 
            logger.info(f"Job '{original_name}' updated (new name: '{new_name}').")


    def delete_job(self, name: str) -> None:
        with self.lock:
            if name not in self.jobs: raise ValueError(f"Job '{name}' not found for deletion.")
            if self.is_job_running(name): self.stop_job(name, wait=True)
            
            job_ref = self.jobs.get(name)
            if job_ref and not self._is_globally_recording_keys: self._unbind_job_keys(job_ref)
            
            del self.jobs[name]
            self.save_current_profile()
            logger.info(f"Job '{name}' deleted.")


    def enable_job(self, name: str, enable_status: bool) -> None:
         with self.lock:
              job = self.jobs.get(name)
              if not job: raise ValueError(f"Job '{name}' not found.")
              
              new_state = bool(enable_status)
              if job.enabled == new_state: return 
              
              if self.is_job_running(name) and not new_state: 
                  self.stop_job(name, wait=True)
              
              if not self._is_globally_recording_keys: self._unbind_job_keys(job) 
              job.enabled = new_state
              if job.enabled and not self._is_globally_recording_keys: self._bind_job_keys(job) 
              
              self.save_current_profile()
              logger.info(f"Job '{name}' enabled status set to {new_state}.")

    def add_trigger(self, trigger: Trigger) -> None:
        with self.lock:
            if not isinstance(trigger, Trigger): raise TypeError("Must provide a Trigger object.")
            name = trigger.name.strip()
            if not name: raise ValueError("Trigger name cannot be empty.")
            if name in self.triggers: raise ValueError(f"Trigger '{name}' already exists. Use update_trigger.")
            self.triggers[name] = trigger
            if self.observer: self.observer.load_triggers(list(self.triggers.values()))
            self.save_current_profile()
            logger.info(f"Trigger '{name}' added.")

    def get_trigger(self, name: str) -> Optional[Trigger]:
         with self.lock: return self.triggers.get(name)

    def get_all_triggers(self) -> List[str]:
         with self.lock: return list(self.triggers.keys())

    def update_trigger(self, original_name: str, updated_trigger: Trigger) -> None:
        if not isinstance(updated_trigger, Trigger): raise TypeError("Updated trigger must be a Trigger object.")
        original_name = original_name.strip()
        if not original_name: raise ValueError("Original trigger name cannot be empty.")
        with self.lock:
            if original_name not in self.triggers: raise ValueError(f"Trigger '{original_name}' not found.")
            new_name = updated_trigger.name.strip()
            if not new_name: raise ValueError("Updated trigger name cannot be empty.")
            if new_name != original_name and new_name in self.triggers:
                raise ValueError(f"Cannot rename trigger to '{new_name}': Name already exists.")
            if original_name != new_name: del self.triggers[original_name]
            self.triggers[new_name] = updated_trigger
            if self.observer: self.observer.load_triggers(list(self.triggers.values()))
            self.save_current_profile()
            logger.info(f"Trigger '{original_name}' updated (new name: '{new_name}').")


    def delete_trigger(self, name: str) -> bool:
        with self.lock:
            if name not in self.triggers:
                logger.warning(f"Attempted to delete non-existent trigger: '{name}'.")
                return False 

            del self.triggers[name]
            if self.observer: self.observer.load_triggers(list(self.triggers.values()))
            self.save_current_profile()
            logger.info(f"Trigger '{name}' deleted.")
            return True 


    def enable_trigger(self, name: str, enable_status: bool) -> None:
         with self.lock:
              trigger = self.triggers.get(name)
              if not trigger: raise ValueError(f"Trigger '{name}' not found.")
              new_enabled_state = bool(enable_status)
              if trigger.enabled == new_enabled_state: return
              trigger.enabled = new_enabled_state
              self.save_current_profile()
              logger.info(f"Trigger '{name}' enabled status set to {new_enabled_state}.")

    def add_shared_condition(self, condition_obj: 'Condition') -> bool:
        if self.condition_manager:
            if self.condition_manager.add_or_update_shared_condition(condition_obj):
                self.save_current_profile(); return True
        return False

    def update_shared_condition(self, condition_id: str, updated_condition_data: Dict[str, Any]) -> bool:
        if self.condition_manager:
            if self.condition_manager.update_shared_condition_from_data(condition_id, updated_condition_data):
                self.save_current_profile(); return True
        return False

    def delete_shared_condition(self, condition_id: str) -> bool:
        if not self.condition_manager: return False
        try:
            all_jobs = list(self.jobs.values()) if self.jobs else []
            if self.condition_manager.is_condition_id_in_use(condition_id, all_jobs): 
                cond_obj = self.condition_manager.get_shared_condition_by_id(condition_id)
                cond_name_for_msg = cond_obj.name if cond_obj else condition_id
                raise ValueError(f"Cannot delete condition '{cond_name_for_msg}': It is currently used by one or more actions.")
            if self.condition_manager.delete_shared_condition(condition_id):
                self.save_current_profile(); return True
            return False
        except ValueError as ve: raise ve
        except Exception as e: logger.error(f"Error deleting shared condition {condition_id}: {e}"); return False


    def get_shared_condition_by_id(self, condition_id: str) -> Optional['Condition']:
        return self.condition_manager.get_shared_condition_by_id(condition_id) if self.condition_manager else None

    def get_all_shared_conditions_summary(self) -> Dict[str, Dict[str, str]]:
        return self.condition_manager.get_all_shared_conditions_summary() if self.condition_manager else {}
    
    def get_condition_display_map_for_ui(self) -> Dict[str,str]:
        return self.condition_manager.get_condition_display_map() if self.condition_manager else {}

    def add_shape_template(self, template_name: str, template_data: Dict[str, Any]) -> None:
        with self.lock:
            if not isinstance(template_name, str) or not template_name.strip(): raise ValueError("Shape Template internal name cannot be empty.")
            if not isinstance(template_data, dict): raise ValueError("Shape Template data must be a dictionary.")
            if template_data.get("template_name") != template_name: template_data["template_name"] = template_name
            if template_name in self.shape_templates: raise ValueError(f"Shape Template '{template_name}' already exists. Use update.")
            self.shape_templates[template_name] = copy.deepcopy(template_data)
            self.save_current_profile()
            logger.info(f"Shape template '{template_name}' added.")

    def get_shape_template_data(self, template_name: str) -> Optional[Dict[str, Any]]:
        with self.lock: return copy.deepcopy(self.shape_templates.get(template_name))

    def update_shape_template(self, original_template_name: str, updated_template_data: Dict[str, Any]) -> None:
        with self.lock:
            if not (isinstance(original_template_name, str) and original_template_name.strip()): raise ValueError("Original name empty.")
            if not isinstance(updated_template_data, dict): raise ValueError("Updated data not dict.")
            new_internal_name = updated_template_data.get("template_name", "").strip()
            if not new_internal_name: raise ValueError("Updated data needs valid 'template_name'.")
            if original_template_name not in self.shape_templates: raise ValueError(f"Template '{original_template_name}' not found for update.")
            if original_template_name != new_internal_name and new_internal_name in self.shape_templates:
                raise ValueError(f"Cannot rename to '{new_internal_name}': Name exists.")
            if original_template_name != new_internal_name: del self.shape_templates[original_template_name]
            self.shape_templates[new_internal_name] = copy.deepcopy(updated_template_data)
            self.save_current_profile()
            logger.info(f"Shape template '{original_template_name}' updated (new name: '{new_internal_name}').")


    def delete_shape_template(self, template_name: str) -> None:
        with self.lock:
            if not (isinstance(template_name, str) and template_name.strip()): raise ValueError("Name empty for deletion.")
            if template_name not in self.shape_templates: raise ValueError(f"Template '{template_name}' not found for deletion.")
            del self.shape_templates[template_name]
            self.save_current_profile()
            logger.info(f"Shape template '{template_name}' deleted.")


    def list_shape_templates(self) -> List[str]:
        with self.lock: return sorted(list(self.shape_templates.keys()))

    def get_shape_template_display_names(self) -> Dict[str, str]:
        with self.lock:
            if not self.shape_templates: return {}
            name_pairs = [(data.get("display_name", name), name) for name, data in self.shape_templates.items() if isinstance(data, dict)]
            name_pairs.sort(key=lambda item: item[0].lower())
            return {internal: display for display, internal in name_pairs}

    def get_all_jobs(self) -> List[str]:
        with self.lock: return list(self.jobs.keys())

    def is_job_running(self, name: str) -> bool:
        with self.lock: return name in self.running_executors

    def start_job(self, name: str) -> None:
        with self.lock:
            job = self.jobs.get(name)
            if not job: raise ValueError(f"Job '{name}' not found.")
            if not job.enabled: raise ValueError(f"Job '{name}' is disabled.")
            if name in self.running_executors: return
            stop_event = threading.Event()
            if not _CoreClassesImported: raise ImportError("Cannot start job: Core JobExecutor not available.")
            executor = JobExecutor(job, stop_event, image_storage=self._image_storage, condition_manager=self.condition_manager) # type: ignore
            self.running_executors[name] = executor
            self._executor_stop_events[name] = stop_event
            job.running = True
        try: executor.start()
        except Exception as e:
             with self.lock:
                  if name in self.running_executors: del self.running_executors[name]
                  if name in self._executor_stop_events: del self._executor_stop_events[name]
                  job_ref = self.jobs.get(name)
                  if job_ref: job_ref.running = False
             raise e

    def stop_job(self, name: str, wait: bool = True, timeout: float = 5.0) -> None:
        executor_to_stop: Optional[JobExecutor] = None
        job_object: Optional[Job] = None
        with self.lock:
            job_object = self.jobs.get(name)
            if not job_object: return
            if name not in self.running_executors:
                if job_object.running: job_object.running = False
                return
            executor_to_stop = self.running_executors.pop(name, None)
            if name in self._executor_stop_events: del self._executor_stop_events[name]
            job_object.running = False
        if executor_to_stop:
             try: executor_to_stop.stop(wait=wait, timeout=timeout)
             except Exception: pass

    def toggle_job(self, name: str) -> None:
        job: Optional[Job] = None
        is_running_check = False
        with self.lock:
            job = self.jobs.get(name)
            if not job: raise ValueError(f"Job '{name}' not found.")
            is_running_check = name in self.running_executors
            if not job.enabled and not is_running_check:
                raise ValueError(f"Cannot toggle disabled and stopped job '{name}'.")
        
        if is_running_check: self.stop_job(name)
        else:
            if job and not job.enabled: raise ValueError(f"Cannot start disabled job '{name}'.")
            self.start_job(name)

    def stop_all_running_jobs(self, wait: bool = True, timeout: float = 5.0) -> None:
        jobs_to_stop: List[str] = []
        with self.lock:
            jobs_to_stop = list(self.running_executors.keys())
            if not jobs_to_stop: return
        for job_name_to_stop in jobs_to_stop:
            try: self.stop_job(job_name_to_stop, wait=wait, timeout=timeout)
            except Exception: pass

    def _ensure_keyboard_hook(self) -> None:
        """
        Ensures the keyboard library's global hook is active if it wasn't already.
        This is a general check and might be redundant if keyboard.add_hotkey already does this.
        The _keyboard_hook_active flag tracks if JobManager thinks it has listeners.
        """
        if not self._keyboard_hook_active:
            try:
                self._keyboard_hook_active = True 
                logger.debug("JobManager: Keyboard hook mechanism ensured (or assumed active by library).")
            except Exception as e:
                 logger.error(f"JobManager: Error trying to ensure keyboard hook: {e}")
                 self._keyboard_hook_active = False

    def _bind_job_keys(self, job: Job) -> None:
        if self._is_globally_recording_keys: 
            logger.debug(f"JobManager: Skipping binding keys for job '{job.name}' as global key recording is active.")
            return
        if not isinstance(job, Job) or not job.enabled: return # type: ignore
        
        with self.lock:
            clean_hotkey = job.hotkey.strip().lower() if job.hotkey else ""
            clean_stopkey = job.stop_key.strip().lower() if job.stop_key else ""
            job_name_for_lambda = job.name 

            if clean_hotkey:
                if clean_hotkey in self._bound_hotkeys or clean_hotkey in self._bound_stopkeys:
                    logger.warning(f"Hotkey '{clean_hotkey}' for job '{job.name}' is already bound or is a stopkey. Skipping.")
                else:
                    try:
                        keyboard.add_hotkey(clean_hotkey, lambda jn=job_name_for_lambda: self.toggle_job(jn), suppress=True)
                        self._bound_hotkeys[clean_hotkey] = job_name_for_lambda
                        self._ensure_keyboard_hook() 
                        logger.debug(f"JobManager: Bound hotkey '{clean_hotkey}' to job '{job.name}'.")
                    except Exception as e:
                        logger.error(f"JobManager: Failed to bind hotkey '{clean_hotkey}' for job '{job.name}': {e}")
            
            if clean_stopkey and clean_stopkey != clean_hotkey: # 
                 if clean_stopkey in self._bound_hotkeys or clean_stopkey in self._bound_stopkeys:
                     logger.warning(f"Stopkey '{clean_stopkey}' for job '{job.name}' is already bound or is a hotkey. Skipping.")
                 else:
                    try:
                        keyboard.add_hotkey(clean_stopkey, lambda jn=job_name_for_lambda: self.stop_job(jn, wait=False), suppress=True)
                        self._bound_stopkeys[clean_stopkey] = job_name_for_lambda
                        self._ensure_keyboard_hook() 
                        logger.debug(f"JobManager: Bound stopkey '{clean_stopkey}' to job '{job.name}'.")
                    except Exception as e:
                        logger.error(f"JobManager: Failed to bind stopkey '{clean_stopkey}' for job '{job.name}': {e}")

    def _unbind_job_keys(self, job: Job) -> None:
         if not isinstance(job, Job): return # type: ignore
         with self.lock:
             clean_hotkey = job.hotkey.strip().lower() if job.hotkey else ""
             clean_stopkey = job.stop_key.strip().lower() if job.stop_key else ""
             job_name = job.name
             
             if clean_hotkey and self._bound_hotkeys.get(clean_hotkey) == job_name:
                 try:
                     keyboard.remove_hotkey(clean_hotkey)
                     del self._bound_hotkeys[clean_hotkey]
                     logger.debug(f"JobManager: Unbound hotkey '{clean_hotkey}' for job '{job.name}'.")
                 except Exception as e:
                     logger.warning(f"JobManager: Error unbinding hotkey '{clean_hotkey}' for job '{job.name}': {e}")
             
             if clean_stopkey and clean_stopkey != clean_hotkey and self._bound_stopkeys.get(clean_stopkey) == job_name:
                  try:
                      keyboard.remove_hotkey(clean_stopkey)
                      del self._bound_stopkeys[clean_stopkey]
                      logger.debug(f"JobManager: Unbound stopkey '{clean_stopkey}' for job '{job.name}'.")
                  except Exception as e:
                      logger.warning(f"JobManager: Error unbinding stopkey '{clean_stopkey}' for job '{job.name}': {e}")

    def _bind_all_keys(self) -> None:
        logger.info("JobManager: Binding all job keys for current profile...")
        with self.lock:
            self._cleanup_bindings_internal() 
            
            for job_obj in self.jobs.values():
                 if isinstance(job_obj, Job) and job_obj.enabled: # type: ignore
                     self._bind_job_keys(job_obj) 
            
            if self._bound_hotkeys or self._bound_stopkeys:
                self._keyboard_hook_active = True 
                logger.info("JobManager: Finished binding all job keys. Hook active flag set.")
            else:
                self._keyboard_hook_active = False
                logger.info("JobManager: Finished binding all job keys. No keys to bind, hook active flag unset.")


    def _cleanup_bindings_internal(self):
        """Internal helper to unbind all keys JobManager is tracking, without changing _keyboard_hook_active."""
        logger.debug("JobManager: Internal cleanup of all tracked hotkeys and stopkeys...")
        keys_to_remove = list(self._bound_hotkeys.keys()) + list(self._bound_stopkeys.keys())
        unique_keys_to_remove = list(set(keys_to_remove))

        for key_str in unique_keys_to_remove:
            try:
                keyboard.remove_hotkey(key_str)
                logger.debug(f"JobManager: Removed binding for key '{key_str}' during internal cleanup.")
            except Exception as e:
                logger.warning(f"JobManager: Error removing binding for key '{key_str}' during internal cleanup: {e}")
        
        self._bound_hotkeys.clear()
        self._bound_stopkeys.clear()
        logger.debug("JobManager: Tracked hotkey/stopkey dictionaries cleared.")


    def cleanup_bindings(self) -> None:
         """Unbinds all JobManager hotkeys and stopkeys. Typically called on application shutdown or full profile unload."""
         with self.lock:
              self._cleanup_bindings_internal() 
              self._keyboard_hook_active = False 
              logger.info("JobManager: All hotkey bindings cleaned up (e.g., for shutdown). Hook active flag unset.")


    def handle_global_key_hook_state_change(self, is_hook_being_taken_by_recorder: bool):
        logger.info(f"JobManager: Received hook state change. Is hook being taken: {is_hook_being_taken_by_recorder}. Current JM recording flag: {self._is_globally_recording_keys}")
        with self.lock:
            if is_hook_being_taken_by_recorder:
                if not self._is_globally_recording_keys: 
                    logger.info("JobManager: Global key hook being taken by a KeyRecorder. Unbinding job hotkeys temporarily.")
                    self._cleanup_bindings_internal() 
                    self._is_globally_recording_keys = True
                else:
                    logger.debug("JobManager: Hook state change (taken), but JobManager already in 'globally recording' state. No action on bindings.")
            else: 
                if self._is_globally_recording_keys: 
                    logger.info("JobManager: Global key hook released by KeyRecorder. Rebinding job hotkeys.")
                    self._is_globally_recording_keys = False 
                    self._bind_all_keys() 
                else:
                    logger.debug("JobManager: Hook state change (released), but JobManager not in 'globally recording' state. No action on bindings.")
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
