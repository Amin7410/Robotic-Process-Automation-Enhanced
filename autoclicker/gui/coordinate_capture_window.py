# gui/coordinate_capture_window.py
import tkinter as tk
from tkinter import messagebox
import logging
from tkinter import ttk 
from typing import Callable, Optional, List, Dict, Any, Tuple
import threading 

logger = logging.getLogger(__name__)

try:
    from python_csharp_bridge import os_interaction_client
    _BridgeImported_CCW = True
    logger.debug("CoordinateCaptureWindow: OSInteractionClient imported.")
except ImportError:
    logger.error("CoordinateCaptureWindow: Could not import os_interaction_client. Point capture will fail.")
    _BridgeImported_CCW = False
    class DummyOSInteractionClient:
        def start_interactive_point_select(self, num_points: int = 1) -> Optional[List[Dict[str, int]]]:
            logger.error("DummyOSInteractionClient: start_interactive_point_select called.")

            return None
    os_interaction_client = DummyOSInteractionClient()


class CoordinateCaptureWindow:
    def __init__(self, master: tk.Tk | tk.Toplevel,
                 callback: Callable[[Optional[List[Dict[str, int]] | Tuple[int, int] | Tuple[Tuple[int,int], Tuple[int,int]]]], None],
                 num_points: int = 1):

        self.master_window = master
        self.callback = callback
        self.num_points_to_capture = num_points

        logger.debug(f"CoordinateCaptureWindow: Initializing (will start C# call for {num_points} point(s) in a new thread).")

        self._disable_master_window(True)

        self.capture_thread = threading.Thread(target=self._initiate_csharp_point_select_threaded, daemon=True)
        self.capture_thread.start()

    def _disable_master_window(self, disable: bool):
        try:
            if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                if hasattr(self.master_window, 'attributes'):
                    self.master_window.attributes("-disabled", disable)
        except tk.TclError:
            logger.warning("CoordinateCaptureWindow: TclError trying to change master window state.")
        except Exception as e:
            logger.error(f"CoordinateCaptureWindow: Error changing master window state: {e}")

    def _initiate_csharp_point_select_threaded(self):
        captured_points_list: Optional[List[Dict[str, int]]] = None
        error_message_for_user: Optional[str] = None

        if not _BridgeImported_CCW:
            logger.error("CoordinateCaptureWindow (Thread): Cannot initiate point selection, bridge not imported.")
            error_message_for_user = "OS Interaction service bridge is not available.\nPoint selection cannot proceed."
        else:
            try:
                logger.info(f"CoordinateCaptureWindow (Thread): Calling C# service for {self.num_points_to_capture} point(s)...")
                captured_points_list = os_interaction_client.start_interactive_point_select(num_points=self.num_points_to_capture)

                if captured_points_list:
                    logger.info(f"CoordinateCaptureWindow (Thread): Point data received from C#: {captured_points_list}")
                else:
                    logger.info("CoordinateCaptureWindow (Thread): Point selection cancelled or no data returned from C#.")

            except TimeoutError as te:
                logger.error(f"CoordinateCaptureWindow (Thread): Timeout: {te}")
                error_message_for_user = "Point selection timed out."
            except ConnectionRefusedError as cre:
                logger.error(f"CoordinateCaptureWindow (Thread): Connection refused: {cre}")
                error_message_for_user = "Could not connect to the OS Interaction Service."
            except Exception as e:
                logger.error(f"CoordinateCaptureWindow (Thread): Error during C# call: {e}", exc_info=True)
                error_message_for_user = f"An unexpected error occurred: {e}"

        try:
            if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                self.master_window.after(0, self._handle_capture_result_on_main_thread, captured_points_list, error_message_for_user)
            else:
                logger.warning("CoordinateCaptureWindow (Thread): Master window no longer exists. Cannot schedule callback.")
                if captured_points_list: logger.info(f"  (Discarded point data: {captured_points_list})")
                if error_message_for_user: logger.info(f"  (Discarded error: {error_message_for_user})")
        except Exception as e:
            logger.error(f"CoordinateCaptureWindow (Thread): Error scheduling callback to main thread: {e}", exc_info=True)


    def _handle_capture_result_on_main_thread(self, result_data_list: Optional[List[Dict[str, int]]], error_msg_for_user: Optional[str]):
        logger.debug(f"CoordinateCaptureWindow (MainThread): Handling capture result. Data: {'Yes' if result_data_list else 'No'}, Error: '{error_msg_for_user or 'None'}'")

        self._disable_master_window(False)
        try:
             if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                  if hasattr(self.master_window, 'lift'): self.master_window.lift()
                  if hasattr(self.master_window, 'focus_force'): self.master_window.focus_force()
        except tk.TclError: pass


        if error_msg_for_user:
            if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                messagebox.showerror("Capture Error", error_msg_for_user, parent=self.master_window)
            else:
                logger.error(f"Capture Error (master window destroyed, cannot show messagebox): {error_msg_for_user}")

        if self.callback:
            final_result_for_callback: Optional[Any] = None
            if result_data_list:
                try:
                    if self.num_points_to_capture == 1 and len(result_data_list) == 1:
                        point_dict = result_data_list[0]
                        final_result_for_callback = (int(point_dict['x']), int(point_dict['y']))
                    elif self.num_points_to_capture == 2 and len(result_data_list) == 2:
                        p1_dict = result_data_list[0]
                        p2_dict = result_data_list[1]
                        final_result_for_callback = (
                            (int(p1_dict['x']), int(p1_dict['y'])),
                            (int(p2_dict['x']), int(p2_dict['y']))
                        )
                    else: 
                        final_result_for_callback = [
                            {"x": int(p.get("x", 0)), "y": int(p.get("y", 0))} for p in result_data_list
                        ]
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"CoordinateCaptureWindow (MainThread): Error parsing point data from C#: {e}. Data: {result_data_list}", exc_info=True)
                    if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                        messagebox.showerror("Data Error", "Received invalid point data from capture service.", parent=self.master_window)
                    final_result_for_callback = None 

            try:
                self.callback(final_result_for_callback)
            except Exception as e:
                logger.error(f"CoordinateCaptureWindow (MainThread): Error executing callback: {e}", exc_info=True)
                if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                     messagebox.showerror("Callback Error", f"Error processing captured point data:\n{e}", parent=self.master_window)
