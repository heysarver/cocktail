__all__ = ["DatabaseController"]

from PySide6 import QtCore, QtWidgets, QtSql
import logging
import cocktail.core.database
from cocktail.core.database import data_classes, api as db_api
from cocktail.core.providers.model_data import ModelDataProvider
from cocktail.ui.database.view import DatabaseView
from cocktail.ui.logger import LogController


class DatabaseWorker(QtCore.QObject):
    """Worker thread for database operations to prevent UI freezing"""
    dataUpdated = QtCore.Signal()
    updateMessage = QtCore.Signal(str)
    finished = QtCore.Signal()
    error = QtCore.Signal(str)

    def __init__(self, connection):
        super().__init__()
        self.connection = connection

    @QtCore.Slot(object)
    def insertPage(self, page):
        """Insert page data in background thread"""
        try:
            # Create new connection for this thread
            thread_connection = QtSql.QSqlDatabase.cloneDatabase(self.connection, 
                                                               f"worker_{QtCore.QThread.currentThreadId()}")
            if not thread_connection.open():
                self.error.emit(f"Failed to open database connection: {thread_connection.lastError().text()}")
                return
                
            db_api.insert_page(thread_connection, page)
            thread_connection.close()
            QtSql.QSqlDatabase.removeDatabase(f"worker_{QtCore.QThread.currentThreadId()}")
            
            self.dataUpdated.emit()
        except Exception as e:
            self.error.emit(f"Database error: {str(e)}")

    @QtCore.Slot()
    def setLastUpdated(self):
        """Set last updated timestamp in background thread"""
        try:
            thread_connection = QtSql.QSqlDatabase.cloneDatabase(self.connection, 
                                                               f"worker_last_updated_{QtCore.QThread.currentThreadId()}")
            if not thread_connection.open():
                self.error.emit(f"Failed to open database connection: {thread_connection.lastError().text()}")
                return
                
            db_api.set_last_updated(thread_connection)
            thread_connection.close()
            QtSql.QSqlDatabase.removeDatabase(f"worker_last_updated_{QtCore.QThread.currentThreadId()}")
            
            self.finished.emit()
        except Exception as e:
            self.error.emit(f"Database error: {str(e)}")


class DatabaseController(QtCore.QObject):
    updateComplete = QtCore.Signal()
    updateProgress = QtCore.Signal(int)
    updateMessage = QtCore.Signal(str)
    dataUpdated = QtCore.Signal()

    def __init__(self, connection, view=None, parent=None):
        super().__init__(parent)
        self.view = view or DatabaseView()
        self.connection: QtSql.QSqlDatabase = connection
        
        # Set up worker thread for database operations
        self.worker_thread = QtCore.QThread()
        self.worker = DatabaseWorker(connection)
        self.worker.moveToThread(self.worker_thread)
        
        # Connect worker signals
        self.worker.dataUpdated.connect(self.dataUpdated.emit)
        self.worker.updateMessage.connect(self.updateMessage.emit)
        self.worker.finished.connect(self.onUpdateEnd)
        self.worker.error.connect(self.onDatabaseError)
        
        # Start worker thread
        self.worker_thread.start()
        
        # Set up model data provider with throttling
        self.model_data_provider = ModelDataProvider()
        self.model_data_provider.pageReady.connect(self.onPageReady)
        self.model_data_provider.beginRequest.connect(self.onUpdateBegin)
        self.model_data_provider.progress.connect(self.onUpdateProgress)
        self.model_data_provider.endRequest.connect(self.onProviderUpdateEnd)
        
        # Connect view signals
        self.view.updateClicked.connect(self.updateModelData)
        
        # Set up logging
        self.logger = logging.getLogger(cocktail.core.database.__name__)
        self.log_controller = LogController(self.logger, self.view.log_view)
        self.log_controller.logMessageReceived.connect(self.updateMessage)
        
        # Throttle database updates to prevent UI freezing
        self.update_timer = QtCore.QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._emitDataUpdated)
        self.pending_updates = 0

    def updateModelData(self, period: data_classes.Period = None):
        """Start model data update with better UI feedback"""
        if period is None:
            period = db_api.get_db_update_period(self.connection)

        self.logger.info(f"Updating model data for period: {period.value}")
        self.updateMessage.emit(f"Starting update for {period.value}")

        # Disable UI during update to prevent multiple concurrent updates
        if hasattr(self.view, 'setUpdateInProgress'):
            self.view.setUpdateInProgress(True)

        self.model_data_provider.requestModelData(period)

    def onPageReady(self):
        """Handle page ready with background processing"""
        page = self.model_data_provider.queue.get()
        
        # Process page in worker thread
        QtCore.QMetaObject.invokeMethod(
            self.worker, 
            "insertPage", 
            QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(object, page)
        )
        
        # Throttle UI updates to prevent freezing
        self.pending_updates += 1
        if not self.update_timer.isActive():
            self.update_timer.start(100)  # Update UI every 100ms max

    def _emitDataUpdated(self):
        """Throttled data update signal"""
        if self.pending_updates > 0:
            self.pending_updates = 0
            # Only emit if we're still visible/active
            if self.view and self.view.isVisible():
                self.dataUpdated.emit()

    def onUpdateBegin(self):
        """Handle update start"""
        self.updateMessage.emit("Connecting to API...")
        self.view.setProgressText("Connecting to API...")
        self.view.setProgress(0, 0)

    def onUpdateProgress(self, value, total):
        """Handle update progress with less frequent UI updates"""
        # Only update UI every 50 items to reduce overhead
        if value % 50 == 0 or value == total:
            progress_text = f"Processing models: {value}/{total}"
            self.view.setProgressText(progress_text)
            self.updateMessage.emit(progress_text)
            self.view.setProgress(value, total)
            
            # Process events to keep UI responsive
            QtCore.QCoreApplication.processEvents()

    def onProviderUpdateEnd(self):
        """Handle provider update completion"""
        self.updateMessage.emit("Finalizing update...")
        
        # Set last updated in worker thread
        QtCore.QMetaObject.invokeMethod(
            self.worker, 
            "setLastUpdated", 
            QtCore.Qt.ConnectionType.QueuedConnection
        )

    def onUpdateEnd(self):
        """Handle complete update end"""
        self.view.setProgress(0, 100)
        self.view.setProgressText("Update Complete")
        self.updateMessage.emit("Update Complete")
        
        # Re-enable UI
        if hasattr(self.view, 'setUpdateInProgress'):
            self.view.setUpdateInProgress(False)
            
        self.updateComplete.emit()
        
        # Force final data update
        self.dataUpdated.emit()

    def onDatabaseError(self, error_message):
        """Handle database errors"""
        self.logger.error(f"Database error: {error_message}")
        self.updateMessage.emit(f"Error: {error_message}")
        
        # Re-enable UI on error
        if hasattr(self.view, 'setUpdateInProgress'):
            self.view.setUpdateInProgress(False)

    def __del__(self):
        """Clean up worker thread"""
        if hasattr(self, 'worker_thread'):
            self.worker_thread.quit()
            self.worker_thread.wait()


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)

    app = QtWidgets.QApplication()

    db = db_api.get_connection()

    controller = DatabaseController(db)
    controller.updateModelData(period=data_classes.Period.Day)
    controller.view.show()

    app.exec()
