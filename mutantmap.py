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

from qgis.PyQt.QtCore import Qt, QPoint, pyqtSignal
from qgis.PyQt.QtGui import QCursor, QPixmap

from qgis.gui import QgsMapTool


class MutantMap(QgsMapTool):

    moved = pyqtSignal(QPoint)
    pressed = pyqtSignal(QPoint)

    def __init__(self, canvas, button):
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas
        self.cursor = QCursor(Qt.CrossCursor)
        self.button = button

    def activate(self):
        QgsMapTool.activate(self)
        self.canvas.setCursor(self.cursor)
        self.button.setCheckable(True)
        self.button.setChecked(True)
        
    def deactivate(self):
        if not self:
            return
        # self.deactivate.emit()
        self.button.setChecked(False)
        self.button.setCheckable(False)
        QgsMapTool.deactivate(self)

    def setCursor(self, cursor):
        self.cursor = QCursor(cursor)

    def canvasMoveEvent(self, event):
        self.moved.emit(QPoint(event.pos().x(), event.pos().y()))

    def canvasPressEvent(self, event):
        self.pressed.emit(QPoint(event.pos().x(), event.pos().y()))
