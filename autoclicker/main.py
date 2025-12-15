# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Đinh Khởi Minh

# main.py
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import logging
import subprocess
import os
import sys
import time
import atexit

logger = logging.getLogger(__name__)

from core.job_manager import JobManager 
from utils.config_loader import ConfigLoader 
from utils.image_storage import ImageStorage 
from gui.main_window import MainWindow 
from python_csharp_bridge import os_interaction_client

logger = logging.getLogger(__name__)

csharp_service_process: subprocess.Popen | None = None

CSHARP_EXE_NAME = "sever.exe" 

if getattr(sys, 'frozen', False):
    application_root = os.path.dirname(sys.executable) 
    
    csharp_bundle_dir_in_frozen = os.path.join(application_root, "_internal", "sever_bundle") 
    
    if not os.path.exists(csharp_bundle_dir_in_frozen) or not os.path.isdir(csharp_bundle_dir_in_frozen):
        csharp_bundle_dir_in_frozen = os.path.join(application_root, "sever_bundle")
    
    csharp_exe_full_path = os.path.join(csharp_bundle_dir_in_frozen, CSHARP_EXE_NAME)
    logger.debug(f"Running as frozen app. C# EXE path: {csharp_exe_full_path}")
else:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_script_dir, os.pardir))
    csharp_dev_build_dir = os.path.join(project_root, "sever", "bin", "Debug", "net9.0-windows","win-x64","publish")
    csharp_exe_full_path = os.path.join(csharp_dev_build_dir, CSHARP_EXE_NAME)
    logger.debug(f"Running in dev environment. C# EXE path: {csharp_exe_full_path}")

job_manager_instance: JobManager | None = None 

def on_closing(root: tk.Tk | None = None):
    logger.info("Application closing...")

    global job_manager_instance 

    if job_manager_instance:
        logger.info("Performing global cleanup via JobManager...")
        try:
            job_manager_instance.stop_all_running_jobs(wait=True, timeout=5.0) 
            logger.info("All jobs stopped.")

            job_manager_instance.cleanup_bindings()
            logger.info("Key bindings cleaned up.")

        except Exception as e:
            logger.error(f"Error during JobManager cleanup: {e}.", exc_info=True)
    else:
        logger.warning("JobManager instance not available during cleanup.")

    global csharp_service_process 
    if csharp_service_process and csharp_service_process.poll() is None:
        logger.info(f"Terminating C# OS Interaction Service (PID: {csharp_service_process.pid})...")
        try:
            csharp_service_process.terminate()
            csharp_service_process.wait(timeout=5)
            logger.info("C# process terminated gracefully.")
        except subprocess.TimeoutExpired:
             logger.warning("C# process did not terminate gracefully within timeout, killing it.")
             try:
                 csharp_service_process.kill()
                 logger.info("C# process killed.")
             except Exception as kill_ex:
                 logger.error(f"Error killing C# process: {kill_ex}.", exc_info=True)
        except Exception as e:
             logger.error(f"Error terminating C# process: {e}.", exc_info=True)
        csharp_service_process = None 

    if root and root.winfo_exists():
         logger.info("Destroying root window.")
         try:
             root.destroy()
         except Exception as e:
              logger.error(f"Error destroying root window: {e}.", exc_info=True)

    logger.info("Application shutdown complete.")
  
def main():
    global csharp_service_process
    global job_manager_instance

    logging.basicConfig(level=logging.DEBUG, 
                        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logger.info("Application starting...")

    if not JobManager:
        logger.critical("FATAL ERROR: JobManager failed to import.")
        messagebox.showerror("Startup Error", "JobManager component failed to load.\nPlease check console logs for details.")
        sys.exit("JobManager missing.") 

    if not ConfigLoader or not ImageStorage:
         logger.critical("FATAL ERROR: ConfigLoader or ImageStorage failed to import from utils.")
         messagebox.showerror("Startup Error", "Utility components failed to load.\nPlease check console logs for details.")
         sys.exit("Utils missing.") 

    if not MainWindow:
         logger.critical("FATAL ERROR: MainWindow failed to import.")
         messagebox.showerror("Startup Error", "MainWindow UI component failed to load.\nPlease check console logs for details.")
         sys.exit("MainWindow missing.") 

    if not os_interaction_client:
         logger.critical("FATAL ERROR: OS Interaction Bridge failed to import.")
         messagebox.showerror("Startup Error", "OS Interaction Bridge component failed to load.\nPlease check console logs for details.")
         sys.exit("Bridge missing.") 

    if not os.path.exists(csharp_exe_full_path):
        logger.critical(f"FATAL ERROR: C# OS Interaction Service executable not found at: '{csharp_exe_full_path}'")
        messagebox.showerror("Startup Error", f"C# OS Interaction Service executable not found.\nExpected at: '{csharp_exe_full_path}'")
        sys.exit("C# Service not found.") 

    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        csharp_service_process = subprocess.Popen([csharp_exe_full_path], creationflags=creation_flags, cwd=os.path.dirname(csharp_exe_full_path))
        logger.info(f"C# OS Interaction Service started. PID: {csharp_service_process.pid}")

        logger.info("Checking initial connection to C# service...")
        connect_attempts = 0
        max_connect_attempts = 20 
        connected = False
        last_error = None

        while connect_attempts < max_connect_attempts:
             try:
                  ping_result = os_interaction_client.ping()
                  logger.info(f"Initial connection successful. Ping response: {ping_result}")
                  screen_size = os_interaction_client.get_screen_size()
                  logger.info(f"Got initial screen size from C# service: {screen_size}")
                  connected = True
                  break 
             except Exception as e:
                  last_error = e
                  connect_attempts += 1
                  logger.warning(f"Initial connection attempt {connect_attempts} failed: {e}. Retrying in 0.1s.")
                  time.sleep(0.1) 

        if not connected:
             logger.critical(f"FATAL ERROR: Failed initial connection to C# service after {max_connect_attempts} attempts.")
             if last_error: logger.critical(f"Last connection error: {last_error}", exc_info=True)
             messagebox.showerror("Startup Error", f"Failed to connect to C# OS Interaction Service after multiple attempts.\nIs it built correctly and firewall allowing Named Pipes?\nError: {last_error}")
             on_closing(None) 
             sys.exit("Failed to connect to C# service.")

    except Exception as e:
        logger.critical(f"FATAL ERROR: Failed to start C# OS Interaction Service process: {e}.", exc_info=True)
        messagebox.showerror("Startup Error", f"Failed to start C# OS Interaction Service process.\nError: {e}")
        sys.exit("Failed to start C# service process.")

    try:
        config_loader = ConfigLoader(profile_dir="profiles", general_config_file="config.json")
        image_storage = ImageStorage("captured_images") 
        job_manager_instance = JobManager(config_loader, image_storage)

        root = tk.Tk()
        root.title("Auto Clicker Enhanced")
        root.geometry("900x700")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        style = ttk.Style()
        try:
            style.configure("Danger.TButton", foreground="white", background="red", bordercolor="red")
            style.map("Danger.TButton",
                  foreground=[('active', 'white'), ('pressed', 'white')],
                  background=[('active', '#CC0000'), ('pressed', '#990000')])
        except tk.TclError:
             logger.warning("Chosen theme or custom styles not available, using default.")
        except Exception as e:
             logger.warning(f"Error applying GUI style: {e}")

        main_window_frame = MainWindow(root, job_manager_instance, image_storage)
        main_window_frame.grid(row=0, column=0, sticky="nsew")

        root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root))
        root._main_app_on_closing_handler = lambda: on_closing(root) 

        logger.info("Starting Tkinter main loop...")
        try:
            root.mainloop()
        except KeyboardInterrupt:
             logger.info("KeyboardInterrupt received in main loop. Initiating shutdown.")
             on_closing(root) 
        except Exception as e:
            logger.critical(f"CRITICAL UNHANDLED EXCEPTION IN MAIN LOOP: {e}.", exc_info=True)
            messagebox.showerror("Fatal Error", f"An unhandled error occurred:\n{e}\nApplication will now close.")
            on_closing(root)

    except Exception as e:
        logger.critical(f"FATAL ERROR: Application initialization failed: {e}.", exc_info=True)
        messagebox.showerror("Startup Error", f"Application failed to initialize:\n{e}\nPlease check console logs for details.")
        on_closing(None) 
    logger.info("Main function finished.")

if __name__ == "__main__":
    if not hasattr(subprocess, 'CREATE_NO_WINDOW'):
         subprocess.CREATE_NO_WINDOW = 0x08000000 
    main()
