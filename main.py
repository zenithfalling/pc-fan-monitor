import sys
import json
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.data_manager import DataManager
from core.data_manager import StatisticsManager
from core.uart_manager import SerialReceiver


def main():
    # 读取配置
    with open("config/config.json","r",encoding="utf-8-sig") as f:
        config_mode = json.load(f)

    dataProcess = DataManager(config_mode)
    serialProcess = SerialReceiver()
    staProcess = StatisticsManager()

    app = QApplication(sys.argv)
    myWindow = MainWindow(config_mode,dataProcess,serialProcess,staProcess)
    myWindow.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
