# core/condition_manager.py
import logging
import copy
from typing import Dict, List, Optional, Any
from core.condition import Condition, create_condition, NoneCondition # << THÊM NoneCondition

logger = logging.getLogger(__name__)

class ConditionManager:
    def __init__(self):
        self.shared_conditions: Dict[str, Condition] = {}
        logger.debug("ConditionManager initialized.")

    def load_shared_conditions(self, conditions_data_list: List[Dict[str, Any]]):
        self.shared_conditions.clear()
        loaded_count = 0
        error_count = 0
        if not isinstance(conditions_data_list, list):
            logger.warning(f"load_shared_conditions received invalid data type: {type(conditions_data_list)}. Expected list.")
            return

        for cond_data in conditions_data_list:
            if not isinstance(cond_data, dict):
                logger.warning(f"Skipping invalid condition data item (not a dict): {cond_data}")
                error_count += 1
                continue

            condition_type = cond_data.get("type")
            if condition_type == NoneCondition.TYPE:
                logger.debug(f"Skipping loading of 'Always True' (NoneCondition) condition into shared library: {cond_data.get('name', cond_data.get('id', 'Unknown'))}")
                error_count +=1 
                continue

            try:
                condition_obj = create_condition(cond_data) 
                if condition_obj and condition_obj.id and condition_obj.type != NoneCondition.TYPE: 
                    self.shared_conditions[condition_obj.id] = condition_obj
                    loaded_count += 1
                else:
                    reason = "Failed to create valid condition object"
                    if not condition_obj: pass
                    elif not condition_obj.id: reason = "Missing ID"
                    elif condition_obj.type == NoneCondition.TYPE: reason = "Is an Always True condition"
                    logger.warning(f"{reason} from data: {cond_data}")
                    error_count += 1
            except Exception as e:
                logger.error(f"Error creating shared condition from data {cond_data}: {e}", exc_info=True)
                error_count += 1
        logger.info(f"ConditionManager loaded {loaded_count} shared conditions (skipped {error_count}).")

    def get_all_shared_conditions(self) -> List[Condition]:
        return list(self.shared_conditions.values())

    def get_all_shared_conditions_summary(self) -> Dict[str, Dict[str, str]]:
        summary = {}
        for cond_id, cond_obj in self.shared_conditions.items():
            try:
                summary[cond_id] = {
                    "id": cond_obj.id,
                    "name": cond_obj.name,
                    "type": cond_obj.type,
                    "str": str(cond_obj)
                }
            except Exception as e:
                logger.warning(f"Error generating summary for condition ID '{cond_id}': {e}")
        return summary

    def get_shared_condition_by_id(self, condition_id: str) -> Optional[Condition]:
        if not condition_id:
            return None
        return self.shared_conditions.get(condition_id)

    def add_or_update_shared_condition(self, condition_obj: Condition) -> bool:
        if not isinstance(condition_obj, Condition) or not condition_obj.id:
            logger.error("Cannot add/update shared condition: Invalid Condition object or missing ID.")
            return False
        if condition_obj.type == NoneCondition.TYPE:
            logger.warning(f"Cannot add/update Shared Condition '{condition_obj.name}' (ID: {condition_obj.id}): 'Always True' conditions are not allowed in the shared library.")
            return False
        
        is_update = condition_obj.id in self.shared_conditions
        action_taken = "Updated" if is_update else "Added"

        self.shared_conditions[condition_obj.id] = condition_obj
        logger.info(f"{action_taken} shared condition: '{condition_obj.name}' (ID: {condition_obj.id})")
        return True

    def update_shared_condition_from_data(self, condition_id: str, updated_condition_data: Dict[str, Any]) -> bool:
        if not condition_id or not isinstance(updated_condition_data, dict):
            logger.error("Cannot update shared condition: Invalid ID or data.")
            return False

        if condition_id not in self.shared_conditions:
            logger.warning(f"Cannot update shared condition: ID '{condition_id}' not found. Consider adding it instead.")
            return False
        new_type = updated_condition_data.get("type")
        if new_type == NoneCondition.TYPE:
            logger.error(f"Cannot update shared condition ID '{condition_id}' to type 'Always True'. This type is not allowed in the shared library.")
            return False

        try:
            if "id" in updated_condition_data and updated_condition_data["id"] != condition_id:
                logger.warning(f"ID mismatch during update. Provided data ID '{updated_condition_data['id']}' differs from target ID '{condition_id}'. Using target ID.")
            updated_condition_data["id"] = condition_id 

            if "name" not in updated_condition_data or not str(updated_condition_data.get("name", "")).strip():
                original_name = self.shared_conditions[condition_id].name
                updated_condition_data["name"] = original_name
                logger.debug(f"Update for condition ID '{condition_id}': Name not in update data or empty, preserving original name '{original_name}'.")

            updated_condition_obj = create_condition(updated_condition_data)
            if not updated_condition_obj:
                logger.error(f"Failed to create valid condition object from updated data for ID '{condition_id}'.")
                return False
            if updated_condition_obj.type == NoneCondition.TYPE:
                 logger.error(f"Attempted to update condition ID '{condition_id}' to an 'Always True' type through create_condition. Update aborted.")
                 return False
            
            self.shared_conditions[condition_id] = updated_condition_obj
            logger.info(f"Updated shared condition: '{updated_condition_obj.name}' (ID: {condition_id})")
            return True
        except Exception as e:
            logger.error(f"Error updating shared condition ID '{condition_id}' from data: {e}", exc_info=True)
            return False

    def delete_shared_condition(self, condition_id: str) -> bool:
        if not condition_id:
            logger.warning("Cannot delete shared condition: ID is empty.")
            return False
        if condition_id in self.shared_conditions:
            removed_condition_name = self.shared_conditions[condition_id].name
            del self.shared_conditions[condition_id]
            logger.info(f"Deleted shared condition: '{removed_condition_name}' (ID: {condition_id})")
            return True
        else:
            logger.warning(f"Cannot delete shared condition: ID '{condition_id}' not found.")
            return False

    def get_serializable_data(self) -> List[Dict[str, Any]]:
        return [
            cond.to_dict()
            for cond in self.shared_conditions.values()
            if cond.type != NoneCondition.TYPE
        ]

    def clear_all_shared_conditions(self):
        self.shared_conditions.clear()
        logger.info("All shared conditions cleared from ConditionManager.")

    def get_condition_display_map(self) -> Dict[str, str]:
        return {
            cond_id: f"{cond.name} ({cond.type})"
            for cond_id, cond in self.shared_conditions.items()
        }

    def is_condition_id_in_use(self, condition_id_to_check: str, all_jobs: List[Any]) -> bool:
        if not condition_id_to_check:
            return False
        for job in all_jobs:
            if hasattr(job, 'actions') and isinstance(job.actions, list):
                for action in job.actions:
                    if hasattr(action, 'condition_id') and action.condition_id == condition_id_to_check:
                        logger.debug(f"Condition ID '{condition_id_to_check}' is in use by action of type '{getattr(action,'type','unknown')}' in job '{getattr(job,'name','unknown')}'.")
                        return True
        return False
