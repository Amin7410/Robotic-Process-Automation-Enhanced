// Program.cs
using System;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Drawing;
using sever; 

namespace server
{
    public class PipeServer
    {
        private readonly string _pipeName;
        private const int DefaultBufferSize = 16384; 

        public PipeServer(string pipeName)
        {
            _pipeName = pipeName ?? throw new ArgumentNullException(nameof(pipeName));
        }

        public async Task StartAsync(CancellationToken cancellationToken)
        {
            Console.WriteLine($"DEBUG CSPROGRAM: PipeServer.StartAsync called. PipeName: {_pipeName}. Timestamp: {DateTime.Now}");
            Console.WriteLine($"Named Pipe Server starting on '{_pipeName}'...");
            Console.WriteLine($"Buffer Size: {DefaultBufferSize} bytes");

            while (!cancellationToken.IsCancellationRequested)
            {
                NamedPipeServerStream? pipeServer = null;
                try
                {
                    pipeServer = new NamedPipeServerStream(
                        _pipeName,
                        PipeDirection.InOut,
                        1, // Max 1 server instance, client connects sequentially
                        PipeTransmissionMode.Byte,
                        PipeOptions.Asynchronous | PipeOptions.WriteThrough);

                    Console.WriteLine("Waiting for client connection...");
                    await pipeServer.WaitForConnectionAsync(cancellationToken).ConfigureAwait(false);
                    Console.WriteLine("Client connected. Handling communication...");

                    await HandleClientCommunicationAsync(pipeServer, cancellationToken).ConfigureAwait(false);
                }
                catch (OperationCanceledException)
                {
                    Console.WriteLine("Server operation cancelled.");
                    break;
                }
                catch (IOException ioEx)
                {
                    Console.WriteLine($"IO Error in pipe server loop: {ioEx.Message}");
                    // Avoid tight loop on persistent IO errors
                    await Task.Delay(500, cancellationToken).ConfigureAwait(false);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Unexpected error in server loop: {ex.GetType().Name} - {ex.Message}");
                    Console.WriteLine(ex.StackTrace);
                    await Task.Delay(1000, cancellationToken).ConfigureAwait(false);
                }
                finally
                {
                    if (pipeServer != null)
                    {
                        if (pipeServer.IsConnected)
                        {
                            try { pipeServer.Disconnect(); } catch { /* Ignore disconnect errors */ }
                        }
                        await pipeServer.DisposeAsync();
                    }
                    Console.WriteLine("Pipe instance disposed. Waiting for new connection...");
                }
            }
            Console.WriteLine("Pipe server loop exited.");
        }

        private async Task HandleClientCommunicationAsync(NamedPipeServerStream pipeServer, CancellationToken cancellationToken)
        {
            byte[] readChunkBuffer = new byte[DefaultBufferSize];
            List<byte> messageBuffer = new List<byte>(); // Accumulates bytes for a full message

            try
            {
                while (pipeServer.IsConnected && !cancellationToken.IsCancellationRequested)
                {
                    int bytesRead = 0;
                    try
                    {
                        bytesRead = await pipeServer.ReadAsync(readChunkBuffer.AsMemory(0, readChunkBuffer.Length), cancellationToken).ConfigureAwait(false);
                    }
                    catch (OperationCanceledException) { throw; }
                    catch (IOException ioEx) { Console.WriteLine($"IO Error during read (client likely disconnected): {ioEx.Message}"); break; }
                    catch (ObjectDisposedException) { Console.WriteLine("Pipe was disposed during read."); break; }
                    catch (Exception readEx) { Console.WriteLine($"Unexpected error during read: {readEx.Message}"); break; }

                    if (bytesRead == 0)
                    {
                        Console.WriteLine("Client disconnected (read 0 bytes).");
                        break;
                    }

                    messageBuffer.AddRange(readChunkBuffer.AsSpan(0, bytesRead).ToArray());

                    // Process all complete messages (ending with '\n') found in the buffer
                    while (true)
                    {
                        int newlineIndex = messageBuffer.IndexOf((byte)'\n');
                        if (newlineIndex == -1) break; // No complete message yet

                        byte[] requestBytes = messageBuffer.GetRange(0, newlineIndex).ToArray();
                        messageBuffer.RemoveRange(0, newlineIndex + 1); // Remove processed message and newline

                        string requestJson;
                        try
                        {
                            requestJson = Encoding.UTF8.GetString(requestBytes);
                            string logMsg = requestJson.Length > 200 ? requestJson.Substring(0, 200) + "..." : requestJson;
                            Console.WriteLine($"PIPE IN <- {logMsg}");
                        }
                        catch (Exception decodeEx)
                        {
                            Console.WriteLine($"Error decoding request bytes: {decodeEx.Message}. Bytes: {BitConverter.ToString(requestBytes)}");
                            await SendErrorResponseAsync(pipeServer, "Invalid byte sequence.", cancellationToken);
                            continue;
                        }

                        ServerResponse response = await ProcessRequestJsonAsync(requestJson);

                        string responseJson = JsonSerializer.Serialize(response, new JsonSerializerOptions { WriteIndented = false });
                        byte[] responseBytes = Encoding.UTF8.GetBytes(responseJson + '\n');

                        try
                        {
                            await pipeServer.WriteAsync(responseBytes.AsMemory(0, responseBytes.Length), cancellationToken).ConfigureAwait(false);
                            await pipeServer.FlushAsync(cancellationToken).ConfigureAwait(false);
                            Console.WriteLine($"PIPE OUT -> {responseJson}");
                        }
                        catch (OperationCanceledException) { throw; }
                        catch (IOException ioEx) { Console.WriteLine($"IO Error during write (client likely disconnected): {ioEx.Message}"); throw; }
                        catch (ObjectDisposedException) { Console.WriteLine("Pipe was disposed during write."); throw; }
                        catch (Exception writeEx) { Console.WriteLine($"Unexpected error during write: {writeEx.Message}"); throw; }

                        if (messageBuffer.Count == 0) break; // Buffer is empty, wait for more data
                    }
                }
                Console.WriteLine("Exited client communication loop normally.");
            }
            catch (OperationCanceledException) { Console.WriteLine("Client communication handling cancelled."); }
            catch (Exception ex) { Console.WriteLine($"Unhandled error during client communication handling: {ex}"); }
        }

        private async Task SendErrorResponseAsync(NamedPipeServerStream pipe, string errorMessage, CancellationToken ct)
        {
            try
            {
                var errorResponse = new ServerResponse { Status = "Error", Message = errorMessage };
                string errorJson = JsonSerializer.Serialize(errorResponse);
                byte[] errorBytes = Encoding.UTF8.GetBytes(errorJson + '\n');
                if (pipe.IsConnected) // Check before writing
                {
                    await pipe.WriteAsync(errorBytes.AsMemory(), ct).ConfigureAwait(false);
                    await pipe.FlushAsync(ct).ConfigureAwait(false);
                    Console.WriteLine($"PIPE OUT -> {errorJson} (Error)");
                }
                else
                {
                    Console.WriteLine($"Could not send error response ('{errorMessage}'): Pipe not connected.");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Failed to send error response ('{errorMessage}'): {ex.Message}");
            }
        }

        private async Task<ServerResponse> ProcessRequestJsonAsync(string requestJson)
        {
            ClientRequest? request = null;
            try
            {
                request = JsonSerializer.Deserialize<ClientRequest>(requestJson.Trim());
                if (request == null || string.IsNullOrWhiteSpace(request.Command))
                {
                    return new ServerResponse { Status = "Error", Message = "Invalid request format or empty command." };
                }
                Console.WriteLine($"Processing command: {request.Command}");
                return await ProcessCommandAsync(request);
            }
            catch (JsonException jsonEx)
            {
                Console.WriteLine($"JSON Deserialization Error: {jsonEx.Message}");
                return new ServerResponse { Status = "Error", Message = $"Invalid JSON request: {jsonEx.Message}" };
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error Processing Command '{request?.Command ?? "Unknown"}': {ex}");
                return new ServerResponse { Status = "Error", Message = $"Failed to execute command '{request?.Command ?? "Unknown"}': {ex.Message}" };
            }
        }

        private static int GetIntParam(JsonNode? parameters, string key, int defaultValue = 0)
        {
            try { return parameters?[key]?.GetValue<int>() ?? defaultValue; }
            catch { Console.WriteLine($"Warning: Could not parse int param '{key}', using default {defaultValue}."); return defaultValue; }
        }
        private static double GetDoubleParam(JsonNode? parameters, string key, double defaultValue = 0.0)
        {
            try { return parameters?[key]?.GetValue<double>() ?? defaultValue; }
            catch { Console.WriteLine($"Warning: Could not parse double param '{key}', using default {defaultValue}."); return defaultValue; }
        }
        private static string GetStringParam(JsonNode? parameters, string key, string defaultValue = "")
        {
            try { return parameters?[key]?.GetValue<string>() ?? defaultValue; }
            catch { Console.WriteLine($"Warning: Could not parse string param '{key}', using default '{defaultValue}'."); return defaultValue; }
        }
        private static bool GetBooleanParam(JsonNode? parameters, string key, bool defaultValue = false)
        {
            try { return parameters?[key]?.GetValue<bool>() ?? defaultValue; }
            catch { Console.WriteLine($"Warning: Could not parse bool param '{key}', using default {defaultValue}."); return defaultValue; }
        }

        private async Task<ServerResponse> ProcessCommandAsync(ClientRequest request)
        {
            JsonNode? resultNode = null;
            string status = "Success";
            string? message = null;

            try
            {
                JsonNode? p = request.Params;

                switch (request.Command)
                {
                    case "Ping":
                        resultNode = JsonNode.Parse($@"{{ ""message"": ""Pong from C#! Service is running."", ""pid"": {Environment.ProcessId} }}");
                        message = "Ping successful.";
                        break;

                    case "GetScreenSize":
                        Size size = OSInteractions.GetScreenSize();
                        resultNode = JsonNode.Parse($@"{{ ""width"": {size.Width}, ""height"": {size.Height} }}");
                        break;

                    case "GetPixelColor":
                        int px = GetIntParam(p, "x");
                        int py = GetIntParam(p, "y");
                        string? colorHex = OSInteractions.GetPixelColor(px, py);
                        if (colorHex != null)
                        {
                            resultNode = JsonNode.Parse($@"{{ ""color_hex"": ""{colorHex}"" }}");
                        }
                        else
                        {
                            status = "Error"; message = $"Failed to get pixel color at ({px},{py}).";
                        }
                        break;

                    case "CaptureRegion":
                        int x1 = GetIntParam(p, "x1");
                        int y1 = GetIntParam(p, "y1");
                        Size currentScreenSize = OSInteractions.GetScreenSize();
                        int x2 = GetIntParam(p, "x2", currentScreenSize.Width);
                        int y2 = GetIntParam(p, "y2", currentScreenSize.Height);
                        bool useGray = GetBooleanParam(p, "useGrayscale");
                        bool useBin = GetBooleanParam(p, "useBinarization");

                        byte[]? imgBytes = OSInteractions.CaptureRegionAndPreprocess(x1, y1, x2, y2, useGray, useBin);

                        if (imgBytes != null)
                        {
                            Rectangle virtualScreen = OSInteractions.GetVirtualScreenBounds();
                            int actualX1 = Math.Max(virtualScreen.Left, Math.Min(virtualScreen.Right, x1));
                            int actualY1 = Math.Max(virtualScreen.Top, Math.Min(virtualScreen.Bottom, y1));
                            int actualX2 = Math.Max(virtualScreen.Left, Math.Min(virtualScreen.Right, x2));
                            int actualY2 = Math.Max(virtualScreen.Top, Math.Min(virtualScreen.Bottom, y2));
                            if (actualX2 < actualX1) actualX2 = actualX1;
                            if (actualY2 < actualY1) actualY2 = actualY1;

                            string base64Image = Convert.ToBase64String(imgBytes);
                            resultNode = new JsonObject
                            {
                                ["captured_image_bytes"] = base64Image,
                                ["actual_x1"] = actualX1,
                                ["actual_y1"] = actualY1,
                                ["actual_x2"] = actualX2,
                                ["actual_y2"] = actualY2
                            };
                        }
                        else
                        {
                            status = "Error"; message = "Screen capture or preprocessing failed.";
                        }
                        break;

                    case "SimulateClick":
                        OSInteractions.SimulateClick(
                            GetIntParam(p, "x"), GetIntParam(p, "y"),
                            GetStringParam(p, "button", "left"),
                            GetStringParam(p, "click_type", "single"),
                            GetDoubleParam(p, "hold_duration"));
                        message = "Click simulated.";
                        break;

                    case "SimulateMouseMove":
                        OSInteractions.SimulateMouseMove(
                            GetIntParam(p, "x"), GetIntParam(p, "y"),
                            GetDoubleParam(p, "duration", 0.1));
                        message = "Mouse move simulated.";
                        break;

                    case "SimulateDrag":
                        OSInteractions.SimulateDrag(
                           GetIntParam(p, "end_x"), GetIntParam(p, "end_y"),
                           GetStringParam(p, "button", "left"),
                           GetDoubleParam(p, "duration_seconds", 0.1));
                        message = "Drag simulated.";
                        break;

                    case "SimulateScroll":
                        OSInteractions.SimulateScroll(
                            GetIntParam(p, "scroll_amount"),
                            GetStringParam(p, "direction", "vertical"));
                        message = "Scroll simulated.";
                        break;

                    case "SimulateKeyPress":
                        string keyPressName = GetStringParam(p, "key_name");
                        if (string.IsNullOrWhiteSpace(keyPressName)) { status = "Error"; message = "Missing 'key_name' for KeyPress."; }
                        else { OSInteractions.SimulateKeyPress(keyPressName); message = $"KeyPress '{keyPressName}' simulated."; }
                        break;

                    case "SimulateKeyDown":
                        string keyDownName = GetStringParam(p, "key_name");
                        if (string.IsNullOrWhiteSpace(keyDownName)) { status = "Error"; message = "Missing 'key_name' for KeyDown."; }
                        else { OSInteractions.SimulateKeyDown(keyDownName); message = $"KeyDown '{keyDownName}' simulated."; }
                        break;

                    case "SimulateKeyUp":
                        string keyUpName = GetStringParam(p, "key_name");
                        if (string.IsNullOrWhiteSpace(keyUpName)) { status = "Error"; message = "Missing 'key_name' for KeyUp."; }
                        else { OSInteractions.SimulateKeyUp(keyUpName); message = $"KeyUp '{keyUpName}' simulated."; }
                        break;

                    case "SimulateTextEntry":
                        OSInteractions.SimulateTextEntry(GetStringParam(p, "text"));
                        message = "Text entry simulated.";
                        break;

                    case "SimulateModifiedKeyStroke":
                        string modKey = GetStringParam(p, "modifier");
                        string mainKey = GetStringParam(p, "main_key");
                        if (string.IsNullOrWhiteSpace(modKey) || string.IsNullOrWhiteSpace(mainKey)) { status = "Error"; message = "Missing 'modifier' or 'main_key'."; }
                        else { OSInteractions.SimulateModifiedKeyStroke(modKey, mainKey); message = $"ModifiedKeyStroke '{modKey}+{mainKey}' simulated."; }
                        break;

                    case "CheckWindowExists":
                        string? className = GetStringParam(p, "class_name", "");
                        string? windowTitle = GetStringParam(p, "window_title", "");
                        if (string.IsNullOrWhiteSpace(className) && string.IsNullOrWhiteSpace(windowTitle)) { status = "Error"; message = "Both 'class_name' and 'window_title' are empty."; }
                        else
                        {
                            bool wFound = OSInteractions.CheckWindowExists(className, windowTitle);
                            resultNode = new JsonObject { ["exists"] = wFound };
                        }
                        break;

                    case "CheckProcessExists":
                        string procName = GetStringParam(p, "process_name");
                        if (string.IsNullOrWhiteSpace(procName)) { status = "Error"; message = "Missing 'process_name'."; }
                        else
                        {
                            bool pFound = OSInteractions.CheckProcessExists(procName);
                            resultNode = new JsonObject { ["exists"] = pFound };
                        }
                        break;

                    case "StartInteractiveDrawingCapture":
                        Console.WriteLine("Received StartInteractiveDrawingCapture command.");
                        Task<string?> drawingTask = OSInteractions.StartInteractiveDrawingCapture();
                        string? drawingJsonResult = await drawingTask.ConfigureAwait(false);
                        Console.WriteLine($"Interactive Drawing Capture completed. Result: {(drawingJsonResult == null ? "NULL/Cancelled" : "Data returned")}");
                        if (!string.IsNullOrEmpty(drawingJsonResult))
                        {
                            try { resultNode = JsonNode.Parse(drawingJsonResult); }
                            catch (JsonException je)
                            {
                                Console.WriteLine($"JSON Parse error for drawing result: {je.Message}");
                                status = "Error"; message = "Drawing data from service was invalid JSON."; resultNode = null;
                            }
                        }
                        message = (drawingJsonResult != null) ? "Drawing captured." : "Drawing cancelled or no data.";
                        break;

                    case "StartInteractiveRegionSelect":
                        Console.WriteLine("Received StartInteractiveRegionSelect command.");
                        Task<string?> regionTask = OSInteractions.StartInteractiveRegionSelect();
                        string? regionJsonResult = await regionTask.ConfigureAwait(false);
                        Console.WriteLine($"Interactive Region Select completed. Result: {(regionJsonResult == null ? "NULL/Cancelled" : "Data returned")}");
                        if (!string.IsNullOrEmpty(regionJsonResult))
                        {
                            try { resultNode = JsonNode.Parse(regionJsonResult); }
                            catch (JsonException je)
                            {
                                Console.WriteLine($"JSON Parse error for region result: {je.Message}");
                                status = "Error"; message = "Region data from service was invalid JSON."; resultNode = null;
                            }
                        }
                        message = (regionJsonResult != null) ? "Region selected." : "Region selection cancelled or no data.";
                        break;

                    case "StartInteractivePointSelect":
                        int numPoints = GetIntParam(p, "num_points", 1);
                        Console.WriteLine($"Received StartInteractivePointSelect command for {numPoints} points.");
                        Task<string?> pointsTask = OSInteractions.StartInteractivePointSelect(numPoints);
                        string? pointsJsonResult = await pointsTask.ConfigureAwait(false);
                        Console.WriteLine($"Interactive Point Select completed. Result: {(pointsJsonResult == null ? "NULL/Cancelled" : "Data returned")}");
                        if (!string.IsNullOrEmpty(pointsJsonResult))
                        {
                            try { resultNode = JsonNode.Parse(pointsJsonResult); }
                            catch (JsonException je)
                            {
                                Console.WriteLine($"JSON Parse error for points result: {je.Message}");
                                status = "Error"; message = "Point data from service was invalid JSON."; resultNode = null;
                            }
                        }
                        message = (pointsJsonResult != null) ? $"{numPoints} point(s) selected." : "Point selection cancelled or no data.";
                        break;

                    default:
                        status = "Error";
                        message = $"Unknown command received: {request.Command}";
                        Console.WriteLine(message);
                        break;
                }
                return new ServerResponse { Status = status, Message = message, Result = resultNode };
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Exception processing command '{request?.Command ?? "Unknown"}': {ex}");
                return new ServerResponse { Status = "Error", Message = $"Internal server error processing command '{request?.Command ?? "Unknown"}': {ex.Message}" };
            }
        }
    }

    public class Program
    {
        private const string DefaultPipeName = "AutoClickerEnhanced_OS_Interaction_Pipe";
        private static CancellationTokenSource _cts = new CancellationTokenSource();

        public static async Task Main(string[] args)
        {
            Console.WriteLine($"DEBUG CSPROGRAM: Main started. Process ID: {Environment.ProcessId}. Timestamp: {DateTime.Now}");
            Console.Title = "OS Interaction Service";
            string pipeName = DefaultPipeName;

            Console.WriteLine("------------------------------------------");
            Console.WriteLine(" OS Interaction Service for AutoClicker   ");
            Console.WriteLine($" Pipe Name: {pipeName}                   ");
            Console.WriteLine(" Status: Starting...                      ");
            Console.WriteLine("------------------------------------------");
            Console.WriteLine("Press Ctrl+C to stop the service.");

            Console.CancelKeyPress += (sender, e) =>
            {
                e.Cancel = true; // Prevent default OS termination
                Console.WriteLine("\nShutdown requested via Ctrl+C...");
                try { _cts.Cancel(); } catch (ObjectDisposedException) { /* Already disposed */ }
            };

            try
            {
                PipeServer server = new PipeServer(pipeName);
                await server.StartAsync(_cts.Token);
            }
            catch (OperationCanceledException)
            {
                Console.WriteLine("Server task was cancelled successfully (expected on shutdown).");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"FATAL ERROR in service: {ex.GetType().Name} - {ex.Message}");
                Console.WriteLine(ex.StackTrace);
            }
            finally
            {
                if (!_cts.IsCancellationRequested)
                {
                    try { _cts.Cancel(); } catch (ObjectDisposedException) { /* Already disposed */ }
                }
                _cts.Dispose(); // Dispose the CancellationTokenSource
                Console.WriteLine("------------------------------------------");
                Console.WriteLine(" OS Interaction Service has shut down.    ");
                Console.WriteLine("------------------------------------------");
                // Short delay to allow console messages to flush before the window might close
                await Task.Delay(200);
            }
        }
    }
}
