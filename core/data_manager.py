from enum import IntEnum
import json
from PySide6.QtCore import QObject, Signal,Slot,QMutex,QMutexLocker
from collections import deque
import numpy as np
import csv
import os
from datetime import datetime
from openpyxl import Workbook

class DataMode(IntEnum):
    DEBUG = 1
    NORMAL = 2

class StatisticsManager(QObject):
    def __init__(self):
        super().__init__()
        self.errorCRCNum = 0
        self.packetLoss = 0
        self.mutex = QMutex()
    
    @Slot()
    def on_crc_error(self):
        with QMutexLocker(self.mutex):
            self.errorCRCNum += 1

    @Slot(int)
    def on_packetloss(self,count):
        with QMutexLocker(self.mutex):
            self.packetLoss += count

    @Slot()
    def clear(self):
        with QMutexLocker(self.mutex):
            self.errorCRCNum = 0
            self.packetLoss = 0


    def get_statistics_data(self):
        with QMutexLocker(self.mutex):
            return {
                "crc_num": self.errorCRCNum,
                "packetloss": self.packetLoss
                }


class DataManager(QObject):

    def __init__(self,configmode):
        super().__init__()
        self.mode = None
        self.configMode = configmode
        self.mutex = QMutex()
        self.buffer_currentSpeed = None
        self.buffer_targetSpeed = None
        self.buffer_speedDiff = None
        self.speedGap = None

    @Slot(int)
    def set_mode(self,mode):
        with QMutexLocker(self.mutex):
            if self.mode == mode:
                return           
            if(mode == DataMode.DEBUG):
                max_length = self.configMode["debug"]["max_length"]
            elif(mode == DataMode.NORMAL):
                max_length = self.configMode["normal"]["max_length"]
            else:
                return

            self.mode = mode
            self.buffer_currentSpeed = deque(maxlen=max_length)
            self.buffer_targetSpeed = deque(maxlen=max_length)
            self.buffer_speedDiff = deque(maxlen=max_length)
            self.speedGap = None

    @Slot(object)
    def save_data(self,data):
        with QMutexLocker(self.mutex):
            self.speedGap = data.targetSpeed - data.currentSpeed
            self.buffer_currentSpeed.append(data.currentSpeed)
            self.buffer_targetSpeed.append(data.targetSpeed)
            self.buffer_speedDiff.append(data.targetSpeed - data.currentSpeed)
    
    @Slot()
    def clear_pic_data(self):
        with QMutexLocker(self.mutex):
            self.buffer_currentSpeed.clear()
            self.buffer_targetSpeed.clear()
            self.buffer_speedDiff.clear()

    def get_debug_data(self):
        with QMutexLocker(self.mutex):
            return {
                "current_speed": np.array(self.buffer_currentSpeed),
                "target_speed":np.array(self.buffer_targetSpeed)
                }

    def get_normal_data(self):
        with QMutexLocker(self.mutex):
            return {
                "current_speed": np.array(self.buffer_currentSpeed),
                "target_speed":np.array(self.buffer_targetSpeed),
                "buffer_speedgap":np.array(self.buffer_speedDiff)
                }

class DataLogger(QObject):
    sig_save_success = Signal()

    def __init__(self):
        super().__init__()
        self.workbook = None
        self.config_sheet = None
        self.data_sheet = None
        self.is_logging = False
        self.rowcount = 0
        self.file_path = r"D:\ProjectAll\VSProject\fan-monitor-pc\PIDDebugData"
        # 如果路径中的文件夹不存在，可以自动创建
        os.makedirs(self.file_path, exist_ok=True)
        


    def start_logging(self):
        if self.is_logging:
            return
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.workbook = Workbook()
        self.config_sheet = self.workbook.active
        self.config_sheet.title = "ConfigData"
        self.data_sheet = self.workbook.create_sheet("RawData")
        filename = f"{current_time}.xlsx"
        self.full_path = os.path.join(self.file_path, filename)
        #把配置写入表格
        with open("./config/experiment_config.json","r",encoding="utf-8-sig") as f:
            exper_config = json.load(f)
        self.config_sheet.append(["parameter","value"])
        for key,value in exper_config.items():
            self.config_sheet.append([key,value])
        self.data_sheet.append(["timestamp","currentspeed","targetspeed","duty","P","I","D"])
        self.is_logging = True
        self.rowcount = 0

    def write_data(self,data):
        if not self.is_logging:
            return
        self.data_sheet.append([data.timestamp,
                                data.currentSpeed,
                                data.targetSpeed,
                                data.duty,
                                data.P,
                                data.I,
                                data.D])
        self.rowcount += 1
        if self.rowcount % 50 == 0:
            self.workbook.save(self.full_path)
            

    def stop_logging(self):
        if not self.is_logging:
            return
        self.workbook.save(self.full_path)
        self.config_sheet = None
        self.data_sheet = None
        self.is_logging = False
        self.sig_save_success.emit()
        