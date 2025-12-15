# utils/image_processing.py
import logging
import cv2 
import numpy as np
from .parsing_utils import parse_tuple_str 

logger = logging.getLogger(__name__)

DEFAULT_GAUSSIAN_KERNEL = (3, 3)
DEFAULT_MEDIAN_KERNEL = 3
DEFAULT_CLAHE_CLIP_LIMIT = 2.0
DEFAULT_CLAHE_TILE_SIZE = (8, 8)
DEFAULT_BILATERAL_D = 9
DEFAULT_BILATERAL_SIGMA = 75
DEFAULT_CANNY_T1 = 50
DEFAULT_CANNY_T2 = 150

def preprocess_for_image_matching(image_np: np.ndarray | None, pp_params: dict) -> np.ndarray | None:
    """
    Apply a configurable preprocessing procedure suitable for image matching.
    (Template Matching, Feature Matching).
    
    Args:
        image_np: Input image as a NumPy array (BGR, BGRA, or Grayscale). Can be None.
        pp_params: A dictionary containing preprocessor parameters such as:  
        'grayscale': bool (default: True)
        'binarization': bool (default: False - use Otsu)
        'gaussian_blur': bool (default: False)
        'gaussian_blur_kernel': str (e.g., "3,3")
        'median_blur': bool (default: False)
        'median_blur_kernel': int (e.g., 3)
        'clahe': bool (default: False)
        'clahe_clip_limit': float (e.g., 2.0)
        'clahe_tile_grid_size': str (e.g., "8,8")
        'bilateral_filter': bool (default: False)
        'bilateral_d': int (e.g., 9)
        'bilateral_sigma_color': float (e.g., 75)
        'bilateral_sigma_space': float (e.g., 75)
        'canny_edges': bool (default: False)
        'canny_threshold1': float (e.g., 50)
        'canny_threshold2': float (e.g., 150)
    Returns:
    Preprocessed image as a NumPy array, or original image if no
    processing applied or possible, or None if input is invalid.
    
    """
    if image_np is None or not isinstance(image_np, np.ndarray) or image_np.size == 0:
    logger.warning("preprocess_for_image_matching received an invalid input image.")
        return None

    try:
        processed = image_np.copy()
        logger.debug(f"Image Matching Preprocessing Start. Input shape: {processed.shape}")

        use_grayscale = pp_params.get('grayscale', True) 
        is_gray = False
        if use_grayscale:
            if processed.ndim == 3:
                try:
                    code = cv2.COLOR_BGRA2GRAY if processed.shape[2] == 4 else cv2.COLOR_BGR2GRAY
                    processed = cv2.cvtColor(processed, code)
                    is_gray = True
                    logger.debug("Applied Grayscale")
                except cv2.error as e:
                    logger.warning(f"Grayscale conversion error: {e}. Continue with the original image if possible.")
            elif processed.ndim == 2:
                is_gray = True 
                logger.debug("Input image is already grayscale.")

        can_do_2d_filtering = is_gray
        if not can_do_2d_filtering and (pp_params.get('gaussian_blur', False) or
                                      pp_params.get('median_blur', False) or
                                      pp_params.get('clahe', False) or
                                      pp_params.get('canny_edges', False) or
                                      pp_params.get('binarization', False)):
            logger.warning("Cannot apply 2D filters/processing because the image is not grayscale.")

        try:
            if can_do_2d_filtering and pp_params.get('gaussian_blur', False):
                kernel_str = pp_params.get('gaussian_blur_kernel', "3,3")
                kernel = parse_tuple_str(kernel_str, 2, int) or DEFAULT_GAUSSIAN_KERNEL
                if all(k > 0 and k % 2 == 1 for k in kernel):
                    processed = cv2.GaussianBlur(processed, kernel, 0)
                    logger.debug(f"Applied Gaussian Blur (Kernel: {kernel})")
                else:
                    logger.warning(f"Invalid Gaussian kernel '{kernel_str}', skip the blurring step.")

            if can_do_2d_filtering and pp_params.get('median_blur', False):
                kernel_size = pp_params.get('median_blur_kernel', DEFAULT_MEDIAN_KERNEL)
                if kernel_size > 0 and kernel_size % 2 == 1:
                    if processed.shape[0] > kernel_size and processed.shape[1] > kernel_size:
                        processed = cv2.medianBlur(processed, kernel_size)
                        logger.debug(f"Applied Median Blur (Kernel: {kernel_size})")
                    else:
                        logger.warning(f"Invalid Gaussian kernel '{kernel_str}', skip the blurring step.")
                else:
                    logger.warning(f"Invalid kernel media size {kernel_size}, skip the blurring step.")

            if pp_params.get('bilateral_filter', False):
                d = pp_params.get('bilateral_d', DEFAULT_BILATERAL_D)
                sc = pp_params.get('bilateral_sigma_color', DEFAULT_BILATERAL_SIGMA)
                ss = pp_params.get('bilateral_sigma_space', DEFAULT_BILATERAL_SIGMA)
                processed = cv2.bilateralFilter(processed, d, sc, ss)
                logger.debug(f"Applied Bilateral Filter (d={d}, sc={sc}, ss={ss})")

        except cv2.error as e: logger.warning(f"Blurring/Filtering step failed: {e}")
        except Exception as e: logger.error(f"Unexpected error during blurring: {e}", exc_info=True)

        try:
            if can_do_2d_filtering and pp_params.get('clahe', False):
                clip = pp_params.get('clahe_clip_limit', DEFAULT_CLAHE_CLIP_LIMIT)
                tile_str = pp_params.get('clahe_tile_grid_size', "8,8")
                tile = parse_tuple_str(tile_str, 2, int) or DEFAULT_CLAHE_TILE_SIZE
                if all(s > 0 for s in tile):
                    clahe_obj = cv2.createCLAHE(clipLimit=clip, tileGridSize=tile)
                    processed = clahe_obj.apply(processed)
                    logger.debug(f"Applied CLAHE (Clip: {clip}, Tile: {tile})")
                else:
                    logger.warning(f"Invalid tile size CLAHE '{tile_str}', skip CLAHE.")
            except cv2.error as e: logger.warning(f"CLAHE failed: {e}")
            except Exception as e: logger.error(f"Unexpected error during CLAHE: {e}", exc_info=True)

        use_canny = False 
        try:
            if can_do_2d_filtering and pp_params.get('canny_edges', False):
                t1 = pp_params.get('canny_threshold1', DEFAULT_CANNY_T1)
                t2 = pp_params.get('canny_threshold2', DEFAULT_CANNY_T2)
                processed = cv2.Canny(processed, t1, t2)
                use_canny = True 
                logger.debug(f"Applied Canny Edges (T1: {t1}, T2: {t2})")
        except cv2.error as e: logger.warning(f"Canny edge detection failed: {e}")
        except Exception as e: logger.error(f"Unexpected error during Canny process: {e}", exc_info=True)

        try:
            if can_do_2d_filtering and pp_params.get('binarization', False) and not use_canny:
                _, processed = cv2.threshold(processed, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                logger.debug("Applied Otsu Binarization")
        except cv2.error as e: logger.warning(f"Binization failed: {e}")
        except Exception as e: logger.error(f"Unexpected error during binization: {e}", exc_info=True)

        logger.debug(f"Image Matching Preprocessing End. Output shape: {processed.shape}")
        return processed

    except Exception as main_ex:
        logger.error(f"Unexpected error in preprocess_for_image_matching: {main_ex}", exc_info=True)
        return image_np 

def preprocess_for_ocr(image_np: np.ndarray | None, pp_params: dict) -> np.ndarray | None:
    """
    Apply a configurable preprocessing procedure optimized for OCR.

    Args:
        image_np: Input image as a NumPy array (BGR, BGRA, or Grayscale). Can be None.
        pp_params: A dictionary containing preprocessor parameters such as:
        'grayscale': bool (default: True)
        'adaptive_threshold': bool (default: True) # Prioritize adaptive threshold
        'binarization': bool (default: False) # Use only if adaptive_threshold is False
        'ocr_upscale_factor': float (default: 1.0)
        'median_blur': bool (default: True)
        'median_blur_kernel': int (e.g., 3)
        'gaussian_blur': bool (default: False)
        'gaussian_blur_kernel': str (e.g., "3,3")
        'clahe': bool (default: False)
        'clahe_clip_limit': float (e.g., 2.0)
        'clahe_tile_grid_size': str (e.g., "8,8")
        'bilateral_filter': bool (default: False)
        # ... other bilateral parameters if used for OCR ...
    Returns:
        The image is pre-processed as a NumPy array, or the original image if no processing is applied or possible, or None if the input is invalid.
    """
    if image_np is None or not isinstance(image_np, np.ndarray) or image_np.size == 0:
        logger.warning("preprocess_for_ocr received an invalid input image.")
        return None

    try:
        processed = image_np.copy()
        logger.debug(f"OCR Preprocessing Start. Input shape: {processed.shape}")

        try:
            upscale_factor = pp_params.get('ocr_upscale_factor', 1.0)
            try:
                upscale_factor = float(upscale_factor)
            except (ValueError, TypeError):
                logger.warning(f"ocr_upscale_factor is invalid '{pp_params.get('ocr_upscale_factor')}', use 1.0.")
                upscale_factor = 1.0

            if upscale_factor > 1.0:
                    new_width = int(processed.shape[1] * upscale_factor)
                    new_height = int(processed.shape[0] * upscale_factor)
                    processed = cv2.resize(processed, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
                    logger.debug(f"Applied Upscaling (Factor: {upscale_factor:.2f}), New shape: {processed.shape}")
        except cv2.error as e: logger.warning(f"Upscaling failed: {e}")
        except Exception as e: logger.error(f"Unexpected error during Upscaling: {e}", exc_info=True)

        use_grayscale = pp_params.get('grayscale', True) 
        is_gray = False
        if use_grayscale or processed.ndim != 2:
            if processed.ndim == 3:
                try:
                    code = cv2.COLOR_BGRA2GRAY if processed.shape[2] == 4 else cv2.COLOR_BGR2GRAY
                    processed = cv2.cvtColor(processed, code)
                    is_gray = True
                    logger.debug("Applied Grayscale for OCR")
                except cv2.error as e:
                    logger.warning(f"Grayscale conversion error for OCR: {e}. Continue with the original image if possible.")
            elif processed.ndim == 2:
                 is_gray = True
                 logger.debug("Input image is already grayscale for OCR.")
            else:
                logger.warning(f"Cannot apply OCR preprocessing, image format is incompatible (ndim={processed.ndim}).")
                return processed 
        if not is_gray:
             logger.warning("Image not Grayscale after conversion attempt, skipping subsequent OCR preprocessing steps.")
             return processed

        try:
            if pp_params.get('gaussian_blur', False): 
                kernel_str = pp_params.get('gaussian_blur_kernel', "3,3")
                kernel = parse_tuple_str(kernel_str, 2, int) or DEFAULT_GAUSSIAN_KERNEL
                if all(k > 0 and k % 2 == 1 for k in kernel):
                    processed = cv2.GaussianBlur(processed, kernel, 0)
                    logger.debug(f"Applied Gaussian Blur (Kernel: {kernel}) for OCR")
                else: logger.warning(f"Invalid Gaussian kernel '{kernel_str}', ignore blur for OCR.")

            if pp_params.get('median_blur', True): 
                kernel_size = pp_params.get('median_blur_kernel', DEFAULT_MEDIAN_KERNEL)
                if kernel_size > 0 and kernel_size % 2 == 1:
                    if processed.shape[0] > kernel_size and processed.shape[1] > kernel_size:
                        processed = cv2.medianBlur(processed, kernel_size)
                        logger.debug(f"Applied Median Blur (Kernel: {kernel_size}) for OCR")
                    else: logger.warning(f"Image size is smaller than kernel median({kernel_size}), ignore blur for OCR.")
                else: logger.warning(f"Invalid kernel median size {kernel_size}, ignore blur for OCR.")

            if pp_params.get('bilateral_filter', False):
                d = pp_params.get('bilateral_d', 5) 
                sc = pp_params.get('bilateral_sigma_color', DEFAULT_BILATERAL_SIGMA)
                ss = pp_params.get('bilateral_sigma_space', DEFAULT_BILATERAL_SIGMA)
                processed = cv2.bilateralFilter(processed, d, sc, ss)
                logger.debug(f"Applied Bilateral Filter (d={d}, sc={sc}, ss={ss}) for OCR")

        except cv2.error as e: logger.warning(f"OCR blurring step failed: {e}")
        except Exception as e: logger.error(f"Unexpected error during OCR blurring: {e}", exc_info=True)

        try:
            if pp_params.get('clahe', False): 
                clip = pp_params.get('clahe_clip_limit', DEFAULT_CLAHE_CLIP_LIMIT)
                tile_str = pp_params.get('clahe_tile_grid_size', "8,8")
                tile = parse_tuple_str(tile_str, 2, int) or DEFAULT_CLAHE_TILE_SIZE
                if all(s > 0 for s in tile):
                    clahe_obj = cv2.createCLAHE(clipLimit=clip, tileGridSize=tile)
                    processed = clahe_obj.apply(processed)
                    logger.debug(f"Applied CLAHE (Clip: {clip}, Tile: {tile}) for OCR")
                else: logger.warning(f"Invalid tile size '{tile_str}', skip CLAHE for OCR.")
            except cv2.error as e: logger.warning(f"CLAHE for OCR failed: {e}")
            except Exception as e: logger.error(f"Unexpected error during CLAHE OCR: {e}", exc_info=True)

        try:
            if pp_params.get('adaptive_threshold', True): 
                 block_size = 21 
                 C = 9 
                 processed = cv2.adaptiveThreshold(processed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                   cv2.THRESH_BINARY, block_size, C)
                 logger.debug("Applied Adaptive Threshold (Gaussian) for OCR")
            elif pp_params.get('binarization', False): 
                 _, processed = cv2.threshold(processed, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                 logger.debug("Applied Otsu Binarization for OCR")
        except cv2.error as e: logger.warning(f"Thresholding for OCR failed: {e}")
        except Exception as e: logger.error(f"Unexpected error during Thresholding OCR: {e}", exc_info=True)

        logger.debug(f"OCR Preprocessing End. Output shape: {processed.shape}")
        return processed

    except Exception as main_ex:
        logger.error(f"Unexpected error in preprocess_for_ocr: {main_ex}", exc_info=True)
        return image_np 
