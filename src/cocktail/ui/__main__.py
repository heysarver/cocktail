import logging
import argparse

from PySide6 import QtWidgets, QtCore
from cocktail import resources
from cocktail.ui.main_window import MainWindowController
from cocktail.ui.startup import StartupController

MAIN_CONTROLLER = None


def apply_stylesheet():
    app = QtWidgets.QApplication.instance()
    style_sheet = resources.text("stylesheet.qss")
    app.setStyleSheet(style_sheet)


def list_resources(root=None):
    root = root or QtCore.QResource(":/cocktail")
    for child in root.children():
        child = QtCore.QResource(f"{root.absoluteFilePath()}/{child}")
        if child.isDir():
            list_resources(child)
        else:
            print(child.absoluteFilePath())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-update", action="store_true")
    parser.add_argument("--list-resources", action="store_true")
    parser.add_argument("--performance", action="store_true", help="Enable performance monitoring")

    args = parser.parse_args()

    # Set up application with performance optimizations
    app = QtWidgets.QApplication()
    
    # Performance optimizations
    app.setAttribute(QtCore.Qt.ApplicationAttribute.AA_DisableWindowContextHelpButton, True)
    app.setAttribute(QtCore.Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
    app.setAttribute(QtCore.Qt.ApplicationAttribute.AA_NativeWindows, False)
    
    # Set up threading for better responsiveness
    QtCore.QThread.idealThreadCount()  # Initialize thread pool
    
    icon = resources.icon("cocktail.png")
    app.setWindowIcon(icon)
    app.setApplicationName("Cocktail")
    app.setApplicationDisplayName("🍸 Cocktail Model Manager")
    app.setApplicationVersion("2.0")
    apply_stylesheet()

    if args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Performance monitoring
    if args.performance:
        import psutil
        import os
        process = psutil.Process(os.getpid())
        print(f"Initial memory usage: {process.memory_info().rss / 1024 / 1024:.1f} MB")

    if args.list_resources:
        list_resources()
        return

    def start():
        """
        Creating a database connection will create an empty database if one does not exist.
        This will fool the startup controller into thinking that the database is already
        downloaded and extracted. so we only instantiate the main window controller after
        the startup controller has completed.
        """
        global MAIN_CONTROLLER
        MAIN_CONTROLLER = MainWindowController()
        MAIN_CONTROLLER.view.showMaximized()
        
        # Show welcome message instead of immediately starting heavy operations
        MAIN_CONTROLLER.view.status_bar.showMessage("Welcome to Cocktail • Ready for use")
        
        # Only auto-update if explicitly requested and not disabled
        if not args.no_update:
            # Delay automatic updates to let UI settle first
            def delayed_update():
                if MAIN_CONTROLLER and MAIN_CONTROLLER.view.isVisible():
                    MAIN_CONTROLLER.view.status_bar.showMessage("Checking for updates...")
                    try:
                        MAIN_CONTROLLER.database_controller.updateModelData()
                    except Exception as e:
                        logging.error(f"Auto-update failed: {e}")
                        MAIN_CONTROLLER.view.status_bar.showMessage("Auto-update failed • Manual update available in Database tab")
            
            # Start update after 2 seconds to let UI fully load
            QtCore.QTimer.singleShot(2000, delayed_update)
        else:
            MAIN_CONTROLLER.view.status_bar.showMessage("Auto-update disabled • Use Database tab to update manually")

    start_up_controller = StartupController()
    start_up_controller.complete.connect(start)
    start_up_controller.start()

    # Set up graceful shutdown
    def cleanup():
        global MAIN_CONTROLLER
        if MAIN_CONTROLLER:
            # Clear caches to free memory
            if hasattr(MAIN_CONTROLLER, 'model_gallery_controller'):
                gallery_view = MAIN_CONTROLLER.model_gallery_controller.view
                if hasattr(gallery_view, 'clearCaches'):
                    gallery_view.clearCaches()
            
            # Clean up database connections
            if hasattr(MAIN_CONTROLLER, 'database_controller'):
                if hasattr(MAIN_CONTROLLER.database_controller, 'worker_thread'):
                    MAIN_CONTROLLER.database_controller.worker_thread.quit()
                    MAIN_CONTROLLER.database_controller.worker_thread.wait(5000)
    
    app.aboutToQuit.connect(cleanup)

    try:
        exit_code = app.exec()
        
        # Performance monitoring at exit
        if args.performance:
            print(f"Final memory usage: {process.memory_info().rss / 1024 / 1024:.1f} MB")
            
        return exit_code
    except Exception as e:
        logging.error(f"Application error: {e}")
        return 1
    finally:
        cleanup()


if __name__ == "__main__":
    import sys
    sys.exit(main())
