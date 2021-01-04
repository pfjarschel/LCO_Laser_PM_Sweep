# -*- coding: utf-8 -*-

"""
Created on Thu Oct 29 14:59:19 2020

@author: pfjarschel
"""

import sys, time, os.path, datetime
import pickle
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from threading import Timer, Thread, Lock
from PyQt5 import uic
from PyQt5.QtCore import Qt, QCoreApplication, QTimer, QDir
from PyQt5.QtWidgets import QApplication, QFileDialog, QWidget, QSpinBox, QDoubleSpinBox, QCheckBox
from PyQt5.QtGui import QIcon

import thorlabsPM300
import agilent816xb

FormUI, WindowUI = uic.loadUiType("MainWindow.ui")


class MainWindow(FormUI, WindowUI):

    simulate = False

    def __init__(self):
        super(MainWindow, self).__init__()
        
        self.pm = None
        self.laser = None
        self.measurements = []
        self.timestamps = []
        self.xaxis = []
        self.prev_measurements = []
        self.prev_timestamps = []
        self.prev_xaxis = []
        self.measTimer = None
        self.busymeas = False
        self.meas_i = 0
        self.launchtime = []
        self.launchwl = []
        self.stoptime = []
        self.stopwl = []
        self.sweepspan = 0
        self.sweepesttime = 0
        self.timeout = 10.00
        self.settingsfile = "settings.p"
        self.tempfile = "temp_results.txt"
        self.fullpath = str(__file__)
        self.lastdir = QDir.homePath()

        # Testing stuff
        self.sweep_start_delay = 2000
        self.test_noise = 1e-1
        self.avg_power_mw = 1.0
        self.real_wav = 0
        self.gauss_A_0 = 1.0
        self.gauss_X0_0 = 0.5
        self.gauss_W_0 = 0.1

        self.setupUi(self)
        self.setupOtherUi()
        self.SetupActions()
        self.show()
        # self.setWindowIcon(QIcon("micro.ico"))

        resizeEvent = self.OnWindowResize

        # self.delayedInit = Timer(0.1, self.InitializeDevices)
        self.InitializeDevices()
        # self.delayedInit.start()

    def OnWindowResize(self, event):
        pass

    def setupOtherUi(self):
        self.statusbar.showMessage(f"Initializing...")

        self.figure = plt.figure()
        self.graph = FigureCanvas(self.figure)
        self.graphToolbar = NavigationToolbar(self.graph, self)
        self.graphHolder.addWidget(self.graphToolbar)
        self.graphHolder.addWidget(self.graph)
        self.graph_ax = self.figure.add_subplot()
        self.graph_ax.set_xlabel("Wavelength (nm)")
        self.graph_ax.set_ylabel("Power (dBm)")
        self.graph_ax.set_title("Transmission")
        self.graph_ax.grid(True)
        self.graph.draw()

        self.loadSettings()

    def SetupActions(self):
        # Buttons and etc
        self.startBut.clicked.connect(self.startMeas)
        self.stopBut.clicked.connect(self.stopClick)
        self.saveBut.clicked.connect(self.saveClick)
        self.clearprevBut.clicked.connect(self.clearPreviousData)
        self.loadprevBut.clicked.connect(self.loadPreviousData)

        # Timers
        self.measTimer = QTimer()
        self.measTimer.timeout.connect(self.measLoop)
        self.measTimer.setInterval(1)

    def InitializeDevices(self):
        self.statusbar.showMessage(f"Initializing...")
        self.laser = agilent816xb.Agilent816xb()
        self.pm = thorlabsPM300.ThorLabsPM300()
        if not self.simulate:
            self.pm.init()
            self.laser.connectlaser(True, 17)

        statstr = ""
        if self.laser.laserOK:
            statstr = statstr + "Laser OK."
        else:
            statstr = statstr + "Laser Error."
        if self.pm.ok:
            statstr = statstr + " Power Meter OK."
        else:
            statstr = statstr + " Power Meter Error."
        
        self.statusbar.showMessage(statstr)

    def startMeas(self):
        self.statusbar.showMessage(f"Starting measurement...")
        self.laser.setState(self.slotSpin.value(), True)
        
        if self.keepplotCheck.isChecked():
            for i in range(0, len(self.measurements)):
                self.prev_measurements.append(self.measurements[i])
                self.prev_timestamps.append(self.timestamps[i])
                self.prev_xaxis.append(self.xaxis[i])
        self.measurements = []
        self.timestamps = []
        self.xaxis = []
        self.meas_i = 0
        self.launchtime = []
        self.launchwl = []
        self.stoptime = []
        self.stopwl = []

        self.figure.clear()
        self.graph_ax = self.figure.add_subplot()
        self.graph_ax.set_xlabel("Time stamp (s)")
        self.graph_ax.set_ylabel("Power (dBm)")
        self.graph.draw()
        
        self.prepareSweep()


    def stopMeas(self):
        self.measTimer.stop()
        self.laser.setSweepState(self.slotSpin.value(), "Stop")
        if self.turnoffCheck.isChecked():
            self.laser.disableAll()
        self.statusbar.showMessage(f"Measurement stopped")

    def stopClick(self):
        self.endSweep(time.time())
        self.stopMeas()
        self.processFinal()

    def prepareSweep(self):
        self.measurements.append([])
        self.timestamps.append([])
        self.laser.setWL(self.slotSpin.value(), self.startSpin.value())
        self.laser.setSweep(self.slotSpin.value(), "CONT", self.startSpin.value(),
                            self.stopSpin.value(), 1, 1, 0, self.speedSpin.value())
        self.laser.setSweepState(self.slotSpin.value(), "Start")
        
        if self.simulate:
            r1 = (1 + 2*np.random.uniform(-self.test_noise, self.test_noise))
            r2 = (1 + 3*np.random.uniform(-self.test_noise, self.test_noise))
            r3 = (1 + 2*np.random.uniform(-self.test_noise, self.test_noise))
            self.gauss_A = self.gauss_A_0*r1
            self.gauss_X0 = self.gauss_X0_0*r2
            self.gauss_W = self.gauss_W_0*r3

        self.launchwl.append(self.startSpin.value())
        startime = time.time()
        prep_elapsed = time.time() - startime
        while self.launchwl[-1] <= self.startSpin.value() and prep_elapsed < self.timeout:
            if not self.simulate:
                self.launchwl[-1] = self.laser.getWL(self.slotSpin.value())
            else:
                if (time.time() - startime)*1000.0 >= self.sweep_start_delay:
                    self.launchwl[-1] = self.startSpin.value() + np.random.uniform(0.000, 0.1)
            prep_elapsed = time.time() - startime
        
        self.launchtime.append(time.time())
        self.sweepspan = np.abs(self.stopSpin.value() - self.launchwl[-1])
        if self.launchwl[-1] < 100:
            self.sweepesttime = (self.stopSpin.value() - self.startSpin.value())/self.speedSpin.value()
        else:
            self.sweepesttime = self.sweepspan/self.speedSpin.value()

        if not self.simulate:
            pwr = self.pm.readPwr()
        else:
            pwr = self.test_response(self.launchwl[-1])
        self.measurements[-1].append(pwr)
        self.timestamps[-1].append(0)

        self.measTimer.start()

        self.statusbar.showMessage(f"Measuring ({self.meas_i + 1}/{self.sweepsSpin.value()})...")

    def measLoop(self):
        thistime = time.time()
        if thistime - self.launchtime[-1] < self.sweepesttime:
            if not self.simulate:
                pwr = self.pm.readPwr()
            else:
                self.real_wav = self.launchwl[-1] + \
                                (thistime - self.launchtime[-1])*self.speedSpin.value()
                if self.real_wav > self.stopSpin.value():
                    self.real_wav = self.stopSpin.value()
                pwr = self.test_response(self.real_wav)
            self.measurements[-1].append(pwr)
            self.timestamps[-1].append(thistime - self.launchtime[-1])
            if self.updateplotCheck.isChecked():
                self.updatePlot()

        else:
            self.endSweep(thistime)
            self.updatePlot()

            if self.meas_i >= self.sweepsSpin.value():
                self.stopMeas()
                self.processFinal()
                self.plotFinal()
                self.statusbar.showMessage(f"Measurement done!")
            else:                
                self.prepareSweep()

    def endSweep(self, thistime):
        self.meas_i += 1
        self.measTimer.stop()
        self.stoptime.append(thistime)
        if not self.simulate:
            self.stopwl.append(self.laser.getWL(self.slotSpin.value()))
            pwr = self.pm.readPwr()
        else:
            self.real_wav = self.launchwl[-1] + \
                            (thistime - self.launchtime[-1])*self.speedSpin.value()
            if self.real_wav > self.stopSpin.value():
                self.real_wav = self.stopSpin.value()
            self.stopwl.append(self.real_wav)
            pwr = self.test_response(self.real_wav)
        self.measurements[-1].append(pwr)
        self.timestamps[-1].append(thistime - self.launchtime[-1])
        self.laser.setSweepState(self.slotSpin.value(), "Stop")

        self.xaxis.append([0]*len(self.timestamps[-1]))
        lastslash = self.fullpath.rfind("/")
        path = self.fullpath[:lastslash + 1] + self.tempfile
        self.saveMeas(path)

    def updatePlot(self):
        self.figure.clear()
        self.graph_ax = self.figure.add_subplot()
        self.graph_ax.set_xlabel("Time stamp (s)")
        self.graph_ax.set_ylabel("Power (dBm)")
        self.graph_ax.set_title("Transmission")
        self.graph_ax.grid(True)

        # if self.keepplotCheck.isChecked():
        #     for i in range(0, len(self.prev_measurements)):
        #         self.graph_ax.plot(self.prev_timestamps[i], self.prev_measurements[i], 
        #                             linestyle='dotted', marker='None')
        for i in range(0, len(self.measurements)):
            self.graph_ax.plot(self.timestamps[i], self.measurements[i], 
                                linestyle='-', marker='None')
        
        # if self.legendCheck.isChecked():
        #     self.graph_ax.legend(range(1, 1 + len(self.measurements) + len(self.prev_measurements)))

        self.graph.draw()

    def processFinal(self):
        for i in range(0, len(self.measurements)):
            wavslope = (self.stopwl[i] - self.launchwl[i])/(self.stoptime[i] - self.launchtime[i])
            
            for j in range(0, len(self.measurements[i])):
                wl = self.launchwl[i] + self.timestamps[i][j]*wavslope
                self.xaxis[i][j] = wl

        lastslash = self.fullpath.rfind("/")
        path = self.fullpath[:lastslash + 1] + self.tempfile
        self.saveMeas(path)

    def plotFinal(self):
        self.figure.clear()
        self.graph_ax = self.figure.add_subplot()
        self.graph_ax.set_xlabel("Wavelength (nm)")
        self.graph_ax.set_ylabel("Power (dBm)")
        self.graph_ax.set_title("Transmission")
        self.graph_ax.grid(True)

        if self.keepplotCheck.isChecked():
            for i in range(0, len(self.prev_measurements)):
                self.graph_ax.plot(self.prev_xaxis[i], self.prev_measurements[i], 
                                    linestyle='dotted', marker='None')
        for i in range(0, len(self.measurements)):
            self.graph_ax.plot(self.xaxis[i], self.measurements[i],
                                linestyle='-', marker='None')
        
        if self.legendCheck.isChecked():
            self.graph_ax.legend(range(1, 1 + len(self.measurements) + len(self.prev_measurements)))
        
        self.graph.draw()
    
    def test_response(self, wl):
        a = self.gauss_A
        x0 = self.startSpin.value() + self.gauss_X0*self.sweepspan
        w = self.gauss_W*self.sweepspan
        pwr = self.avg_power_mw*a*np.exp(-((wl - x0)**2)/(2*w**2)) + np.random.uniform(0.01, 2*self.test_noise)
        pwrdbm = 10.0*np.log10(pwr)
        time.sleep(0.1*(1 + np.random.uniform(-self.test_noise, self.test_noise)))
        return pwrdbm

    def saveClick(self):
        self.statusbar.showMessage(f"Saving measurement...")
        file = QFileDialog.getSaveFileName(self, "Save file", self.lastdir, "Text files (*.txt)")
        filename = file[0]
        if filename != "":
            if filename[-4:] != ".txt" and filename[-4:] != ".TXT":
                filename = filename + ".txt"   
        else:
            filename = QDir.homePath() + f"/lost_measurement_{time.time():.0f}.txt"
        
        lastslash = filename.rfind("/")
        self.lastdir = filename[:lastslash + 1]
        self.saveMeas(filename)

    def saveMeas(self, name):
        with open(name, "w") as file:
            max_rows = 0
            rows = []
            for i in range(0, len(self.measurements)):
                rows.append(len(self.measurements[i]))
                if len(self.measurements[i]) > max_rows:
                    max_rows = len(self.measurements[i])
                file.write(f"{i}_Time (s)\t{i}_Wavlength (nm)\t{i}_Power (dBm)")
                if i < len(self.measurements) - 1:
                    file.write("\t")
                else:
                    file.write("\n")

            for j in range(0, max_rows):
                for i in range(0, len(self.measurements)):
                    if j < rows[i]:
                        file.write(f"{self.timestamps[i][j]:.4f}\t{self.xaxis[i][j]:.4f}\t{self.measurements[i][j]:.4f}")
                    else:
                        file.write(f"\t\t")
                    if i < len(self.measurements) - 1:
                        file.write("\t")
                    else:
                        file.write("\n")
            file.close()
            
        self.statusbar.showMessage(f"Measurement saved!")

    def clearPreviousData(self):
        self.prev_measurements = []
        self.prev_timestamps = []
        self.prev_xaxis = []

        self.plotFinal()

    def loadPreviousData(self):
        self.statusbar.showMessage(f"Loading data...")
        file = QFileDialog.getOpenFileName(self, "Open file", self.lastdir, "Text files (*.txt)")
        filename = file[0]
        
        lastslash = filename.rfind("/")
        self.lastdir = filename[:lastslash + 1]
        
        if os.path.isfile(filename):
            with open(filename, "r") as file:
                lines = file.readlines()
                n_prev_meas = len(self.prev_measurements)

                line0 = lines[0].strip("\n")
                fields0 = line0.split("\t")
                n_meas = int(np.floor(len(fields0)/3))
                for i in range(n_meas):
                    self.prev_measurements.append([])
                    self.prev_timestamps.append([])
                    self.prev_xaxis.append([])

                for i in range(1, len(lines)):
                    line = lines[i].strip("\n")
                    fields = line.split("\t")
                    for j in range(len(fields)):
                        if j % 3 == 0:
                            self.prev_timestamps[n_prev_meas + int(np.floor(j/3))].append(float(fields[j]))
                        if j % 3 == 1:
                            self.prev_xaxis[n_prev_meas + int(np.floor(j/3))].append(float(fields[j]))
                        if j % 3 == 2:
                            self.prev_measurements[n_prev_meas + int(np.floor(j/3))].append(float(fields[j]))
                file.close()
        self.plotFinal()
        self.statusbar.showMessage(f"Data loaded!")

    def saveSettings(self):
        settings_dict = {}
        settings_dict["__lastdir__"] = self.lastdir
        for w in self.findChildren(QSpinBox):
            settings_dict[w.objectName()] = w.value()
        for w in self.findChildren(QDoubleSpinBox):
            settings_dict[w.objectName()] = w.value()
        for w in self.findChildren(QCheckBox):
            settings_dict[w.objectName()] = w.isChecked()

        pickle.dump(settings_dict, open(self.settingsfile, "wb"))
        
    def loadSettings(self):
        lastslash = self.fullpath.rfind("/")
        path = self.fullpath[:lastslash + 1] + self.settingsfile

        if os.path.isfile(path):
            settings_dict = pickle.load(open(path, "rb"))
            if "__lastdir__" in settings_dict:
                self.lastdir = settings_dict["__lastdir__"]
            for key in settings_dict:
                if key[:2] != "__" and key[-2:] != "__":
                    w = self.findChild(QWidget, key)
                    if "Spin" in key:
                        w.setValue(settings_dict[key])
                    if "Check" in key:
                        w.setChecked(settings_dict[key])

    def CloseDevices(self):
        if self.turnoffCheck.isChecked():
            self.laser.disableAll()
        self.laser.closelaser()
        self.pm.close()
        self.statusbar.showMessage(f"Devices closed")

    def closeEvent(self, event):
        self.saveSettings()
        self.CloseDevices()

#Run
if __name__ == "__main__":

    app = QApplication(sys.argv)
    window = MainWindow()

    sys.exit(app.exec_())