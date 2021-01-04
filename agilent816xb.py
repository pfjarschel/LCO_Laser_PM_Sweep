# -*- coding: utf-8 -*-

import visa
import numpy as np


class Agilent816xb:
    # definitions
    gpib = True
    eth = False
    usb = False
    gpibAddr = 17
    ip = "192.168.1.2"
    port = 10001
    visarm = None
    visaOK = False
    laser = None
    laserOK = False
    laserID = ""

    # main functions
    def __init__(self):
        try:
            self.visarm = visa.ResourceManager('@ni')
            self.visaOK = True
        except:
            print("Error creating VISA Resource Manager! Is the GPIB Card connected?")
            pass
        if not self.visaOK:
            try:
                self.visarm = visa.ResourceManager('@py')
                self.visaOK = True
            except:
                print("Error creating VISA Resource Manager! Is the GPIB Card connected?")
                pass

    def __del__(self):
        self.closelaser()
        return 0

    # laser functions

    def connectlaser(self, isgpib=True, address=17, iseth=False, ethip="192.168.1.2", ethport=10001):
        if self.visaOK:
            self.gpib = isgpib
            self.gpibAddr = address
            self.eth = iseth
            self.ip = ethip
            self.port = ethport
            try:
                if self.gpib:
                    lasername = "GPIB0::" + str(self.gpibAddr) + "::INSTR"
                    self.laser = self.visarm.open_resource(lasername)
                # elif self.eth:
                #     osaname = "TCPIP0::" + self.ip + "::" + str(self.port) + "::SOCKET"
                #     self.laser = self.visarm.open_resource(osaname, read_termination="\r\n", timeout=5000)
                #     self.laser.query('open "' + self.user + '"')
                #     self.laser.query(self.passwd)
                if "816" in self.laser.query("*IDN?"):
                    self.laserOK = True
                else:
                    print("Error opening lasererator! Is it connected?")
            except:
                print("Error opening lasererator! Is it connected?")
                pass

    def initlaser(self):
        return 0

    def enableAll(self):
        for i in range(0, 5):
             self.setState(i, True)

    def disableAll(self):
        for i in range(0, 5):
             self.setState(i, False)

    def closelaser(self):
        if self.laserOK:
            self.laserOK = False
            self.laser.close()

    def getWL(self, slot):
        if self.laserOK:
            resp = self.laser.query(f":sour{slot}:wav?")
            wl = float(resp)*1e9
            return wl
        else:
            return float(0.0)

    def setWL(self, slot, wl):
        if self.laserOK:
            self.laser.write(f"sour{slot}:wav {wl*1e-9}")

    def getPwr(self, slot):
        if self.laserOK:
            pwr = float(self.laser.query(f":sour{slot}:pow?"))
            return pwr
        else:
            return -99.99

    def setPwr(self, slot, pwr):
        if self.laserOK:
            self.laser.write(f":sour{slot}:pow {pwr}")

    def getState(self, slot):
        if self.laserOK:
            resp = self.laser.query(f":sour{slot}:pow:stat?")
            if "0" in resp:
                return False
            else:
                return True
        else:
            return False

    def setState(self, slot, onoff):
        if self.laserOK:
            if onoff:
                self.laser.write(f":sour{slot}:pow:stat 1")
            else:
                self.laser.write(f":sour{slot}:pow:stat 0")

    def setSweep(self, slot, mode, start, stop, step, cycles, dwell, speed):
        if self.laserOK:
            if mode != "CONT" and mode != "STEP":
                mode = "CONT"
            self.laser.write(f":sour{slot}:wav:swe:mode {mode}")
            self.laser.write(f":sour{slot}:wav:swe:start {start}nm")
            self.laser.write(f":sour{slot}:wav:swe:stop {stop}nm")
            self.laser.write(f":sour{slot}:wav:swe:step {step}nm")
            self.laser.write(f":sour{slot}:wav:swe:cycl {cycles}")
            self.laser.write(f":sour{slot}:wav:swe:dwel {dwell}ms")
            self.laser.write(f":sour{slot}:wav:swe:spe {speed}nm/s")

    def setSweepState(self, slot, state):
        if self.laserOK:
            options = ["Stop", "Start", "Pause (Stepped)", "Continue (Stepped)"]
            self.laser.write(f":sour{slot}:wav:swe:stat {options.index(state)}")