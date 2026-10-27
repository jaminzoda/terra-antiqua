"""
/***************************************************************************
 Terra Antiqua
                                 A QGIS plugin

Terra Antiqua deals with the reconstruction of paleogeography, simplifying the reconstruction process. The conceptual approach we follow consists of modifying present-day topography, assuming that it is possible to infer the paleogeography based on present-day observations (e.g., fossil data, thermochronological data). Terra Antiqua provides a complete set of tools to edit Digital Elevations Models (DEM) for paleoreconstructions.
                              -------------------
        begin             : 2019-03-18
        git sha           : $Format:%H$
        copyright         : (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
        email             : jovid.aminov@outlook.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 *   This program is distributed in the hope that it will be useful,       *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU General Public License for more details.                          *
 *                                                                         *
 *   You should have received a copy of the GNU General Public License     *
 *   along with this program.  If not, see <https://www.gnu.org/licenses/>.*
 *                                                                         *
 *                                                                         *
 ***************************************************************************/
"""
# [QGIS4 port] Changes made in v1.1.1 for QGIS 4 compatibility (lines marked "# [QGIS4 port]"):
#  - Imports switched from PyQt5 to qgis.PyQt (works with both Qt5 and Qt6);
#    QAction comes from compat (it moved from QtWidgets to QtGui in Qt6)
#  - initGui: toolbar icons are loaded from the resources/ folder through compat.icon_path
#    (removed: the compiled resources.py, which only worked with Qt5)
#  - __init__: no error when QGIS has no locale setting yet
#  - initRemoveArtefacts: no error when the tool is clicked again after closing its tooltip
#  See core/compat.py for the note on how this port was made.
from qgis.PyQt.QtCore import (  # [QGIS4 port]
                            QSettings,
                            QTranslator,
                            qVersion,
                            QCoreApplication
                        )
from qgis.PyQt.QtGui import QIcon  # [QGIS4 port]
from qgis.PyQt.QtWidgets import QToolBar  # [QGIS4 port]
from qgis.core import QgsSettings

import os.path

from .compile_tb import TaCompileTopoBathy
from .create_tb import TaCreateTopoBathy
from .prepare_masks import TaPrepareMasks
from .set_pls import TaSetPaleoshorelines
from .standard_proc import TaStandardProcessing
from .modify_tb import TaModifyTopoBathy
from .remove_arts_tooltip import TaRemoveArtefactsTooltip
from .settings import TaSettings
from .algorithm_provider import TaAlgorithmProvider, TaRemoveArtefactsAlgProvider
from .compat import QAction, icon_path as ta_icon_path  # [QGIS4 port]

from ..gui.compile_tb_dlg import  TaCompileTopoBathyDlg
from ..gui.modify_tb_dlg import  TaModifyTopoBathyDlg
from ..gui.create_tb_dlg import  TaCreateTopoBathyDlg
from ..gui.prepare_masks_dlg import  TaPrepareMasksDlg
from ..gui.set_pls_dlg import  TaSetPaleoshorelinesDlg
from ..gui.remove_arts_dlg import  TaRemoveArtefactsDlg
from ..gui.standard_proc_dlg import  TaStandardProcessingDlg



class TerraAntiqua:

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # the reference to the Map canvas of the current project
        self.canvas = self.iface.mapCanvas()
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = (QSettings().value('locale/userLocale') or '')[0:2]  # [QGIS4 port]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'TerraAntiqua_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Terra Antiqua')

        # Create a separate toolbar for the plugin
        self.ta_toolBar = iface.mainWindow().findChild(QToolBar, u'Terra Antiqua')
        if not self.ta_toolBar:
            self.ta_toolBar = iface.addToolBar(u'Terra Antiqua')
            self.ta_toolBar.setObjectName(u'Terra Antiqua')

        # Load the settings object. Read settings and passes them to the plugin
        self.settings = TaSettings("TerraAntiqua", "Terra Antiqua")
        self.settings.tempValueChanged.connect(self.updatePluginSettings)

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start =None


    # Create the tool dialog

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('TerraAntiqua', message)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag = True,
            add_to_menu = True,
            add_to_toolbar = True,
            status_tip = None,
            whats_this = None,
            parent = None,
            checkable = False):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)


        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Terra Antiqua toolbar
            self.ta_toolBar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)
        if checkable:
            action.setCheckable(True)
        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        compile_tb_icon = ta_icon_path('compile_tb_icon.png')  # [QGIS4 port]
        prepare_masks_icon = ta_icon_path('prepare_masks_icon.png')  # [QGIS4 port]
        modify_tb_icon = ta_icon_path('modify_tb_icon.png')  # [QGIS4 port]
        set_pls_icon = ta_icon_path('set_pls_icon.png')  # [QGIS4 port]
        std_proc_icon = ta_icon_path('std_proc_icon.png')  # [QGIS4 port]
        feat_create_icon = ta_icon_path('feat_create_icon.png')  # [QGIS4 port]
        remove_arts_icon = ta_icon_path('remove_arts_icon.png')  # [QGIS4 port]

        self.add_action(
            compile_tb_icon,
            text = self.tr(u'Compile Topo/Bathymetry'),
            callback = self.initCompileTopoBathy,
            parent = self.iface.mainWindow())

        self.add_action(
            set_pls_icon,
            text = self.tr(u'Set Paleoshorelines'),
            callback = self.initSetPaleoShorelines,
            parent = self.iface.mainWindow())

        self.add_action(
            modify_tb_icon,
            text = self.tr(u'Modify Topo/Bathymetry'),
            callback = self.initModifyTopoBathy,
            parent = self.iface.mainWindow())


        self.add_action(
            feat_create_icon,
            text = self.tr(u'Create Topo/Bathymetry'),
            callback = self.initCreateTopoBathy,
            parent = self.iface.mainWindow())


        self.add_action(
            remove_arts_icon,
            text = self.tr(u'Remove Artefacts'),
            callback = self.initRemoveArtefacts,
            parent = self.iface.mainWindow(),
            checkable = True)

        self.add_action(
            prepare_masks_icon,
            text = self.tr(u'Prepare masks'),
            callback = self.initPrepareMasks,
            parent = self.iface.mainWindow())

        self.add_action(
            std_proc_icon,
            text = self.tr(u'Standard Processing'),
            callback = self.initStandardProcessing,
            parent = self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True
        self.settings.setTempValue("first_start", True)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Terra Antiqua'),
                action)
            self.iface.removeToolBarIcon(action)
            self.ta_toolBar.removeAction(action)

    def updatePluginSettings(self, key, value):
        if key == "first_start":
            self.first_start = False


    def initCompileTopoBathy(self):
        """Initializes the Compile Topo/Bathymetry algorithm and loads it"""
        self.compileTopoBathy = TaAlgorithmProvider(
                                                        TaCompileTopoBathyDlg,
                                                        TaCompileTopoBathy,
                                                        self.iface,
                                                        self.settings)
        self.compileTopoBathy.load()

    def initPrepareMasks(self):
        """Initializes the Prepare masks algorithm and loads it"""
        self.prepareMasks = TaAlgorithmProvider(TaPrepareMasksDlg,
                                                   TaPrepareMasks,
                                                   self.iface,
                                                   self.settings)
        self.prepareMasks.load()

    def initModifyTopoBathy(self):
        """Initializes the Modify Topo/Bathymetry algorithm and loads it"""
        self.modifyTopoBathy = TaAlgorithmProvider(TaModifyTopoBathyDlg,
                                                      TaModifyTopoBathy,
                                                      self.iface,
                                                      self.settings)
        self.modifyTopoBathy.load()


    def initSetPaleoShorelines(self):
        """Initializes the Set Paleoshorelines algorithm and loads it"""
        self.setPaleoshorelines = TaAlgorithmProvider(
                                                        TaSetPaleoshorelinesDlg,
                                                        TaSetPaleoshorelines,
                                                        self.iface,
                                                        self.settings)
        self.setPaleoshorelines.load()

    def initStandardProcessing(self):
        """Initializes the Standard processing algorithm set and loads it"""
        self.standardProcessing = TaAlgorithmProvider(TaStandardProcessingDlg,
                                                         TaStandardProcessing,
                                                         self.iface,
                                                         self.settings)
        self.standardProcessing.load()

    def initCreateTopoBathy(self):
        """Initializes the Create Topography/Bathymetry algorithm and loads it"""
        self.createTopoBathy = TaAlgorithmProvider(TaCreateTopoBathyDlg,
                                                      TaCreateTopoBathy,
                                                      self.iface,
                                                      self.settings)
        self.createTopoBathy.load()

    def initRemoveArtefacts(self):
        """Initializes the Remove artefacts algorithm and activates it"""
        if self.settings.removeArtefactsChecked and not hasattr(self.removeArtefacts, "toolPoly"):  # [QGIS4 port]
            # The tooltip was dismissed before any polygon tool was started: just reset.
            self.removeArtefacts.clean()  # [QGIS4 port]
        elif self.settings.removeArtefactsChecked:  # [QGIS4 port]
            self.removeArtefacts.storeRubberbands(self.removeArtefacts.toolPoly.rubberband, self.removeArtefacts.toolPoly.vertices, self.removeArtefacts.toolPoly.points)
            self.removeArtefacts.clean()
        else:
            self.settings.removeArtefactsChecked = True
            self.removeArtefacts = TaRemoveArtefactsAlgProvider(TaRemoveArtefactsTooltip, TaRemoveArtefactsDlg, self.iface, self.actions, self.settings)
            self.removeArtefacts.initiate()







