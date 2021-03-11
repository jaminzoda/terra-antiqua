from .base_dialog import TaBaseDialog
from .widgets import TaVectorLayerComboBox
class TaInterpolateBetweenTimeStepsDlg(TaBaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.defineParameters()
    def defineParameters(self):
        self.static_polygons_box = self.addMandatoryParameter(
