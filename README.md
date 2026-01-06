Auto Clicker Enhanced: A Powerful UI Automation Tool

![alt text](https://img.shields.io/badge/Python-3.8%2B-blue.svg?logo=python&logoColor=white)

![alt text](https://img.shields.io/badge/C%23-.NET-purple.svg?logo=csharp&logoColor=white)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> [!IMPORTANT]
> **PROJECT STATUS: INDEFINITELY SUSPENDED**
>
> After careful consideration, I have decided to **indefinitely suspend** the development and maintenance of this project.
>
> While this project served as a significant milestone as my first major endeavor as a student—providing immense practical value and critical software engineering lessons—the current pace of technological advancement has outstripped the project's original architectural vision. Continuing development in its current state would yield diminishing returns relative to the resources required, without achieving the technological breakthroughs initially envisioned.
>
> This is a strategic pause rather than an abandonment. I intend to revisit this concept when the timing is right and I have acquired the advanced capabilities necessary to fully realize the potential of this tool.
>
> Thank you for your interest and support.

## Table of Contents
- Introduction
- Features
- Architecture
- Installation
- System Requirements
- Installation Steps
- Usage
- Configuration
- Profiles
- C# Service Path
- Tesseract OCR
- Project Structure
- Contribution
- License
- Contact

## Introduction

Auto Clicker Enhanced is a versatile user interface (UI) automation application designed to simplify and accelerate repetitive tasks on your computer. By combining the power of Python for flexible UI and business logic with C# for low-level interaction with the Windows operating system, this tool provides a reliable and efficient solution for various automation needs.

Whether you need to automate simple mouse clicks, complex key sequences, text input, or intricate workflows based on screen states, Auto Clicker Enhanced can handle it all. With advanced features such as AI Brain and Drawing Templates, it opens the door to more intelligent and adaptive automation scenarios.

⚠️ **Status of Project:**  
The current codebase prioritizes functionality, experimentation, and system behavior exploration over strict clean code practices. As a result, parts of the application may contain tightly coupled components, large modules, and technical debt.

## Features

    Jobs:
        Create and manage sequential action chains to perform automation tasks.
        Triggered by hotkeys or automatically via Triggers.
        Configurable run conditions: infinite loops, run N times, or within a specific time range.
        
    Actions:
        Perform multiple types of UI interactions:
        Mouse clicks: single, double, press/release at specific coordinates.
        Mouse movement: move cursor to coordinates with customizable duration.
        Drag & drop: simulate drag-and-drop operations.
        Scroll: vertical or horizontal
        Key press: press a single key.
        Key down/up: hold down or release a key.
        Text input: type a text string.
        Key combinations: simulate combinations (e.g., Ctrl+C).
        Wait: pause execution for a specified time.
        Conditional Logic (If-Then-Else): each actioncan have an assigned condition; the job flow can branch based on the result (next_action_index_if_condition_met/_not_met).
        Absolute Actions: actions marked as "absolute" will retry until success or until retry limit is reached if their conditions are not met.
        Fallback Sequence: define backup actions to execute if the main action fails or the absolute action conditions are not met
    
    Conditions:
        Flexible state checks to control Job and Trigger logic:
        Pixel color at a position
        Image on screen: detect the presence of an image in a region (using template or feature matching).
        Text on screen: recognize text in a region via OCR (supports Regex, case sensitivity, whitelist, custom dictionary).
        Window existence: check for a window by name or class.
        Process existence: check if a process is running.
        Relative region text: OCR text within a region defined relative to an anchor image.
        Color percentage in a region.
        Multiple image patterns: detect complex patterns of sub-images positioned relative to an anchor image.
        Shared conditions: define once and reuse across multiple Jobs or Triggers.
    
    Triggers:
        Automatically start Jobs or specific actions when one or more conditions are met.
        AND/OR logic for multiple conditions.
        Customizable check frequency.
    
    AI Brain:
        An advanced mode that continuously monitors specific conditions.
        Create "AI Triggers" whose logic is evaluated based on aggregated and updated condition states, enabling adaptive and faster automation.
        Drawing Templates:
        Record mouse paths or drawings by drawing directly on the screen using an interactive interface.
        Import mouse path data from JSON.
        Automatically convert these drawings into sequences of move_mouse and click actions with customizable speed and delay.
        Reuse "Drawing Blocks" in any Job.
    
    Profiles:
        Manage multiple complete automation configurations (Jobs, Triggers, Shared Conditions, Drawing Templates).
        Easily switch between profiles for different tasks or environments.
        Reliable low-level OS interaction:
        Uses a backend service written in C# (Windows) to perform mouse/keyboard operations and interact with the system.
        Communication via Named Pipes ensures reliability, high performance, and avoids conflicts common with pure Python UI automation.
        Supports interactive windows (transparent overlays) for selecting points, regions, or drawing paths visually.

## Architecture

The project uses a layered architecture combining Python and C# to leverage the strengths of each language:

    graph TD
    subgraph Python Layer
        A[GUI (Tkinter)] --> B(JobManager)
        B --> C(Observer)
        B --> D(JobExecutor)
        D --> E(Actions)
        E --> F(Conditions)
        F --> G(OS Interaction Client<br>(Python Bridge))
        C --> G
        C --> B
        B --> G
        H(Utilities<br>ConfigLoader, ImageStorage,<br>ImageProcessing, etc.) --> B
        H --> F
    end
    subgraph C# Layer (OS Interaction Service)
        I(Named Pipe Server<br>(Program.cs)) <--> J(OS Interactions<br>(OSInteractions.cs))
        J --> K(Interactive Capture Service<br>(InteractiveCaptureService.cs))
        J --> L(Windows API / InputSimulatorStandard)
    end
    G <--> I
Python Layer:

    main.py: Application entry point, initializes core components and starts the C# service.

    GUI (Tkinter): Interactive UI built on modules like gui/job_list, gui/job_edit, gui/trigger_list, etc.

    JobManager: Central coordinator managing all Jobs, Triggers, Shared Conditions, and Profiles. Communicates with ConfigLoader for saving/loading data and controls JobExecutor and Observer.

    Observer: Runs in a background thread, manages Triggers, and maintains "world state" for AI Brain.

    JobExecutor: Runs in a separate thread per Job, executing actions sequentially and handling branching logic.

    Actions & Conditions: Core logic definitions for automation actions and conditions.

    Python-C# Bridge (python_csharp_bridge.py): Python client communicating with the C# service via Named Pipes; translates Python requests into JSON and decodes responses.

    Utilities: Helper modules for configuration management, image storage, image processing, color analysis, and drawing path conversion.

C# Layer (OS Interaction Service):

    A console application running in the background.

    Named Pipe Server: Defined in server/Program.cs, listens for JSON requests from Python.

    OS Interactions: Low-level OS interactions implemented using WinAPI (via P/Invoke) and InputSimulatorStandard library.

    Interactive Capture Service: Handles advanced interactions like region selection, point selection, and interactive drawing using transparent overlays and global hooks.

    Communication Protocol: Defined in server/Protocol.cs (JSON request/response).

## Installation

System Requirements:
- OS: Windows 10/11 (Named Pipe and low-level OS interactions implemented specifically for Windows).
- Python: Python 3.8 or higher.
- .NET SDK: .NET 8 SDK or higher (to build the C# service).
- Tesseract OCR: Install if you want to use text recognition conditions.

Installation Steps:

Clone the repository:
    cd <your-project_directory>
    git clone <https://github.com/Amin7410/ACE.git>

Download library:
    pip install -r requirements.txt

Build the C# OS Interaction Service:
+ Navigate to the C# project directory (server/).
+ Build in Debug or Release mode for Windows:

    cd server
    dotnet publish -c Debug -r win-x64 --self-contained false

After building, the executable will be in e.g.: server/bin/Debug/net9.0-windows/server.exe.
Configure the C# executable path in main.py:
+ Open main.py in the project root.
+ Find CSHARP_EXE_PATH_RELATIVE = ... and update it with the relative path to the built server.exe.
+ Example:
+ CSHARP_EXE_PATH_RELATIVE = os.path.join("server", "bin", "Debug", "net9.0-windows", CSHARP_EXE_NAME)

Install and configure Tesseract OCR (optional):
+ Download and install from GitHub.
+ Ensure tesseract.exe is in the system PATH, OR
+ Configure the path directly in core/condition.py (pytesseract.pytesseract.tesseract_cmd = ...).

## Usage

To start the application:

python main.py


The Tkinter GUI will launch.

    Create Jobs: Use the "Job List" tab to add new Jobs, edit actions, hotkeys, and run conditions.

    Create Triggers: Use the "Triggers" tab to define auto-trigger conditions.

    Manage Shared Conditions: Use "Shared Conditions" tab for reusable conditions.

    AI Brain: Explore the "AI Brain" tab to configure monitored conditions and AI Triggers. Enable "AI Brain Active" to turn it on.

    Drawing Templates: Create or edit drawing templates in the "Drawing Templates" tab, then add them to Jobs as drawing action blocks.

Profiles:

    The application manages separate configurations (Jobs, Triggers, Conditions, Drawing Templates) as "Profiles".

    Switch between profiles, create new ones, or delete (except default and active) via the Profiles menu.

    Profile files are stored in the profiles/ directory as .profile.json.

C# Service Path:

    This is crucial. The C# service (server.exe) must be found and run correctly. Configured in main.py.

Tesseract OCR:

    If using "Text on Screen" or "Text in Relative Region", ensure Tesseract OCR is installed and accessible.

    Best practice: add its install directory to system PATH.

    Otherwise, manually configure tesseract_cmd in core/condition.py.

## Contribution
Contributions are welcome! To improve this project:
Fork the repository.
Create a new branch: git checkout -b feature/AmazingFeature.
Make your changes.
Commit: git commit -m 'Add some AmazingFeature'.
Push: git push origin feature/AmazingFeature.
Open a Pull Request.

## License
This project is licensed under the GPLv3 License. See the LICENSE file for details.

## Contact
For questions or support, please open an Issue in this repository.
