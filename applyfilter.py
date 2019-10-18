"""mutant - MUlti Temporal ANalysis Tool
begin			: 2014/10/15
copyright		: (c) 2014- by Werner Macho
email			: werner.macho@gmail.com

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.
"""
from builtins import range
from builtins import object
from scipy.signal import savgol_filter,medfilt,wiener
import numpy as np
__author__ = 'werner.macho@gmail.com'
__date__ = '2014/06/16'
__copyright__ = 'Copyright 2014, Werner Macho'


class ApplyFilter(object):

    def __init__(self, parent, canvas):
        self.parent = parent
        self.canvas = canvas

    def smooth(self, orig_x, orig_y,window=9,polyorder=3,perc=75,median=5):
        try:
            new_x = orig_x
            #new_y = medfilt(orig_y,median)
            new_y =[]
            for i in range(0,len(orig_x),median):
                y_subset = orig_y[i:i+median]
                pc = np.percentile(y_subset,perc)
                y_subset = [x if x>pc else pc for x in y_subset]
                new_y = new_y+y_subset


            #new_y = wiener(orig_y,mysize=window,noise=polyorder)
            new_y = savgol_filter(new_y, window_length=window, polyorder=polyorder)
        except Exception as e:
            print(e)
            new_x = []
            new_y = []
            for i in range(3, len(orig_x)-3):
                new_x.append(orig_x[i])
                try:
                    new_y.append((orig_y[i-3] + orig_y[i-2] + orig_y[i-1] + orig_y[i] + orig_y[i+1]+ orig_y[i+2]+ orig_y[i+3]) / 7.0)
                except TypeError:
                    new_y.append(None)

        return new_x, new_y

    def whittaker(self, orig_x, orig_y):
        new_x = []
        new_y = []
        return
