from PyQt5 import QtGui, uic, QtCore
from PyQt5.QtWidgets import QFileDialog
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import sys, os
import numpy as np
import c3d
import cv2
import qtm
import asyncio
from quamash import QSelectorEventLoop

from extensions.GLTextItem import GLTextItem
from scriptsGui import ScriptsGUI

class MotionGUI:
    def __init__(self):
        # Placeholder data while waiting for stream to connect
        self.data = np.array([(0,0,0)])
        
        self.window = uic.loadUi("./ui/streamGui.ui")
        self.window.show()
        
        # Setup plotting window
        self.plot = self.window.findChild(gl.GLViewWidget, "plot")
        self.plot.setCameraPosition(distance = 3000)
        self.scatter = gl.GLScatterPlotItem(pos = self.data)
        self.plot.addItem(self.scatter)
        
        self.frame = 0
        
        # IP address textbox. Give localhost as default.
        self.tbIP = self.window.findChild(QtGui.QLineEdit, "tbIP")
        self.tbIP.setText("127.0.0.1")
        
        self.btStream = self.window.findChild(QtGui.QPushButton, "btStream")
        self.btStream.clicked.connect(self.loadStream)

        self.btScripts = self.window.findChild(QtGui.QPushButton, "btScripts")
        self.btScripts.clicked.connect(self.openScripts)
        
        self.btRecord = self.window.findChild(QtGui.QPushButton, "btRecord")
        self.btRecord.clicked.connect(self.recordPlot)
        self.btRecord.setText("Record Data")
        self.recordStyle = self.btRecord.styleSheet()
        self.recording = False
        self.out = []

        self.scripts = ScriptsGUI(self)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(30)

    def update(self):
        self.frame = 0
        
    def openScripts(self):
        self.scripts.window.show()
        
    # A non-async function that calls the async function to run the data stream
    def loadStream(self):
        asyncio.ensure_future(self.setupStream())
        asyncio.get_event_loop().run_forever()
    
    # Connect to given IP and set up packet collection at 30 fps
    async def setupStream(self):
        ip = self.tbIP.text()
        connection = await qtm.connect(ip)
        if connection is None:
            return
        await connection.stream_frames(frames = "frequency:30", components = ["3d"], on_packet = self.onPacket)
        
    # When a packet is recieved, update plot and if recording, add to file
    def onPacket(self, packet):
        self.data = []
        header, markers = packet.get_3d_markers()
        for marker in markers:
            self.data.append((marker.x, marker.y, marker.z))
        data = self.scripts.parseData(self.data)
        self.scatter.setData(pos = np.array(data))
        
        if self.recording:
            self.out.append(data)
                     
    def openScripts(self):
        self.scripts.window.show()
        
    
    def recordPlot(self):
        if self.recording:
            # Saves the recorded data as a .npy file
            dialog = QFileDialog()
            fl = dialog.getSaveFileName(self.window, "Save Recorded Data", "", "NumPy file (*.npy)")
            if fl[0] == "":
                Print("ERROR: No filename selected. Data not saved")
                return
            self.btRecord.setText("Record Data")
            self.btRecord.setStyleSheet(self.recordStyle)
            self.recording = False
            np.save(fl[0], self.out)
        else:
            # Change UI apperance to show recording has started
            self.btRecord.setText("Stop Recording")
            self.btRecord.setStyleSheet("background-color: red")
            self.data = []
            if not os.path.exists("./temp/"):
                os.mkdir("./temp")
            self.recording = True
            self.frame = 0

## Start Qt event loop unless running in interactive mode.
if __name__ == '__main__':
    import sys
    app = QtGui.QApplication(sys.argv)
    loop = QSelectorEventLoop(app)
    asyncio.set_event_loop(loop)
    gui = MotionGUI()
    #if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    QtGui.QApplication.instance().exec_()