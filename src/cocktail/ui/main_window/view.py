import PySide6.QtGui
import qtawesome
from PySide6 import QtWidgets, QtGui, QtCore
from cocktail.ui.model_gallery import ModelGalleryView
from cocktail.ui.model_info import ModelInfoView
from cocktail.ui.download import ModelDownloadView
from cocktail.ui.database import DatabaseView
from cocktail.ui.search import SearchView
from cocktail.ui.settings import SettingsView


class TopBar(QtWidgets.QWidget):
    downloadClicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.download_icon = QtWidgets.QPushButton("Download")
        self.download_icon.setIcon(qtawesome.icon("fa5s.download", color="#89B4FA"))
        
        # Add modern styling to the download button
        self.download_icon.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, 
                                            stop: 0 #89B4FA, stop: 1 #74C7EC);
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                color: #1E1E2E;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, 
                                            stop: 0 #74C7EC, stop: 1 #89B4FA);
                transform: translateY(-1px);
            }
            QPushButton:pressed {
                background: #585B70;
                transform: translateY(0px);
            }
        """)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.insertStretch(0)
        layout.addWidget(self.download_icon)

        self.download_icon.clicked.connect(self.downloadClicked.emit)


class CenterWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.search_view = SearchView()
        self.model_gallery_view = ModelGalleryView()
        self.model_info_view = ModelInfoView()
        self.model_download_view = ModelDownloadView()
        self.database_view = DatabaseView()
        self.settings_view = SettingsView()

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(False)
        self.tabs.setMovable(False)
        
        # Use modern icons with consistent color
        icon_color = "#BAC2DE"
        info_icon = qtawesome.icon("fa5s.info-circle", color=icon_color)
        self.tabs.addTab(self.model_info_view, info_icon, "Info")

        download_icon = qtawesome.icon("fa5s.download", color=icon_color)
        self.tabs.addTab(self.model_download_view, download_icon, "Downloads")

        db_icon = qtawesome.icon("fa5s.database", color=icon_color)
        self.tabs.addTab(self.database_view, db_icon, "Database")

        settings_icon = qtawesome.icon("fa5s.cog", color=icon_color)
        self.tabs.addTab(self.settings_view, settings_icon, "Settings")

        # Create browser section with improved layout
        browser_widget = QtWidgets.QWidget()
        browser_layout = QtWidgets.QVBoxLayout(browser_widget)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(8)
        browser_layout.addWidget(self.search_view)
        browser_layout.addWidget(self.model_gallery_view, 1)  # Give gallery more space

        # Create tabs section with scroll area
        tabs_widget = QtWidgets.QWidget()
        tabs_layout = QtWidgets.QVBoxLayout(tabs_widget)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.addWidget(self.tabs)

        tabs_scroll_area = QtWidgets.QScrollArea()
        tabs_scroll_area.setWidgetResizable(True)
        tabs_scroll_area.setWidget(tabs_widget)
        tabs_scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        tabs_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Create main splitter for better layout control
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(browser_widget)
        self.main_splitter.addWidget(tabs_scroll_area)
        
        # Set initial proportions (60% browser, 40% tabs)
        self.main_splitter.setSizes([600, 400])
        self.main_splitter.setStretchFactor(0, 3)  # Browser gets more stretch
        self.main_splitter.setStretchFactor(1, 2)  # Tabs get less stretch
        
        # Style the splitter handle
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #45475A;
                margin: 2px 4px;
                border-radius: 3px;
            }
            QSplitter::handle:hover {
                background: #89B4FA;
            }
        """)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.main_splitter)

        self.model_info_view.requestFocus.connect(self.switchToTab)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        # Improved keyboard handling
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.search_view.hide()
        elif event.key() in (QtCore.Qt.Key.Key_F, QtCore.Qt.Key.Key_Slash) and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            self.search_view.show()
            self.search_view.setFocus()
        else:
            self.search_view.show()
            self.search_view.keyPressEvent(event)
        return super().keyPressEvent(event)

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:
        # Only hide search on click elsewhere, not on all focus events
        if event.reason() == QtCore.Qt.FocusReason.MouseFocusReason:
            self.search_view.hide()
        return super().focusInEvent(event)

    def onDownloadClicked(self):
        # Improved download button positioning
        button_rect = self.sender().geometry() if self.sender() else QtCore.QRect()
        view_rect = self.model_download_view.geometry()

        # Calculate position relative to parent widget
        global_pos = self.mapToGlobal(QtCore.QPoint(
            button_rect.left() + button_rect.width() - view_rect.width(),
            button_rect.bottom() + 10
        ))
        
        local_pos = self.mapFromGlobal(global_pos)
        self.model_download_view.move(local_pos)
        self.model_download_view.show()
        
        # Animate the appearance
        self.model_download_view.setGraphicsEffect(None)  # Remove any existing effects
        effect = QtWidgets.QGraphicsOpacityEffect()
        self.model_download_view.setGraphicsEffect(effect)
        
        self.fade_animation = QtCore.QPropertyAnimation(effect, b"opacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()

    def switchToTab(self, widget):
        self.tabs.setCurrentWidget(widget)
        
        # Add subtle animation to tab switching
        current_index = self.tabs.currentIndex()
        self.tabs.tabBar().setCurrentIndex(current_index)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        # Set window properties for better appearance
        self.setWindowTitle("🍸 Cocktail Model Manager")
        self.setMinimumSize(1200, 800)
        
        # Create top bar
        self.top_bar = TopBar()
        
        # Create central widget
        self.central_widget = CenterWidget()
        
        # Create main layout combining top bar and center widget
        main_container = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.top_bar)
        main_layout.addWidget(self.central_widget, 1)
        
        self.setCentralWidget(main_container)
        
        # Connect top bar signals
        self.top_bar.downloadClicked.connect(self.central_widget.onDownloadClicked)
        
        # Set up status bar with modern styling
        self.status_bar = QtWidgets.QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #2A2A3A;
                border-top: 1px solid #45475A;
                color: #BAC2DE;
                font-size: 12px;
                padding: 4px 8px;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready • Modern UI Loaded")

    def resizeEvent(self, event):
        """Handle window resize for responsive design"""
        super().resizeEvent(event)
        
        # Adjust splitter proportions based on window size
        if hasattr(self.central_widget, 'main_splitter'):
            width = event.size().width()
            if width < 1400:
                # Smaller window: give more space to browser
                self.central_widget.main_splitter.setSizes([int(width * 0.65), int(width * 0.35)])
            else:
                # Larger window: more balanced
                self.central_widget.main_splitter.setSizes([int(width * 0.6), int(width * 0.4)])
