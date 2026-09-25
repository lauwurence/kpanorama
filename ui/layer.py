################################################################################
## Layer

import numpy as np
from PIL import Image

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMenu,
    QPushButton,
    QWidget,
    QColorDialog,
    QLineEdit,
    QMessageBox,
    QFileDialog,
)

from core.layer import Layer
from context import icon


class LayerRowWidget(QWidget):

    def __init__(self, window, layer, item):
        super().__init__()

        self.window = window
        self.layer = layer
        self.item = item

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        index = window.layers.index(layer)

        if index == 0:
            item.setBackground(QColor("#2C5827"))

            # corner_label = QLabel("🔒")
            # corner_label.setStyleSheet("color: #888888; font-weight: bold;")
            # layout.addSpacing(6)
            # layout.addWidget(corner_label)
            # layout.addSpacing(1)

        elif layer.group_id is not None:
            corner_label = QLabel("└")
            corner_label.setStyleSheet("color: #888888; font-weight: bold;")
            layout.addSpacing(8)
            layout.addWidget(corner_label)
            layout.addSpacing(7)

        self.eye_button = QPushButton()
        self.eye_button.setFixedSize(24, 24)
        if layer.group_id is not None:
            self.eye_button.setIconSize(QSize(16, 16))
        else:
            self.eye_button.setIconSize(QSize(20, 20))
        self.eye_button.setFlat(True)
        self.eye_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.eye_button.clicked.connect(lambda: self.window.toggle_layer_visibility(self.window.layers.index(self.layer)))

        self.color_button = None

        if layer.is_solid:
            self.color_button = QPushButton()
            self.color_button.setFixedSize(20, 20)
            self.color_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.color_button.setToolTip("Change solid color")
            self.color_button.setFlat(True)
            self.color_button.clicked.connect(self.choose_fill_color)
            self.update_color_button()

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

        self.opacity = QLabel()
        self.opacity.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Tag Button
        self.tag_button = QPushButton()
        self.tag_button.setFixedSize(24, 24)
        self.tag_button.setFlat(True)
        self.tag_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tag_button.setToolTip("Layer quality suffix tag for kConverter")
        self.tag_button.clicked.connect(self.show_tag_menu)

        # Copy Coordinates
        self.copy_button = QPushButton()
        self.copy_button.setFixedSize(24, 24)
        self.copy_button.setIcon(icon("copy_coordinates.svg"))
        self.copy_button.setIconSize(QSize(20, 20))
        self.copy_button.setFlat(True)
        self.copy_button.setToolTip("Copy layer coordinates")
        self.copy_button.clicked.connect(self.copy_coordinates)
        self.copy_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Save Layer
        self.save_button = QPushButton()
        self.save_button.setFixedSize(24, 24)
        self.save_button.setIcon(icon("save_layer.svg"))
        self.save_button.setIconSize(QSize(20, 20))
        self.save_button.setFlat(True)
        self.save_button.setToolTip("Save layer (Shift+E)")
        self.save_button.clicked.connect(self.save_layer)
        self.save_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.index = QLabel("-")
        layout.addWidget(self.index)

        layout.addWidget(self.eye_button)
        layout.addSpacing(2)
        if layer.is_solid:
            layout.addWidget(self.color_button, 1)
            layout.addSpacing(5)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.name_edit, 1)
        layout.addWidget(self.opacity)

        if index != 0:
            layout.addWidget(self.tag_button)

            if layer.is_image:
                layout.addWidget(self.copy_button)

        layout.addWidget(self.save_button)

        self.update_appearance()
        self.update_tag_button()


    # =========================================================================
    # Solid color
    # =========================================================================

    def choose_fill_color(self):
        """
        Opens the color dialog and changes layer.fill_color.
        """

        current = self.layer.fill_color

        color = QColor(
            int(current[0]),
            int(current[1]),
            int(current[2]),
        )

        color = QColorDialog.getColor(
            color,
            self,
            "Choose Solid Color",
        )

        if not color.isValid():
            return

        new_color = (
            color.red(),
            color.green(),
            color.blue(),
        )

        if new_color == tuple(self.layer.fill_color):
            return

        self.layer.fill_color = new_color

        self.update_color_button()

        self.window.update_layer_preview(self.layer)
        self.window.rebuild_scene_view()
        self.window.update_project_stats()
        self.window.update_window_title()


    def update_color_button(self):
        """
        Updates the square color preview.
        """

        if self.color_button is None:
            return

        r, g, b = self.layer.fill_color

        self.color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb({r}, {g}, {b});
                border: 1px solid #666666;
                border-radius: 3px;
            }}

            QPushButton:hover {{
                background-color: rgb({r}, {g}, {b});
                border: 2px solid #FFFFFF;
                border-radius: 3px;
            }}

            QPushButton:pressed {{
                background-color: rgb({r}, {g}, {b});
                border: 2px solid #AAAAAA;
                border-radius: 3px;
            }}
            """
        )

        self.color_button.setToolTip(f"Solid color: #{r:02X}{g:02X}{b:02X}")


    # =========================================================================
    # Tag
    # =========================================================================

    def show_tag_menu(self):
        menu = QMenu(self)

        tags = [
            None,
            "HQ",
            "MQ",
            "LQ",
            "SQ",
        ]

        for tag in tags:
            action = menu.addAction(tag or "Character")
            action.setCheckable(True)
            action.setChecked(self.layer.tag == tag)
            action.triggered.connect(lambda checked=False, t=tag: self.set_tag(t))

        menu.exec(self.tag_button.mapToGlobal(self.tag_button.rect().bottomLeft()))

    def set_tag(self, tag):
        if tag not in {None, "HQ", "MQ", "LQ", "SQ"}:
            return

        if self.layer.tag == tag:
            return

        self.layer.tag = tag

        self.update_tag_button()

        self.window.update_window_title()
        self.window.update_project_stats()

    def update_tag_button(self):
        tag = self.layer.tag

        self.tag_button.setText(tag or "#")
        size = 10

        if tag == "HQ":
            color = "#63E73B"
        elif tag == "MQ":
            color = "#F2E714"
        elif tag == "LQ":
            color = "#FF9800"
        elif tag == "SQ":
            color = "#F44336"
        else:
            color = "#1CD5FF"
            size = 14

        self.tag_button.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: none;
                color: %s;
                font-size: %spx;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #333333;
                border-radius: 4px;
            }
            """ % (color, size)
        )


    # =========================================================================
    # Appearance
    # =========================================================================

    def update_appearance(self):

        self.index.setText("%s" %  self.window.sorted_layers.index(self.layer))

        if self.window.is_layer_visible(self.layer):
            self.eye_button.setIcon(icon("eye_show.svg"))
            self.name_label.setStyleSheet("color: white;")
        else:
            self.eye_button.setIcon(icon("eye_hide.svg"))
            self.name_label.setStyleSheet("color: #777;")

        self.opacity.setText(f"{self.layer.opacity}%" if self.layer.opacity != 100 else "")

        self.opacity.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 11px;
            }
        """)

        self.save_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: #333333;
                border-radius: 4px;
            }
        """)

        self.copy_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: #333333;
                border-radius: 4px;
            }
        """)

        self.name_edit.setStyleSheet("""
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
        """)

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

        name = name.replace(" ", "_")

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


class LayerListWidget(QListWidget):

    def __init__(self, window):
        super().__init__()

        self.window = window


################################################################################
## Methods

class MainWindowLayer():


    def get_separate_layers(self):
        return [ l for l in self.layers if not l.group_id or not self.get_group(l.group_id) ]


    # ========================================================
    # Selection
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
        row = self.layer_list.currentRow()

        if row < 0:
            return None

        item = self.layer_list.item(row)

        if not item:
            return None

        layer = item.data(Qt.ItemDataRole.UserRole)

        if layer not in self.layers:
            return None

        return layer


    def select_layer(self, index):

        if isinstance(index, Layer):
            layer = index

        elif not 0 <= index < len(self.layers):
            return

        else:
            layer = self.layers[index]

        if layer.list_item:
            row = self.layer_list.row(layer.list_item)
            self.layer_list.setCurrentRow(row)


    def layer_selected(self, row):
        self.update_solo_visibility()
        self.update_mask_display()

        self.view.viewport().update()
        self.update_project_stats()


    # ========================================================
    # Visibility
    # ========================================================

    def is_layer_visible(self, layer):
        if not layer.visible:
            return False

        if layer.group_id is None:
            return True

        for group in self.groups:

            if group.id == layer.group_id:
                return group.visible

        return True


    def toggle_layer_visibility(self, index=None, layer=None):

        if layer:
            index = self.layers.index(layer)

        if not 0 <= index < len(self.layers):
            return

        layer = self.layers[index]
        layer.visible = not layer.visible

        if layer.item:

            if self.solo_mode_enabled:
                layer.item.setVisible(layer is self.selected_layer())
            else:
                layer.item.setVisible(layer.visible)

        if layer.list_item:
            try:
                row_widget = self.layer_list.itemWidget(layer.list_item)

                if row_widget:
                    row_widget.update_appearance()
            except:
                pass

        self.update_project_stats()
        self.layer_list.viewport().update()


    # ========================================================
    # Move
    # ========================================================

    def move_layer_down(self):
        layer = self.selected_layer()

        if layer is None:
            return

        ordered = self.sorted_layers
        index = ordered.index(layer)

        if index <= 0:
            return

        neighbor = ordered[index - 1]

        if layer.group_id != neighbor.group_id:
            return

        i1 = self.layers.index(layer)
        i2 = self.layers.index(neighbor)

        self.layers[i1], self.layers[i2] = (
            self.layers[i2],
            self.layers[i1],
        )

        self.rebuild_layers_ui()
        self.update_scene_layer_order()
        self.select_layer(layer)


    def move_layer_up(self):
        layer = self.selected_layer()

        if layer is None:
            return

        ordered = self.sorted_layers
        index = ordered.index(layer)

        if index >= len(ordered) - 1:
            return

        neighbor = ordered[index + 1]

        # Пока запрещаем выход из группы
        if layer.group_id != neighbor.group_id:
            return

        i1 = self.layers.index(layer)
        i2 = self.layers.index(neighbor)

        self.layers[i1], self.layers[i2] = (
            self.layers[i2],
            self.layers[i1],
        )

        self.rebuild_layers_ui()
        self.update_scene_layer_order()
        self.select_layer(layer)

    # ========================================================
    # Delete
    # ========================================================

    def delete_layer(self, index=None):

        if index is None:
            index = self.selected_index()

        if index <= 0:
            QMessageBox.information(self, "Удаление", "Фоновый слой удалить нельзя.")
            return

        layer = self.layers.pop(index)

        self.push_undo({
            "type": "delete_layer",
            "index": index,
            "layer": layer,
        })

        self.rebuild_scene()

        if self.layers:
            self.select_layer(min(index, len(self.layers) - 1))

        self.update_project_stats()
        self.update_window_title()
        self.update_history_buttons()


    # ========================================================
    # Duplicate
    # ========================================================

    def duplicate_layer(self, layer):

        if not self.layers:
            return

        if layer is None:
            layer = self.selected_layer()

        index = self.layers.index(layer)
        new_index = index + 1
        new_layer = layer.copy()
        self.layers.insert(new_index, new_layer)
        self.rebuild_scene()

        self.select_layer(layer)

        self.push_undo({
            "type": "add",
            "index": new_index,
            "layer": new_layer,
        })

        self.update_project_stats()
        self.update_history_buttons()
        self.update_window_title()


    # ========================================================
    # Replace layer
    # ========================================================

    def replace_layer(self, index):
        if not (0 <= index < len(self.layers)):
            return

        layer = self.layers[index]

        path, _ = QFileDialog.getOpenFileName(self, "Pick a new image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)",
        )

        if not path:
            return

        try:

            old_image = layer.image
            new_image = Image.open(path).convert("RGB")

            layer.image = new_image

            # Сбрасываем только кеш изображения.
            layer.image_cache = None
            layer.image_dirty = True

            # Перестраиваем отображение.
            self.rebuild_scene()
            self.select_layer(layer)

            self.push_undo({
                "type": "replace_image",
                "index": index,
                "old_image": old_image,
                "new_image": new_image,
            })

            self.update_layer_preview(layer)
            self.update_project_stats()
            self.update_window_title()
            self.update_history_buttons()

        except Exception as e:
            QMessageBox.critical(self, "Replace Image", f"Unable to replace image:\n{e}")


    def replace_layer_from_clipboard(self, index):

        if not (0 <= index < len(self.layers)):
            return

        layer = self.layers[index]
        clipboard = QApplication.clipboard()

        if not clipboard.mimeData().hasImage():
            QMessageBox.information(self, "Replace Image Clipboard", "Clipboard does not contain an image.")
            return

        qimage = clipboard.image()

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
            new_image = pil_image.convert("RGB")

            old_image = layer.image

            layer.image = new_image

            layer.image_cache = None
            layer.image_dirty = True

            self.rebuild_scene()
            self.select_layer(layer)

            self.push_undo({
                "type": "replace_image",
                "index": index,
                "old_image": old_image,
                "new_image": new_image,
            })

            self.update_layer_preview(layer)
            self.update_project_stats()
            self.update_window_title()
            self.update_history_buttons()

            self.status.setText(f"Image replaced from clipboard: {width} × {height}")

        except Exception as e:
            QMessageBox.critical(self, "Replace Image Clipboard", f"Unable to replace image:\n{e}")


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
