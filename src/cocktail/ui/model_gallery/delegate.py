from PySide6 import QtWidgets, QtCore, QtGui
from cocktail.ui.model_gallery.model import ModelGalleryProxyModel
from cocktail.ui.model_info.view import CreatorInfoView
import cocktail.resources
import threading
import weakref
from typing import Dict, Optional


class AsyncImageLoader(QtCore.QObject):
    """Asynchronous image loader to prevent UI freezing"""
    imageReady = QtCore.Signal(object, QtGui.QImage)  # (cache_key, image)
    
    def __init__(self):
        super().__init__()
        self._worker_thread = QtCore.QThread()
        self._worker = ImageWorker()
        self._worker.moveToThread(self._worker_thread)
        
        # Connect signals
        self._worker.imageLoaded.connect(self.imageReady.emit)
        
        # Start worker thread
        self._worker_thread.start()
    
    def loadImage(self, cache_key: str, image_data: QtGui.QImage, target_size: QtCore.QSize):
        """Load and scale image asynchronously"""
        QtCore.QMetaObject.invokeMethod(
            self._worker,
            "processImage",
            QtCore.Qt.ConnectionType.QueuedConnection,
            QtCore.Q_ARG(str, cache_key),
            QtCore.Q_ARG(QtGui.QImage, image_data),
            QtCore.Q_ARG(QtCore.QSize, target_size)
        )
    
    def __del__(self):
        if hasattr(self, '_worker_thread'):
            self._worker_thread.quit()
            self._worker_thread.wait()


class ImageWorker(QtCore.QObject):
    """Worker for image processing in background thread"""
    imageLoaded = QtCore.Signal(str, QtGui.QImage)  # (cache_key, processed_image)
    
    @QtCore.Slot(str, QtGui.QImage, QtCore.QSize)
    def processImage(self, cache_key: str, image: QtGui.QImage, target_size: QtCore.QSize):
        """Process image in background thread"""
        try:
            if image.isNull():
                self.imageLoaded.emit(cache_key, image)
                return
                
            # Scale image with appropriate quality
            if target_size.width() > 400 or target_size.height() > 400:
                # Use smooth transformation for larger images
                scaled = image.scaled(
                    target_size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation
                )
            else:
                # Use fast transformation for smaller images
                scaled = image.scaled(
                    target_size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.FastTransformation
                )
            
            self.imageLoaded.emit(cache_key, scaled)
        except Exception:
            # Return original image on error
            self.imageLoaded.emit(cache_key, image)


class InfoLabel(QtWidgets.QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setWordWrap(True)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setProperty("class", "model-info-label")


class ItemRenderWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self._image = QtGui.QImage()
        self._scaled_image_cache = None  # Cache for scaled images
        self._cache_size = QtCore.QSize()
        self._error_image = (
            cocktail.resources.icon("error.png").pixmap(512, 512).toImage()
        )
        
        # Async loading state
        self._loading_placeholder = None
        self._is_loading = False

        self.selected = False

        self.model_name_label = InfoLabel("name")
        self.model_type_label = InfoLabel("type")

        info_layout = QtWidgets.QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.addWidget(self.model_type_label)
        info_layout.insertStretch(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addStretch(1)
        layout.addLayout(info_layout)
        layout.addWidget(self.model_name_label)

    def resize(self, size):
        super().resize(size)
        margin = size.width() * 0.025
        self.layout().setContentsMargins(margin * 2, margin * 2, margin * 2, margin * 2)
        # Clear cache when size changes
        if self._cache_size != size:
            self._scaled_image_cache = None
            self._cache_size = size

    def setModelName(self, name):
        self.model_name_label.setText(name)

    def setModelType(self, type):
        self.model_type_label.setText(type)

    def setImage(self, image):
        if self._image != image:
            self._image = image
            self._scaled_image_cache = None  # Clear cache when image changes
            self._is_loading = False

    def setLoadingState(self, loading: bool):
        """Set loading state for async image loading"""
        self._is_loading = loading
        if loading and self._loading_placeholder is None:
            # Create loading placeholder
            self._loading_placeholder = QtGui.QImage(200, 200, QtGui.QImage.Format.Format_ARGB32)
            self._loading_placeholder.fill(QtGui.QColor("#45475A"))

    def getImageAspectRatio(self, image):
        if image.isNull():
            return 1.0
        if image.width() == 0 or image.height() == 0:
            return 1.0
        return image.width() / image.height()

    def _getDisplayImage(self, draw_rect):
        """Get image to display (cached, loading, or error)"""
        if self._is_loading and self._loading_placeholder:
            return self._loading_placeholder
            
        if self._scaled_image_cache is not None:
            return self._scaled_image_cache

        if self._image is None or self._image.isNull():
            desired_width = self.width() * 0.5
            desired_height = desired_width / self.getImageAspectRatio(self._error_image)
            return self._error_image.scaled(
                int(desired_width),
                int(desired_height),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.FastTransformation,
            )
        
        # Return original image if no cache available
        return self._image

    def setScaledImage(self, scaled_image: QtGui.QImage):
        """Set cached scaled image from async loader"""
        self._scaled_image_cache = scaled_image
        self._is_loading = False
        self.update()  # Trigger repaint

    def paintEvent(self, e: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        
        # Use a more sophisticated background color
        bg_color = QtGui.QColor("#313244")  # Match our new theme
        painter.setBrush(bg_color)

        margin = max(1, self.rect().width() * 0.025)  # Ensure minimum margin

        draw_rect = self.rect().adjusted(margin, margin, -margin, -margin)

        # Create rounded rectangle path
        clip_path = QtGui.QPainterPath()
        clip_path.addRoundedRect(draw_rect, margin, margin)
        painter.setClipPath(clip_path)

        # Fill background
        painter.drawPath(clip_path)

        # Draw image (cached, loading, or error)
        display_image = self._getDisplayImage(draw_rect)
        image_rect = display_image.rect()
        image_rect.moveCenter(draw_rect.center())
        
        if self._image is None or self._image.isNull() or self._is_loading:
            # Center placeholder/error image
            pass
        else:
            image_rect.moveTop(draw_rect.top())

        painter.drawImage(image_rect, display_image)

        # Draw selection border with modern styling
        if self.selected:
            # Gradient border for selected state
            gradient = QtGui.QLinearGradient(draw_rect.topLeft(), draw_rect.bottomRight())
            gradient.setColorAt(0, QtGui.QColor("#89B4FA"))
            gradient.setColorAt(1, QtGui.QColor("#74C7EC"))
            pen = QtGui.QPen(QtGui.QBrush(gradient), 3)
        else:
            # Subtle border for normal state
            pen = QtGui.QPen(QtGui.QColor("#45475A"), 1)

        painter.setBrush(QtGui.Qt.BrushStyle.NoBrush)
        painter.setPen(pen)
        painter.drawRoundedRect(draw_rect, margin, margin)

        painter.end()
        super().paintEvent(e)


class ModelGalleryItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._item_size = QtCore.QSize(450, 650)
        self._widget = ItemRenderWidget()
        self._pixmap_cache: Dict[str, QtGui.QPixmap] = {}  # Cache for rendered widgets
        self._image_cache: Dict[str, QtGui.QImage] = {}    # Cache for processed images
        self._max_cache_size = 200  # Increased cache size
        self._max_image_cache_size = 100
        
        # Async image loader
        self._image_loader = AsyncImageLoader()
        self._image_loader.imageReady.connect(self._onImageReady)
        
        # Track pending loads
        self._pending_loads: Dict[str, weakref.ref] = {}

    def setItemSize(self, size):
        self._item_size = size
        self._widget.resize(size)
        # Clear caches when size changes
        self._pixmap_cache.clear()
        self._image_cache.clear()

    def sizeHint(self, *_):
        return self._item_size

    def _getCacheKey(self, index, selected):
        """Generate cache key for the item"""
        name = index.data(ModelGalleryProxyModel.NameRole) or ""
        model_type = index.data(ModelGalleryProxyModel.TypeRole) or ""
        # Use image hash or pointer for unique identification
        image = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        image_key = hash(image.cacheKey()) if image and not image.isNull() else "no_image"
        return f"{name}_{model_type}_{image_key}_{selected}_{self._item_size.width()}_{self._item_size.height()}"

    def _getImageCacheKey(self, index):
        """Generate cache key for processed images"""
        image = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        image_key = hash(image.cacheKey()) if image and not image.isNull() else "no_image"
        return f"img_{image_key}_{self._item_size.width()}_{self._item_size.height()}"

    @QtCore.Slot(str, QtGui.QImage)
    def _onImageReady(self, cache_key: str, processed_image: QtGui.QImage):
        """Handle async image processing completion"""
        # Store in image cache
        if len(self._image_cache) < self._max_image_cache_size:
            self._image_cache[cache_key] = processed_image
        
        # Clear related pixmap cache entries to force re-render
        keys_to_remove = [k for k in self._pixmap_cache.keys() if cache_key.split('_', 1)[1] in k]
        for key in keys_to_remove:
            del self._pixmap_cache[key]
        
        # Remove from pending loads
        if cache_key in self._pending_loads:
            del self._pending_loads[cache_key]

    def paint(self, painter, option, index):
        # Check pixmap cache first
        cache_key = self._getCacheKey(index, bool(option.state & QtWidgets.QStyle.State_Selected))
        
        if cache_key in self._pixmap_cache:
            pixmap = self._pixmap_cache[cache_key]
            painter.drawPixmap(option.rect, pixmap)
            return

        # Set up widget data
        self._widget.setModelName(index.data(ModelGalleryProxyModel.NameRole))
        self._widget.setModelType(index.data(ModelGalleryProxyModel.TypeRole))
        
        # Handle image loading
        image = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        image_cache_key = self._getImageCacheKey(index)
        
        if image_cache_key in self._image_cache:
            # Use cached processed image
            self._widget.setImage(self._image_cache[image_cache_key])
            self._widget.setLoadingState(False)
        elif image and not image.isNull() and image_cache_key not in self._pending_loads:
            # Start async loading
            self._widget.setImage(image)
            self._widget.setLoadingState(True)
            self._pending_loads[image_cache_key] = weakref.ref(self._widget)
            
            # Calculate target size for scaling
            height = self._item_size.height()
            aspect_ratio = image.width() / image.height() if image.height() > 0 else 1.0
            width = height * aspect_ratio
            if width < self._item_size.width():
                width = self._item_size.width()
                height = width / aspect_ratio
            
            target_size = QtCore.QSize(int(width), int(height))
            self._image_loader.loadImage(image_cache_key, image, target_size)
        else:
            # Use original image or error placeholder
            self._widget.setImage(image)
            self._widget.setLoadingState(False)
        
        self._widget.selected = bool(option.state & QtWidgets.QStyle.State_Selected)
        self._widget.setGeometry(option.rect)

        painter.save()
        try:
            # Create high-quality pixmap
            pixmap = QtGui.QPixmap(self._widget.size())
            pixmap.fill(QtCore.Qt.GlobalColor.transparent)
            self._widget.render(pixmap, QtCore.QPoint(), QtGui.QRegion(), 
                              QtWidgets.QWidget.RenderFlag.DrawChildren)
            
            # Cache management with LRU-like behavior
            if len(self._pixmap_cache) >= self._max_cache_size:
                # Remove random entries to make room (simplified LRU)
                keys_to_remove = list(self._pixmap_cache.keys())[:20]
                for key in keys_to_remove:
                    del self._pixmap_cache[key]
            
            self._pixmap_cache[cache_key] = pixmap
            painter.drawPixmap(option.rect, pixmap)
        finally:
            painter.restore()

    def clearCaches(self):
        """Clear all caches to free memory"""
        self._pixmap_cache.clear()
        self._image_cache.clear()
        self._pending_loads.clear()
