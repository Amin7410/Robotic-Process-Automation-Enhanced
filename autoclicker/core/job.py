# core/job.py
import logging
import time 
import threading 
from typing import List, Dict, Any, Optional # Thêm Optional

logger = logging.getLogger(__name__)

_ActionImported = False
try:
    from core.action import Action
    _ActionImported = True
except ImportError:
    logger.warning("Could not import Action class. Job serialization/deserialization involving actions may fail or be limited.")
    class Action: # type: ignore
        type: str; params: Dict[str,Any]; condition_id: Optional[str]
        next_action_index_if_condition_met: Optional[int]
        next_action_index_if_condition_not_met: Optional[int]
        def __init__(self, type:str="unknown_dummy", params:Optional[Dict[str,Any]]=None, condition_id:Optional[str]=None,
                    next_action_index_if_condition_met:Optional[int]=None, next_action_index_if_condition_not_met:Optional[int]=None) -> None:
            self.type = type; self.params = params or {}; self.condition_id = condition_id
            self.next_action_index_if_condition_met = next_action_index_if_condition_met
            self.next_action_index_if_condition_not_met = next_action_index_if_condition_not_met
        def to_dict(self) -> Dict[str,Any]:
            return {
                "type": self.type, "params": self.params, "condition_id": self.condition_id,
                "next_action_index_if_condition_met": self.next_action_index_if_condition_met,
                "next_action_index_if_condition_not_met": self.next_action_index_if_condition_not_met,
            }
        @classmethod
        def from_dict(cls, data: Dict[str,Any]) -> 'Action':
            return cls( str(data.get("type", "dummy_error")), data.get("params", {}), data.get("condition_id"),
                        data.get("next_action_index_if_condition_met"), data.get("next_action_index_if_condition_not_met") )
        def __repr__(self) -> str: return f"DummyAction(type='{self.type}', ...)"
    _ActionImported = False


_JobRunConditionImported = False
try:
    from core.job_run_condition import JobRunCondition, InfiniteRunCondition, create_job_run_condition
    _JobRunConditionImported = True
except ImportError:
    logger.warning("Could not import JobRunCondition classes. Job run condition handling will be limited.")
    class JobRunCondition: # type: ignore
        type: str; params: Dict[str, Any]
        def __init__(self, type:str="dummy_rc", params:Optional[Dict[str,Any]]=None): self.type = type; self.params = params or {}
        def to_dict(self) -> Dict[str,Any]: return {"type":self.type, "params":self.params}
    class InfiniteRunCondition(JobRunCondition): # type: ignore
        def __init__(self, params:Optional[Dict[str,Any]]=None): super().__init__("infinite", params)
    def create_job_run_condition(data: Optional[Dict[str,Any]]) -> JobRunCondition: # type: ignore
        if data and isinstance(data, dict) and data.get("type") == "infinite": return InfiniteRunCondition(data.get("params"))
        return InfiniteRunCondition() 
    _JobRunConditionImported = False



class Job:
    name: str
    actions: List[Action]
    hotkey: str
    stop_key: str
    enabled: bool
    run_condition: JobRunCondition
    running: bool
    params: Dict[str, Any]


    def __init__(self, name: str, actions: Optional[List[Action]] = None,
                 hotkey: str = "", stop_key: str = "", enabled: bool = True,
                 run_condition: Optional[JobRunCondition] = None,
                 job_params: Optional[Dict[str, Any]] = None) -> None: 
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Job name must be a non-empty string.")
        self.name = name.strip()

        self.actions = []
        if actions is not None:
            if isinstance(actions, list):
                 valid_actions: List[Action] = []
                 for item in actions:
                     if _ActionImported and isinstance(item, Action): 
                         valid_actions.append(item)
                 self.actions = valid_actions

        self.hotkey = hotkey if isinstance(hotkey, str) else ""
        self.stop_key = stop_key if isinstance(stop_key, str) else ""
        self.enabled = bool(enabled)

        if _JobRunConditionImported and isinstance(run_condition, JobRunCondition):
             self.run_condition = run_condition
        else:
             self.run_condition = InfiniteRunCondition() if _JobRunConditionImported else JobRunCondition("infinite") # type: ignore

        self.params = job_params if isinstance(job_params, dict) else {} 
        self.running = False

    
    def to_dict(self) -> Dict[str, Any]:
        actions_data: List[Dict[str, Any]] = []
        if isinstance(self.actions, list):
            for action in self.actions:
                try:
                    if _ActionImported and isinstance(action, Action):
                        actions_data.append(action.to_dict())
                    elif isinstance(action, dict): 
                         actions_data.append(action)
                except Exception:
                     pass

        run_condition_data: Dict[str, Any] = {"type": "infinite", "params": {}} 
        if hasattr(self.run_condition, 'to_dict'):
             try: run_condition_data = self.run_condition.to_dict()
             except Exception: pass
        
        job_dict: Dict[str, Any] = {
             "name": self.name, "actions": actions_data,
             "hotkey": self.hotkey, "stop_key": self.stop_key,
             "enabled": self.enabled, "run_condition": run_condition_data,
             "params": self.params 
        }
        return job_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        if not isinstance(data, dict):
            raise ValueError("Input data for Job.from_dict must be a dictionary.")
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
             raise ValueError("Job data must contain a non-empty 'name' string.")
        name = name.strip()

        hotkey = data.get("hotkey", ""); stop_key = data.get("stop_key", "")
        enabled = data.get("enabled", True)
        actions_data = data.get("actions", [])
        deserialized_actions: List[Action] = []
        
        if isinstance(actions_data, list):
             if _ActionImported: 
                 for a_data in actions_data:
                     try:
                         if isinstance(a_data, dict): deserialized_actions.append(Action.from_dict(a_data))
                     except Exception: pass

        run_condition_data = data.get("run_condition")
        run_condition_obj: JobRunCondition
        if _JobRunConditionImported:
            run_condition_obj = create_job_run_condition(run_condition_data) # type: ignore
        else: 
            run_condition_obj = JobRunCondition("infinite" if not run_condition_data or not isinstance(run_condition_data, dict) else str(run_condition_data.get("type","infinite")), 
                                                run_condition_data.get("params",{}) if run_condition_data and isinstance(run_condition_data, dict) else {}) # type: ignore
        
        job_params_data = data.get("params", {}) 
        if not isinstance(job_params_data, dict): job_params_data = {}


        try:
            job_instance = cls(name=name, actions=deserialized_actions, hotkey=hotkey,
                               stop_key=stop_key, enabled=enabled,
                               run_condition=run_condition_obj, job_params=job_params_data)
            return job_instance
        except Exception as e:
             raise ValueError(f"Could not construct Job '{name}' from dictionary data.") from e

    def __str__(self) -> str:
        status = "Running" if self.running else "Stopped"; enabled_status = "Enabled" if self.enabled else "Disabled"
        run_cond_desc = str(self.run_condition) if hasattr(self.run_condition, '__str__') else "Unknown RunCond"
        hotkey_display = self.hotkey if self.hotkey and self.hotkey.strip() else "None"
        stopkey_display = self.stop_key if self.stop_key and self.stop_key.strip() else "None"
        is_brain = False
        if isinstance(self.actions, list):
            for a in self.actions:
                 if isinstance(a, Action): 
                      if (hasattr(a, 'next_action_index_if_condition_met') and isinstance(a.next_action_index_if_condition_met, int) and a.next_action_index_if_condition_met >= 0) or \
                         (hasattr(a, 'next_action_index_if_condition_not_met') and isinstance(a.next_action_index_if_condition_not_met, int) and a.next_action_index_if_condition_not_met >= 0):
                          is_brain = True; break
        brain_status = " (Logic Flow)" if is_brain else ""
        return (f"Job(name='{self.name}', actions={len(self.actions)}, {run_cond_desc}, "
                f"hotkey='{hotkey_display}', stop_key='{stopkey_display}', {enabled_status}, {status}){brain_status}")

    def __repr__(self) -> str:
        actions_repr = repr(self.actions)
        run_condition_repr = repr(self.run_condition)
        return (f"Job(name={repr(self.name)}, actions={actions_repr}, hotkey={repr(self.hotkey)}, "
                f"stop_key={repr(self.stop_key)}, enabled={repr(self.enabled)}, run_condition={run_condition_repr}, "
                f"running={repr(self.running)}, params={repr(self.params)})")
