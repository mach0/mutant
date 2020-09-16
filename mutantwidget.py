"""mutant - MUlti Temporal ANalysis Tool
begin			: 2014/06/16
copyright		: (c) 2014- by Werner Macho
email			: werner.macho@gmail.com

based on valuetool
copyright		: (C) 2008-2010 by G. Picard

__author__ = 'werner.macho@gmail.com'
__date__ = '2014/06/16'
__copyright__ = 'Copyright 2014, Werner Macho'

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.
"""

import fnmatch  # Import filtering for Layer names
import datetime  # for dealing with Multi-temporal data
import time
import csv
import operator

from distutils.version import StrictVersion
from .time_tracker import TimeTracker
from .applyfilter import ApplyFilter
from qgis.PyQt.QtCore import (
    QSettings,
    Qt,
    QSize,
    QEvent
)
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QWidget,
    QMenu,
    QApplication,
    QTableWidgetItem,
    QToolButton,
    QActionGroup,
    QAction,
    QLabel
)
from qgis.PyQt.QtGui import (
    QBrush,
    QPen,
    QIcon
)
from qgis.core import (
    Qgis,
    QgsMapLayer,
    QgsProject,
    QgsRasterDataProvider,
    QgsCsException,
    QgsPoint,
    QgsCoordinateTransform,
    QgsRaster,
    QgsRasterBandStats,
    QgsRectangle
)

from .ui_mutant import Ui_Mutant as Ui_Widget
import logging
# change the level back to logging.WARNING(the default) before releasing
logging.basicConfig(level=logging.DEBUG)


# TODO: Get better debugging
debug = 0

has_qwt = True
try:
    from PyQt5.Qwt import QwtPlot, QwtPlotCurve, QwtScaleDiv, QwtSymbol
except ImportError:
    has_qwt = False

has_mpl = True

try:
    import matplotlib
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import matplotlib.dates as dates
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
    from .cust.mpl_cust import MplSettings
    has_mpl = StrictVersion(matplotlib.__version__) >= StrictVersion('1.0.0')
except ImportError:
    has_mpl = False

has_pyqtgraph = True

try:
    import pyqtgraph as pg
    from .cust.pqg_cust import DateTimeViewBox, DateTimeAxis
    if pg.__version__ == "":  # assuming debian package with no version
        has_pyqtgraph = True
    else:
        has_pyqtgraph = StrictVersion(pg.__version__) >= StrictVersion('0.9.8')

except ImportError:
    has_pyqtgraph = False
    pg = False


class MutantWidget(QWidget, Ui_Widget):

    def __init__(self, iface):
        self.hasqwt = has_qwt
        self.hasmpl = has_mpl
        self.haspqg = has_pyqtgraph
        self.layerMap = dict()
        self.statsChecked = False
        self.ymin = 100
        self.ymax = 200
        self.isActive = False
        self.mt_enabled = False


        # Statistics (>=1.9)
        self.statsSampleSize = 2500000
        self.stats = {}  # stats per layer

        self.layersSelected = []
        self.layerBands = dict()

        self.iface = iface
        self.canvas = self.iface.mapCanvas()

        # self.legend = self.iface.legendInterface()
        self.legend = QgsProject.instance().layerTreeRoot()
        self.logger = logging.getLogger('.'.join((__name__,
                                        self.__class__.__name__)))

        QWidget.__init__(self)
        self.setupUi(self)
        self.tabWidget.setEnabled(False)
        self.plotOnMove.setChecked(QSettings().value('plugins/mutant/mouseClick', False, type=bool))


        self.window_s = 99
        self.power = 3
        self.perc_win = 25
        self.perc = 75

        self.window_size.setEnabled(True)
        self.power_eq.setEnabled(True)
        self.perc_win_val.setEnabled(True)
        self.percentil.setEnabled(True)

        self.window_size.setText(str(self.window_s))
        self.power_eq.setText(str(self.power))
        self.perc_win_val.setText(str(self.perc_win))
        self.percentil.setText(str(self.perc))

        self.leYMin.setText(str(self.ymin))
        self.leYMax.setText(str(self.ymax))

        self.tracker = TimeTracker(self, self.canvas)
        self.filter = ApplyFilter(self, self.canvas)
        if has_mpl:
            self.mpl_cust = MplSettings(self, self.canvas)

        # self.setupUi_plot()
        # don't setup plot until Graph(1) tab is clicked - workaround for bug
        # #7450
        # qgis will still crash in some cases, but at least the tool can be
        # used in Table mode

        self.qwtPlot = None
        self.mplPlot = None
        self.mplLine = None

        self.plotLibSelector.currentIndexChanged .connect(self.change_plot)
        self.tabWidget.currentChanged .connect(self.tabWidgetChanged)
        self.layerSelection.currentIndexChanged .connect(self.update_layers)
        self.bandSelection.currentIndexChanged .connect(self.update_layers)
        self.selectionTable.cellChanged .connect(self.layerSelected)
        self.enableMTAnalysesCheckBox.toggled .connect(self.on_mt_analysis_toggled)
        self.selectionStringLineEdit.textChanged .connect(self.update_layers)
        self.yAutoCheckBox.toggled .connect(self.y_auto_toggle)

        self.toggleMutant.toggled .connect(self.catch_errors)

        self.exportPushButton.clicked .connect(self.export_values)
        # TODO Get Export from graph values
        # self.exportPushButton_2.clicked.connect(self.xxxx)

        self.registry = QgsProject.instance()
        self.registry.layersAdded .connect(self.catch_errors)
        self.registry.layersRemoved .connect(self.catch_errors)
        self.setupUi_plot()

    def catch_errors(self):
        if self.toggleMutant.isChecked():
            layers = self.activeRasterLayers()
            if len(layers) == 0:
                if self.canvas.layerCount() > 0:
                    text = self.tr("Mutant: No valid layers to display - "
                                   "add Rasterlayers")
                    self.pop_messagebar(text)
                    self.changeActive(False)
                else:
                    text = self.tr("Mutant: No valid layers to display")
                    self.pop_messagebar(text)
                    self.changeActive(False)
                self.values = []
                return
            else:
                return
        else:
            return

    def y_auto_toggle(self, state):
        # User has toggled automatic (default) y min/max values
        if state == 1:
            self.leYMin.setEnabled(False)
            self.leYMax.setEnabled(False)
            self.leYMin.setText(str(self.ymin))
            self.leYMax.setText(str(self.ymax))
        else:
            self.leYMin.setEnabled(True)
            self.leYMax.setEnabled(True)

    def pop_messagebar(self, text, d_time=5):
        if d_time == 0:
            self.iface.messageBar().pushWidget(self.iface.messageBar().createMessage(text), Qgis.Warning)
        else:
            self.iface.messageBar().pushWidget(self.iface.messageBar().createMessage(text), Qgis.Warning, d_time)

    def setupUi_plot(self):
        # plot
        self.plotLibSelector.setVisible(False)
        self.enableStatistics.setVisible(False)
        # stats by default because estimated are fast
        self.enableStatistics.setChecked(True)

        plot_count = 0
        self.mplLine = None  # make sure to invalidate when layers change

        if self.hasqwt:  # Page 2 - qwt
            self.plotLibSelector.addItem('Qwt')
            plot_count += 1
            # Setup Qwt Plot Area in Widget
            self.qwtPlot = QwtPlot(self.stackedWidget)
            self.qwtPlot.setAutoFillBackground(False)
            self.qwtPlot.setObjectName("qwtPlot")
            #self.curve = QwtPlotCurve()
            #self.curve.setSymbol(
            #    QwtSymbol(QwtSymbol.Ellipse,
            #              QBrush(Qt.white),
            #              QPen(Qt.red, 2),
            #              QSize(9, 9)))
            #self.curve.attach(self.qwtPlot)

            # Size Policy ???
            sizePolicy = QSizePolicy(QSizePolicy.Expanding,
                                     QSizePolicy.Expanding)
            sizePolicy.setHorizontalStretch(0)
            sizePolicy.setVerticalStretch(0)
            sizePolicy.setHeightForWidth(self.qwtPlot.sizePolicy().hasHeightForWidth())
            self.qwtPlot.setSizePolicy(sizePolicy)
            # Size Policy ???

            self.qwtPlot.updateGeometry()
            self.stackedWidget.addWidget(self.qwtPlot)
            self.qwt_widgetnumber = self.stackedWidget.indexOf(self.qwtPlot)

        if self.hasmpl:  # Page 3 -  setup matplotlib
            self.plotLibSelector.addItem('matplotlib')
            # If matplotlib is the only one
            self.toggleInterpolation.setEnabled(True)
            self.toggleInterpolation.setVisible(True)
            plot_count += 1
            self.mplBackground = None
            # http://www.scipy.org/Cookbook/Matplotlib/Animations
            self.mplFig = plt.Figure(facecolor='w',
                                     edgecolor='g',
                                     linewidth=0.0)

            self.mpl_subplot = self.mplFig.add_subplot(111)
            self.pltCanvas = FigureCanvasQTAgg(self.mplFig)
            self.pltCanvas.setParent(self.stackedWidget)
            self.pltCanvas.setAutoFillBackground(False)
            self.pltCanvas.setObjectName("mplPlot")
            self.mplPlot = self.pltCanvas
            self.mplPlot.updateGeometry()
            self.stackedWidget.addWidget(self.mplPlot)
            self.mpl_widgetnumber = self.stackedWidget.indexOf(self.mplPlot)

        if self.haspqg:  # Page 3 - setup PyQtGraph
            self.plotLibSelector.addItem('PyQtGraph')
            plot_count += 1
            # Setup PyQtGraph stuff
            pg.setConfigOption('background', 'w')
            pg.setConfigOption('foreground', 'k')
            self.pqg_axis = DateTimeAxis(orientation='bottom')
            self.pqg_plot_widget = pg.PlotWidget(parent=self.stackedWidget,
                                                 axisItems={'bottom':
                                                 self.pqg_axis})
            self.pqg_plot_item = self.pqg_plot_widget.getPlotItem()
            self.pqg_plot_widget.updateGeometry()
            self.stackedWidget.addWidget(self.pqg_plot_widget)
            self.pqg_widgetnumber = self.stackedWidget.indexOf(
                self.pqg_plot_widget)
            # on zoom change do:
            self.pqg_plot_item.sigXRangeChanged .connect(self.refresh_ticks)

        if plot_count > 1:
            self.plotLibSelector.setEnabled(True)
            self.plotLibSelector.setVisible(True)
            self.plotLibSelector.setCurrentIndex(0)
            if self.hasqwt:
                self.plotLibSelector.setCurrentIndex(self.qwt_widgetnumber)
            elif self.hasmpl:
                self.plotLibSelector.setCurrentIndex(self.mpl_widgetnumber)
            else:
                self.plotLibSelector.setCurrentIndex(self.pqg_widgetnumber)
            self.change_plot()
        elif plot_count == 1:
            self.plotLibSelector.setCurrentIndex(0)
            self.change_plot()
        else:  # can only be 0 if nothing else matched
            message_text = "Mutant cannot find any graphiclibrary for " \
                           "creating plots. Please install either Qwt >= 5.0 " \
                           ",matplotlib >= 1.0 or PyQtGraph >= 0.9.8!"
            self.plot_message = QLabel(message_text)
            self.plot_message.setWordWrap(True)
            self.stackedWidget.addWidget(self.plot_message)
            self.pop_messagebar(message_text)

    def change_plot(self):
        if self.stackedWidget.count() > 1:
            if self.plotLibSelector.currentText() == 'Qwt':
                self.stackedWidget.setCurrentIndex(self.qwt_widgetnumber)
                self.toggleInterpolation.setDisabled(True)
                self.toggleInterpolation.setVisible(False)
            elif self.plotLibSelector.currentText() == 'matplotlib':
                self.stackedWidget.setCurrentIndex(self.mpl_widgetnumber)
                self.toggleInterpolation.setEnabled(True)
                self.toggleInterpolation.setVisible(True)
                self.mpl_subplot.clear()
            elif self.plotLibSelector.currentText() == 'PyQtGraph':
                self.stackedWidget.setCurrentIndex(self.pqg_widgetnumber)
                self.toggleInterpolation.setDisabled(True)
                self.toggleInterpolation.setVisible(False)
                self.pqg_plot_widget.clear()
        elif self.stackedWidget.count() == 1:
            self.stackedWidget.setCurrentIndex(0)
        else:
            self.stackedWidget.setCurrentIndex(-1)

    def keyPressEvent(self, e):
        if (e.modifiers() == Qt.ControlModifier or e.modifiers() == Qt.MetaModifier) and e.key() == Qt.Key_C:
            items = ''
            for rec in range(self.valueTable.rowCount()):
                items += '"' + self.valueTable.item(rec, 0).text() + '",' + self.valueTable.item(rec, 1).text() + "\n"
            if not items == '':
                clipboard = QApplication.clipboard()
                clipboard.setText(items)
        else:
            QWidget.keyPressEvent(self, e)

    def changeActive(self, active, gui=True):
        if self.isActive == active:
            return
        self.isActive = active

        if active:
            self.toggleMutant.setCheckState(Qt.Checked)
            self.canvas.layersChanged .connect(self.invalidatePlot)
            if not self.plotOnMove.isChecked():
                self.canvas.xyCoordinates .connect(self.printValue)
        else:
            self.toggleMutant.setCheckState(Qt.Unchecked)
            self.canvas.layersChanged .disconnect(self.invalidatePlot)
            try:
                self.canvas.xyCoordinates.disconnect(self.printValue)
            except TypeError:
                pass  # it was not connected so there is nothing to do here

        if gui:
            self.tabWidget.setEnabled(active)
            if active:
                self.labelStatus.setText(self.tr("Mutant is enabled!"))
                # FIXME: Only on Options Tab?
                if self.tabWidget.currentIndex() == 2:
                    self.update_layers()
            else:
                self.labelStatus.setText(self.tr(""))
                # use this to clear plot when deactivated
                # self.values=[]
                # self.showValues()

    def activeRasterLayers(self, index=None):
        layers = []
        allLayers = []

        if not index:
            index = self.layerSelection.currentIndex()
        if index == 0:  # visible layers
            allLayers = self.canvas.layers()
        elif index == 1 or index == 3:  # All layers | by selection string
            allLayers = [ltl.layer() for ltl in self.legend.findLayers()]
        elif index == 2:  # Manual selection
            for layer in [ltl.layer() for ltl in self.legend.findLayers()]:
                if layer.id() in self.layersSelected:
                    allLayers.append(layer)

        for layer in allLayers:

            if index == 3:  # by selection string
                # Check if the layer name matches our filter and skip it if it
                # doesn't
                if not self.name_matches_filter(layer.name()):
                    continue

            if layer is not None and layer.isValid() and \
                    layer.type() == QgsMapLayer.RasterLayer and \
                    layer.dataProvider() and \
                    (layer.dataProvider().capabilities() & QgsRasterDataProvider.IdentifyValue):
                layers.append(layer)

        return layers

    def activeBandsForRaster(self, layer):
        activeBands = []

        if self.bandSelection.currentIndex() == 1 and layer.renderer():
            activeBands = layer.renderer().usesBands()
        elif self.bandSelection.currentIndex() == 2:
            if layer.bandCount() == 1:
                activeBands = [1]
            else:
                activeBands = self.layerBands[layer.id()] if (layer.id() in self.layerBands) else []
        else:
            activeBands = list(range(1, layer.bandCount()+1))

        return activeBands

    def printValue(self, position):

        if debug > 0:
            print(position)

        if not position:
            return
        if self.tabWidget.currentIndex() == 2:
            return

        if debug > 0:
            print("%d active rasters, %d canvas layers" % (len(
                self.activeRasterLayers()), self.canvas.layerCount()))

        layers = self.activeRasterLayers()

        self.labelStatus.setText(self.tr('Coordinate:') + ' (%f, %f)' % (
            position.x(), position.y()))

        need_extremum = (self.tabWidget.currentIndex() == 1)  # if plot is shown
        # count the number of required rows and remember the raster layers
        nrow = 0
        rasterlayers = []
        layersWOStatistics = []

        for layer in layers:
            nrow += layer.bandCount()
            rasterlayers.append(layer)

            # check statistics for each band
            if need_extremum:
                for i in range(1, layer.bandCount()+1):
                    has_stats = self.get_statistics(layer, i) is not None
                    if not layer.id() in self.layerMap and not has_stats \
                            and not layer in layersWOStatistics:
                        layersWOStatistics.append(layer)

        if layersWOStatistics and not self.statsChecked:
            self.calculateStatistics(layersWOStatistics)

        irow = 0
        self.values = []
        self.ymin = 1e38
        self.ymax = -1e38

        mapCanvasSrs = self.iface.mapCanvas().mapSettings().destinationCrs()

        # TODO - calculate the min/max values only once,
        # instead of every time!!!
        # And keep them in a dict() with key=layer.id()

        counter = 0
        for layer in rasterlayers:
            layer_name = str(layer.name())
            layer_srs = layer.crs()

            pos = position

            # if given no position, get dummy values
            if position is None:
                pos = QgsPoint(0, 0)
            # transform points if needed
            elif not mapCanvasSrs == layer_srs:
                srsTransform = QgsCoordinateTransform(mapCanvasSrs, layer_srs)
                try:
                    pos = srsTransform.transform(position)
                except QgsCsException as err:
                    continue

            if True:
                if not layer.dataProvider():
                    continue
                ident = None

                if position is not None:
                    canvas = self.iface.mapCanvas()

                    # first test if point is within map layer extent
                    # maintain same behaviour as in 1.8 and print out of extent
                    if not layer.dataProvider().extent().contains(pos):
                        ident = dict()
                        for iband in range(1, layer.bandCount()+1):
                            ident[iband] = str(self.tr('out of extent'))
                    # we can only use context if layer is not projected
                    elif layer.dataProvider().crs() != \
                                    canvas.mapSettings().destinationCrs():
                        ident = layer.dataProvider().identify(pos,
                                QgsRaster.IdentifyFormatValue).results()
                    else:
                        extent = canvas.extent()
                        width = round(extent.width() /
                                      canvas.mapUnitsPerPixel())
                        height = round(extent.height() /
                                       canvas.mapUnitsPerPixel())
                        extent = canvas.mapSettings().mapToLayerCoordinates(
                            layer, extent)
                        ident = layer.dataProvider().identify(pos,
                                                              QgsRaster.IdentifyFormatValue,
                                                              canvas.extent(),
                                                              width,
                                                              height).results()
                    if not len(ident) > 0:
                        continue

                # if given no position, set values to 0
                if position is None and ident is not None and iter(ident.keys()) is not None:
                    for key in ident.keys():
                        ident[key] = layer.dataProvider().noDataValue(key)

                # bands displayed depends on cbxBands (all / active / selected)
                activeBands = self.activeBandsForRaster(layer)

                for iband in activeBands:  # loop over the active bands
                    layer_name_with_band = layer_name
                    if ident is not None and len(ident) > 1:
                        layer_name_with_band += ' ' + layer.bandName(iband)

                    if not ident or iband not in ident:
                        bandvalue = "?"
                    else:
                        bandvalue = ident[iband]
                        if bandvalue is None:
                            bandvalue = "no data"

                    # different x-Axis depending on if we want to use time or
                    # not
                    if self.mt_enabled:
                        layer_time = self.tracker.get_time_for_layer(layer)

                        if layer_time is None:
                            continue
                        else:
                            # pyqtgraph enabled convert date to epoch
                            graphlib = self.plotLibSelector.currentText()

                            if graphlib == 'PyQtGraph':
                                layer_time = time.mktime(layer_time.timetuple())
                                # overwrite
                            tup = (layer_name_with_band,
                                   layer_time,
                                   str(bandvalue))
                    else:
                        tup = (layer_name_with_band,
                               counter+1,
                               str(bandvalue))

                    self.values.append(tup)

                    if need_extremum:
                        # estimated statistics
                        stats = self.get_statistics(layer, iband)
                        if stats:
                            self.ymin = min(self.ymin, stats.minimumValue)
                            self.ymax = max(self.ymax, stats.maximumValue)
                    counter += 1

        # Update the ymin, ymax line edits if required
        if self.yAutoCheckBox.isChecked():
            self.leYMin.setText(str(self.ymin))
            self.leYMax.setText(str(self.ymax))

        self.values.sort(key=operator.itemgetter(1))

        if len(self.values) == 0:
            self.labelStatus.setText(self.tr("No valid bands to display"))

        self.showValues(position)

    def showValues(self, position):
        if self.tabWidget.currentIndex() == 1:
            if len(self.values) == 0:
                # FIXME don't plot if there is no data to plot...
                return
            else:
                self.plot()
        else:
            self.printInTable(position)

    def export_values(self):
        #path = QFileDialog.getSaveFileName(self, 'Save File', '', 'CSV(*.csv)')
        path = r'B:/VEGA/monitoramento_bayer/api_monitoramento/teste/TESTE.csv'
        if path != "":
            with open(path, 'wb') as stream:
                writer = csv.writer(stream)
                for row in range(self.valueTable.rowCount()):
                    rowdata = []
                    for column in range(self.valueTable.columnCount()):
                        item = self.valueTable.item(row, column)
                        if item is not None:
                            rowdata.append(
                                str(item.text()).encode('utf8'))
                        else:
                            rowdata.append('')
                    writer.writerow(rowdata)

    def calculateStatistics(self, layersWOStatistics):

        self.invalidatePlot(False)
        self.statsChecked = True

        layernames = []
        for layer in layersWOStatistics:
            if not layer.id() in self.layerMap:
                layernames.append(layer.name())

        if len(layernames) != 0:
            if not self.enableStatistics.isChecked():
                for layer in layersWOStatistics:
                    self.layerMap[layer.id()] = True
                return
        else:
            print('ERROR, no layers to get stats for')

        save_state = self.isActive
        self.changeActive(False, False)  # deactivate

        # calculate statistics
        for layer in layersWOStatistics:
            if not layer.id() in self.layerMap:
                self.layerMap[layer.id()] = True
                for i in range(1, layer.bandCount()+1):
                    self.get_statistics(layer, i, True)

        if save_state:
            self.changeActive(True, False)  # activate if necessary

    # get cached statistics for layer and band or None if not calculated
    def get_statistics(self, layer, bandNo, force=False):
        if layer in self.stats:
            if bandNo in self.stats[layer]:
                return self.stats[layer][bandNo]
        else:
            self.stats[layer] = {}

        if force or \
                layer.dataProvider().hasStatistics(bandNo,
                                                   QgsRasterBandStats.Min | QgsRasterBandStats.Min,
                                                   QgsRectangle(),
                                                   self.statsSampleSize):
            self.stats[layer][bandNo] = \
                layer.dataProvider().bandStatistics(bandNo,
                                                    QgsRasterBandStats.Min | QgsRasterBandStats.Min,
                                                    QgsRectangle(),
                                                    self.statsSampleSize)
            return self.stats[layer][bandNo]
        return None

    def printInTable(self, position):
        self.valueTable.clearContents()
        # set table widget row count
        self.valueTable.setRowCount(len(self.values))
        posX = position.x()
        posY = position.y()
        irow = 0
        for layername, xval, value in self.values:

            if self.valueTable.item(irow, 0) is None:
                # create the item
                self.valueTable.setItem(irow, 0, QTableWidgetItem())
                self.valueTable.setItem(irow, 1, QTableWidgetItem())
                self.valueTable.setItem(irow, 2, QTableWidgetItem())
                self.valueTable.setItem(irow, 3, QTableWidgetItem())
                self.valueTable.setItem(irow, 4, QTableWidgetItem())

            self.valueTable.item(irow, 0).setText(layername)
            self.valueTable.item(irow, 3).setText(str(posX))
            self.valueTable.item(irow, 4).setText(str(posY))

            if self.mt_enabled:
                graphlib = self.plotLibSelector.currentText()
                if graphlib == 'PyQtGraph':
                    date = datetime.datetime.fromtimestamp(xval)
                    self.valueTable.item(irow, 2).setText(str(date))
                else:
                    self.valueTable.item(irow, 2).setText(str(xval))
            # else:
                # self.valueTable.item(irow, 2).setText('')

            if value == 'no data' or value == 'out of extent':
                self.valueTable.item(irow, 1).setText(value)
            else:
                value = float(value)
                if self.cbxDigits.isChecked():
                    try:
                        x = str(self.spinDigits.value())
                        y = "{:."+x+"f}"
                        value = y.format(value)
                    except ValueError:
                        pass
                self.valueTable.item(irow, 1).setData(Qt.EditRole, value)
            irow += 1

    def refresh_ticks(self):
        # At this point the X extent has been changed (e.g. zoom) and we need
        #  to redraw ticks and associated labels
        major_tick_times = []
        # define label width as minimum label distance readable
        label_width = 40

        # First determine what visible x range we are looking at
        view_min_x = self.pqg_plot_item.getViewBox().viewRange()[0][0]
        view_max_x = self.pqg_plot_item.getViewBox().viewRange()[0][1]
        min_date_axis = datetime.datetime.fromtimestamp(view_min_x)

        view_range = view_max_x - view_min_x

        # Determine the current width of the plot in px
        rect_bound = self.pqg_plot_item.viewGeometry()
        width = rect_bound.width()

        major_label_count = (width - label_width) // label_width

        major_label_spacing = view_range // (major_label_count * 3600.0 * 24
                                             * 365.25)  # In major tick units

        min_tick_to_label_int = int(datetime.datetime.strftime(min_date_axis, '%Y')) + 1

        major_label_spacing_delta = view_range / major_label_count

        min_tick_to_label_stamp = (datetime.datetime(min_tick_to_label_int, 1, 1) -
                                   datetime.datetime(1970, 1, 1)).total_seconds()

        major_tick_times.append((int(min_tick_to_label_stamp),
                                 str(datetime.datetime.fromtimestamp(
                                     min_tick_to_label_stamp).strftime('%Y'))))

        next_tick_to_label_int = int((datetime.datetime(
                                      min_tick_to_label_int, 1,
                                      1) - datetime.datetime(
                                      1970, 1, 1)).total_seconds())

        next_tick_to_label_stamp = min_tick_to_label_stamp

        while True:
            next_tick_to_label_int += int(major_label_spacing_delta)
            next_tick_to_label_stamp += major_label_spacing_delta

            if next_tick_to_label_int > int(view_max_x):
                break
            major_tick_times.append((next_tick_to_label_int,
                                     str(datetime.datetime.fromtimestamp(
                                         next_tick_to_label_stamp).strftime(
                                         '%Y'))))
        # An experiment
        # ticks = [
        #      [(631152000.34, '1990'), (788918400, '1995')],
        #      [(662688000, '1991'),(694224000.46, '1992'),
        #       (725846400, '1993'), (757382400, '1994')]
        # ]
        self.pqg_axis.setTicks([major_tick_times])

    def plot(self):
        data_values = []
        x_values = []
        do_filter = self.toggleFilter.isChecked()
        do_interpolation = self.toggleInterpolation.isChecked()

        if self.hasqwt or self.hasmpl or self.haspqg:
            for layername, xval, value in self.values:
                x_values.append(xval)
                try:
                    data_values.append(float(value))
                except ValueError:
                    data_values.append(None)
                    # instead to not be plotted, be aware of min()
                    # calculation in plotting range = affects graphs (check
                    # there?
            if not data_values:
                data_values = [0]
        self.window_s = int(self.window_size.text())
        self.power = int(self.power_eq.text())
        self.perc_win = int(self.perc_win_val.text())
        self.perc = int(self.percentil.text())
        
        if self.yAutoCheckBox.isChecked():
            ymin = self.ymin
            ymax = self.ymax
        else:
            # Beware the user may not have entered a number
            try:
                ymin = float(self.leYMin.text())
                ymax = float(self.leYMax.text())
            except ValueError:
                message = 'Valuetool: Please enter Numbers!'
                self.pop_messagebar(message)
                return

        # Qwt Plot
        if self.hasqwt and (self.plotLibSelector.currentText() == 'Qwt'):
            self.qwtPlot.setAxisMaxMinor(QwtPlot.xBottom, 0)
            # self.qwtPlot.setAxisMaxMajor(QwtPlot.xBottom,0)
            self.qwtPlot.setAxisScale(QwtPlot.xBottom, 1, len(self.values))
            # self.qwtPlot.setAxisScale(QwtPlot.yLeft, self.ymin, self.ymax)
            self.qwtPlot.setAxisScale(QwtPlot.yLeft, ymin, ymax)
            try:
                qwtx, qwtydata = list(zip(*[x for x in zip(x_values, data_values) if x[1] is not None]))
            except ValueError:
                return
            #self.curve.setSamples(list(range(1, len(qwtydata)+1)), qwtydata)
            self.qwtPlot.replot()
            self.qwtPlot.setVisible(len(qwtydata) > 0)

        # matplotlib Plot
        elif self.hasmpl and (self.plotLibSelector.currentText() ==
                              'matplotlib'):
            # don't clear to draw another row of data
            self.mpl_subplot.clear()
            self.mpl_cust.mpl_setup()
            # If Multi-temporal Analysis enabled set xAxis away from Standard
            # 1 to values to dates.
            # Plot code from here
            xv = np.asarray(x_values)
            dv = np.asarray(data_values)
            dvd = dv.astype(np.double)
            datav_mask = np.isfinite(dvd)

            if do_interpolation:
                xaxis = xv[datav_mask]
                yaxis = dvd[datav_mask]
            else:
                xaxis = x_values
                yaxis = data_values

            self.mpl_subplot.plot_date(xaxis,
                                       yaxis,
                                       #linestyle='-',
                                       xdate=self.mt_enabled,
                                       ydate=False,
                                       marker='o',
                                       markersize=4,
                                       color='k',
                                       markerfacecolor='b',
                                       markeredgecolor='b')
            if self.mt_enabled:
                plt.xticks(rotation='vertical')
                self.mpl_cust.mpl_date_settings(x_values, ymin, ymax)
            else:
                self.mpl_cust.mpl_value_settings(x_values, ymin, ymax)

            if do_filter:
                derived_x, derived_y = self.filter.smooth(xaxis, yaxis,window=self.window_s,polyorder=self.power,perc=self.perc,p_window=self.perc_win)
                self.mpl_subplot.plot_date(derived_x,
                                           derived_y,
                                           linestyle='-',
                                           xdate=self.mt_enabled,
                                           ydate=False,
                                           marker='x',
                                           markersize=2,
                                           color='r',
                                           markerfacecolor='r',
                                           markeredgecolor='r')
            self.mplFig.canvas.draw()

        # PyQtGraph Plot
        elif self.haspqg and (self.plotLibSelector.currentText() == 'PyQtGraph'):
            # clear on plot - don't clear if additional data should be added
            self.pqg_plot_widget.clear()  # clean canvas on call
            # self.pqg_plot_item.clear()  # clear item
            # self.pqg_plot_widget.scene().removeItem(legend)
            self.pqg_plot_item.setYRange(ymin, ymax)
            style_normal = Qt.SolidLine
            # Qt.DashLine, Qt.DotLine, Qt.DashDotLine, Qt.DashDotDotLine, Qt.CustomDashLine
            style_filter = Qt.SolidLine
            # filter None values out of input data
            try:
                pgxaxis, pgyaxis = list(zip(*[x for x in zip(x_values, data_values) if x[1] is not None]))
            except ValueError:
                return
            self.pqg_plot_widget.plot(pgxaxis,
                                      pgyaxis,
                                      name='data',
                                      symbol='o',
                                      pen=pg.mkPen(color='k',
                                                   width=1,
                                                   style=style_normal))
            if do_filter:
                derived_x, derived_y = self.filter.smooth(pgxaxis, pgyaxis,window=self.window_s,polyorder=self.power,perc=self.perc,p_window=self.perc_win)
                self.pqg_plot_widget.plot(derived_x,
                                          derived_y,
                                          name='filter',
                                          symbol='x',
                                          pen=pg.mkPen(color='r',
                                                       width=1,
                                                       style=style_filter))

    def invalidatePlot(self, replot=True):
        if self.tabWidget.currentIndex() == 2:
            self.update_layers()
        if not self.isActive:
            return
        self.statsChecked = False
        if self.mplLine is not None:
            del self.mplLine
            self.mplLine = None
        # update empty plot
        if replot and self.tabWidget.currentIndex() == 1:
            # self.values=[]
            self.printValue(None)

    def resizeEvent(self, event):
        self.invalidatePlot()

    def tabWidgetChanged(self):
        if self.tabWidget.currentIndex() == 2:
            self.update_layers()

    def on_mt_analysis_toggled(self, new_state):
        if new_state == 1:
            self.mt_enabled = True
            if self.haspqg:
                self.pqg_axis.set_time_enabled(True)
            if self.hasqwt and self.plotLibSelector.currentText() == 'Qwt':
                message = 'Mutant: There is currently no support using Date ' \
                          'values while using the Qwt plotlibrary'
                self.pop_messagebar(message, 0)
            self.tracker.enable_selection()
            self.priorityLabel.setEnabled(True)
            self.extractionPriorityListWidget.setEnabled(True)
            self.patternLabel.setEnabled(True)
            self.patternLineEdit.setEnabled(True)
            self.writeMetaDataCheckBox.setEnabled(True)
            self.labelStatus.setText(self.tr("Multi-temporal analysis "
                                             "enabled!"))
            self.cutFirst.setEnabled(True)
            self.dateLength.setEnabled(True)
            self.sampleLineEdit.setEnabled(True)
            self.sampleLabel.setEnabled(True)
            self.tracker.refresh_tracker()  # Only call when mt_enabled
        else:
            self.mt_enabled = False
            if self.haspqg:
                self.pqg_axis.set_time_enabled(False)
            self.priorityLabel.setEnabled(False)
            self.extractionPriorityListWidget.setEnabled(False)
            self.patternLabel.setEnabled(False)
            self.patternLineEdit.setEnabled(False)
            self.writeMetaDataCheckBox.setEnabled(False)
            self.labelStatus.setText(self.tr(""))
            self.cutFirst.setEnabled(False)
            self.dateLength.setEnabled(False)
            self.sampleLineEdit.setEnabled(False)
            self.sampleLabel.setEnabled(False)
            self.tracker.disable_selection()

    def name_matches_filter(self, name):
        selection_string = self.selectionStringLineEdit.text()
        return fnmatch.fnmatchcase(name, selection_string)

    # update active layers in table
    def update_layers(self):
        if self.tabWidget.currentIndex() != 2:
            return

        if self.layerSelection.currentIndex() == 3:  # by selection string
            self.selectionStringLineEdit.setEnabled(True)
        else:
            self.selectionStringLineEdit.setEnabled(False)

        if self.layerSelection.currentIndex() == 0:  # visible layers
            layers = self.activeRasterLayers(0)
        elif self.layerSelection.currentIndex() == 3:  # by selection string
            layers = self.activeRasterLayers(3)
        else:
            layers = self.activeRasterLayers(1)  # All layers

        self.selectionTable.blockSignals(True)
        self.selectionTable.clearContents()
        self.selectionTable.setRowCount(len(layers))
        self.selectionTable.horizontalHeader().resizeSection(0, 20)
        self.selectionTable.horizontalHeader().resizeSection(2, 20)

        j = 0
        for layer in layers:
            item = QTableWidgetItem()
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if self.layerSelection.currentIndex() != 2:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setCheckState(Qt.Checked)
            else:
                # manual selection
                if layer.id() in self.layersSelected:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
            self.selectionTable.setItem(j, 0, item)
            item = QTableWidgetItem(layer.name())
            item.setData(Qt.UserRole, layer.id())
            self.selectionTable.setItem(j, 1, item)
            activeBands = self.activeBandsForRaster(layer)
            button = QToolButton()
            button.setIcon(QIcon(':/plugins/mutant/img/bands.jpg'))
            # button.setIconSize(QtCore.QSize(400, 400))
            button.setPopupMode(QToolButton.InstantPopup)
            group = QActionGroup(button)
            group.setExclusive(False)
            group.triggered .connect(self.bandSelected)
            if self.bandSelection.currentIndex() == 2 and layer.bandCount() > 1:
                menu = QMenu()
                menu.installEventFilter(self)

                for iband in range(1, layer.bandCount()+1):
                    action = QAction(str(layer.bandName(iband)), group)
                    action.setData([layer.id(), iband, j, False])
                    action.setCheckable(True)
                    action.setChecked(iband in activeBands)
                    menu.addAction(action)
                if layer.bandCount() > 1:
                    action = QAction(str(self.tr("All")), group)
                    action.setData([layer.id(), -1, j, True])
                    action.setCheckable(False)
                    menu.addAction(action)
                    action = QAction(str(self.tr("None")), group)
                    action.setData([layer.id(), -1, j, False])
                    action.setCheckable(False)
                    menu.addAction(action)

                button.setMenu(menu)
            else:
                button.setEnabled(False)
            self.selectionTable.setCellWidget(j, 2, button)
            item = QTableWidgetItem(str(activeBands))
            item.setToolTip(str(activeBands))
            self.selectionTable.setItem(j, 3, item)
            j += 1

        self.selectionTable.blockSignals(False)

    # slot for when active layer selection has changed
    def layerSelected(self, row, column):
        if column != 0:
            return

        self.layersSelected = []
        for i in range(0, self.selectionTable.rowCount()):
            item = self.selectionTable.item(i, 0)
            layer_id = self.selectionTable.item(i, 1).data(Qt.UserRole)
            if item and item.checkState() == Qt.Checked:
                self.layersSelected.append(layer_id)
            elif layer_id in self.layersSelected:
                self.layersSelected.remove(layer_id)

    # slot for when active band selection has changed
    def bandSelected(self, action):
        layer_id = action.data()[0]
        layerBand = action.data()[1]
        j = action.data()[2]
        toggleAll = action.data()[3]
        activeBands = self.layerBands[layer_id] if (layer_id in self.layerBands) else []

        # special actions All/None
        if layerBand == -1:
            for layer in [ltl.layer() for ltl in self.legend.findLayers()]:
                if layer.id() == layer_id:
                    if toggleAll:
                        activeBands = list(range(1, layer.bandCount()+1))
                    else:
                        activeBands = []
                    # toggle all band# actions
                    group = action.parent()
                    if group and not isinstance(group, QActionGroup):
                        group = None
                    if group:
                        group.blockSignals(True)
                        for a in group.actions():
                            if a.isCheckable():
                                a.setChecked(toggleAll)
                        group.blockSignals(False)

        # any Band# action
        else:
            if action.isChecked():
                activeBands.append(layerBand)
            else:
                if layerBand in activeBands:
                    activeBands.remove(layerBand)
            activeBands.sort()

        self.layerBands[layer_id] = activeBands

        # update UI
        item = QTableWidgetItem(str(activeBands))
        item.setToolTip(str(activeBands))
        self.selectionTable.setItem(j, 3, item)

    # event filter for band selection menu, do not close after toggling each
    # band
    def eventFilter(self, obj, event):
        if event.type() in [QEvent.MouseButtonRelease]:
            if isinstance(obj, QMenu):
                if obj.activeAction():
                    if not obj.activeAction().menu():
                        # if the selected action does not have a submenu eat the event, but trigger the function
                        obj.activeAction().trigger()
                        return True
        return super(MutantWidget, self).eventFilter(obj, event)

    def shouldPrintValues(self):
        return self.isVisible() and not self.visibleRegion().isEmpty() and \
               self.isActive and self.tabWidget.currentIndex() != 2

    def toolMoved(self, position):
        if self.shouldPrintValues() and not self.plotOnMove.isChecked():
            self.printValue(self.canvas.getCoordinateTransform().toMapCoordinates(position))

    def toolPressed(self, position):
        if self.shouldPrintValues() and self.plotOnMove.isChecked():
            self.printValue(self.canvas.getCoordinateTransform().toMapCoordinates(position))
