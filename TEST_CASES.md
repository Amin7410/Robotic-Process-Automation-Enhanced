# Auto Clicker Enhanced - Test Cases & Verification Guide

This document outlines the procedures for verifying the functionality of the Auto Clicker Enhanced system. It includes both automated checks using the provided test suite and manual user acceptance tests (UAT).

## 1. Automated E2E Testing Suite

We have provided an automated test runner that validates the core "Bridge" connection between Python and the C# OS Interaction Service.

### Prerequisites
1.  **Build the C# Project**: Ensure `sever.exe` is built (Debug mode).
    -   Path: `sever/bin/Debug/net9.0-windows/sever.exe`
2.  **Dependencies**: Ensure Python requirements are installed (`pip install -r autoclicker/requirements.txt`).

### Running the Tests
Execute the following command in your terminal from the project root:

```bash
python tests/run_tests.py
```

### What Happens?
1.  **Server Launch**: The script attempts to start `sever.exe`.
2.  **Test App Launch**: A dummy window "Auto Clicker Test Subject" will open.
3.  **Bridge Check**: The script sends a "Ping" / "Get Screen Size" command to the C# service.
    -   *Pass*: You see `[SUCCESS] Bridge Connected!`.
    -   *Fail*: You see connection errors or timeouts.
4.  **Smoke Tests**: The script fires test commands (Pixel Color, OCR placeholder) to ensure the pipe protocol is working.

## 2. Manual Test Cases

Use the **Test Subject App** (`python tests/test_subject_app.py`) as a target for these manual tests.

### TC-01: Basic Click Action
*   **Goal**: Verify mouse clicking works.
*   **Steps**:
    1.  Open `Test Subject App`.
    2.  Open Auto Clicker GUI.
    3.  Create a strict job:
        -   Action: `Mouse Click` (Left).
        -   Target: Pick the "Click Me" button on the Test App using "Pick Point".
    4.  Run the Job.
*   **Expected**: The "Click Me" button turns Green and says "Clicked!".

### TC-02: Color Detection Condition
*   **Goal**: Verify the system can "see" color.
*   **Steps**:
    1.  Create a job with a **Condition**:
        -   Type: `Pixel Color`.
        -   Target: Pick a point inside the Red Square of the Test App.
        -   Color: Pick the red color.
    2.  Action: Click the "Input Field".
    3.  Run the Job.
*   **Expected**: The Input Field gets focused (clicked) ONLY if the red square is visible.

### TC-03: Image Template Matching
*   **Goal**: Verify "Smart Finding" of buttons.
*   **Steps**:
    1.  Take a screenshot of the "Click Me" button and save as `btn.png`.
    2.  Create a job:
        -   Action: `Find Image & Click`.
        -   Image Path: Select `btn.png`.
    3.  Move the Test App window to a different location on screen.
    4.  Run the Job.
*   **Expected**: The mouse automatically hunts down the button's new location and clicks it.

### TC-04: Text Recognition (OCR)
*   **Goal**: Verify Tesseract OCR integration.
*   **Steps**:
    1.  Create a job with **Condition**:
        -   Type: `OCR Text`.
        -   Region: Select the area around "AUTO_CLICKER_TARGET" in the Test App.
        -   Text to find: "TARGET".
    2.  Action: Any.
    3.  Run the Job.
*   **Expected**: The job runs successfully because the text exists.

### TC-05: Macro Recording (Teach Mode)
*   **Goal**: Verify the recording capability.
*   **Steps**:
    1.  Click "Record" on the Auto Clicker.
    2.  Click the "Click Me" button in the Test App manually.
    3.  Type "Hello" in the Input Field.
    4.  Stop Recording.
    5.  Play back the recorded script.
*   **Expected**: The ghost mouse clicks the button and types "Hello" exactly as you did.
