import sys
import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import ctypes
import webbrowser
import urllib.request
import time


# === 新增：PyInstaller 内置资源路径解析函数 ===
def get_resource_path(relative_path):
    """ 获取资源的绝对路径 (兼容开发环境和 PyInstaller 打包后的环境) """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后，会将资源解压到 sys._MEIPASS 指向的临时目录
        return os.path.join(sys._MEIPASS, relative_path)
    # 开发环境下，直接从当前目录读取
    return os.path.join(os.path.abspath("."), relative_path)

# === 核心工具：获取 8.3 短路径 (防闪退神器) ===
def get_short_path(long_path):
    if not os.path.exists(long_path): return long_path
    buf_size = 256
    buf = ctypes.create_unicode_buffer(buf_size)
    GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
    ret = GetShortPathNameW(long_path, buf, buf_size)
    if ret > buf_size:
        buf = ctypes.create_unicode_buffer(ret)
        ret = GetShortPathNameW(long_path, buf, ret)
    return buf.value if ret > 0 else long_path

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Whisper 启动器（又名：这群人在唱or念什么东西）")
        self.geometry("720x650")

        # === 新增：加载内嵌的窗口图标 ===
        icon_path = get_resource_path("栞子.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        # ================================

        self.process = None 
        self.is_running = False
        self.check_timer = None
        
        # 自动查找路径
        base_dir = os.getcwd()
        self.default_model = os.path.join(base_dir, "models", "ggml-large-v3-turbo.bin")
        
        # 自动寻找 exe
        bin_dir = os.path.join(base_dir, "bin")
        possible_exes = ["whisper-server.exe", "server.exe"]
        self.server_exe = os.path.join(bin_dir, "whisper-server.exe")
        if os.path.exists(bin_dir):
            for f in possible_exes:
                if os.path.exists(os.path.join(bin_dir, f)):
                    self.server_exe = os.path.join(bin_dir, f)
                    break

        # --- 界面布局 ---
        # 1. 配置区
        config_frame = tk.LabelFrame(self, text="基础配置")
        config_frame.pack(pady=10, padx=10, fill="x")
        
        tk.Label(config_frame, text="Server程序:").grid(row=0, column=0, sticky="w", padx=5)
        self.exe_path_var = tk.StringVar(value=self.server_exe)
        tk.Entry(config_frame, textvariable=self.exe_path_var, width=60).grid(row=0, column=1, padx=5)
        tk.Button(config_frame, text="...", command=lambda: self.browse_file(self.exe_path_var, "exe")).grid(row=0, column=2)

        tk.Label(config_frame, text="模型路径:").grid(row=1, column=0, sticky="w", padx=5)
        self.model_path_var = tk.StringVar(value=self.default_model)
        tk.Entry(config_frame, textvariable=self.model_path_var, width=60).grid(row=1, column=1, padx=5)
        tk.Button(config_frame, text="...", command=lambda: self.browse_file(self.model_path_var, "bin")).grid(row=1, column=2)

        tk.Label(config_frame, text="端口 (Port):").grid(row=2, column=0, sticky="w", padx=5)
        self.port_var = tk.IntVar(value=8080)
        tk.Entry(config_frame, textvariable=self.port_var, width=10).grid(row=2, column=1, sticky="w", padx=5, pady=5)

        # 2. 控制区
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)
        
        self.btn_start = tk.Button(btn_frame, text="启动服务", command=self.toggle_server, 
                                 bg="#e1f5fe", font=("微软雅黑", 14, "bold"), width=15, height=2)
        self.btn_start.pack(side="left", padx=10)

        self.btn_test = tk.Button(btn_frame, text="打开网页测试", command=self.open_test_page,
                                state="disabled", font=("微软雅黑", 10))
        self.btn_test.pack(side="left", padx=10)
        
        self.status_var = tk.StringVar(value="状态: 已停止")
        self.status_label = tk.Label(self, textvariable=self.status_var, fg="#555", font=("微软雅黑", 10, "bold"))
        self.status_label.pack(pady=5)

        # 3. 关键说明区 (OpenAI 地址)
        info_frame = tk.Frame(self, bg="#e8f5e9", borderwidth=1, relief="solid")
        info_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(info_frame, text="✅ 兼容模式已开启，请复制下方地址到打轴软件：", 
                 bg="#e8f5e9", fg="#1b5e20").pack(pady=2)
        
        self.url_label = tk.Entry(info_frame, font=("Consolas", 11, "bold"), fg="#2e7d32", bg="#e8f5e9", justify="center", bd=0)
        self.url_label.insert(0, "http://127.0.0.1:8080/v1")#如果写成完整的地址，打轴软件可能会因为路径不匹配而无法正确连接，所以默认显示到 /v1 就好
        self.url_label.pack(fill="x", padx=20, pady=5)
        # 设置为只读，方便复制
        self.url_label.configure(state="readonly")

        # 4. 日志
        log_frame = tk.LabelFrame(self, text="运行日志")
        log_frame.pack(pady=5, padx=10, fill="both", expand=True)
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def browse_file(self, var, type_):
        ft = [("Executable", "*.exe")] if type_ == "exe" else [("GGML Model", "*.bin"), ("All Files", "*.*")]
        f = filedialog.askopenfilename(filetypes=ft)
        if f: var.set(f)

    def log(self, text):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", text)
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

    def monitor_server(self):
        """ 检测服务存活 """
        if not self.is_running: return
        port = self.port_var.get()
        # 即使改了路径，通常根路径 / 依然会返回 index 页面，用于检测存活足够了
        url = f"http://127.0.0.1:{port}/" 
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    self.after(0, self.set_running_ui)
        except:
            pass
        if self.is_running:
            self.check_timer = self.after(1000, self.monitor_server)

    def read_output(self):
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if not line: break
                try: text = line.decode("utf-8")
                except: text = line.decode("mbcs", errors="ignore")
                self.after(0, lambda t=text: self.log(t))
            except: break
        
        self.is_running = False
        code = self.process.poll() if self.process else -1
        self.after(0, lambda: self.set_stopped(code))

    def set_loading(self):
        self.status_var.set("状态: 🚀 正在启动 (加载 OpenAI 兼容模式)...")
        self.status_label.config(fg="orange")
        self.btn_start.config(text="启动中...", state="disabled", bg="#ffe0b2")
        self.btn_test.config(state="disabled")

    def set_running_ui(self):
        port = self.port_var.get()
        self.status_var.set(f"状态: ✅ 服务运行中 (OpenAI Ready)")
        self.status_label.config(fg="green")
        self.btn_start.config(text="停止服务", state="normal", bg="#ffcdd2")
        self.btn_test.config(state="normal")
        
        # 更新显示的地址
        self.url_label.configure(state="normal")
        self.url_label.delete(0, "end")
        self.url_label.insert(0, f"http://127.0.0.1:{port}/v1")
        self.url_label.configure(state="readonly")

    def set_stopped(self, code):
        if self.check_timer:
            self.after_cancel(self.check_timer)
            self.check_timer = None
        msg = f"状态: ⛔ 已停止 (代码 {code})" if code else "状态: ⛔ 已停止"
        self.status_var.set(msg)
        self.status_label.config(fg="red")
        self.btn_start.config(text="启动服务", state="normal", bg="#e1f5fe")
        self.btn_test.config(state="disabled")

    def open_test_page(self):
        port = self.port_var.get()
        webbrowser.open(f"http://127.0.0.1:{port}")

    def toggle_server(self):
        if self.is_running:
            self.is_running = False
            if self.process: self.process.terminate()
            return

        exe = get_short_path(self.exe_path_var.get())
        model = get_short_path(self.model_path_var.get())
        port = self.port_var.get()

        if not os.path.exists(exe): return messagebox.showerror("错误", "找不到exe")

        # === 核心修改：添加 --inference-path 参数 ===
        cmd = [
            exe, 
            "-m", model, 
            "--port", str(port), 
            "--host", "127.0.0.1",
            "--inference-path", "/v1/audio/transcriptions"  # 👈 这里就是你要的关键修改
        ]

        self.log(f"[系统] 执行命令: {' '.join(cmd)}\n")

        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                startupinfo=startupinfo,
                env=env,
                bufsize=0
            )
            self.is_running = True
            self.set_loading()
            threading.Thread(target=self.read_output, daemon=True).start()
            self.monitor_server()
            
        except Exception as e:
            messagebox.showerror("异常", str(e))

    def on_closing(self):
        self.is_running = False
        if self.process: self.process.kill()
        self.destroy()

if __name__ == "__main__":
    app = Application()
    app.mainloop()