# core/trigger.py
import logging
from typing import List, Optional, Any, Dict 
import time 

logger = logging.getLogger(__name__)

_ConditionClassesImported = False
try:
    from core.condition import Condition, create_condition, NoneCondition 
    _ConditionClassesImported = True
    logger.debug("core.trigger: Successfully imported Condition classes from core.condition.")
except ImportError as e_cond_imp:
    logger.error(f"core.trigger: Failed to import Condition classes from core.condition: {e_cond_imp}. Using dummy classes.")
    _ConditionClassesImported = False
    class Condition:
        id: Optional[str]; name: Optional[str]; type: str; params: Dict[str,Any]; is_monitored_by_ai_brain: bool
        def __init__(self, type_val:str="dummy_cond", params_val:Optional[Dict[str,Any]]=None, id_val:Optional[str]=None, name_val:Optional[str]=None, is_monitored_by_ai_brain:bool=False) -> None:
            self.type=type_val
            self.params=params_val if isinstance(params_val, dict) else {}
            self.id=id_val
            self.name=name_val
            self.is_monitored_by_ai_brain=is_monitored_by_ai_brain
        def to_dict(self) -> Dict[str,Any]: return {"id":self.id, "name":self.name, "type":self.type, "params":self.params, "is_monitored_by_ai_brain":self.is_monitored_by_ai_brain}
        def check(self, **context) -> bool: return False 

    class NoneCondition(Condition): # type: ignore
        TYPE="none"
        def __init__(self, params_val:Optional[Dict[str,Any]]=None, id_val:Optional[str]=None, name_val:Optional[str]=None, is_monitored_by_ai_brain:bool=False) -> None:
            super().__init__("none",params_val,id_val, name_val if name_val and name_val.strip() else "Always True" ,False) 

    def create_condition(d: Dict[str,Any]) -> Optional[Condition]: 
        if not isinstance(d, dict): return None
        return Condition(
            type_val=str(d.get("type", "dummy_fallback")),
            params_val=d.get("params"),
            id_val=d.get("id"),
            name_val=d.get("name"),
            is_monitored_by_ai_brain=bool(d.get("is_monitored_by_ai_brain", False))
        )

class TriggerAction:
    """Định nghĩa hành động sẽ thực hiện khi trigger kích hoạt."""
    START_JOB = "start_job"
    STOP_JOB = "stop_job"
    PAUSE_JOB = "pause_job"
    RESUME_JOB = "resume_job"
    SWITCH_PROFILE = "switch_profile"

    VALID_ACTIONS = [START_JOB, STOP_JOB, PAUSE_JOB, RESUME_JOB, SWITCH_PROFILE]

    def __init__(self, action_type: str, target: Optional[str]):
        if action_type not in self.VALID_ACTIONS:
            raise ValueError(f"Invalid trigger action type: {action_type}")
        self.action_type = action_type
        self.target = target.strip() if isinstance(target, str) else ""

    def to_dict(self) -> Dict[str, str]:
        return {"action_type": self.action_type, "target": self.target}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TriggerAction':
        if not isinstance(data, dict):
            raise ValueError("TriggerAction data must be a dictionary.")
        action_type = data.get("action_type")
        target = data.get("target")
        if not action_type:
             raise ValueError("Missing 'action_type' in TriggerAction data.")
        return cls(str(action_type), target)
    def __str__(self) -> str:
        target_display = self.target
        if self.action_type == self.STOP_JOB and self.target.lower() == "all":
            target_display = "All Running Jobs"
        elif not self.target:
            if self.action_type in [self.START_JOB, self.STOP_JOB, self.PAUSE_JOB, self.RESUME_JOB, self.SWITCH_PROFILE]:
                target_display = "(No Target Selected)"
            else:
                target_display = "(N/A)"
        return f"{self.action_type.replace('_', ' ').title()}: '{target_display}'"

    def __repr__(self) -> str:
        return f"TriggerAction(action_type='{self.action_type}', target='{self.target}')"


class Trigger:
    LOGIC_AND = "AND"
    LOGIC_OR = "OR"
    VALID_LOGICS = [LOGIC_AND, LOGIC_OR]

    def __init__(self, name: str,
                 conditions: List[Condition],
                 condition_logic: str = LOGIC_AND,
                 actions: Optional[List[TriggerAction]] = None,
                 enabled: bool = True,
                 check_interval_seconds: float = 0.5,
                 is_ai_trigger: bool = False):

        if not isinstance(name, str) or not name.strip():
            raise ValueError("Trigger name cannot be empty.")
        if not isinstance(conditions, list):
             raise ValueError("Conditions must be a list.")
        if not all(isinstance(c, Condition) for c in conditions):
             raise ValueError("All items in conditions list must be Condition objects.")
        if condition_logic not in self.VALID_LOGICS:
            raise ValueError(f"Invalid condition logic: {condition_logic}.")

        if actions is not None:
            if not isinstance(actions, list):
                raise ValueError("'actions' must be a list of TriggerAction objects or None.")
            if not all(isinstance(a, TriggerAction) for a in actions):
                raise ValueError("All items in 'actions' list must be TriggerAction objects.")

        self.name = name.strip()
        self.conditions = conditions
        self.condition_logic = condition_logic
        self.actions: List[TriggerAction] = actions if actions else []
        self.enabled = enabled
        self.check_interval_seconds = max(0.1, check_interval_seconds)
        self.is_ai_trigger = bool(is_ai_trigger) 
        self.last_checked_time: float = 0.0
        self.last_triggered_time: float = 0.0

    def should_check(self, current_time: float) -> bool:
        return self.enabled and (current_time - self.last_checked_time >= self.check_interval_seconds)

    def check_conditions(self, **context) -> bool:
        """
        Kiểm tra các điều kiện của trigger.
        LƯU Ý: Đối với AI Triggers, logic kiểm tra điều kiện sẽ khác và được xử lý
        trong Observer dựa trên _monitored_conditions_map. Hàm này chủ yếu dùng cho trigger thường.
        """
        if not self.enabled:
            return False
     
        if self.is_ai_trigger:
            logger.debug(f"Trigger '{self.name}' is an AI Trigger. Its condition checking is handled by Observer's AI logic.")
    
            return False


        if not self.conditions: 
            return bool(self.actions) 
        self.last_checked_time = time.monotonic()
        results = []
        for condition_obj in self.conditions: 
            try:
                result = condition_obj.check(**context)
                results.append(result)
                logger.debug(f"Trigger '{self.name}', Condition '{condition_obj.name} ({condition_obj.type})' check result: {result}")
                if self.condition_logic == self.LOGIC_OR and result:
                    return True
                if self.condition_logic == self.LOGIC_AND and not result:
                    return False
            except Exception as e:
                 logger.error(f"Error checking condition '{getattr(condition_obj,'name','UnknownCondition')}' for trigger '{self.name}': {e}", exc_info=True)
                 results.append(False)
                 if self.condition_logic == self.LOGIC_AND:
                     return False
        
        if not results: 
            return False

        return self.condition_logic == self.LOGIC_AND 

    def trigger(self, current_time: float) -> Optional[List[TriggerAction]]:
         if not self.actions:
              logger.info(f"Trigger '{self.name}' activated but has no actions defined.")
              self.last_triggered_time = current_time
              return None

         logger.info(f"Trigger '{self.name}' activated! Returning {len(self.actions)} action(s).")
         self.last_triggered_time = current_time
         return self.actions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "conditions": [c.to_dict() for c in self.conditions if hasattr(c, 'to_dict')],
            "condition_logic": self.condition_logic,
            "actions": [a.to_dict() for a in self.actions if hasattr(a, 'to_dict')],
            "enabled": self.enabled,
            "check_interval_seconds": self.check_interval_seconds,
            "is_ai_trigger": self.is_ai_trigger 
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Trigger':
        if not isinstance(data, dict):
            raise ValueError("Trigger data must be a dictionary.")

        name = data.get("name")
        conditions_data = data.get("conditions", [])
        condition_logic = data.get("condition_logic", cls.LOGIC_AND)
        actions_data = data.get("actions", []) 
        enabled = data.get("enabled", True)
        check_interval = data.get("check_interval_seconds", 0.5)
        is_ai_trigger = data.get("is_ai_trigger", False) 
        if not name: raise ValueError("Missing 'name' in Trigger data.")
        if not isinstance(conditions_data, list): raise ValueError("'conditions' must be a list.")

        conditions: List[Condition] = []
        if _ConditionClassesImported: 
            for c_data in conditions_data:
                if isinstance(c_data, dict):
                    try:
                        condition_obj = create_condition(c_data) 
                        if condition_obj:
                            conditions.append(condition_obj)
                        else:
                            logger.warning(f"Failed to create condition from data in trigger '{name}': {c_data}")
                    except Exception as e_create_cond:
                        logger.error(f"Error creating condition for trigger '{name}' from data {c_data}: {e_create_cond}", exc_info=True)
                else:
                    logger.warning(f"Skipping invalid condition data item (not a dict) in trigger '{name}': {c_data}")
        else: 
            logger.warning(f"Trigger.from_dict for '{name}': Using DUMMY condition creation due to import failure.")
            for c_data in conditions_data:
                if isinstance(c_data, dict):
                    dummy_cond = create_condition(c_data) 
                    if dummy_cond: conditions.append(dummy_cond)


        actions: List[TriggerAction] = []
        if isinstance(actions_data, list):
            for a_data in actions_data:
                if isinstance(a_data, dict):
                    try:
                        actions.append(TriggerAction.from_dict(a_data))
                    except Exception as e_create_action:
                        logger.error(f"Error creating TriggerAction from data {a_data} for trigger '{name}': {e_create_action}", exc_info=True)
                else:
                    logger.warning(f"Skipping invalid action data item (not a dict) in trigger '{name}': {a_data}")
        elif actions_data is not None:
             logger.warning(f"'actions' data in trigger '{name}' is not a list (type: {type(actions_data)}). Trigger will have no actions.")

        return cls(
            name=str(name),
            conditions=conditions,
            condition_logic=str(condition_logic),
            actions=actions,
            enabled=bool(enabled),
            check_interval_seconds=float(check_interval),
            is_ai_trigger=bool(is_ai_trigger) 
        )

    def __str__(self) -> str:
        cond_summary = "(No Conditions)"
        if self.conditions:
            parts = []
            for c in self.conditions:
                c_name = getattr(c, 'name', getattr(c, 'type', 'UnknownCond'))
                c_name = c_name[:30] + "..." if len(c_name) > 30 else c_name
                parts.append(f"'{c_name}'")
            cond_summary = f" {self.condition_logic} ".join(parts)
        
        action_summary = "(No Action)"
        if self.actions:
            if len(self.actions) == 1:
                action_summary = str(self.actions[0])
            else:
                action_summary = f"{len(self.actions)} actions"

        status = "Enabled" if self.enabled else "Disabled"
        ai_status = " (AI)" if self.is_ai_trigger else ""
        return (f"Trigger(Name='{self.name}'{ai_status}, If: [{cond_summary}], "
                f"Then: [{action_summary}], Int: {self.check_interval_seconds:.2f}s, {status})")

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}(name='{self.name}', conditions={self.conditions}, "
                f"logic='{self.condition_logic}', actions={self.actions}, "
                f"enabled={self.enabled}, interval={self.check_interval_seconds}, is_ai_trigger={self.is_ai_trigger})")
