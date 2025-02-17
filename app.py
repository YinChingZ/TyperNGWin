"""
Key mapping application
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import logging
import sys
import threading
import asyncio
import keyboard
import Quartz
import ctypes
from ctypes import c_bool
import os
import subprocess

# 设置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('typerm')

class TyperM(toga.App):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
            self.target_string = ""
            self.current_pos = 0
            self.is_mapping = False
            self.is_paused = False
            self.my_loop = asyncio.get_event_loop()
            self.quartz_listener = None
            logger.debug("TyperM initialized successfully")
        except Exception as e:
            logger.error(f"Error in initialization: {str(e)}")
            raise

    def check_accessibility_permissions(self):
        # Load the ApplicationServices framework
        app_services = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )

        # Set the function's return type and argument types
        app_services.AXIsProcessTrusted.restype = c_bool
        app_services.AXIsProcessTrusted.argtypes = []

        if app_services.AXIsProcessTrusted():
            logger.info("Accessibility permissions granted")
            return True
        else:
            logger.error("Accessibility permissions not granted")
            self.main_window.info_dialog(
                "权限错误",
                "应用程序需要访问辅助功能权限 (Accessibility权限) 才能正常运行。"
                "请在系统偏好设置中启用此权限。"
                "如果在启用权限后还是弹出此窗口，请在权限设置页面中移除TyperNGen后重新添加TyperNGen。"
            )
            return False
            
    def startup(self):
        """Construct and show the Toga application."""
        try:
            self.main_window = toga.MainWindow(title=self.formal_name, size=(800, 600), resizable=False)
            self.main_window.show()
            if not self.check_accessibility_permissions():
                return

            main_box = toga.Box(style=Pack(direction=COLUMN, padding=10, flex=1))
            
            # 创建标题标签
            title_label = toga.Label(
                "TyperM - 键盘映射工具",
                style=Pack(padding=(0, 0, 10, 0))
            )
            
            # 创建输入框
            self.input_text = toga.MultilineTextInput(
                placeholder='请粘贴要映射的字符串',
                style=Pack(padding=(0, 0, 10, 0), flex=1, height=470, width=780)
            )
            
            # 创建滚动容器
            scroll_container = toga.ScrollContainer(
                content=self.input_text,
                style=Pack(flex=1)
            )
            
            # 创建按钮
            self.map_button = toga.Button(
                "开始映射",
                on_press=self.toggle_mapping,
                style=Pack(padding=5)
            )
            
            # 创建状态标签
            self.status_label = toga.Label(
                "未开始映射",
                style=Pack(padding=(5, 0))
            )
            
            # 将组件添加到主容器
            main_box.add(title_label)
            main_box.add(scroll_container)
            main_box.add(self.map_button)
            main_box.add(self.status_label)

            self.main_window = toga.MainWindow(title=self.formal_name, size=(800, 600), resizable=False)
            self.main_window.content = main_box
            self.main_window.show()
            logger.debug("UI setup completed")
            
        except Exception as e:
            logger.error(f"Error in startup: {str(e)}")
            raise

    def show_notification(self, title, text):
        try:
            cmd = 'display notification \"' + text + '\" with title \"' + title + '\"'
            subprocess.call(["osascript", "-e", cmd])
        except Exception as e:
            logger.error(f"Error showing notification: {str(e)}")

    def handle_key_event(self, event):
        try:
            if not self.is_mapping:
                return

            # 只处理按键按下事件
            if event.event_type != keyboard.KEY_DOWN:
                return

            # ESC key detection
            if event.name == 'esc':
                logger.debug("ESC pressed, stopping mapping")
                asyncio.create_task(self.async_stop_mapping())
                return

            # Control + P key detection
            if event.name == 'p' and event.modifiers == ['control']:
                logger.debug("Control + P pressed, toggling pause state")
                self.is_paused = not self.is_paused
                if self.is_paused:
                    self.show_notification("TyperM", "映射已暂停")
                else:
                    self.show_notification("TyperM", "映射已恢复")
                return

            if self.is_paused:
                return

            logger.debug(f"Received key event: keyCode={event.scan_code}")

            if self.current_pos >= len(self.target_string):
                # 达到字符串末尾，停止映射
                logger.debug("Reached end of string, stopping mapping")
                asyncio.create_task(self.async_stop_mapping())
                return
                
            next_char = self.target_string[self.current_pos]
            logger.debug(f"Typing character: {next_char}")
            self.type_character(next_char)
            self.current_pos += 1
                
        except Exception as e:
            logger.error(f"Error in key event handler: {str(e)}")

    def type_character(self, char):
        """使用 keyboard 库模拟按键"""
        try:
            logger.debug(f"Typing character: {char}")
            keyboard.write(char)
        except Exception as e:
            logger.error(f"Error typing character: {str(e)}")

    def toggle_mapping(self, widget):
        try:
            if not self.is_mapping:
                self.start_mapping()
            else:
                asyncio.create_task(self.async_stop_mapping())
        except Exception as e:
            logger.error(f"Error in toggle_mapping: {str(e)}")
            self.main_window.info_dialog(
                "错误",
                f"切换映射状态时发生错误: {str(e)}"
            )

    def start_mapping(self):
        try:
            self.target_string = self.input_text.value
            if not self.target_string:
                self.main_window.info_dialog("错误", "请先输入要映射的字符串")
                return

            self.is_mapping = True
            self.current_pos = 0
            self.map_button.text = "停止映射"
            self.status_label.text = "映射进行中 (按ESC停止)"

            self.quartz_listener = Quartz.CGEventTapCreate(
                Quartz.kCGHIDEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
                self.quartz_callback,
                None
            )

            runLoopSource = Quartz.CFMachPortCreateRunLoopSource(None, self.quartz_listener, 0)
            Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), runLoopSource, Quartz.kCFRunLoopDefaultMode)
            Quartz.CGEventTapEnable(self.quartz_listener, True)

            self.main_window.hide()
            logger.debug("Mapping started: Quartz listener installed and window hidden")
        except Exception as e:
            logger.error(f"Error in start_mapping: {str(e)}")
            self.main_window.info_dialog("错误", f"启动映射时发生错误: {str(e)}")

    def quartz_callback(self, proxy, type, event, refcon):
        try:
            key_code = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            logger.debug(f"Quartz received key event: keyCode={key_code}")

            if key_code == 53:  # ESC key code
                logger.debug("ESC pressed, stopping mapping")
                asyncio.create_task(self.async_stop_mapping())
                return None

            if key_code == 49:  # Space key code
                logger.debug("Space key pressed, allowing event to pass through")
                return event

            if key_code == 36:  # Enter key code
                logger.debug("Enter key pressed, allowing event to pass through")
                return event

            if key_code == 35 and Quartz.CGEventGetFlags(event) & Quartz.kCGEventFlagMaskControl:  # Control + P key code
                logger.debug("Control + P pressed, toggling pause state")
                self.is_paused = not self.is_paused
                if self.is_paused:
                    self.show_notification("TyperM", "映射已暂停")
                else:
                    self.show_notification("TyperM", "映射已恢复")
                return None

            if self.is_paused:
                return event

            if self.current_pos >= len(self.target_string):
                # 达到字符串末尾，停止映射
                logger.debug("Reached end of string, stopping mapping")
                asyncio.create_task(self.async_stop_mapping())
                return None

            next_char = self.target_string[self.current_pos]
            logger.debug(f"Typing character: {next_char}")
            self.type_character(next_char)
            self.current_pos += 1

            return None  # Block the key event
        except Exception as e:
            logger.error(f"Error in quartz_callback: {str(e)}")
            return event

    async def async_stop_mapping(self):
        try:
            self.is_mapping = False
            self.map_button.text = "开始映射"
            self.status_label.text = "映射已停止"
            self.main_window.show()
            self.show_notification("TyperM", "映射已停止")
            logger.debug("Mapping stopped")

            if self.quartz_listener:
                Quartz.CFRunLoopRemoveSource(Quartz.CFRunLoopGetCurrent(), self.quartz_listener, Quartz.kCFRunLoopDefaultMode)
                Quartz.CFMachPortInvalidate(self.quartz_listener)
                self.quartz_listener = None

            keyboard.unhook_all()
        except Exception as e:
            logger.error(f"Error in async_stop_mapping: {str(e)}")

def main():
    try:
        logger.debug("Starting TyperM application")
        return TyperM()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise
