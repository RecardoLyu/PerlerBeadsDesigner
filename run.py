"""PyInstaller 引导入口：以包方式调用 webapp main（避免相对导入失败）。"""
from src.webapp.main import main

if __name__ == "__main__":
    main()
