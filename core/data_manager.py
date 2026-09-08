from enum import IntEnum
from PySide6.QtCore import QObject,Slot,QMutex,QMutexLocker
from collections import deque
import numpy as np

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

    @Slot(int,int)
    def save_data(self,currentSpeed,targetSpeed):
        with QMutexLocker(self.mutex):
            self.speedGap = targetSpeed - currentSpeed
            self.buffer_currentSpeed.append(currentSpeed)
            self.buffer_targetSpeed.append(targetSpeed)
            self.buffer_speedDiff.append(targetSpeed - currentSpeed)
    
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
                "buffer_speedgap":np.array(self.buffer_speedDiff),
                "speed_diff":self.speedGap
                }

