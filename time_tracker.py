"""mutant - MUlti Temporal ANalysis Tool
begin			: 2014/06/15
copyright		: (c) 2014- by Werner Macho
email			: werner.macho@gmail.com

based on valuetool
copyright		: (C) 2008-2010 by G. Picard

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.
"""

from builtins import object
from qgis.PyQt.QtCore import QObject, Qt, QFileInfo
from qgis.PyQt.QtGui import QPalette
from qgis.core import QgsProject, QgsMapLayer

import datetime

# work with gdal xml
try:
    from osgeo import gdal
    from osgeo.gdalconst import *
except ImportError:
    import gdal
    from gdalconst import *


class TimeTracker(object):

    def __init__(self, parent, canvas):
        self.layer_times = dict()
        self.parent = parent
        self.canvas = canvas

        self.widget = self.parent.extractionPriorityListWidget
        self.cut_first = self.parent.cutFirst
        self.select_date = self.parent.dateLength
        self.pattern_edit = self.parent.patternLineEdit
        self.sample_edit = self.parent.sampleLineEdit
        self.write_meta = self.parent.writeMetaPushButton

        # This data structure looks like:
        # {
        #   'layer_id' : datetime.datetime(2014, 2, 23),
        # }

        self.registry = QgsProject.instance()

    def enable_selection(self):
        self.registry.layersAdded.connect(self.refresh_tracker)
        self.registry.layersRemoved.connect(self.refresh_tracker)

        self.widget.itemChanged.connect(self.refresh_tracker)
        self.widget.itemChanged.connect(self.validate_date_string)

        self.widget.model().rowsMoved.connect(self.refresh_tracker)
        self.widget.model().rowsMoved.connect(self.validate_date_string)

        self.cut_first.valueChanged.connect(self.cut_first_spinbox_changed)
        self.cut_first.valueChanged.connect(self.refresh_tracker)

        self.select_date.valueChanged.connect(self.date_length_spinbox_changed)
        self.select_date.valueChanged.connect(self.refresh_tracker)

        self.pattern_edit.textChanged.connect(self.refresh_tracker)
        self.pattern_edit.textChanged.connect(self.validate_date_string)

        self.sample_edit.textChanged.connect(self.refresh_tracker)
        self.sample_edit.textChanged.connect(self.validate_date_string)

        #  self.write_meta.clicked.connect(self.write_XML) # FIXME Find function
        #  to only write XML

        self.initiate_values()

    def disable_selection(self):
        self.registry.layersAdded.disconnect(self.refresh_tracker)
        self.registry.layersRemoved.disconnect(self.refresh_tracker)

        self.widget.itemChanged.disconnect(self.refresh_tracker)
        self.widget.itemChanged.disconnect(self.validate_date_string)

        self.widget.model().rowsMoved.disconnect(self.refresh_tracker)
        self.widget.model().rowsMoved.disconnect(self.validate_date_string)

        self.cut_first.valueChanged.disconnect(self.cut_first_spinbox_changed)
        self.cut_first.valueChanged.disconnect(self.refresh_tracker)

        self.select_date.valueChanged.disconnect(
            self.date_length_spinbox_changed)
        self.select_date.valueChanged.disconnect(self.refresh_tracker)

        self.pattern_edit.textChanged.disconnect(self.refresh_tracker)
        self.pattern_edit.textChanged.disconnect(self.validate_date_string)

        self.sample_edit.textChanged.disconnect(self.refresh_tracker)
        self.sample_edit.textChanged.disconnect(self.validate_date_string)

    def refresh_tracker(self):
        # initialise (or re-initialise) self.layer_times
        # Empty the dictionary
        self.layer_times = {}
        # Loop through all raster layers in qgis and call
        # track_layer, populating the dictionary

        if QgsMapLayerRegistry is None:
            return

        reg = QgsMapLayerRegistry.instance()
        for layer_id, layer in reg.mapLayers().items():
            try:
                if layer.type() == QgsMapLayer.RasterLayer:
                    self.track_layer(layer)
            except AttributeError:
                pass

    def track_layer(self, layer):
        """given a layer, determine its date and write the entry to the data
        structure."""
        layer_id = layer.id()
        # extract time from layers if there is some
        self.layer_times[layer_id] = self.extract_time_from_layer(layer)

    def get_time_for_layer(self, layer):
        """Retrieves a time from the internal store"""
        layer_id = layer.id()
        try:
            layer_time = self.layer_times[layer_id]
        except KeyError:
            return None
        return layer_time

    def extract_time_from_layer(self, layer):
        """ Returns the time for the given layer from either its file name,
        exif data, tif header or xml file. """
        extraction_methods = []

        i = 0
        list_widget = self.parent.extractionPriorityListWidget
        write_meta = self.parent.writeMetaDataCheckBox

        while i < list_widget.count():
            if list_widget.item(i).text() == "XML" and \
                    list_widget.item(i).checkState() == Qt.Checked:
                extraction_methods.append(
                    self.extract_time_from_persistent_metadata)

            elif list_widget.item(i).text() == "Filename" and \
                    list_widget.item(i).checkState() == Qt.Checked:
                extraction_methods.append(self.extract_time_from_filename)

            elif list_widget.item(i).text() == "Exif" and \
                    list_widget.item(i).checkState() == Qt.Checked:
                extraction_methods.append(self.extract_time_from_exif)

            elif list_widget.item(i).text() == "TIFF-Header" and \
                    list_widget.item(i).checkState() == Qt.Checked:
                extraction_methods.append(self.extract_time_from_tif)
            i += 1

        t = None
        for extraction_method in extraction_methods:
            t = extraction_method(layer)
            if t is not None:
                break

        if write_meta.isChecked():
            self.write_time_to_metadata(layer, t)

        return t  # Is meant to return a datetime.datetime but could actually
        # return None

    def extract_time_from_persistent_metadata(self, layer):
        layer_path = layer.source()
        # read from associated *.aux.xml file
        ds = gdal.Open(layer_path, GA_ReadOnly)
        date = ds.GetMetadataItem('DateTime')
        if date is None:
            return_date = None
        else:
            return_date = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%S")
        return return_date

    def cut_first_spinbox_changed(self):
        self.update_sample()
        current_sample_len = len(self.parent.sampleLineEdit.text())
        self.parent.dateLength.setValue(current_sample_len)

    def date_length_spinbox_changed(self):
        self.update_sample()

    def initiate_values(self):
        path_to_layer = None
        for layer_id, layer in self.registry.mapLayers().items():
            if layer.type() == QgsMapLayer.RasterLayer:
                path_to_layer = layer.source()
                break

        if path_to_layer is None:
            return

        filename = QFileInfo(path_to_layer).completeBaseName()

        if self.parent.cutFirst.value() > 0 and \
           self.parent.dateLength.value() > 0:

            filename = self.make_strptime_safe(filename)

        self.parent.dateLength.setValue(len(filename))
        self.parent.sampleLineEdit.setText(filename)

    def update_sample(self):
        path_to_layer = None
        for layer_id, layer in self.registry.mapLayers().items():
            if layer.type() == QgsMapLayer.RasterLayer:
                path_to_layer = layer.source()
                break
        if path_to_layer is None:
            return
        filename = QFileInfo(path_to_layer).completeBaseName()
        final_name = self.make_strptime_safe(filename)
        # set the value back to GUI
        self.parent.sampleLineEdit.setText(final_name)

    def make_strptime_safe(self, filename):
        cut_front_characters = self.parent.cutFirst.value()
        length_of_date = self.parent.dateLength.value()
        # cut filename according to the values in GUI
        cut_name = filename[cut_front_characters:]
        final_name = cut_name[:length_of_date]
        return final_name

    def extract_time_from_filename(self, layer):
        path_to_layer = layer.source()
        filename = QFileInfo(path_to_layer).completeBaseName()
        trimmed_filename = self.make_strptime_safe(filename)

        pattern = self.parent.patternLineEdit.text()
        try:
            date = datetime.datetime.strptime(trimmed_filename, pattern)
        except ValueError:
            date = None
        # return that date as a datetime.datetime
        return date

    def validate_date_string(self):  # FIXME check for double input e.g. %H%H
        list_widget = self.parent.extractionPriorityListWidget
        valid = True

        pattern_line = self.pattern_edit
        pal = QPalette(pattern_line.palette())

        pattern = self.parent.patternLineEdit.text()
        sample = self.parent.sampleLineEdit.text()
        today_string = ''
        i = 0
        from_file_name_checked = False
        # orig_color = pal.background()

        while i < list_widget.count():

            if list_widget.item(i).text() == "Filename" and \
                    list_widget.item(i).checkState() == Qt.Checked:
                from_file_name_checked = True
            i += 1
        if not from_file_name_checked:
            pal.setColor(QPalette.Base, QColor('white'))
            pattern_line.setPalette(pal)
            return
        try:
            datetime.datetime.strptime(sample,
                                       pattern)
        except ValueError:
            valid = False
        try:
            today_string = datetime.datetime.strftime(datetime.datetime.today(),
                                                      pattern)
        except ValueError:
            valid = False
        if len(today_string) != len(sample):
            valid = False
        if valid:
            pal.setColor(QPalette.Base, QColor(0, 255, 0, 127))  # light green
        else:
            pal.setColor(QPalette.Base, QColor(255, 0, 0, 127))  # light red
        pattern_line.setPalette(pal)

    def extract_time_from_exif(self, layer):
        #  FIXME add functionality here
        return  # datetime.datetime(2000, 3, 1)

    def extract_time_from_tif(self, layer):
        #  FIXME add functionality here
        return  # datetime.datetime(2000, 12, 1)

    def write_time_to_metadata(self, layer, t):
        layer_path = layer.source()
        # read from associated *.aux.xml file
        ds = gdal.Open(layer_path, GA_Update)
        if t is not None:
            metadata = t.isoformat()
            ds.SetMetadataItem('DateTime', metadata, '')
        else:
            return
        ds.FlushCache()
