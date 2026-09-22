################################################################################
## Main

import os
import sys

import numpy as np
from PIL import Image

from PyQt6.QtCore import Qt, QSize, QTimer, QSettings
from PyQt6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPixmap,
    QIcon,
    QImageReader,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsPixmapItem,
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
from core.history import History
from project.project_io import ProjectIO
from ui.canvas import CanvasView

APP_VERSION = (0, 1, 2)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(BASE_DIR, "icons")

def icon(name):
    return QIcon(os.path.join(ICON_DIR, name))

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
        self.eye_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.eye_button.clicked.connect(
            lambda: self.window.toggle_layer_visibility(self.window.layers.index(self.layer))
        )

        # Обычное отображение имени
        self.name_label = QLabel(layer.name)
        self.name_label.setSizePolicy(
            self.name_label.sizePolicy().Policy.Expanding,
            self.name_label.sizePolicy().Policy.Preferred,
        )
        self.name_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)

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
        self.copy_button.setIcon(icon("copy_coordinates.svg"))
        self.copy_button.setIconSize(QSize(20, 20))
        self.copy_button.setFlat(True)
        self.copy_button.setToolTip("Copy layer coordinates")
        self.copy_button.clicked.connect(self.copy_coordinates)
        self.copy_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.save_button = QPushButton()
        self.save_button.setFixedSize(24, 24)
        self.save_button.setIcon(icon("save_layer.svg"))
        self.save_button.setIconSize(QSize(20, 20))
        self.save_button.setFlat(True)
        self.save_button.setToolTip("Save layer (Shift + E)")
        self.save_button.clicked.connect(self.save_layer)
        self.save_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout.addWidget(self.eye_button)
        layout.addSpacing(2)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.name_edit, 1)
        layout.addWidget(self.copy_button)
        layout.addWidget(self.save_button)

        self.update_appearance()

    def update_appearance(self):
        if self.layer.visible:
            self.eye_button.setIcon(icon("eye_show.svg"))
            self.name_label.setStyleSheet("color: white;")
        else:
            self.eye_button.setIcon(icon("eye_hide.svg"))
            self.name_label.setStyleSheet("color: #777;")

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
        self.name_label.setVisible(False)

        self.name_edit.setText(self.layer.name)
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
            x, y, w, h = bounds
            text = f"({x}, {y})"
        else:
            text = f"({self.layer.x}, {self.layer.y})"

        QApplication.clipboard().setText(text)

        self.window.status.setText(f"Coordinates copied: {text}")

    def save_layer(self):
        self.window.save_layer_to_project_folder(self.layer)


# ============================================================
# Список слоёв
# ============================================================

class LayerListWidget(QListWidget):

    def __init__(self, window):
        super().__init__()

        self.window = window


# ============================================================
# Main Window
# ============================================================

class MainWindow(QMainWindow, History, ProjectIO):

    def __init__(self):
        super().__init__()

        self.settings = QSettings("keyclap", "kPanorama")

        self.project_path = None
        self.saved_history = ()

        self.setWindowTitle("")
        self.setWindowIcon(icon("icon.svg"))
        self.resize(1450, 900)

        self.brush_size = 100
        self.brush_strength = 100
        self.brush_hardness = 50

        self.layers = []

        self.canvas_width = 0
        self.canvas_height = 0

        self.max_preview_size = 3000
        self.preview_scale = 1.0

        # Режим визуализации alpha-маски
        self.mask_display_enabled = False
        self.mask_color_lut = self.create_mask_color_lut()

        self.solo_mode_enabled = False

        self.setup_ui()
        self.update_window_title()

        geometry = self.settings.value("geometry")

        if geometry:
            self.restoreGeometry(geometry)

    def create_mask_color_lut(self):
        lut = np.zeros((256, 3), dtype=np.uint8)
        lut[0] = (0, 0, 255)

        values = np.arange(1, 255, dtype=np.float32)

        t = (values - 1.0) / 253.0

        lut[1:255, 0] = np.round(255.0 * t).astype(np.uint8)
        lut[1:255, 1] = np.round(255.0 * (1.0 - t)).astype(np.uint8)

        lut[255] = (255, 255, 255)

        return lut

    def fill_layer_alpha(self, layer, white):

        if not layer:
            return

        if layer is self.layers[0]:
            return

        bbox = layer.original_visible_bbox()

        if bbox is None:
            return

        x0, y0, x1, y1 = bbox

        before = layer.alpha.crop((x0, y0, x1, y1))

        if white:
            layer.alpha = layer.content_alpha.copy()
        else:
            layer.alpha.paste(0, (x0, y0, x1, y1))

        after = layer.alpha.crop((x0, y0, x1, y1))

        if np.array_equal(np.asarray(before), np.asarray(after) ):
            return

        layer.alpha_dirty = True
        layer.recalculate_content_bbox()

        index = self.layers.index(layer)

        self.push_undo({
            "type": "fill_alpha",
            "index": index,
            "rect": (x0, y0, x1, y1),
            "before": before,
            "after": after,
        })

        self.update_layer_preview(layer)

        self.update_history_buttons()
        self.update_project_stats()
        self.view.viewport().update()


    def update_layer_preview_region(self, layer, rect):
        if not layer.item:
            return

        layer.preview_mask_qimage = None

        if not isinstance(layer.item, LayerPreviewItem):
            self.update_layer_preview(layer)
            return

        s = self.preview_scale

        x0, y0, x1, y1 = rect

        # Координаты изменяемой области в preview-пикселях
        px0 = max(0, int(np.floor(x0 * s)))
        py0 = max(0, int(np.floor(y0 * s)))
        px1 = min(layer.item.image.width(), int(np.ceil(x1 * s)))
        py1 = min(layer.item.image.height(), int(np.ceil(y1 * s)))

        if px1 <= px0 or py1 <= py0:
            return

        preview_w = px1 - px0
        preview_h = py1 - py0

        # ----------------------------------------
        # Берём только нужный участок исходника
        # ----------------------------------------

        src_x0 = max(0, int(np.floor(px0 / s)))
        src_y0 = max(0, int(np.floor(py0 / s)))
        src_x1 = min(layer.image.width, int(np.ceil(px1 / s)))
        src_y1 = min(layer.image.height, int(np.ceil(py1 / s)))

        if src_x1 <= src_x0 or src_y1 <= src_y0:
            return

        if self.mask_display_enabled:
            alpha = layer.alpha.crop((src_x0, src_y0, src_x1, src_y1))
            alpha_array = np.asarray(alpha, dtype=np.uint8)
            rgb_array = self.mask_color_lut[alpha_array]
            rgb = Image.fromarray(rgb_array, "RGB").convert("RGBA")

        else:
            rgb = layer.image.crop((src_x0, src_y0, src_x1, src_y1))
            alpha = layer.alpha.crop((src_x0, src_y0, src_x1, src_y1))
            rgb.putalpha(alpha)

        # ----------------------------------------
        # Очень важно:
        # patch должен иметь ровно preview-размер
        # ----------------------------------------

        if (rgb.width != preview_w) or (rgb.height != preview_h):
            rgb = rgb.resize((preview_w, preview_h), Image.Resampling.LANCZOS)

        patch = pil_to_qimage(rgb)

        # ----------------------------------------
        # Меняем только маленький участок QImage
        # ----------------------------------------

        layer.item.update_region(patch, px0, py0)

    def add_image_from_clipboard(self, qimage):
        if qimage.isNull():
            return

        try:
            qimage = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
            width = qimage.width()
            height = qimage.height()

            ptr = qimage.bits()
            ptr.setsize(width * height * 4)

            arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4))

            pil_image = Image.fromarray(arr, "RGBA")

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
                x = 0
                y = 0

            base_name = "Clipboard"
            layer_name = base_name
            number = 2

            existing_names = { layer.name for layer in self.layers }

            while layer_name in existing_names:
                layer_name = f"{base_name} {number}"
                number += 1

            layer = Layer(layer_name, rgb, x, y, alpha)

            index = len(self.layers)

            self.layers.append(layer)

            self.rebuild_scene()
            self.select_layer(index)
            self.update_project_stats()

            # ------------------------------------------------
            # Undo / Redo
            # ------------------------------------------------

            self.push_undo({
                "type": "add",
                "index": index,
                "layer": layer,
            })

            self.update_window_title()
            self.update_history_buttons()

            self.status.setText(f"Pasted from clipboard: {rgb.width} × {rgb.height}")

        except Exception as e:
            QMessageBox.critical(self, "Error pasting from clipboard", str(e))

    # ========================================================
    # Project state
    # ========================================================

    def has_unsaved_changes(self):
        return self.current_history != self.saved_history

    def update_window_title(self):
        if self.project_path:
            filename = os.path.splitext(os.path.basename(self.project_path))[0]
            full_path = os.path.abspath(self.project_path)
            title = f"{filename} [{full_path}] - kPanorama {".".join(str(n) for n in APP_VERSION)}"
        else:
            title = f"Untitled - kPanorama {".".join(str(n) for n in APP_VERSION)}"

        if self.has_unsaved_changes():
            title = "* " + title

        self.setWindowTitle(title)

    def mark_project_saved(self):
        self.saved_history = self.current_history
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

        save_button = msg.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        discard_button = msg.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

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
        self.layer_list.itemDoubleClicked.connect(self.start_layer_rename)
        self.layer_list.currentRowChanged.connect(self.layer_selected)
        self.layer_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.layer_list.customContextMenuRequested.connect(self.layer_context_menu)

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
        file_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

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
        settings_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

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

        self.undo_action = toolbar.addAction(icon("undo.svg"), "")
        self.undo_action.setToolTip("Undo (Ctrl+Z)")
        self.undo_action.triggered.connect(self.undo)

        self.redo_action = toolbar.addAction(icon("redo.svg"), "")
        self.redo_action.setToolTip("Redo (Ctrl+Shift+Z)")
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
            }

            QSlider::add-page:horizontal {
                background: #292929;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                width: 6px;
                height: 6px;
                margin: 0px;
                background: #8a8a8a;
                border: none;
                border-radius: 3px;
            }
        """


        # ----------------------------------------------------
        # Strength
        # ----------------------------------------------------

        toolbar.addWidget(QLabel("Strength:"))

        self.brush_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_strength_slider.setRange(0, 100)
        self.brush_strength_slider.setValue(int(self.brush_strength))
        self.brush_strength_slider.setFixedWidth(110)
        self.brush_strength_slider.setStyleSheet(slider_style)
        self.brush_strength_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.brush_strength_slider.valueChanged.connect(self.set_brush_strength)

        toolbar.addWidget(self.brush_strength_slider)

        self.brush_strength_label = QLabel(f"{int(self.brush_strength)}%")
        self.brush_strength_label.setFixedWidth(40)

        toolbar.addWidget(self.brush_strength_label)

        toolbar.addWidget(create_separator())

        # ----------------------------------------------------
        # Size
        # ----------------------------------------------------

        toolbar.addWidget(QLabel("Size:"))

        self.brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_size_slider.setRange(1, 3000)
        self.brush_size_slider.setValue(self.brush_size)
        self.brush_size_slider.setFixedWidth(110)
        self.brush_size_slider.setStyleSheet(slider_style)
        self.brush_size_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.brush_size_slider.valueChanged.connect(self.set_brush_size)

        toolbar.addWidget(self.brush_size_slider)

        self.brush_size_label = QLabel(f"{self.brush_size}px")
        self.brush_size_label.setFixedWidth(50)

        toolbar.addWidget(self.brush_size_label)

        toolbar.addWidget(create_separator())

        # ----------------------------------------------------
        # Hardness
        # ----------------------------------------------------

        toolbar.addWidget(QLabel("Hardness:"))

        self.brush_hardness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_hardness_slider.setRange(0, 100)
        self.brush_hardness_slider.setValue(int(self.brush_hardness))
        self.brush_hardness_slider.setFixedWidth(110)
        self.brush_hardness_slider.setStyleSheet(slider_style)
        self.brush_hardness_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.brush_hardness_slider.valueChanged.connect(self.set_brush_hardness)

        toolbar.addWidget(self.brush_hardness_slider)

        self.brush_hardness_label = QLabel(f"{self.brush_hardness:.0f}%")
        self.brush_hardness_label.setFixedWidth(40)

        toolbar.addWidget(self.brush_hardness_label)

        self.status = QLabel("Drag and drop images")
        self.statusBar().addWidget(self.status)

        # ----------------------------------------------------
        # Transparency Mask
        # ----------------------------------------------------

        toolbar.addWidget(create_separator())

        self.mask_display_action = toolbar.addAction("Visualize Mask")
        self.mask_display_action.setCheckable(True)
        self.mask_display_action.setChecked(self.mask_display_enabled)
        self.mask_display_action.setToolTip("Display Transparency Mask (V)")
        self.mask_display_action.triggered.connect(self.toggle_mask_display)

        toolbar.addWidget(create_separator())

        self.solo_mode_action = toolbar.addAction("Solo Mode")
        self.solo_mode_action.setCheckable(True)
        self.solo_mode_action.setChecked(self.solo_mode_enabled)
        self.solo_mode_action.setToolTip("Show only the selected layer (S)")
        self.solo_mode_action.triggered.connect(self.toggle_solo_mode)

        # ----------------------------------------------------
        # Статистика проекта
        # ----------------------------------------------------

        self.project_stats = QLabel()

        self.zoom_label = QLabel("Zoom: 100%")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.zoom_label.setStyleSheet(
            """
            QLabel {
                color: #999;
                padding: 0 8px;
            }
            """
        )

        self.statusBar().addPermanentWidget(self.zoom_label)

        self.project_stats.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.project_stats.setStyleSheet(
            """
            QLabel {
                color: #999;
                padding: 0 8px;
            }
            """
        )

        self.statusBar().addPermanentWidget(self.project_stats)
        self.update_project_stats()

        self.update_window_title()
        self.update_history_buttons()

    def update_project_stats(self):
        # Размер проекта
        if self.canvas_width and self.canvas_height:
            project_size = f"{self.canvas_width} × {self.canvas_height}"
        else:
            project_size = "-"

        # Количество слоёв
        layer_count = len(self.layers)

        # Количество видимых слоёв
        visible_count = sum(1 for layer in self.layers if layer.visible)

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
        if self.project_path and os.path.isfile(self.project_path):
            file_size = os.path.getsize(self.project_path)

            if file_size < 1024:
                file_size_text = f"{file_size} B"

            elif file_size < 1024 ** 2:
                file_size_text = f"{file_size / 1024:.1f} KB"

            elif file_size < 1024 ** 3:
                file_size_text = f"{file_size / (1024 ** 2):.1f} MB"

            else:
                file_size_text = f"{file_size / (1024 ** 3):.2f} GB"

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
        from association import register_kpp_file_association

        register_kpp_file_association()

        QMessageBox.information(self, "File Associations", ".kpp file association registered.")

    # ========================================================
    # Alpha mask display mode
    # ========================================================

    def toggle_mask_display(self, enabled=None):
        if enabled is None:
            enabled = not self.mask_display_enabled

        enabled = bool(enabled)

        if enabled == self.mask_display_enabled:
            return

        self.mask_display_enabled = enabled

        if hasattr(self, "mask_display_action"):
            self.mask_display_action.setChecked(enabled)

        for layer in self.layers:
            if not layer.item:
                continue

            qimage = self.get_preview_qimage(
                layer,
                mask=enabled,
            )

            layer.item.set_image(qimage)

            if layer.mask_dirty:
                layer.mask_dirty = False

                self.update_layer_preview(layer)

        self.view.viewport().update()

        if enabled:
            self.status.setText("Transparency mask display enabled")
        else:
            self.status.setText("Normal image display enabled")


    # ========================================================
    # Solo layer display mode
    # ========================================================

    def toggle_solo_mode(self, enabled=None):

        if enabled is None:
            enabled = not self.solo_mode_enabled

        enabled = bool(enabled)

        if enabled == self.solo_mode_enabled:
            return

        self.solo_mode_enabled = enabled

        if hasattr(self, "solo_mode_action"):
            self.solo_mode_action.setChecked(enabled)

        self.update_solo_visibility()

        if enabled:
            self.status.setText("Solo mode enabled")
        else:
            self.status.setText("Solo mode disabled")


    def update_solo_visibility(self):

        selected = self.selected_layer()

        for layer in self.layers:

            if not layer.item:
                continue

            if self.solo_mode_enabled:

                # В Solo Mode показываем только выбранный слой.
                layer.item.setVisible(
                    layer is selected
                )

            else:

                # Обычный режим — возвращаем реальные
                # состояния eye каждой строки.
                layer.item.setVisible(
                    layer.visible
                )

        self.layer_list.viewport().update()
        self.view.viewport().update()


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

        if self.brush_size_slider.value() != value:
            self.brush_size_slider.setValue(value)

        self.brush_size_label.setText(f"{value}px")

        self.view.viewport().update()

    def set_brush_strength(self, value):
        value = max(1, min(100, int(value)))

        self.brush_strength = value

        if self.brush_strength_slider.value() != value:
            self.brush_strength_slider.setValue(value)

        self.brush_strength_label.setText(f"{value}%")

        self.view.viewport().update()

    def set_brush_hardness(self, value):
        value = max(0.0, min(100.0, float(value)))

        self.brush_hardness = value

        slider_value = int(round(value))

        if self.brush_hardness_slider.value() != slider_value:
            self.brush_hardness_slider.setValue(slider_value)

        # Обновляем число справа.
        self.brush_hardness_label.setText(f"{value:.0f}%")

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

        self.push_undo({
            "type": "reorder",
            "old_ids": old_ids,
            "new_ids": new_ids,
        })

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
        replace_action = menu.addAction("Replace Image")

        menu.addSeparator()

        fill_white_action = menu.addAction("Fill White")
        fill_white_action.triggered.connect(lambda checked=False, l=layer: self.fill_layer_alpha(l, True))

        fill_black_action = menu.addAction("Fill Black")
        fill_black_action.triggered.connect(lambda checked=False, l=layer: self.fill_layer_alpha(l, False))

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
            "Rename Layer",
            "Name:",
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

        self.push_undo({
            "type": "rename",
            "index": index,
            "old_name": old_name,
            "new_name": new_name,
        })

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

            if self.solo_mode_enabled:
                layer.item.setVisible(
                    layer is self.selected_layer()
                )
            else:
                layer.item.setVisible(
                    layer.visible
                )

        if layer.list_item:
            row_widget = self.layer_list.itemWidget(layer.list_item)

            if row_widget:
                row_widget.update_appearance()

        self.push_undo({
            "type": "visibility",
            "index": index,
            "old": old_visible,
            "new": layer.visible,
        })

        self.update_history_buttons()
        self.update_window_title()
        self.update_project_stats()
        self.layer_list.viewport().update()

    # ========================================================
    # Open image
    # ========================================================

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(self,
            "Add image",
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
                rgb = rgb.resize(canvas_size, Image.Resampling.LANCZOS)
                alpha = alpha.resize(canvas_size, Image.Resampling.LANCZOS )

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
                rgb, alpha = self.load_image_file(path, background=False)

            layer_name = os.path.splitext(os.path.basename(path))[0]
            layer = Layer(layer_name, rgb, 0, 0, alpha)

            index = len(self.layers)
            self.layers.append(layer)

            self.rebuild_scene()
            self.select_layer(index)
            self.update_project_stats()

            self.push_undo({
                "type": "add",
                "index": index,
                "layer": layer,
            })

            self.update_window_title()
            self.update_history_buttons()

            self.status.setText(
                f"Добавлено: {os.path.basename(path)} "
                f"({rgb.width} × {rgb.height})"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error adding image", str(e))

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
            rgb, alpha = self.load_image_file(path, background=index == 0)
            layer_name = os.path.splitext(os.path.basename(path))[0]

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

            self.push_undo({
                "type": "replace",
                "index": index,
                "old": old_layer,
                "new": new_layer,
            })

            self.update_window_title()
            self.update_history_buttons()

            self.status.setText(f"Image replaced: {new_layer.name}")

        except Exception as e:
            QMessageBox.critical(self, "Error replacing image", str(e))

    # ========================================================
    # Preview scale
    # ========================================================

    def calculate_preview_scale(self):
        if not self.canvas_width or not self.canvas_height:
            return 1.0

        longest = max(self.canvas_width, self.canvas_height)
        return min(1.0, self.max_preview_size / longest)


    def alpha_to_mask_color(self, alpha):
        """
        alpha:
            0   -> blue
            1   -> green
            2..254 -> green -> red
            255 -> white

        Возвращает RGB-кортеж.
        """

        alpha = int(alpha)

        if alpha <= 0:
            return (0, 0, 255)

        if alpha >= 255:
            return (255, 255, 255)

        # 1..254:
        # green -> red
        t = (alpha - 1) / 253.0

        r = int(round(255 * t))
        g = int(round(255 * (1.0 - t)))
        b = 0

        return (r, g, b)


    def create_mask_preview(self, layer):
        s = self.preview_scale

        w = max(1, round(layer.image.width * s))
        h = max(1, round(layer.image.height * s))

        alpha = layer.alpha.resize((w, h), Image.Resampling.LANCZOS)
        alpha_array = np.asarray(alpha, dtype=np.uint8)
        rgb_array = self.mask_color_lut[alpha_array]

        return Image.fromarray(rgb_array, "RGB").convert("RGBA")


    def get_preview_qimage(self, layer, mask=False):
        if mask:
            if layer.preview_mask_qimage is None:
                preview = self.create_mask_preview(layer)
                layer.preview_mask_qimage = pil_to_qimage(preview)

            return layer.preview_mask_qimage

        else:
            if layer.preview_normal_qimage is None:
                preview = self.create_preview(layer)
                layer.preview_normal_qimage = pil_to_qimage(preview)

            return layer.preview_normal_qimage

    def create_preview(self, layer):
        s = self.preview_scale

        w = max(1, round(layer.image.width * s))
        h = max(1, round(layer.image.height * s))

        rgb = layer.image.resize((w, h), Image.Resampling.LANCZOS)
        alpha = layer.alpha.resize((w, h), Image.Resampling.LANCZOS)

        rgb.putalpha(alpha)

        return rgb


    def update_layer_preview(self, layer):
        if not layer.item:
            return

        # Всегда обновляем обычный preview-кэш
        normal_preview = self.create_preview(layer)
        normal_qimage = pil_to_qimage(normal_preview)
        layer.preview_normal_qimage = normal_qimage

        # Маска после изменения alpha становится устаревшей
        layer.preview_mask_qimage = None

        if self.mask_display_enabled:
            # В режиме маски сразу строим новую маску
            mask_preview = self.create_mask_preview(layer)
            mask_qimage = pil_to_qimage(mask_preview)
            layer.preview_mask_qimage = mask_qimage

            layer.preview_qimage = mask_qimage
            layer.item.set_image(mask_qimage)
        else:
            layer.preview_qimage = normal_qimage
            layer.item.set_image(normal_qimage)

        self.view.viewport().update()

    # ========================================================
    # Checkerboard background
    # ========================================================

    def create_checkerboard(self, width, height, cell_size=16):
        image = QImage(width, height, QImage.Format.Format_RGB32)
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

                painter.drawRect(x, y, min(cell_size, width - x), min(cell_size, height - y))

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
                max(1, round(self.canvas_width * self.preview_scale)),
                max(1, round(self.canvas_height * self.preview_scale)),
                cell_size=max(1, round(16 * self.preview_scale)),
            )

            checker_item = QGraphicsPixmapItem(QPixmap.fromImage(checker))
            checker_item.setZValue(-1000)

            scene.addItem(checker_item)

        # ----------------------------------------------------
        # Layers
        # ----------------------------------------------------

        for layer in self.layers:
            preview = self.create_preview(layer)
            layer.preview_qimage = pil_to_qimage(preview)

            item = LayerPreviewItem(layer.preview_qimage)
            item.setPos(layer.x * self.preview_scale, layer.y * self.preview_scale)
            if self.solo_mode_enabled:
                item.setVisible(
                    layer is self.selected_layer()
                )
            else:
                item.setVisible(
                    layer.visible
                )
            layer.item = item

            self.view.scene().addItem(item)

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
        margin = max(self.view.viewport().width(), self.view.viewport().height())

        self.view.scene().setSceneRect(-margin, -margin, scene_w + margin * 2, scene_h + margin * 2)

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
        self.update_solo_visibility()

        self.view.viewport().update()
        self.update_project_stats()


    # ========================================================
    # Delete layer
    # ========================================================

    def delete_layer(self):
        index = self.selected_index()

        if index <= 0:
            QMessageBox.information(self, "Удаление", "Фоновый слой удалить нельзя.")
            return

        layer = self.layers.pop(index)

        self.push_undo({
            "type": "delete",
            "index": index,
            "layer": layer,
        })

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

        self.push_undo({
            "type": "brush",
            "index": index,
            "patches": patches,
        })

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
            layer.alpha.paste(before if undo else after, rect[:2])

        if layer:
            layer.recalculate_content_bbox()

        self.update_layer_preview(layer)

    def apply_fill_alpha(self, action, undo):
        index = action["index"]

        if not 0 <= index < len(self.layers):
            return

        layer = self.layers[index]

        x0, y0, x1, y1 = action["rect"]

        alpha = action["before"] if undo else action["after"]

        layer.alpha.paste(
            alpha,
            (x0, y0),
        )

        layer.alpha_dirty = True
        layer.recalculate_content_bbox()

        self.update_layer_preview(layer)


    # ========================================================
    # History buttons
    # ========================================================

    def update_history_buttons(self):

        if self.can_undo:
            self.undo_action.setEnabled(True)
            self.undo_action.setIcon(icon("undo.svg"))
        else:
            self.undo_action.setEnabled(False)
            self.undo_action.setIcon(icon("undo_inactive.svg"))

        if self.can_redo:
            self.redo_action.setEnabled(True)
            self.redo_action.setIcon(icon("redo.svg"))
        else:
            self.redo_action.setEnabled(False)
            self.redo_action.setIcon(icon("redo_inactive.svg"))

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
            QMessageBox.information(self, "Экспорт", "Слой полностью прозрачный.")
            return

        left = int(xs.min())
        right = int(xs.max()) + 1
        top = int(ys.min())
        bottom = int(ys.max()) + 1

        result = layer.rgba().crop((left, top, right, bottom))

        path, _ = QFileDialog.getSaveFileName(self, "Save PNG", os.path.splitext(layer.name)[0] + ".png", "PNG (*.png)")

        if not path:
            return

        result.save(path, "PNG")

        x = int(layer.x + left)
        y = int(layer.y + top)

        QApplication.clipboard().setText(f"({x}, {y})")

        self.status.setText(f"Layer saved: {os.path.basename(path)} ({x}, {y})")

    def save_layer_to_project_folder(self, layer):
        if not self.project_path:
            QMessageBox.information(self, "Сохранение слоя", "Сначала сохраните проект.")
            return

        project_dir = os.path.dirname(os.path.abspath(self.project_path))
        filename = layer.name.strip()

        if not filename:
            filename = "Layer"

        filename = os.path.splitext(filename)[0]
        path = os.path.join(project_dir, filename + ".png")

        alpha = np.asarray(layer.alpha)
        ys, xs = np.where(alpha > 0)

        if len(xs) == 0:
            QMessageBox.information(self, "Сохранение слоя", "Слой полностью прозрачный.")
            return

        left = int(xs.min())
        right = int(xs.max()) + 1
        top = int(ys.min())
        bottom = int(ys.max()) + 1

        result = layer.rgba().crop((left, top, right, bottom))

        try:
            result.save(path, "PNG")

            x = int(layer.x + left)
            y = int(layer.y + top)

            QApplication.clipboard().setText(f"({x}, {y})")

            self.status.setText(f"Layer saved: {os.path.basename(path)} ({x}, {y})")

        except Exception as e:
            QMessageBox.critical(self, "Error saving", str(e))


    # ========================================================
    # Keyboard shortcuts
    # ========================================================

    def keyPressEvent(self, e):
        modifiers = e.modifiers()

        # Save
        if modifiers == Qt.KeyboardModifier.ControlModifier and (e.key() == Qt.Key.Key_S):
            self.save_project()
            return

        # Save As
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

        # Open
        if modifiers == Qt.KeyboardModifier.ControlModifier and (e.key() == Qt.Key.Key_O):
            self.load_project()
            return

        # Ctrl + E — сохранить текущий слой
        if modifiers == Qt.KeyboardModifier.ControlModifier and (e.key() == Qt.Key.Key_E):
            layer = self.selected_layer()

            if layer:
                self.save_layer_to_project_folder(layer)

        # Visualize Mask
        if (
            modifiers == Qt.KeyboardModifier.NoModifier
            and e.nativeScanCode() == 47
        ):
            self.toggle_mask_display()
            return

        # Solo Mode
        if (
            modifiers == Qt.KeyboardModifier.NoModifier
            and e.nativeScanCode() == 31
        ):
            self.toggle_solo_mode()
            return

        # Undo
        if modifiers == Qt.KeyboardModifier.ControlModifier and (e.key() == Qt.Key.Key_Z):
            self.undo()
            return

        # Redo
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

    if os.path.isfile(file_path) and file_path.lower().endswith(".kpp"):
        QTimer.singleShot(0, lambda: window.load_project_from_path(file_path))

sys.exit(app.exec())
