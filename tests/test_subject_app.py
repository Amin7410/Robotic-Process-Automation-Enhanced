import tkinter as tk
import time

class TestSubjectApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Clicker Test Subject")
        self.root.geometry("600x400")
        
        # 1. Color Zone (Red Square)
        self.color_params = {"color": "red", "width": 100, "height": 100}
        self.color_canvas = tk.Canvas(root, width=100, height=100, bg="white", highlightthickness=0)
        self.color_canvas.place(x=50, y=50)
        self.color_canvas.create_rectangle(0, 0, 100, 100, fill="red", outline="red")
        self.color_label = tk.Label(root, text="Color Zone (Red)")
        self.color_label.place(x=50, y=155)

        # 2. Text Zone (OCR Target)
        self.text_label_target = tk.Label(root, text="AUTO_CLICKER_TARGET", font=("Arial", 20, "bold"))
        self.text_label_target.place(x=250, y=50)
        self.text_desc = tk.Label(root, text="Text Zone")
        self.text_desc.place(x=250, y=90)

        # 3. Interactive Button
        self.btn = tk.Button(root, text="Click Me", command=self.on_click, width=15, height=2)
        self.btn.place(x=50, y=250)
        
        self.btn_status = tk.Label(root, text="Not Clicked")
        self.btn_status.place(x=180, y=260)

        # 4. Input Field
        self.input_entry = tk.Entry(root, width=30)
        self.input_entry.place(x=50, y=320)
        self.input_desc = tk.Label(root, text="Input Zone")
        self.input_desc.place(x=250, y=320)

        # 5. Coordinate Info (Helper)
        self.root.bind('<Motion>', self.update_coords)
        self.coord_label = tk.Label(root, text="X: 0, Y: 0")
        self.coord_label.pack(side="bottom")

    def on_click(self):
        self.btn.config(text="Clicked!", bg="green", fg="white")
        self.btn_status.config(text="Success: Clicked")

    def update_coords(self, event):
        self.coord_label.config(text=f"X: {event.x}, Y: {event.y}")

if __name__ == "__main__":
    root = tk.Tk()
    app = TestSubjectApp(root)
    
    # Force focus and update to get coordinates
    root.focus_force()
    root.update()
    
    # Print content area absolute position
    # The runner will capture this to know where to click
    print(f"WINDOW_COORDS:{root.winfo_rootx()},{root.winfo_rooty()}")
    sys.stdout.flush()
    
    root.mainloop()
