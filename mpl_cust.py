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
# import matplotlib
# import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
# import matplotlib.dates as dates

import datetime


class MplSettings:
    def __init__(self, parent, canvas):
        self.parent = parent
        self.canvas = canvas

    def mpl_setup(self):
        self.parent.mplFig.subplots_adjust(left=0.15,
                                           right=0.98,
                                           bottom=0.07,
                                           top=0.97)
        self.parent.mpl_subplot.tick_params(axis='both',
                                            which='major',
                                            labelsize=12)
        self.parent.mpl_subplot.tick_params(axis='both',
                                            which='minor',
                                            labelsize=10)

    def mpl_value_settings(self, x_values, ymin, ymax):
        self.parent.mpl_subplot.xaxis.set_major_locator(ticker.MaxNLocator(
            integer=True))
        # self.parent.mpl_subplot.yaxis.set_minor_locator(
        # ticker.AutoMinorLocator())
        offset = 0.05*(max(x_values)-min(x_values))
        self.parent.mpl_subplot.set_xlim((min(x_values)-offset,
                                          max(x_values)+offset))
        self.parent.mpl_subplot.grid(True)
        self.parent.mpl_subplot.set_ylim((ymin, ymax))
        # self.parent.mplFig.autofmt_xdate()

    def mpl_date_settings(self, x_values, y_min, y_max):
        # space = None
        # set min and max values to display in x and y
        # TODO Add more reasonable comparisons here
        date_delta = max(x_values)-min(x_values)
        if date_delta >= datetime.timedelta(days=3650):
            space = datetime.timedelta(days=1095)
        elif datetime.timedelta(days=3650) > date_delta >= \
                datetime.timedelta(days=1095):
            space = datetime.timedelta(days=180)
        elif datetime.timedelta(days=1094) > date_delta >= \
                datetime.timedelta(days=366):
            space = datetime.timedelta(days=30)
        elif datetime.timedelta(days=365) > date_delta >= datetime.timedelta(
                days=1):
            space = datetime.timedelta(days=1)
        else:
            space = datetime.timedelta(hours=6)

        min_date = min(x_values)-space
        max_date = max(x_values)+space

        self.parent.mpl_subplot.set_xlim((min_date, max_date))
        self.parent.mpl_subplot.set_ylim((y_min, y_max))
        # add a nice looking grid
        self.parent.mpl_subplot.grid(True)

        labels = self.parent.mpl_subplot.get_xticklabels()
        for label in labels:
            label.set_rotation(75)

        self.parent.mplFig.autofmt_xdate()
        # hours = dates.HourLocator()
        # days = dates.DayLocator()
        # years = dates.YearLocator()   # every year
        # months = dates.MonthLocator()  # every month
        # major_formatter = dates.DateFormatter('%b')
        # minor_formatter = dates.DateFormatter('%j')
        # self.mpl_subplot.xaxis.set_major_locator(months)
        # self.mpl_subplot.xaxis.set_major_formatter(major_formatter)
        #
        # self.mpl_subplot.xaxis.set_minor_locator(days)
        # self.mpl_subplot.xaxis.set_minor_formatter(minor_formatter)

        # hfmt = dates.DateFormatter('%m/%d/%Y')
        # self.parent.mpl_subplot.xaxis.set_major_locator(dates.YearLocator())
        # self.parent.mpl_subplot.xaxis.set_major_formatter(hfmt)
        # plt.xticks(rotation='vertical') # not working - we work with figure
        # plt.subplots_adjust(bottom=0.5)

        #     label.set_color('orange')