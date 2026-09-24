################################################################################
## Layer

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMenu,
    QPushButton,
    QWidget,
    QLineEdit,
)

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

            corner_label = QLabel("🔒")
            corner_label.setStyleSheet("color: #888888; font-weight: bold;")
            layout.addSpacing(6)
            layout.addWidget(corner_label)
            layout.addSpacing(1)

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

        self.opacity = QLabel("")
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

        layout.addWidget(self.eye_button)
        layout.addSpacing(2)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.name_edit, 1)
        layout.addWidget(self.opacity)

        if index != 0:
            layout.addWidget(self.tag_button)
            layout.addWidget(self.copy_button)

        layout.addWidget(self.save_button)

        self.update_appearance()
        self.update_tag_button()


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

    def update_appearance(self):
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
