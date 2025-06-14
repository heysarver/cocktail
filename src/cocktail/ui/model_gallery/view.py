__all__ = ["ModelGalleryView"]
import math
from PySide6 import QtCore, QtGui, QtWidgets, QtSql

from cocktail.ui.model_gallery.delegate import ModelGalleryItemDelegate


class ImageGalleryListView(QtWidgets.QListView):
    gridSizeChanged = QtCore.Signal(QtCore.QSize)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._item_delegate = ModelGalleryItemDelegate()

        self.setWrapping(True)
        self.setFlow(QtWidgets.QListView.Flow.LeftToRight)
        self.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        
        # Performance optimizations
        self.setUniformItemSizes(True)  # All items same size for better performance
        self.setLayoutMode(QtWidgets.QListView.LayoutMode.Batched)  # Batch layout updates
        self.setBatchSize(25)  # Reduced batch size for more responsive updates
        
        # Enable viewport updates for smoother scrolling
        self.setUpdatesEnabled(True)
        self.viewport().setUpdatesEnabled(True)
        
        # Viewport-only rendering optimization
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        
        # Smooth scrolling improvements
        self.verticalScrollBar().setSingleStep(20)
        self.setMouseTracking(True)  # Better hover effects
        
        self.setGridSize(QtCore.QSize(450, 650))
        self.setItemDelegate(self._item_delegate)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        self.gridSizeChanged.connect(self._item_delegate.setItemSize)

        self._items_per_row = 5
        self._item_aspect_ratio = 1.5
        
        # Cache for better performance
        self._cached_grid_size = QtCore.QSize()
        self._cached_viewport_width = 0
        
        # Lazy loading and viewport optimization
        self._last_visible_range = (0, 0)
        self._viewport_timer = QtCore.QTimer()
        self._viewport_timer.setSingleShot(True)
        self._viewport_timer.timeout.connect(self._updateVisibleItems)
        
        # Connect scroll events for lazy loading
        self.verticalScrollBar().valueChanged.connect(self._onScrollChanged)
        
        # Intersection observer for performance
        self._visible_items_cache = set()

    def setItemsPerRow(self, items_per_row):
        if self._items_per_row != items_per_row:
            self._items_per_row = items_per_row
            self._updateGridSize()

    def setGridSize(self, size: QtCore.QSize) -> None:
        if self.gridSize() != size:
            super().setGridSize(size)
            self.gridSizeChanged.emit(size)

    def itemsPerRow(self):
        return self._items_per_row

    def calculateGridSize(self):
        viewport_width = (
            self.viewport().width()
            - self.contentsMargins().left()
            - self.contentsMargins().right()
        )
        
        # Use cached value if viewport width hasn't changed significantly
        if abs(viewport_width - self._cached_viewport_width) < 10 and not self._cached_grid_size.isEmpty():
            return self._cached_grid_size
            
        width = math.floor(viewport_width / self._items_per_row)
        width = max(width * 0.99, 200)  # Minimum width to prevent too small items
        height = math.floor(width * self._item_aspect_ratio)
        
        grid_size = QtCore.QSize(int(width), int(height))
        
        # Cache the calculated values
        self._cached_grid_size = grid_size
        self._cached_viewport_width = viewport_width
        
        return grid_size

    def _updateGridSize(self):
        """Internal method to update grid size and layout"""
        size = self.calculateGridSize()
        self.setGridSize(size)
        # Use timer to batch layout updates
        QtCore.QTimer.singleShot(0, self.doItemsLayout)

    def _getVisibleRange(self):
        """Get range of visible items for lazy loading"""
        if not self.model():
            return (0, 0)
            
        viewport_rect = self.viewport().rect()
        top_index = self.indexAt(viewport_rect.topLeft())
        bottom_index = self.indexAt(viewport_rect.bottomLeft())
        
        if not top_index.isValid():
            top_index = self.model().index(0, 0)
        if not bottom_index.isValid():
            bottom_index = self.model().index(self.model().rowCount() - 1, 0)
            
        # Add buffer for smooth scrolling
        buffer = self._items_per_row * 2
        start = max(0, top_index.row() - buffer)
        end = min(self.model().rowCount(), bottom_index.row() + buffer)
        
        return (start, end)

    def _onScrollChanged(self):
        """Handle scroll changes with debouncing"""
        self._viewport_timer.stop()
        self._viewport_timer.start(50)  # Debounce scroll events

    def _updateVisibleItems(self):
        """Update only visible items for better performance"""
        visible_range = self._getVisibleRange()
        
        # Only update if range changed significantly
        if visible_range != self._last_visible_range:
            self._last_visible_range = visible_range
            
            # Update viewport to show current visible items
            start_index = self.model().index(visible_range[0], 0) if self.model() else QtCore.QModelIndex()
            end_index = self.model().index(visible_range[1], 0) if self.model() else QtCore.QModelIndex()
            
            if start_index.isValid() and end_index.isValid():
                # Use minimal update for visible region
                self.viewport().update(self.visualRect(start_index).united(self.visualRect(end_index)))

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:
        # Only update if size change is significant
        if abs(e.size().width() - e.oldSize().width()) > 50:
            self._updateGridSize()
            
            # Update scroll step based on new grid size
            grid_size = self.gridSize()
            self.verticalScrollBar().setSingleStep(max(grid_size.height() // 5, 20))
            
            # Clear delegate caches on resize
            if hasattr(self._item_delegate, 'clearCaches'):
                self._item_delegate.clearCaches()
            
        return super().resizeEvent(e)

    def wheelEvent(self, e: QtGui.QWheelEvent) -> None:
        """Smooth scrolling with acceleration and performance optimization"""
        # Get the scroll delta
        delta = e.angleDelta().y()
        
        # Calculate scroll amount with acceleration for larger movements
        scroll_amount = delta // 8  # Standard wheel step
        if abs(delta) > 240:  # Fast scrolling
            scroll_amount *= 1.5
            
        # Apply smooth scrolling with performance optimization
        scrollbar = self.verticalScrollBar()
        current_value = scrollbar.value()
        new_value = max(0, min(scrollbar.maximum(), current_value - scroll_amount))
        
        # Use immediate scrolling for small deltas, animation for large ones
        if abs(scroll_amount) < 100:
            # Immediate scroll for small movements
            scrollbar.setValue(new_value)
        else:
            # Animate larger scrolls
            if hasattr(self, '_scroll_animation'):
                self._scroll_animation.stop()
                
            self._scroll_animation = QtCore.QPropertyAnimation(scrollbar, b"value")
            self._scroll_animation.setDuration(100)  # Faster animation
            self._scroll_animation.setStartValue(current_value)
            self._scroll_animation.setEndValue(new_value)
            self._scroll_animation.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad)
            self._scroll_animation.start()
        
        e.accept()

    def startDrag(self, supportedActions):
        """Disable drag for better performance"""
        pass

    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
        """Optimized mouse press handling"""
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            index = self.indexAt(e.pos())
            if index.isValid():
                self.clicked.emit(index)
                # Immediate selection update
                self.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect)
        return super().mousePressEvent(e)

    def setModel(self, model):
        """Override setModel to set up lazy loading"""
        # Clear caches when model changes
        if hasattr(self._item_delegate, 'clearCaches'):
            self._item_delegate.clearCaches()
            
        super().setModel(model)
        
        # Reset visible range tracking
        self._last_visible_range = (0, 0)
        self._visible_items_cache.clear()

    def paintEvent(self, e: QtGui.QPaintEvent) -> None:
        """Optimized paint event with viewport culling"""
        # Only paint if widget is visible
        if not self.isVisible():
            return
            
        # Optimize painting for visible region only
        painter = QtGui.QPainter(self.viewport())
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)  # Disable for performance
        
        # Set clip region to update region only
        painter.setClipRegion(e.region())
        
        # Call parent paint with optimizations
        super().paintEvent(e)


class ModelGalleryView(QtWidgets.QWidget):
    modelIndexChanged = QtCore.Signal(QtCore.QModelIndex)
    contextMenuRequested = QtCore.Signal(QtCore.QModelIndex)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._list_view = ImageGalleryListView()

        # Add subtle styling to the gallery container
        self.setStyleSheet("""
            ModelGalleryView {
                background: #2A2A3A;
                border: 1px solid #45475A;
                border-radius: 12px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._list_view)

        self._list_view.clicked.connect(self.modelIndexChanged)
        self._list_view.customContextMenuRequested.connect(self.onContextMenuRequested)
        
        # Performance monitoring
        self._update_timer = QtCore.QTimer()
        self._update_timer.setSingleShot(True)
        self._pending_model_updates = False

    def onContextMenuRequested(self, pos):
        index = self._list_view.indexAt(pos)
        self.contextMenuRequested.emit(index)

    def setModel(self, model):
        """Set model with optimizations and batched updates"""
        # Temporarily disable updates during model setting for better performance
        self.setUpdatesEnabled(False)
        self._list_view.setUpdatesEnabled(False)
        
        # Clear any pending updates
        self._update_timer.stop()
        
        try:
            self._list_view.setModel(model)
            
            # Connect model signals for smart updates
            if model:
                if hasattr(model, 'dataChanged'):
                    model.dataChanged.connect(self._onModelDataChanged)
                if hasattr(model, 'modelReset'):
                    model.modelReset.connect(self._onModelReset)
        finally:
            # Re-enable updates
            self._list_view.setUpdatesEnabled(True)
            self.setUpdatesEnabled(True)
            
            # Force a single comprehensive update
            QtCore.QTimer.singleShot(0, self._forceUpdate)

    def _onModelDataChanged(self, topLeft, bottomRight, roles=None):
        """Handle model data changes with batching"""
        self._pending_model_updates = True
        if not self._update_timer.isActive():
            self._update_timer.start(100)  # Batch updates every 100ms

    def _onModelReset(self):
        """Handle model reset"""
        # Clear caches and force update
        if hasattr(self._list_view._item_delegate, 'clearCaches'):
            self._list_view._item_delegate.clearCaches()
        self._forceUpdate()

    def _forceUpdate(self):
        """Force a comprehensive update"""
        if self.isVisible():
            self._list_view.viewport().update()
            self._pending_model_updates = False

    def scrollToTop(self):
        """Smooth scroll to top"""
        scrollbar = self._list_view.verticalScrollBar()
        if hasattr(self, '_scroll_to_top_animation'):
            self._scroll_to_top_animation.stop()
            
        self._scroll_to_top_animation = QtCore.QPropertyAnimation(scrollbar, b"value")
        self._scroll_to_top_animation.setDuration(300)
        self._scroll_to_top_animation.setStartValue(scrollbar.value())
        self._scroll_to_top_animation.setEndValue(0)
        self._scroll_to_top_animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._scroll_to_top_animation.start()

    def clearSelection(self):
        """Clear selection with optimized updates"""
        self._list_view.clearSelection()

    def updateItemsPerRow(self, count):
        """Update items per row with validation"""
        if 1 <= count <= 10:  # Reasonable limits
            self._list_view.setItemsPerRow(count)

    def clearCaches(self):
        """Clear all caches to free memory"""
        if hasattr(self._list_view._item_delegate, 'clearCaches'):
            self._list_view._item_delegate.clearCaches()

    def setVisible(self, visible):
        """Override setVisible to optimize performance"""
        was_visible = self.isVisible()
        super().setVisible(visible)
        
        # Clear caches when hiding to free memory
        if was_visible and not visible:
            self.clearCaches()
        elif not was_visible and visible:
            # Force update when becoming visible
            QtCore.QTimer.singleShot(0, self._forceUpdate)
