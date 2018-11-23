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
# activate pycharm debugging
# import pydevd
# pydevd.settrace('localhost', port=55555, stdoutToServer=True,stderrToServer=True, suspend=False)

from qgis.PyQt.QtCore import (
    QObject,
    QSettings,
    Qt
)
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QAction
)
from qgis.PyQt.QtGui import (
    QIcon
)

from .mutantmap import MutantMap
from .mutantwidget import MutantWidget


class Mutant(object):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = self.iface.mapCanvas()

    def initGui(self):
        # add action to toolbar
        self.action = QAction(QIcon(":/plugins/mutant/img/icon.png"),
                              "Mutant",
                              self.iface.mainWindow())
        self.iface.addToolBarIcon(self.action)
        self.tool = MutantMap(self.canvas, self.action)
        self.saveTool = None
        self.action.triggered.connect(self.activateTool)
        self.tool.deactivated.connect(self.deactivateTool)

        # create the widget to display information
        self.mutantwidget = MutantWidget(self.iface)
        self.tool.moved.connect(self.mutantwidget.toolMoved)
        self.tool.pressed.connect(self.mutantwidget.toolPressed)
        self.mutantwidget.toggleMutant.clicked.connect(self.toggleTool)
        self.mutantwidget.plotOnMove.clicked.connect(self.toggleMouseClick)

        # create the dockwidget with the correct parent and add the widget
        self.mutantdockwidget = QDockWidget("Mutant",
                                            self.iface.mainWindow()
                                            )
        self.mutantdockwidget.setObjectName("Mutant")
        self.mutantdockwidget.setWidget(self.mutantwidget)
        # QObject.connect(self.mutantdockwidget,
        # SIGNAL('visibilityChanged ( bool )'), self.showHideDockWidget)

        # add the dockwidget to iface
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.mutantdockwidget)
        # self.mutantwidget.show()

    def unload(self):
        QSettings().setValue('plugins/mutant/mouseClick',
                             self.mutantwidget.plotOnMove.isChecked())
        self.mutantdockwidget.close()
        self.deactivateTool()
        # remove dockwidget from iface
        self.iface.removeDockWidget(self.mutantdockwidget)
        # remove plugin menu item and icon
        # self.iface.removePluginMenu("Analyses",self.action)
        self.iface.removeToolBarIcon(self.action)

    def toggleTool(self, active):
        self.activateTool() if active else self.deactivateTool()

    def toggleMouseClick(self, toggle):
        if toggle:
            self.activateTool(False)
        else:
            self.deactivateTool(False)
        self.mutantwidget.changeActive(False, False)
        self.mutantwidget.changeActive(True, False)

    def activateTool(self, changeActive=True):
        if self.mutantwidget.plotOnMove.isChecked():
            self.saveTool = self.canvas.mapTool()
            self.canvas.setMapTool(self.tool)
        if not self.mutantdockwidget.isVisible():
            self.mutantdockwidget.show()
        if changeActive:
            self.mutantwidget.changeActive(True)

    def deactivateTool(self, changeActive=True):
        if self.canvas.mapTool() and self.canvas.mapTool() == self.tool:
            # block signals to avoid recursion
            self.tool.blockSignals(True)
        if self.saveTool:
            self.canvas.setMapTool(self.saveTool)
            self.saveTool = None
        else:
            self.canvas.unsetMapTool(self.tool)

        self.tool.blockSignals(False)
        if changeActive:
            self.mutantwidget.changeActive(False)
