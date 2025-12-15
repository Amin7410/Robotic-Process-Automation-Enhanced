// InteractiveCaptureService.cs
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms; // Required for Form, Keys, PaintEventArgs, etc.

namespace sever
{
    public class InteractiveCaptureService : IDisposable
    {
        // P/Invoke for Hooks and Window Styles (similar to OSInteractions.cs)
        private const int WH_MOUSE_LL = 14;
        private const int WH_KEYBOARD_LL = 13;
        private const int WM_LBUTTONDOWN = 0x0201;
        private const int WM_LBUTTONUP = 0x0202;
        private const int WM_MOUSEMOVE = 0x0200;
        private const int WM_RBUTTONDOWN = 0x0204;
        private const int WM_KEYDOWN = 0x0100;

        [StructLayout(LayoutKind.Sequential)]
        public struct POINT { public int X; public int Y; }

        [StructLayout(LayoutKind.Sequential)]
        private struct MSLLHOOKSTRUCT
        {
            public POINT pt; public uint mouseData; public uint flags; public uint time; public IntPtr dwExtraInfo;
        }

        private delegate IntPtr HookProc(int nCode, IntPtr wParam, IntPtr lParam);

        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern IntPtr SetWindowsHookEx(int idHook, HookProc lpfn, IntPtr hMod, uint dwThreadId);
        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool UnhookWindowsHookEx(IntPtr hhk);
        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);
        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern IntPtr GetModuleHandle(string? lpModuleName);

        private const int GWL_EXSTYLE = -20;
        private const uint WS_EX_LAYERED = 0x00080000;
        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr SetWindowLongPtr(IntPtr hWnd, int nIndex, IntPtr dwNewLong);
        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex);


        private Form? _interactiveCaptureForm;
        private IntPtr _mouseHookHandle = IntPtr.Zero;
        private HookProc? _mouseHookDelegate;
        private IntPtr _keyboardHookHandle = IntPtr.Zero;
        private HookProc? _keyboardHookDelegate;

        private List<List<OSInteractions.PointDto>> _allStrokes = new List<List<OSInteractions.PointDto>>();
        private List<OSInteractions.PointDto> _currentStrokePoints = new List<OSInteractions.PointDto>();
        private bool _isDrawingOrDragging = false;
        private Point _captureStartPoint = Point.Empty;
        private Point _currentMousePosition = Point.Empty;

        private enum CaptureModeInternal { None, Drawing, RegionSelect, PointSelect }
        private CaptureModeInternal _currentCaptureModeInternal = CaptureModeInternal.None;
        private int _pointsToSelectInternal = 0;
        private int _pointsSelectedInternal = 0;

        private TaskCompletionSource<string?> _captureCompletionSourceInternal;

        public InteractiveCaptureService()
        {
            _captureCompletionSourceInternal = new TaskCompletionSource<string?>(TaskCreationOptions.RunContinuationsAsynchronously);
        }

        private void PrepareInteractiveCaptureInternal(CaptureModeInternal mode, int pointsToSelect = 0)
        {
            // CleanupInteractiveCaptureInternal(); // Ensure no prior state if re-used, but usually new instance per capture

            _currentCaptureModeInternal = mode;
            _pointsToSelectInternal = pointsToSelect;
            _pointsSelectedInternal = 0;
            _allStrokes.Clear();
            _currentStrokePoints.Clear();
            _isDrawingOrDragging = false;
            _captureStartPoint = Point.Empty;
            // _captureCompletionSourceInternal is already new from constructor

            _interactiveCaptureForm = new Form
            {
                FormBorderStyle = FormBorderStyle.None,
                WindowState = FormWindowState.Maximized,
                TopMost = true,
                ShowInTaskbar = false,
                BackColor = Color.Magenta,
                TransparencyKey = Color.Magenta,
                Cursor = Cursors.Cross,
                KeyPreview = true
            };

            IntPtr originalExStyle = GetWindowLongPtr(_interactiveCaptureForm.Handle, GWL_EXSTYLE);
            SetWindowLongPtr(_interactiveCaptureForm.Handle, GWL_EXSTYLE, (IntPtr)(originalExStyle.ToInt64() | WS_EX_LAYERED));

            _interactiveCaptureForm.Paint += OnCaptureFormPaintInternal;
            _interactiveCaptureForm.KeyDown += OnCaptureFormKeyDownInternal;

            // The form must run on an STA thread.
            // The calling method in OSInteractions.cs (which is called from PipeServer's async loop)
            // will handle running this whole capture sequence in a way that doesn't block the pipe server.
            _interactiveCaptureForm.Load += (s, e) =>
            { // Setup hooks after form handle is created
                _mouseHookDelegate = MouseHookCallbackInternal;
                _mouseHookHandle = SetWindowsHookEx(WH_MOUSE_LL, _mouseHookDelegate, GetModuleHandle(null), 0);
                if (_mouseHookHandle == IntPtr.Zero)
                {
                    Console.WriteLine("ICS: Failed to set mouse hook. Error: " + Marshal.GetLastWin32Error());
                    CompleteInteractiveCaptureInternal(true); return;
                }

                _keyboardHookDelegate = KeyboardHookCallbackInternal;
                _keyboardHookHandle = SetWindowsHookEx(WH_KEYBOARD_LL, _keyboardHookDelegate, GetModuleHandle(null), 0);
                if (_keyboardHookHandle == IntPtr.Zero)
                {
                    Console.WriteLine("ICS: Failed to set keyboard hook. Error: " + Marshal.GetLastWin32Error());
                    if (_mouseHookHandle == IntPtr.Zero) CompleteInteractiveCaptureInternal(true); // only if mouse also failed
                }
                // Activate the form after hooks are set
                _interactiveCaptureForm.Activate();
            };
            _interactiveCaptureForm.FormClosed += (s, e) =>
            {
                // If form is closed by other means (e.g. Alt+F4 before Esc), ensure cleanup and completion
                if (!_captureCompletionSourceInternal.Task.IsCompleted)
                {
                    Console.WriteLine("ICS: Capture form closed unexpectedly. Completing as cancelled.");
                    CompleteInteractiveCaptureInternal(true); // Consider it cancelled
                }
            };

            _interactiveCaptureForm.ShowDialog(); // This blocks the current thread until the form is closed.
                                                  // This is fine if this whole method is run on a dedicated thread.
        }

        public Task<string?> StartDrawingCaptureAsync()
        {
            Console.WriteLine("ICS: Starting Drawing Capture...");
            // Run PrepareInteractiveCaptureInternal and ShowDialog on a new STA thread
            // to avoid blocking the caller if the caller is not already on an STA thread
            // or if the caller is an async method on a thread pool thread.
            Thread staThread = new Thread(() => PrepareInteractiveCaptureInternal(CaptureModeInternal.Drawing))
            {
                IsBackground = true // Ensure thread doesn't keep app alive
            };
            staThread.SetApartmentState(ApartmentState.STA);
            staThread.Start();
            return _captureCompletionSourceInternal.Task;
        }

        public Task<string?> StartRegionSelectAsync()
        {
            Console.WriteLine("ICS: Starting Region Select...");
            Thread staThread = new Thread(() => PrepareInteractiveCaptureInternal(CaptureModeInternal.RegionSelect))
            {
                IsBackground = true
            };
            staThread.SetApartmentState(ApartmentState.STA);
            staThread.Start();
            return _captureCompletionSourceInternal.Task;
        }

        public Task<string?> StartPointSelectAsync(int numPoints)
        {
            Console.WriteLine($"ICS: Starting Point Select (Points: {numPoints})...");
            if (numPoints <= 0) numPoints = 1;
            Thread staThread = new Thread(() => PrepareInteractiveCaptureInternal(CaptureModeInternal.PointSelect, numPoints))
            {
                IsBackground = true
            };
            staThread.SetApartmentState(ApartmentState.STA);
            staThread.Start();
            return _captureCompletionSourceInternal.Task;
        }


        private void CleanupInteractiveCaptureInternal()
        {
            if (_mouseHookHandle != IntPtr.Zero) UnhookWindowsHookEx(_mouseHookHandle);
            _mouseHookHandle = IntPtr.Zero;
            if (_keyboardHookHandle != IntPtr.Zero) UnhookWindowsHookEx(_keyboardHookHandle);
            _keyboardHookHandle = IntPtr.Zero;
            _mouseHookDelegate = null;
            _keyboardHookDelegate = null;

            if (_interactiveCaptureForm != null)
            {
                // Ensure form closure happens on its own thread if it's still alive
                if (_interactiveCaptureForm.IsHandleCreated && !_interactiveCaptureForm.IsDisposed)
                {
                    try
                    {
                        if (_interactiveCaptureForm.InvokeRequired)
                        {
                            _interactiveCaptureForm.BeginInvoke(new Action(() =>
                            {
                                _interactiveCaptureForm?.Close();
                            }));
                        }
                        else
                        {
                            _interactiveCaptureForm?.Close();
                        }
                    }
                    catch (Exception ex) { Console.WriteLine($"ICS: Error closing form: {ex.Message}"); }
                }
                // _interactiveCaptureForm.Dispose() will be called by Form.Close() or when the STA thread exits.
                _interactiveCaptureForm = null;
            }
            _currentCaptureModeInternal = CaptureModeInternal.None;
            Console.WriteLine("ICS: Interactive capture resources cleaned up.");
        }

        private void CompleteInteractiveCaptureInternal(bool cancelled)
        {
            Console.WriteLine($"ICS: Completing interactive capture. Cancelled: {cancelled}. Mode: {_currentCaptureModeInternal}");
            string? jsonResult = null;
            if (!cancelled)
            {
                if (_currentCaptureModeInternal == CaptureModeInternal.Drawing && _allStrokes.Any())
                {
                    jsonResult = JsonSerializer.Serialize(_allStrokes);
                }
                else if (_currentCaptureModeInternal == CaptureModeInternal.RegionSelect && _captureStartPoint != Point.Empty && _currentMousePosition != Point.Empty && _captureStartPoint != _currentMousePosition)
                {
                    int r_x1 = Math.Min(_captureStartPoint.X, _currentMousePosition.X);
                    int r_y1 = Math.Min(_captureStartPoint.Y, _currentMousePosition.Y);
                    int r_x2 = Math.Max(_captureStartPoint.X, _currentMousePosition.X);
                    int r_y2 = Math.Max(_captureStartPoint.Y, _currentMousePosition.Y);
                    if (r_x2 == r_x1) r_x2 = r_x1 + 1;
                    if (r_y2 == r_y1) r_y2 = r_y1 + 1;

                    byte[]? regionImgBytes = OSInteractions.CaptureRegionGDI(r_x1, r_y1, r_x2, r_y2); // Call static GDI capture
                    var regionData = new
                    {
                        x1 = r_x1,
                        y1 = r_y1,
                        x2 = r_x2,
                        y2 = r_y2,
                        image_base64 = regionImgBytes != null && regionImgBytes.Length > 0 ? Convert.ToBase64String(regionImgBytes) : null
                    };
                    jsonResult = JsonSerializer.Serialize(regionData);
                }
                else if (_currentCaptureModeInternal == CaptureModeInternal.PointSelect && _allStrokes.Any() && _allStrokes[0].Any())
                {
                    jsonResult = JsonSerializer.Serialize(_allStrokes[0]);
                }
            }
            // Must call CleanupInteractiveCaptureInternal BEFORE TrySetResult,
            // because TrySetResult might allow the awaiting thread to continue and
            // potentially try to start a new capture before cleanup is done.
            CleanupInteractiveCaptureInternal();
            _captureCompletionSourceInternal.TrySetResult(jsonResult);
        }


        private void OnCaptureFormPaintInternal(object? sender, PaintEventArgs e)
        {
            if (_interactiveCaptureForm == null) return;
            Graphics g = e.Graphics;
            g.Clear(_interactiveCaptureForm.TransparencyKey);

            using Pen strokePen = new Pen(Color.LimeGreen, 2);
            using Pen currentStrokePen = new Pen(Color.Cyan, 2) { DashStyle = System.Drawing.Drawing2D.DashStyle.Dash };
            using Brush pointBrush = new SolidBrush(Color.Red);
            // ... (rest of the painting logic, same as before but using _currentCaptureModeInternal etc.)
            if (_currentCaptureModeInternal == CaptureModeInternal.Drawing)
            {
                foreach (var stroke in _allStrokes)
                {
                    if (stroke.Count > 1) g.DrawLines(strokePen, stroke.Select(p => new Point(p.x, p.y)).ToArray());
                    foreach (var pDto in stroke) g.FillEllipse(pointBrush, pDto.x - 2, pDto.y - 2, 5, 5);
                }
                if (_currentStrokePoints.Count > 1) g.DrawLines(currentStrokePen, _currentStrokePoints.Select(p => new Point(p.x, p.y)).ToArray());
                foreach (var pDto in _currentStrokePoints) g.FillEllipse(pointBrush, pDto.x - 2, pDto.y - 2, 5, 5);
            }
            else if (_currentCaptureModeInternal == CaptureModeInternal.RegionSelect && _isDrawingOrDragging)
            {
                int x = Math.Min(_captureStartPoint.X, _currentMousePosition.X);
                int y = Math.Min(_captureStartPoint.Y, _currentMousePosition.Y);
                int width = Math.Abs(_captureStartPoint.X - _currentMousePosition.X);
                int height = Math.Abs(_captureStartPoint.Y - _currentMousePosition.Y);
                if (width > 0 && height > 0) g.DrawRectangle(currentStrokePen, x, y, width, height);
            }
            else if (_currentCaptureModeInternal == CaptureModeInternal.PointSelect)
            {
                if (_allStrokes.Any() && _allStrokes[0].Any())
                {
                    foreach (var pDto in _allStrokes[0])
                    {
                        g.FillEllipse(pointBrush, pDto.x - 3, pDto.y - 3, 7, 7);
                        using Font font = new Font("Arial", 8, FontStyle.Bold);
                        using Brush textBrush = new SolidBrush(Color.White);
                        int pointNumber = _allStrokes[0].IndexOf(pDto) + 1;
                        g.DrawString(pointNumber.ToString(), font, textBrush, pDto.x - 4, pDto.y - 5);
                    }
                }
            }
        }

        private void OnCaptureFormKeyDownInternal(object? sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Escape) CompleteInteractiveCaptureInternal(true);
            else if (_currentCaptureModeInternal == CaptureModeInternal.Drawing && (e.KeyCode == Keys.Enter || e.KeyCode == Keys.Space))
            {
                if (_isDrawingOrDragging || _currentStrokePoints.Any())
                {
                    _isDrawingOrDragging = false;
                    if (_currentStrokePoints.Any()) _allStrokes.Add(new List<OSInteractions.PointDto>(_currentStrokePoints));
                    _currentStrokePoints.Clear();
                    _interactiveCaptureForm?.Invalidate();
                }
            }
        }

        private IntPtr KeyboardHookCallbackInternal(int nCode, IntPtr wParam, IntPtr lParam)
        {
            if (nCode >= 0 && wParam == (IntPtr)WM_KEYDOWN)
            {
                int vkCode = Marshal.ReadInt32(lParam); Keys key = (Keys)vkCode;
                if (key == Keys.Escape)
                {
                    Console.WriteLine("ICS Keyboard Hook: Escape pressed.");
                    _interactiveCaptureForm?.BeginInvoke(new Action(() => CompleteInteractiveCaptureInternal(true)));
                    return (IntPtr)1;
                }
                if (_currentCaptureModeInternal == CaptureModeInternal.Drawing && (key == Keys.Enter || key == Keys.Space))
                {
                    _interactiveCaptureForm?.BeginInvoke(new Action(() =>
                    {
                        if (_isDrawingOrDragging || _currentStrokePoints.Any())
                        {
                            _isDrawingOrDragging = false;
                            if (_currentStrokePoints.Any()) _allStrokes.Add(new List<OSInteractions.PointDto>(_currentStrokePoints));
                            _currentStrokePoints.Clear();
                            _interactiveCaptureForm?.Invalidate();
                        }
                    }));
                    return (IntPtr)1;
                }
            }
            return CallNextHookEx(_keyboardHookHandle, nCode, wParam, lParam);
        }

        private IntPtr MouseHookCallbackInternal(int nCode, IntPtr wParam, IntPtr lParam)
        {
            if (nCode >= 0 && _interactiveCaptureForm != null && _interactiveCaptureForm.Visible)
            {
                MSLLHOOKSTRUCT hookStruct = (MSLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(MSLLHOOKSTRUCT))!;
                Point currentPoint = new Point(hookStruct.pt.X, hookStruct.pt.Y);
                _currentMousePosition = currentPoint;

                Action? invalidateAction = () => _interactiveCaptureForm?.Invalidate();

                if (_currentCaptureModeInternal == CaptureModeInternal.Drawing)
                {
                    if (wParam == (IntPtr)WM_LBUTTONDOWN)
                    {
                        if (!_isDrawingOrDragging) { _isDrawingOrDragging = true; _currentStrokePoints.Clear(); }
                        _currentStrokePoints.Add(new OSInteractions.PointDto { x = currentPoint.X, y = currentPoint.Y });
                        if (_interactiveCaptureForm.IsHandleCreated) _interactiveCaptureForm.BeginInvoke(invalidateAction);
                        return (IntPtr)1;
                    }
                    else if (wParam == (IntPtr)WM_MOUSEMOVE && _isDrawingOrDragging)
                    {
                        if (_currentStrokePoints.Any() && (Math.Abs(_currentStrokePoints.Last().x - currentPoint.X) > 1 || Math.Abs(_currentStrokePoints.Last().y - currentPoint.Y) > 1))
                        {
                            _currentStrokePoints.Add(new OSInteractions.PointDto { x = currentPoint.X, y = currentPoint.Y });
                            if (_interactiveCaptureForm.IsHandleCreated) _interactiveCaptureForm.BeginInvoke(invalidateAction);
                        }
                        return (IntPtr)1;
                    }
                    else if (wParam == (IntPtr)WM_LBUTTONUP && _isDrawingOrDragging)
                    {
                        if (_currentStrokePoints.Any() && (Math.Abs(_currentStrokePoints.Last().x - currentPoint.X) > 1 || Math.Abs(_currentStrokePoints.Last().y - currentPoint.Y) > 1))
                        {
                            _currentStrokePoints.Add(new OSInteractions.PointDto { x = currentPoint.X, y = currentPoint.Y });
                        }
                        if (_interactiveCaptureForm.IsHandleCreated) _interactiveCaptureForm.BeginInvoke(invalidateAction);
                        return (IntPtr)1;
                    }
                    else if (wParam == (IntPtr)WM_RBUTTONDOWN)
                    {
                        if (_isDrawingOrDragging || _currentStrokePoints.Any())
                        {
                            _isDrawingOrDragging = false;
                            if (_currentStrokePoints.Any()) _allStrokes.Add(new List<OSInteractions.PointDto>(_currentStrokePoints));
                        }
                        _currentStrokePoints.Clear();
                        if (_interactiveCaptureForm.IsHandleCreated) _interactiveCaptureForm.BeginInvoke(invalidateAction);
                        return (IntPtr)1;
                    }
                }
                else if (_currentCaptureModeInternal == CaptureModeInternal.RegionSelect)
                {
                    if (wParam == (IntPtr)WM_LBUTTONDOWN)
                    {
                        _isDrawingOrDragging = true; _captureStartPoint = currentPoint;
                        if (_interactiveCaptureForm.IsHandleCreated) _interactiveCaptureForm.BeginInvoke(invalidateAction);
                        return (IntPtr)1;
                    }
                    else if (wParam == (IntPtr)WM_MOUSEMOVE && _isDrawingOrDragging)
                    {
                        if (_interactiveCaptureForm.IsHandleCreated) _interactiveCaptureForm.BeginInvoke(invalidateAction);
                        // return (IntPtr)1;
                    }
                    else if (wParam == (IntPtr)WM_LBUTTONUP && _isDrawingOrDragging)
                    {
                        _isDrawingOrDragging = false;
                        if (_interactiveCaptureForm.IsHandleCreated) _interactiveCaptureForm.BeginInvoke(new Action(() => CompleteInteractiveCaptureInternal(false)));
                        return (IntPtr)1;
                    }
                }
                else if (_currentCaptureModeInternal == CaptureModeInternal.PointSelect)
                {
                    if (wParam == (IntPtr)WM_LBUTTONDOWN)
                    {
                        if (_allStrokes.Count == 0) _allStrokes.Add(new List<OSInteractions.PointDto>());
                        _allStrokes[0].Add(new OSInteractions.PointDto { x = currentPoint.X, y = currentPoint.Y });
                        _pointsSelectedInternal++;
                        if (_interactiveCaptureForm.IsHandleCreated) _interactiveCaptureForm.BeginInvoke(invalidateAction);
                        if (_pointsSelectedInternal >= _pointsToSelectInternal)
                        {
                            if (_interactiveCaptureForm.IsHandleCreated) _interactiveCaptureForm.BeginInvoke(new Action(() => CompleteInteractiveCaptureInternal(false)));
                        }
                        return (IntPtr)1;
                    }
                }
            }
            return CallNextHookEx(_mouseHookHandle, nCode, wParam, lParam);
        }

        public void Dispose()
        {
            Console.WriteLine("ICS: Dispose called.");
            CleanupInteractiveCaptureInternal();
            // If _captureCompletionSourceInternal is still pending, cancel it.
            _captureCompletionSourceInternal?.TrySetCanceled();
        }
    }
}
