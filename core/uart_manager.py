from enum import IntEnum
from PySide6.QtCore import QObject,Slot,Signal
from PySide6.QtSerialPort import QSerialPort,QSerialPortInfo
import struct
from dataclasses import dataclass

#专门用来传输协议数据的类型，把长短帧统一起来
@dataclass
class ProtocolData:
    currentSpeed:int | None = None
    targetSpeed:int | None = None
    duty:int | None = None
    P:float | None = None
    I:float | None = None
    D:float | None = None
    timestamp:int | None = None

# 定义一个类，区分串口是打开动作还是关闭动作，把主界面对应的串口状态改变整理到一个函数中
class SerialAction(IntEnum):
    OPEN = 1
    CLOSE = 2

class SerialReceiver(QObject):
    sig_serial_status = Signal(bool,int,str) # 串口状态监视，影响主界面的按钮可用性
    sig_receivedData = Signal(object)# 解析后的原始数据，发给datamanager
    sig_crc = Signal()
    sig_packetLoss = Signal(int)
    sig_savedata = Signal(object)

    def __init__(self):
        super().__init__()
        self.ser = QSerialPort(self)
        #self.ser.readyRead.connect(self.readData) # 信号与槽连接
        self.ser.readyRead.connect(self.readDataDebug) #为debug模式单独写的，但是能否切换信号与槽的绑定，随着不同模式？
        self.FRAME_HEADER = b'\x55\xAA'
        self.FRAME_LEN = 12 # 字节数
        self.FRAME_LEN_DEBUG = 30
        self.buffer = bytearray()
        self.errorCRCNum = 0
        self.speedGap = 0
        self.packetIndex = None
        self.packetLoss = 0

    @Slot(dict)
    def open_port(self,port_config):
        if self.ser.isOpen():
            self.ser.close() #如果已经打开，肯定不能这么简单就结束，还得有别的操作

        self.ser.setPortName(port_config['port_name'])
        self.ser.setBaudRate(port_config['baud_rate'])
        self.ser.setDataBits(port_config['databits'])
        self.ser.setParity(port_config['paritybits'])
        self.ser.setStopBits(port_config['stopbits'])
        if self.ser.open(QSerialPort.ReadWrite):
            self.sig_serial_status.emit(True,SerialAction.OPEN,'串口打开成功')
        else:
            self.sig_serial_status.emit(False,SerialAction.OPEN,self.ser.errorString())


    def calcrc32(self,data:bytes):
        poly = 0x04C11DB7
        reg = 0x00000000 #自己计算用的验证初始值
        reg = 0xFFFFFFFF # 对应stm32正确的结果
        if(len(data) % 4 != 0):
            data = data + b'\x00' * (4 - len(data) % 4) # 如果不够4个字节，要补充满
        for i in range(0,len(data),4):
            eachblock = int.from_bytes(data[i:i+4],byteorder='big') #每次要4个字节一起算，否则数据是有问题的
            reg ^= eachblock
            for i in range(32):
                if(reg & 0x80000000 == 0x80000000):
                    reg = ((reg << 1) & 0xFFFFFFFF) ^ poly
                else:
                    reg = reg << 1
        return struct.pack('>I',reg) # 为了与bytes比较是否相等，转化类型，>I表示大端序无符号32位整型

    @Slot()
    def readData(self):
        data_temp = self.ser.readAll().data()
        self.buffer.extend(data_temp)
        while(len(self.buffer) >= self.FRAME_LEN):
            if(self.buffer[0:2] == self.FRAME_HEADER):
                dbts = bytes(self.buffer[0:self.FRAME_LEN]) 
                del self.buffer[0:self.FRAME_LEN]
                #breakpoint()
                if(self.calcrc32(dbts[0:8]) == dbts[8:12]): #CRC校验通过
                    #breakpoint()
                    packageNumber = dbts[3] # 单独的这个直接就是int了，不用转换
                    self.currentSpeed = int.from_bytes(dbts[4:6],byteorder='big',signed=False)
                    self.targetSpeed = int.from_bytes(dbts[6:8],byteorder='big',signed=False)
                    if(self.packetIndex == None):
                        self.packetIndex = packageNumber
                    else:
                        self.packetIndex += 1
                        if(self.packetIndex & 0xFF != packageNumber):
                            self.packetLoss = packageNumber - self.packetIndex
                            self.packetIndex = packageNumber #如果丢了不止1包，要补上最新的
                            self.sig_packetLoss.emit(self.packetLoss)
                else:
                    #breakpoint()
                    self.errorCRCNum += 1
                    self.packetIndex += 1
                    self.sig_crc.emit()
                data_temp02 = ProtocolData(currentSpeed=self.currentSpeed,targetSpeed=self.targetSpeed)
                self.sig_receivedData.emit(data_temp02)
            else:
                del self.buffer[0]

    @Slot()
    def readDataDebug(self):
        data_temp = self.ser.readAll().data()
        self.buffer.extend(data_temp)
        while(len(self.buffer) >= self.FRAME_LEN_DEBUG):
            if(self.buffer[0:2] == self.FRAME_HEADER):
                dbts = bytes(self.buffer[0:self.FRAME_LEN_DEBUG])
                del self.buffer[0:self.FRAME_LEN_DEBUG]
                if(self.calcrc32(dbts[0:26]) == dbts[26:30]):
                    packageNumber = dbts[3]
                    self.currentSpeed = int.from_bytes(dbts[4:6],byteorder='big',signed=False)
                    self.targetSpeed = int.from_bytes(dbts[6:8],byteorder='big',signed=False)
                    self.duty = int.from_bytes(dbts[8:10],byteorder='big',signed=False)
                    #breakpoint()
                    self.P, self.I, self.D = struct.unpack('>fff',dbts[10:22])
                    #breakpoint()
                    self.timestamp = int.from_bytes(dbts[22:26],byteorder='big',signed=False)
                    if(self.packetIndex == None):
                        self.packetIndex = packageNumber
                    else:
                        self.packetIndex += 1
                        if(self.packetIndex & 0xFF != packageNumber):
                            self.packetLoss = packageNumber - self.packetIndex
                            self.packetIndex = packageNumber #如果丢了不止1包，要补上最新的
                            self.sig_packetLoss.emit(self.packetLoss)
                else:
                    self.errorCRCNum += 1
                    self.packetIndex += 1
                    self.sig_crc.emit()
                data_temp02 = ProtocolData(
                    currentSpeed=self.currentSpeed,
                    targetSpeed=self.targetSpeed,
                    duty=self.duty,
                    P=self.P,
                    I=self.I,
                    D=self.D,
                    timestamp=self.timestamp)
                self.sig_receivedData.emit(data_temp02)
                self.sig_savedata.emit(data_temp02)
            else:
                del self.buffer[0]

    @Slot()
    def closeport(self):
        if self.ser.isOpen():
            self.ser.clear()
            self.ser.close()
            self.buffer.clear()
            self.sig_serial_status.emit(True,SerialAction.CLOSE,'串口已关闭')
        # 还应该发个信号，清除datamanager的所有缓存