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
import json


# === PyInstaller 内置资源路径解析函数 ===
def get_resource_path(relative_path):
    """ 获取资源的绝对路径 (兼容开发环境和 PyInstaller 打包后的环境) """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
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
        self.geometry("720x680") # 稍微调高了一点窗口以放下新选项

        # === 加载内嵌的窗口图标 ===
        icon_path = get_resource_path("栞子.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # === 确定配置文件的保存路径 ===
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(base_path, "models.json")

        self.process = None 
        self.is_running = False
        self.check_timer = None
        
        # 自动查找路径
        base_dir = os.getcwd()
        self.default_model = os.path.join(base_dir, "models", "ggml-large-v3.bin")
        
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

        # === 新增：自动启动选项 ===
        self.auto_start_var = tk.BooleanVar(value=False)
        tk.Checkbutton(config_frame, text="打开程序时自动启动服务", variable=self.auto_start_var).grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=2)

        # === 初始化时加载上次的配置 ===
        self.load_config()

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
        self.url_label.insert(0, f"http://127.0.0.1:{self.port_var.get()}/v1")
        self.url_label.pack(fill="x", padx=20, pady=5)
        self.url_label.configure(state="readonly")

        # 4. 日志
        log_frame = tk.LabelFrame(self, text="运行日志")
        log_frame.pack(pady=5, padx=10, fill="both", expand=True)
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # === 新增：触发自动启动逻辑 ===
        if self.auto_start_var.get():
            # 延时 500ms 启动，确保 UI 已经完全渲染出来
            self.after(500, self.auto_start_sequence)

    def auto_start_sequence(self):
        """ 执行自动启动前检查路径是否有效 """
        exe = self.exe_path_var.get()
        model = self.model_path_var.get()
        if os.path.exists(exe) and os.path.exists(model):
            self.log("[系统] 检测到自动启动已勾选，正在拉起服务...\n")
            self.toggle_server()
        else:
            self.log("[系统] 自动启动取消：找不到 exe 或模型文件，请检查路径是否正确。\n")

    # === 读取 JSON 配置 ===
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if "exe_path" in config and os.path.exists(config["exe_path"]):
                        self.exe_path_var.set(config["exe_path"])
                    if "model_path" in config and os.path.exists(config["model_path"]):
                        self.model_path_var.set(config["model_path"])
                    if "port" in config:
                        self.port_var.set(config["port"])
                    # 读取自动启动状态
                    if "auto_start" in config:
                        self.auto_start_var.set(config["auto_start"])
            except Exception as e:
                print(f"读取配置文件失败: {e}")

    # === 保存 JSON 配置 ===
    def save_config(self):
        config = {
            "exe_path": self.exe_path_var.get(),
            "model_path": self.model_path_var.get(),
            "port": self.port_var.get(),
            "auto_start": self.auto_start_var.get() # 保存自动启动状态
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件失败: {e}")

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

            exe_abs = self.exe_path_var.get()
            model_abs = self.model_path_var.get()
            port = self.port_var.get()

            if not os.path.exists(exe_abs): 
                return messagebox.showerror("错误", "找不到 Server 程序文件！")
            if not os.path.exists(model_abs):
                return messagebox.showerror("错误", "找不到模型文件！")

            # ================= 核心修复逻辑 =================
            exe_dir = os.path.dirname(exe_abs)
            
            # 1. 尝试获取模型相对于 exe 的相对路径
            try:
                model_arg = os.path.relpath(model_abs, start=exe_dir)
            except ValueError:
                # 如果在不同盘符（比如 exe 在 C 盘，model 在 D 盘），无法生成相对路径
                model_arg = model_abs

            # 2. 检查最终传给 whisper 的路径字符串中是否还包含非 ASCII 字符（中文等）
            def has_non_ascii(text):
                return any(ord(c) > 127 for c in text)

            if has_non_ascii(model_arg):
                # 如果此时还有中文，说明相对路径法也救不了（比如用户自己从外面选了个带中文的模型路径）
                # 直接弹窗拦截，防止小白面对闪退一脸懵逼
                messagebox.showerror(
                    "路径错误 (防闪退拦截)",
                    f"检测到模型路径参数包含中文字符：\n{model_arg}\n\n"
                    f"AI 引擎底层不支持中文路径，强行启动会直接闪退！\n\n"
                    f"👉 【小白专用解决方法】\n"
                    f"1. 请把整个软件文件夹移动到纯英文路径下（例如 D:\\WhisperTool\\ ）\n"
                    f"2. 如果你的电脑用户名是中文（放桌面就会报错），请直接剪切到 D 盘或 E 盘根目录！"
                )
                self.log("[系统] 启动已拦截：路径中包含引擎不支持的中文字符。\n")
                return
            # ================================================

            # 注意：cmd 第一个参数依然用绝对路径启动 exe，但 -m 参数传纯英文的相对路径
            cmd = [
                exe_abs, 
                "-m", model_arg, 
                "--port", str(port), 
                "--host", "127.0.0.1",
                "--inference-path", "/v1/audio/transcriptions"
            ]

            self.log(f"[系统] 执行命令: {' '.join(cmd)}\n")
            self.log(f"[系统] 工作目录(cwd): {exe_dir}\n") # 打印出来方便你调试

            try:
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                self.process = subprocess.Popen(
                    cmd,
                    cwd=exe_dir,  # <--- 极其关键：将底层工作目录指定为 exe 所在的目录
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
                messagebox.showerror("启动异常", str(e))

    def on_closing(self):
        # 退出前自动保存配置
        self.save_config()
        self.is_running = False
        if self.process: self.process.kill()
        self.destroy()

if __name__ == "__main__":
    app = Application()
    app.mainloop()