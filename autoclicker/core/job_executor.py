# core/job_executor.py
import threading
import time
import logging
import traceback
from typing import Optional, Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_CoreClassesImported = False
try:
    from core.job import Job
    from core.action import Action, create_action 
    from core.job_run_condition import JobRunCondition, JobContext
    from core.condition import Condition
    from core.condition_manager import ConditionManager
    _CoreClassesImported = True
except ImportError as e:
     _CoreClassesImported = False
     class Job:
         name: str; actions: list; run_condition: Any; params: Dict[str, Any]
         def __init__(self) -> None: self.name="dummy"; self.actions=[]; self.run_condition=None; self.params={}
     class Action:
         next_action_index_if_condition_met: Optional[int] = None
         next_action_index_if_condition_not_met: Optional[int] = None
         type: str = "dummy_action"
         is_absolute: bool = False
         fallback_action_sequence: Optional[List[Dict[str, Any]]] = None 
         condition_id: Optional[str] = None
         def __init__(self, type: str, params: Optional[Dict[str,Any]]=None, condition_id: Optional[str]=None, next_action_index_if_condition_met: Optional[int]=None, next_action_index_if_condition_not_met: Optional[int]=None, is_absolute: bool=False, fallback_action_sequence: Optional[List[Dict[str,Any]]]=None): # Cập nhật __init__
             self.type = type; self.params=params or {}; self.condition_id = condition_id
             self.next_action_index_if_condition_met=next_action_index_if_condition_met
             self.next_action_index_if_condition_not_met=next_action_index_if_condition_not_met
             self.is_absolute=is_absolute; self.fallback_action_sequence=fallback_action_sequence

         def execute(self, job_stop_event:Optional[threading.Event]=None, condition_manager:Any=None, **context:Any) -> bool: return True
         def _execute_core_logic(self, job_stop_event:Optional[threading.Event]=None, **context:Any) -> None: pass
     def create_action(data: Optional[Dict[str, Any]]) -> Action: 
          if data and isinstance(data, dict):
              return Action(data.get("type","dummy"), data.get("params",{}), data.get("condition_id"),
                            data.get("next_action_index_if_condition_met"), data.get("next_action_index_if_condition_not_met"),
                            data.get("is_absolute", False), data.get("fallback_action_sequence"))
          return Action("dummy_fallback_error")

     class JobRunCondition:
         def reset(self) -> None: pass
         def check_continue(self, context: Any) -> bool: return True
     class JobContext:
         last_click_position: Optional[Tuple[int,int]] = None 
         def __init__(self, run_count: int = 0, start_time: float = 0.0, job_name: str = ""):
             self.run_count = run_count; self.start_time = start_time; self.job_name = job_name
             self.last_click_position = None
     class Condition: pass
     class ConditionManager: pass


class JobExecutionError(Exception):
    pass

class JobExecutor:
    _job: Job
    _stop_event: threading.Event
    _image_storage: Optional[Any]
    _condition_manager: Optional[ConditionManager]
    _execution_thread: Optional[threading.Thread]
    _is_executing: bool
    _current_run_count: int
    _start_time: float
    _job_context: JobContext 

    _MAX_FALLBACK_DEPTH = 3 
    _ABSOLUTE_ACTION_MAX_RETRIES = 10 
    _ABSOLUTE_ACTION_RETRY_INTERVAL = 0.5
    def __init__(self,
                 job: Job,
                 stop_event: threading.Event,
                 image_storage: Optional[Any] = None,
                 condition_manager: Optional[ConditionManager] = None) -> None:
        if not _CoreClassesImported:
            raise ImportError("JobExecutor failed to initialize due to missing core dependencies.")

        if not isinstance(job, Job):
            raise TypeError("JobExecutor requires a Job object.")
        if not isinstance(stop_event, threading.Event):
            raise TypeError("JobExecutor requires a threading.Event for stop_event.")
        if condition_manager is not None and not isinstance(condition_manager, ConditionManager):
            self._condition_manager = None
            logger.warning("JobExecutor received an invalid ConditionManager instance. Condition checks may fail.")
        else:
            self._condition_manager = condition_manager

        self._job = job
        self._stop_event = stop_event
        self._image_storage = image_storage

        self._execution_thread = None
        self._is_executing = False
        self._current_run_count = 0
        self._start_time = 0.0
        self._job_context = JobContext(job_name=self._job.name)


    def start(self) -> None:
        if self._is_executing:
            logger.warning(f"Job '{self._job.name}' is already executing. Start command ignored.")
            return
        self._is_executing = True
        self._stop_event.clear()
        self._current_run_count = 0
        self._start_time = time.monotonic()
        self._job_context.run_count = self._current_run_count
        self._job_context.start_time = self._start_time
        self._job_context.last_click_position = None 

        logger.info(f"Starting job '{self._job.name}'")

        try:
            if isinstance(self._job.run_condition, JobRunCondition):
                 self._job.run_condition.reset()
                 logger.debug(f"Job '{self._job.name}': Run condition reset.")
        except Exception as e_rc_reset:
             logger.error(f"Job '{self._job.name}': Error resetting run condition: {e_rc_reset}", exc_info=True)

        self._execution_thread = threading.Thread(target=self._execute_loop, name=f"JobExecutor-{self._job.name}", daemon=True)
        self._execution_thread.start()
        logger.debug(f"Job '{self._job.name}': Execution thread started.")

    def stop(self, wait: bool = True, timeout: float = 5.0) -> None:
        logger.info(f"Stopping job '{self._job.name}' (Wait: {wait}, Timeout: {timeout}s)")
        if not self._is_executing and not (self._execution_thread and self._execution_thread.is_alive()):
            logger.debug(f"Job '{self._job.name}' is not executing or thread already finished. Stop command ignored.")
            return
        self._is_executing = False
        self._stop_event.set()

        if wait and self._execution_thread and self._execution_thread.is_alive():
            logger.debug(f"Job '{self._job.name}': Waiting for execution thread to join...")
            try:
                self._execution_thread.join(timeout)
                if self._execution_thread.is_alive():
                    logger.warning(f"Job '{self._job.name}': Execution thread did not join within timeout ({timeout}s).")
                else:
                    logger.debug(f"Job '{self._job.name}': Execution thread joined successfully.")
            except Exception as e_join:
                logger.error(f"Job '{self._job.name}': Error during thread join: {e_join}", exc_info=True)

        self._execution_thread = None
        logger.info(f"Job '{self._job.name}' stop process completed.")

    def _execute_action_with_fallback(self, action_to_execute: Action, current_action_index: int, fallback_depth: int) -> Tuple[bool, int]:
        """
        Thực thi một action, bao gồm logic is_absolute và fallback.
        Trả về (condition_met_for_main_or_successful_fallback, next_action_index_to_jump_to)
        """
        if fallback_depth > self._MAX_FALLBACK_DEPTH:
            logger.warning(f"Job '{self._job.name}', Action Idx {current_action_index} ({action_to_execute.type}): Max fallback depth ({self._MAX_FALLBACK_DEPTH}) reached. Skipping further fallbacks for this branch.")
            return False, current_action_index + 1 

        action_context_for_execute = {
            "job_name": self._job.name,
            "image_storage_instance": self._image_storage,
            "job_context": self._job_context 
        }

        absolute_retries_left = self._ABSOLUTE_ACTION_MAX_RETRIES if action_to_execute.is_absolute else 1
        condition_met_for_this_action = False 

        while absolute_retries_left > 0:
            if not self._is_executing or self._stop_event.is_set():
                logger.info(f"Job '{self._job.name}', Action Idx {current_action_index} ({action_to_execute.type}): Stop signal received during action processing (depth {fallback_depth}).")
                self._is_executing = False
                return condition_met_for_this_action, current_action_index + 1 

            try:
                logger.debug(f"Job '{self._job.name}', Action Idx {current_action_index} ({action_to_execute.type}, Depth {fallback_depth}): Calling action.execute(). Absolute: {action_to_execute.is_absolute}, Retries left: {absolute_retries_left}")
                condition_met_for_this_action = action_to_execute.execute(
                    job_stop_event=self._stop_event,
                    condition_manager=self._condition_manager,
                    **action_context_for_execute
                )
                logger.debug(f"Job '{self._job.name}', Action Idx {current_action_index} ({action_to_execute.type}): action.execute() returned: {condition_met_for_this_action}")

                if hasattr(action_to_execute, 'type') and action_to_execute.type == "click" and condition_met_for_this_action:
                     if hasattr(action_to_execute, 'x') and hasattr(action_to_execute, 'y'):
                        self._job_context.last_click_position = (action_to_execute.x, action_to_execute.y) # type: ignore
                        logger.debug(f"JobContext: Updated last_click_position to ({action_to_execute.x}, {action_to_execute.y})")


            except (ValueError, RuntimeError) as e_action: 
                logger.error(f"Job '{self._job.name}': Error executing action {current_action_index} ({action_to_execute.type}, Depth {fallback_depth}): {e_action}. Stopping job.", exc_info=True)
                self._is_executing = False; self._stop_event.set();
                return False, -1 
            except Exception as e_unhandled:
                logger.error(f"Job '{self._job.name}': Unhandled error during action {current_action_index} ({action_to_execute.type}, Depth {fallback_depth}) execution: {e_unhandled}. Stopping job.", exc_info=True)
                self._is_executing = False; self._stop_event.set();
                return False, -1

            if not self._is_executing: 
                return condition_met_for_this_action, current_action_index + 1

            if condition_met_for_this_action:
                logger.debug(f"Job '{self._job.name}', Action Idx {current_action_index} ({action_to_execute.type}, Depth {fallback_depth}): Successfully executed (condition met and core logic ran).")
                if hasattr(action_to_execute, 'next_action_index_if_condition_met') and isinstance(action_to_execute.next_action_index_if_condition_met, int) and action_to_execute.next_action_index_if_condition_met >=0:
                    return True, action_to_execute.next_action_index_if_condition_met
                else:
                    return True, current_action_index + 1 
            else: 
                if action_to_execute.is_absolute:
                    absolute_retries_left -= 1
                    if absolute_retries_left > 0:
                        logger.info(f"Job '{self._job.name}', Absolute Action Idx {current_action_index} ({action_to_execute.type}, Depth {fallback_depth}): Condition not met. Waiting (Retries left {absolute_retries_left})...")
                        if self._stop_event.wait(timeout=self._ABSOLUTE_ACTION_RETRY_INTERVAL):
                            logger.info(f"Job '{self._job.name}': Stop event set while waiting for absolute action {current_action_index}.")
                            self._is_executing = False
                            return False, current_action_index + 1 
                        continue 
                    else: 
                        logger.warning(f"Job '{self._job.name}', Absolute Action Idx {current_action_index} ({action_to_execute.type}, Depth {fallback_depth}): Max retries reached, condition still not met. Treating as 'condition not met'.")
                        pass 
                else: 
                    logger.debug(f"Job '{self._job.name}', Action Idx {current_action_index} ({action_to_execute.type}, Depth {fallback_depth}): Condition not met (Non-absolute).")

                    pass 
            if not condition_met_for_this_action and hasattr(action_to_execute, 'fallback_action_sequence') and action_to_execute.fallback_action_sequence:
                logger.info(f"Job '{self._job.name}', Action Idx {current_action_index} ({action_to_execute.type}): Condition not met. Attempting fallback sequence (Depth {fallback_depth}).")

                any_fallback_successful = False
                last_fallback_next_index = current_action_index + 1

                for i, fallback_action_data in enumerate(action_to_execute.fallback_action_sequence):
                    if not self._is_executing or self._stop_event.is_set(): break
                    
                    logger.debug(f"Job '{self._job.name}', Fallback Action #{i+1} for Action Idx {current_action_index}. Data: {fallback_action_data.get('type')}")
                    try:
                        fallback_action_obj = create_action(fallback_action_data)
                        if not isinstance(fallback_action_obj, Action):
                            logger.warning(f"Could not create valid fallback action object from data: {fallback_action_data}")
                            continue
                        
                        fallback_condition_met, next_idx_from_fallback = self._execute_action_with_fallback(
                            fallback_action_obj,
                            current_action_index, 
                            fallback_depth + 1
                        )

                        if fallback_condition_met:
                            any_fallback_successful = True
                            logger.info(f"Job '{self._job.name}', Fallback Action #{i+1} (Type: {fallback_action_obj.type}) for Action Idx {current_action_index} was successful.")
                            break 
                        else:
                             logger.debug(f"Job '{self._job.name}', Fallback Action #{i+1} (Type: {fallback_action_obj.type}) for Action Idx {current_action_index} did not meet its condition or failed.")


                    except Exception as e_create_fallback:
                        logger.error(f"Error creating/executing fallback action #{i+1} for Action Idx {current_action_index}: {e_create_fallback}", exc_info=True)

                if any_fallback_successful:
                    logger.debug(f"Job '{self._job.name}', Action Idx {current_action_index}: At least one fallback successful. Proceeding based on main action's 'condition_not_met' logic.")
                    if hasattr(action_to_execute, 'next_action_index_if_condition_not_met') and isinstance(action_to_execute.next_action_index_if_condition_not_met, int) and action_to_execute.next_action_index_if_condition_not_met >=0:
                        return True, action_to_execute.next_action_index_if_condition_not_met
                    else:
                        return True, current_action_index + 1
                else:
                    logger.debug(f"Job '{self._job.name}', Action Idx {current_action_index}: No fallback successful or no fallback defined. Proceeding based on main action's 'condition_not_met' logic.")
                    if hasattr(action_to_execute, 'next_action_index_if_condition_not_met') and isinstance(action_to_execute.next_action_index_if_condition_not_met, int) and action_to_execute.next_action_index_if_condition_not_met >=0:
                        return False, action_to_execute.next_action_index_if_condition_not_met
                    else:
                        return False, current_action_index + 1

            if hasattr(action_to_execute, 'next_action_index_if_condition_not_met') and isinstance(action_to_execute.next_action_index_if_condition_not_met, int) and action_to_execute.next_action_index_if_condition_not_met >=0:
                return False, action_to_execute.next_action_index_if_condition_not_met
            else:
                return False, current_action_index + 1

        if hasattr(action_to_execute, 'next_action_index_if_condition_not_met') and isinstance(action_to_execute.next_action_index_if_condition_not_met, int) and action_to_execute.next_action_index_if_condition_not_met >=0:
             return False, action_to_execute.next_action_index_if_condition_not_met
        else:
             return False, current_action_index + 1


    def _execute_loop(self) -> None:
        try:
            logger.info(f"Job '{self._job.name}': Execution loop started.")
            while self._is_executing and not self._stop_event.is_set():
                self._job_context.run_count = self._current_run_count 
                self._job_context.start_time = self._start_time    
                should_continue_job_run_cycle = False
                if not isinstance(self._job.run_condition, JobRunCondition) and self._job.run_condition is not None:
                     logger.error(f"Job '{self._job.name}': Invalid run_condition type ({type(self._job.run_condition)}). Stopping job.")
                elif self._job.run_condition is None:
                     logger.debug(f"Job '{self._job.name}': No run condition, assuming infinite run for this cycle.")
                     should_continue_job_run_cycle = True
                else:
                    try:
                        should_continue_job_run_cycle = self._job.run_condition.check_continue(self._job_context)
                        logger.debug(f"Job '{self._job.name}': Run condition check_continue returned {should_continue_job_run_cycle} (Run {self._current_run_count}).")
                    except Exception as e_rc_check:
                         logger.error(f"Job '{self._job.name}': Error checking run condition: {e_rc_check}. Stopping job.", exc_info=True)
                         should_continue_job_run_cycle = False

                if not should_continue_job_run_cycle:
                    logger.info(f"Job '{self._job.name}': Run condition indicates job should stop (or error occurred).")
                    self._is_executing = False
                    self._stop_event.set()
                    break

                current_action_index = 0
                actions_list = self._job.actions
                logger.debug(f"Job '{self._job.name}', Run {self._current_run_count}: Starting action sequence (Total actions: {len(actions_list)}).")

                execution_history: List[Tuple[int, str, Optional[str]]] = [] 
                MAX_HISTORY_LENGTH = 20 
                MIN_REPETITIONS_FOR_LOOP_DETECTION = 3 

                while 0 <= current_action_index < len(actions_list):
                    if not self._is_executing or self._stop_event.is_set():
                        logger.info(f"Job '{self._job.name}': Loop/stop event triggered. Breaking action sequence.")
                        self._is_executing = False
                        break

                    action = actions_list[current_action_index]
                    if not isinstance(action, Action):
                         logger.warning(f"Job '{self._job.name}', Action Idx {current_action_index}: Item is not an Action instance (Type: {type(action)}). Skipping.")
                         current_action_index += 1
                         continue

                    current_action_signature = (current_action_index, action.type, action.condition_id)
                    execution_history.append(current_action_signature)
                    if len(execution_history) > MAX_HISTORY_LENGTH:
                        execution_history.pop(0)

                    if len(execution_history) >= MIN_REPETITIONS_FOR_LOOP_DETECTION:
                        recent_signatures = execution_history[-MIN_REPETITIONS_FOR_LOOP_DETECTION:]
                        if all(sig == current_action_signature for sig in recent_signatures):
                            logger.error(f"Job '{self._job.name}': Potential infinite loop detected! Action signature {current_action_signature} repeated {MIN_REPETITIONS_FOR_LOOP_DETECTION} times consecutively. Stopping job.")
                            self._is_executing = False; self._stop_event.set(); break


                    final_condition_check_result_for_jump, next_index_to_jump_to = self._execute_action_with_fallback(
                        action, current_action_index, fallback_depth=0
                    )

                    if next_index_to_jump_to == -1 : 
                         self._is_executing = False; self._stop_event.set(); break


                    logger.debug(f"Job '{self._job.name}', Action Idx {current_action_index}: Jump logic. Condition result for jump: {final_condition_check_result_for_jump}. Next index: {next_index_to_jump_to}")
                    current_action_index = next_index_to_jump_to

                if not self._is_executing:
                    logger.info(f"Job '{self._job.name}': Stopping before completing run cycle {self._current_run_count}.")
                    break

                self._current_run_count += 1
                logger.info(f"Job '{self._job.name}': Completed run cycle {self._current_run_count -1}.")

                loop_delay_seconds = self._job.params.get("delay_between_runs_s", 0.01)
                loop_delay_seconds = max(0.0, loop_delay_seconds) # Đảm bảo không âm
                logger.debug(f"Job '{self._job.name}': Loop delay is {loop_delay_seconds}s.")

                if self._is_executing and not self._stop_event.is_set() and loop_delay_seconds > 0:
                     logger.debug(f"Job '{self._job.name}': Waiting for {loop_delay_seconds}s before next run cycle.")
                     if self._stop_event.wait(timeout=loop_delay_seconds):
                         logger.info(f"Job '{self._job.name}': Stop event set during loop delay. Exiting.")
                         self._is_executing = False
        except Exception as e_loop:
            logger.error(f"Job '{self._job.name}': Unhandled exception in execution loop: {e_loop}", exc_info=True)
            self._is_executing = False
            self._stop_event.set()
        finally:
            self._is_executing = False
            job_object = self._job
            if job_object and hasattr(job_object, 'running'):
                job_object.running = False
            logger.info(f"Job '{self._job.name}': Execution loop finished. Final run count: {self._current_run_count}.")
