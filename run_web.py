#!/usr/bin/env python3
"""
洛克王国战斗模拟器 - Web图形界面启动入口
Usage: python3 run_web.py
"""
import sys
import os
import webbrowser
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:8765/battle")

if __name__ == "__main__":
    print("=" * 50)
    print("  洛克王国战斗模拟器 - Web图形界面")
    print("=" * 50)
    print("  地址: http://localhost:8765/battle")
    print("  按 Ctrl+C 退出")
    print("=" * 50)

    # 自动打开浏览器
    threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    uvicorn.run(
        "src.server:app",
        host="0.0.0.0",
        port=8765,
        log_level="warning",
    )
