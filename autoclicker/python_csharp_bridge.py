# python_csharp_bridge.py
import json
import time
import base64
import os
import subprocess
import io
import sys
import logging
import numpy as np

logger = logging.getLogger(__name__)

_IS_WINDOWS = sys.platform == "win32"
if _IS_WINDOWS:
    try:
        import win32file
        import win32pipe
        import winerror
        import pywintypes
        _WinPipeAvailable = True
        logger.debug("Windows Named Pipe modules (pywin32) imported successfully.")
    except ImportError:
        _WinPipeAvailable = False
        logger.error("pywin32 library not found. Windows Named Pipe communication will not work.")
else:
    _WinPipeAvailable = False
    logger.warning("Named Pipe client currently implemented for Windows only.")
    class win32file: # type: ignore
        INVALID_HANDLE_VALUE = -1
        GENERIC_READ = 0
        GENERIC_WRITE = 0
        OPEN_EXISTING = 0
    class winerror: # type: ignore
        ERROR_PIPE_BUSY = 0
        ERROR_FILE_NOT_FOUND = 0
        ERROR_BROKEN_PIPE = 0
    class pywintypes: # type: ignore
        error = Exception
    class win32pipe: pass # type: ignore


try:
    import cv2
    _CV2Available = True
    logger.debug("OpenCV (cv2) imported successfully for image decoding.")
except ImportError:
    _CV2Available = False
    logger.error("OpenCV (cv2) library not found. Cannot decode captured images.")


PIPE_NAME = r'\\.\pipe\AutoClickerEnhanced_OS_Interaction_Pipe'
BUFFER_SIZE = 8192 * 4 
INITIAL_CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS_SHORT = 20 
READ_TIMEOUT_SECONDS_LONG_INTERACTIVE = 60 * 15 
RECONNECT_DELAY_SECONDS = 0.05


class OSInteractionClient:
    def __init__(self, pipe_name=PIPE_NAME):
        self.pipe_name = pipe_name
        logger.debug(f"Initialized OSInteractionClient for pipe: {self.pipe_name}")
        if not _IS_WINDOWS:
             logger.critical("OSInteractionClient currently only supports Windows due to Named Pipe implementation.")
        elif not _WinPipeAvailable:
             logger.critical("OSInteractionClient cannot function on Windows because pywin32 is not installed.")
        if not _CV2Available:
            logger.error("OpenCV is not available, image decoding will fail.")

    def _connect_to_pipe(self, timeout_seconds=INITIAL_CONNECT_TIMEOUT_SECONDS):
        if not _IS_WINDOWS or not _WinPipeAvailable:
            raise OSError("Named Pipe communication is only supported on Windows with pywin32.")

        handle = win32file.INVALID_HANDLE_VALUE
        start_time = time.monotonic()
        last_error = None
        logger.debug(f"Attempting to connect to pipe '{self.pipe_name}' with timeout {timeout_seconds}s...")

        while time.monotonic() - start_time < timeout_seconds:
            try:
                handle = win32file.CreateFile(
                    self.pipe_name,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None
                )
                if handle != win32file.INVALID_HANDLE_VALUE:
                    logger.debug(f"Successfully connected to pipe.")
                    return handle
            except pywintypes.error as e:
                last_error = e
                if e.winerror == winerror.ERROR_PIPE_BUSY or e.winerror == winerror.ERROR_FILE_NOT_FOUND:
                    time.sleep(RECONNECT_DELAY_SECONDS)
                else:
                    logger.error(f"Win32 error {e.winerror} ({e.strerror}) during pipe connection attempt.")
                    break
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during pipe connection attempt: {e}", exc_info=True)
                break

        logger.error(f"Failed to connect to pipe '{self.pipe_name}' within timeout ({timeout_seconds}s).")
        if last_error:
            logger.error(f"Last connection error: {getattr(last_error, 'winerror', 'N/A')} - {getattr(last_error, 'strerror', str(last_error))}")
        return win32file.INVALID_HANDLE_VALUE

    def _send_request(self, command: str, params: dict | None = None, response_timeout_seconds: float = READ_TIMEOUT_SECONDS_SHORT):
        if not _IS_WINDOWS or not _WinPipeAvailable:
            raise OSError("Cannot send request: Named Pipe communication not supported or pywin32 missing.")

        handle = win32file.INVALID_HANDLE_VALUE
        try:
            handle = self._connect_to_pipe()
            if handle == win32file.INVALID_HANDLE_VALUE:
                raise ConnectionRefusedError(f"Could not connect to OS Interaction Service pipe '{self.pipe_name}'.")

            request_obj = {"Command": command, "Params": params or {}}
            try:
                request_json = json.dumps(request_obj) + '\n'
                request_bytes = request_json.encode('utf-8')
            except TypeError as json_err:
                 logger.error(f"Failed to serialize request object to JSON for command '{command}': {json_err}. Params: {params}")
                 raise ValueError(f"Cannot serialize request parameters for command '{command}'.") from json_err

            logger.debug(f"PIPE OUT -> {request_json.strip()}")
            try:
                 _, bytes_written = win32file.WriteFile(handle, request_bytes)
                 win32file.FlushFileBuffers(handle)
                 logger.debug(f"Wrote {bytes_written} bytes.")
            except pywintypes.error as write_ex:
                 if write_ex.winerror == winerror.ERROR_BROKEN_PIPE or getattr(write_ex, 'winerror', 0) == 232: # ERROR_NO_DATA might be 232
                      raise ConnectionAbortedError(f"Pipe closed by server during write: {write_ex.strerror}") from write_ex
                 raise IOError(f"Win32 error during pipe write: {write_ex.winerror} - {write_ex.strerror}") from write_ex
            except Exception as write_ex:
                 raise IOError(f"Unexpected error during pipe write: {write_ex}") from write_ex

            response_buffer = bytearray()
            start_time = time.monotonic()
            response_json_line = None

            while time.monotonic() - start_time < response_timeout_seconds:
                try:
                    hr, data_read = win32file.ReadFile(handle, BUFFER_SIZE)
                    if not data_read:
                        if response_buffer:
                             logger.warning("Pipe closed by server or read returned 0 bytes, but buffer has data. Attempting to process.")
                             break
                        else:
                             logger.warning("Pipe closed by server or read returned 0 bytes with empty buffer.")
                             raise ConnectionAbortedError("Pipe closed by server during read.")

                    response_buffer.extend(data_read)
                    newline_index = response_buffer.find(b'\n')
                    if newline_index != -1:
                        response_line_bytes = response_buffer[:newline_index]
                        response_buffer = response_buffer[newline_index + 1:]
                        try:
                            response_json_line = response_line_bytes.decode('utf-8')
                            logger.debug(f"PIPE IN <- {response_json_line.strip()}")
                            break
                        except UnicodeDecodeError as decode_err:
                            logger.error(f"Failed to decode response bytes: {decode_err}. Bytes: {response_line_bytes!r}")
                            raise ValueError("Received invalid UTF-8 data from C# service.") from decode_err
                except pywintypes.error as read_ex:
                    if read_ex.winerror == winerror.ERROR_BROKEN_PIPE or getattr(read_ex, 'winerror', 0) == 109: 
                        raise ConnectionAbortedError(f"Pipe broken or not connected during read: {read_ex.strerror}") from read_ex
                    raise IOError(f"Win32 error during pipe read: {read_ex.winerror} - {read_ex.strerror}") from read_ex
                except Exception as read_ex:
                     raise IOError(f"Unexpected error during pipe read loop: {read_ex}") from read_ex

            if response_json_line:
                try:
                    response = json.loads(response_json_line)
                    status = response.get("Status")
                    message = response.get("Message", "No message.")
                    result = response.get("Result") 

                    if status == "Success":
                        return result
                    elif status == "Error":
                        logger.error(f"C# Service Error for command '{command}': {message}")
                        raise RuntimeError(f"C# Service Error: {message}")
                    else:
                        logger.error(f"Received unexpected status '{status}' from C# service for command '{command}'. Message: {message}")
                        raise ValueError(f"Unexpected status '{status}' from C# service.")
                except json.JSONDecodeError as json_err: 
                    logger.error(f"Failed to parse JSON response envelope from C# service: {json_err}. Response: {response_json_line}")
                    raise ValueError(f"Invalid JSON response envelope received from C# service.") from json_err
            else:
                if response_buffer:
                     partial_response_str = response_buffer.decode('utf-8', errors='replace')
                     logger.error(f"Read timeout ({response_timeout_seconds}s) for command '{command}'. Received incomplete message (no newline): {partial_response_str!r}")
                     raise TimeoutError(f"Timeout waiting for complete response (no newline). Partial data: {partial_response_str[:100]}...")
                else:
                     logger.error(f"Read timeout ({response_timeout_seconds}s) for command '{command}'. No data received.")
                     raise TimeoutError(f"Timeout waiting for response from C# service. No data received.")

        except (ConnectionRefusedError, ConnectionAbortedError, IOError, TimeoutError, ValueError, RuntimeError) as e:
            logger.error(f"Pipe/Service Error for command '{command}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in _send_request for command '{command}': {e}", exc_info=True)
            raise RuntimeError(f"Unexpected bridge error for command '{command}'.") from e
        finally:
            if handle != win32file.INVALID_HANDLE_VALUE:
                try:
                    win32file.CloseHandle(handle)
                except Exception as close_ex:
                    logger.error(f"Error closing Win32 pipe handle: {close_ex}", exc_info=True)
        return None 

    def capture_region(self, x1: int, y1: int, x2: int, y2: int,
                       useGrayscale: bool = False, useBinarization: bool = False) -> dict:
        if not _CV2Available: raise RuntimeError("OpenCV (cv2) is required for capture_region response decoding.")
        params = {
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "useGrayscale": useGrayscale,
            "useBinarization": useBinarization,
        }
        result = self._send_request("CaptureRegion", params) 

        if isinstance(result, dict) and result.get("captured_image_bytes") is not None:
            try:
                image_bytes_base64 = result["captured_image_bytes"]
                image_bytes = base64.b64decode(image_bytes_base64)
                img_np = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
                if img_np is None:
                    raise ValueError("Invalid image data received (cv2.imdecode returned None).")

                actual_x1 = result.get("actual_x1", x1)
                actual_y1 = result.get("actual_y1", y1)
                actual_x2 = result.get("actual_x2", x2)
                actual_y2 = result.get("actual_y2", y2)
                if actual_x2 < actual_x1: actual_x2 = actual_x1
                if actual_y2 < actual_y1: actual_y2 = actual_y1

                logger.debug(f"CaptureRegion success. Shape: {img_np.shape}, Actual Bounds: ({actual_x1},{actual_y1})-({actual_x2},{actual_y2})")
                return {"image_np": img_np, "x1": actual_x1, "y1": actual_y1, "x2": actual_x2, "y2": actual_y2}
            except (TypeError, ValueError, base64.binascii.Error) as decode_err:
                 logger.error(f"Failed to decode Base64 image data from C# service: {decode_err}")
                 raise IOError("Failed to decode image data from C# service.") from decode_err
            except cv2.error as cv_err:
                 logger.error(f"OpenCV error decoding image from C# service: {cv_err}")
                 raise IOError("Failed to decode image data using OpenCV.") from cv_err
            except Exception as proc_err:
                 logger.error(f"Unexpected error processing image response from C# CaptureRegion: {proc_err}", exc_info=True)
                 raise IOError("Failed to process image response from C# service.") from proc_err
        else:
             logger.error(f"Invalid or incomplete result received from C# CaptureRegion: {result}")
             raise ValueError("Invalid or incomplete result from C# CaptureRegion (missing 'captured_image_bytes').")

    def get_pixel_color(self, x: int, y: int) -> str:
        params = {"x": x, "y": y}
        result = self._send_request("GetPixelColor", params) 
        if isinstance(result, dict) and result.get("color_hex") is not None:
             color = str(result["color_hex"])
             logger.debug(f"GetPixelColor ({x},{y}) -> {color}")
             return color
        logger.error(f"Invalid or incomplete result received from C# GetPixelColor: {result}")
        raise ValueError("Invalid or incomplete result from C# GetPixelColor (missing 'color_hex').")

    def simulate_click(self, x: int, y: int, button: str = "left", click_type: str = "single", hold_duration: float = 0.0):
        params = {"x": x, "y": y, "button": button, "click_type": click_type, "hold_duration": hold_duration}
        self._send_request("SimulateClick", params)
        logger.debug(f"Sent SimulateClick: ({x},{y}), Btn={button}, Type={click_type}, Hold={hold_duration}s")

    def simulate_move_mouse(self, x: int, y: int, duration: float = 0.1):
        params = {"x": x, "y": y, "duration": duration}
        self._send_request("SimulateMouseMove", params)
        logger.debug(f"Sent SimulateMouseMove: To=({x},{y}), Dur={duration}s")

    def simulate_drag(self, end_x: int, end_y: int, button: str = "left", duration_seconds: float = 0.1):
        params = {"end_x": end_x, "end_y": end_y, "button": button, "duration_seconds": duration_seconds}
        self._send_request("SimulateDrag", params)
        logger.debug(f"Sent SimulateDrag: To=({end_x},{end_y}), Btn={button}, Dur={duration_seconds}s")

    def simulate_scroll(self, scroll_amount: int, direction: str = "vertical"):
        params = {"scroll_amount": scroll_amount, "direction": direction}
        self._send_request("SimulateScroll", params)
        logger.debug(f"Sent SimulateScroll: Amount={scroll_amount}, Dir={direction}")

    def simulate_key_press(self, key_name: str):
        if not key_name: raise ValueError("Key name for simulate_key_press cannot be empty.")
        params = {"key_name": key_name}
        self._send_request("SimulateKeyPress", params)
        logger.debug(f"Sent SimulateKeyPress: Key='{key_name}'")

    def simulate_key_down(self, key_name: str):
        if not key_name: raise ValueError("Key name for simulate_key_down cannot be empty.")
        params = {"key_name": key_name}
        self._send_request("SimulateKeyDown", params)
        logger.debug(f"Sent SimulateKeyDown: Key='{key_name}'")

    def simulate_key_up(self, key_name: str):
        if not key_name: raise ValueError("Key name for simulate_key_up cannot be empty.")
        params = {"key_name": key_name}
        self._send_request("SimulateKeyUp", params)
        logger.debug(f"Sent SimulateKeyUp: Key='{key_name}'")

    def simulate_text_entry(self, text: str):
        params = {"text": text if isinstance(text, str) else ""}
        self._send_request("SimulateTextEntry", params)
        logger.debug(f"Sent SimulateTextEntry: Text='{text[:50]}{'...' if len(text)>50 else ''}'")

    def simulate_modified_key_stroke(self, modifier: str, main_key: str):
        if not modifier or not main_key: raise ValueError("Modifier and main_key cannot be empty.")
        params = {"modifier": modifier, "main_key": main_key}
        self._send_request("SimulateModifiedKeyStroke", params)
        logger.debug(f"Sent SimulateModifiedKeyStroke: Mod='{modifier}', Key='{main_key}'")

    def get_screen_size(self) -> tuple[int, int]:
         result = self._send_request("GetScreenSize") 
         if isinstance(result, dict) and result.get("width") is not None and result.get("height") is not None:
              try:
                  width = int(result["width"])
                  height = int(result["height"])
                  logger.debug(f"GetScreenSize -> ({width},{height})")
                  return (width, height)
              except (ValueError, TypeError) as e:
                   logger.error(f"C# GetScreenSize returned non-integer size: {result}")
                   raise ValueError(f"C# GetScreenSize returned non-integer size: {result}") from e
         logger.error(f"Invalid or incomplete result received from C# GetScreenSize: {result}")
         raise ValueError("Invalid or incomplete result from C# GetScreenSize (missing width/height).")

    def ping(self) -> dict:
        result = self._send_request("Ping") 
        if isinstance(result, dict) and result.get("message") is not None and result.get("pid") is not None:
             try:
                 pid = int(result["pid"])
                 message = str(result["message"])
                 logger.debug(f"Ping -> Msg='{message}', PID={pid}")
                 return {"message": message, "pid": pid}
             except (ValueError, TypeError) as e:
                 logger.error(f"C# Ping returned unexpected format: {result}")
                 raise ValueError(f"C# Ping returned unexpected format: {result}") from e
        logger.error(f"Invalid or incomplete result received from C# Ping: {result}")
        raise ValueError("Invalid or incomplete result from C# Ping (missing message/pid).")

    def check_window_exists(self, window_title: str | None = None, class_name: str | None = None) -> bool:
        if not window_title and not class_name:
            logger.warning("check_window_exists called with no title or class name.")
            return False
        params = {"window_title": window_title, "class_name": class_name}
        result = self._send_request("CheckWindowExists", params) 
        if isinstance(result, dict) and isinstance(result.get("exists"), bool):
            exists = result["exists"]
            logger.debug(f"CheckWindowExists (Title='{window_title or '*'}', Class='{class_name or '*'}') -> {exists}")
            return exists
        logger.error(f"Invalid or incomplete result received from C# CheckWindowExists: {result}")
        return False

    def check_process_exists(self, process_name: str) -> bool:
        if not process_name:
            logger.warning("check_process_exists called with empty process name.")
            return False
        params = {"process_name": process_name}
        result = self._send_request("CheckProcessExists", params) 
        if isinstance(result, dict) and isinstance(result.get("exists"), bool):
            exists = result["exists"]
            logger.debug(f"CheckProcessExists (Name='{process_name}') -> {exists}")
            return exists
        logger.error(f"Invalid or incomplete result received from C# CheckProcessExists: {result}")
        return False

    def start_interactive_drawing_capture(self) -> list[list[dict[str, int]]] | None:
        """Initiates interactive drawing capture via C# and waits for the result."""
        logger.info("Requesting C# service to start interactive drawing capture...")
        result_from_send_request = self._send_request("StartInteractiveDrawingCapture", response_timeout_seconds=READ_TIMEOUT_SECONDS_LONG_INTERACTIVE)

        if result_from_send_request is None:
            logger.info("Interactive drawing capture cancelled or no data returned from C#.")
            return None

        if isinstance(result_from_send_request, list):
            if all(isinstance(stroke, list) for stroke in result_from_send_request):
                if all(all(isinstance(point, dict) and 'x' in point and 'y' in point for point in stroke) for stroke in result_from_send_request if stroke): # check if stroke is not empty before iterating points
                    logger.info(f"Interactive drawing capture successful. Received {len(result_from_send_request)} strokes.")
                    return result_from_send_request
            logger.error(f"Parsed drawing data has incorrect structure: {result_from_send_request}")
            return None
        else:
             logger.error(f"Unexpected drawing capture result type from C#: {type(result_from_send_request)}. Data: {result_from_send_request}")
             return None

    def start_interactive_region_select(self) -> dict | None:
        """Initiates interactive region selection via C# and waits for the result."""
        logger.info("Requesting C# service to start interactive region selection...")
        result_from_send_request = self._send_request("StartInteractiveRegionSelect", response_timeout_seconds=READ_TIMEOUT_SECONDS_LONG_INTERACTIVE)

        if result_from_send_request is None:
            logger.info("Interactive region selection cancelled or no data returned from C#.")
            return None

        if isinstance(result_from_send_request, dict) and \
           all(k in result_from_send_request for k in ["x1", "y1", "x2", "y2"]) and \
           result_from_send_request.get("image_base64") is not None:
            try:
                x1 = int(result_from_send_request["x1"])
                y1 = int(result_from_send_request["y1"])
                x2 = int(result_from_send_request["x2"])
                y2 = int(result_from_send_request["y2"])
                image_bytes_base64 = result_from_send_request["image_base64"]
                if not _CV2Available:
                     logger.error("OpenCV not available to decode region image.")
                     return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "image_np": None}

                image_bytes = base64.b64decode(image_bytes_base64)
                img_np = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
                if img_np is None:
                    logger.error("Failed to decode region image from C# (cv2.imdecode returned None).")
                    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "image_np": None}

                logger.info(f"Interactive region selection successful. Region: ({x1},{y1})-({x2},{y2}), Image shape: {img_np.shape}")
                return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "image_np": img_np}
            except (TypeError, ValueError, base64.binascii.Error, cv2.error) as e:
                logger.error(f"Error processing region selection result from C#: {e}")
                return None
        else:
            logger.error(f"Invalid or incomplete result from C# StartInteractiveRegionSelect: {result_from_send_request}")
            return None

    def start_interactive_point_select(self, num_points: int = 1) -> list[dict[str, int]] | None:
        """Initiates interactive point selection via C# and waits for the result."""
        logger.info(f"Requesting C# service to start interactive point selection for {num_points} point(s)...")
        params = {"num_points": num_points}
        result_from_send_request = self._send_request("StartInteractivePointSelect", params=params, response_timeout_seconds=READ_TIMEOUT_SECONDS_LONG_INTERACTIVE)

        if result_from_send_request is None:
            logger.info("Interactive point selection cancelled or no data returned from C#.")
            return None
        if isinstance(result_from_send_request, list):
             if all(isinstance(point, dict) and 'x' in point and 'y' in point for point in result_from_send_request):
                 try:
                     validated_points = [{"x": int(p["x"]), "y": int(p["y"])} for p in result_from_send_request]
                     logger.info(f"Interactive point selection successful. Received {len(validated_points)} points.")
                     return validated_points
                 except (ValueError, TypeError, KeyError) as e:
                     logger.error(f"Error converting point data to integers: {e}. Data: {result_from_send_request}")
                     return None
             logger.error(f"Parsed point data has incorrect structure: {result_from_send_request}")
             return None
        else:
             logger.error(f"Unexpected point selection result type at final check: {type(result_from_send_request)}. Data: {result_from_send_request}")
             return None

os_interaction_client = OSInteractionClient()


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.DEBUG)
#     logger.info("--- OSInteractionClient Test (with Interactive Capture) ---")

#     if not _IS_WINDOWS or not _WinPipeAvailable:
#         logger.error("Cannot run test: Windows Named Pipes require pywin32 on Windows.")
#         sys.exit(1)

#     csharp_exe_path = os.path.join("..", "sever", "bin", "Debug", "net9.0-windows", "sever.exe") # Adjust if needed
#     csharp_process = None
#     if os.path.exists(csharp_exe_path):
#         try:
#              logger.info(f"Starting C# service for testing: {csharp_exe_path}")
#              creation_flags = 0x08000000 if _IS_WINDOWS else 0
#              csharp_process = subprocess.Popen([csharp_exe_path], creationflags=creation_flags, cwd=os.path.dirname(csharp_exe_path))
#              logger.info(f"C# service process started (PID: {csharp_process.pid}). Waiting a moment...")
#              time.sleep(2)
#         except Exception as start_ex:
#              logger.error(f"Failed to start C# service for testing: {start_ex}", exc_info=True)
#              csharp_process = None
#     else:
#         logger.warning(f"C# executable not found at '{csharp_exe_path}'. Skipping tests that require the service.")

#     test_client_interactive = os_interaction_client

#     if csharp_process:
#         try:
#             print("\nTesting Ping...")
#             try: print(f"Ping: {test_client_interactive.ping()}")
#             except Exception as e: print(f"Ping failed: {e}")

#             print("\nTesting Interactive Drawing Capture (Press Esc in C# window to cancel/finish)...")
#             try:
#                 drawing_data = test_client_interactive.start_interactive_drawing_capture()
#                 if drawing_data is not None:
#                     print(f"Drawing data received: {len(drawing_data)} strokes.")
#                     for i, stroke in enumerate(drawing_data):
#                         print(f"  Stroke {i+1}: {stroke[:3]}{'...' if len(stroke)>3 else ''}")
#                 else:
#                     print("Drawing capture cancelled or returned no data.")
#             except Exception as e: print(f"Interactive Drawing Capture failed: {e}")

#             print("\nTesting Interactive Region Select (Drag a rectangle, Esc to cancel)...")
#             try:
#                 region_data = test_client_interactive.start_interactive_region_select()
#                 if region_data:
#                     print(f"Region selected: ({region_data.get('x1')},{region_data.get('y1')})-({region_data.get('x2')},{region_data.get('y2')})")
#                     if region_data.get("image_np") is not None:
#                         print(f"  Image captured, shape: {region_data['image_np'].shape}")
#                         if _CV2Available:
#                             pass 
#                     else:
#                         print("  No image data returned with region.")
#                 else:
#                     print("Region selection cancelled or returned no data.")
#             except Exception as e: print(f"Interactive Region Select failed: {e}")

#             print("\nTesting Interactive Point Select (Click 2 points, Esc to cancel)...")
#             try:
#                 points_data = test_client_interactive.start_interactive_point_select(num_points=2)
#                 if points_data:
#                     print(f"Points selected: {points_data}")
#                 else:
#                     print("Point selection cancelled or returned no data.")
#             except Exception as e: print(f"Interactive Point Select failed: {e}")

#         finally:
#             if csharp_process and csharp_process.poll() is None:
#                 logger.info(f"Terminating C# service process (PID: {csharp_process.pid})...")
#                 try:
#                     csharp_process.terminate()
#                     csharp_process.wait(timeout=3)
#                 except subprocess.TimeoutExpired: csharp_process.kill()
#                 except Exception as term_ex: logger.error(f"Error stopping C# service: {term_ex}")
#                 logger.info("C# service stopped.")
#     else:
#         logger.warning("C# service process not started. Skipping interactive tests.")

#     logger.info("--- OSInteractionClient Interactive Test Finished ---")
