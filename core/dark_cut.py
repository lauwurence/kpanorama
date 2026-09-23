################################################################################
## Dark Cut

import numpy as np
from PIL import Image
from scipy import ndimage

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QDoubleSpinBox,
)

################################################################################
## Dark Cut

class DarkCutDialog(QDialog):

    def __init__(
        self,
        parent=None,
        strength_percent=None,
        threshold=None,
        blur=None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Dark Cut")
        self.setModal(True)
        self.setMinimumWidth(380)

        settings = QSettings("kPanorama", "kPanorama")

        if strength_percent is None:
            strength_percent = settings.value(
                "dark_cut/strength_percent",
                100,
                type=int,
            )

        if threshold is None:
            threshold = settings.value(
                "dark_cut/threshold",
                200,
                type=int,
            )

        if blur is None:
            blur = settings.value(
                "dark_cut/blur",
                0.0,
                type=float,
            )

        layout = QFormLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.strength_spin = QDoubleSpinBox()
        self.strength_spin.setRange(0, 100)
        self.strength_spin.setSingleStep(5)
        self.strength_spin.setDecimals(0)
        self.strength_spin.setValue(strength_percent)
        self.strength_spin.setSuffix(" %")
        self.strength_spin.setToolTip(
            "Maximum alpha reduction on a completely black background."
        )

        layout.addRow(
            "Strength:",
            self.strength_spin,
        )

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(1, 255)
        self.threshold_spin.setSingleStep(5)
        self.threshold_spin.setDecimals(0)
        self.threshold_spin.setValue(threshold)
        self.threshold_spin.setSuffix(" RGB")
        self.threshold_spin.setToolTip(
            "Background brightness above this value is not affected."
        )

        layout.addRow(
            "Brightness threshold:",
            self.threshold_spin,
        )

        self.blur_spin = QDoubleSpinBox()
        self.blur_spin.setRange(0.0, 100.0)
        self.blur_spin.setSingleStep(0.5)
        self.blur_spin.setDecimals(1)
        self.blur_spin.setValue(blur)
        self.blur_spin.setSuffix(" px")
        self.blur_spin.setToolTip(
            "Blur the background brightness map before calculating transparency."
        )

        layout.addRow(
            "Blur:",
            self.blur_spin,
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.save_and_accept)
        buttons.rejected.connect(self.reject)

        layout.addRow(buttons)

    @property
    def strength_percent(self):
        return self.strength_spin.value()

    @property
    def threshold(self):
        return self.threshold_spin.value()

    @property
    def blur(self):
        return self.blur_spin.value()

    def save_and_accept(self):
        settings = QSettings("kPanorama", "kPanorama")

        settings.setValue(
            "dark_cut/strength_percent",
            self.strength_spin.value(),
        )

        settings.setValue(
            "dark_cut/threshold",
            self.threshold_spin.value(),
        )

        settings.setValue(
            "dark_cut/blur",
            self.blur_spin.value(),
        )

        settings.sync()

        self.accept()


################################################################################
## Action

class DarkCutAction():

    def apply_dark_cut(self):

        layer = self.selected_layer()

        if not layer:
            self.status.setText("No layer selected")
            return

        if layer is self.layers[0]:
            self.status.setText(
                "Background layer cannot be dark cut"
            )
            return

        layer.clip_alpha_to_original_bbox()

        bbox = layer.original_visible_bbox()

        if bbox is None:
            self.status.setText(
                "Layer has no visible content"
            )
            return

        x0, y0, x1, y1 = bbox

        width = x1 - x0
        height = y1 - y0

        if width <= 0 or height <= 0:
            return

        # ---------------------------------------------------------
        # Диалог настроек
        # ---------------------------------------------------------

        dialog = DarkCutDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        strength = dialog.strength_percent / 100.0
        threshold = dialog.threshold
        blur = dialog.blur

        # ---------------------------------------------------------
        # Координаты слоя на canvas
        # ---------------------------------------------------------

        layer_x = int(round(layer.x))
        layer_y = int(round(layer.y))

        canvas_x0 = layer_x + x0
        canvas_y0 = layer_y + y0
        canvas_x1 = layer_x + x1
        canvas_y1 = layer_y + y1

        # ---------------------------------------------------------
        # Ограничиваем область canvas
        # ---------------------------------------------------------

        crop_x0 = max(0, canvas_x0)
        crop_y0 = max(0, canvas_y0)
        crop_x1 = min(self.canvas_width, canvas_x1)
        crop_y1 = min(self.canvas_height, canvas_y1)

        if crop_x1 <= crop_x0 or crop_y1 <= crop_y0:
            self.status.setText(
                "Layer content is outside the canvas"
            )
            return

        # ---------------------------------------------------------
        # Перевод canvas-координат обратно в координаты слоя
        # ---------------------------------------------------------

        local_x0 = crop_x0 - layer_x
        local_y0 = crop_y0 - layer_y
        local_x1 = crop_x1 - layer_x
        local_y1 = crop_y1 - layer_y

        # ---------------------------------------------------------
        # Берём соответствующий участок фона.
        #
        # Используем ту же схему, что Smart Mask.
        # ---------------------------------------------------------

        background = self.layers[0]

        background_crop = background.image.crop(
            (
                crop_x0,
                crop_y0,
                crop_x1,
                crop_y1,
            )
        )

        background_rgb = np.asarray(
            background_crop,
            dtype=np.float32,
        )

        # ---------------------------------------------------------
        # Яркость каждого пикселя фона.
        #
        # 0   = чёрный
        # 255 = белый
        # ---------------------------------------------------------

        luminance = (
            0.2126 * background_rgb[:, :, 0]
            + 0.7152 * background_rgb[:, :, 1]
            + 0.0722 * background_rgb[:, :, 2]
        )

        if blur > 0:
            luminance = ndimage.gaussian_filter(
                luminance,
                sigma=blur,
            )

        # ---------------------------------------------------------
        # Насколько фон темнее threshold.
        #
        # Светлее threshold:
        #     darkness = 0
        #
        # Чёрный:
        #     darkness = 1
        # ---------------------------------------------------------

        darkness = np.clip(
            (threshold - luminance) / threshold,
            0.0,
            1.0,
        )

        # ---------------------------------------------------------
        # Сила воздействия.
        #
        # Например strength = 0.75:
        #
        # белый фон  -> 0% уменьшения alpha
        # чёрный фон -> 75% уменьшения alpha
        # ---------------------------------------------------------

        reduction = darkness * strength

        # ---------------------------------------------------------
        # Исходная alpha слоя
        # ---------------------------------------------------------

        source_alpha = np.asarray(
            layer.alpha.crop(
                (
                    local_x0,
                    local_y0,
                    local_x1,
                    local_y1,
                )
            ),
            dtype=np.float32,
        )

        # ---------------------------------------------------------
        # Уменьшаем alpha точечно.
        # ---------------------------------------------------------

        generated_alpha = (
            source_alpha * (1.0 - reduction)
        )

        generated_alpha = np.clip(
            generated_alpha,
            0,
            255,
        ).astype(np.uint8)

        # Невидимые пиксели остаются невидимыми.
        generated_alpha[
            source_alpha <= 0
        ] = 0

        # ---------------------------------------------------------
        # Сохраняем состояние для Undo.
        # ---------------------------------------------------------

        before = layer.alpha.copy()

        full_alpha = np.asarray(
            layer.alpha,
            dtype=np.uint8,
        ).copy()

        full_alpha[
            local_y0:local_y1,
            local_x0:local_x1,
        ] = generated_alpha

        after = Image.fromarray(
            full_alpha,
            mode="L",
        )

        # ---------------------------------------------------------
        # Проверяем, были ли изменения.
        # ---------------------------------------------------------

        if np.array_equal(
            np.asarray(before),
            np.asarray(after),
        ):
            self.status.setText(
                "Dark Cut made no changes"
            )
            return

        # ---------------------------------------------------------
        # Применяем новую alpha
        # ---------------------------------------------------------

        layer.alpha = after
        layer.alpha_dirty = True
        layer.recalculate_content_bbox()

        index = self.layers.index(layer)

        # ---------------------------------------------------------
        # Undo
        # ---------------------------------------------------------

        self.push_undo({
            "type": "dark_cut",
            "index": index,
            "before": before,
            "after": after,
        })

        # ---------------------------------------------------------
        # Обновляем интерфейс
        # ---------------------------------------------------------

        self.update_layer_preview(layer)

        self.update_history_buttons()
        self.update_project_stats()
        self.update_window_title()

        self.view.viewport().update()

        self.status.setText(
            f"Dark Cut applied "
            f"(strength {dialog.strength_percent:.1f}%, "
            f"threshold {dialog.threshold:.1f}, "
            f"blur {dialog.blur:.1f}px)"
        )