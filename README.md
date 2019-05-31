The QGIS plugin directory is located at:
    /home/USER_PROFILE/.local/share/QGIS/QGIS3/profiles/default/python/plugins

To use this plugin do the following:

  * Copy the entire directory containing your new plugin to the QGIS plugin
    directory

  * Compile the resources file using pyrcc5

  * Run the tests (``make test``)

  * Test the plugin by enabling it in the QGIS plugin manager

  * Customize it by editing the implementation file: ``dem_builder.py``

  * Create your own custom icon, replacing the default icon.png

  * Modify the user interface by opening DEMBuilder_dialog_base.ui in Qt Designer

  * You can use the Makefile to compile your Ui and resource files when
    you make changes. This requires GNU make (gmake)

For more information, see the PyQGIS Developer Cookbook at:
http://www.qgis.org/pyqgis-cookbook/index.html

(C) 2019 Magic - paleoenvironment.eu
