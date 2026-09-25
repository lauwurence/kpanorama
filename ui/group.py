################################################################################
## Groups

import os

import numpy as np
from PIL import Image

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import (
    QColor,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QWidget,
    QLabel,
)

from core.layer import LayerGroup

from context import icon


class MainWindowGroup():


    def get_group_layers(self, group):
        return [ l for l in self.layers if l.group_id == group.id ]


    def get_group(self, id):

        if id is None:
            return None

        for group in self.groups:

            if group.id == id:
                return group

        return None


    def create_group(self):
        group = LayerGroup()
        self.groups.append(group)
        self.rebuild_layers_ui()
        self.status.setText(f"Group created: {group.name}")


    def rename_group(self, group):
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Rename Group")
        dialog.setLabelText("Rename group to:")
        dialog.setTextValue(group.name)
        dialog.resize(300, dialog.sizeHint().height())

        ok = dialog.exec()
        name = dialog.textValue()

        if not ok:
            return

        name = name.strip()

        if not name:
            return

        name = name.replace(" ", "_")

        group.name = name

        self.rebuild_layers_ui()

        self.update_window_title()
        self.update_project_stats()

        self.status.setText(f"Group renamed to: {name}")


    def delete_group(self, group):
        reply = QMessageBox.question(
            self,
            "Delete Group",
            f'Delete group "{group.name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        layers = []

        # Удаляем слои
        for layer in self.layers:
            index = self.layers.index(layer)

            if layer.group_id == group.id:
                layers.append((index, self.layers.pop(index)))

        # Удаляем группу
        index = self.groups.index(group)
        self.groups.remove(group)

        self.push_undo({
            "type": "delete_group",
            "index": index,
            "group": group,
            "layers": layers,
        })

        self.rebuild_scene()

        self.update_window_title()
        self.update_project_stats()

        self.status.setText(f"Group deleted: {group.name}")


    def show_group_context_menu(self, group, position):
        menu = QMenu(self)

        index = self.groups.index(group)

        rename_action = menu.addAction("Rename Group")

        menu.addSeparator()

        move_up_action = menu.addAction("Move Up")
        move_up_action.triggered.connect(self.move_group_up)
        move_up_action.setEnabled(index < len(self.groups) - 1)

        move_down_action = menu.addAction("Move Down")
        move_down_action.triggered.connect(self.move_group_down)
        move_down_action.setEnabled(index > 0)

        menu.addSeparator()

        delete_action = menu.addAction("Delete Group")

        action = menu.exec(position)

        if action == rename_action:
            self.rename_group(group)

        elif action == delete_action:
            self.delete_group(group)


    def add_selected_layer_to_group(self):
        layer = self.selected_layer()

        if layer is None:
            QMessageBox.information(self, "Group", "Select a layer first.")
            return

        if not self.groups:
            QMessageBox.information(self, "Group", "Create a group first.")
            return

        group_names = [ group.name for group in self.groups ]

        current_index = 0

        if layer.group_id is not None:

            for i, group in enumerate(self.groups):

                if group.id == layer.group_id:
                    current_index = i
                    break

        name, ok = QInputDialog.getItem(
            self,
            "Add To Group",
            f"Select group:",
            group_names,
            current_index,
            False,
        )

        if not ok:
            return

        group = self.groups[group_names.index(name)]

        old_group_id = layer.group_id

        if old_group_id == group.id:
            return

        layer.group_id = group.id

        self.rebuild_layers_ui()
        self.update_scene_layer_order()

        self.status.setText(f'"{layer.name}" moved to "{group.name}"')


    def remove_selected_layer_from_group(self):
        layer = self.selected_layer()

        if layer is None:
            QMessageBox.information(self, "Group", "Select a layer first.")
            return

        if layer.group_id is None:
            return

        layer.group_id = None

        self.rebuild_layers_ui()
        self.update_scene_layer_order()

        self.status.setText(f'"{layer.name}" removed from the group.')


    def export_selected_group(self):
        group = self.selected_group()

        if group is None:
            QMessageBox.information(self, "Group export", "Select a group first.")
            return

        self.export_group(group)


    def create_group_list_item(self, group):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole + 1, group)
        item.setSizeHint(QSize(100, 34))
        item.setBackground(QColor("#333333"))
        self.layer_list.addItem(item)

        widget = QWidget()

        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        widget.customContextMenuRequested.connect(
            lambda position, g=group: self.show_group_context_menu(g, widget.mapToGlobal(position))
        )

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        # -------------------------
        # Expand / Collapse
        # -------------------------

        expand_button = QPushButton()
        expand_button.setFlat(True)
        expand_button.setFixedSize(24, 24)
        expand_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        def update_expand_button():
            expand_button.setText("▾" if group.expanded else "▸")
            expand_button.setStyleSheet("font-size: 20px;")

        update_expand_button()

        # -------------------------
        # Видимость
        # -------------------------

        eye_button = QPushButton()
        eye_button.setFlat(True)
        eye_button.setFixedSize(24, 24)
        eye_button.setIconSize(QSize(20, 20))
        eye_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        def update_eye_button():
            if group.visible:
                eye_button.setIcon(icon("eye_show.svg"))
                eye_button.setStyleSheet("color: white;")
            else:
                eye_button.setIcon(icon("eye_hide.svg"))
                eye_button.setStyleSheet("color: #777;")

        update_eye_button()

        # -------------------------
        # Название
        # -------------------------

        name_edit = QLabel(group.name)
        name_edit.setStyleSheet("font-weight: bold;")
        name_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        name_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        name_edit.customContextMenuRequested.connect(
            lambda position, g=group: self.show_group_context_menu(g, name_edit.mapToGlobal(position))
        )

        # -------------------------
        # Tag
        # -------------------------

        tag_button = QPushButton("#")
        tag_button.setFixedSize(24, 24)
        tag_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tag_button.clicked.connect(lambda checked=False, g=group: self.show_group_tag_menu(g))

        group.tag_button = tag_button
        self.update_group_tag_button(group)

        # -------------------------
        # Координаты
        # -------------------------

        coords_button = QPushButton("")
        coords_button.setFixedSize(24, 24)
        coords_button.setIcon(icon("copy_coordinates.svg"))
        coords_button.setIconSize(QSize(20, 20))
        coords_button.setFlat(True)
        coords_button.setToolTip("Copy group coordinates")
        coords_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        coords_button.clicked.connect(lambda: self.copy_group_coords(group))

        # -------------------------
        # Save
        # -------------------------

        export_button = QPushButton("")
        export_button.setFixedSize(24, 24)
        export_button.setIcon(icon("save_layer.svg"))
        export_button.setIconSize(QSize(20, 20))
        export_button.setFlat(True)
        export_button.setToolTip("Save group")
        export_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        export_button.clicked.connect(lambda: self.export_group(group))

        # -------------------------
        # Layout
        # -------------------------

        layout.addWidget(expand_button)
        layout.addWidget(eye_button)
        layout.addWidget(name_edit, 1)
        layout.addWidget(tag_button)
        layout.addWidget(coords_button)
        layout.addWidget(export_button)

        self.layer_list.setItemWidget(item, widget)

        # =================================================
        # Expand / Collapse
        # =================================================

        def toggle_expanded():
            group.expanded = not group.expanded
            self.rebuild_layers_ui()

        expand_button.clicked.connect(toggle_expanded)

        # =================================================
        # Visibility
        # =================================================

        def toggle_visibility():
            group.visible = not group.visible

            for layer in self.get_group_layers(group):
                self.toggle_layer_visibility(layer)

            update_eye_button()

        eye_button.clicked.connect(toggle_visibility)

        return item


    def show_group_tag_menu(self, group):
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
            action.setChecked(group.tag == tag)

            action.triggered.connect(
                lambda checked=False, t=tag, g=group: self.set_group_tag(g, t)
            )

        menu.exec(group.tag_button.mapToGlobal(group.tag_button.rect().bottomLeft()))


    def set_group_tag(self, group, tag):
        if tag not in {None, "HQ", "MQ", "LQ", "SQ"}:
            return

        if group.tag == tag:
            return

        group.tag = tag

        self.update_group_tag_button(group)

        self.update_window_title()
        self.update_project_stats()


    def update_group_tag_button(self, group):
        tag = group.tag

        group.tag_button.setText(tag or "#")

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

        group.tag_button.setStyleSheet("""
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
        """ % (color, size))


    def select_group(self, index):
        return

        if not 0 <= index < len(self.groups):
            return

        group = self.groups[index]

        if group.list_item:
            row = self.layer_list.row(group.list_item)
            self.layer_list.setCurrentRow(row)


    def selected_group_index(self):
        group = self.selected_group()

        if group not in self.groups:
            return -1

        return self.groups.index(group)


    def selected_group(self):
        row = self.layer_list.currentRow()

        if row < 0:
            return None

        item = self.layer_list.item(row)

        if not item:
            return None

        group = item.data(Qt.ItemDataRole.UserRole + 1)

        if group not in self.groups:
            return None

        return group


    # ========================================================
    # Move
    # ========================================================

    def move_group_down(self):
        index = self.selected_group_index()

        if index is None:
            return

        if index <= 0:
            return

        self.groups[index - 1], self.groups[index] = (
            self.groups[index],
            self.groups[index - 1],
        )

        # self.select_group(index - 1)
        self.rebuild_layers_ui()
        self.update_scene_layer_order()


    def move_group_up(self):
        index = self.selected_group_index()

        if index is None:
            return

        if index >= len(self.groups) - 1:
            return

        self.groups[index + 1], self.groups[index] = (
            self.groups[index],
            self.groups[index + 1],
        )

        # self.select_group(index + 1)
        self.rebuild_layers_ui()
        self.update_scene_layer_order()


    def copy_group_coords(self, group):

        layers = [ l for l in self.layers if l.group_id == group.id and l.visible ]

        if not layers:
            QMessageBox.information(self, "Coordinates", "No visible layers in the group.")
            return

        left = top = right = bottom = None

        for layer in layers:
            bbox = layer.content_bbox

            if bbox is None:
                continue

            x0, y0, x1, y1 = bbox

            x0 += int(round(layer.x))
            y0 += int(round(layer.y))
            x1 += int(round(layer.x))
            y1 += int(round(layer.y))

            if left is None:
                left = x0
                top = y0
            else:
                left = min(left, x0)
                top = min(top, y0)

        if left is None:
            return

        text = f"({left}, {top})"

        QApplication.clipboard().setText(text)

        self.status.setText(f"Coordinates copied: {text}")


    def get_group_save_name(self, group):
        name = group.name.strip()

        if not name:
            name = "Group"

        name = os.path.splitext(name)[0]

        if group.tag is not None:
            name += f"_{group.tag}"

        return name


    def export_group(self, group):

        if not self.project_path:
            QMessageBox.information(self, "Save Group", "Save the project first.")
            return

        layers = [ l for l in self.layers if l.group_id == group.id and l.visible ]

        if not layers:
            QMessageBox.information(
                self,
                "Save Group",
                "Group has no visible layers."
            )
            return

        project_dir = os.path.dirname(os.path.abspath(self.project_path))

        # -------------------------------------------------
        # Определяем общий bbox группы
        # -------------------------------------------------

        left = top = right = bottom = None

        for layer in layers:

            layer.clip_alpha_to_original_bbox()

            alpha = np.asarray(layer.alpha)

            ys, xs = np.where(alpha > 0)

            if len(xs) == 0:
                continue

            layer_left = int(layer.x + xs.min())
            layer_top = int(layer.y + ys.min())
            layer_right = int(layer.x + xs.max()) + 1
            layer_bottom = int(layer.y + ys.max()) + 1

            if left is None:
                left = layer_left
                top = layer_top
                right = layer_right
                bottom = layer_bottom
            else:
                left = min(left, layer_left)
                top = min(top, layer_top)
                right = max(right, layer_right)
                bottom = max(bottom, layer_bottom)

        if left is None:
            QMessageBox.information(self, "Save Group", "Group is completely transparent.")
            return

        width = right - left
        height = bottom - top

        # -------------------------------------------------
        # Собираем группу
        # -------------------------------------------------

        result = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        # self.layers идут снизу вверх,
        # поэтому сохраняем этот порядок
        for layer in layers:

            alpha = np.asarray(layer.alpha)
            ys, xs = np.where(alpha > 0)

            if len(xs) == 0:
                continue

            layer_left = int(xs.min())
            layer_top = int(ys.min())
            layer_right = int(xs.max()) + 1
            layer_bottom = int(ys.max()) + 1

            rgba = layer.rgba().crop(
                (
                    layer_left,
                    layer_top,
                    layer_right,
                    layer_bottom
                )
            )

            paste_x = int(layer.x + layer_left - left)
            paste_y = int(layer.y + layer_top - top)

            result.alpha_composite(rgba, (paste_x, paste_y))

        filename = self.get_group_save_name(group)
        path = os.path.join(project_dir, filename + ".png")

        self._save_image(result, path, x=left, y=top, k='group')
