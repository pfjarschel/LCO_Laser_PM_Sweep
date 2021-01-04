# -*- coding: utf-8 -*-
"""
Created on Mon Jan 8 11:00:00 2019

@author: Paulo Jarschel
"""

import visa
import numpy as np

class ThorLabsPM300:

    stringsearch = "P300"
    ok = False
    pm = None
    rm = None

    def __init__(self):
        True

    def __del__(self):
        self.close()
        return 0

    def close(self):
        if self.ok:
            self.pm.close()
            self.ok = False

    def init(self):
        self.rm = visa.ResourceManager("@ni")
        list = self.rm.list_resources()
        self.pm = None
        for i in range(0, len(list)):
            if self.stringsearch in list[i]:
                self.pm = self.rm.open_resource(list[i])
                self.ok = True
                break

    def readPwr(self, db=True):
        if self.ok:
            val = float(self.pm.query("READ?"))
            if db:
                pwr = 10.0*np.log10(val/0.001)
                return pwr
            else:
                return val
        else:
            if db:
                return -99.99
            else:
                return 0.00
