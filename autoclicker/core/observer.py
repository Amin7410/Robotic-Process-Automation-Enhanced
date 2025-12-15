# core/observer.py
import threading
import time
import logging
from typing import TYPE_CHECKING, List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

_CoreClassesImported = False
try:
    from core.trigger import Trigger, TriggerAction
    from core.condition import Condition
    _CoreClassesImported = True
except ImportError as e:
    _CoreClassesImported = False
    class Condition: # type: ignore
        id: str; name: str; type: str; is_monitored_by_ai_brain: bool = False
        def __init__(self, id_val:str="dummy_cond_id", name_val:str="DummyCond", type_val:str="dummy", is_monitored:bool=False) -> None: self.id=id_val; self.name=name_val; self.type=type_val; self.is_monitored_by_ai_brain=is_monitored
        def check(self, **c: Any) -> bool: return False
    class Trigger: # type: ignore
        name: str; enabled: bool; check_interval_seconds: float; last_checked_time: float; last_triggered_time: float
        actions: List[Any]; conditions: List[Condition]; condition_logic: str
        is_ai_trigger: bool 
        def __init__(self, name: str = "DummyTrigger", conditions: Optional[List[Condition]] = None, actions: Optional[List[Any]] = None,
                     enabled: bool = True, interval: float = 1.0, logic: str = "AND", is_ai_trigger: bool = False) -> None:
            self.name=name; self.enabled=enabled; self.actions = actions or []
            self.conditions = conditions or []; self.check_interval_seconds=interval;
            self.condition_logic=logic; self.last_checked_time=0.0; self.last_triggered_time = 0.0
            self.is_ai_trigger = is_ai_trigger
        def should_check(self, t: float) -> bool: return self.enabled and (t - self.last_checked_time >= self.check_interval_seconds)
        def check_conditions(self, **c: Any) -> bool: return False 
        def trigger(self, t: float) -> Optional[List[Any]]: return self.actions if self.actions else None
    class TriggerAction: pass # type: ignore
    

if TYPE_CHECKING:
    from core.job_manager import JobManager
    from utils.image_storage import ImageStorage
    from core.condition_manager import ConditionManager


class Observer:
    job_manager: 'JobManager'
    image_storage: Optional['ImageStorage']
    _triggers: List[Trigger]
    _ai_triggers: List[Trigger]
    _monitored_conditions_map: Dict[str, bool]
    _observer_thread: Optional[threading.Thread]
    _stop_event: threading.Event
    lock: threading.Lock
    running: bool
    is_globally_enabled: bool
    ai_brain_mode_enabled: bool

    def __init__(self, job_manager: 'JobManager', image_storage: Optional['ImageStorage']) -> None: # type: ignore
        self.job_manager = job_manager
        self.image_storage = image_storage
        self._triggers = []
        self._ai_triggers = []
        self._monitored_conditions_map = {}
        self._observer_thread = None
        self._stop_event = threading.Event()
        self.lock = threading.Lock()
        self.running = False
        self.is_globally_enabled = False
        self.ai_brain_mode_enabled = False

    def load_triggers(self, triggers_from_profile: List[Trigger]) -> None:
        if not isinstance(triggers_from_profile, list):
            return
        logger.debug("def load_triggers")
        with self.lock:
            self._triggers = []
            self._ai_triggers = []
            
            for t_obj in triggers_from_profile: 
                if _CoreClassesImported and isinstance(t_obj, Trigger):
                     t_obj.last_checked_time = 0.0
                     t_obj.last_triggered_time = 0.0
                     if hasattr(t_obj, 'is_ai_trigger') and t_obj.is_ai_trigger:
                         self._ai_triggers.append(t_obj)
                     else:
                         self._triggers.append(t_obj)
                elif not _CoreClassesImported and hasattr(t_obj, 'name'):
                    if hasattr(t_obj, 'is_ai_trigger') and t_obj.is_ai_trigger: # type: ignore
                         self._ai_triggers.append(t_obj) # type: ignore
                    else:
                         self._triggers.append(t_obj) # type: ignore
            if self.ai_brain_mode_enabled:
                 self._refresh_monitored_conditions_list()


    def set_global_enable(self, enabled: bool) -> None:
        logger.debug("set_global_enable")
        if self.is_globally_enabled != enabled:
            self.is_globally_enabled = enabled

    def set_ai_brain_mode_enable(self, enabled: bool) -> None:
        logger.debug("set_ai_brain_mode_enable")
        if self.ai_brain_mode_enabled != enabled:
            self.ai_brain_mode_enabled = enabled
            if enabled:
                self._refresh_monitored_conditions_list()
            else:
                with self.lock:
                    self._monitored_conditions_map.clear()

    def _refresh_monitored_conditions_list(self) -> None:
        if not self.job_manager or not hasattr(self.job_manager, 'condition_manager') or not self.job_manager.condition_manager:
            with self.lock: self._monitored_conditions_map.clear() 
            return

        with self.lock:
            logger.debug("_refresh_monitored_conditions_list")
            self._monitored_conditions_map.clear()
            condition_manager = self.job_manager.condition_manager
            all_shared_conditions: List[Condition] = []
            if hasattr(condition_manager, 'get_all_shared_conditions'):
                all_shared_conditions = condition_manager.get_all_shared_conditions()

            for cond in all_shared_conditions:
                if (_CoreClassesImported and isinstance(cond, Condition) and cond.is_monitored_by_ai_brain) or \
                   (not _CoreClassesImported and hasattr(cond, 'is_monitored_by_ai_brain') and cond.is_monitored_by_ai_brain): # type: ignore
                    if hasattr(cond, 'id') and isinstance(cond.id, str):
                         self._monitored_conditions_map[cond.id] = False
    def start(self) -> None:
        logger.debug("Observer: Start method called.")
        if self.running or (self._observer_thread and self._observer_thread.is_alive()):
            logger.debug("Observer: Already running or thread alive.")
            return
        if not _CoreClassesImported or not self.job_manager:
            logger.warning("Observer: Cannot start, core classes or job_manager missing.")
            return

        self.is_globally_enabled = True 
        self._stop_event.clear()
        self.running = True
        if self.ai_brain_mode_enabled:
            self._refresh_monitored_conditions_list()
        self._observer_thread = threading.Thread(target=self._observer_loop, name="ObserverThread", daemon=True)
        try:
            self._observer_thread.start()
            logger.info("Observer: Thread started.")
        except RuntimeError as e:
            logger.error(f"Observer: Runtime error starting thread: {e}")
            self.running = False
            self.is_globally_enabled = False 
            self._observer_thread = None

    def stop(self, wait: bool = True, timeout: float = 3.0) -> None:
        logger.debug("stop")
        self.set_global_enable(False) 
        if not self.running and not (self._observer_thread and self._observer_thread.is_alive()): return
        self._stop_event.set(); self.running = False
        thread_to_join = self._observer_thread; self._observer_thread = None
        if wait and thread_to_join and thread_to_join.is_alive(): thread_to_join.join(timeout)

    def _observer_loop(self) -> None:
        logger.debug("_observer_loop")
        min_sleep_time = 0.1; disabled_sleep_time = 1.0
        ai_brain_scan_interval = 0.2; last_ai_brain_scan_time = 0.0

        while not self._stop_event.is_set():
            try:
                if not self.is_globally_enabled:
                    if self._stop_event.wait(timeout=disabled_sleep_time): break
                    continue

                current_time = time.monotonic()
                actions_to_execute_batch: List[TriggerAction] = [] # type: ignore
                
                if self.ai_brain_mode_enabled and (current_time - last_ai_brain_scan_time >= ai_brain_scan_interval):
                    self._scan_monitored_conditions(current_time)
                    with self.lock: 
                        ai_triggers_copy = list(self._ai_triggers)
                    for ai_trigger in ai_triggers_copy:
                        if ai_trigger.enabled and ai_trigger.should_check(current_time):
                            if self._check_ai_trigger_conditions(ai_trigger, current_time):
                                triggered_actions = ai_trigger.trigger(current_time)
                                if triggered_actions: actions_to_execute_batch.extend(triggered_actions)
                    last_ai_brain_scan_time = current_time

                next_regular_trigger_check_time = float('inf')
                with self.lock: 
                    regular_triggers_copy = list(self._triggers)
                for trigger in regular_triggers_copy:
                    if trigger.enabled and trigger.should_check(current_time):
                        context = {"image_storage_instance": self.image_storage, "condition_manager": self.job_manager.condition_manager if self.job_manager else None}
                        try:
                            is_condition_met = trigger.check_conditions(**context)
                            if is_condition_met:
                                triggered_actions = trigger.trigger(current_time)
                                if triggered_actions: actions_to_execute_batch.extend(triggered_actions)
                        except Exception: pass
                    if trigger.enabled:
                        trigger_next_check = trigger.last_checked_time + trigger.check_interval_seconds
                        next_regular_trigger_check_time = min(next_regular_trigger_check_time, trigger_next_check)
                
                if actions_to_execute_batch:
                    self._execute_triggered_actions(actions_to_execute_batch)
                    actions_to_execute_batch.clear()

                sleep_duration = min_sleep_time
                time_until_next_regular_check = max(0, next_regular_trigger_check_time - time.monotonic())
                
                if self.ai_brain_mode_enabled:
                    time_until_next_ai_scan = max(0, (last_ai_brain_scan_time + ai_brain_scan_interval) - time.monotonic())
                    current_ai_triggers_exist = False
                    current_monitored_conds_exist = False
                    with self.lock:
                        current_ai_triggers_exist = bool(self._ai_triggers)
                        current_monitored_conds_exist = bool(self._monitored_conditions_map)
                    
                    effective_ai_check_interval = time_until_next_ai_scan if (current_ai_triggers_exist or current_monitored_conds_exist) else float('inf')
                    effective_regular_check_interval = time_until_next_regular_check if self._triggers else float('inf')
                    sleep_duration = max(min_sleep_time, min(effective_regular_check_interval, effective_ai_check_interval))

                else: 
                    sleep_duration = max(min_sleep_time, time_until_next_regular_check if self._triggers else disabled_sleep_time)
                
                no_regular_triggers = False
                no_ai_activity = True
                with self.lock:
                    no_regular_triggers = not bool(self._triggers)
                    if self.ai_brain_mode_enabled:
                        no_ai_activity = not (bool(self._ai_triggers) or bool(self._monitored_conditions_map))
                
                if no_regular_triggers and no_ai_activity :
                    sleep_duration = disabled_sleep_time


                if self._stop_event.wait(timeout=sleep_duration): break
            except Exception:
                if self._stop_event.wait(timeout=5.0): break
        
    def _scan_monitored_conditions(self, current_time: float) -> None:
        logger.debug("_scan_monitored_conditions")
        if not self.job_manager or not hasattr(self.job_manager, 'condition_manager') or not self.job_manager.condition_manager:
            return

        condition_manager = self.job_manager.condition_manager
        with self.lock:
            monitored_ids_copy = list(self._monitored_conditions_map.keys())
            for cond_id in monitored_ids_copy: 
                condition_obj = condition_manager.get_shared_condition_by_id(cond_id)
                if condition_obj and hasattr(condition_obj, 'is_monitored_by_ai_brain') and condition_obj.is_monitored_by_ai_brain:
                    context = {"image_storage_instance": self.image_storage, "condition_manager": condition_manager}
                    try:
                        current_check_result = condition_obj.check(**context)
                        self._monitored_conditions_map[cond_id] = current_check_result
                    except Exception:
                        self._monitored_conditions_map[cond_id] = False 
                else:
                    if cond_id in self._monitored_conditions_map:
                        del self._monitored_conditions_map[cond_id]
        
    def _check_ai_trigger_conditions(self, ai_trigger: Trigger, current_time: float) -> bool:
        logger.debug("_check_ai_trigger_conditions")
        if not ai_trigger.enabled: return False
        if not ai_trigger.conditions: return bool(ai_trigger.actions) if ai_trigger.enabled else False

        ai_trigger.last_checked_time = current_time
        results: List[bool] = []
        with self.lock:
            for condition_in_trigger in ai_trigger.conditions:
                if not hasattr(condition_in_trigger, 'id'): 
                    results.append(False); continue

                condition_id_to_check = condition_in_trigger.id
                current_state = self._monitored_conditions_map.get(condition_id_to_check, False)
                results.append(current_state)
                if ai_trigger.condition_logic == Trigger.LOGIC_OR and current_state: return True
                if ai_trigger.condition_logic == Trigger.LOGIC_AND and not current_state: return False
        
        return ai_trigger.condition_logic == Trigger.LOGIC_AND and all(results) if results else (ai_trigger.condition_logic == Trigger.LOGIC_AND)


    def _execute_triggered_actions(self, actions: List[TriggerAction]) -> None: # type: ignore
        logger.debug("_execute_triggered_actions")
        if not self.job_manager: return
        for action in actions:
             if not (_CoreClassesImported and isinstance(action, TriggerAction)): continue # type: ignore
             try:
                 action_type = action.action_type; target = action.target
                 action_requires_target = action_type in [TriggerAction.START_JOB, TriggerAction.STOP_JOB, TriggerAction.PAUSE_JOB, TriggerAction.RESUME_JOB, TriggerAction.SWITCH_PROFILE] # type: ignore
                 is_valid_target = bool(target) or (action_type == TriggerAction.STOP_JOB and target.lower() == "all") # type: ignore
                 if action_requires_target and not is_valid_target: continue

                 if action_type == TriggerAction.START_JOB: # type: ignore
                     if self.job_manager: self.job_manager.start_job(target)
                 elif action_type == TriggerAction.STOP_JOB: # type: ignore
                      if self.job_manager:
                          if target.lower() == "all": self.job_manager.stop_all_running_jobs(wait=False)
                          else: self.job_manager.stop_job(target, wait=False)
                 elif action_type == TriggerAction.SWITCH_PROFILE: # type: ignore
                       if self.job_manager: self.job_manager.load_profile(target); break
             except ValueError: pass
             except Exception: pass
             if self._stop_event.is_set(): break
    
    def destroy(self) -> None:
        self.stop(wait=True)
