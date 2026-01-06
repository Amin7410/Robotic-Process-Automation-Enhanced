// OSInteractions.cs
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using InputSimulatorStandard;
using InputSimulatorStandard.Native;
using System.Collections.Generic;
using System.Linq;
// using System.Security.Permissions; 
using System.Diagnostics;
using System.Windows.Forms;
using System.Threading.Tasks;

namespace server
{
    public static class OSInteractions
    {
        // Constants for GetSystemMetrics
        private const int SM_CXSCREEN = 0;
        private const int SM_CYSCREEN = 1;
        private const int SM_XVIRTUALSCREEN = 76;
        private const int SM_YVIRTUALSCREEN = 77;
        private const int SM_CXVIRTUALSCREEN = 78;
        private const int SM_CYVIRTUALSCREEN = 79;

        [DllImport("user32.dll")]
        private static extern int GetSystemMetrics(int nIndex);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool GetCursorPos(out POINT lpPoint);

        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern IntPtr FindWindow(string? lpClassName, string? lpWindowName);

        [StructLayout(LayoutKind.Sequential)]
        public struct POINT { public int X; public int Y; }

        public class PointDto { public int x { get; set; } public int y { get; set; } }

        private static readonly InputSimulator I = new InputSimulator();
        private static readonly string _logPrefix = "OSInteractions."; 

        public static Size GetScreenSize()
        {
            Console.WriteLine($"{_logPrefix}GetScreenSize: Called.");
            int screenWidth = GetSystemMetrics(SM_CXSCREEN);
            int screenHeight = GetSystemMetrics(SM_CYSCREEN);
            Console.WriteLine($"{_logPrefix}GetScreenSize: Width={screenWidth}, Height={screenHeight}.");
            return new Size(screenWidth, screenHeight);
        }

        public static Rectangle GetVirtualScreenBounds()
        {
            Console.WriteLine($"{_logPrefix}GetVirtualScreenBounds: Called.");
            int virtualLeft = GetSystemMetrics(SM_XVIRTUALSCREEN);
            int virtualTop = GetSystemMetrics(SM_YVIRTUALSCREEN);
            int virtualWidth = GetSystemMetrics(SM_CXVIRTUALSCREEN);
            int virtualHeight = GetSystemMetrics(SM_CYVIRTUALSCREEN);
            var bounds = new Rectangle(virtualLeft, virtualTop, virtualWidth, virtualHeight);
            Console.WriteLine($"{_logPrefix}GetVirtualScreenBounds: Left={bounds.Left}, Top={bounds.Top}, Width={bounds.Width}, Height={bounds.Height}.");
            return bounds;
        }

        public static byte[]? CaptureRegionGDI(int x1, int y1, int x2, int y2)
        {
            Console.WriteLine($"{_logPrefix}CaptureRegionGDI: Called with region ({x1},{y1})-({x2},{y2}).");
            Rectangle virtualScreenBounds = GetVirtualScreenBounds(); 
            if (virtualScreenBounds.Width <= 0 || virtualScreenBounds.Height <= 0)
            {
                Console.WriteLine($"{_logPrefix}CaptureRegionGDI: Error - Invalid virtual screen bounds.");
                return null;
            }

            // Clamp coordinates to virtual screen
            int captureX1 = Math.Max(virtualScreenBounds.Left, Math.Min(virtualScreenBounds.Right, x1));
            int captureY1 = Math.Max(virtualScreenBounds.Top, Math.Min(virtualScreenBounds.Bottom, y1));
            int captureX2 = Math.Max(virtualScreenBounds.Left, Math.Min(virtualScreenBounds.Right, x2));
            int captureY2 = Math.Max(virtualScreenBounds.Top, Math.Min(virtualScreenBounds.Bottom, y2));

            int width = captureX2 - captureX1;
            int height = captureY2 - captureY1;

            Console.WriteLine($"{_logPrefix}CaptureRegionGDI: Clamped region ({captureX1},{captureY1})-({captureX2},{captureY2}). Capture size: {width}x{height}.");

            if (width <= 0 || height <= 0)
            {
                Console.WriteLine($"{_logPrefix}CaptureRegionGDI: Error - Invalid capture dimensions after clamping. WxH: {width}x{height}. Returning empty byte array.");
                return Array.Empty<byte>(); 
            }
            try
            {
                using Bitmap bitmap = new Bitmap(width, height, PixelFormat.Format32bppArgb);
                using Graphics g = Graphics.FromImage(bitmap);
                Console.WriteLine($"{_logPrefix}CaptureRegionGDI: Attempting CopyFromScreen from ({captureX1},{captureY1}) with size {width}x{height}.");
                g.CopyFromScreen(captureX1, captureY1, 0, 0, new Size(width, height), CopyPixelOperation.SourceCopy);
                Console.WriteLine($"{_logPrefix}CaptureRegionGDI: CopyFromScreen successful. Saving to PNG byte array.");
                using MemoryStream ms = new MemoryStream();
                bitmap.Save(ms, ImageFormat.Png);
                byte[] imageBytes = ms.ToArray();
                Console.WriteLine($"{_logPrefix}CaptureRegionGDI: Image saved to byte array (Length: {imageBytes.Length}).");
                return imageBytes;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"{_logPrefix}CaptureRegionGDI: Exception during capture or save: {ex.Message}\n{ex.StackTrace}");
                return null;
            }
        }


        public static byte[]? CaptureRegionAndPreprocess(int x1, int y1, int x2, int y2, bool useGrayscale, bool useBinarization)
        {
            Console.WriteLine($"{_logPrefix}CaptureRegionAndPreprocess: Called for region ({x1},{y1})-({x2},{y2}), Grayscale={useGrayscale}, Binarization={useBinarization}.");
            byte[]? originalPngBytes = CaptureRegionGDI(x1, y1, x2, y2); 
            if (originalPngBytes == null || originalPngBytes.Length == 0)
            {
                Console.WriteLine($"{_logPrefix}CaptureRegionAndPreprocess: CaptureRegionGDI returned null or empty. Cannot preprocess.");
                return originalPngBytes;
            }

            if (useGrayscale || useBinarization)
            {
                Console.WriteLine($"{_logPrefix}CaptureRegionAndPreprocess: Note - C# preprocessing flags (grayscale, binarization) are noted, but advanced preprocessing is currently expected in Python.");
                // byte[]? processedBytes = PreprocessImageBasic(originalPngBytes, useGrayscale, useBinarization);
                // return processedBytes ?? originalPngBytes;
            }
            Console.WriteLine($"{_logPrefix}CaptureRegionAndPreprocess: Returning captured (potentially raw) image bytes.");
            return originalPngBytes;
        }

        public static string? GetPixelColor(int x, int y)
        {
            Console.WriteLine($"{_logPrefix}GetPixelColor: Called for ({x},{y}).");
            Rectangle virtualScreenBounds = GetVirtualScreenBounds();
            if (virtualScreenBounds.Width <= 0 || virtualScreenBounds.Height <= 0)
            {
                Console.WriteLine($"{_logPrefix}GetPixelColor: Error - Invalid virtual screen bounds.");
                return null;
            }

            int targetX = Math.Max(virtualScreenBounds.Left, Math.Min(virtualScreenBounds.Right - 1, x));
            int targetY = Math.Max(virtualScreenBounds.Top, Math.Min(virtualScreenBounds.Bottom - 1, y));
            Console.WriteLine($"{_logPrefix}GetPixelColor: Clamped target coordinates to ({targetX},{targetY}).");

            try
            {
                using Bitmap pb = new Bitmap(1, 1, PixelFormat.Format32bppArgb);
                using Graphics g = Graphics.FromImage(pb);
                Console.WriteLine($"{_logPrefix}GetPixelColor: Attempting CopyFromScreen for 1x1 at ({targetX},{targetY}).");
                g.CopyFromScreen(targetX, targetY, 0, 0, new Size(1, 1));
                Color color = pb.GetPixel(0, 0);
                string colorHex = ColorTranslator.ToHtml(color);
                Console.WriteLine($"{_logPrefix}GetPixelColor: Success. Color at ({targetX},{targetY}) is {colorHex} (ARGB: {color.ToArgb():X8}).");
                return colorHex;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"{_logPrefix}GetPixelColor: Exception for ({x},{y}): {ex.Message}\n{ex.StackTrace}");
                return null;
            }
        }

        private static void MoveMouseToNormalizedPosition(int absX, int absY)
        {
            Console.WriteLine($"{_logPrefix}MoveMouseToNormalizedPosition: Input absolute ({absX},{absY}).");
            var vsb = GetVirtualScreenBounds();
            if (vsb.Width <= 0 || vsb.Height <= 0)
            {
                Console.WriteLine($"{_logPrefix}MoveMouseToNormalizedPosition: Error - Invalid virtual screen bounds. Skipping move.");
                return;
            }

            int cX = Math.Max(vsb.Left, Math.Min(vsb.Right - 1, absX));
            int cY = Math.Max(vsb.Top, Math.Min(vsb.Bottom - 1, absY));
            Console.WriteLine($"{_logPrefix}MoveMouseToNormalizedPosition: Clamped absolute to ({cX},{cY}).");

            double nX = (double)(cX - vsb.Left) * 65535.0 / vsb.Width;
            double nY = (double)(cY - vsb.Top) * 65535.0 / vsb.Height;
            Console.WriteLine($"{_logPrefix}MoveMouseToNormalizedPosition: Calculated normalized ({nX:F2},{nY:F2}).");

            try
            {
                I.Mouse.MoveMouseTo(Math.Max(0.0, Math.Min(65535.0, nX)), Math.Max(0.0, Math.Min(65535.0, nY)));
                Console.WriteLine($"{_logPrefix}MoveMouseToNormalizedPosition: MoveMouseTo called.");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"{_logPrefix}MoveMouseToNormalizedPosition: Exception during I.Mouse.MoveMouseTo: {ex.Message}\n{ex.StackTrace}");
            }
        }

        public static void SimulateClick(int x, int y, string button, string clickType, double holdDurationSeconds = 0)
        {
            Console.WriteLine($"{_logPrefix}SimulateClick: Called for ({x},{y}), Button='{button}', Type='{clickType}', Hold={holdDurationSeconds}s.");
            try
            {
                MoveMouseToNormalizedPosition(x, y);
                Console.WriteLine($"{_logPrefix}SimulateClick: Mouse moved to target. Sleeping 20ms before click action.");
                Thread.Sleep(20);

                MouseButton mb = button.ToLowerInvariant() switch
                {
                    "right" => MouseButton.RightButton,
                    "middle" => MouseButton.MiddleButton,
                    _ => MouseButton.LeftButton
                };
                Console.WriteLine($"{_logPrefix}SimulateClick: Mapped button '{button}' to MouseButton enum '{mb}'.");

                switch (clickType.ToLowerInvariant())
                {
                    case "single":
                        Console.WriteLine($"{_logPrefix}SimulateClick: Performing single click with {mb}.");
                        if (mb == MouseButton.LeftButton) I.Mouse.LeftButtonClick();
                        else if (mb == MouseButton.RightButton) I.Mouse.RightButtonClick();
                        else I.Mouse.MiddleButtonClick();
                        break;
                    case "double":
                        Console.WriteLine($"{_logPrefix}SimulateClick: Performing double click with {mb}.");
                        if (mb == MouseButton.LeftButton) I.Mouse.LeftButtonDoubleClick();
                        else if (mb == MouseButton.RightButton) I.Mouse.RightButtonDoubleClick();
                        else I.Mouse.MiddleButtonDoubleClick();
                        break;
                    case "down":
                        Console.WriteLine($"{_logPrefix}SimulateClick: Performing mouse down with {mb}.");
                        if (mb == MouseButton.LeftButton) I.Mouse.LeftButtonDown();
                        else if (mb == MouseButton.RightButton) I.Mouse.RightButtonDown();
                        else I.Mouse.MiddleButtonDown();
                        if (holdDurationSeconds > 0)
                        {
                            int hms = (int)(holdDurationSeconds * 1000);
                            Console.WriteLine($"{_logPrefix}SimulateClick: Holding mouse down for {hms}ms.");
                            if (hms > 0) Thread.Sleep(hms);
                            Console.WriteLine($"{_logPrefix}SimulateClick: Releasing mouse ({mb}) after hold.");
                            if (mb == MouseButton.LeftButton) I.Mouse.LeftButtonUp();
                            else if (mb == MouseButton.RightButton) I.Mouse.RightButtonUp();
                            else I.Mouse.MiddleButtonUp();
                        }
                        break;
                    case "up":
                        Console.WriteLine($"{_logPrefix}SimulateClick: Performing mouse up with {mb}.");
                        if (mb == MouseButton.LeftButton) I.Mouse.LeftButtonUp();
                        else if (mb == MouseButton.RightButton) I.Mouse.RightButtonUp();
                        else I.Mouse.MiddleButtonUp();
                        break;
                    default:
                        Console.WriteLine($"{_logPrefix}SimulateClick: Unknown clickType '{clickType}', defaulting to LeftButtonClick.");
                        I.Mouse.LeftButtonClick();
                        break;
                }
                Console.WriteLine($"{_logPrefix}SimulateClick: Action for '{clickType}' with {mb} completed.");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"{_logPrefix}SimulateClick: Exception for ({x},{y}), Btn='{button}', Type='{clickType}': {ex.Message}\n{ex.StackTrace}");
            }
        }
        public static void SimulateMouseMove(int x, int y, double durationSeconds = 0.1)
        {
            Console.WriteLine($"{_logPrefix}SimulateMouseMove: Called for ({x},{y}), Duration={durationSeconds}s.");
            try
            {
                if (!GetCursorPos(out POINT curPos))
                {
                    Console.WriteLine($"{_logPrefix}SimulateMouseMove: GetCursorPos failed. Moving directly.");
                    MoveMouseToNormalizedPosition(x, y); return;
                }
                int sX = curPos.X, sY = curPos.Y;
                Console.WriteLine($"{_logPrefix}SimulateMouseMove: Current cursor pos ({sX},{sY}). Target ({x},{y}).");

                if (durationSeconds <= 0.01 || (Math.Abs(sX - x) < 2 && Math.Abs(sY - y) < 2))
                {
                    Console.WriteLine($"{_logPrefix}SimulateMouseMove: Duration too short or already at target. Moving directly.");
                    MoveMouseToNormalizedPosition(x, y); return;
                }

                int steps = Math.Max(2, (int)(durationSeconds * 100.0));
                int slpMs = Math.Max(1, (int)((durationSeconds * 1000.0) / steps));
                Console.WriteLine($"{_logPrefix}SimulateMouseMove: Interpolating move over {steps} steps, with {slpMs}ms sleep between steps.");

                double stX = (double)(x - sX) / steps;
                double stY = (double)(y - sY) / steps;

                for (int i = 1; i <= steps; i++)
                {
                    int nextX = sX + (int)Math.Round(stX * i);
                    int nextY = sY + (int)Math.Round(stY * i);
                    Console.WriteLine($"{_logPrefix}SimulateMouseMove: Step {i}/{steps} to ({nextX},{nextY}).");
                    MoveMouseToNormalizedPosition(nextX, nextY);
                    if (i < steps) Thread.Sleep(slpMs);
                }
                Console.WriteLine($"{_logPrefix}SimulateMouseMove: Finalizing move to ensure exact target ({x},{y}).");
                MoveMouseToNormalizedPosition(x, y); // Ensure final position
                Console.WriteLine($"{_logPrefix}SimulateMouseMove: Completed.");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"{_logPrefix}SimulateMouseMove: Exception for ({x},{y}), Dur={durationSeconds}s: {ex.Message}\n{ex.StackTrace}");
            }
        }
        public static void SimulateDrag(int endX, int endY, string button, double durationSeconds = 0.1)
        {
            Console.WriteLine($"{_logPrefix}SimulateDrag: Called to ({endX},{endY}), Button='{button}', Duration={durationSeconds}s.");
            try
            {
                MouseButton mb = button.ToLowerInvariant() switch
                {
                    "right" => MouseButton.RightButton,
                    "middle" => MouseButton.MiddleButton,
                    _ => MouseButton.LeftButton
                };
                Console.WriteLine($"{_logPrefix}SimulateDrag: Mapped button '{button}' to MouseButton '{mb}'. Performing MouseDown.");
                if (mb == MouseButton.LeftButton) I.Mouse.LeftButtonDown();
                else if (mb == MouseButton.RightButton) I.Mouse.RightButtonDown();
                else I.Mouse.MiddleButtonDown();

                Console.WriteLine($"{_logPrefix}SimulateDrag: MouseDown completed. Sleeping 30ms.");
                Thread.Sleep(30); // Small delay after mousedown

                Console.WriteLine($"{_logPrefix}SimulateDrag: Simulating mouse move to ({endX},{endY}) over {durationSeconds}s.");
                SimulateMouseMove(endX, endY, durationSeconds); // Calls method with its own logging

                Console.WriteLine($"{_logPrefix}SimulateDrag: MouseMove for drag completed. Sleeping 30ms before MouseUp.");
                Thread.Sleep(30); // Small delay before mouseup

                Console.WriteLine($"{_logPrefix}SimulateDrag: Performing MouseUp with {mb}.");
                if (mb == MouseButton.LeftButton) I.Mouse.LeftButtonUp();
                else if (mb == MouseButton.RightButton) I.Mouse.RightButtonUp();
                else I.Mouse.MiddleButtonUp();
                Console.WriteLine($"{_logPrefix}SimulateDrag: Completed.");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"{_logPrefix}SimulateDrag: Exception to ({endX},{endY}), Btn='{button}', Dur={durationSeconds}s: {ex.Message}\n{ex.StackTrace}");
            }
        }
        public static void SimulateScroll(int scrollAmount, string direction = "vertical")
        {
            Console.WriteLine($"{_logPrefix}SimulateScroll: Called Amount={scrollAmount}, Direction='{direction}'.");
            try
            {
                if (direction.ToLowerInvariant() == "vertical")
                {
                    Console.WriteLine($"{_logPrefix}SimulateScroll: Performing VerticalScroll({scrollAmount}).");
                    I.Mouse.VerticalScroll(scrollAmount);
                }
                else
                {
                    Console.WriteLine($"{_logPrefix}SimulateScroll: Performing HorizontalScroll({scrollAmount}).");
                    I.Mouse.HorizontalScroll(scrollAmount);
                }
                Console.WriteLine($"{_logPrefix}SimulateScroll: Completed.");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"{_logPrefix}SimulateScroll: Exception Amount={scrollAmount}, Dir='{direction}': {ex.Message}\n{ex.StackTrace}");
            }
        }

        private static bool TryMapKeyNameToVirtualKeyCode(string keyName, out VirtualKeyCode vk)
        {
            vk = default;
            if (string.IsNullOrWhiteSpace(keyName))
            {
                Console.WriteLine($"{_logPrefix}TryMapKeyNameToVirtualKeyCode: keyName is null or whitespace. Returning false.");
                return false;
            }

            string upperKeyName = keyName.ToUpperInvariant();
            Console.WriteLine($"{_logPrefix}TryMapKeyNameToVirtualKeyCode: Attempting to map keyName='{keyName}' (ToUpper='{upperKeyName}').");

            if (upperKeyName.Length == 1)
            {
                char c = upperKeyName[0];
                if (c >= 'A' && c <= 'Z')
                {
                    if (Enum.TryParse("VK_" + c, out VirtualKeyCode letterVk))
                    {
                        vk = letterVk;
                        Console.WriteLine($"{_logPrefix}TryMapKeyNameToVirtualKeyCode: Mapped character '{c}' (from '{keyName}') to VirtualKeyCode '{vk}'.");
                        return true;
                    }
                    else { Console.WriteLine($"{_logPrefix}TryMapKeyNameToVirtualKeyCode: Enum.TryParse failed for 'VK_{c}'. This should not happen for A-Z."); }
                }
                else if (c >= '0' && c <= '9')
                {
                    if (Enum.TryParse("VK_" + c, out VirtualKeyCode digitVk))
                    {
                        vk = digitVk;
                        Console.WriteLine($"{_logPrefix}TryMapKeyNameToVirtualKeyCode: Mapped digit '{c}' (from '{keyName}') to VirtualKeyCode '{vk}'.");
                        return true;
                    }
                    else { Console.WriteLine($"{_logPrefix}TryMapKeyNameToVirtualKeyCode: Enum.TryParse failed for 'VK_{c}'. This should not happen for 0-9."); }
                }
            }

            switch (keyName.ToLowerInvariant()) // Use original keyName for special keys, case-insensitively
            {
                case "enter": case "return": vk = VirtualKeyCode.RETURN; break;
                case "esc": case "escape": vk = VirtualKeyCode.ESCAPE; break;
                case "tab": vk = VirtualKeyCode.TAB; break;
                case "space": case "spacebar": vk = VirtualKeyCode.SPACE; break;
                case "backspace": vk = VirtualKeyCode.BACK; break;
                case "delete": vk = VirtualKeyCode.DELETE; break;
                case "insert": vk = VirtualKeyCode.INSERT; break;
                case "home": vk = VirtualKeyCode.HOME; break;
                case "end": vk = VirtualKeyCode.END; break;
                case "pageup": vk = VirtualKeyCode.PRIOR; break; // PRIOR is PageUp
                case "pagedown": vk = VirtualKeyCode.NEXT; break; // NEXT is PageDown
                case "left": case "left_arrow": vk = VirtualKeyCode.LEFT; break;
                case "right": case "right_arrow": vk = VirtualKeyCode.RIGHT; break;
                case "up": case "up_arrow": vk = VirtualKeyCode.UP; break;
                case "down": case "down_arrow": vk = VirtualKeyCode.DOWN; break;
                case "ctrl": case "control": vk = VirtualKeyCode.CONTROL; break;
                case "lctrl": case "left_control": vk = VirtualKeyCode.LCONTROL; break;
                case "rctrl": case "right_control": vk = VirtualKeyCode.RCONTROL; break;
                case "shift": vk = VirtualKeyCode.SHIFT; break;
                case "lshift": case "left_shift": vk = VirtualKeyCode.LSHIFT; break;
                case "rshift": case "right_shift": vk = VirtualKeyCode.RSHIFT; break;
                case "alt": vk = VirtualKeyCode.MENU; break; // MENU is Alt
                case "lalt": case "left_alt": vk = VirtualKeyCode.LMENU; break;
                case "ralt": case "right_alt": vk = VirtualKeyCode.RMENU; break;
                case "win": case "lwin": case "left_windows": vk = VirtualKeyCode.LWIN; break;
                case "rwin": case "right_windows": vk = VirtualKeyCode.RWIN; break;
                case "f1": vk = VirtualKeyCode.F1; break;
                case "f2": vk = VirtualKeyCode.F2; break;
                case "f3": vk = VirtualKeyCode.F3; break;
                case "f4": vk = VirtualKeyCode.F4; break;
                case "f5": vk = VirtualKeyCode.F5; break;
                case "f6": vk = VirtualKeyCode.F6; break;
                case "f7": vk = VirtualKeyCode.F7; break;
                case "f8": vk = VirtualKeyCode.F8; break;
                case "f9": vk = VirtualKeyCode.F9; break;
                case "f10": vk = VirtualKeyCode.F10; break;
                case "f11": vk = VirtualKeyCode.F11; break;
                case "f12": vk = VirtualKeyCode.F12; break;
                case "num0": vk = VirtualKeyCode.NUMPAD0; break;
                case "num1": vk = VirtualKeyCode.NUMPAD1; break;
                case "num2": vk = VirtualKeyCode.NUMPAD2; break;
                case "num3": vk = VirtualKeyCode.NUMPAD3; break;
                case "num4": vk = VirtualKeyCode.NUMPAD4; break;
                case "num5": vk = VirtualKeyCode.NUMPAD5; break;
                case "num6": vk = VirtualKeyCode.NUMPAD6; break;
                case "num7": vk = VirtualKeyCode.NUMPAD7; break;
                case "num8": vk = VirtualKeyCode.NUMPAD8; break;
                case "num9": vk = VirtualKeyCode.NUMPAD9; break;
                case "add": vk = VirtualKeyCode.ADD; break;
                case "subtract": vk = VirtualKeyCode.SUBTRACT; break;
                case "multiply": vk = VirtualKeyCode.MULTIPLY; break;
                case "divide": vk = VirtualKeyCode.DIVIDE; break;
                case "decimal": vk = VirtualKeyCode.DECIMAL; break;
                // Add more mappings as needed
                default:
                    Console.WriteLine($"{_logPrefix}TryMapKeyNameToVirtualKeyCode: Failed to map special keyName: '{keyName}'. Returning false.");
                    return false;
            }
            Console.WriteLine($"{_logPrefix}TryMapKeyNameToVirtualKeyCode: Mapped special keyName '{keyName}' to VirtualKeyCode '{vk}'.");
            return true;
        }
        public static void SimulateKeyPress(string keyName)
        {
            Console.WriteLine($"{_logPrefix}SimulateKeyPress: Received keyName: '{keyName}'.");
            try
            {
                if (TryMapKeyNameToVirtualKeyCode(keyName, out var vk)) // Calls method with its own logging
                {
                    Console.WriteLine($"{_logPrefix}SimulateKeyPress: TESTING WITH TextEntry for '{keyName}' instead of KeyPress.");
                    I.Keyboard.TextEntry(keyName);
                    Console.WriteLine($"{_logPrefix}SimulateKeyPress: I.Keyboard.KeyPress({vk}) called successfully.");
                }
                else
                {
                    // TryMapKeyNameToVirtualKeyCode already logged the failure
                    Console.WriteLine($"{_logPrefix}SimulateKeyPress: Mapping failed for keyName '{keyName}'. No key press simulated.");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"{_logPrefix}SimulateKeyPress: Exception for key '{keyName}': {ex.Message}\n{ex.StackTrace}");
            }
        }
        public static void SimulateKeyDown(string keyName)
        {
            Console.WriteLine($"{_logPrefix}SimulateKeyDown: Received keyName: '{keyName}'.");
            try
            {
                if (TryMapKeyNameToVirtualKeyCode(keyName, out var vk))
                {
                    Console.WriteLine($"{_logPrefix}SimulateKeyDown: Attempting I.Keyboard.KeyDown with VirtualKeyCode: {vk} (for '{keyName}')");
                    I.Keyboard.KeyDown(vk);
                    Console.WriteLine($"{_logPrefix}SimulateKeyDown: I.Keyboard.KeyDown({vk}) called.");
                }
                else { Console.WriteLine($"{_logPrefix}SimulateKeyDown: Mapping failed for '{keyName}'."); }
            }
            catch (Exception ex) { Console.WriteLine($"{_logPrefix}SimulateKeyDown: Exception for '{keyName}': {ex.Message}\n{ex.StackTrace}"); }
        }
        public static void SimulateKeyUp(string keyName)
        {
            Console.WriteLine($"{_logPrefix}SimulateKeyUp: Received keyName: '{keyName}'.");
            try
            {
                if (TryMapKeyNameToVirtualKeyCode(keyName, out var vk))
                {
                    Console.WriteLine($"{_logPrefix}SimulateKeyUp: Attempting I.Keyboard.KeyUp with VirtualKeyCode: {vk} (for '{keyName}')");
                    I.Keyboard.KeyUp(vk);
                    Console.WriteLine($"{_logPrefix}SimulateKeyUp: I.Keyboard.KeyUp({vk}) called.");
                }
                else { Console.WriteLine($"{_logPrefix}SimulateKeyUp: Mapping failed for '{keyName}'."); }
            }
            catch (Exception ex) { Console.WriteLine($"{_logPrefix}SimulateKeyUp: Exception for '{keyName}': {ex.Message}\n{ex.StackTrace}"); }
        }
        public static void SimulateTextEntry(string text)
        {
            string logText = (text ?? "").Length > 50 ? (text ?? "").Substring(0, 50) + "..." : (text ?? "");
            Console.WriteLine($"{_logPrefix}SimulateTextEntry: Called with text (preview): '{logText}'.");
            try
            {
                I.Keyboard.TextEntry(text ?? "");
                Console.WriteLine($"{_logPrefix}SimulateTextEntry: I.Keyboard.TextEntry called.");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"{_logPrefix}SimulateTextEntry: Exception for text '{logText}': {ex.Message}\n{ex.StackTrace}");
            }
        }
        public static void SimulateModifiedKeyStroke(string modKeyName, string mainKeyName)
        {
            Console.WriteLine($"{_logPrefix}SimulateModifiedKeyStroke: Called with Modifier='{modKeyName}', MainKey='{mainKeyName}'.");
            try
            {
                VirtualKeyCode mVk, mnVk;
                bool modMapped = TryMapKeyNameToVirtualKeyCode(modKeyName, out mVk); // Calls method with its own logging
                bool mainMapped = TryMapKeyNameToVirtualKeyCode(mainKeyName, out mnVk); // Calls method with its own logging

                if (modMapped && mainMapped)
                {
                    Console.WriteLine($"{_logPrefix}SimulateModifiedKeyStroke: Attempting I.Keyboard.ModifiedKeyStroke(ModVK={mVk}, MainVK={mnVk}).");
                    I.Keyboard.ModifiedKeyStroke(mVk, mnVk);
                    Console.WriteLine($"{_logPrefix}SimulateModifiedKeyStroke: I.Keyboard.ModifiedKeyStroke called.");
                }
                else
                {
                    if (!modMapped) Console.WriteLine($"{_logPrefix}SimulateModifiedKeyStroke: Modifier key '{modKeyName}' could not be mapped.");
                    if (!mainMapped) Console.WriteLine($"{_logPrefix}SimulateModifiedKeyStroke: Main key '{mainKeyName}' could not be mapped.");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"{_logPrefix}SimulateModifiedKeyStroke: Exception for Mod='{modKeyName}', Main='{mainKeyName}': {ex.Message}\n{ex.StackTrace}");
            }
        }

        public static bool CheckWindowExists(string? className, string? windowTitle)
        {
            string? actualClassName = string.IsNullOrWhiteSpace(className) ? null : className;
            string? actualWindowTitle = string.IsNullOrWhiteSpace(windowTitle) ? null : windowTitle;
            Console.WriteLine($"{_logPrefix}CheckWindowExists: Called. Class='{actualClassName ?? "null"}', Title='{actualWindowTitle ?? "null"}'.");

            if (actualClassName == null && actualWindowTitle == null)
            {
                Console.WriteLine($"{_logPrefix}CheckWindowExists: Both class and title are null/empty. Returning false.");
                return false;
            }

            IntPtr hWnd = IntPtr.Zero;
            try
            {
                Console.WriteLine($"{_logPrefix}CheckWindowExists: Calling FindWindow...");
                hWnd = FindWindow(actualClassName, actualWindowTitle);
                bool found = hWnd != IntPtr.Zero;
                Console.WriteLine($"{_logPrefix}CheckWindowExists: FindWindow returned handle {hWnd}. Window {(found ? "found" : "not found")}.");
                return found;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"{_logPrefix}CheckWindowExists: FindWindow exception: {ex.Message}\n{ex.StackTrace}");
                return false;
            }
        }

        public static bool CheckProcessExists(string processName)
        {
            Console.WriteLine($"{_logPrefix}CheckProcessExists: Called for ProcessName='{processName}'.");
            if (string.IsNullOrWhiteSpace(processName))
            {
                Console.WriteLine($"{_logPrefix}CheckProcessExists: ProcessName is null or whitespace. Returning false.");
                return false;
            }

            string targetName = processName.Trim();
            if (targetName.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
            {
                targetName = targetName.Substring(0, targetName.Length - 4);
                Console.WriteLine($"{_logPrefix}CheckProcessExists: Removed .exe, targetName is now '{targetName}'.");
            }

            Process[] processes = Process.GetProcesses();
            Console.WriteLine($"{_logPrefix}CheckProcessExists: Found {processes.Length} running processes. Iterating...");
            bool found = false;
            foreach (Process p in processes)
            {
                try
                {
                    // Console.WriteLine($"{_logPrefix}CheckProcessExists: Checking process '{p.ProcessName}' (PID: {p.Id}).");
                    if (p.ProcessName.Equals(targetName, StringComparison.OrdinalIgnoreCase))
                    {
                        Console.WriteLine($"{_logPrefix}CheckProcessExists: Match found! Process '{p.ProcessName}' (PID: {p.Id}).");
                        found = true;
                        p.Dispose();
                        break;
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"{_logPrefix}CheckProcessExists: Error accessing info for process PID {p.Id}: {ex.Message}");
                }
                finally
                {
                    p.Dispose();
                }
            }
            if (!found) Console.WriteLine($"{_logPrefix}CheckProcessExists: Process '{targetName}' not found after checking all processes.");
            return found;
        }


        public static Task<string?> StartInteractiveDrawingCapture()
        {
            Console.WriteLine($"{_logPrefix}StartInteractiveDrawingCapture: Delegating to InteractiveCaptureService.");
            var captureService = new InteractiveCaptureService();
            return captureService.StartDrawingCaptureAsync();
        }

        public static Task<string?> StartInteractiveRegionSelect()
        {
            Console.WriteLine($"{_logPrefix}StartInteractiveRegionSelect: Delegating to InteractiveCaptureService.");
            var captureService = new InteractiveCaptureService();
            return captureService.StartRegionSelectAsync();
        }

        public static Task<string?> StartInteractivePointSelect(int numPoints)
        {
            Console.WriteLine($"{_logPrefix}StartInteractivePointSelect: Delegating to InteractiveCaptureService for {numPoints} point(s).");
            var captureService = new InteractiveCaptureService();
            return captureService.StartPointSelectAsync(numPoints);
        }
    }
}
