from PyQt5 import QtCore

import logging

class TaLogHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.COLORS = {
            logging.DEBUG: 'blue',
            logging.INFO: 'black',
            logging.WARNING: 'brown',
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
    _progress = None
    messageWritten = QtCore.pyqtSignal(str)
    progressSet = QtCore.pyqtSignal(int)
    def flush( self ):
        pass
    def fileno( self ):
        return -1
    def write( self, msg ):
        if ( not self.signalsBlocked() ):
            self.messageWritten.emit(unicode(msg))
    def emitProgress(self, progress_count):
        self.progressSet.emit(int(progress_count))
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

    @staticmethod
    def progress():
        if (not TaLogStream._progress):
            TaLogStream._progress = TaLogStream()
        return TaLogStream._progress

class TaFeedback(QtCore.QObject):
    finished = QtCore.pyqtSignal(bool)
    def __init__(self, dlg):
        super(TaFeedback).__init__()
        self.canceled = False
        self.logger= logging.getLogger(dlg.alg_name)
        if len(self.logger.handlers):
            for handler in self.logger.handlers:
                self.logger.removeHandler(handler)

        handler = TaLogHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt='%I:%M:%S'))
        #handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt='%Y-%m-%d %I:%M:%S'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)
        self.progress_count = 0
        TaLogStream.stdout().messageWritten.connect( dlg.logBrowser.textCursor().insertHtml )
        #TaLogStream.stderr().messageWritten.connect( self.logText.insertPlainText )
        TaLogStream.progress().progressSet.connect(dlg.setProgressValue)
        self.Critical = self.critical
        self.Error = self.error
        self.Warning = self.warning
        self.Info = self.info
        self.Debug = self.debug

    def debug(self, record):
        self.logger.debug(record)

    def info(self, record):
        if not self.canceled:
           self.logger.info(record)

    def warning(self, record):
        self.logger.warning(record)

    def error(self, record):
        self.logger.error(record)

    def critical(self, record):
        self.logger.critical(record)

    def setProgress(self, progress_value):
        pass

    @property
    def progress(self):
        return self.progress_count

    @progress.setter
    def progress(self, progress_value):
        self.progress_count = progress_value
        if progress_value:
            TaLogStream.progress().emitProgress(self.progress_count)
       #     with open("log.txt", "a") as log_file:
        #        log_file.write("progress: {}\n".format(self.progress_count))

    def setCanceled(self, value:bool):
        self.canceled =value
        self.progress_count = 0
