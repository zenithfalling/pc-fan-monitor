import sys
import json
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.data_manager import DataManager
from core.data_manager import StatisticsManager
from core.uart_manager import SerialReceiver
from core.data_manager import DataLogger

def main():
    # 读取配置
    with open("config/app_config.json","r",encoding="utf-8-sig") as f:
        config_mode = json.load(f)

    dataProcess = DataManager(config_mode)
    serialProcess = SerialReceiver()
    staProcess = StatisticsManager()
    dataSaveProcess = DataLogger()

    app = QApplication(sys.argv)
    myWindow = MainWindow(config_mode,dataProcess,serialProcess,staProcess,dataSaveProcess)
    myWindow.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
