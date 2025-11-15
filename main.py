import tkinter as tk
from tkinter import ttk, messagebox
import pynput
from pynput.mouse import Controller, Button, Listener as MouseListener
from pynput.keyboard import GlobalHotKeys
import time
import threading
import ctypes
from ctypes import wintypes
import math
import locale

# 国际化支持
def get_system_language():
    try:
        lang, _ = locale.getdefaultlocale()
        return lang.lower() if lang else "en_us"
    except:
        return "en_us"

# 翻译字典
translations = {
    "en_us": {
        "主窗口标题": "Mouse Event Recorder (Mask Edition)",
        "开始记录 (F9)": "Start Recording (F9)",
        "停止记录 (F10)": "Stop Recording (F10)",
        "开始重放 (F11)": "Start Replay (F11)",
        "停止重放 (F8)": "Stop Replay (F8)",
        "清除记录与轨迹": "Clear Records & Traces",
        "蒙版全屏/窗口 (F12)": "Mask Fullscreen/Window (F12)",
        "设置": "Settings",
        "使用硬件加速透明（白屏请关闭）": "Use hardware-accelerated transparency (disable if white screen)",
        "重放时控制鼠标": "Control mouse during replay",
        "显示轨迹": "Show trace",
        "就绪：操作前会自动检查蒙版": "Ready: Mask will be checked automatically before operation",
        "已记录事件：{}": "Recorded events: {}",
        "蒙版已创建：可开始操作": "Mask created: Ready to operate",
        "创建蒙版失败：{}": "Failed to create mask: {}",
        "记录已停止（蒙版不存在）": "Recording stopped (mask not exists)",
        "记录完成：共{}个事件（F11重放）": "Recording completed: {} events total (F11 to replay)",
        "正在记录：蒙版内操作将被记录": "Recording: Operations within mask will be recorded",
        "正在重放：按F8停止": "Replaying: Press F8 to stop",
        "重放完成：共执行{}个事件": "Replay completed: {} events executed",
        "重放超时自动停止": "Replay stopped automatically (timeout)",
        "重放出错：{}": "Replay error: {}",
        "蒙版不存在，无法切换全屏": "Mask not exists, cannot toggle fullscreen",
        "蒙版已全屏": "Mask is fullscreen",
        "蒙版已窗口化": "Mask is windowed",
        "正在清除（蒙版将重建）": "Clearing (mask will be rebuilt)",
        "已清除记录和轨迹": "Records and traces cleared",
        "使用硬件加速透明：若白屏请关闭": "Using hardware transparency: disable if white screen",
        "使用兼容透明模式：无白屏风险": "Using compatible transparency: no white screen risk",
        "透明模式初始化失败：使用基础显示": "Transparency init failed: using basic display",
        "错误": "Error",
        "提示": "Tip",
        "警告": "Warning",
        "无法创建蒙版窗口，请重试": "Failed to create mask window, please retry",
        "无法创建蒙版窗口，无法重放": "Failed to create mask window, cannot replay",
        "请开启「控制鼠标」选项以实际操作文件": "Please enable 'Control mouse' to perform actions",
        "没有可重放的事件，请先记录": "No events to replay, please record first",
        "程序发生错误：{}": "Program error: {}",
        "记录范围蒙版": "Recording Range Mask",
        "拖动移动 | 双击调整大小": "Drag to move | Double-click to resize",
        "检测到左键双击": "Left double-click detected"
    }
}

# 翻译函数
def _(text, *args):
    lang = get_system_language()
    if lang.startswith("zh"):
        return text.format(*args) if args else text
    else:
        en_text = translations["en_us"].get(text, text)
        return en_text.format(*args) if args else en_text

class MouseRecorder:
    def __init__(self):
        # 核心变量初始化
        self.recording = False
        self.replaying = False
        self.mouse_events = []
        self.mask_window = None  # 蒙版窗口初始为None
        self.trace_window = None
        self.fullscreen = False
        self.occupy_mouse = True
        self.resizing = False
        self.dragging = False
        self.last_pos = None
        self.title_bar_height = 30
        self.trace_elements = []
        self.screen_scale = self.get_screen_scale()
        self.last_click_info = None
        self.double_click_threshold = 0.5
        
        # 性能控制变量
        self.last_move_time = 0
        self.move_throttle = 0.02
        self.last_ui_update_time = 0
        self.ui_update_interval = 0.1
        
        # 颜色配置
        self.COLOR_MOVE = "#4287f5"
        self.COLOR_LEFT_CLICK = "#ff3333"
        self.COLOR_RIGHT_CLICK = "#33cc33"
        self.COLOR_MIDDLE_CLICK = "#ffff33"
        self.COLOR_SCROLL = "#ff9933"
        self.COLOR_REPLAY_MOVE = "#9966ff"
        self.COLOR_REPLAY_CLICK = "#cc33ff"
        self.COLOR_TITLE_BAR = "#2a5cad"
        self.COLOR_MASK_BODY = "#4287f5"
        self.TRACE_BG_COLOR = "#000000"
        
        # 轨迹样式
        self.TRACE_LINE_WIDTH = 2
        self.CLICK_MARK_SIZE = 6
        self.SCROLL_MARK_SIZE = 8
        self.TRACE_ALPHA = 0.7
        self.MAX_GAP = 30
        
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title(_("主窗口标题"))
        self.root.geometry("400x720")
        self.root.resizable(False, False)
        self.root.attributes("-alpha", 1.0)
        
        # 初始化UI和功能
        self.create_widgets()
        self.set_hotkeys()
        # 初始延迟创建蒙版（但允许后续自动重建）
        self.root.after(100, self.ensure_mask_exists)
        self.root.after(200, self.create_trace_window)
        
        # 退出清理
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    # -------------------------- 新增核心逻辑：检查并创建蒙版 --------------------------
    def ensure_mask_exists(self):
        """确保蒙版窗口存在，不存在则创建"""
        # 检查条件：窗口未初始化 或 已被销毁（winfo_exists()返回0）
        if self.mask_window is None or not self.mask_window.winfo_exists():
            try:
                self.create_mask_window()  # 重建蒙版
                self.status_var.set(_("蒙版已创建：可开始操作"))
            except Exception as e:
                self.status_var.set(_("创建蒙版失败：{}", str(e)))
                print(f"重建蒙版错误：{e}")
        return self.mask_window is not None and self.mask_window.winfo_exists()
    
    # -------------------------- 原有方法修改：添加蒙版检查 --------------------------
    def start_recording(self):
        # 操作前先检查蒙版是否存在
        if not self.ensure_mask_exists():
            messagebox.showerror(_("错误"), _("无法创建蒙版窗口，请重试"))
            return
            
        if not self.recording and not self.replaying:
            self.recording = True
            self.mouse_events = []
            self.last_click_info = None
            self.last_move_time = 0
            self.clear_trace()
            self.status_var.set(_("正在记录：蒙版内操作将被记录"))
            self.mouse_listener = MouseListener(
                on_move=self.on_mouse_move,
                on_click=self.on_mouse_click,
                on_scroll=self.on_mouse_scroll
            )
            self.mouse_listener.daemon = True
            self.mouse_listener.start()
    
    def stop_recording(self):
        # 停止记录也需要检查蒙版（避免引用已销毁窗口）
        if not self.ensure_mask_exists():
            self.recording = False  # 强制停止记录状态
            self.status_var.set(_("记录已停止（蒙版不存在）"))
            return
            
        if self.recording:
            self.recording = False
            if hasattr(self, 'mouse_listener') and self.mouse_listener.is_alive():
                self.mouse_listener.stop()
            self.status_var.set(_("记录完成：共{}个事件（F11重放）", len(self.mouse_events)))
    
    def start_replaying(self):
        # 重放前必须确保蒙版存在（用于范围判断）
        if not self.ensure_mask_exists():
            messagebox.showerror(_("错误"), _("无法创建蒙版窗口，无法重放"))
            return
            
        if not self.replaying and not self.recording and self.mouse_events:
            if not self.occupy_var.get():
                messagebox.showwarning(_("提示"), _("请开启「控制鼠标」选项以实际操作文件"))
                return
            self.replaying = True
            self.clear_trace()
            self.status_var.set(_("正在重放：按F8停止"))
            thread = threading.Thread(target=self.replay_events, daemon=True)
            thread.start()
        elif not self.mouse_events:
            messagebox.showwarning(_("警告"), _("没有可重放的事件，请先记录"))
    
    def toggle_fullscreen(self):
        # 切换全屏前检查蒙版
        if not self.ensure_mask_exists():
            messagebox.showerror(_("错误"), _("蒙版不存在，无法切换全屏"))
            return
            
        self.fullscreen = not self.fullscreen
        self.mask_window.attributes("-fullscreen", self.fullscreen)
        if self.fullscreen:
            self.title_bar.pack_forget()
            self.status_var.set(_("蒙版已全屏"))
        else:
            self.title_bar.pack(fill=tk.X)
            self.status_var.set(_("蒙版已窗口化"))
    
    def clear_all(self):
        # 清除操作涉及轨迹和记录，也需确保蒙版状态
        if not self.ensure_mask_exists():
            self.status_var.set(_("正在清除（蒙版将重建）"))
        
        def async_clear():
            for elem_id in self.trace_elements:
                try:
                    self.trace_canvas.delete(elem_id)
                except:
                    pass
            self.trace_elements = []
            self.last_pos = None
            self.mouse_events = []
            self.last_click_info = None
            self.event_count_var.set(_("已记录事件：{}", 0))
            self.status_var.set(_("已清除记录和轨迹"))
        self.root.after(10, async_clear)
    
    # -------------------------- 其他原有方法保持不变 --------------------------
    def get_screen_scale(self):
        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            return user32.GetDpiForSystem() / 96.0
        except:
            return 1.0
    
    def create_widgets(self):
        frame = ttk.Frame(self.root, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 主控制按钮
        ttk.Button(frame, text=_("开始记录 (F9)"), command=self.start_recording).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text=_("停止记录 (F10)"), command=self.stop_recording).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text=_("开始重放 (F11)"), command=self.start_replaying).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text=_("停止重放 (F8)"), command=self.stop_replaying).pack(fill=tk.X, pady=2)
        
        # 辅助功能按钮
        ttk.Button(frame, text=_("清除记录与轨迹"), command=self.clear_all).pack(fill=tk.X, pady=2)
        ttk.Button(frame, text=_("蒙版全屏/窗口 (F12)"), command=self.toggle_fullscreen).pack(fill=tk.X, pady=2)
        
        # 选项区域
        options_frame = ttk.LabelFrame(frame, text=_("设置"), padding="5")
        options_frame.pack(fill=tk.X, pady=5)
        
        self.transparent_mode = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame, 
            text=_("使用硬件加速透明（白屏请关闭）"), 
            variable=self.transparent_mode,
            command=self.update_transparent_mode
        ).pack(anchor=tk.W, pady=2)
        
        self.occupy_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame, 
            text=_("重放时控制鼠标"), 
            variable=self.occupy_var
        ).pack(anchor=tk.W, pady=2)
        
        self.show_trace_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame, 
            text=_("显示轨迹"), 
            variable=self.show_trace_var, 
            command=self.toggle_trace_visibility
        ).pack(anchor=tk.W, pady=2)
        
        # 状态显示
        self.status_var = tk.StringVar(value=_("就绪：操作前会自动检查蒙版"))
        ttk.Label(frame, textvariable=self.status_var, foreground="#0066cc").pack(side=tk.BOTTOM, pady=5)
        self.event_count_var = tk.StringVar(value=_("已记录事件：{}", 0))
        ttk.Label(frame, textvariable=self.event_count_var).pack(side=tk.BOTTOM, pady=2)
    
    def create_mask_window(self):
        """创建蒙版窗口（若已存在则先销毁）"""
        # 若已有旧窗口，先销毁
        if self.mask_window is not None and self.mask_window.winfo_exists():
            try:
                self.mask_window.destroy()
            except:
                pass
        
        self.mask_window = tk.Toplevel(self.root)
        self.mask_window.title(_("记录范围蒙版"))
        self.mask_window.geometry("600x400+200+200")
        self.mask_window.attributes("-alpha", 0.2)
        self.mask_window.attributes("-topmost", False)
        self.mask_window.lift()
        
        # 顶部拖动条
        self.title_bar = tk.Frame(
            self.mask_window, 
            bg=self.COLOR_TITLE_BAR, 
            height=self.title_bar_height,
            relief=tk.RAISED,
            bd=1
        )
        self.title_bar.pack(fill=tk.X)
        tk.Label(
            self.title_bar, 
            text=_("拖动移动 | 双击调整大小"), 
            bg=self.COLOR_TITLE_BAR, 
            fg="white",
            font=("SimHei", 9)
        ).pack(side=tk.LEFT, padx=5, pady=2)
        
        # 蒙版主体
        self.mask_body = tk.Frame(
            self.mask_window, 
            bg=self.COLOR_MASK_BODY
        )
        self.mask_body.pack(fill=tk.BOTH, expand=True)
        
        # 右下角调整手柄
        self.resize_handle = tk.Frame(
            self.mask_body, 
            bg="gray", 
            width=12, 
            height=12,
            cursor="sizing"
        )
        self.resize_handle.place(relx=1.0, rely=1.0, anchor="se")
        
        # 绑定交互事件
        self.title_bar.bind("<Button-1>", self.safe_event(self.start_drag))
        self.title_bar.bind("<B1-Motion>", self.safe_event(self.on_drag))
        self.mask_body.bind("<Double-1>", self.safe_event(self.start_resize))
        self.resize_handle.bind("<Button-1>", self.safe_event(self.start_resize))
        self.mask_window.bind("<B1-Motion>", self.safe_event(self.on_resize))
        self.mask_window.bind("<ButtonRelease-1>", self.safe_event(self.stop_resize_or_drag))
        
        # 设置点击穿透
        self.root.after(300, lambda: self.set_click_through(self.mask_window))
    
    def create_trace_window(self):
        self.trace_window = tk.Toplevel(self.root)
        self.trace_window.overrideredirect(True)
        self.trace_window.attributes("-alpha", self.TRACE_ALPHA)
        self.trace_window.attributes("-topmost", True)
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.trace_window.geometry(f"{screen_width}x{screen_height}+0+0")
        
        self.trace_canvas = tk.Canvas(
            self.trace_window, 
            bg=self.TRACE_BG_COLOR,
            highlightthickness=0,
            bd=0
        )
        self.trace_canvas.pack(fill=tk.BOTH, expand=True)
        
        self.update_transparent_mode()
        self.root.after(300, lambda: self.set_click_through(self.trace_window))
    
    def update_transparent_mode(self):
        if self.transparent_mode.get():
            try:
                self.trace_window.wm_attributes("-transparentcolor", self.TRACE_BG_COLOR)
                self.trace_window.attributes("-alpha", self.TRACE_ALPHA)
                self.status_var.set(_("使用硬件加速透明：若白屏请关闭"))
            except:
                self.fallback_transparency()
        else:
            self.fallback_transparency()
    
    def fallback_transparency(self):
        try:
            self.trace_window.wm_attributes("-transparentcolor", "")
            self.trace_window.attributes("-alpha", 0.5)
            self.status_var.set(_("使用兼容透明模式：无白屏风险"))
        except:
            self.status_var.set(_("透明模式初始化失败：使用基础显示"))
    
    def set_click_through(self, window):
        try:
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000
            hwnd = wintypes.HWND(int(window.wm_frame(), 16))
            
            current_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            # ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 200, 2)
        except Exception as e:
            print(f"点击穿透设置警告：{e}")
    
    def toggle_trace_visibility(self):
        alpha = self.TRACE_ALPHA if self.show_trace_var.get() else 0
        self.trace_window.attributes("-alpha", alpha)
    
    def safe_event(self, func):
        def wrapper(event):
            try:
                return func(event)
            except Exception as e:
                print(f"事件处理错误：{e}")
        return wrapper
    
    def start_drag(self, event):
        self.dragging = True
        self.drag_start_x = event.x
        self.drag_start_y = event.y
    
    def on_drag(self, event):
        if self.dragging and not self.resizing:
            new_x = self.mask_window.winfo_x() + (event.x - self.drag_start_x)
            new_y = self.mask_window.winfo_y() + (event.y - self.drag_start_y)
            self.mask_window.geometry(f"+{new_x}+{new_y}")
    
    def start_resize(self, event):
        self.resizing = True
        self.resize_start_x = event.x_root
        self.resize_start_y = event.y_root
        self.original_width = self.mask_window.winfo_width()
        self.original_height = self.mask_window.winfo_height()
    
    def on_resize(self, event):
        if self.resizing and not self.dragging:
            delta_x = event.x_root - self.resize_start_x
            delta_y = event.y_root - self.resize_start_y
            new_width = max(200, self.original_width + delta_x)
            new_height = max(150 + self.title_bar_height, self.original_height + delta_y)
            self.mask_window.geometry(f"{new_width}x{new_height}")
    
    def stop_resize_or_drag(self, event):
        self.resizing = False
        self.dragging = False
    
    def set_hotkeys(self):
        def on_start(): self.start_recording()
        def on_stop(): self.stop_recording()
        def on_replay(): self.start_replaying()
        def on_stop_replay(): self.stop_replaying()
        def on_fullscreen(): self.toggle_fullscreen()
            
        self.hotkey_listener = GlobalHotKeys({
            '<f9>': on_start,
            '<f10>': on_stop,
            '<f11>': on_replay,
            '<f8>': on_stop_replay,
            '<f12>': on_fullscreen,
        })
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()
    
    def is_inside_mask(self, x, y):
        # 先确保蒙版存在再判断范围
        if not self.ensure_mask_exists():
            return False
            
        mask_x = self.mask_window.winfo_x() * self.screen_scale
        mask_y = self.mask_window.winfo_y() * self.screen_scale
        mask_width = self.mask_window.winfo_width() * self.screen_scale
        mask_height = self.mask_window.winfo_height() * self.screen_scale
        return (mask_x <= x <= mask_x + mask_width) and (mask_y <= y <= mask_y + mask_height)
    
    def interpolate_points(self, x1, y1, x2, y2):
        points = []
        distance = math.hypot(x2 - x1, y2 - y1)
        if distance > self.MAX_GAP:
            steps = max(1, int(distance // (self.MAX_GAP * 1.5)))
            for i in range(1, steps):
                ratio = i / steps
                points.append((x1 + (x2 - x1)*ratio, y1 + (y2 - y1)*ratio))
        return points
    
    def draw_trace_safe(self, *args, **kwargs):
        current_time = time.time()
        if current_time - self.last_move_time > self.move_throttle:
            self.last_move_time = current_time
            self.trace_window.after(0, lambda: self.draw_trace(*args, **kwargs))
    
    def draw_trace(self, x, y, event_type, button=None, is_replay=False):
        if not self.show_trace_var.get():
            return
        try:
            x_scaled = x * self.screen_scale
            y_scaled = y * self.screen_scale
            color = self._get_event_color(event_type, button, is_replay)
            
            if event_type == 'move' and self.last_pos:
                last_x, last_y = self.last_pos
                interpolated = self.interpolate_points(last_x, last_y, x, y)
                prev_x, prev_y = last_x, last_y
                for ix, iy in interpolated:
                    line_id = self.trace_canvas.create_line(
                        prev_x*self.screen_scale, prev_y*self.screen_scale,
                        ix*self.screen_scale, iy*self.screen_scale,
                        width=self.TRACE_LINE_WIDTH, fill=color,
                        capstyle=tk.ROUND, smooth=tk.TRUE
                    )
                    self.trace_elements.append(line_id)
                    prev_x, prev_y = ix, iy
                line_id = self.trace_canvas.create_line(
                    prev_x*self.screen_scale, prev_y*self.screen_scale,
                    x_scaled, y_scaled,
                    width=self.TRACE_LINE_WIDTH, fill=color,
                    capstyle=tk.ROUND, smooth=tk.TRUE
                )
                self.trace_elements.append(line_id)
            
            if event_type == 'click':
                mark_id = self.trace_canvas.create_oval(
                    x_scaled - self.CLICK_MARK_SIZE,
                    y_scaled - self.CLICK_MARK_SIZE,
                    x_scaled + self.CLICK_MARK_SIZE,
                    y_scaled + self.CLICK_MARK_SIZE,
                    fill=color, outline="white", width=1
                )
                self.trace_elements.append(mark_id)
                self.animate_click_mark(mark_id)
            elif event_type == 'scroll':
                mark_id = self.trace_canvas.create_polygon(
                    x_scaled, y_scaled - self.SCROLL_MARK_SIZE,
                    x_scaled + self.SCROLL_MARK_SIZE, y_scaled + self.SCROLL_MARK_SIZE,
                    x_scaled - self.SCROLL_MARK_SIZE, y_scaled + self.SCROLL_MARK_SIZE,
                    fill=color, outline="white", width=1
                )
                self.trace_elements.append(mark_id)
            
            self.last_pos = (x, y)
        except Exception as e:
            print(f"轨迹绘制错误：{e}")
    
    def animate_click_mark(self, mark_id):
        try:
            x1, y1, x2, y2 = self.trace_canvas.coords(mark_id)
            self.trace_canvas.coords(mark_id, x1-1, y1-1, x2+1, y2+1)
            self.trace_window.after(60, lambda: self.trace_canvas.coords(mark_id, x1, y1, x2, y2))
        except:
            pass
    
    def _get_event_color(self, event_type, button=None, is_replay=False):
        if is_replay:
            return self.COLOR_REPLAY_MOVE if event_type == 'move' else self.COLOR_REPLAY_CLICK
        else:
            if event_type == 'move':
                return self.COLOR_MOVE
            elif event_type == 'click':
                if button == Button.left:
                    return self.COLOR_LEFT_CLICK
                elif button == Button.right:
                    return self.COLOR_RIGHT_CLICK
                elif button == Button.middle:
                    return self.COLOR_MIDDLE_CLICK
                return "#666666"
            elif event_type == 'scroll':
                return self.COLOR_SCROLL
        return "#000000"
    
    def on_mouse_move(self, x, y):
        if self.recording and self.is_inside_mask(x, y):
            current_time = time.time()
            if current_time - self.last_move_time > self.move_throttle:
                self.last_move_time = current_time
                x_actual = x / self.screen_scale
                y_actual = y / self.screen_scale
                self.mouse_events.append(('move', x_actual, y_actual, current_time))
                self.draw_trace_safe(x_actual, y_actual, 'move')
                if current_time - self.last_ui_update_time > self.ui_update_interval:
                    self.last_ui_update_time = current_time
                    self.event_count_var.set(_("已记录事件：{}", len(self.mouse_events)))
    
    def on_mouse_click(self, x, y, button, pressed):
        if self.recording and self.is_inside_mask(x, y):
            x_actual = x / self.screen_scale
            y_actual = y / self.screen_scale
            timestamp = time.time()
            self.mouse_events.append(('click', x_actual, y_actual, button, pressed, timestamp))
            self.draw_trace_safe(x_actual, y_actual, 'click', button)
            self.event_count_var.set(_("已记录事件：{}", len(self.mouse_events)))
            
            if button == Button.left and pressed:
                current_time = timestamp
                if self.last_click_info:
                    last_btn, last_x, last_y, last_time = self.last_click_info
                    if (last_btn == Button.left and 
                        abs(current_time - last_time) < self.double_click_threshold and
                        abs(x_actual - last_x) < 5 and
                        abs(y_actual - last_y) < 5):
                        print(_("检测到左键双击"))
                self.last_click_info = (button, x_actual, y_actual, current_time)
    
    def on_mouse_scroll(self, x, y, dx, dy):
        if self.recording and self.is_inside_mask(x, y):
            x_actual = x / self.screen_scale
            y_actual = y / self.screen_scale
            timestamp = time.time()
            self.mouse_events.append(('scroll', x_actual, y_actual, dx, dy, timestamp))
            self.draw_trace_safe(x_actual, y_actual, 'scroll')
            self.event_count_var.set(_("已记录事件：{}", len(self.mouse_events)))
    
    def stop_replaying(self):
        if self.replaying:
            self.replaying = False
            self.status_var.set(_("重放已停止"))
    
    def replay_events(self):
        mouse = Controller()
        original_pos = mouse.position
        start_time = time.time()
        
        try:
            if not self.mouse_events:
                return
                
            event_start_time = self.mouse_events[0][-1]
            self.last_pos = None
            
            for event in self.mouse_events:
                if time.time() - start_time > 30:
                    self.status_var.set(_("重放超时自动停止"))
                    break
                if not self.replaying:
                    break
                    
                event_type = event[0]
                timestamp = event[-1]
                delay = timestamp - event_start_time
                event_start_time = timestamp
                
                if delay > 1.0:
                    delay = 1.0
                if delay > 0.005:
                    time.sleep(delay)
                
                if event_type == 'move':
                    _, x, y, _ = event
                    self.draw_trace_safe(x, y, 'move', is_replay=True)
                    mouse.position = (x * self.screen_scale, y * self.screen_scale)
                    time.sleep(0.001)
                
                elif event_type == 'click':
                    _, x, y, button, pressed, _ = event
                    self.draw_trace_safe(x, y, 'click', button, is_replay=True)
                    mouse.position = (x * self.screen_scale, y * self.screen_scale)
                    time.sleep(0.01)
                    if pressed:
                        mouse.press(button)
                    else:
                        mouse.release(button)
                    if button == Button.left and not pressed:
                        time.sleep(0.02)
                
                elif event_type == 'scroll':
                    _, x, y, dx, dy, _ = event
                    self.draw_trace_safe(x, y, 'scroll', is_replay=True)
                    mouse.position = (x * self.screen_scale, y * self.screen_scale)
                    mouse.scroll(dx, dy)
        
        except Exception as e:
            print(f"重放错误：{e}")
            self.status_var.set(_("重放出错：{}", str(e)))
        finally:
            self.replaying = False
            self.status_var.set(_("重放完成：共执行{}个事件", len(self.mouse_events)))
            mouse.position = original_pos
    
    def clear_trace(self):
        def async_clear():
            for elem_id in self.trace_elements:
                try:
                    self.trace_canvas.delete(elem_id)
                except:
                    pass
            self.trace_elements = []
            self.last_pos = None
        self.root.after(10, async_clear)
    
    def on_close(self):
        self.recording = False
        self.replaying = False
        if hasattr(self, 'mouse_listener') and self.mouse_listener.is_alive():
            self.mouse_listener.stop()
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()
        # 销毁所有窗口
        if self.mask_window is not None and self.mask_window.winfo_exists():
            try:
                self.mask_window.destroy()
            except:
                pass
        if self.trace_window is not None and self.trace_window.winfo_exists():
            try:
                self.trace_window.destroy()
            except:
                pass
        self.root.destroy()
    
    def run(self):
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"主程序错误：{e}")
            messagebox.showerror(_("错误"), _("程序发生错误：{}", str(e)))

if __name__ == "__main__":
    recorder = MouseRecorder()
    recorder.run()