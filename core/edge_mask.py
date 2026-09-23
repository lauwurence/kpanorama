################################################################################
## Edge Mask

import numpy as np
from PIL import Image

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QDoubleSpinBox,
    QComboBox,
)

class EdgeMaskDialog(QDialog):

    def __init__(
        self,
        parent=None,
        mode=None,
        percent=None,
        pixels=None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Edge Mask")
        self.setModal(True)
        self.setMinimumWidth(380)

        # ----------------------------------------------------
        # Загружаем последние настройки.
        # ----------------------------------------------------

        settings = QSettings(
            "kPanorama",
            "kPanorama",
        )

        if mode is None:
            mode = settings.value(
                "edge_mask/mode",
                "percent",
                type=str,
            )

        if percent is None:
            percent = settings.value(
                "edge_mask/percent",
                10,
                type=int,
            )

        if pixels is None:
            pixels = settings.value(
                "edge_mask/pixels",
                50,
                type=int,
            )

        layout = QFormLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ----------------------------------------------------
        # Mode
        # ----------------------------------------------------

        self.mode_combo = QComboBox()

        self.mode_combo.addItem(
            "Percents",
            "percent",
        )

        self.mode_combo.addItem(
            "Pixels",
            "pixels",
        )

        index = self.mode_combo.findData(mode)

        if index >= 0:
            self.mode_combo.setCurrentIndex(index)

        layout.addRow(
            "Mode:",
            self.mode_combo,
        )

        # ----------------------------------------------------
        # Percentage
        # ----------------------------------------------------

        self.percent_spin = QDoubleSpinBox()

        self.percent_spin.setRange(
            1,
            100,
        )

        self.percent_spin.setSingleStep(1)
        self.percent_spin.setDecimals(0)
        self.percent_spin.setValue(percent)
        self.percent_spin.setSuffix(" %")

        self.percent_spin.setToolTip(
            "Feather width as a percentage of the "
            "smaller side of the actual content area."
        )

        layout.addRow(
            "Feather:",
            self.percent_spin,
        )

        # ----------------------------------------------------
        # Pixels
        # ----------------------------------------------------

        self.pixels_spin = QDoubleSpinBox()

        self.pixels_spin.setRange(
            0.1,
            10000.0,
        )

        self.pixels_spin.setSingleStep(1)
        self.pixels_spin.setDecimals(0)
        self.pixels_spin.setValue(pixels)
        self.pixels_spin.setSuffix(" px")

        self.pixels_spin.setToolTip(
            "Fixed feather width in pixels."
        )

        layout.addRow(
            "Feather:",
            self.pixels_spin,
        )

        # ----------------------------------------------------
        # Buttons
        # ----------------------------------------------------

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(
            self.save_and_accept
        )

        buttons.rejected.connect(
            self.reject
        )

        layout.addRow(buttons)

        self.mode_combo.currentIndexChanged.connect(
            self.update_mode
        )

        self.update_mode()

    # --------------------------------------------------------
    # Enable only the currently selected value.
    # --------------------------------------------------------

    def update_mode(self):
        mode = self.mode_combo.currentData()

        self.percent_spin.setEnabled(
            mode == "percent"
        )

        self.pixels_spin.setEnabled(
            mode == "pixels"
        )

    # --------------------------------------------------------
    # Save settings and close dialog.
    # --------------------------------------------------------

    def save_and_accept(self):
        settings = QSettings(
            "kPanorama",
            "kPanorama",
        )

        settings.setValue(
            "edge_mask/mode",
            self.mode_combo.currentData(),
        )

        settings.setValue(
            "edge_mask/percent",
            self.percent_spin.value(),
        )

        settings.setValue(
            "edge_mask/pixels",
            self.pixels_spin.value(),
        )

        settings.sync()

        self.accept()

    # --------------------------------------------------------
    # Properties
    # --------------------------------------------------------

    @property
    def mode(self):
        return self.mode_combo.currentData()

    @property
    def percent(self):
        return self.percent_spin.value()

    @property
    def pixels(self):
        return self.pixels_spin.value()


################################################################################
## Action

class EdgeMaskAction():

    def apply_edge_mask(self):
        layer = self.selected_layer()

        if not layer:
            self.status.setText("No layer selected")
            return

        # Фоновый слой не маскируем.
        if layer is self.layers[0]:
            self.status.setText(
                "Background layer cannot be masked"
            )
            return

        layer.clip_alpha_to_original_bbox()

        # ----------------------------------------------------
        # Получаем реальные границы контента.
        #
        # Это особенно важно для больших слоёв вроде:
        #
        # 12000 x 6000
        #
        # когда реальный объект занимает, например:
        #
        # 1000 x 300.
        # ----------------------------------------------------

        bbox = layer.original_visible_bbox()

        if bbox is None:
            self.status.setText(
                "Layer has no visible content"
            )
            return

        x0, y0, x1, y1 = bbox

        content_width = x1 - x0
        content_height = y1 - y0

        if content_width <= 0 or content_height <= 0:
            self.status.setText(
                "Layer has no visible content"
            )
            return

        # ----------------------------------------------------
        # Окно настроек.
        # ----------------------------------------------------

        dialog = EdgeMaskDialog(
            self,
            mode="percent",
            percent=10.0,
            pixels=50.0,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # ----------------------------------------------------
        # Определяем ширину feather.
        #
        # В percentage-режиме используется НЕ размер
        # всего изображения, а размер content bbox.
        # ----------------------------------------------------

        if dialog.mode == "percent":
            feather = (
                dialog.percent / 100.0
                * min(
                    content_width,
                    content_height,
                )
            )
        else:
            feather = dialog.pixels

        if feather <= 0:
            return

        # Feather не может быть больше половины
        # минимальной стороны content bbox.
        #
        # Иначе противоположные edge-зоны начинают
        # перекрываться.
        max_feather = min(
            content_width,
            content_height,
        ) / 2.0

        feather = min(
            feather,
            max_feather,
        )

        if feather <= 0:
            return

        # ----------------------------------------------------
        # Сохраняем исходную alpha целиком для Undo.
        # ----------------------------------------------------

        before = layer.alpha.copy()

        # ----------------------------------------------------
        # Работаем ТОЛЬКО с content bbox.
        # ----------------------------------------------------

        alpha_crop = np.asarray(
            layer.alpha.crop(
                (x0, y0, x1, y1)
            ),
            dtype=np.float32,
        )

        # ----------------------------------------------------
        # Расстояние до границы content bbox.
        #
        # 0             -> край
        # feather       -> полностью непрозрачная область
        # ----------------------------------------------------

        y, x = np.ogrid[
            :content_height,
            :content_width,
        ]

        distance_x = np.minimum(
            x,
            content_width - 1 - x,
        )

        distance_y = np.minimum(
            y,
            content_height - 1 - y,
        )

        distance = np.minimum(
            distance_x,
            distance_y,
        ).astype(np.float32)

        # ----------------------------------------------------
        # Нормализуем расстояние.
        # ----------------------------------------------------

        t = np.clip(
            distance / feather,
            0.0,
            1.0,
        )

        # Smoothstep:
        #
        # 0 -> полностью прозрачно
        # 1 -> исходная alpha
        #
        mask = t * t * (
            3.0 - 2.0 * t
        )

        # ----------------------------------------------------
        # Маска только уменьшает существующую alpha.
        #
        # Поэтому:
        #
        # new_alpha <= old_alpha
        #
        # Прозрачные пиксели никогда не станут
        # непрозрачными.
        # ----------------------------------------------------

        new_alpha_crop = np.floor(
            alpha_crop * mask
        ).astype(np.uint8)

        # ----------------------------------------------------
        # Возвращаем обработанный bbox обратно
        # в полный alpha-канал.
        # ----------------------------------------------------

        full_alpha = np.asarray(
            layer.alpha,
            dtype=np.uint8,
        ).copy()

        full_alpha[
            y0:y1,
            x0:x1,
        ] = new_alpha_crop

        after = Image.fromarray(
            full_alpha,
            mode="L",
        )

        # ----------------------------------------------------
        # Ничего не изменилось.
        # ----------------------------------------------------

        if np.array_equal(
            np.asarray(before),
            np.asarray(after),
        ):
            self.status.setText(
                "Edge mask made no changes"
            )
            return

        # ----------------------------------------------------
        # Применяем.
        # ----------------------------------------------------

        layer.alpha = after
        layer.alpha_dirty = True
        layer.recalculate_content_bbox()

        index = self.layers.index(layer)

        self.push_undo({
            "type": "edge_mask",
            "index": index,
            "before": before,
            "after": after,
        })

        self.update_layer_preview(layer)

        self.update_history_buttons()
        self.update_project_stats()
        self.update_window_title()
        self.view.viewport().update()

        self.status.setText(
            "Edge mask applied "
            f"({feather:.1f}px feather)"
        )
