import sip
from PyQt5 import QtCore

import sys
from PyQt5 import QtWidgets
import logging

class TaLogHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.COLORS = {
            logging.DEBUG: 'blue',
            logging.INFO: 'black',
            logging.WARNING: 'orange',
            logging.ERROR: 'red',
            logging.CRITICAL: 'purple',
            }
    def emit(self, record):
        color = self.COLORS.get(record.levelno)
        record = self.format(record)
        msg = '<font color="%s">%s</font>' % (color, record)
        if record: TaLogStream.stdout().write('{}<br>'.format(msg))

class TaLogStream(QtCore.QObject):
    _stdout = None
    _stderr = None
    messageWritten = QtCore.pyqtSignal(str)
    def flush( self ):
        pass
    def fileno( self ):
        return -1
    def write( self, msg ):
        if ( not self.signalsBlocked() ):
            self.messageWritten.emit(unicode(msg))
    @staticmethod
    def stdout():
        if ( not TaLogStream._stdout ):
            TaLogStream._stdout = TaLogStream()
            #sys.stdout = TaLogStream._stdout
        return TaLogStream._stdout
    @staticmethod
    def stderr():
        if ( not TaLogStream._stderr ):
            TaLogStream._stderr = TaLogStream()
            #sys.stderr = TaLogStream._stderr
        return TaLogStream._stderr

