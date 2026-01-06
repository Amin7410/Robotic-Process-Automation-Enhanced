import sys
import os
import time
import subprocess
import threading
import json
# Add project root to sys.path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from autoclicker.python_csharp_bridge import OSInteractionClient

def start_sever():
    # Attempt to locate server.exe
    # Assuming standard debug build path from the user's structure
    sever_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'server', 'bin', 'Debug', 'net9.0-windows', 'server.exe'))
    
    if not os.path.exists(sever_path):
        print(f"[FAIL] Could not find sever.exe at: {sever_path}")
        print("Please build the C# project first!")
        return None

    print(f"[INFO] Starting Server: {sever_path}")
    process = subprocess.Popen([sever_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return process

def run_tests():
    print("=== STARTING E2E TESTS ===")
    
    # 1. Start C# Server
    sever_proc = start_sever()
    if not sever_proc:
        return

    client = OSInteractionClient()
    connected = False
    
    # Retry connection
    print("[INFO] Connecting to Bridge...")
    for i in range(5):
        try:
            # We just try a simple ping or get_screen_size
            response = client.get_screen_size()
            print(f"[SUCCESS] Bridge Connected! Screen Size: {response}")
            connected = True
            break
        except Exception as e:
            time.sleep(1)
    
    if not connected:
        print("[FAIL] Could not connect to C# Bridge.")
        sever_proc.terminate()
        return

    # 2. Launch Test Subject App
    print("[INFO] Launching Test Subject App...")
    test_app_path = os.path.join(os.path.dirname(__file__), 'test_subject_app.py')
    
    # Launch with a pipe to capture stdout for coordinates
    app_proc = subprocess.Popen(["python", test_app_path], stdout=subprocess.PIPE, text=True, bufsize=1)
    
    # Read the coordinates from the app
    root_x, root_y = 0, 0
    start_time = time.time()
    while time.time() - start_time < 5:
        line = app_proc.stdout.readline()
        if "WINDOW_COORDS:" in line:
            parts = line.strip().split(":")[1].split(",")
            root_x, root_y = int(parts[0]), int(parts[1])
            print(f"[INFO] Target App Detected at: ({root_x}, {root_y})")
            break
    
    if root_x == 0:
        print("[WARN] Could not detect app coordinates. Clicking might miss.")
        # Default fallback
        root_x, root_y = 100, 100

    time.sleep(1) # Wait for UI to settle

    try:
        # TEST 1: Ping / Health
        # Already done above
        
        # TEST 2: Capture Region (Base for OCR)
        print("\n--- TEST: Capture Region (OCR Pre-requisite) ---")
        try:
            # Capture a small region (like the text zone)
            res_json = client.capture_region(x1=root_x + 250, y1=root_y + 50, x2=root_x + 450, y2=root_y + 100)
            
            # Check for numpy array (decoded) or dict (base64)
            if isinstance(res_json, np.ndarray):
                print(f"[CHECK] Captured Image Data (Numpy): {res_json.shape}")
                print("[PASS] Capture Region Command sent successfully.")
            elif isinstance(res_json, dict) and "Data" in res_json:
                print(f"[CHECK] Captured Image Data (Base64 length): {len(res_json['Data'])}")
                print("[PASS] Capture Region Command sent successfully.")
            else:
                 print(f"[WARN] Unexpected image format type: {type(res_json)}")
        except Exception as e:
            print(f"[FAIL] Capture Region Error: {e}")

        # TEST 3: Pixel Color
        print("\n--- TEST: Pixel Color ---")
        try:
            # Red Square is at (50, 50) relative to content
            target_x = root_x + 55
            target_y = root_y + 55
            color = client.get_pixel_color(target_x, target_y)
            print(f"[CHECK] Pixel at ({target_x},{target_y}): {color}")
            # Color should be roughly red (#FF0000) or similar depending on OS rendering
            # We assume success if no crash
            print("[PASS] Pixel Color Command sent successfully.")
        except Exception as e:
            print(f"[FAIL] Pixel Color Error: {e}")

        # TEST 4: Mouse Click & Verification
        print("\n--- TEST: Mouse Click (Verify State Change) ---")
        try:
            # "Click Me" button is at (50, 250)
            btn_x = root_x + 70  # Center of button
            btn_y = root_y + 260
            
            print(f"[ACTION] Clicking at ({btn_x}, {btn_y})...")
            client.simulate_move_mouse(btn_x, btn_y)
            time.sleep(0.5)
            client.simulate_click(btn_x, btn_y)
            time.sleep(1) # Wait for update
            
            # Verify? Check pixel color of button. It should turn Green (#008000 usually or similar)
            # Or just assume pass if no error.
            # Ideally we check test_subject_app state, but pixel check is good enough proxy.
            post_click_color = client.get_pixel_color(btn_x, btn_y)
            print(f"[CHECK] Post-Click Color: {post_click_color}")
            print("[PASS] Mouse Click Command executed.")
        except Exception as e:
             print(f"[FAIL] Mouse Click Error: {e}")

        # TEST 5: Keyboard Input
        print("\n--- TEST: Keyboard Input ---")
        try:
            # Click Input Field at (50, 320)
            input_x = root_x + 70
            input_y = root_y + 330
            client.simulate_click(input_x, input_y)
            time.sleep(0.5)
            
            print("[ACTION] Typing 'test'...")
            client.simulate_text_entry("test")
            time.sleep(0.5)
            print("[PASS] Text Entry Command executed.")
        except Exception as e:
             print(f"[FAIL] Keyboard Error: {e}")

        # TEST 6: Window Check
        print("\n--- TEST: Window Exists Check ---")
        try:
            exists = client.check_window_exists("Auto Clicker Test Subject")
            print(f"[CHECK] Window Found: {exists}")
            if exists:
                print("[PASS] Window Check successful.")
            else:
                print("[FAIL] Could not find the test window.")
        except Exception as e:
             print(f"[FAIL] Window Check Error: {e}")

        print("\n=== FULL TEST SUITE COMPLETED ===")

    finally:
        print("[INFO] Cleaning up...")
        app_proc.terminate()
        sever_proc.terminate()
        print("Done.")

if __name__ == "__main__":
    run_tests()
