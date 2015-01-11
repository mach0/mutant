"""mutant - MUlti Temporal ANalysis Tool
begin			: 2014/06/16
copyright		: (c) 2014- by Werner Macho
email			: werner.macho@gmail.com

based on valuetool
copyright		: (C) 2008-2010 by G. Picard

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.
"""
__author__ = 'werner.macho@gmail.com'
__date__ = '2014/06/16'
__copyright__ = 'Copyright 2014, Werner Macho'

import pyqtgraph as pg
import time
from PyQt4 import QtCore
import datetime

# def pqg_settings():
#     style_values = QtCore.Qt.DashLine
#     style_filter = QtCore.Qt.DashLine
#     return style_values, style_filter


class DateTimeAxis(pg.AxisItem):
    time_enabled = False
    # def tickValues(self, min, max, size):
    #     if self.time_enabled:
    #         res = [
    #             (datetime.timedelta(days=365, hours=6), 0),
    #             (datetime.timedelta(months=3), 0),
    #             (datetime.timedelta(months=1), 0)
    #         ]
    #         return res
    #     else:
    #         return pg.AxisItem.tickValues(self, min, max, size)

    def set_time_enabled(self, time_enabled):
        self.time_enabled = time_enabled

    def tickStrings(self, values, scale, spacing):

        if values is None or len(values) <= 0:
            return []

        if self.time_enabled:
            strns = []
            timerange = max(values)-min(values)

            if timerange < 3600*24:  # less than one day
                string = '%H:%M:%S'
                label1 = '%b %d  %Y -'
                label2 = ' %b %d, %Y'
            elif 3600*24 <= timerange < 3600*24*30:  # approx one month
                string = '%d %H:%M'
                label1 = '%b - '
                label2 = '%b, %Y'
            elif 3600*24*30 <= timerange < 3600*24*30*24:  # approx 2 years
                string = '%b %y'
                label1 = '%Y -'
                label2 = ' %Y'
            elif timerange >= 3600*24*30*24:  # more than 2 years
                string = '%Y'
                label1 = ''
                label2 = ''

            for x in values:
                try:
                    strns.append(time.strftime(string, time.localtime(x)))
                except ValueError:  # Windows can't handle dates before 1970
                    strns.append('')
            try:
                # label = time.strftime(label1, time.localtime(min(
                # values)))+time.strftime(label2, time.localtime(max(values)))
                # label = time.strftime(label1, time.localtime(min(values)))
                pass
            except ValueError:
                pass
                # label = ''
                # self.setLabel(text=label) # sets label below graph
            return strns
        else:
            strns = []

            for val in values:
                try:
                    strns.append('%.0f' % val)
                except ValueError:  # Windows can't handle dates before 1970
                    strns.append('')
            # self.setLabel(text='')
            return strns


class DateTimeViewBox(pg.ViewBox):
    pass
    # def __init__(self, *args, **kwds):
    #     pg.ViewBox.__init__(self, *args, **kwds)
    #     self.setMouseMode(self.RectMode)
    #
    # ## reimplement right-click to zoom out
    # def mouseClickEvent(self, ev):
    #     if ev.button() == QtCore.Qt.RightButton:
    #         self.autoRange()
    #
    # def mouseDragEvent(self, ev):
    #     if ev.button() == QtCore.Qt.RightButton:
    #         ev.ignore()
    #     else:
    #         pg.ViewBox.mouseDragEvent(self, ev)