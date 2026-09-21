
import io
import json
import os
import sys
import zipfile

import numpy as np
from PIL import Image

from PyQt6.QtCore import Qt, QSize, QTimer, QSettings
from PyQt6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QIcon,
    QRadialGradient,
    QGuiApplication,
    QImageReader,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QToolBar,
    QWidget,
    QLineEdit,
    QToolButton,
)

from layer import Layer, LayerPreviewItem

APP_VERSION = (0, 1)

if sys.platform == "win32":
    import ctypes
    myappid = f'keyclap.kpanorama.version.{"".join(str(n) for n in APP_VERSION)}'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# ============================================================
# PIL -> QImage
# ============================================================

def pil_to_qimage(img):
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    data = img.tobytes("raw", "RGBA")
    qimg = QImage(
        data,
        img.width,
        img.height,
        img.width * 4,
        QImage.Format.Format_RGBA8888,
    )

    return qimg.copy()


# ============================================================
# Строка слоя
# ============================================================

class LayerRowWidget(QWidget):
    def __init__(self, window, layer, item):
        super().__init__()

        self.window = window
        self.layer = layer
        self.item = item

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        self.eye_button = QPushButton()
        self.eye_button.setFixedSize(24, 24)
        self.eye_button.setIconSize(QSize(20, 20))
        self.eye_button.setFlat(True)
        self.eye_button.clicked.connect(
            lambda: self.window.toggle_layer_visibility(
                self.window.layers.index(self.layer)
            )
        )

        # Обычное отображение имени
        self.name_label = QLabel(layer.name)
        self.name_label.setSizePolicy(
            self.name_label.sizePolicy().Policy.Expanding,
            self.name_label.sizePolicy().Policy.Preferred,
        )

        # Поле для переименования
        self.name_edit = QLineEdit(layer.name)
        self.name_edit.setSizePolicy(
            self.name_edit.sizePolicy().Policy.Expanding,
            self.name_edit.sizePolicy().Policy.Preferred,
        )
        self.name_edit.setVisible(False)
        self.name_edit.returnPressed.connect(self.finish_rename)

        self.copy_button = QPushButton()
        self.copy_button.setFixedSize(24, 24)
        self.copy_button.setIcon(QIcon("icons/copy_coordinates.svg"))
        self.copy_button.setIconSize(QSize(20, 20))
        self.copy_button.setFlat(True)
        self.copy_button.setToolTip("Copy layer coordinates")
        self.copy_button.clicked.connect(self.copy_coordinates)

        self.save_button = QPushButton()
        self.save_button.setFixedSize(24, 24)
        self.save_button.setIcon(QIcon("icons/save_layer.svg"))
        self.save_button.setIconSize(QSize(20, 20))
        self.save_button.setFlat(True)
        self.save_button.setToolTip("Save layer")
        self.save_button.clicked.connect(self.save_layer)

        layout.addWidget(self.eye_button)
        layout.addSpacing(2)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.name_edit, 1)
        layout.addWidget(self.copy_button)
        layout.addWidget(self.save_button)

        self.update_appearance()

    def update_appearance(self):
        if self.layer.visible:
            self.eye_button.setIcon(
                QIcon("icons/eye_show.svg")
            )
            self.name_label.setStyleSheet(
                "color: white;"
            )
        else:
            self.eye_button.setIcon(
                QIcon("icons/eye_hide.svg")
            )
            self.name_label.setStyleSheet(
                "color: #777;"
            )

        self.save_button.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: #333333;
                border-radius: 4px;
            }
            """
        )

        self.copy_button.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: #333333;
                border-radius: 4px;
            }
            """
        )

        self.name_edit.setStyleSheet(
            """
            QLineEdit {
                background: #2b2b2b;
                color: white;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 1px 4px;
            }
            QLineEdit:focus {
                border: 1px solid #777777;
            }
            """
        )

    def start_rename(self):
        self.name_edit.setText(self.layer.name)

        self.name_label.setVisible(False)
        self.name_edit.setVisible(True)

        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def finish_rename(self):
        name = self.name_edit.text().strip()

        if not name:
            name = self.layer.name

        self.layer.name = name
        self.name_label.setText(name)

        self.name_edit.setVisible(False)
        self.name_label.setVisible(True)

        self.window.update_window_title()

        if hasattr(self.window, "update_project_stats"):
            self.window.update_project_stats()

    def cancel_rename(self):
        self.name_edit.setText(self.layer.name)

        self.name_edit.setVisible(False)
        self.name_label.setVisible(True)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.cancel_rename()
            e.accept()
            return

        super().keyPressEvent(e)

    def copy_coordinates(self):
        x = int(self.layer.x)
        y = int(self.layer.y)

        bounds = self.layer.visible_bounds()

        if bounds:
            x, y, width, height = bounds
            text = f"{x}, {y}"
        else:
            text = f"{self.layer.x}, {self.layer.y}"

        QApplication.clipboard().setText(text)

        self.window.status.setText(f"Coordinates copied: ({text})")

    def save_layer(self):
        self.window.save_layer_to_project_folder(
            self.layer
        )


# ============================================================
# Список слоёв
# ============================================================

class LayerListWidget(QListWidget):
    def __init__(self, window):
        super().__init__()

        self.window = window


# ============================================================
# Canvas
# ============================================================

class CanvasView(QGraphicsView):
    def __init__(self, window):
        super().__init__()

        self.window = window

        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        self.painting = False
        self.ctrl_brush = False
        self.stroke_layer = None
        self.stroke_patches = []
        self.stroke_alpha_start = None
        self.stroke_mask = None

        self.cursor_pos = None

        self.grabbing = False
        self.grab_last_pos = None

        # F + движение мыши
        self.resizing_brush = False

        self.brush_resize_start_x = 0
        self.brush_resize_last_x = 0
        self.brush_resize_start_size = 0

        self.brush_hardness_start_y = 0
        self.brush_hardness_start_value = 50.0

        self.adjusting_brush_opacity = False

        self.brush_opacity_start_y = 0
        self.brush_opacity_start_x = 0
        self.brush_strength_start_value = 100

        self.brush_mask = None
        self.brush_mask_key = None


    # ========================================================
    # Drag & Drop
    # ========================================================

    def dragEnterEvent(self, e):
        if not e.mimeData().hasUrls():
            e.ignore()
            return

        files = [
            u.toLocalFile()
            for u in e.mimeData().urls()
            if u.isLocalFile()
        ]

        valid_files = [
            path
            for path in files
            if (
                path.lower().endswith(".kpp")
                or path.lower().endswith((
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp",
                    ".bmp",
                    ".tif",
                    ".tiff",
                ))
            )
        ]

        if valid_files:
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if not e.mimeData().hasUrls():
            e.ignore()
            return

        files = [
            u.toLocalFile()
            for u in e.mimeData().urls()
            if u.isLocalFile()
        ]

        if any(
            path.lower().endswith(".kpp")
            or path.lower().endswith((
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
                ".bmp",
                ".tif",
                ".tiff",
            ))
            for path in files
        ):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        files = [
            u.toLocalFile()
            for u in e.mimeData().urls()
            if u.isLocalFile()
        ]

        for path in files:
            if not os.path.isfile(path):
                continue

            # --------------------------------------------
            # .kpp = открыть проект
            # --------------------------------------------

            if path.lower().endswith(".kpp"):
                self.window.load_project_from_path(path)

            # --------------------------------------------
            # Изображения = добавить как слой
            # --------------------------------------------

            else:
                self.window.add_image(path)

        e.acceptProposedAction()

    # ========================================================
    # Zoom
    # ========================================================

    def wheelEvent(self, e):
        old_pos = self.mapToScene(e.position().toPoint())

        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

        new_pos = self.mapToScene(e.position().toPoint())
        delta = new_pos - old_pos

        self.translate(delta.x(), delta.y())

        self.window.update_zoom_status()
        self.viewport().update()

        e.accept()


    # ========================================================
    # Mouse move
    # ========================================================

    def mouseMoveEvent(self, e):
        self.cursor_pos = e.position()
        self.viewport().update()

        # ----------------------------------------------------
        # F + движение = размер / жёсткость кисти
        # ----------------------------------------------------

        if self.resizing_brush:

            # ====================================================
            # Shift + F = сила кисти
            # ====================================================

            if self.adjusting_brush_opacity:
                delta_x = (
                    e.position().x()
                    - self.brush_opacity_start_x
                )

                delta_y = (
                    self.brush_opacity_start_y
                    - e.position().y()
                )

                delta = delta_x + delta_y

                new_strength = (
                    self.brush_strength_start_value
                    + delta * 0.5
                )

                new_strength = max(
                    1,
                    min(100, int(new_strength)),
                )

                self.window.set_brush_opacity(
                    new_strength
                )

                self.viewport().update()
                return

            # ====================================================
            # Обычный F
            # ====================================================

            delta_x = (
                e.position().x()
                - self.brush_resize_last_x
            )

            if delta_x != 0:
                current_size = (
                    self.window.brush_size
                )

                scale = max(
                    1.0,
                    current_size / 200.0,
                )

                new_size = max(
                    1,
                    int(
                        current_size
                        + delta_x * scale
                    ),
                )

                self.window.set_brush_size(
                    new_size
                )

                self.brush_resize_last_x = (
                    e.position().x()
                )

            delta_y = (
                self.brush_hardness_start_y
                - e.position().y()
            )

            new_hardness = (
                self.brush_hardness_start_value
                + delta_y * 0.5
            )

            new_hardness = max(
                0.0,
                min(100.0, new_hardness),
            )

            self.window.set_brush_hardness(
                new_hardness
            )

            self.viewport().update()
            return

        # ----------------------------------------------------
        # СКМ = Grab
        # ----------------------------------------------------

        if (
            self.grabbing
            and self.grab_last_pos is not None
        ):
            delta = (
                e.position()
                - self.grab_last_pos
            )

            self.grab_last_pos = e.position()

            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value()
                - int(delta.x())
            )

            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value()
                - int(delta.y())
            )

            return

        # ----------------------------------------------------
        # ЛКМ = кисть
        # ----------------------------------------------------

        if (
            self.painting
            and self.stroke_layer
        ):
            self.paint_at(e.position())
            return

        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self.cursor_pos = None
        self.viewport().update()
        super().leaveEvent(e)

    # ========================================================
    # Brush cursor
    # ========================================================

    def paintEvent(self, e):
        super().paintEvent(e)

        p = QPainter(self.viewport())

        p.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        # ========================================================
        # Bounding boxes активного слоя
        # ========================================================

        layer = self.window.selected_layer()

        if (
            layer
            and layer.visible
            and layer is not self.window.layers[0]
        ):
            s = self.window.preview_scale

            p.setBrush(
                Qt.BrushStyle.NoBrush
            )

            # ====================================================
            # Original bounding box
            # Полный размер исходного изображения
            # ====================================================

            original_bbox = layer.original_visible_bbox()

            if original_bbox:
                x0, y0, x1, y1 = original_bbox

                original_x0 = (
                    layer.x + x0
                ) * s

                original_y0 = (
                    layer.y + y0
                ) * s

                original_x1 = (
                    layer.x + x1
                ) * s

                original_y1 = (
                    layer.y + y1
                ) * s

                p1 = self.mapFromScene(
                    original_x0,
                    original_y0,
                )

                p2 = self.mapFromScene(
                    original_x1,
                    original_y1,
                )

                p.setPen(
                    QPen(
                        QColor(255, 255, 0, 220),
                        1,
                        Qt.PenStyle.DashLine,
                    )
                )

                p.drawRect(
                    p1.x(),
                    p1.y(),
                    p2.x() - p1.x(),
                    p2.y() - p1.y(),
                )

            p1 = self.mapFromScene(
                original_x0,
                original_y0,
            )

            p2 = self.mapFromScene(
                original_x1,
                original_y1,
            )

            p.setPen(
                QPen(
                    QColor(255, 255, 0, 220),
                    1,
                    Qt.PenStyle.DashLine,
                )
            )

            p.drawRect(
                p1.x(),
                p1.y(),
                p2.x() - p1.x(),
                p2.y() - p1.y(),
            )

            # ====================================================
            # Visible bounding box
            # Существующий bbox по применённой маске
            # ====================================================

            bbox = layer.visible_bbox()

            if bbox:
                x0, y0, x1, y1 = bbox

                scene_x0 = (
                    layer.x + x0
                ) * s

                scene_y0 = (
                    layer.y + y0
                ) * s

                scene_x1 = (
                    layer.x + x1
                ) * s

                scene_y1 = (
                    layer.y + y1
                ) * s

                p1 = self.mapFromScene(
                    scene_x0,
                    scene_y0,
                )

                p2 = self.mapFromScene(
                    scene_x1,
                    scene_y1,
                )

                p.setPen(
                    QPen(
                        QColor(255, 255, 255, 220),
                        1,
                        Qt.PenStyle.DashLine,
                    )
                )

                p.drawRect(
                    p1.x(),
                    p1.y(),
                    p2.x() - p1.x(),
                    p2.y() - p1.y(),
                )

        # ========================================================
        # Курсор кисти
        # ========================================================

        if (
            self.cursor_pos is None
            or not self.window.brush_enabled
        ):
            p.end()
            return

        p.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        zoom = self.transform().m11()

        radius = (
            self.window.brush_size
            * self.window.preview_scale
            * zoom
        )

        if radius < 1:
            p.end()
            return

        if self.resizing_brush and self.adjusting_brush_opacity:
            opacity = self.window.brush_opacity
            strength = self.window.brush_strength

            # Чем выше сила, тем плотнее круг
            alpha = int(
                opacity * 255
            )

            p.setBrush(
                QColor(180, 180, 180, alpha)
            )

            p.setPen(
                QPen(QColor(230, 230, 230, 220), 2)
            )

            p.drawEllipse(
                self.cursor_pos,
                radius,
                radius,
            )

            p.setPen(
                QColor(255, 255, 255, 230)
            )

            p.drawText(
                round(self.cursor_pos.x() + radius + 10),
                round(self.cursor_pos.y() - 10),
                f"Strength {strength}%",
            )

            p.end()
            return

        # ========================================================
        # Preview мягкости при зажатой F
        # ========================================================

        if self.resizing_brush:
            hardness = (
                self.window.brush_hardness / 100.0
            )

            # Чем выше Hardness, тем уже мягкая зона.
            fade_start = hardness
            fade_start = max(
                0.0,
                min(0.99, fade_start),
            )

            # Радиальный градиент мягкости.
            gradient = QRadialGradient(
                self.cursor_pos,
                radius,
            )

            gradient.setColorAt(
                0.0,
                QColor(220, 220, 220, 75),
            )

            if fade_start > 0.0:
                gradient.setColorAt(
                    fade_start,
                    QColor(220, 220, 220, 75),
                )

            gradient.setColorAt(
                1.0,
                QColor(220, 220, 220, 0),
            )

            # Мягкая внутренняя часть.
            p.setPen(
                Qt.PenStyle.NoPen
            )

            p.setBrush(
                gradient
            )

            p.drawEllipse(
                self.cursor_pos,
                radius,
                radius,
            )

            # Старый контур размера кисти.
            p.setBrush(
                Qt.BrushStyle.NoBrush
            )

            p.setPen(
                QPen(
                    QColor(255, 255, 255, 230),
                    2,
                )
            )

            p.drawEllipse(
                self.cursor_pos,
                radius,
                radius,
            )

            # Текст.
            p.setPen(
                QColor(255, 255, 255, 230)
            )

            text = (
                f"Size {self.window.brush_size}px  "
                f"Hardness {self.window.brush_hardness:.0f}%"
            )

            p.drawText(
                round(
                    self.cursor_pos.x()
                    + radius
                    + 10
                ),
                round(
                    self.cursor_pos.y()
                    - 10
                ),
                text,
            )

        else:
            # ====================================================
            # Обычный курсор кисти
            # ====================================================

            p.setBrush(Qt.BrushStyle.NoBrush)

            p.setPen(
                QPen(
                    QColor(255, 255, 255, 230),
                    2,
                )
            )

            p.drawEllipse(
                self.cursor_pos,
                radius,
                radius,
            )

            p.setPen(
                QPen(
                    QColor(0, 0, 0, 180),
                    1,
                )
            )

            p.drawEllipse(
                self.cursor_pos,
                radius + 1,
                radius + 1,
            )

        p.end()

    # ========================================================
    # Keyboard
    # ========================================================

    def keyPressEvent(self, e):

        if (
            e.key() == Qt.Key.Key_V
            and e.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            clipboard = QGuiApplication.clipboard()
            mime = clipboard.mimeData()

            if mime.hasImage():
                print(mime)
                image = clipboard.image()

                if not image.isNull():
                    self.window.add_image_from_clipboard(image)

                    e.accept()
                    return

        if e.key() == Qt.Key.Key_Control:
            self.ctrl_brush = True
            e.accept()
            return

        if e.nativeScanCode() == 33 and not e.isAutoRepeat():

            local_pos = self.mapFromGlobal(
                self.cursor().pos()
            )

            self.resizing_brush = True
            self.brush_resize_last_x = local_pos.x()

            self.brush_resize_start_x = local_pos.x()
            self.brush_resize_start_size = (
                self.window.brush_size
            )

            self.brush_hardness_start_y = local_pos.y()
            self.brush_hardness_start_value = (
                self.window.brush_hardness
            )

            # ================================================
            # Shift + F = регулировка силы
            # ================================================

            self.adjusting_brush_opacity = bool(
                e.modifiers()
                & Qt.KeyboardModifier.ShiftModifier
            )

            if self.adjusting_brush_opacity:
                self.brush_opacity_start_x = local_pos.x()
                self.brush_opacity_start_y = local_pos.y()
                self.brush_strength_start_value = self.window.brush_strength
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)

            else:
                self.setCursor( Qt.CursorShape.SizeAllCursor)

            self.viewport().update()

            e.accept()
            return

        super().keyPressEvent(e)


    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key.Key_Control:
            self.ctrl_brush = False
            e.accept()
            return

        if e.nativeScanCode() == 33 and not e.isAutoRepeat():

            self.resizing_brush = False
            self.adjusting_brush_opacity = False

            if not self.grabbing:
                self.setCursor(
                    Qt.CursorShape.ArrowCursor
                )

            self.viewport().update()

            e.accept()
            return

        super().keyReleaseEvent(e)


    # ========================================================
    # Mouse press
    # ========================================================

    def mousePressEvent(self, e):
        # ----------------------------------------------------
        # СКМ = Grab
        # ----------------------------------------------------

        if e.button() == Qt.MouseButton.MiddleButton:
            self.grabbing = True
            self.grab_last_pos = e.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

            e.accept()
            return

        # ----------------------------------------------------
        # ЛКМ = кисть
        # ----------------------------------------------------

        if (
            e.button() == Qt.MouseButton.LeftButton
            and self.window.brush_enabled
        ):
            layer = self.window.selected_layer()

            if layer is self.window.layers[0]:
                return

            if layer:
                self.painting = True
                self.stroke_layer = layer
                self.stroke_patches = []

                # Снимок альфы в начале текущего мазка.
                self.stroke_alpha_start = np.asarray(
                    layer.alpha,
                    dtype=np.uint8,
                ).copy()

                # Накопительная маска текущего мазка.
                self.stroke_mask = np.zeros(
                    (
                        layer.alpha.height,
                        layer.alpha.width,
                    ),
                    dtype=np.float32,
                )

                self.paint_at(e.position())
                return

        super().mousePressEvent(e)

    # ========================================================
    # Mouse release
    # ========================================================

    def mouseReleaseEvent(self, e):
        # ----------------------------------------------------
        # СКМ = Grab
        # ----------------------------------------------------

        if e.button() == Qt.MouseButton.MiddleButton:
            self.grabbing = False
            self.grab_last_pos = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

            e.accept()
            return

        # ----------------------------------------------------
        # ЛКМ = завершение мазка
        # ----------------------------------------------------

        if e.button() == Qt.MouseButton.LeftButton:
            if self.painting:
                self.painting = False

                if (
                    self.stroke_layer
                    and self.stroke_patches
                ):
                    self.window.finish_brush_action(
                        self.stroke_layer,
                        self.stroke_patches,
                    )

                    self.stroke_layer.recalculate_content_bbox()

                self.stroke_layer = None
                self.stroke_patches = []

                self.stroke_alpha_start = None
                self.stroke_mask = None

                self.viewport().update()

                e.accept()
                return

        super().mouseReleaseEvent(e)


    # ========================================================
    # Painting
    # ========================================================

    def paint_at(self, pos):
        layer = self.stroke_layer

        if not layer:
            return

        if layer is self.window.layers[0]:
            return

        if self.stroke_alpha_start is None:
            return

        if self.stroke_mask is None:
            return

        scene_pos = self.mapToScene(
            int(pos.x()),
            int(pos.y()),
        )

        s = self.window.preview_scale

        cx = int(
            scene_pos.x() / s
        ) - layer.x

        cy = int(
            scene_pos.y() / s
        ) - layer.y

        r = self.window.brush_size

        if r <= 0:
            return

        x0 = max(
            0,
            cx - r,
        )

        y0 = max(
            0,
            cy - r,
        )

        x1 = min(
            layer.alpha.width,
            cx + r + 1,
        )

        y1 = min(
            layer.alpha.height,
            cy + r + 1,
        )

        if x1 <= x0 or y1 <= y0:
            return

        mask = self.get_brush_mask()

        mx0 = x0 - (cx - r)
        my0 = y0 - (cy - r)

        mx1 = mx0 + (x1 - x0)
        my1 = my0 + (y1 - y0)

        brush_strength = mask[
            my0:my1,
            mx0:mx1,
        ]

        stroke_mask = self.stroke_mask[
            y0:y1,
            x0:x1,
        ]

        old_mask = stroke_mask.copy()

        np.maximum(
            stroke_mask,
            brush_strength,
            out=stroke_mask,
        )

        if np.array_equal(
            old_mask,
            stroke_mask,
        ):
            return

        start_alpha = self.stroke_alpha_start[
            y0:y1,
            x0:x1,
        ].astype(
            np.float32,
            copy=False,
        )

        if not self.ctrl_brush:
            content = layer.content_alpha_array[
                y0:y1,
                x0:x1,
            ]

            result = (
                start_alpha
                + (
                    content
                    - start_alpha
                ) * stroke_mask
            )

            result = np.minimum(
                result,
                content,
            )

        else:
            result = (
                start_alpha
                * (1.0 - stroke_mask)
            )

        result = np.clip(
            result,
            0,
            255,
        ).astype(
            np.uint8
        )

        # ------------------------------------------------
        # Undo patch
        # ------------------------------------------------

        before_array = self.stroke_alpha_start[
            y0:y1,
            x0:x1,
        ]

        before = Image.fromarray(
            before_array.copy(),
            "L",
        )

        after = Image.fromarray(
            result,
            "L",
        )

        layer.alpha.paste(
            after,
            (x0, y0),
        )

        if not np.array_equal(
            before_array,
            result,
        ):
            self.stroke_patches.append(
                (
                    (x0, y0, x1, y1),
                    before,
                    after.copy(),
                )
            )

        layer.alpha_dirty = True

        self.window.update_layer_preview_region(
            layer,
            (x0, y0, x1, y1),
        )


    def get_brush_mask(self):
        r = self.window.brush_size
        hardness = self.window.brush_hardness
        opacity = self.window.brush_opacity

        key = (
            r,
            round(hardness, 3),
            round(opacity, 4),
        )

        if (
            self.brush_mask is not None
            and self.brush_mask_key == key
        ):
            return self.brush_mask

        size = r * 2 + 1

        yy, xx = np.ogrid[:size, :size]

        dx = xx - r
        dy = yy - r

        dist = np.sqrt(
            dx * dx + dy * dy
        )

        t = np.clip(
            dist / max(1, r),
            0.0,
            1.0,
        )

        hardness_value = hardness / 100.0
        hard_edge = hardness_value * 0.95

        if hard_edge >= 0.999:
            edge = np.clip(
                (1.0 - t) / 0.05,
                0.0,
                1.0,
            )

            strength = edge

        else:
            fade = np.clip(
                (t - hard_edge)
                / (1.0 - hard_edge),
                0.0,
                1.0,
            )

            fade = (
                fade * fade * (3.0 - 2.0 * fade)
            )

            strength = 1.0 - fade

        strength *= opacity

        self.brush_mask = strength.astype(
            np.float32
        )

        self.brush_mask_key = key

        return self.brush_mask


    def erase_alpha(self, layer, cx, cy):
        r = self.window.brush_size

        if r <= 0:
            return

        x0 = max(0, cx - r)
        y0 = max(0, cy - r)
        x1 = min(
            layer.alpha.width,
            cx + r + 1,
        )
        y1 = min(
            layer.alpha.height,
            cy + r + 1,
        )

        if x1 <= x0 or y1 <= y0:
            return

        mask = self.get_brush_mask()

        mx0 = x0 - (cx - r)
        my0 = y0 - (cy - r)

        mx1 = mx0 + (x1 - x0)
        my1 = my0 + (y1 - y0)

        strength = mask[
            my0:my1,
            mx0:mx1,
        ]

        arr = np.asarray(
            layer.alpha.crop(
                (x0, y0, x1, y1)
            ),
            dtype=np.float32,
        )

        if not self.ctrl_brush:
            content = np.asarray(
                layer.content_alpha.crop(
                    (x0, y0, x1, y1)
                ),
                dtype=np.float32,
            )

            arr += 255.0 * strength

            # Нельзя восстановить прозрачность
            # выше исходной альфа-маски.
            arr = np.minimum(
                arr,
                content,
            )

        else:
            arr *= 1.0 - strength

        arr = np.clip(
            arr,
            0,
            255,
        ).astype(np.uint8)

        layer.alpha.paste(
            Image.fromarray(arr, "L"),
            (x0, y0),
        )

# ============================================================
# Main Window
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.settings = QSettings("keyclap", "kPanorama")

        self.project_path = None
        self.saved_history = ()

        self.setWindowTitle("")
        self.setWindowIcon(QIcon("icons/icon.svg"))
        self.resize(1450, 900)

        self.layers = []

        self.canvas_width = 0
        self.canvas_height = 0

        self.max_preview_size = 1800
        self.preview_scale = 1.0

        self.brush_enabled = True
        self.brush_size = 100
        self.brush_strength = 100
        self.brush_opacity = 1.0
        self.brush_hardness = 50.0

        self.undo_stack = []
        self.redo_stack = []

        self.setup_ui()
        self.update_window_title()

        geometry = self.settings.value("geometry")

        if geometry:
            self.restoreGeometry(geometry)

    def fill_layer_alpha(self, layer, value):
        if not layer:
            return

        if layer is self.layers[0]:
            return

        before = layer.alpha.copy()

        bbox = layer.original_visible_bbox()

        if bbox is None:
            return

        x0, y0, x1, y1 = bbox

        # Заполняем только исходную область слоя.
        layer.alpha.paste(
            value,
            (x0, y0, x1, y1),
        )

        layer.alpha_dirty = True

        layer.recalculate_content_bbox()

        self.update_layer_preview(
            layer
        )

        self.view.viewport().update()

    def update_layer_preview_region(
        self,
        layer,
        rect,
    ):
        if not layer.item:
            return

        if not isinstance(
            layer.item,
            LayerPreviewItem,
        ):
            self.update_layer_preview(
                layer
            )
            return

        s = self.preview_scale

        x0, y0, x1, y1 = rect

        # Координаты изменяемой области
        # в preview-пикселях.

        px0 = max(
            0,
            int(np.floor(x0 * s)),
        )

        py0 = max(
            0,
            int(np.floor(y0 * s)),
        )

        px1 = min(
            layer.item.image.width(),
            int(np.ceil(x1 * s)),
        )

        py1 = min(
            layer.item.image.height(),
            int(np.ceil(y1 * s)),
        )

        if px1 <= px0 or py1 <= py0:
            return

        preview_w = px1 - px0
        preview_h = py1 - py0

        # ----------------------------------------
        # Берём только нужный участок исходника
        # ----------------------------------------

        src_x0 = max(
            0,
            int(np.floor(px0 / s)),
        )

        src_y0 = max(
            0,
            int(np.floor(py0 / s)),
        )

        src_x1 = min(
            layer.image.width,
            int(np.ceil(px1 / s)),
        )

        src_y1 = min(
            layer.image.height,
            int(np.ceil(py1 / s)),
        )

        if src_x1 <= src_x0 or src_y1 <= src_y0:
            return

        # RGB patch
        rgb = layer.image.crop(
            (
                src_x0,
                src_y0,
                src_x1,
                src_y1,
            )
        )

        # Alpha patch
        alpha = layer.alpha.crop(
            (
                src_x0,
                src_y0,
                src_x1,
                src_y1,
            )
        )

        rgb.putalpha(alpha)

        # ----------------------------------------
        # Очень важно:
        # patch должен иметь ровно preview-размер
        # ----------------------------------------

        if (
            rgb.width != preview_w
            or rgb.height != preview_h
        ):
            rgb = rgb.resize(
                (
                    preview_w,
                    preview_h,
                ),
                Image.Resampling.LANCZOS,
            )

        patch = pil_to_qimage(
            rgb
        )

        # ----------------------------------------
        # Меняем только маленький участок QImage
        # ----------------------------------------

        layer.item.update_region(
            patch,
            px0,
            py0,
        )

    def add_image_from_clipboard(self, qimage):
        if qimage.isNull():
            return

        try:
            qimage = qimage.convertToFormat(
                QImage.Format.Format_RGBA8888
            )

            width = qimage.width()
            height = qimage.height()

            ptr = qimage.bits()
            ptr.setsize(width * height * 4)

            arr = np.frombuffer(
                ptr,
                dtype=np.uint8,
            ).reshape(
                (height, width, 4)
            )

            pil_image = Image.fromarray(
                arr,
                "RGBA",
            )

            rgb = pil_image.convert("RGB")
            alpha = pil_image.getchannel("A")

            # ------------------------------------------------
            # Если проекта ещё нет — clipboard становится
            # первым (фоновым) изображением.
            # ------------------------------------------------

            if not self.layers:
                self.canvas_width = rgb.width
                self.canvas_height = rgb.height

                x = 0
                y = 0

            else:
                # --------------------------------------------
                # Новое изображение ставим по центру canvas.
                # --------------------------------------------

                x = int(
                    (self.canvas_width - rgb.width) / 2
                )

                y = int(
                    (self.canvas_height - rgb.height) / 2
                )

            # Уникальное имя
            base_name = "Clipboard"
            layer_name = base_name
            number = 2

            existing_names = {
                layer.name
                for layer in self.layers
            }

            while layer_name in existing_names:
                layer_name = f"{base_name} {number}"
                number += 1

            layer = Layer(
                layer_name,
                rgb,
                x,
                y,
                alpha,
            )

            index = len(self.layers)

            self.layers.append(layer)

            self.rebuild_scene()
            self.select_layer(index)
            self.update_project_stats()

            # ------------------------------------------------
            # Undo / Redo
            # ------------------------------------------------

            self.undo_stack.append({
                "type": "add",
                "index": index,
                "layer": layer,
            })

            self.redo_stack.clear()

            self.update_window_title()
            self.update_history_buttons()

            self.status.setText(
                f"Вставлено из clipboard: "
                f"{rgb.width} × {rgb.height}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка вставки",
                str(e),
            )
    # ========================================================
    # Project state
    # ========================================================

    def current_history(self):
        return tuple(id(action) for action in self.undo_stack)

    def has_unsaved_changes(self):
        return self.current_history() != self.saved_history

    def update_window_title(self):
        if self.project_path:
            filename = os.path.splitext(
                os.path.basename(self.project_path)
            )[0]
            full_path = os.path.abspath(self.project_path)

            title = (
                f"{filename} [{full_path}] - "
                f"kPanorama {".".join(str(n) for n in APP_VERSION)}"
            )
        else:
            title = f"Untitled - kPanorama {".".join(str(n) for n in APP_VERSION)}"

        if self.has_unsaved_changes():
            title = "* " + title

        self.setWindowTitle(title)

    def mark_project_saved(self):
        self.saved_history = self.current_history()
        self.update_window_title()

    def update_project_title(self):
        self.update_window_title()

    # ========================================================
    # Close
    # ========================================================

    def closeEvent(self, e):

        if not self.has_unsaved_changes():
            self.settings.setValue("geometry", self.saveGeometry())
            e.accept()
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Unsaved changes")
        msg.setText("The project has unsaved changes. Save them?")

        save_button = msg.addButton(
            "Save",
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard_button = msg.addButton(
            "Discard",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = msg.addButton(
            "Cancel",
            QMessageBox.ButtonRole.RejectRole,
        )

        msg.exec()
        clicked = msg.clickedButton()

        if clicked == save_button:
            self.settings.setValue("geometry", self.saveGeometry())
            if self.save_project():
                e.accept()
            else:
                e.ignore()

        elif clicked == discard_button:
            self.settings.setValue("geometry", self.saveGeometry())
            e.accept()

        elif clicked == cancel_button:
            e.ignore()

        else:
            e.ignore()


    # ========================================================
    # UI
    # ========================================================

    def setup_ui(self):

        def create_separator():
            separator = QWidget()
            separator.setFixedWidth(21)
            separator.setFixedHeight(20)
            separator.setStyleSheet(
                """
                QWidget {
                    background-color: transparent;
                    border-left: 1px solid #555;
                    margin-left: 10px;
                    margin-right: 10px;
                }
                """
            )

            return separator

        self.view = CanvasView(self)
        self.layer_list = LayerListWidget(self)
        self.layer_list.itemDoubleClicked.connect(
            self.start_layer_rename
        )
        self.layer_list.currentRowChanged.connect(self.layer_selected)
        self.layer_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.layer_list.customContextMenuRequested.connect(
            self.layer_context_menu
        )

        splitter = QSplitter()
        splitter.addWidget(self.view)
        splitter.addWidget(self.layer_list)
        splitter.setSizes([1150, 300])

        self.setCentralWidget(splitter)

        # ----------------------------------------------------
        # Toolbar
        # ----------------------------------------------------

        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        file_button = QToolButton()
        file_button.setText("File")
        file_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )

        file_menu = QMenu(self)

        # file_menu.addAction("New", self.new_project)
        file_menu.addAction("Open", self.load_project)
        file_menu.addSeparator()
        file_menu.addAction("Save", self.save_project)
        file_menu.addAction("Save As...", self.save_project_as)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        file_button.setMenu(file_menu)

        toolbar.addWidget(file_button)


        settings_button = QToolButton()
        settings_button.setText("Settings")
        settings_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )

        settings_menu = QMenu(self)

        settings_menu.addAction(
            "Register File Associations",
            self.register_file_associations,
        )

        settings_button.setMenu(settings_menu)

        toolbar.addWidget(settings_button)

        toolbar.addWidget(create_separator())


        # ----------------------------------------------------
        # Undo / Redo
        # ----------------------------------------------------

        toolbar.setIconSize(QSize(20, 20))

        self.undo_action = toolbar.addAction(
            QIcon("icons/undo.svg"),
            ""
        )
        self.undo_action.setToolTip("Undo")
        self.undo_action.triggered.connect(self.undo)

        self.redo_action = toolbar.addAction(
            QIcon("icons/redo.svg"),
            ""
        )
        self.redo_action.setToolTip("Redo")
        self.redo_action.triggered.connect(self.redo)

        toolbar.addWidget(create_separator())

        # ----------------------------------------------------
        # Кисть
        # ----------------------------------------------------

        slider_style = """
            QSlider {
                padding-left: 10px;
                padding-right: 10px;
            }

            QSlider::groove:horizontal {
                height: 6px;
                background: #292929;
                border-radius: 3px;
            }

            QSlider::sub-page:horizontal {
                background: #8a8a8a;
                border-radius: 3px;
                min-width: 6px;
            }

            QSlider::add-page:horizontal {
                background: #292929;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                width: 0px;
                height: 0px;
                margin: 0px;
                background: transparent;
                border: none;
            }
        """

        # ----------------------------------------------------
        # Strength
        # ----------------------------------------------------

        toolbar.addWidget(QLabel("Strength:"))

        self.brush_opacity_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.brush_opacity_slider.setRange(1, 100)
        self.brush_opacity_slider.setValue(
            self.brush_strength
        )
        self.brush_opacity_slider.setFixedWidth(110)
        self.brush_opacity_slider.setStyleSheet(
            slider_style
        )
        self.brush_opacity_slider.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.brush_opacity_slider.valueChanged.connect(
            self.set_brush_opacity
        )

        toolbar.addWidget(
            self.brush_opacity_slider
        )

        self.brush_opacity_label = QLabel(
            f"{self.brush_strength}%"
        )
        self.brush_opacity_label.setFixedWidth(40)

        toolbar.addWidget(
            self.brush_opacity_label
        )

        toolbar.addWidget(create_separator())


        # ----------------------------------------------------
        # Size
        # ----------------------------------------------------

        toolbar.addWidget(QLabel("Size:"))

        self.brush_size_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.brush_size_slider.setRange(1, 3000)
        self.brush_size_slider.setValue(
            self.brush_size
        )
        self.brush_size_slider.setFixedWidth(110)
        self.brush_size_slider.setStyleSheet(
            slider_style
        )
        self.brush_size_slider.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.brush_size_slider.valueChanged.connect(
            self.set_brush_size
        )

        toolbar.addWidget(
            self.brush_size_slider
        )

        self.brush_size_label = QLabel(
            f"{self.brush_size}px"
        )
        self.brush_size_label.setFixedWidth(50)

        toolbar.addWidget(
            self.brush_size_label
        )

        toolbar.addWidget(create_separator())


        # ----------------------------------------------------
        # Hardness
        # ----------------------------------------------------

        toolbar.addWidget(QLabel("Hardness:"))

        self.brush_hardness_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.brush_hardness_slider.setRange(0, 100)
        self.brush_hardness_slider.setValue(
            int(self.brush_hardness)
        )
        self.brush_hardness_slider.setFixedWidth(110)
        self.brush_hardness_slider.setStyleSheet(
            slider_style
        )
        self.brush_hardness_slider.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self.brush_hardness_slider.valueChanged.connect(
            self.set_brush_hardness
        )

        toolbar.addWidget(
            self.brush_hardness_slider
        )

        self.brush_hardness_label = QLabel(
            f"{self.brush_hardness:.0f}%"
        )
        self.brush_hardness_label.setFixedWidth(40)

        toolbar.addWidget(
            self.brush_hardness_label
        )

        # toolbar.addWidget(create_separator())


        self.status = QLabel("Drag and drop images")
        self.statusBar().addWidget(self.status)

        # ----------------------------------------------------
        # Статистика проекта
        # ----------------------------------------------------

        self.project_stats = QLabel()

        self.zoom_label = QLabel("Zoom: 100%")
        self.zoom_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.zoom_label.setStyleSheet(
            """
            QLabel {
                color: #999;
                padding: 0 8px;
            }
            """
        )

        self.statusBar().addPermanentWidget(
            self.zoom_label
        )

        self.project_stats.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.project_stats.setStyleSheet(
            """
            QLabel {
                color: #999;
                padding: 0 8px;
            }
            """
        )

        self.statusBar().addPermanentWidget(
            self.project_stats
        )

        self.update_project_stats()

        self.update_window_title()
        self.update_history_buttons()

    def update_project_stats(self):
        # Размер проекта
        if self.canvas_width and self.canvas_height:
            project_size = (
                f"{self.canvas_width} × {self.canvas_height}"
            )
        else:
            project_size = "-"

        # Количество слоёв
        layer_count = len(self.layers)

        # Количество видимых слоёв
        visible_count = sum(
            1 for layer in self.layers
            if layer.visible
        )

        # Информация о выбранном слое
        layer = self.selected_layer()

        if layer:
            layer_size = f"{layer.image.width} × {layer.image.height}"
            bounds = layer.visible_bounds()

            if bounds:
                x, y, w, h = bounds
                layer_position = f"({int(x)}, {int(y)})"

            else:
                layer_position = "(-, -)"

        else:
            layer_size = "-"
            layer_position = "-"

        # Размер файла проекта
        if self.project_path and os.path.isfile(
            self.project_path
        ):
            file_size = os.path.getsize(
                self.project_path
            )

            if file_size < 1024:
                file_size_text = f"{file_size} B"

            elif file_size < 1024 ** 2:
                file_size_text = (
                    f"{file_size / 1024:.1f} KB"
                )

            elif file_size < 1024 ** 3:
                file_size_text = (
                    f"{file_size / (1024 ** 2):.1f} MB"
                )

            else:
                file_size_text = (
                    f"{file_size / (1024 ** 3):.2f} GB"
                )
        else:
            file_size_text = "-"

        self.project_stats.setText(
            f"Canvas: {project_size}   |   "
            f"Active: {layer_size}   |   "
            f"Layers: {visible_count}/{layer_count}   |   "
            f"Pos: {layer_position}   |   "
            f"Size: {file_size_text}"
        )

    def start_layer_rename(self, item):
        widget = self.layer_list.itemWidget(item)

        if isinstance(widget, LayerRowWidget):
            widget.start_rename()

    def register_file_associations(self):
        from .association import register_kpp_file_association

        register_kpp_file_association()

        QMessageBox.information(
            self,
            "File Associations",
            ".kpp file association registered.",
        )

    # ========================================================
    # Zoom
    # ========================================================

    def update_zoom_status(self):
        zoom = self.view.transform().m11() * 100
        self.zoom_label.setText(f"Zoom: {zoom:.0f}%")

    # ========================================================
    # Brush
    # ========================================================

    def set_brush_size(self, value):
        value = max(1, min(3000, int(value)))

        self.brush_size = value

        # Обновляем ползунок, в том числе
        # когда размер меняется через F.
        if self.brush_size_slider.value() != value:
            self.brush_size_slider.setValue(value)

        # Обновляем число справа.
        self.brush_size_label.setText(
            f"{value}px"
        )

        self.view.viewport().update()

    def set_brush_opacity(self, value):
        value = max(1, min(100, int(value)))

        self.brush_strength = value

        # Strength 1..100 -> реальная сила 1..100%
        self.brush_opacity = value / 100.0

        if self.brush_opacity_slider.value() != value:
            self.brush_opacity_slider.setValue(value)

        self.brush_opacity_label.setText(
            f"{value}%"
        )

        self.view.viewport().update()

    def set_brush_hardness(self, value):
        value = max(
            0.0,
            min(100.0, float(value)),
        )

        self.brush_hardness = value

        # Обновляем ползунок при изменении через F.
        slider_value = int(round(value))

        if self.brush_hardness_slider.value() != slider_value:
            self.brush_hardness_slider.setValue(
                slider_value
            )

        # Обновляем число справа.
        self.brush_hardness_label.setText(
            f"{value:.0f}%"
        )

        self.view.viewport().update()

    # ========================================================
    # Layer list item widget
    # ========================================================

    def create_layer_list_item(self, layer):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, layer)
        item.setSizeHint(QSize(100, 34))

        self.layer_list.addItem(item)

        row_widget = LayerRowWidget(self, layer, item)

        layer.list_item = item
        layer.eye_button = row_widget.eye_button

        self.layer_list.setItemWidget(item, row_widget)

        return item

    # ========================================================
    # Layer reorder
    # ========================================================

    def reorder_layers_from_list(self):
        if not self.layers:
            return

        old_order = list(self.layers)
        selected = self.selected_layer()

        new_order = []

        for row in range(self.layer_list.count() - 1, -1, -1):
            item = self.layer_list.item(row)

            if item is None:
                continue

            layer = item.data(Qt.ItemDataRole.UserRole)

            if layer is not None:
                new_order.append(layer)

        if len(new_order) != len(old_order):
            return

        if set(new_order) != set(old_order):
            return

        # Фон всегда остаётся первым.
        background = old_order[0]

        if new_order[0] is not background:
            new_order.remove(background)
            new_order.insert(0, background)

        if new_order == old_order:
            return

        # В undo сохраняем только порядок ID,
        # а не сами Layer/QGraphicsPixmapItem.
        old_ids = [layer.id for layer in old_order]
        new_ids = [layer.id for layer in new_order]

        self.layers = new_order

        self.undo_stack.append({
            "type": "reorder",
            "old_ids": old_ids,
            "new_ids": new_ids,
        })
        self.redo_stack.clear()

        self.rebuild_scene()

        if selected in self.layers:
            self.select_layer(self.layers.index(selected))

        self.update_history_buttons()
        self.update_window_title()

    def restore_layer_order(self, ids):
        layers_by_id = {layer.id: layer for layer in self.layers}
        new_layers = []

        for layer_id in ids:
            layer = layers_by_id.get(layer_id)

            if layer is not None:
                new_layers.append(layer)

        if len(new_layers) != len(self.layers):
            return

        self.layers = new_layers
        self.rebuild_scene()

    # ========================================================
    # Layer context menu
    # ========================================================

    def layer_context_menu(self, pos):
        item = self.layer_list.itemAt(pos)

        if not item:
            return

        layer = item.data(Qt.ItemDataRole.UserRole)

        if layer not in self.layers:
            return

        index = self.layers.index(layer)
        row = self.layer_list.row(item)

        self.layer_list.setCurrentRow(row)

        menu = QMenu(self)

        save_action = menu.addAction("Save as PNG")
        replace_action = menu.addAction("Replace Contents")

        menu.addSeparator()

        fill_white_action = menu.addAction("Fill White")
        fill_black_action = menu.addAction("Fill Black")

        fill_white_action.triggered.connect(
            lambda checked=False, l=layer:
                self.fill_layer_alpha(l, 255)
        )

        fill_black_action.triggered.connect(
            lambda checked=False, l=layer:
                self.fill_layer_alpha(l, 0)
        )

        menu.addSeparator()

        delete_action = menu.addAction("Delete Layer")
        delete_action.setEnabled(index != 0)

        action = menu.exec(self.layer_list.mapToGlobal(pos))

        if action == save_action:
            self.export_layer()
        elif action == replace_action:
            self.replace_layer(index)
        elif action == delete_action:
            self.delete_layer()

    # ========================================================
    # Rename
    # ========================================================

    def rename_layer(self, item=None):
        if item is None:
            item = self.layer_list.currentItem()

        if not item:
            return

        layer = item.data(Qt.ItemDataRole.UserRole)

        if layer not in self.layers:
            return

        index = self.layers.index(layer)
        old_name = layer.name

        new_name, ok = QInputDialog.getText(
            self,
            "Переименовать слой",
            "Название:",
            text=old_name,
        )

        if not ok:
            return

        new_name = new_name.strip()

        if not new_name or new_name == old_name:
            return

        layer.name = new_name

        if layer.list_item:
            row_widget = self.layer_list.itemWidget(layer.list_item)

            if row_widget:
                row_widget.name_label.setText(new_name)

        self.undo_stack.append({
            "type": "rename",
            "index": index,
            "old_name": old_name,
            "new_name": new_name,
        })
        self.redo_stack.clear()

        self.update_history_buttons()
        self.update_window_title()

    # ========================================================
    # Visibility
    # ========================================================

    def toggle_layer_visibility(self, index):
        if not 0 <= index < len(self.layers):
            return

        layer = self.layers[index]
        old_visible = layer.visible
        layer.visible = not layer.visible

        if layer.item:
            layer.item.setVisible(layer.visible)

        if layer.list_item:
            row_widget = self.layer_list.itemWidget(layer.list_item)

            if row_widget:
                row_widget.update_appearance()

        self.undo_stack.append({
            "type": "visibility",
            "index": index,
            "old": old_visible,
            "new": layer.visible,
        })
        self.redo_stack.clear()

        self.update_history_buttons()
        self.update_window_title()
        self.update_project_stats()
        self.layer_list.viewport().update()

    # ========================================================
    # Open image
    # ========================================================

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Добавить изображение",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)",
        )

        if path:
            self.add_image(path)

    # ========================================================
    # Load image
    # ========================================================

    def load_image_file(self, path, background=False):
        img = Image.open(path)
        img.load()

        if "A" in img.getbands():
            rgba = img.convert("RGBA")
            rgb = rgba.convert("RGB")
            alpha = rgba.getchannel("A")
        else:
            rgb = img.convert("RGB")
            alpha = Image.new("L", rgb.size, 255)

        if background:
            canvas_size = (self.canvas_width, self.canvas_height)

            if rgb.size != canvas_size:
                rgb = rgb.resize(
                    canvas_size,
                    Image.Resampling.LANCZOS,
                )
                alpha = alpha.resize(
                    canvas_size,
                    Image.Resampling.LANCZOS,
                )

        return rgb, alpha

    # ========================================================
    # Add image
    # ========================================================

    def add_image(self, path):
        try:
            if not self.layers:
                img = Image.open(path)
                img.load()

                if "A" in img.getbands():
                    rgba = img.convert("RGBA")
                    rgb = rgba.convert("RGB")
                    alpha = rgba.getchannel("A")
                else:
                    rgb = img.convert("RGB")
                    alpha = Image.new("L", rgb.size, 255)

                self.canvas_width = rgb.width
                self.canvas_height = rgb.height
            else:
                rgb, alpha = self.load_image_file(
                    path,
                    background=False,
                )

            layer_name = os.path.splitext(
                os.path.basename(path)
            )[0]

            layer = Layer(
                layer_name,
                rgb,
                0,
                0,
                alpha,
            )

            index = len(self.layers)
            self.layers.append(layer)

            self.rebuild_scene()
            self.select_layer(index)
            self.update_project_stats()

            self.undo_stack.append({
                "type": "add",
                "index": index,
                "layer": layer,
            })
            self.redo_stack.clear()

            self.update_window_title()
            self.update_history_buttons()

            self.status.setText(
                f"Добавлено: {os.path.basename(path)} "
                f"({rgb.width} × {rgb.height})"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка загрузки",
                str(e),
            )

    # ========================================================
    # Replace layer
    # ========================================================

    def replace_layer(self, index):
        if not 0 <= index < len(self.layers):
            return

        old_layer = self.layers[index]

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pick a new image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)",
        )

        if not path:
            return

        try:
            rgb, alpha = self.load_image_file(
                path,
                background=index == 0,
            )

            layer_name = os.path.splitext(
                os.path.basename(path)
            )[0]

            new_layer = Layer(
                layer_name,
                rgb,
                old_layer.x,
                old_layer.y,
                alpha,
                old_layer.visible,
            )

            self.layers[index] = new_layer

            self.rebuild_scene()
            self.select_layer(index)
            self.update_project_stats()

            self.undo_stack.append({
                "type": "replace",
                "index": index,
                "old": old_layer,
                "new": new_layer,
            })
            self.redo_stack.clear()

            self.update_window_title()
            self.update_history_buttons()

            self.status.setText(
                f"Изображение заменено: {new_layer.name}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка замены",
                str(e),
            )

    # ========================================================
    # Preview scale
    # ========================================================

    def calculate_preview_scale(self):
        if not self.canvas_width or not self.canvas_height:
            return 1.0

        longest = max(self.canvas_width, self.canvas_height)
        return min(1.0, self.max_preview_size / longest)

    def create_preview(self, layer):
        s = self.preview_scale

        w = max(1, round(layer.image.width * s))
        h = max(1, round(layer.image.height * s))

        rgb = layer.image.resize(
            (w, h),
            Image.Resampling.LANCZOS,
        )
        alpha = layer.alpha.resize(
            (w, h),
            Image.Resampling.LANCZOS,
        )

        rgb.putalpha(alpha)
        return rgb

    def update_layer_preview(self, layer):
        if not layer.item:
            return

        preview = self.create_preview(
            layer
        )

        qimage = pil_to_qimage(
            preview
        )

        layer.preview_qimage = qimage

        if isinstance(
            layer.item,
            LayerPreviewItem,
        ):
            layer.item.set_image(
                qimage
            )
        else:
            item = LayerPreviewItem(
                qimage
            )

            item.setPos(
                layer.x * self.preview_scale,
                layer.y * self.preview_scale,
            )

            item.setVisible(
                layer.visible
            )

            layer.item = item

            self.view.scene().addItem(
                item
            )

    # ========================================================
    # Checkerboard background
    # ========================================================

    def create_checkerboard(self, width, height, cell_size=16):
        image = QImage(
            width,
            height,
            QImage.Format.Format_RGB32,
        )

        image.fill(QColor("#bdbdbd"))

        painter = QPainter(image)
        painter.setPen(Qt.PenStyle.NoPen)

        color1 = QColor("#525252")
        color2 = QColor("#8f8f8f")

        for y in range(0, height, cell_size):
            for x in range(0, width, cell_size):
                if ((x // cell_size) + (y // cell_size)) % 2:
                    painter.setBrush(color2)
                else:
                    painter.setBrush(color1)

                painter.drawRect(
                    x,
                    y,
                    min(cell_size, width - x),
                    min(cell_size, height - y),
                )

        painter.end()

        return image

    # ========================================================
    # Rebuild scene
    # ========================================================

    def rebuild_scene(self):
        scene = self.view.scene()
        scene.clear()

        self.preview_scale = self.calculate_preview_scale()

        # ----------------------------------------------------
        # Checkerboard background
        # ----------------------------------------------------

        if self.canvas_width and self.canvas_height:
            checker = self.create_checkerboard(
                max(1, round(
                    self.canvas_width * self.preview_scale
                )),
                max(1, round(
                    self.canvas_height * self.preview_scale
                )),
                cell_size=max(
                    1,
                    round(16 * self.preview_scale),
                ),
            )

            checker_item = QGraphicsPixmapItem(
                QPixmap.fromImage(checker)
            )

            checker_item.setZValue(-1000)

            scene.addItem(checker_item)

        # ----------------------------------------------------
        # Layers
        # ----------------------------------------------------

        for layer in self.layers:
            preview = self.create_preview(layer)

            layer.preview_qimage = pil_to_qimage(
                preview
            )

            item = LayerPreviewItem(
                layer.preview_qimage
            )

            item.setPos(
                layer.x * self.preview_scale,
                layer.y * self.preview_scale,
            )

            item.setVisible(
                layer.visible
            )

            layer.item = item

            self.view.scene().addItem(
                item
            )

        self.update_scene_rect()

        # ----------------------------------------------------
        # Перестраиваем список слоёв
        # ----------------------------------------------------

        self.layer_list.blockSignals(True)
        self.layer_list.clear()

        # Сверху вниз:
        # последний слой -> первый слой
        for index in range(len(self.layers) - 1, -1, -1):
            self.create_layer_list_item(self.layers[index])

        self.layer_list.blockSignals(False)

        self.view.viewport().update()
        self.update_window_title()
        self.update_history_buttons()
        self.update_project_stats()

    # ========================================================
    # Scene rect
    # ========================================================

    def update_scene_rect(self):
        if not self.canvas_width or not self.canvas_height:
            return

        scene_w = self.canvas_width * self.preview_scale
        scene_h = self.canvas_height * self.preview_scale

        margin = max(
            self.view.viewport().width(),
            self.view.viewport().height(),
        )

        self.view.scene().setSceneRect(
            -margin,
            -margin,
            scene_w + margin * 2,
            scene_h + margin * 2,
        )

    # ========================================================
    # Layers
    # ========================================================

    def selected_index(self):
        row = self.layer_list.currentRow()

        if row < 0:
            return -1

        item = self.layer_list.item(row)

        if not item:
            return -1

        layer = item.data(Qt.ItemDataRole.UserRole)

        if layer not in self.layers:
            return -1

        return self.layers.index(layer)

    def selected_layer(self):
        index = self.selected_index()

        if 0 <= index < len(self.layers):
            return self.layers[index]

        return None

    def select_layer(self, index):
        if not 0 <= index < len(self.layers):
            return

        layer = self.layers[index]

        if layer.list_item:
            row = self.layer_list.row(layer.list_item)
            self.layer_list.setCurrentRow(row)


    def layer_selected(self, row):
        self.view.viewport().update()
        self.update_project_stats()


    # ========================================================
    # Delete layer
    # ========================================================

    def delete_layer(self):
        index = self.selected_index()

        if index <= 0:
            QMessageBox.information(
                self,
                "Удаление",
                "Фоновый слой удалить нельзя.",
            )
            return

        layer = self.layers.pop(index)

        self.undo_stack.append({
            "type": "delete",
            "index": index,
            "layer": layer,
        })
        self.redo_stack.clear()

        self.rebuild_scene()
        self.update_project_stats()

        if self.layers:
            self.select_layer(min(index, len(self.layers) - 1))

        self.update_window_title()
        self.update_history_buttons()

    # ========================================================
    # Brush Undo / Redo
    # ========================================================

    def finish_brush_action(self, layer, patches):
        if not patches:
            return

        index = self.layers.index(layer)

        self.undo_stack.append({
            "type": "brush",
            "index": index,
            "patches": patches,
        })
        self.redo_stack.clear()

        self.update_window_title()
        self.update_history_buttons()

    def apply_brush_patches(self, action, undo):
        index = action["index"]

        if not 0 <= index < len(self.layers):
            return

        layer = self.layers[index]
        patches = action["patches"]
        sequence = reversed(patches) if undo else patches

        for rect, before, after in sequence:
            layer.alpha.paste(
                before if undo else after,
                rect[:2],
            )

        self.update_layer_preview(layer)

    # ========================================================
    # Undo
    # ========================================================

    def undo(self):
        if not self.undo_stack:
            return

        action = self.undo_stack.pop()
        typ = action["type"]

        if typ == "brush":
            self.apply_brush_patches(action, True)

        elif typ == "add":
            index = action["index"]

            if 0 <= index < len(self.layers):
                self.layers.pop(index)

            self.rebuild_scene()

        elif typ == "delete":
            index = action["index"]
            layer = action["layer"]

            self.layers.insert(min(index, len(self.layers)), layer)
            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "replace":
            index = action["index"]
            self.layers[index] = action["old"]

            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "rename":
            index = action["index"]

            if 0 <= index < len(self.layers):
                self.layers[index].name = action["old_name"]

            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "visibility":
            index = action["index"]

            if 0 <= index < len(self.layers):
                self.layers[index].visible = action["old"]

            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "reorder":
            self.restore_layer_order(action["old_ids"])

        self.update_window_title()
        self.update_project_stats()
        self.update_history_buttons()


    # ========================================================
    # Redo
    # ========================================================

    def redo(self):
        if not self.redo_stack:
            return

        action = self.redo_stack.pop()
        typ = action["type"]

        if typ == "brush":
            self.apply_brush_patches(action, False)

        elif typ == "add":
            index = action["index"]
            layer = action["layer"]

            self.layers.insert(min(index, len(self.layers)), layer)
            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "delete":
            index = action["index"]

            if 0 <= index < len(self.layers):
                self.layers.pop(index)

            self.rebuild_scene()

        elif typ == "replace":
            index = action["index"]
            self.layers[index] = action["new"]

            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "rename":
            index = action["index"]

            if 0 <= index < len(self.layers):
                self.layers[index].name = action["new_name"]

            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "visibility":
            index = action["index"]

            if 0 <= index < len(self.layers):
                self.layers[index].visible = action["new"]

            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "reorder":
            self.restore_layer_order(action["new_ids"])

        self.undo_stack.append(action)

        self.update_window_title()
        self.update_project_stats()
        self.update_history_buttons()


    # ========================================================
    # History buttons
    # ========================================================

    def update_history_buttons(self):
        self.undo_action.setEnabled(bool(self.undo_stack))
        self.redo_action.setEnabled(bool(self.redo_stack))

    # ========================================================
    # Export PNG
    # ========================================================

    def export_layer(self):
        layer = self.selected_layer()

        if not layer:
            return

        self.save_layer_as_png(layer)

    def save_layer_as_png(self, layer):
        alpha = np.asarray(layer.alpha)
        ys, xs = np.where(alpha > 0)

        if len(xs) == 0:
            QMessageBox.information(
                self,
                "Экспорт",
                "Слой полностью прозрачный.",
            )
            return

        left = int(xs.min())
        right = int(xs.max()) + 1
        top = int(ys.min())
        bottom = int(ys.max()) + 1

        result = layer.rgba().crop(
            (left, top, right, bottom)
        )

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PNG",
            os.path.splitext(layer.name)[0] + ".png",
            "PNG (*.png)",
        )

        if not path:
            return

        result.save(path, "PNG")

        x = int(layer.x + left)
        y = int(layer.y + top)

        QApplication.clipboard().setText(
            f"({x}, {y})"
        )

        self.status.setText(
            f"Coordinates copied: ({x}, {y})",
        )

    def save_layer_to_project_folder(self, layer):
        if not self.project_path:
            QMessageBox.information(
                self,
                "Сохранение слоя",
                "Сначала сохраните проект.",
            )
            return

        project_dir = os.path.dirname(
            os.path.abspath(self.project_path)
        )

        filename = layer.name.strip()

        if not filename:
            filename = "Layer"

        filename = os.path.splitext(filename)[0]

        path = os.path.join(
            project_dir,
            filename + ".png",
        )

        alpha = np.asarray(layer.alpha)
        ys, xs = np.where(alpha > 0)

        if len(xs) == 0:
            QMessageBox.information(
                self,
                "Сохранение слоя",
                "Слой полностью прозрачный.",
            )
            return

        left = int(xs.min())
        right = int(xs.max()) + 1
        top = int(ys.min())
        bottom = int(ys.max()) + 1

        result = layer.rgba().crop(
            (left, top, right, bottom)
        )

        try:
            result.save(path, "PNG")

            x = int(layer.x + left)
            y = int(layer.y + top)

            QApplication.clipboard().setText(
                f"({x}, {y})"
            )

            self.status.setText(
                f"Слой сохранён: {os.path.basename(path)}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка сохранения",
                str(e),
            )

    # ========================================================
    # Save project
    # ========================================================

    def save_project(self):
        if not self.layers:
            return False

        if not self.project_path:
            return self.save_project_as()

        return self.write_project(self.project_path)

    def save_project_as(self):
        if not self.layers:
            return False

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            "",
            "kPanorama Project (*.kpp)",
        )

        if not path:
            return False

        if not path.lower().endswith(".kpp"):
            path += ".kpp"

        return self.write_project(path)


    def write_project(self, path):
        try:
            with zipfile.ZipFile(
                path,
                "w",
                compression=zipfile.ZIP_STORED,
            ) as z:

                project = {
                    "version": 10,
                    "canvas": [
                        self.canvas_width,
                        self.canvas_height,
                    ],
                    "layers": [],
                }

                for i, layer in enumerate(self.layers):
                    image_name = f"layer_{i}.png"

                    # RGB-изображение всегда сохраняется lossless.
                    # Если кэш актуален — PNG повторно не кодируется.
                    z.writestr(
                        image_name,
                        layer.get_image_data(),
                    )

                    is_background = (
                        i == 0 or layer is self.layers[0]
                    )

                    alpha_name = None
                    content_alpha_name = None
                    original_bbox = None

                    # Фоновому слою альфа не нужна вообще.
                    if not is_background:
                        alpha_name = f"alpha_{i}.png"

                        z.writestr(
                            alpha_name,
                            layer.get_alpha_data(),
                        )

                        content_alpha_data = (
                            layer.get_content_alpha_data()
                        )

                        if content_alpha_data:
                            content_alpha_name = (
                                f"content_alpha_{i}.png"
                            )

                            z.writestr(
                                content_alpha_name,
                                content_alpha_data,
                            )

                        original_bbox = (
                            layer.original_visible_bbox()
                        )

                    project["layers"].append({
                        "name": layer.name,
                        "image": image_name,
                        "alpha": alpha_name,
                        "content_alpha": content_alpha_name,
                        "original_bbox": (
                            list(original_bbox)
                            if original_bbox is not None
                            else None
                        ),
                        "x": layer.x,
                        "y": layer.y,
                        "visible": layer.visible,
                    })

                z.writestr(
                    "project.json",
                    json.dumps(
                        project,
                        ensure_ascii=False,
                        indent=2,
                    ),
                )

            self.project_path = os.path.abspath(path)

            self.mark_project_saved()
            self.status.setText("Проект сохранён")
            self.update_project_stats()

            return True

        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка сохранения",
                str(e),
            )
            return False

    # ========================================================
    # Load project
    # ========================================================

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            "kPanorama Project (*.kpp)",
        )

        if not path:
            return

        self.load_project_from_path(path)


    def load_project_from_path(self, path):
        try:
            with zipfile.ZipFile(path, "r") as z:
                project = json.loads(
                    z.read("project.json")
                )

                if project.get("version") != 10:
                    raise ValueError(
                        "Неподдерживаемая версия проекта"
                    )

                self.layers.clear()

                self.canvas_width, self.canvas_height = (
                    project["canvas"]
                )

                for i, data in enumerate(
                    project["layers"]
                ):
                    image_name = data["image"]

                    image_data = z.read(
                        image_name
                    )

                    rgb = Image.open(
                        io.BytesIO(image_data)
                    ).convert("RGB")

                    is_background = (
                        i == 0
                    )

                    if is_background:
                        alpha = Image.new(
                            "L",
                            rgb.size,
                            255,
                        )

                        content_alpha = Image.new(
                            "L",
                            rgb.size,
                            255,
                        )

                        alpha_data = None
                        content_alpha_data = b""

                    else:
                        alpha_name = data["alpha"]

                        if not alpha_name:
                            raise ValueError(
                                f"У слоя {i} отсутствует alpha"
                            )

                        alpha_data = z.read(
                            alpha_name
                        )

                        alpha = Image.open(
                            io.BytesIO(alpha_data)
                        ).convert("L")

                        content_alpha_name = (
                            data["content_alpha"]
                        )

                        if content_alpha_name:
                            content_alpha_data = z.read(
                                content_alpha_name
                            )

                            content_alpha = Image.open(
                                io.BytesIO(
                                    content_alpha_data
                                )
                            ).convert("L")
                        else:
                            content_alpha_data = b""

                            content_alpha = Image.new(
                                "L",
                                rgb.size,
                                255,
                            )

                    layer = Layer(
                        data["name"],
                        rgb,
                        data["x"],
                        data["y"],
                        alpha,
                        data["visible"],
                        original_bbox=data[
                            "original_bbox"
                        ],
                    )

                    # В проекте content_alpha хранится
                    # отдельно от текущей alpha.
                    layer.content_alpha = (
                        content_alpha
                    )

                    # ВАЖНО:
                    # пересоздаём numpy-кэш именно
                    # из загруженной content_alpha.
                    layer.content_alpha_array = (
                        np.asarray(
                            content_alpha,
                            dtype=np.float32,
                        )
                    )

                    # ------------------------------------------------
                    # Кэши PNG
                    # ------------------------------------------------

                    layer.image_cache = image_data
                    layer.image_dirty = False

                    layer.alpha_cache = alpha_data
                    layer.alpha_dirty = False

                    layer.content_alpha_cache = (
                        content_alpha_data
                    )
                    layer.content_alpha_dirty = False

                    self.layers.append(layer)

            self.undo_stack.clear()
            self.redo_stack.clear()

            self.rebuild_scene()

            self.project_path = os.path.abspath(
                path
            )

            self.update_project_stats()

            if self.layers:
                self.select_layer(
                    len(self.layers) - 1
                )

            self.mark_project_saved()

            self.status.setText(
                "Проект загружен"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка загрузки",
                str(e),
            )

    # ========================================================
    # Keyboard shortcuts
    # ========================================================

    def keyPressEvent(self, e):
        modifiers = e.modifiers()

        if (
            modifiers == Qt.KeyboardModifier.ControlModifier
            and e.key() == Qt.Key.Key_S
        ):
            self.save_project()
            return

        if (
            modifiers
            == (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.ShiftModifier
            )
            and e.key() == Qt.Key.Key_S
        ):
            self.save_project_as()
            return

        if (
            modifiers == Qt.KeyboardModifier.ControlModifier
            and e.key() == Qt.Key.Key_O
        ):
            self.load_project()
            return

        # Ctrl + E — сохранить текущий слой
        if (
            modifiers == Qt.KeyboardModifier.ControlModifier
            and e.key() == Qt.Key.Key_E
        ):
            layer = self.selected_layer()

            if layer:
                self.save_layer_to_project_folder(layer)

        if (
            modifiers == Qt.KeyboardModifier.ControlModifier
            and e.key() == Qt.Key.Key_Z
        ):
            self.undo()
            return

        if (
            modifiers & Qt.KeyboardModifier.ControlModifier
            and modifiers & Qt.KeyboardModifier.ShiftModifier
            and e.key() == Qt.Key.Key_Z
        ):
            self.redo()
            return

        super().keyPressEvent(e)


# ============================================================
# Run
# ============================================================

app = QApplication(sys.argv)

QImageReader.setAllocationLimit(1024 * 1024 * 1024)  # 2 GB

window = MainWindow()
window.show()

if len(sys.argv) > 1:
    file_path = sys.argv[1]

    if (
        os.path.isfile(file_path)
        and file_path.lower().endswith(".kpp")
    ):
        QTimer.singleShot(
            0,
            lambda: window.load_project_from_path(file_path)
        )

sys.exit(app.exec())
