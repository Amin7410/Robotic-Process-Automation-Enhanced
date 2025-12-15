# core/condition.py
from abc import ABC, abstractmethod
import logging
import time
import numpy as np
import os
from PIL import Image
import pytesseract
import re
from utils.parsing_utils import parse_tuple_str
import uuid
from typing import Dict, Optional, Any, List, Tuple, Literal

logger = logging.getLogger(__name__)

_ImageProcessingAvailable = False
try:
    from utils.image_processing import preprocess_for_image_matching, preprocess_for_ocr
    _ImageProcessingAvailable = True
except ImportError:
    logger.warning("core.condition: image_processing utils not found. Preprocessing in conditions will be limited.")
    def preprocess_for_image_matching(img: Any, params: Dict[str, Any]) -> Any: return img
    def preprocess_for_ocr(img: Any, params: Dict[str, Any]) -> Any: return img

_CV2Available = False
try:
    import cv2
    _CV2Available = True
except ImportError:
    logger.warning("core.condition: OpenCV (cv2) not available. Image-based conditions will be severely limited.")
    pass

_PytesseractAvailable = False
try:
    import pytesseract
    tesseract_cmd_path_env = os.getenv('TESSERACT_CMD')
    tesseract_cmd_path_config = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    final_tesseract_path = None
    if tesseract_cmd_path_env and os.path.exists(tesseract_cmd_path_env):
        final_tesseract_path = tesseract_cmd_path_env
    elif os.path.exists(tesseract_cmd_path_config):
        final_tesseract_path = tesseract_cmd_path_config
    elif sys.platform.startswith('linux') and os.path.exists('/usr/bin/tesseract'): # type: ignore
        final_tesseract_path = '/usr/bin/tesseract'
    elif sys.platform.startswith('darwin') and os.path.exists('/usr/local/bin/tesseract'): # type: ignore
        final_tesseract_path = '/usr/local/bin/tesseract'

    if final_tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = final_tesseract_path
        try:
            version = pytesseract.get_tesseract_version()
            _PytesseractAvailable = True
            logger.info(f"core.condition: Tesseract OCR configured. Path: '{final_tesseract_path}', Version: {version}")
        except pytesseract.TesseractNotFoundError:
            _PytesseractAvailable = False
            logger.error(f"core.condition: Tesseract command set to '{final_tesseract_path}', but TesseractNotFoundError occurred. OCR will fail.")
        except Exception as e_tess_version:
            _PytesseractAvailable = True
            logger.warning(f"core.condition: Tesseract configured, but get_tesseract_version() failed: {e_tess_version}. Assuming Tesseract is available.")
    else:
        try:
            version = pytesseract.get_tesseract_version()
            _PytesseractAvailable = True
            logger.info(f"core.condition: Tesseract OCR found in system PATH. Version: {version}")
        except pytesseract.TesseractNotFoundError:
            _PytesseractAvailable = False
            logger.error("core.condition: Tesseract OCR not found in system PATH or configured manually. OCR features will be unavailable.")
        except Exception:
             _PytesseractAvailable = False
             logger.error("core.condition: Error trying to get Tesseract version from system PATH. OCR features will be unavailable.")
except ImportError:
    _PytesseractAvailable = False
    logger.error("core.condition: Pytesseract library not imported. OCR features will be unavailable.")
except Exception as e_tess_init:
     _PytesseractAvailable = False
     logger.error(f"core.condition: Unexpected error during Pytesseract initialization: {e_tess_init}", exc_info=True)

_BridgeImported = False
try:
    from python_csharp_bridge import os_interaction_client
    _BridgeImported = True
except ImportError:
    logger.error("core.condition: python_csharp_bridge.os_interaction_client not found. OS interactions will fail.")
    class DummyOSInteractionClient:
         def capture_region(self, *args: Any, **kwargs: Any) -> Dict[str, Any]: return {"image_np": None, "x1": 0, "y1": 0, "x2": 0, "y2": 0}
         def get_pixel_color(self, *args: Any, **kwargs: Any) -> str: return "#000000"
         def check_window_exists(self, *args: Any, **kwargs: Any) -> bool: return False
         def check_process_exists(self, *args: Any, **kwargs: Any) -> bool: return False
         def get_screen_size(self) -> Tuple[int, int]: return (1920, 1080)
    os_interaction_client = DummyOSInteractionClient()

_UtilsImported = False
try:
    from utils.image_storage import ImageStorage
    from utils.color_utils import hex_to_rgb, rgb_to_hex
    from utils.image_analysis import analyze_region_colors
    _UtilsImported = True
except ImportError:
    logger.error("core.condition: image_storage, color_utils, or image_analysis_utils not found. Some condition features will be limited.")
    class DummyImageStorage:
         def get_full_path(self, relative_path: str) -> str: return os.path.abspath(relative_path)
         def file_exists(self, relative_path: str) -> bool: return os.path.exists(self.get_full_path(relative_path))
    def hex_to_rgb(hex_color: str) -> Tuple[int,int,int]: raise ImportError("color_utils not imported") # type: ignore
    def rgb_to_hex(rgb_color: Tuple[int,int,int]) -> str: raise ImportError("color_utils not imported") # type: ignore
    def analyze_region_colors(img, targets, sampling) -> Dict[str, float]: return {}
    ImageStorage = DummyImageStorage # type: ignore


class Condition(ABC):
    id: str
    name: str
    type: str
    params: Dict[str, Any]
    is_monitored_by_ai_brain: bool
    _is_valid: bool
    _validation_error: Optional[str]

    def __init__(self, type: str, params: Optional[Dict[str, Any]] = None,
                 id: Optional[str] = None, name: Optional[str] = None,
                 is_monitored_by_ai_brain: bool = False) -> None:
        if not isinstance(type, str) or not type:
            raise ValueError("Condition type must be a non-empty string.")
        self.type = type
        self.params = params if isinstance(params, dict) else {}
        self.id = id if id and isinstance(id, str) and id.strip() else uuid.uuid4().hex
        final_name = name
        if not (final_name and isinstance(final_name, str) and final_name.strip()):
            type_display = self.type.replace('_',' ').title()
            final_name = f"{type_display}_{self.id[:8]}"
        self.name = final_name.strip()
        self.is_monitored_by_ai_brain = bool(is_monitored_by_ai_brain)
        self._is_valid = True
        self._validation_error = None
        self._validate_basic_params()

    def _validate_basic_params(self) -> None:
        if "region_x1" in self.params or "region_y1" in self.params or \
           "region_x2" in self.params or "region_y2" in self.params:
            try:
                x1 = int(self.params.get("region_x1", 0))
                y1 = int(self.params.get("region_y1", 0))
                x2 = int(self.params.get("region_x2", x1 + 1))
                y2 = int(self.params.get("region_y2", y1 + 1))
                if x2 <= x1 or y2 <= y1:
                    self._is_valid = False
                    self._validation_error = f"Invalid region: x2({x2}) must be > x1({x1}) and y2({y2}) must be > y1({y1})."
                self.params["region_x1"] = x1
                self.params["region_y1"] = y1
                self.params["region_x2"] = x2
                self.params["region_y2"] = y2
            except (ValueError, TypeError) as e:
                self._is_valid = False
                self._validation_error = f"Invalid region coordinate types: {e}"

    @abstractmethod
    def check(self, **context: Any) -> bool:
        if not self._is_valid:
            logger.warning(f"Condition '{self.name}' (Type: {self.type}, ID: {self.id}) is invalid, check() returning False. Reason: {self._validation_error}")
            return False
        if not _BridgeImported and self.type not in [NoneCondition.TYPE]:
            logger.warning(f"Condition '{self.name}' (Type: {self.type}) requires OS Interaction Bridge, which is not imported. check() returning False.")
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "type": self.type, "params": self.params,
            "is_monitored_by_ai_brain": self.is_monitored_by_ai_brain
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Condition':
        try:
            return create_condition(data)
        except ValueError as ve:
            logger.error(f"ValueError during Condition.from_dict: {ve}. Data: {data}")
            raise ve
        except Exception as e:
            logger.error(f"Unexpected error in Condition.from_dict: {e}. Data: {data}", exc_info=True)
            raise ValueError(f"Could not create Condition from dictionary data: {e}") from e

    def __str__(self) -> str:
        param_str_parts = []
        max_params_to_show = 3
        max_value_len = 20
        params_shown_count = 0
        for k, v in self.params.items():
            if k in ['type', 'name', 'id', 'is_monitored_by_ai_brain']: continue
            if params_shown_count >= max_params_to_show:
                param_str_parts.append("...")
                break
            v_str = str(v)
            if len(v_str) > max_value_len:
                v_str = v_str[:max_value_len-3] + "..."
            param_str_parts.append(f"{k}={v_str}")
            params_shown_count += 1

        param_str = ", ".join(param_str_parts) if param_str_parts else "No Specific Params"
        ai_monitored_str = " (AI Monitored)" if self.is_monitored_by_ai_brain else ""
        return f"Condition(Name='{self.name}', Type='{self.type}', Params=({param_str})){ai_monitored_str}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id='{self.id}', name='{self.name}', type='{self.type}', params={self.params}, is_monitored={self.is_monitored_by_ai_brain})"

class NoneCondition(Condition):
    TYPE = "none"
    def __init__(self, params: Optional[Dict[str, Any]] = None, id: Optional[str] = None, name: Optional[str] = None,
                 is_monitored_by_ai_brain: bool = False) -> None:
        resolved_name = name if name and name.strip() else "Always True"
        super().__init__(type=self.TYPE, params=params, id=id, name=resolved_name, is_monitored_by_ai_brain=False)

    def check(self, **context: Any) -> bool:
        if not super().check(**context): return False
        return True
    def __str__(self) -> str: return f"{self.name} (Always True)"
    def __repr__(self) -> str: return f"NoneCondition(id='{self.id}', name='{self.name}', params={self.params}, is_monitored=False)"

class MultiImageCondition(Condition):
    TYPE = "multi_image_on_screen"

    def __init__(self, params: Optional[Dict[str, Any]] = None, id: Optional[str] = None, name: Optional[str] = None,
                 is_monitored_by_ai_brain: bool = False) -> None:
        super().__init__(type=self.TYPE, params=params, id=id, name=name, is_monitored_by_ai_brain=is_monitored_by_ai_brain)
        if not self._is_valid: return

        if not _CV2Available:
            self._is_valid = False; self._validation_error = "OpenCV (cv2) is not available for MultiImageCondition."
            return
        if not _ImageProcessingAvailable:
            self._is_valid = False; self._validation_error = "Image processing utilities are not available."
            return

        self.anchor_image_path = str(self.params.get("anchor_image_path", "")).strip()
        if not self.anchor_image_path:
            self._is_valid = False; self._validation_error = "Anchor image path is required for MultiImageCondition."
            return
        
        self.anchor_matching_method = str(self.params.get("anchor_matching_method", "template")).lower()
        if self.anchor_matching_method not in ["template", "feature"]: self.anchor_matching_method = "template"
        self.params["anchor_matching_method"] = self.anchor_matching_method 

        try:
            self.anchor_threshold = float(self.params.get("anchor_threshold", 0.8))
            self.anchor_threshold = max(0.0, min(1.0, self.anchor_threshold))
        except (ValueError, TypeError): self.anchor_threshold = 0.8
        self.params["anchor_threshold"] = self.anchor_threshold

        self.anchor_pp_params = {
            key.replace("anchor_pp_", ""): value
            for key, value in self.params.items() if key.startswith("anchor_pp_")
        }
        if not self.anchor_pp_params:
            self.anchor_pp_params = {
                "grayscale": self.params.get("grayscale", True),
            }


        self.sub_images_definitions = self.params.get("sub_images", [])
        if not isinstance(self.sub_images_definitions, list):
            self._is_valid = False; self._validation_error = "'sub_images' parameter must be a list of sub-image definitions."
            return

        for i, sub_def in enumerate(self.sub_images_definitions):
            if not isinstance(sub_def, dict) or \
               not str(sub_def.get("path", "")).strip() or \
               not isinstance(sub_def.get("offset_x_from_anchor"), int) or \
               not isinstance(sub_def.get("offset_y_from_anchor"), int):
                self._is_valid = False; self._validation_error = f"Invalid sub-image definition at index {i}. Requires 'path', 'offset_x_from_anchor' (int), 'offset_y_from_anchor' (int)."
                return
            sub_def["path"] = str(sub_def["path"]).strip()

        self.sub_image_matching_method = str(self.params.get("sub_image_matching_method", "template")).lower()
        if self.sub_image_matching_method not in ["template", "feature"]: self.sub_image_matching_method = "template"
        self.params["sub_image_matching_method"] = self.sub_image_matching_method

        try:
            self.sub_image_threshold = float(self.params.get("sub_image_threshold", 0.7))
            self.sub_image_threshold = max(0.0, min(1.0, self.sub_image_threshold))
        except (ValueError, TypeError): self.sub_image_threshold = 0.7
        self.params["sub_image_threshold"] = self.sub_image_threshold
        
        self.sub_image_pp_params = {
            key.replace("sub_image_pp_", ""): value
            for key, value in self.params.items() if key.startswith("sub_image_pp_")
        }
        if not self.sub_image_pp_params: 
             self.sub_image_pp_params = {
                "grayscale": self.params.get("grayscale", True),
            }


        try:
            self.position_tolerance_x = int(self.params.get("position_tolerance_x", 5))
            self.position_tolerance_y = int(self.params.get("position_tolerance_y", 5))
            if self.position_tolerance_x < 0 or self.position_tolerance_y < 0:
                raise ValueError("Position tolerances must be non-negative.")
        except (ValueError, TypeError):
            self.position_tolerance_x = 5; self.position_tolerance_y = 5
        self.params["position_tolerance_x"] = self.position_tolerance_x
        self.params["position_tolerance_y"] = self.position_tolerance_y
    def _find_single_image(self,
                           screenshot_np: np.ndarray,
                           template_path_relative: str,
                           threshold: float,
                           matching_method_str: str,
                           preprocessing_params: Dict[str, Any],
                           image_storage_instance: Optional[ImageStorage], # type: ignore
                           search_region_for_sub_image: Optional[Tuple[int,int,int,int]] = None
                           ) -> Optional[Tuple[int, int, int, int]]: 
        """
        Helper function to find a single image (anchor or sub-image).
        If search_region_for_sub_image is provided, it searches within that sub-region of screenshot_np.
        The returned coordinates are relative to the original screenshot_np.
        """
        if not template_path_relative: return None

        full_path: Optional[str] = None
        if image_storage_instance:
            try:
                full_path = image_storage_instance.get_full_path(template_path_relative)
                if not image_storage_instance.file_exists(template_path_relative): full_path = None
            except: full_path = os.path.abspath(template_path_relative) # Fallback
        else: full_path = os.path.abspath(template_path_relative)
        
        if not (full_path and os.path.exists(full_path)):
            logger.debug(f"_find_single_image: Template '{template_path_relative}' not found at '{full_path}'.")
            return None

        template_original_cv = cv2.imread(full_path, cv2.IMREAD_UNCHANGED)
        if template_original_cv is None:
            logger.debug(f"_find_single_image: cv2.imread failed for template '{full_path}'.")
            return None

        template_processed_cv = preprocess_for_image_matching(template_original_cv, preprocessing_params)
        if template_processed_cv is None or template_processed_cv.size == 0:
            logger.debug(f"_find_single_image: Preprocessing failed for template '{full_path}'.")
            return None

        search_target_cv = screenshot_np
        offset_x_for_result, offset_y_for_result = 0, 0 

        if search_region_for_sub_image:
            sx1, sy1, sx2, sy2 = search_region_for_sub_image
            h_main, w_main = screenshot_np.shape[:2]
            sx1 = max(0, min(sx1, w_main -1))
            sy1 = max(0, min(sy1, h_main -1))
            sx2 = max(sx1 + 1, min(sx2, w_main))
            sy2 = max(sy1 + 1, min(sy2, h_main))
            if sx2 <= sx1 or sy2 <= sy1:
                logger.debug(f"_find_single_image: Invalid sub-search region {search_region_for_sub_image}. Skipping.")
                return None
            search_target_cv = screenshot_np[sy1:sy2, sx1:sx2]
            offset_x_for_result, offset_y_for_result = sx1, sy1
            if search_target_cv.size == 0:
                logger.debug(f"_find_single_image: Sub-search region is empty. Skipping.")
                return None
        
        search_target_processed_cv = preprocess_for_image_matching(search_target_cv.copy(), preprocessing_params) # Preprocess the search area
        if search_target_processed_cv is None or search_target_processed_cv.size == 0:
            logger.debug(f"_find_single_image: Preprocessing failed for search target area.")
            return None

        if template_processed_cv.shape[0] > search_target_processed_cv.shape[0] or \
           template_processed_cv.shape[1] > search_target_processed_cv.shape[1]:
            logger.debug(f"_find_single_image: Template larger than search area. Tpl: {template_processed_cv.shape}, Search: {search_target_processed_cv.shape}")
            return None
        if template_processed_cv.ndim != search_target_processed_cv.ndim:
            logger.debug(f"_find_single_image: Dimension mismatch. Tpl:{template_processed_cv.ndim}D, Search:{search_target_processed_cv.ndim}D")
            return None
        if template_processed_cv.ndim == 3 and search_target_processed_cv.ndim == 3 and \
           template_processed_cv.shape[2] != search_target_processed_cv.shape[2]:
            logger.debug(f"_find_single_image: Channel mismatch. Tpl:{template_processed_cv.shape[2]}ch, Search:{search_target_processed_cv.shape[2]}ch")
            return None
        found_location_in_search_target: Optional[Tuple[int,int,int,int]] = None 
        if matching_method_str == "template":
            try:
                tm_method_cv2 = cv2.TM_CCOEFF_NORMED
                res_matrix = cv2.matchTemplate(search_target_processed_cv, template_processed_cv, tm_method_cv2)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res_matrix)
                
                match_value = max_val
                loc = max_loc
                if match_value >= threshold:
                    h_tpl, w_tpl = template_processed_cv.shape[:2]
                    found_location_in_search_target = (loc[0], loc[1], loc[0] + w_tpl, loc[1] + h_tpl)
            except cv2.error as e:
                logger.warning(f"_find_single_image: Template matching error for '{template_path_relative}': {e}")
                return None

        elif matching_method_str == "feature":
            if template_processed_cv.ndim != 2 or search_target_processed_cv.ndim != 2:
                logger.debug(f"_find_single_image: Feature matching needs grayscale. Tpl:{template_processed_cv.ndim}, Search:{search_target_processed_cv.ndim}")
                return None
            try:
                current_orb_nfeatures = int(preprocessing_params.get("orb_nfeatures", self.params.get("orb_nfeatures", 500)))
                current_min_matches = int(preprocessing_params.get("min_feature_matches", self.params.get("min_feature_matches", 10)))
                current_inlier_ratio = float(preprocessing_params.get("homography_inlier_ratio", self.params.get("homography_inlier_ratio", 0.75)))


                orb = cv2.ORB_create(nfeatures=current_orb_nfeatures)
                kp1, des1 = orb.detectAndCompute(template_processed_cv, None)
                kp2, des2 = orb.detectAndCompute(search_target_processed_cv, None)

                if des1 is not None and des2 is not None and len(kp1) >= 2 and len(kp2) >= 2:
                    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True) 
                    matches = bf.match(des1, des2)
                    matches = sorted(matches, key=lambda x: x.distance) 
                    good_matches = matches

                    logger.debug(f"_find_single_image: Feature matching for '{template_path_relative}'. Total matches: {len(matches)}, Using 'good' matches: {len(good_matches)}")

                    if len(good_matches) >= current_min_matches:
                        if len(good_matches) >= 4:
                            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

                            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

                            if M is not None and mask is not None:
                                inliers = np.sum(mask)
                                min_inliers_required_for_match = max(4, int(len(good_matches) * current_inlier_ratio))

                                logger.debug(f"_find_single_image: Homography for '{template_path_relative}'. Inliers: {inliers}, Required inliers: {min_inliers_required_for_match}")

                                if inliers >= min_inliers_required_for_match:

                                    h_tpl, w_tpl = template_processed_cv.shape[:2]
                                    pts_template_corners = np.float32([[0, 0], [0, h_tpl - 1], [w_tpl - 1, h_tpl - 1], [w_tpl - 1, 0]]).reshape(-1, 1, 2)

                                    if M.shape == (3,3): 
                                        dst_corners_in_search_target = cv2.perspectiveTransform(pts_template_corners, M)

                                        x_coords = dst_corners_in_search_target[:,0,0]
                                        y_coords = dst_corners_in_search_target[:,0,1]

                                        box_x1 = int(np.min(x_coords))
                                        box_y1 = int(np.min(y_coords))
                                        box_x2 = int(np.max(x_coords))
                                        box_y2 = int(np.max(y_coords))

                                        if box_x2 > box_x1 and box_y2 > box_y1:
                                            found_location_in_search_target = (box_x1, box_y1, box_x2, box_y2)
                                            logger.debug(f"_find_single_image: Feature match success for '{template_path_relative}', Box in search_target: {found_location_in_search_target}")
                                        else:
                                            logger.warning(f"_find_single_image: Feature match for '{template_path_relative}', but bounding box from homography is invalid: ({box_x1},{box_y1})-({box_x2},{box_y2}).")
                                    else:
                                        logger.warning(f"_find_single_image: Homography matrix M for '{template_path_relative}' is not 3x3. Shape: {M.shape}")
                                else:
                                    logger.debug(f"_find_single_image: Not enough inliers for '{template_path_relative}' after homography.")
                            else:
                                logger.debug(f"_find_single_image: findHomography returned None for '{template_path_relative}'.")
                        else:
                             logger.debug(f"_find_single_image: Not enough 'good' matches ({len(good_matches)}) for homography for '{template_path_relative}' (min 4 required).")
                    else:
                        logger.debug(f"_find_single_image: Not enough 'good' matches ({len(good_matches)}) for '{template_path_relative}' (min {current_min_matches} required).")
            except cv2.error as e:
                logger.warning(f"_find_single_image: Feature matching cv2 error for '{template_path_relative}': {e}")
                return None
            except Exception as ex_feat:
                logger.error(f"_find_single_image: Unexpected error in feature matching for '{template_path_relative}': {ex_feat}", exc_info=True)
                return None

        if found_location_in_search_target:
            fx1, fy1, fx2, fy2 = found_location_in_search_target
            return (fx1 + offset_x_for_result, fy1 + offset_y_for_result,
                    fx2 + offset_x_for_result, fy2 + offset_y_for_result)
        return None


    def check(self, image_storage_instance: Optional[ImageStorage] = None, **context: Any) -> bool: # type: ignore
        if not super().check(**context): return False
        if not _CV2Available or not _ImageProcessingAvailable: return False

        # 1. Get the main screenshot
        region_x1 = self.params.get("region_x1", 0)
        region_y1 = self.params.get("region_y1", 0)
        s_width, s_height = os_interaction_client.get_screen_size()
        region_x2 = self.params.get("region_x2", s_width)
        if region_x2 == -1: region_x2 = s_width
        region_y2 = self.params.get("region_y2", s_height)
        if region_y2 == -1: region_y2 = s_height

        if region_x2 <= region_x1 or region_y2 <= region_y1:
            logger.warning(f"MultiImageCondition: Invalid overall search region ({region_x1},{region_y1})-({region_x2},{region_y2}).")
            return False
        
        capture_result = os_interaction_client.capture_region(region_x1, region_y1, region_x2, region_y2)
        full_screenshot_np = capture_result.get("image_np")
        if full_screenshot_np is None or full_screenshot_np.size == 0:
            logger.debug("MultiImageCondition: Failed to capture main screen area for pattern.")
            return False
        main_capture_offset_x = capture_result.get("x1", region_x1)
        main_capture_offset_y = capture_result.get("y1", region_y1)

        # 2. Find Anchor Image (A4.1)
        anchor_found_rect = self._find_single_image(
            full_screenshot_np,
            self.anchor_image_path,
            self.anchor_threshold,
            self.anchor_matching_method,
            self.anchor_pp_params,
            image_storage_instance
        )

        if anchor_found_rect is None:
            logger.debug(f"MultiImageCondition '{self.name}': Anchor image '{self.anchor_image_path}' not found.")
            return False
        
        ax1_rel_to_capture, ay1_rel_to_capture, ax2_rel_to_capture, ay2_rel_to_capture = anchor_found_rect
        logger.debug(f"MultiImageCondition '{self.name}': Anchor '{self.anchor_image_path}' found at relative rect ({ax1_rel_to_capture},{ay1_rel_to_capture})-({ax2_rel_to_capture},{ay2_rel_to_capture}) within captured region.")
        anchor_top_left_x_in_capture = ax1_rel_to_capture
        anchor_top_left_y_in_capture = ay1_rel_to_capture
        anchor_screen_x1 = main_capture_offset_x + ax1_rel_to_capture
        anchor_screen_y1 = main_capture_offset_y + ay1_rel_to_capture
        anchor_screen_x2 = main_capture_offset_x + ax2_rel_to_capture
        anchor_screen_y2 = main_capture_offset_y + ay2_rel_to_capture

        context["last_condition_match_info"] = {
            "type": "multi_image_anchor",
            "x": anchor_screen_x1, 
            "y": anchor_screen_y1,
            "width": anchor_screen_x2 - anchor_screen_x1,
            "height": anchor_screen_y2 - anchor_screen_y1,
            "source_condition_id": self.id
        }


        # 3. Find Sub-Images relative to Anchor
        if not self.sub_images_definitions: 
            logger.debug(f"MultiImageCondition '{self.name}': Anchor found and no sub-images defined. Condition MET.")
            return True

        for sub_def in self.sub_images_definitions:
            sub_path = sub_def["path"]
            offset_x = sub_def["offset_x_from_anchor"]
            offset_y = sub_def["offset_y_from_anchor"]
            expected_sub_tl_x_in_capture = anchor_top_left_x_in_capture + offset_x
            expected_sub_tl_y_in_capture = anchor_top_left_y_in_capture + offset_y
            search_radius_x = self.position_tolerance_x * 3 
            search_radius_y = self.position_tolerance_y * 3
            sub_search_x1 = expected_sub_tl_x_in_capture - search_radius_x
            sub_search_y1 = expected_sub_tl_y_in_capture - search_radius_y
            sub_search_x2 = expected_sub_tl_x_in_capture + search_radius_x 
            sub_search_y2 = expected_sub_tl_y_in_capture + search_radius_y 


            sub_image_found_rect = self._find_single_image(
                full_screenshot_np, 
                sub_path,
                self.sub_image_threshold,
                self.sub_image_matching_method,
                self.sub_image_pp_params,
                image_storage_instance,
                search_region_for_sub_image=(sub_search_x1, sub_search_y1, sub_search_x2, sub_search_y2) # Pass the calculated sub-region
            )

            if sub_image_found_rect is None:
                logger.debug(f"MultiImageCondition '{self.name}': Sub-image '{sub_path}' NOT found near expected relative position.")
                return False 
            sub_actual_tl_x_in_capture, sub_actual_tl_y_in_capture, _, _ = sub_image_found_rect
            
            if not (abs(sub_actual_tl_x_in_capture - expected_sub_tl_x_in_capture) <= self.position_tolerance_x and \
                    abs(sub_actual_tl_y_in_capture - expected_sub_tl_y_in_capture) <= self.position_tolerance_y):
                logger.debug(f"MultiImageCondition '{self.name}': Sub-image '{sub_path}' found, but NOT within position tolerance. Expected TL:({expected_sub_tl_x_in_capture},{expected_sub_tl_y_in_capture}), Actual TL:({sub_actual_tl_x_in_capture},{sub_actual_tl_y_in_capture}), Tol:({self.position_tolerance_x},{self.position_tolerance_y})")
                return False
            logger.debug(f"MultiImageCondition '{self.name}': Sub-image '{sub_path}' found AND within position tolerance.")

        logger.info(f"MultiImageCondition '{self.name}': All sub-images found in correct relative positions. Condition MET.")
        return True 

    def __str__(self) -> str:
        anchor_path_short = os.path.basename(self.params.get("anchor_image_path", "N/A"))
        num_subs = len(self.params.get("sub_images", []))
        ai_monitored_str = " (AI Monitored)" if self.is_monitored_by_ai_brain else ""
        return f"'{self.name}' (Pattern: Anchor='{anchor_path_short}', {num_subs} Subs){ai_monitored_str}"

class ImageOnScreenCondition(Condition):
    TYPE = "image_on_screen"

    def __init__(self, params: Optional[Dict[str, Any]] = None, id: Optional[str] = None, name: Optional[str] = None,
                 is_monitored_by_ai_brain: bool = False) -> None:
        super().__init__(type=self.TYPE, params=params, id=id, name=name, is_monitored_by_ai_brain=is_monitored_by_ai_brain)
        if not self._is_valid: return

        if not _CV2Available: self._is_valid = False; self._validation_error = "OpenCV (cv2) is not available."; return
        if not _ImageProcessingAvailable: self._is_valid = False; self._validation_error = "Image processing utilities are not available."; return

        self.image_path_relative = str(self.params.get("image_path", "")).strip()
        if not self.image_path_relative: self._is_valid = False; self._validation_error = "Image path cannot be empty."; return

        self.matching_method = str(self.params.get("matching_method", "template")).lower()
        if self.matching_method not in ["template", "feature"]: self.matching_method = "template"; self.params["matching_method"] = "template"

        try:
            self.threshold = float(self.params.get("threshold", 0.8))
            self.threshold = max(0.0, min(1.0, self.threshold)); self.params["threshold"] = self.threshold
        except (ValueError, TypeError): self.threshold = 0.8; self.params["threshold"] = 0.8

        try:
            self.orb_nfeatures = int(self.params.get("orb_nfeatures", 500)); self.orb_nfeatures = max(50, self.orb_nfeatures); self.params["orb_nfeatures"] = self.orb_nfeatures
            self.min_feature_matches = int(self.params.get("min_feature_matches", 10)); self.min_feature_matches = max(4, self.min_feature_matches); self.params["min_feature_matches"] = self.min_feature_matches
            self.homography_inlier_ratio = float(self.params.get("homography_inlier_ratio", 0.8)); self.homography_inlier_ratio = max(0.1, min(1.0, self.homography_inlier_ratio)); self.params["homography_inlier_ratio"] = self.homography_inlier_ratio
        except (ValueError, TypeError):
             self.orb_nfeatures = 500; self.params["orb_nfeatures"] = 500
             self.min_feature_matches = 10; self.params["min_feature_matches"] = 10
             self.homography_inlier_ratio = 0.8; self.params["homography_inlier_ratio"] = 0.8

        self.template_matching_method_str = str(self.params.get("template_matching_method", "TM_CCOEFF_NORMED"))
        valid_tm_methods: Dict[str, Optional[int]] = {}
        if _CV2Available:
            valid_tm_methods = {
                "TM_CCOEFF_NORMED": cv2.TM_CCOEFF_NORMED, "TM_CCORR_NORMED": cv2.TM_CCORR_NORMED,
                "TM_SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED
            }
        self.template_matching_method_cv2 = valid_tm_methods.get(self.template_matching_method_str)
        if self.template_matching_method_cv2 is None:
            self.template_matching_method_cv2 = valid_tm_methods.get("TM_CCOEFF_NORMED") if _CV2Available else None
            self.params["template_matching_method"] = "TM_CCOEFF_NORMED"

        self.selection_strategy = str(self.params.get("selection_strategy", "first_found")).lower()
        if self.selection_strategy not in ["first_found", "top_most", "bottom_most", "left_most", "right_most", "closest_to_center_search_region", "closest_to_last_click"]:
            self.selection_strategy = "first_found"
            self.params["selection_strategy"] = "first_found"
        self.reference_point_for_closest_strategy = parse_tuple_str(str(self.params.get("reference_point_for_closest_strategy", "")), 2, int)

        self.params.setdefault("grayscale", True); self.params.setdefault("binarization", False)
        self.params.setdefault("gaussian_blur", False); self.params.setdefault("gaussian_blur_kernel", "3,3")
        self.params.setdefault("median_blur", False); self.params.setdefault("median_blur_kernel", 3)
        self.params.setdefault("clahe", False); self.params.setdefault("clahe_clip_limit", 2.0)
        self.params.setdefault("clahe_tile_grid_size", "8,8"); self.params.setdefault("bilateral_filter", False)
        self.params.setdefault("bilateral_d", 9); self.params.setdefault("bilateral_sigma_color", 75.0)
        self.params.setdefault("bilateral_sigma_space", 75.0); self.params.setdefault("canny_edges", False)
        self.params.setdefault("canny_threshold1", 50.0); self.params.setdefault("canny_threshold2", 150.0)

    def check(self, image_storage_instance: Optional[ImageStorage] = None, last_click_position: Optional[Tuple[int,int]] = None, **context: Any) -> bool: # type: ignore
        if not super().check(**context): return False
        if not _CV2Available or not _ImageProcessingAvailable or not self.image_path_relative: return False

        template_full_path: Optional[str] = None; image_file_exists: bool = False
        if _UtilsImported and isinstance(image_storage_instance, ImageStorage):
            try:
                template_full_path = image_storage_instance.get_full_path(self.image_path_relative)
                image_file_exists = image_storage_instance.file_exists(self.image_path_relative)
            except Exception as e_path:
                logger.warning(f"Error getting path from ImageStorage for '{self.image_path_relative}': {e_path}. Falling back.")
                template_full_path = os.path.abspath(self.image_path_relative)
                image_file_exists = os.path.exists(template_full_path)
        else:
            template_full_path = os.path.abspath(self.image_path_relative)
            image_file_exists = os.path.exists(template_full_path)

        if not image_file_exists or template_full_path is None:
            logger.debug(f"Template image '{self.image_path_relative}' (Full: {template_full_path}) not found.")
            return False

        try:
            template_image_original = cv2.imread(template_full_path, cv2.IMREAD_UNCHANGED)
            if template_image_original is None: logger.debug(f"cv2.imread failed for template '{template_full_path}'."); return False

            template_image_processed = preprocess_for_image_matching(template_image_original, self.params)
            if template_image_processed is None or template_image_processed.size == 0:
                logger.debug(f"Preprocessing failed for template '{template_full_path}'.")
                return False

            region_x1 = self.params.get("region_x1", 0); region_y1 = self.params.get("region_y1", 0)
            region_x2 = self.params.get("region_x2", 100); region_y2 = self.params.get("region_y2", 100)

            capture_result = os_interaction_client.capture_region(region_x1, region_y1, region_x2, region_y2, useGrayscale=False, useBinarization=False)
            screenshot_raw = capture_result.get("image_np")
            if screenshot_raw is None or screenshot_raw.shape[0] <= 0 or screenshot_raw.shape[1] <= 0:
                logger.debug("Failed to capture screen region or captured empty image.")
                return False

            screenshot_processed = preprocess_for_image_matching(screenshot_raw, self.params)
            if screenshot_processed is None or screenshot_processed.size == 0:
                logger.debug("Preprocessing failed for captured screenshot.")
                return False
            match_found_overall: bool = False

            if self.matching_method == "template":
                if self.template_matching_method_cv2 is None: logger.debug("Template matching method (cv2 enum) is None."); return False
                if template_image_processed.shape[0] > screenshot_processed.shape[0] or \
                   template_image_processed.shape[1] > screenshot_processed.shape[1]:
                    logger.debug("Template larger than screenshot after processing. No match possible.")
                    return False
                if template_image_processed.ndim != screenshot_processed.ndim:
                    logger.debug(f"Dimension mismatch: Template ({template_image_processed.ndim}D) vs Screen ({screenshot_processed.ndim}D).")
                    return False
                if template_image_processed.ndim == 3 and screenshot_processed.ndim == 3 and \
                   template_image_processed.shape[2] != screenshot_processed.shape[2]:
                    logger.debug(f"Channel mismatch: Template ({template_image_processed.shape[2]}ch) vs Screen ({screenshot_processed.shape[2]}ch).")
                    return False
                try:
                    result_matrix = cv2.matchTemplate(screenshot_processed, template_image_processed, self.template_matching_method_cv2)

                    locations = []
                    h, w = template_image_processed.shape[:2]
                    is_diff_method = self.template_matching_method_cv2 == cv2.TM_SQDIFF_NORMED

                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result_matrix)
                    match_value = min_val if is_diff_method else max_val
                    loc = min_loc if is_diff_method else max_loc
                    
                    if (is_diff_method and match_value <= (1.0 - self.threshold)) or \
                       (not is_diff_method and match_value >= self.threshold):
                        locations.append({"x": loc[0], "y": loc[1], "width": w, "height": h, "score": match_value})
                    if not locations:
                        match_found_overall = False
                    else:
                        best_single_match = locations[0] 

                        if self.selection_strategy == "first_found":
                            match_found_overall = True
                        elif self.selection_strategy == "top_most":
                            match_found_overall = True 
                        else: 
                             match_found_overall = True

                    logger.debug(f"Template match: Method={self.template_matching_method_str}, BestVal={match_value:.4f}, Thresh={self.threshold:.2f}, Found={match_found_overall}")
                except cv2.error as e_match: logger.warning(f"cv2.matchTemplate error: {e_match}"); return False

            elif self.matching_method == "feature":
                if template_image_processed.ndim != 2 or screenshot_processed.ndim != 2:
                    logger.debug("Feature matching requires grayscale images."); return False
                min_dim_for_orb = 20
                if template_image_processed.shape[0] < min_dim_for_orb or template_image_processed.shape[1] < min_dim_for_orb or \
                   screenshot_processed.shape[0] < min_dim_for_orb or screenshot_processed.shape[1] < min_dim_for_orb:
                    logger.debug("Images too small for ORB feature matching."); return False
                try:
                    orb = cv2.ORB_create(nfeatures=self.orb_nfeatures)
                    kp1, des1 = orb.detectAndCompute(template_image_processed, None)
                    kp2, des2 = orb.detectAndCompute(screenshot_processed, None)
                    if des1 is None or des2 is None or len(kp1) < 2 or len(kp2) < 2 :
                        logger.debug(f"Not enough descriptors/keypoints. Tpl KP: {len(kp1)}, Scr KP: {len(kp2)}"); return False
                    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                    matches = bf.match(des1, des2); matches = sorted(matches, key=lambda x: x.distance)
                    good_matches_count = len(matches)
                    if good_matches_count >= self.min_feature_matches:
                        if good_matches_count >= 4: 
                            src_pts = np.float32([ kp1[m.queryIdx].pt for m in matches ]).reshape(-1,1,2); dst_pts = np.float32([ kp2[m.trainIdx].pt for m in matches ]).reshape(-1,1,2)
                            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
                            if M is not None and mask is not None:
                                inliers_count = np.sum(mask); min_inliers_required = max(4, int(good_matches_count * self.homography_inlier_ratio));
                                match_found_overall = inliers_count >= min_inliers_required
                                logger.debug(f"Feature match: GoodMatches={good_matches_count}, Inliers={inliers_count} (Req based on ratio: {min_inliers_required}), Found={match_found_overall}")
                            else: match_found_overall = False; logger.debug("Feature match: Homography failed.")
                        else: match_found_overall = False; logger.debug("Feature match: Not enough good matches for homography (<4).")
                    else: match_found_overall = False; logger.debug(f"Feature match: Not enough good matches ({good_matches_count} < Min: {self.min_feature_matches}).")
                except cv2.error as e_feat: logger.warning(f"cv2 error during feature matching: {e_feat}"); return False
                except Exception as e_feat_unex: logger.error(f"Unexpected error in feature matching: {e_feat_unex}", exc_info=True); return False
            
            logger.debug(f"ImageOnScreenCondition '{self.name}': Path='{self.image_path_relative}', Region=({region_x1},{region_y1})-({region_x2},{region_y2}), Method='{self.matching_method}', Thresh={self.threshold:.2f}. Match found: {match_found_overall}")
            if self.matching_method == "feature" and hasattr(self, '_last_feature_match_details'):
                logger.debug(f"  Feature details: {self._last_feature_match_details}") 
            return match_found_overall
        except Exception as e_check:
            logger.error(f"Unexpected error in ImageOnScreenCondition.check for '{self.name}': {e_check}", exc_info=True)
            return False
            
    def __str__(self) -> str:
        img_name = os.path.basename(self.image_path_relative) if self.image_path_relative else "None"
        method_display = self.matching_method.title()
        strategy_display = self.selection_strategy.replace("_", " ").title()
        ai_monitored_str = " (AI Monitored)" if self.is_monitored_by_ai_brain else ""
        return f"'{self.name}' (Img: '{img_name}', Mtd: {method_display}, Strat: {strategy_display}, Thresh: {self.threshold:.2f}){ai_monitored_str}"


class TextOnScreenCondition(Condition):
    TYPE = "text_on_screen"

    def __init__(self, params: Optional[Dict[str, Any]] = None, id: Optional[str] = None, name: Optional[str] = None, is_monitored_by_ai_brain: bool = False) -> None:
        super().__init__(type=self.TYPE, params=params, id=id, name=name, is_monitored_by_ai_brain=is_monitored_by_ai_brain)
        if not self._is_valid: return

        if not (_CV2Available and _PytesseractAvailable and _ImageProcessingAvailable):
            self._is_valid = False; self._validation_error = "Missing dependencies for TextOnScreen (OpenCV, Pytesseract, or ImageProcessing)."; return

        self.target_text = str(self.params.get("target_text", "")).strip()
        self.case_sensitive = bool(self.params.get("case_sensitive", False))
        self.use_regex = bool(self.params.get("use_regex", False))
        self.ocr_language = str(self.params.get("ocr_language", "eng")).strip() or "eng"; self.params["ocr_language"] = self.ocr_language
        self.ocr_psm = str(self.params.get("ocr_psm", "6")).strip() or "6"
        self.ocr_char_whitelist = str(self.params.get("ocr_char_whitelist", "")).strip()
        self.user_words_file_path = str(self.params.get("user_words_file_path", "")).strip() or None
        if self.user_words_file_path is not None: self.params["user_words_file_path"] = self.user_words_file_path
        else: self.params.pop("user_words_file_path", None)


        if not self.target_text and not self.use_regex:
            self._is_valid = False; self._validation_error = "Target text cannot be empty unless 'Use Regex' is enabled."
            return

        try:
            psm_int = int(self.ocr_psm)
            if not (0 <= psm_int <= 13): self.ocr_psm = "6"; self.params["ocr_psm"] = "6"
        except (ValueError, TypeError): self.ocr_psm = "6"; self.params["ocr_psm"] = "6"

        self.params.setdefault("grayscale", True); self.params.setdefault("adaptive_threshold", True)
        self.params.setdefault("binarization", False)
        self.params.setdefault("ocr_upscale_factor", 1.0)
        try:
            factor = float(self.params["ocr_upscale_factor"])
            self.params["ocr_upscale_factor"] = max(1.0, factor)
        except (ValueError, TypeError): self.params["ocr_upscale_factor"] = 1.0

        self.params.setdefault("median_blur", True); self.params.setdefault("median_blur_kernel", 3)
        try:
            k_med = int(self.params["median_blur_kernel"])
            if not (k_med > 0 and k_med % 2 == 1): raise ValueError("Median kernel must be positive odd int")
            self.params["median_blur_kernel"] = k_med
        except (ValueError, TypeError): self.params["median_blur_kernel"] = 3

        self.params.setdefault("gaussian_blur", False); self.params.setdefault("gaussian_blur_kernel", "3,3")
        self.params.setdefault("clahe", False); self.params.setdefault("clahe_clip_limit", 2.0);
        self.params.setdefault("clahe_tile_grid_size", "8,8"); self.params.setdefault("bilateral_filter", False)
        self.params.setdefault("bilateral_d", 5); self.params.setdefault("bilateral_sigma_color", 75.0);
        self.params.setdefault("bilateral_sigma_space", 75.0)
        self.params.pop("canny_edges", None); self.params.pop("canny_threshold1", None); self.params.pop("canny_threshold2", None)


    def check(self, image_storage_instance: Optional[ImageStorage] = None, **context: Any) -> bool: # type: ignore
        if not super().check(**context): return False
        if not (_CV2Available and _PytesseractAvailable and _ImageProcessingAvailable): return False

        try:
            region_x1 = self.params.get("region_x1", 0); region_y1 = self.params.get("region_y1", 0)
            region_x2 = self.params.get("region_x2", 100); region_y2 = self.params.get("region_y2", 100)

            capture_result = os_interaction_client.capture_region(region_x1, region_y1, region_x2, region_y2, useGrayscale=False, useBinarization=False)
            screenshot_raw = capture_result.get("image_np")
            if screenshot_raw is None or screenshot_raw.shape[0] <= 0 or screenshot_raw.shape[1] <= 0:
                logger.debug("TextOnScreen: Failed to capture screen region or captured empty image.")
                return False

            screenshot_processed_for_ocr = preprocess_for_ocr(screenshot_raw, self.params)
            if screenshot_processed_for_ocr is None or screenshot_processed_for_ocr.size == 0:
                logger.debug("TextOnScreen: Preprocessing for OCR failed.")
                return False

            img_pil_for_ocr: Optional[Image.Image] = None
            try:
                 if screenshot_processed_for_ocr.ndim == 3:
                     img_pil_for_ocr = Image.fromarray(cv2.cvtColor(screenshot_processed_for_ocr, cv2.COLOR_BGR2RGB))
                 elif screenshot_processed_for_ocr.ndim == 2:
                     img_pil_for_ocr = Image.fromarray(screenshot_processed_for_ocr, 'L')
                 else: logger.debug(f"TextOnScreen: Processed image has unsupported dimensions ({screenshot_processed_for_ocr.ndim})."); return False
            except Exception as e_pil: logger.error(f"TextOnScreen: Error converting processed numpy to PIL Image: {e_pil}"); return False

            if img_pil_for_ocr is None: logger.debug("TextOnScreen: PIL image conversion resulted in None."); return False

            tesseract_config_parts = [f'--psm {self.ocr_psm}', '--oem 3', f'-l {self.ocr_language}']
            if self.ocr_char_whitelist: tesseract_config_parts.append(f'-c tessedit_char_whitelist={self.ocr_char_whitelist}')

            if self.user_words_file_path:
                full_user_words_path = ""
                if image_storage_instance and isinstance(image_storage_instance, ImageStorage):
                    try: full_user_words_path = image_storage_instance.get_full_path(self.user_words_file_path)
                    except Exception: full_user_words_path = os.path.abspath(self.user_words_file_path)
                else: full_user_words_path = os.path.abspath(self.user_words_file_path)

                if os.path.exists(full_user_words_path) and os.path.isfile(full_user_words_path):
                    tesseract_config_parts.append(f'-c tessedit_user_words_file="{full_user_words_path}"')
                    logger.debug(f"TextOnScreen: Using user words file: {full_user_words_path}")
                else:
                    logger.warning(f"TextOnScreen: User words file specified but not found: '{self.user_words_file_path}' (Resolved: '{full_user_words_path}')")

            tesseract_config_str = " ".join(tesseract_config_parts)
            logger.debug(f"TextOnScreen: Tesseract config: '{tesseract_config_str}'")

            recognized_text = pytesseract.image_to_string(img_pil_for_ocr, config=tesseract_config_str)
            recognized_text_cleaned = recognized_text.strip()
            logger.debug(f"TextOnScreen: Recognized text (cleaned): '{recognized_text_cleaned[:100]}{'...' if len(recognized_text_cleaned)>100 else ''}'")

            target_to_check = self.target_text
            text_to_search_in = recognized_text_cleaned
            match_flags = 0 if self.case_sensitive else re.IGNORECASE

            if self.use_regex:
                try:
                    match_result = bool(re.search(target_to_check, text_to_search_in, flags=match_flags))
                    logger.debug(f"TextOnScreen: Regex search for '{target_to_check}' in text. Result: {match_result}")
                    return match_result
                except re.error as e_regex:
                    logger.warning(f"TextOnScreen: Invalid regex '{target_to_check}': {e_regex}. Condition returns False.")
                    return False
            else:
                if not self.case_sensitive:
                    found = target_to_check.lower() in text_to_search_in.lower()
                else:
                    found = target_to_check in text_to_search_in
                logger.debug(f"TextOnScreen: Plain text search for '{target_to_check}' (CaseSensitive={self.case_sensitive}). Result: {found}")
                return found
        except pytesseract.TesseractNotFoundError:
            logger.error("TextOnScreen: Tesseract not found. Ensure it's installed and in PATH or tesseract_cmd is set.")
            return False
        except Exception as e_check_ocr:
            logger.error(f"TextOnScreen: Unexpected error during OCR check for '{self.name}': {e_check_ocr}", exc_info=True)
            return False

    def __str__(self) -> str:
        mode = "Regex" if self.use_regex else "Text"
        case = "CS" if self.case_sensitive else "CI"
        text_preview = self.target_text[:20] + ('...' if len(self.target_text) > 20 else '')
        ai_monitored_str = " (AI Monitored)" if self.is_monitored_by_ai_brain else ""
        return f"'{self.name}' ({mode}: '{text_preview}', Lang: {self.ocr_language}, {case}){ai_monitored_str}"


class ColorAtPositionCondition(Condition):
    TYPE = "color_at_position"

    def __init__(self, params: Optional[Dict[str, Any]] = None, id: Optional[str] = None, name: Optional[str] = None, is_monitored_by_ai_brain: bool = False) -> None:
        super().__init__(type=self.TYPE, params=params, id=id, name=name, is_monitored_by_ai_brain=is_monitored_by_ai_brain)
        if not self._is_valid: return
        if not _UtilsImported: self._is_valid = False; self._validation_error = "color_utils dependency missing."; return

        try:
            if "abs_color_x" in self.params and "abs_color_y" in self.params:
                self.abs_color_x = int(self.params["abs_color_x"])
                self.abs_color_y = int(self.params["abs_color_y"])
            else:
                 if "region_x1" not in self.params or "region_y1" not in self.params:
                     self._is_valid = False; self._validation_error = "ColorAtPosition requires either 'abs_color_x/y' or 'region_x1/y1' and 'color_x/y' (offset)."; return
                 self.color_x_in_region = int(self.params.get("color_x", 0))
                 self.color_y_in_region = int(self.params.get("color_y", 0))
                 self.abs_color_x = self.params["region_x1"] + self.color_x_in_region
                 self.abs_color_y = self.params["region_y1"] + self.color_y_in_region
                 self.params["abs_color_x"] = self.abs_color_x
                 self.params["abs_color_y"] = self.abs_color_y

            self.target_color_hex = str(self.params.get("color_hex", "#000000")).strip()
            self.target_color_rgb = hex_to_rgb(self.target_color_hex)
            self.params["color_hex"] = rgb_to_hex(self.target_color_rgb)

            self.tolerance = int(self.params.get("tolerance", 0))
            self.tolerance = max(0, min(765, self.tolerance)); self.params["tolerance"] = self.tolerance
        except (ValueError, TypeError, ImportError) as e_param:
             self._is_valid = False; self._validation_error = f"Invalid parameter for ColorAtPosition: {e_param}"
        except Exception as e_init:
             self._is_valid = False; self._validation_error = f"Unexpected init error in ColorAtPosition: {e_init}"


    def check(self, **context: Any) -> bool:
        if not super().check(**context): return False
        if not _UtilsImported: return False

        try:
            actual_color_hex = os_interaction_client.get_pixel_color(self.abs_color_x, self.abs_color_y)
            if actual_color_hex is None:
                logger.debug(f"ColorAtPosition: get_pixel_color returned None for ({self.abs_color_x},{self.abs_color_y}).")
                return False

            actual_color_rgb = hex_to_rgb(actual_color_hex)
            dist = abs(actual_color_rgb[0] - self.target_color_rgb[0]) + \
                   abs(actual_color_rgb[1] - self.target_color_rgb[1]) + \
                   abs(actual_color_rgb[2] - self.target_color_rgb[2])
            
            is_match = dist <= self.tolerance
            logger.debug(f"ColorAtPosition ({self.abs_color_x},{self.abs_color_y}): Target={self.target_color_hex}, Actual={actual_color_hex}, Dist={dist}, Tol={self.tolerance}, Match={is_match}")
            return is_match
        except ImportError: logger.error("ColorAtPosition: color_utils not available for hex/rgb conversion."); return False
        except Exception as e_check_color:
            logger.error(f"ColorAtPosition: Error during check for '{self.name}': {e_check_color}", exc_info=True)
            return False

    def __str__(self) -> str:
        coords = f"({getattr(self,'abs_color_x','?')},{getattr(self,'abs_color_y','?')})"
        hex_val = getattr(self,'target_color_hex','?')
        tol_val = getattr(self,'tolerance','?')
        ai_monitored_str = " (AI Monitored)" if self.is_monitored_by_ai_brain else ""
        return f"'{self.name}' (Color At {coords} is {hex_val} Tol:{tol_val}){ai_monitored_str}"

class WindowExistsCondition(Condition):
    TYPE = "window_exists";

    def __init__(self, params: Optional[Dict[str, Any]] = None, id: Optional[str] = None, name: Optional[str] = None, is_monitored_by_ai_brain: bool = False) -> None:
        super().__init__(type=self.TYPE, params=params, id=id, name=name, is_monitored_by_ai_brain=is_monitored_by_ai_brain)
        if not self._is_valid: return
        try:
            self.window_title = str(self.params.get("window_title", "")).strip() or None
            self.window_class = str(self.params.get("window_class", "")).strip() or None
            if not self.window_title and not self.window_class:
                self._is_valid = False; self._validation_error = "Either window title (contains) or class name (exact) must be specified."
            self.params["window_title"] = self.window_title if self.window_title else ""
            self.params["window_class"] = self.window_class if self.window_class else ""
        except Exception as e: self._is_valid = False; self._validation_error = str(e)

    def check(self, **context: Any) -> bool:
        if not super().check(**context): return False
        try:
            exists = os_interaction_client.check_window_exists(self.window_title, self.window_class)
            logger.debug(f"WindowExists (Title='{self.window_title or '*'}', Class='{self.window_class or '*'}') -> {exists}")
            return exists
        except Exception as e_check_win:
            logger.error(f"WindowExists: Error during check for '{self.name}': {e_check_win}", exc_info=True)
            return False
    def __str__(self) -> str:
        title_disp = self.params.get("window_title") or '*'
        class_disp = self.params.get("window_class") or '*'
        ai_monitored_str = " (AI Monitored)" if self.is_monitored_by_ai_brain else ""
        return f"'{self.name}' (Window: Title='{title_disp}' Class='{class_disp}'){ai_monitored_str}"

class ProcessExistsCondition(Condition):
    TYPE = "process_exists";

    def __init__(self, params: Optional[Dict[str, Any]] = None, id: Optional[str] = None, name: Optional[str] = None, is_monitored_by_ai_brain: bool = False) -> None:
        super().__init__(type=self.TYPE, params=params, id=id, name=name, is_monitored_by_ai_brain=is_monitored_by_ai_brain)
        if not self._is_valid: return
        try:
            self.process_name = str(self.params.get("process_name", "")).strip()
            if not self.process_name:
                self._is_valid = False; self._validation_error = "Process name must be specified (e.g., notepad.exe)."
            self.params["process_name"] = self.process_name
        except Exception as e: self._is_valid = False; self._validation_error = str(e)

    def check(self, **context: Any) -> bool:
        if not super().check(**context): return False
        try:
            exists = os_interaction_client.check_process_exists(self.process_name)
            logger.debug(f"ProcessExists (Name='{self.process_name}') -> {exists}")
            return exists
        except Exception as e_check_proc:
            logger.error(f"ProcessExists: Error during check for '{self.name}': {e_check_proc}", exc_info=True)
            return False
    def __str__(self) -> str:
        ai_monitored_str = " (AI Monitored)" if self.is_monitored_by_ai_brain else ""
        return f"'{self.name}' (Process: '{self.params.get('process_name', '')}'){ai_monitored_str}"


class TextInRelativeRegionCondition(Condition):
    TYPE = "text_in_relative_region"

    def __init__(self, params: Optional[Dict[str, Any]] = None, id: Optional[str] = None, name: Optional[str] = None,
                 is_monitored_by_ai_brain: bool = False) -> None:
        super().__init__(type=self.TYPE, params=params, id=id, name=name, is_monitored_by_ai_brain=is_monitored_by_ai_brain)
        if not self._is_valid: return

        if not (_CV2Available and _PytesseractAvailable and _ImageProcessingAvailable and _BridgeImported):
            self._is_valid = False; self._validation_error = "Missing dependencies for TextInRelativeRegion."; return

        self.anchor_image_path = str(self.params.get("anchor_image_path", "")).strip()
        if not self.anchor_image_path: self._is_valid = False; self._validation_error = "Anchor image path is required."; return
        self.anchor_matching_method = str(self.params.get("anchor_matching_method", "template")).lower()
        self.params["anchor_matching_method"] = self.anchor_matching_method
        try: self.anchor_threshold = float(self.params.get("anchor_threshold", 0.8)); self.params["anchor_threshold"] = max(0.0, min(1.0, self.anchor_threshold))
        except (ValueError, TypeError): self.anchor_threshold = 0.8; self.params["anchor_threshold"] = 0.8
        self.params.setdefault("anchor_pp_grayscale", True)

        self.text_to_find = str(self.params.get("text_to_find", "")).strip()
        self.ocr_use_regex = bool(self.params.get("ocr_use_regex", False))
        if not self.text_to_find and not self.ocr_use_regex: self._is_valid = False; self._validation_error = "Text to find (or Regex) is required."; return
        self.ocr_case_sensitive = bool(self.params.get("ocr_case_sensitive", False))
        self.ocr_language = str(self.params.get("ocr_language", "eng")).strip() or "eng"; self.params["ocr_language"] = self.ocr_language
        self.ocr_psm = str(self.params.get("ocr_psm", "6")).strip() or "6"; self.params["ocr_psm"] = self.ocr_psm
        self.ocr_char_whitelist = str(self.params.get("ocr_char_whitelist", "")).strip() or None
        if self.ocr_char_whitelist is not None: self.params["ocr_char_whitelist"] = self.ocr_char_whitelist
        else: self.params.pop("ocr_char_whitelist", None)
        self.ocr_user_words_file_path = str(self.params.get("ocr_user_words_file_path", "")).strip() or None
        if self.ocr_user_words_file_path is not None: self.params["ocr_user_words_file_path"] = self.ocr_user_words_file_path
        else: self.params.pop("ocr_user_words_file_path", None)
        self.params.setdefault("ocr_pp_grayscale", True)

        try:
            self.relative_x_offset = int(self.params.get("relative_x_offset", 0))
            self.relative_y_offset = int(self.params.get("relative_y_offset", 0))
            self.relative_width = int(self.params.get("relative_width", 50))
            if self.relative_width <= 0: self._is_valid = False; self._validation_error = "Relative width must be positive."; return
            self.relative_height = int(self.params.get("relative_height", 20))
            if self.relative_height <= 0: self._is_valid = False; self._validation_error = "Relative height must be positive."; return
        except (ValueError, TypeError): self._is_valid = False; self._validation_error = "Relative region dimensions/offsets must be integers."; return
        self.relative_to_corner = str(self.params.get("relative_to_corner", "top_left")).lower()
        if self.relative_to_corner not in ["top_left", "top_right", "bottom_left", "bottom_right", "center"]:
            self.relative_to_corner = "top_left"; self.params["relative_to_corner"] = "top_left"

    def _find_anchor_image(self, screenshot_np: np.ndarray, image_storage_instance: Optional[ImageStorage]) -> Optional[Tuple[int, int, int, int]]: # type: ignore
        if not self.anchor_image_path or not _CV2Available: return None

        anchor_full_path: Optional[str] = None
        if _UtilsImported and isinstance(image_storage_instance, ImageStorage):
            try: anchor_full_path = image_storage_instance.get_full_path(self.anchor_image_path)
            except Exception: anchor_full_path = os.path.abspath(self.anchor_image_path)
        else: anchor_full_path = os.path.abspath(self.anchor_image_path)

        if not (anchor_full_path and os.path.exists(anchor_full_path)):
            logger.debug(f"TextInRelativeRegion: Anchor image '{self.anchor_image_path}' not found at '{anchor_full_path}'."); return None

        anchor_tpl_original = cv2.imread(anchor_full_path, cv2.IMREAD_UNCHANGED)
        if anchor_tpl_original is None: logger.debug(f"TextInRelativeRegion: Failed to load anchor template '{anchor_full_path}'."); return None

        anchor_pp_params = {k.replace("anchor_pp_", ""): v for k,v in self.params.items() if k.startswith("anchor_pp_")}
        if not anchor_pp_params: anchor_pp_params = {"grayscale": self.params.get("anchor_pp_grayscale", True)}

        anchor_tpl_processed = preprocess_for_image_matching(anchor_tpl_original, anchor_pp_params)
        if anchor_tpl_processed is None or anchor_tpl_processed.size == 0: logger.debug("TextInRelativeRegion: Anchor template preprocessing failed."); return None

        screenshot_for_anchor_match = preprocess_for_image_matching(screenshot_np.copy(), anchor_pp_params)
        if screenshot_for_anchor_match is None or screenshot_for_anchor_match.size == 0: logger.debug("TextInRelativeRegion: Screenshot preprocessing for anchor failed."); return None

        if anchor_tpl_processed.shape[0] > screenshot_for_anchor_match.shape[0] or anchor_tpl_processed.shape[1] > screenshot_for_anchor_match.shape[1]:
            logger.debug("TextInRelativeRegion: Anchor template larger than screenshot. No match possible."); return None
        if anchor_tpl_processed.ndim != screenshot_for_anchor_match.ndim:
            logger.debug(f"TextInRelativeRegion: Anchor/Screen dimension mismatch. Tpl:{anchor_tpl_processed.ndim}D, Scr:{screenshot_for_anchor_match.ndim}D"); return None
        if anchor_tpl_processed.ndim == 3 and screenshot_for_anchor_match.ndim == 3 and anchor_tpl_processed.shape[2] != screenshot_for_anchor_match.shape[2]:
            logger.debug(f"TextInRelativeRegion: Anchor/Screen channel mismatch. Tpl:{anchor_tpl_processed.shape[2]}ch, Scr:{screenshot_for_anchor_match.shape[2]}ch"); return None

        try:
            result = cv2.matchTemplate(screenshot_for_anchor_match, anchor_tpl_processed, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= self.anchor_threshold:
                h, w = anchor_tpl_processed.shape[:2]
                top_left_x, top_left_y = max_loc
                return (top_left_x, top_left_y, top_left_x + w, top_left_y + h)
            else:
                logger.debug(f"TextInRelativeRegion: Anchor not found (Match val: {max_val:.2f} < Thresh: {self.anchor_threshold:.2f})")
                return None
        except cv2.error as e_match: logger.warning(f"TextInRelativeRegion: cv2.matchTemplate error for anchor: {e_match}"); return None
        except Exception as e_anchor: logger.error(f"TextInRelativeRegion: Error finding anchor: {e_anchor}", exc_info=True); return None


    def check(self, image_storage_instance: Optional[ImageStorage] = None, **context: Any) -> bool: # type: ignore
        if not super().check(**context): return False

        screen_region_x1 = self.params.get("region_x1", 0)
        screen_region_y1 = self.params.get("region_y1", 0)
        screen_region_x2 = self.params.get("region_x2", -1)
        screen_region_y2 = self.params.get("region_y2", -1)

        if screen_region_x2 == -1 or screen_region_y2 == -1:
            try:
                s_width, s_height = os_interaction_client.get_screen_size()
                if screen_region_x2 == -1: screen_region_x2 = s_width
                if screen_region_y2 == -1: screen_region_y2 = s_height
            except Exception as e_scr_size:
                logger.error(f"TextInRelativeRegion: Could not get screen size: {e_scr_size}. Using defaults.");
                screen_region_x2 = screen_region_x1 + 600 if screen_region_x2 == -1 else screen_region_x2
                screen_region_y2 = screen_region_y1 + 400 if screen_region_y2 == -1 else screen_region_y2
        
        if screen_region_x2 <= screen_region_x1 or screen_region_y2 <= screen_region_y1:
            logger.warning(f"TextInRelativeRegion: Invalid overall search region after defaults/screen size. ({screen_region_x1},{screen_region_y1})-({screen_region_x2},{screen_region_y2})")
            return False

        capture_result = os_interaction_client.capture_region(screen_region_x1, screen_region_y1, screen_region_x2, screen_region_y2)
        full_screenshot_np = capture_result.get("image_np")
        if full_screenshot_np is None or full_screenshot_np.size == 0: logger.debug("TextInRelativeRegion: Failed to capture main screen area."); return False

        anchor_bounds_in_screenshot = self._find_anchor_image(full_screenshot_np, image_storage_instance)
        if anchor_bounds_in_screenshot is None: logger.debug("TextInRelativeRegion: Anchor image not found."); return False
        
        ax1, ay1, ax2, ay2 = anchor_bounds_in_screenshot
        logger.debug(f"TextInRelativeRegion: Anchor found at relative coords ({ax1},{ay1})-({ax2},{ay2}) within captured region.")

        ocr_x1, ocr_y1 = 0, 0
        if self.relative_to_corner == "top_left": ocr_x1, ocr_y1 = ax1 + self.relative_x_offset, ay1 + self.relative_y_offset
        elif self.relative_to_corner == "top_right": ocr_x1, ocr_y1 = ax2 + self.relative_x_offset, ay1 + self.relative_y_offset
        elif self.relative_to_corner == "bottom_left": ocr_x1, ocr_y1 = ax1 + self.relative_x_offset, ay2 + self.relative_y_offset
        elif self.relative_to_corner == "bottom_right": ocr_x1, ocr_y1 = ax2 + self.relative_x_offset, ay2 + self.relative_y_offset
        elif self.relative_to_corner == "center": ocr_x1, ocr_y1 = (ax1+ax2)//2 + self.relative_x_offset, (ay1+ay2)//2 + self.relative_y_offset
        
        ocr_x2, ocr_y2 = ocr_x1 + self.relative_width, ocr_y1 + self.relative_height
        logger.debug(f"TextInRelativeRegion: Calculated relative OCR region (coords in screenshot): ({ocr_x1},{ocr_y1})-({ocr_x2},{ocr_y2})")

        h_screen, w_screen = full_screenshot_np.shape[:2]
        ocr_x1_clamped = max(0, min(ocr_x1, w_screen -1))
        ocr_y1_clamped = max(0, min(ocr_y1, h_screen -1))
        ocr_x2_clamped = max(ocr_x1_clamped + 1, min(ocr_x2, w_screen))
        ocr_y2_clamped = max(ocr_y1_clamped + 1, min(ocr_y2, h_screen))

        if ocr_x2_clamped <= ocr_x1_clamped or ocr_y2_clamped <= ocr_y1_clamped:
            logger.debug(f"TextInRelativeRegion: Clamped OCR region is invalid or zero-size. Original: ({ocr_x1},{ocr_y1})-({ocr_x2},{ocr_y2}), Clamped: ({ocr_x1_clamped},{ocr_y1_clamped})-({ocr_x2_clamped},{ocr_y2_clamped})"); return False
        
        relative_region_np = full_screenshot_np[ocr_y1_clamped:ocr_y2_clamped, ocr_x1_clamped:ocr_x2_clamped]
        if relative_region_np is None or relative_region_np.size == 0: logger.debug("TextInRelativeRegion: Cropped relative region is empty."); return False

        ocr_pp_params = {k.replace("ocr_pp_", ""): v for k,v in self.params.items() if k.startswith("ocr_pp_")}
        if not ocr_pp_params: ocr_pp_params = {"grayscale": self.params.get("ocr_pp_grayscale", True)}

        ocr_region_processed = preprocess_for_ocr(relative_region_np, ocr_pp_params)
        if ocr_region_processed is None or ocr_region_processed.size == 0: logger.debug("TextInRelativeRegion: OCR region preprocessing failed."); return False
        
        try:
            img_pil_for_ocr: Optional[Image.Image] = None
            if ocr_region_processed.ndim == 3: img_pil_for_ocr = Image.fromarray(cv2.cvtColor(ocr_region_processed, cv2.COLOR_BGR2RGB))
            elif ocr_region_processed.ndim == 2: img_pil_for_ocr = Image.fromarray(ocr_region_processed, 'L')
            if img_pil_for_ocr is None: logger.debug("TextInRelativeRegion: PIL conversion for OCR region failed."); return False

            t_conf_parts = [f'--psm {self.ocr_psm}', '--oem 3', f'-l {self.ocr_language}']
            if self.ocr_char_whitelist: t_conf_parts.append(f'-c tessedit_char_whitelist={self.ocr_char_whitelist}')
            if self.ocr_user_words_file_path:
                full_user_words_path_rel = ""
                if image_storage_instance and isinstance(image_storage_instance, ImageStorage):
                    try: full_user_words_path_rel = image_storage_instance.get_full_path(self.ocr_user_words_file_path)
                    except: full_user_words_path_rel = os.path.abspath(self.ocr_user_words_file_path)
                else: full_user_words_path_rel = os.path.abspath(self.ocr_user_words_file_path)
                if os.path.exists(full_user_words_path_rel): t_conf_parts.append(f'-c tessedit_user_words_file="{full_user_words_path_rel}"')
                else: logger.warning(f"TextInRelativeRegion: OCR user words file not found: '{full_user_words_path_rel}'")
            
            t_conf_str = " ".join(t_conf_parts)
            recognized_text = pytesseract.image_to_string(img_pil_for_ocr, config=t_conf_str).strip()
            logger.debug(f"TextInRelativeRegion: OCR Text from relative region: '{recognized_text[:50]}...'")

            match_flags = 0 if self.ocr_case_sensitive else re.IGNORECASE
            if self.ocr_use_regex:
                return bool(re.search(self.text_to_find, recognized_text, flags=match_flags))
            else:
                return self.text_to_find.lower() in recognized_text.lower() if not self.ocr_case_sensitive else self.text_to_find in recognized_text
        except pytesseract.TesseractNotFoundError: logger.error("TextInRelativeRegion: Tesseract not found."); return False
        except Exception as e_ocr_rel: logger.error(f"TextInRelativeRegion: Error during OCR: {e_ocr_rel}", exc_info=True); return False

    def __str__(self) -> str:
        anchor_name = os.path.basename(self.anchor_image_path) if self.anchor_image_path else "None"
        text_preview = self.text_to_find[:15] + ('...' if len(self.text_to_find) > 15 else '')
        ai_monitored_str = " (AI Monitored)" if self.is_monitored_by_ai_brain else ""
        return f"'{self.name}' (Text '{text_preview}' near Anchor '{anchor_name}'){ai_monitored_str}"

RegionColorLogic = Literal["ANY_TARGET_MET_THRESHOLD", "ALL_TARGETS_MET_THRESHOLD", "TOTAL_PERCENTAGE_ABOVE_THRESHOLD"]

class RegionColorCondition(Condition):
    TYPE = "region_color"

    def __init__(self, params: Optional[Dict[str, Any]] = None, id: Optional[str] = None, name: Optional[str] = None,
                 is_monitored_by_ai_brain: bool = False) -> None:
        super().__init__(type=self.TYPE, params=params, id=id, name=name, is_monitored_by_ai_brain=is_monitored_by_ai_brain)
        if not self._is_valid: return
        if not _UtilsImported: self._is_valid = False; self._validation_error = "color_utils or image_analysis_utils dependency missing."; return
        if not _CV2Available: self._is_valid = False; self._validation_error = "OpenCV (cv2) is not available for image processing."; return

        self.target_colors_list: List[Dict[str, Any]] = []
        raw_target_colors = self.params.get("target_colors", [])
        if not isinstance(raw_target_colors, list):
            self._is_valid = False; self._validation_error = "'target_colors' must be a list of color definitions."; return
        for i, color_def in enumerate(raw_target_colors):
            if not isinstance(color_def, dict): self._is_valid = False; self._validation_error = f"Color definition at index {i} must be a dict."; return
            try:
                hex_val = str(color_def.get("hex", "#000000")).strip()
                rgb_val = hex_to_rgb(hex_val)
                tolerance = int(color_def.get("tolerance", 10))
                tolerance = max(0, min(255, tolerance)) # Tolerance per channel for image_analysis
                label = str(color_def.get("label", f"Color{i+1}")).strip()
                color_threshold = float(color_def.get("threshold", self.params.get("match_percentage_threshold", 75.0)))
                color_threshold = max(0.0, min(100.0, color_threshold))

                self.target_colors_list.append({
                    "hex": rgb_to_hex(rgb_val), "rgb": rgb_val, "tolerance": tolerance, "label": label, "threshold": color_threshold
                })
            except (ValueError, TypeError) as e_color_def:
                self._is_valid = False; self._validation_error = f"Invalid color definition at index {i}: {e_color_def}"; return
        
        self.params["target_colors"] = self.target_colors_list

        self.match_percentage_threshold = float(self.params.get("match_percentage_threshold", 75.0))
        self.match_percentage_threshold = max(0.0, min(100.0, self.match_percentage_threshold))
        self.params["match_percentage_threshold"] = self.match_percentage_threshold

        self.sampling_step = int(self.params.get("sampling_step", 1))
        self.sampling_step = max(1, self.sampling_step); self.params["sampling_step"] = self.sampling_step

        self.condition_logic: RegionColorLogic = self.params.get("condition_logic", "ANY_TARGET_MET_THRESHOLD") # type: ignore
        if self.condition_logic not in ["ANY_TARGET_MET_THRESHOLD", "ALL_TARGETS_MET_THRESHOLD", "TOTAL_PERCENTAGE_ABOVE_THRESHOLD"]:
            self.condition_logic = "ANY_TARGET_MET_THRESHOLD"
        self.params["condition_logic"] = self.condition_logic
        
        if not self.target_colors_list and self.condition_logic in ["ANY_TARGET_MET_THRESHOLD", "ALL_TARGETS_MET_THRESHOLD"]:
            self._is_valid = False; self._validation_error = "At least one target color must be defined for the selected logic."; return


    def check(self, **context: Any) -> bool:
        if not super().check(**context): return False
        if not _UtilsImported or not _CV2Available: return False

        try:
            region_x1 = self.params.get("region_x1", 0); region_y1 = self.params.get("region_y1", 0)
            region_x2 = self.params.get("region_x2", 100); region_y2 = self.params.get("region_y2", 100)

            capture_result = os_interaction_client.capture_region(region_x1, region_y1, region_x2, region_y2, useGrayscale=False, useBinarization=False)
            region_image_np = capture_result.get("image_np")
            if region_image_np is None or region_image_np.size == 0:
                logger.debug("RegionColorCondition: Failed to capture region or captured empty image.")
                return False

            img_rgb = None
            if region_image_np.shape[2] == 4: img_rgb = cv2.cvtColor(region_image_np, cv2.COLOR_BGRA2RGB)
            elif region_image_np.shape[2] == 3: img_rgb = cv2.cvtColor(region_image_np, cv2.COLOR_BGR2RGB)
            else: logger.warning(f"RegionColorCondition: Captured image has unexpected channel count: {region_image_np.shape[2]}"); return False
            if img_rgb is None: return False

            targets_for_analysis: List[Tuple[Tuple[int,int,int], int]] = []
            for color_def in self.target_colors_list:
                targets_for_analysis.append((color_def["rgb"], color_def["tolerance"]))

            color_percentages = analyze_region_colors(img_rgb, targets_for_analysis, self.sampling_step)
            logger.debug(f"RegionColorCondition '{self.name}': Analyzed percentages: {color_percentages}")

            if self.condition_logic == "ANY_TARGET_MET_THRESHOLD":
                if not self.target_colors_list: return False
                for color_def in self.target_colors_list:
                    hex_key = color_def["hex"]
                    individual_threshold = color_def.get("threshold", self.match_percentage_threshold)
                    if color_percentages.get(hex_key, 0.0) >= individual_threshold:
                        logger.debug(f"RegionColorCondition '{self.name}': ANY logic MET for {hex_key} ({color_percentages.get(hex_key,0.0):.2f}% >= {individual_threshold:.2f}%)")
                        return True
                logger.debug(f"RegionColorCondition '{self.name}': ANY logic NOT MET for any target.")
                return False
            elif self.condition_logic == "ALL_TARGETS_MET_THRESHOLD":
                if not self.target_colors_list: return True
                for color_def in self.target_colors_list:
                    hex_key = color_def["hex"]
                    individual_threshold = color_def.get("threshold", self.match_percentage_threshold)
                    if color_percentages.get(hex_key, 0.0) < individual_threshold:
                        logger.debug(f"RegionColorCondition '{self.name}': ALL logic FAILED for {hex_key} ({color_percentages.get(hex_key,0.0):.2f}% < {individual_threshold:.2f}%)")
                        return False
                logger.debug(f"RegionColorCondition '{self.name}': ALL logic MET for all targets.")
                return True
            elif self.condition_logic == "TOTAL_PERCENTAGE_ABOVE_THRESHOLD":
                if not self.target_colors_list: # If no targets, total is 0
                    is_met = 0.0 >= self.match_percentage_threshold
                    logger.debug(f"RegionColorCondition '{self.name}': TOTAL logic (no targets). Sum: 0.0%, Threshold: {self.match_percentage_threshold:.2f}%. Met: {is_met}")
                    return is_met
                total_percentage = sum(color_percentages.get(cd["hex"], 0.0) for cd in self.target_colors_list)
                is_met = total_percentage >= self.match_percentage_threshold
                logger.debug(f"RegionColorCondition '{self.name}': TOTAL logic. Sum: {total_percentage:.2f}%, Threshold: {self.match_percentage_threshold:.2f}%. Met: {is_met}")
                return is_met
            
            return False

        except ImportError: logger.error("RegionColorCondition: utils not available."); return False
        except Exception as e_check_region_color:
            logger.error(f"RegionColorCondition: Error during check for '{self.name}': {e_check_region_color}", exc_info=True)
            return False

    def __str__(self) -> str:
        num_targets = len(self.target_colors_list)
        first_target_hex = self.target_colors_list[0]["hex"] if num_targets > 0 else "N/A"
        logic_disp = self.condition_logic.replace("_", " ").title()
        ai_monitored_str = " (AI Monitored)" if self.is_monitored_by_ai_brain else ""
        return f"'{self.name}' (RegColors: {num_targets} tgts e.g. {first_target_hex}, Logic: {logic_disp}, Thresh: {self.match_percentage_threshold}%){ai_monitored_str}"


_CONDITION_CLASSES: Dict[str, type[Condition]] = {
    NoneCondition.TYPE: NoneCondition,
    ColorAtPositionCondition.TYPE: ColorAtPositionCondition,
    ImageOnScreenCondition.TYPE: ImageOnScreenCondition,
    TextOnScreenCondition.TYPE: TextOnScreenCondition,
    WindowExistsCondition.TYPE: WindowExistsCondition,
    ProcessExistsCondition.TYPE: ProcessExistsCondition,
    TextInRelativeRegionCondition.TYPE: TextInRelativeRegionCondition,
    RegionColorCondition.TYPE: RegionColorCondition,
    MultiImageCondition.TYPE: MultiImageCondition,
}

def create_condition(data: Optional[Dict[str, Any]]) -> Condition:
    if not isinstance(data, dict):
        logger.warning(f"create_condition received invalid data type: {type(data)}. Returning NoneCondition.")
        return NoneCondition({}, is_monitored_by_ai_brain=False)

    condition_type = data.get("type")
    params = data.get("params", {})
    condition_id = data.get("id")
    condition_name = data.get("name")
    is_monitored = bool(data.get("is_monitored_by_ai_brain", False))

    if not isinstance(condition_type, str) or not condition_type:
        logger.warning(f"create_condition: Missing or invalid 'type'. Data: {data}. Returning NoneCondition.")
        return NoneCondition(id=condition_id, name=condition_name, params=params, is_monitored_by_ai_brain=is_monitored)
    if not isinstance(params, dict):
        logger.warning(f"create_condition: 'params' is not a dict for type '{condition_type}'. Using empty dict. Data: {data}")
        params = {}

    condition_class = _CONDITION_CLASSES.get(condition_type)
    if condition_class:
        try:
            return condition_class(params=params, id=condition_id, name=condition_name, is_monitored_by_ai_brain=is_monitored)
        except ValueError as ve:
            logger.error(f"create_condition: ValueError creating Condition type '{condition_type}' (Name: {condition_name}, ID: {condition_id}): {ve}. Returning NoneCondition.")
            return NoneCondition(id=condition_id, name=f"{condition_name or 'Errored'}_INVALID", params=params, is_monitored_by_ai_brain=is_monitored)
        except Exception as e:
            logger.error(f"create_condition: Unexpected error creating Condition type '{condition_type}' (Name: {condition_name}, ID: {condition_id}): {e}", exc_info=True)
            return NoneCondition(id=condition_id, name=f"{condition_name or 'Errored'}_UNEXPECTED_ERROR", params=params, is_monitored_by_ai_brain=is_monitored)
    else:
        logger.warning(f"create_condition: Unknown condition type '{condition_type}'. Data: {data}. Returning NoneCondition.")
        return NoneCondition(id=condition_id, name=f"{condition_name or 'UnknownType'}_{condition_type}", params=params, is_monitored_by_ai_brain=is_monitored)


CONDITION_TYPE_SETTINGS: Dict[str, Dict[str, Any]] = {
    NoneCondition.TYPE: {"display_name": "Always True (No Condition)", "create_params_ui": lambda s: s._create_none_params(), "show_preview": False,},
    ColorAtPositionCondition.TYPE: {"display_name": "Color at Position", "create_params_ui": lambda s: s._create_color_at_position_params(), "show_preview": False,},
    ImageOnScreenCondition.TYPE: {"display_name": "Image on Screen", "create_params_ui": lambda s: s._create_image_on_screen_params(), "show_preview": True,},
    TextOnScreenCondition.TYPE: {"display_name": "Text on Screen", "create_params_ui": lambda s: s._create_text_on_screen_params(), "show_preview": True,},
    WindowExistsCondition.TYPE: {"display_name": "Window Exists", "create_params_ui": lambda s: s._create_window_exists_params(), "show_preview": False,},
    ProcessExistsCondition.TYPE: {"display_name": "Process Exists", "create_params_ui": lambda s: s._create_process_exists_params(), "show_preview": False,},
    TextInRelativeRegionCondition.TYPE: {"display_name": "Text near Anchor Image", "create_params_ui": lambda s: s._create_text_in_relative_region_params(), "show_preview": True,},
    MultiImageCondition.TYPE: {"display_name": "Multiple Images Pattern", "create_params_ui": lambda s: s._create_multi_image_params_ui(), "show_preview": True},
    RegionColorCondition.TYPE: {"display_name": "Color in Region (%)", "create_params_ui": lambda s: s._create_region_color_params(), "show_preview": True,},
}
ACTION_CONDITION_TYPES_INTERNAL = list(CONDITION_TYPE_SETTINGS.keys())
ACTION_CONDITION_TYPES_DISPLAY = [settings["display_name"] for settings in CONDITION_TYPE_SETTINGS.values()]
ACTION_CONDITION_DISPLAY_TO_INTERNAL_MAP = {settings["display_name"]: type_key for type_key, settings in CONDITION_TYPE_SETTINGS.items()}
