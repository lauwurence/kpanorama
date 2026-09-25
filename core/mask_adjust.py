################################################################################
## Mask Adjust

import numpy as np
from PIL import Image
from scipy import ndimage

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QDoubleSpinBox,
    QCheckBox,
)


class MaskAdjustDialog(QDialog):

    def __init__(
        self,
        parent=None,
        offset=0,
        contrast=0.0,
        black_point=0,
        white_point=255,
        gamma=1.0,
        blur=0.0,
        sharpen=0.0,
        invert=False,
    ):
        super().__init__(parent)

        self.setWindowTitle("Mask Adjust")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QFormLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ---------------------------------------------------------
        # Offset
        # ---------------------------------------------------------

        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-255.0, 255.0)
        self.offset_spin.setSingleStep(1.0)
        self.offset_spin.setDecimals(0)
        self.offset_spin.setValue(offset)
        self.offset_spin.setSuffix("")
        self.offset_spin.setToolTip("Add or subtract alpha from the entire mask.")

        layout.addRow("Offset:", self.offset_spin)

        # ---------------------------------------------------------
        # Contrast
        # ---------------------------------------------------------

        self.contrast_spin = QDoubleSpinBox()
        self.contrast_spin.setRange(-100.0, 100.0)
        self.contrast_spin.setSingleStep(5.0)
        self.contrast_spin.setDecimals(0)
        self.contrast_spin.setValue(contrast)
        self.contrast_spin.setSuffix(" %")
        self.contrast_spin.setToolTip("Increase or decrease contrast around 50% opacity.")

        layout.addRow("Contrast:", self.contrast_spin)

        # ---------------------------------------------------------
        # Black point
        # ---------------------------------------------------------

        self.black_spin = QDoubleSpinBox()
        self.black_spin.setRange(0.0, 254.0)
        self.black_spin.setSingleStep(1.0)
        self.black_spin.setDecimals(0)
        self.black_spin.setValue(black_point)

        self.black_spin.setToolTip("Pixels at or below this value become fully transparent.")

        layout.addRow("Black point:", self.black_spin)

        # ---------------------------------------------------------
        # White point
        # ---------------------------------------------------------

        self.white_spin = QDoubleSpinBox()
        self.white_spin.setRange(1.0, 255.0)
        self.white_spin.setSingleStep(1.0)
        self.white_spin.setDecimals(0)
        self.white_spin.setValue(white_point)

        self.white_spin.setToolTip("Pixels at or above this value become fully opaque.")

        layout.addRow("White point:", self.white_spin)

        # ---------------------------------------------------------
        # Gamma
        # ---------------------------------------------------------

        self.gamma_spin = QDoubleSpinBox()
        self.gamma_spin.setRange(0.1, 5.0)
        self.gamma_spin.setSingleStep(0.1)
        self.gamma_spin.setDecimals(2)
        self.gamma_spin.setValue(gamma)

        self.gamma_spin.setToolTip("Adjust the middle tones of the mask.")

        layout.addRow("Gamma:", self.gamma_spin)

        # ---------------------------------------------------------
        # Blur
        # ---------------------------------------------------------

        self.blur_spin = QDoubleSpinBox()
        self.blur_spin.setRange(0.0, 100.0)
        self.blur_spin.setSingleStep(0.5)
        self.blur_spin.setDecimals(1)
        self.blur_spin.setValue(blur)
        self.blur_spin.setSuffix(" px")

        self.blur_spin.setToolTip("Gaussian blur applied to the mask.")

        layout.addRow("Blur:", self.blur_spin)

        # ---------------------------------------------------------
        # Sharpen
        # ---------------------------------------------------------

        self.sharpen_spin = QDoubleSpinBox()
        self.sharpen_spin.setRange(0.0, 10.0)
        self.sharpen_spin.setSingleStep(0.25)
        self.sharpen_spin.setDecimals(2)
        self.sharpen_spin.setValue(sharpen)

        self.sharpen_spin.setToolTip("Increase local contrast and sharpen mask edges.")

        layout.addRow("Sharpen:", self.sharpen_spin)

        # ---------------------------------------------------------
        # Invert
        # ---------------------------------------------------------

        self.invert_check = QCheckBox("Invert mask")
        self.invert_check.setChecked(invert)

        layout.addRow("", self.invert_check)

        # ---------------------------------------------------------
        # Buttons
        # ---------------------------------------------------------

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.save_and_accept)
        buttons.rejected.connect(self.reject)

        layout.addRow(buttons)

    @property
    def offset(self):
        return self.offset_spin.value()

    @property
    def contrast(self):
        return self.contrast_spin.value()

    @property
    def black_point(self):
        return self.black_spin.value()

    @property
    def white_point(self):
        return self.white_spin.value()

    @property
    def gamma(self):
        return self.gamma_spin.value()

    @property
    def blur(self):
        return self.blur_spin.value()

    @property
    def sharpen(self):
        return self.sharpen_spin.value()

    @property
    def invert(self):
        return self.invert_check.isChecked()

    def save_and_accept(self):
        self.accept()


################################################################################
## Action

class MaskAdjustAction:


    def adjust_mask(self):

        layer = self.selected_layer()

        if not layer:
            self.status.setText("No layer selected")
            return

        if layer is self.layers[0]:
            self.status.setText("Background layer cannot be adjusted")
            return

        layer.clip_alpha_to_original_bbox()

        if layer.original_visible_bbox() is None:
            self.status.setText("Layer has no visible content")
            return

        dialog = MaskAdjustDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        before = layer.alpha.copy()

        alpha = np.asarray(layer.alpha, dtype=np.float32)

        # ---------------------------------------------------------
        # Offset
        # ---------------------------------------------------------

        alpha += dialog.offset

        alpha = np.clip(
            alpha,
            0.0,
            255.0,
        )

        # ---------------------------------------------------------
        # Contrast
        #
        # 0%   = без изменений
        # 100% = сильный контраст
        # -100% = полностью плоская маска
        # ---------------------------------------------------------

        contrast = dialog.contrast / 100.0

        if contrast != 0:

            if contrast > 0:
                factor = 1.0 + contrast * 4.0
            else:
                factor = 1.0 + contrast

            alpha = (
                (alpha - 127.5) * factor
                + 127.5
            )

            alpha = np.clip(
                alpha,
                0.0,
                255.0,
            )

        # ---------------------------------------------------------
        # Levels
        # ---------------------------------------------------------

        black = dialog.black_point
        white = dialog.white_point

        if white <= black:
            white = black + 1.0

        alpha = (
            (alpha - black)
            / (white - black)
            * 255.0
        )

        alpha = np.clip(
            alpha,
            0.0,
            255.0,
        )

        # ---------------------------------------------------------
        # Gamma
        # ---------------------------------------------------------

        gamma = dialog.gamma

        if gamma != 1.0:

            normalized = alpha / 255.0

            alpha = (
                np.power(
                    normalized,
                    gamma,
                )
                * 255.0
            )

        # ---------------------------------------------------------
        # Blur
        # ---------------------------------------------------------

        if dialog.blur > 0:

            alpha = ndimage.gaussian_filter(
                alpha,
                sigma=dialog.blur,
            )

        # ---------------------------------------------------------
        # Sharpen
        # ---------------------------------------------------------

        if dialog.sharpen > 0:

            blurred = ndimage.gaussian_filter(
                alpha,
                sigma=1.0,
            )

            alpha = (
                alpha
                + (alpha - blurred) * dialog.sharpen
            )

        # ---------------------------------------------------------
        # Invert
        # ---------------------------------------------------------

        if dialog.invert:
            alpha = 255.0 - alpha

        # ---------------------------------------------------------
        # Финальное ограничение
        # ---------------------------------------------------------

        alpha = np.clip(
            alpha,
            0.0,
            255.0,
        ).astype(np.uint8)

        after = Image.fromarray(alpha, mode="L")

        # ---------------------------------------------------------
        # Ничего не изменилось
        # ---------------------------------------------------------

        if np.array_equal(np.asarray(before), np.asarray(after)):
            self.status.setText("Mask Adjust made no changes")
            return

        # ---------------------------------------------------------
        # Применяем
        # ---------------------------------------------------------

        layer.alpha = after
        layer.recalculate_content_bbox()

        index = self.layers.index(layer)

        # ---------------------------------------------------------
        # Undo
        # ---------------------------------------------------------

        self.push_undo({
            "type": "mask_adjust",
            "index": index,
            "before": before,
            "after": after,
        })

        # ---------------------------------------------------------
        # Обновление UI
        # ---------------------------------------------------------

        self.update_layer_preview(layer)

        self.update_history_buttons()
        self.update_project_stats()
        self.update_window_title()

        self.view.viewport().update()

        self.status.setText(
            f"Mask Adjust applied "
            f"(offset {dialog.offset:.1f}, "
            f"contrast {dialog.contrast:.1f}%, "
            f"levels {dialog.black_point:.0f}-{dialog.white_point:.0f}, "
            f"gamma {dialog.gamma:.2f}, "
            f"blur {dialog.blur:.1f}px, "
            f"sharpen {dialog.sharpen:.2f})"
        )
