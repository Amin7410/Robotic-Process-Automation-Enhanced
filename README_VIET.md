Auto Clicker Enhanced: Một Công Cụ Tự Động Hóa UI Mạnh Mẽ 

![alt text](https://img.shields.io/badge/Python-3.8%2B-blue.svg?logo=python&logoColor=white)

![alt text](https://img.shields.io/badge/C%23-.NET-purple.svg?logo=csharp&logoColor=white)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

## Mục lục
- Giới thiệu
- Tính năng
- Kiến trúc
- Cài đặt
- Yêu cầu hệ thống
- Các bước cài đặt
- Cách sử dụng
- Cấu hình
- Hồ sơ (Profiles)
- Đường dẫn dịch vụ C#
- Tesseract OCR
- Cấu trúc dự án
- Đóng góp
- Giấy phép
- Liên hệ


## Giới thiệu
Auto Clicker Enhanced là một ứng dụng tự động hóa giao diện người dùng (UI automation) đa năng, được thiết kế để đơn giản hóa và tăng tốc các tác vụ lặp đi lặp lại trên máy tính của bạn. Bằng cách kết hợp sức mạnh của Python cho giao diện người dùng linh hoạt và logic nghiệp vụ, cùng với C# cho tương tác cấp thấp với hệ điều hành Windows, công cụ này cung cấp một giải pháp đáng tin cậy và hiệu quả cho nhiều nhu cầu tự động hóa.
Dù bạn cần tự động hóa các cú nhấp chuột đơn giản, chuỗi phím phức tạp, nhập liệu văn bản, hoặc các luồng công việc phức tạp dựa trên trạng thái màn hình, Auto Clicker Enhanced đều có thể xử lý. Với các tính năng nâng cao như AI Brain và Drawing Templates, nó mở ra cánh cửa cho các kịch bản tự động hóa thông minh và trực quan hơn.

## Tính năng
    Jobs (Công việc):
        Tạo và quản lý các chuỗi hành động tuần tự để thực hiện các tác vụ tự động hóa.
        Kích hoạt bằng phím nóng (hotkey) hoặc tự động qua Triggers.
        Cấu hình điều kiện chạy: chạy vô hạn, chạy N lần, hoặc chạy trong một khoảng thời gian cụ thể.

    Actions (Hành động):
        Thực hiện nhiều loại tương tác UI:
        Click chuột: Nhấp đơn, nhấp đúp, nhấn giữ/nhả chuột tại tọa độ cụ thể.
        Di chuyển chuột: Di chuyển chuột đến tọa độ với thời gian tùy chỉnh.
        Kéo thả: Mô phỏng thao tác kéo và thả chuột.
        Cuộn: Cuộn dọc hoặc ngang.
        Nhấn phím: Nhấn một phím duy nhất.
        Nhấn giữ/nhả phím: Giữ phím xuống hoặc nhả phím lên.
        Nhập văn bản: Gõ một chuỗi văn bản.
        Tổ hợp phím: Mô phỏng các tổ hợp phím (ví dụ: Ctrl+C).
        Wait (Chờ): Dừng thực thi trong một khoảng thời gian.
        Logic Điều kiện (If-Then-Else): Mỗi hành động có thể có một điều kiện được gán; luồng Job có thể rẽ nhánh dựa trên kết quả điều kiện (next_action_index_if_condition_met/_not_met).
        Absolute Actions (Hành động Tuyệt đối): Hành động được đánh dấu là "tuyệt đối" sẽ cố gắng thực hiện lại nhiều lần nếu điều kiện của nó không được đáp ứng, cho đến khi thành công hoặc đạt giới hạn thử lại.
        Fallback Sequence (Chuỗi dự phòng): Định nghĩa một chuỗi các hành động dự phòng sẽ được thực thi nếu điều kiện của hành động chính không được đáp ứng hoặc hành động tuyệt đối thất bại sau các lần thử lại.

    Conditions (Điều kiện):
        Các kiểm tra trạng thái linh hoạt để điều khiển logic Job và Triggers:
        Màu sắc tại vị trí: Kiểm tra màu pixel tại một tọa độ.
        Hình ảnh trên màn hình: Phát hiện sự hiện diện của một hình ảnh trong một vùng màn hình (sử dụng Template Matching hoặc Feature Matching).
        Văn bản trên màn hình: Nhận dạng văn bản trong một vùng bằng OCR (hỗ trợ Regex, phân biệt chữ hoa/thường, danh sách trắng ký tự, từ điển người dùng).
        Cửa sổ tồn tại: Kiểm tra sự hiện diện của một cửa sổ theo tên hoặc lớp.
        Tiến trình tồn tại: Kiểm tra xem một tiến trình có đang chạy không.
        Văn bản trong vùng tương đối: Nhận dạng văn bản trong một vùng được xác định tương đối với một hình ảnh neo (anchor image).
        Màu sắc trong vùng (%): Phân tích phần trăm pixel của một hoặc nhiều màu cụ thể trong một vùng được định nghĩa.
        Mẫu nhiều hình ảnh: Phát hiện một mẫu phức tạp gồm nhiều hình ảnh nhỏ (sub-images) được định vị tương đối với một hình ảnh neo lớn hơn (anchor image).
        Điều kiện chia sẻ: Định nghĩa các điều kiện một lần và tái sử dụng chúng trên nhiều Jobs hoặc Triggers.

    Triggers (Kích hoạt):
        Tự động khởi chạy Jobs hoặc các hành động cụ thể khi một hoặc nhiều điều kiện được đáp ứng.
        Logic AND hoặc OR cho nhiều điều kiện.
        Tần suất kiểm tra có thể tùy chỉnh.

    AI Brain (Chế độ Trí tuệ nhân tạo):
        Một chế độ nâng cao cho phép bạn đánh dấu các điều kiện cụ thể để "AI Brain" theo dõi liên tục trạng thái của chúng.
        Tạo các "AI Triggers" mà logic của chúng được đánh giá dựa trên trạng thái tổng hợp và cập nhật của các điều kiện được theo dõi, thay vì kiểm tra từng điều kiện riêng lẻ mỗi lần. Điều này mang lại khả năng tự động hóa thích ứng và phản ứng nhanh hơn.

    Drawing Templates (Mẫu vẽ):
        Ghi lại các đường đi chuột hoặc hình vẽ bằng cách vẽ trực tiếp trên màn hình thông qua một giao diện tương tác.
        Nhập dữ liệu đường đi chuột từ JSON.
        Tự động chuyển đổi các nét vẽ này thành một chuỗi các hành động move_mouse và click tương ứng, có thể tùy chỉnh tốc độ và độ trễ.
        Tái sử dụng các "Drawing Blocks" này trong bất kỳ Job nào.

    Profiles (Hồ sơ):
        Quản lý nhiều bộ cấu hình tự động hóa hoàn chỉnh (Jobs, Triggers, Shared Conditions, Drawing Templates).
        Dễ dàng chuyển đổi giữa các hồ sơ khác nhau cho các tác vụ hoặc môi trường khác nhau.
        Tương tác OS cấp thấp đáng tin cậy:
        Sử dụng một dịch vụ phụ trợ được viết bằng C# (Windows) để thực hiện các thao tác chuột/bàn phím và tương tác với hệ thống.
        Giao tiếp qua Named Pipes để đảm bảo độ tin cậy, hiệu suất cao và khả năng tránh các xung đột thường gặp khi tự động hóa UI bằng Python thuần túy.
        Hỗ trợ các cửa sổ tương tác (overlay trong suốt) để chọn điểm, vùng, hoặc vẽ đường đi trên màn hình một cách trực quan.

## Kiến trúc

Dự án sử dụng kiến trúc phân tầng kết hợp Python và C# để tận dụng tối đa thế mạnh của từng ngôn ngữ:

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

    main.py: Điểm vào ứng dụng, khởi tạo các thành phần chính và khởi động dịch vụ C#.
    
    GUI (Tkinter): Cung cấp giao diện người dùng tương tác, được xây dựng trên các module như gui/job_list, gui/job_edit, gui/trigger_list, v.v.
    
    JobManager: Trung tâm điều phối chính, quản lý tất cả Jobs, Triggers, Shared Conditions và Profile. Nó giao tiếp với ConfigLoader để lưu/tải dữ liệu và điều khiển các JobExecutor và Observer.
    
    Observer: Chạy trong một luồng nền, chịu trách nhiệm quản lý và kích hoạt các Triggers, đồng thời duy trì "trạng thái thế giới" cho tính năng AI Brain.
    
    JobExecutor: Chạy trong một luồng riêng cho mỗi Job, thực thi các hành động của Job theo tuần tự và logic rẽ nhánh.
    
    Actions & Conditions: Các định nghĩa logic cốt lõi cho các hành động và điều kiện tự động hóa.
    
    Python C# Bridge (python_csharp_bridge.py): Lớp client Python chịu trách nhiệm giao tiếp với dịch vụ C# thông qua Named Pipes. Nó dịch các yêu cầu 
    
    Python thành định dạng JSON và gửi đi, sau đó nhận và giải mã phản hồi.
    
    Utilities: Các module hỗ trợ cho việc quản lý cấu hình, lưu trữ hình ảnh, xử lý hình ảnh, phân tích màu sắc và chuyển đổi nét vẽ.
    
C# Layer (OS Interaction Service):

    Một ứng dụng console chạy ẩn dưới dạng dịch vụ. 
    
    Named Pipe Server: Được thiết lập trong sever/Program.cs, lắng nghe các kết nối và yêu cầu JSON từ Python thông qua Named Pipes.
    
    OS Interactions: Module cốt lõi thực hiện các tương tác cấp thấp với hệ điều hành Windows bằng cách sử dụng WinAPI (thông qua P/Invoke) và thư viện 
    
    InputSimulatorStandard để giả lập chuột/bàn phím.
    
    Interactive Capture Service: Một module C# chuyên biệt xử lý các tương tác phức tạp hơn như chọn vùng, chọn điểm, và vẽ tương tác trên màn hình bằng cách hiển thị các lớp phủ (overlay) trong suốt và sử dụng Global Hooks.

    Communication Protocol: Được định nghĩa trong sever/Protocol.cs (JSON request/response).

## Cài đặt

Yêu cầu hệ thống
- Hệ điều hành: Windows 10/11 (Named Pipe và các tương tác OS cấp thấp được triển khai cụ thể cho Windows).
- Python: Python 3.8 trở lên.
- .NET SDK: .NET 8 SDK trở lên (để build dịch vụ C#).
- Tesseract OCR: Cài đặt Tesseract OCR nếu bạn muốn sử dụng các tính năng điều kiện nhận dạng văn bản.

Tải thư viện:
    pip install -r requirements.txt

Các bước cài đặt
Clone Repository:
    git clone <thư-mục-dự-án-của-bạn>
    cd <https://github.com/Amin7410/ACE.git>

Cài đặt các gói Python:
    cd .\autoclicker\
    pip install -r requirements.txt

Build dịch vụ C# OS Interaction:
+ Điều hướng đến thư mục chứa project C# (sever/).
+ Build project ở chế độ Debug hoặc Release cho nền tảng Windows.

    cd sever
    dotnet publish -c Debug -r win-x64 --self-contained false

Sau khi build, tệp thực thi sẽ nằm trong thư mục ví dụ: sever/bin/Debug/net9.0-windows/sever.exe.
Cấu hình đường dẫn thực thi C# trong main.py:
+ Mở tệp main.py ở thư mục gốc của dự án Python.
+ Tìm dòng CSHARP_EXE_PATH_RELATIVE = ... và cập nhật đường dẫn tương đối đến tệp sever.exe đã build.
+ Ví dụ: Nếu thư mục dự án của bạn là ACE/ và main.py nằm trong ACE/main.py, còn sever.exe nằm trong ACE/sever/bin/Debug/net9.0-windows/sever.exe, thì đường dẫn tương đối sẽ là:

    CSHARP_EXE_PATH_RELATIVE = os.path.join("sever", "bin", "Debug", "net9.0-windows", CSHARP_EXE_NAME)

(Hoặc os.path.join("..", "sever", "bin", "Debug", "net9.0-windows", CSHARP_EXE_NAME) nếu main.py nằm trong một thư mục con như ACE/src/main.py và sever/ nằm ngang hàng với src/).

Cài đặt và cấu hình Tesseract OCR (Tùy chọn, nếu bạn dùng tính năng văn bản):
+ Tải xuống và cài đặt Tesseract OCR từ GitHub Tesseract.
+ Đảm bảo tesseract.exe nằm trong biến môi trường PATH của hệ thống, HOẶC
+ Cấu hình đường dẫn trực tiếp trong tệp core/condition.py (tìm dòng pytesseract.pytesseract.tesseract_cmd = ...).


## Cách sử dụng

Để khởi chạy ứng dụng:

    python main.py

Ứng dụng sẽ khởi động giao diện người dùng Tkinter.

    Tạo Jobs: Sử dụng tab "Job List" để thêm Jobs mới, chỉnh sửa hành động, hotkey và điều kiện chạy.

    Tạo Triggers: Sử dụng tab "Triggers" để định nghĩa các điều kiện kích hoạt tự động.

    Quản lý điều kiện chia sẻ: Sử dụng tab "Shared Conditions" để tạo và quản lý các điều kiện có thể tái sử dụng.

    AI Brain: Khám phá tab "AI Brain" để định cấu hình các điều kiện được theo dõi và các AI Triggers. Bật "AI Brain Active" để kích hoạt chế độ này.

    Drawing Templates: Tạo hoặc chỉnh sửa các mẫu vẽ trong tab "Drawing Templates", sau đó thêm chúng vào Jobs dưới dạng các khối hành động vẽ.

Cấu hình

    Hồ sơ (Profiles)

    Ứng dụng quản lý các cấu hình riêng biệt (Jobs, Triggers, Conditions, Drawing Templates) thành các "Hồ sơ" (Profiles).

    Bạn có thể chuyển đổi giữa các hồ sơ, tạo hồ sơ mới, hoặc xóa hồ sơ (trừ hồ sơ default và hồ sơ đang hoạt động) thông qua menu Profiles trên thanh menu chính.

    Các file hồ sơ được lưu trữ trong thư mục profiles/ dưới dạng .profile.json.

Đường dẫn dịch vụ C#
    Đây là cài đặt quan trọng nhất. Dịch vụ C# (sever.exe) phải được tìm thấy và chạy đúng cách để ứng dụng hoạt động. Đường dẫn này được cấu hình trong main.py (xem Cài đặt).

Tesseract OCR
    Nếu bạn sử dụng điều kiện "Text on Screen" hoặc "Text in Relative Region", bạn cần đảm bảo Tesseract OCR được cài đặt và có thể truy cập được bởi Python.
    Tốt nhất là thêm thư mục cài đặt Tesseract vào biến môi trường PATH của hệ thống.
    Nếu không, bạn có thể chỉnh sửa thủ công đường dẫn tesseract_cmd trong tệp core/condition.py để trỏ trực tiếp đến tesseract.exe.

======================================================================================================================================================

## Cấu trúc dự án

    ├──autoclicker/
    │   ├── python_csharp_bridge.py
    │   ├── main.py
    │   ├── core/
    │   │   ├── job.py
    │   │   ├── action.py
    │   │   ├── job_run_condition.py
    │   │   ├── condition.py
    │   │   ├── condition_manager.py
    │   │   ├── trigger.py
    │   │   ├── observer.py
    │   │   └── job_executor.py
    │   ├── gui/
    │   │   ├── main_window.py
    │   │   ├── job_list.py
    │   │   ├── job_edit.py
    │   │   ├── action_edit_window.py
    │   │   ├── action_settings.py
    │   │   ├── job_run_condition_settings.py
    │   │   ├── key_recorder.py
    │   │   ├── trigger_list.py
    │   │   ├── trigger_edit.py
    │   │   ├── shared_condition_list.py
    │   │   ├── shared_condition_edit_window.py
    │   │   ├── shape_template_list.py
    │   │   ├── shape_template_editor.py
    │   │   ├── ai_brain_management_tab.py
    │   │   ├── select_target_dialog.py
    │   │   ├── coordinate_capture_window.py
    │   │   ├── drawing_capture_window.py
    │   │   └── screen_capture_window.py
    │   ├── utils/
    │   │   ├── config_loader.py
    │   │   ├── image_storage.py
    │   │   ├── image_processing.py
    │   │   ├── image_analysis.py
    │   │   ├── color_utils.py
    │   │   ├── parsing_utils.py
    │   │   └── drawing_utils.py
    │   └── server/
    │       ├── bin/
    │       ├── obj/
    │       ├── Program.cs
    │       ├── OSInteractions.cs
    │       ├── InteractiveCaptureService.cs
    │       └── server.csproj
    ├── profiles/
    ├── captured_images/
    └── sever/

## Đóng góp
Chào mừng mọi đóng góp! Nếu bạn muốn cải thiện dự án này:
Fork repository.
Tạo một nhánh mới (git checkout -b feature/AmazingFeature).
Thực hiện các thay đổi của bạn.
Commit các thay đổi của bạn (git commit -m 'Add some AmazingFeature').
Push lên nhánh của bạn (git push origin feature/AmazingFeature).
Mở một Pull Request.

## Giấy phép
Dự án này được cấp phép theo Giấy phép GPLv3. Xem tệp `LICENSE` để biết thêm chi tiết.

======================================================================================================================================================

## Liên hệ
Nếu bạn có bất kỳ câu hỏi hoặc cần hỗ trợ, vui lòng mở một Issue trong repository này.
