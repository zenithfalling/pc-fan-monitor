from PySide6.QtWidgets import (QButtonGroup, QComboBox, QRadioButton,QTextEdit,QWidget,QPushButton,QLabel,
                               QHBoxLayout,QVBoxLayout,QGridLayout,QFrame,QStackedWidget,QGroupBox,QMessageBox)
from PySide6.QtCore import QMutex, QObject, QTimer, Slot,QThread,Signal
from PySide6.QtSerialPort import QSerialPort,QSerialPortInfo
import pyqtgraph as pg
from enum import IntEnum

from pyqtgraph.graphicsItems.ScatterPlotItem import tr

class Mode(IntEnum):
    DEBUG = 1
    NORMAL = 2

# 重写串口下拉按钮类
class AutoSerialCombox(QComboBox):
    def __init__(self, parent = None):
        super().__init__(parent = None)

    def showPopup(self):
        self.refresh_ports()
        super().showPopup()

    def refresh_ports(self):
        current_selection = self.currentText()
        self.clear()
        port_info = QSerialPortInfo.availablePorts()
        port_list = [port.portName() for port in port_info]

        if port_list:
            self.addItems(port_list)
            if current_selection in port_list:
                self.setCurrentText(current_selection)
        else:
            self.addItem("未检测到串口")

class DebugPage(QWidget):
    def __init__(self,configMode,dataProcess,staProcess):
        super().__init__()
        self.configMode = configMode
        self.dataProcess = dataProcess
        self.staProcess = staProcess
        self.timer = QTimer(self)
        self.timer.setInterval(self.configMode["debug"]["plot_period"])
        self.timer.timeout.connect(self.debugPlot)
        layout_debugpage = QVBoxLayout(self)
        self.widget_speedRealtime = pg.PlotWidget()
        self.widget_speedRealtime.setBackground("w")
        self.widget_speedRealtime.setLabel("left","value",units="rpm")
        self.widget_speedRealtime.setXRange(0,self.configMode["debug"]["max_length"])
        self.widget_speedRealtime.setYRange(0,8000)
        self.widget_speedRealtime.setTitle("实时转速曲线",color="b",size="10pt",bold=True)
        self.curve01 = self.widget_speedRealtime.plot(pen=pg.mkPen("r",width=1.5),name="实际转速")
        self.curve02 = self.widget_speedRealtime.plot(pen=pg.mkPen("b",width=1.5),name="设定转速")
        layout_debugpage.addWidget(self.widget_speedRealtime)
        # 最后的点都标记数据，这个还得考虑
        self.text1 = pg.TextItem(color='r', anchor=(1, 0))  # anchor=(0,1) 表示文本左下角对齐数据点
        self.text2 = pg.TextItem(color='b', anchor=(0, 0))  # anchor=(0,0) 表示文本左上角对齐数据点
        self.widget_speedRealtime.addItem(self.text1)
        self.widget_speedRealtime.addItem(self.text2)

    def debugPlot(self):
        # 先获取数据
        self.debugData = self.dataProcess.get_debug_data()
        # 画图，更新数据，但是如果把数据放在一起，可能要拆分
        if(len(self.debugData["current_speed"]) == 0):
            return
        self.curve01.setData(self.debugData["current_speed"])
        self.curve02.setData(self.debugData["target_speed"])
        last_x = len(self.debugData["current_speed"]) - 1
        last_currentspeed = self.debugData["current_speed"][-1]
        last_targetspeed = self.debugData["target_speed"][-1]
        self.text1.setText(f"{last_currentspeed:.0f}")
        self.text1.setPos(last_x, last_currentspeed)
        self.text2.setText(f"{last_targetspeed:.0f}")
        self.text2.setPos(last_x, last_targetspeed)

    def clear_plot(self):
        self.curve01.setData([],[])
        self.curve02.setData([],[])
        self.text1.setText("--")
        self.text2.setText("--")

class NormalPage(QWidget):
    def __init__(self,configMode,dataProcess,staProcess):
        super().__init__()
        self.configMode = configMode
        self.dataProcess = dataProcess
        self.staProcess = staProcess
        self.timer = QTimer(self)
        self.timer.setInterval(self.configMode["normal"]["plot_period"])
        self.timer.timeout.connect(self.normalPlot)
        layout_normalpage = QHBoxLayout(self)
        self.widget_speedRealtime = pg.PlotWidget()
        self.widget_speedDiff = pg.PlotWidget()
        self.widget_speedRealtime.setBackground("w")
        self.widget_speedRealtime.setLabel("left","value",units="rpm")
        self.widget_speedRealtime.setXRange(0,self.configMode["normal"]["max_length"])
        self.widget_speedRealtime.setYRange(0,8000)
        self.widget_speedRealtime.setTitle("实时转速曲线",color="b",size="10pt",bold=True)
        self.widget_speedRealtime.addLegend()
        self.curve01 = self.widget_speedRealtime.plot(pen=pg.mkPen("r",width=1.5),name="实际转速")
        self.curve02 = self.widget_speedRealtime.plot(pen=pg.mkPen("b",width=1.5),name="设定转速")
        self.widget_speedDiff.setBackground("w")
        self.widget_speedDiff.setLabel('left','value')
        self.widget_speedDiff.setXRange(0,self.configMode["normal"]["max_length"])
        #self.widget_speedDiff.setYRange(0,8000)
        self.widget_speedDiff.setTitle("转速差",color="b",size="10pt",bold=True)
        self.widget_speedDiff.addLegend()
        self.curve03 = self.widget_speedDiff.plot(pen=pg.mkPen('b',width=1.5))
        layout_normalpage.addWidget(self.widget_speedRealtime)
        layout_normalpage.addWidget(self.widget_speedDiff)

    def normalPlot(self):
        self.normalData = self.dataProcess.get_normal_data()
        if(len(self.normalData["current_speed"]) == 0):
            return
        self.curve01.setData(self.normalData["current_speed"])
        self.curve02.setData(self.normalData["target_speed"])
        self.curve03.setData(self.normalData["buffer_speedgap"])

    def clear_plot(self):
        self.curve01.setData([],[])
        self.curve02.setData([],[])
        self.curve03.setData([],[])

class MainWindow(QWidget):
    sig_openserial = Signal(dict)
    sig_closeserial = Signal()
    sig_modeChange = Signal(int)
    sig_clearStaticsData = Signal()
    sig_clearPicBuffer = Signal()
    sig_savedata = Signal()
    sig_stopsave = Signal()

    def __init__(self,config_mode,dataProcess,serialProcess,staProcess,dataSaveProcess):
        super().__init__()
        self.configMode = config_mode
        self.dataProcess = dataProcess
        self.serialWorker = serialProcess
        self.staProcess = staProcess
        self.dataSaveProcess = dataSaveProcess
        self.sig_modeChange.connect(self.dataProcess.set_mode)
        self.sig_clearStaticsData.connect(self.staProcess.clear)
        self.sig_clearPicBuffer.connect(self.dataProcess.clear_pic_data)
        #
        self.serial_thread = QThread()
        self.serialWorker.moveToThread(self.serial_thread)
        self.sig_openserial.connect(self.serialWorker.open_port)
        self.sig_closeserial.connect(self.serialWorker.closeport)
        self.serialWorker.sig_serial_status.connect(self.serialStatus_changed)
        self.serialWorker.sig_receivedData.connect(self.dataProcess.save_data)
        self.serialWorker.sig_crc.connect(self.staProcess.on_crc_error)
        self.serialWorker.sig_packetLoss.connect(self.staProcess.on_packetloss)
        self.save_thread = QThread()
        self.dataSaveProcess.moveToThread(self.save_thread)
        self.dataSaveProcess.sig_save_success.connect(self.saveDataSuccessful)# 只是显示保存成功
        self.serialWorker.sig_savedata.connect(self.dataSaveProcess.write_data)
        self.sig_savedata.connect(self.dataSaveProcess.start_logging)
        self.sig_stopsave.connect(self.dataSaveProcess.stop_logging)
        self.statisTimer = QTimer(self) # 控制统计数据的显示刷新
        self.statisTimer.setInterval(2000)
        self.initUI()
        self.serial_thread.start()
        self.save_thread.start()

    def initUI(self):
        self.setWindowTitle("风扇转速监控")
        #总布局为水平布局
        main_layout = QHBoxLayout(self)

        left_container = QFrame()
        left_layout = QVBoxLayout(left_container)
        #串口配置部分
        window_serial = QFrame()
        layout_serial = QGridLayout(window_serial)
        layout_serial.addWidget(QLabel("串口号"),0,0)
        self.serialList = AutoSerialCombox()
        self.serialList.refresh_ports()
        layout_serial.addWidget(self.serialList,0,1)
        layout_serial.addWidget(QLabel("波特率"),1,0)
        self.baudList = QComboBox()
        self.baudList.addItem("115200",QSerialPort.BaudRate.Baud115200)
        self.baudList.addItem("230400",230400)
        self.baudList.addItem("460800",460800)
        self.baudList.addItem("614400",614400)
        layout_serial.addWidget(self.baudList,1,1)
        layout_serial.addWidget(QLabel("数据位"),2,0)
        self.dataBits = QComboBox()
        self.dataBits.addItem("7位",QSerialPort.DataBits.Data7)
        self.dataBits.addItem("8位",QSerialPort.DataBits.Data8)
        layout_serial.addWidget(self.dataBits,2,1)
        layout_serial.addWidget(QLabel("校验位"),3,0)
        self.parityBits = QComboBox()
        self.parityBits.addItem("无",QSerialPort.Parity.NoParity)
        self.parityBits.addItem("奇校验",QSerialPort.Parity.OddParity)
        self.parityBits.addItem("偶校验",QSerialPort.Parity.EvenParity)
        layout_serial.addWidget(self.parityBits,3,1)
        layout_serial.addWidget(QLabel("停止位"),4,0)
        self.stopBits = QComboBox()
        self.stopBits.addItem("1位",QSerialPort.StopBits.OneStop)
        self.stopBits.addItem("1.5位",QSerialPort.StopBits.OneAndHalfStop)
        self.stopBits.addItem("2位",QSerialPort.StopBits.TwoStop)
        layout_serial.addWidget(self.stopBits,4,1)
        self.openSerial_btn = QPushButton()
        self.openSerial_btn.setText("打开串口")
        self.openSerial_btn.clicked.connect(self.openSerial_btn_clicked)
        self.closeSerial_btn = QPushButton()
        self.closeSerial_btn.setText("关闭串口")
        self.closeSerial_btn.clicked.connect(self.closeSerial_btn_clicked)
        layout_serial.addWidget(self.openSerial_btn,5,0)
        layout_serial.addWidget(self.closeSerial_btn,5,1)
        layout_serial.addWidget(QLabel("串口状态"),6,0)
        self.serialStatus = QTextEdit()
        self.serialStatus.setText("未打开串口")
        layout_serial.addWidget(self.serialStatus,6,1)
        #模式切换部分
        group_box = QGroupBox("模式选择")
        box_layout = QHBoxLayout(group_box)
        self.debug_radio = QRadioButton("调试模式")
        self.normal_radio = QRadioButton("普通模式")
        self.debug_radio.setChecked(True)#初始化选择调试模式
        box_layout.addWidget(self.debug_radio)
        box_layout.addWidget(self.normal_radio)
        self.modeGroup = QButtonGroup()
        self.modeGroup.addButton(self.debug_radio,Mode.DEBUG)
        self.modeGroup.addButton(self.normal_radio,Mode.NORMAL)
        self.modeGroup.idClicked.connect(self.on_mode_changed)
        #调试数据保存到文件，仅调试模式有效
        group_box2 = QGroupBox("保存数据，仅调试模式")
        box2_layout = QHBoxLayout(group_box2)
        self.saveData_btn = QPushButton("开始保存")
        self.saveData_btn.clicked.connect(self.saveData_btn_clicked)
        self.stopSave_btn = QPushButton("停止保存")
        self.stopSave_btn.clicked.connect(self.stopSave_btn_clicked)
        # 缺少槽函数的连接
        self.saveData_btn.setEnabled(False) #默认禁用，确认是调试页面再启用
        self.stopSave_btn.setEnabled(False)
        box2_layout.addWidget(self.saveData_btn)
        box2_layout.addWidget(self.stopSave_btn)
        #统计信息部分
        window_status = QFrame()
        layout_status = QGridLayout(window_status)
        layout_status.addWidget(QLabel("CRC校验失败"),0,0)
        self.crcStatus = QTextEdit()
        self.crcStatus.setText("0")
        layout_status.addWidget(self.crcStatus,0,1)
        layout_status.addWidget(QLabel("丢包数"),1,0)
        self.lossPackage = QTextEdit()
        self.lossPackage.setText("0")
        layout_status.addWidget(self.lossPackage,1,1)
        self.clearData_btn = QPushButton()
        self.clearData_btn.setText("统计清零")
        self.clearData_btn.clicked.connect(self.clearData_btn_clicked)
        #缺少信号与槽的连接
        self.clearPicture_btn = QPushButton()
        self.clearPicture_btn.setText("清除图像")
        self.clearPicture_btn.clicked.connect(self.clearPicture_btn_clicked)
        layout_status.addWidget(self.clearData_btn,3,0)
        layout_status.addWidget(self.clearPicture_btn,3,1)
        #左侧布局添加
        left_layout.addWidget(window_serial)
        left_layout.addWidget(group_box)
        left_layout.addWidget(group_box2)
        left_layout.addWidget(window_status)
        #图像界面不同显示页面
        self.stack = QStackedWidget()
        self.debug_page = DebugPage(self.configMode,self.dataProcess,self.staProcess)
        self.normal_page = NormalPage(self.configMode,self.dataProcess,self.staProcess)
        self.stack.addWidget(self.debug_page)
        self.stack.addWidget(self.normal_page)
        self.stack.currentChanged.connect(self.on_page_changed)# 存在页面切换，启动或停止计时器
        # 界面的映射关系
        self.page_map = {
            Mode.DEBUG: self.debug_page,
            Mode.NORMAL: self.normal_page}

        main_layout.addWidget(left_container)
        main_layout.addWidget(self.stack)


    def openSerial_btn_clicked(self):
        #打开串口对应槽函数
        self.openSerial_btn.setEnabled(False)
        self.closeSerial_btn.setEnabled(False)
        serialConfig = {
            'port_name':self.serialList.currentText(),
            'baud_rate':self.baudList.currentData(),
            'databits':self.dataBits.currentData(),
            'paritybits':self.parityBits.currentData(),
            'stopbits':self.stopBits.currentData()
            }
        self.sig_openserial.emit(serialConfig)
        #所有串口配置的参数合集到一个变量，只传递这一个

    def closeSerial_btn_clicked(self):
        #关闭串口对应槽函数
        self.openSerial_btn.setEnabled(False)
        self.closeSerial_btn.setEnabled(False)
        self.sig_closeserial.emit()

    def serialStatus_changed(self,status,category,msg):
        if(category == 1):# 1是打开，2是关闭
            if(status == True):
                self.openSerial_btn.setEnabled(False)
                self.closeSerial_btn.setEnabled(True)
                self.serialStatus.setText(msg)
            else:
                self.openSerial_btn.setEnabled(True)
                self.closeSerial_btn.setEnabled(False)
                self.serialStatus.setText("串口打开失败 " + msg)
        else:
            if(status == True):
                self.openSerial_btn.setEnabled(True)
                self.closeSerial_btn.setEnabled(False)
                self.serialStatus.setText(msg)
                #是否考虑串口关闭失败的情况？

    def on_mode_changed(self,mode_id):
        #选择不同的模式对应的页面变更，AI的建议是搞个映射，然后不同模式切换。
        page = self.page_map[mode_id]
        self.stack.setCurrentWidget(page)
        self.sig_modeChange.emit(mode_id)#改变datamanager里的set_mode，改变模式的同时改变变量数据

    def on_page_changed(self):
        # 页面切换的时候也处理定时器
        current_page = self.stack.currentWidget()
        self.debug_page.timer.stop()
        self.normal_page.timer.stop()
        if current_page is self.debug_page:
            self.saveData_btn.setEnabled(True)
            self.stopSave_btn.setEnabled(True)
            self.debug_page.timer.start()
            self.statisTimer.setInterval(self.configMode["debug"]["plot_period"])
        elif current_page is self.normal_page:
            self.saveData_btn.setEnabled(False)
            self.stopSave_btn.setEnabled(False)
            self.normal_page.timer.start()
            self.statisTimer.setInterval(self.configMode["normal"]["plot_period"])

    def saveData_btn_clicked(self):
        self.saveData_btn.setEnabled(False)
        self.stopSave_btn.setEnabled(True)
        self.sig_savedata.emit()

    def stopSave_btn_clicked(self):
        self.saveData_btn.setEnabled(True)
        self.stopSave_btn.setEnabled(False)
        self.sig_stopsave.emit()


    def set_statistics_data(self):
        # 定时更新统计信息显示部分
        stadata = self.staProcess.get_statistics_data()
        self.crcStatus.setText(str(stadata["crc_num"]))
        self.lossPackage.setText(str(stadata["packetloss"]))

    def clearData_btn_clicked(self):
        # 在这里设置显示0会不会有问题，就是还没清除，定时器又来了，显示个0，就清不了了
        self.lossPackage.setText("0")
        self.crcStatus.setText("0")
        self.sig_clearStaticsData.emit()


    def clearPicture_btn_clicked(self):
        current_page = self.stack.currentWidget()
        if current_page == self.debug_page:
            self.debug_page.clear_plot()
        elif current_page == self.normal_page:
            self.normal_page.clear_plot()
        else:
            return
        self.sig_clearPicBuffer.emit()# 清除图像的同时清除数据缓存

    def saveDataSuccessful(self):
        QMessageBox.information(None,"提示信息","文件已写入")