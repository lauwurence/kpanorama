################################################################################
## Smart Mask

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

class SmartMaskDialog(QDialog):

    def __init__(self, parent=None, threshold=None, softness_percent=None, min_object_size_percent=None, cleanup_percent=None):
        super().__init__(parent)

        self.setWindowTitle("Smart Mask")
        self.setModal(True)
        self.setMinimumWidth(380)

        settings = QSettings("kPanorama", "kPanorama")

        if threshold is None:
            threshold = settings.value("smart_mask/threshold", 3.0, type=float)

        if softness_percent is None:
            softness_percent = settings.value("smart_mask/softness_percent", 10.0, type=float)

        if min_object_size_percent is None:
            min_object_size_percent = settings.value("smart_mask/min_object_size_percent", 1.0, type=float)

        if cleanup_percent is None:
            cleanup_percent = settings.value("smart_mask/cleanup_percent", 0.1, type=float)

        layout = QFormLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 255.0)
        self.threshold_spin.setSingleStep(1.0)
        self.threshold_spin.setDecimals(1)
        self.threshold_spin.setValue(threshold)
        self.threshold_spin.setSuffix(" RGB")
        layout.addRow("Threshold:", self.threshold_spin)

        self.softness_spin = QDoubleSpinBox()
        self.softness_spin.setRange(0.1, 50.0)
        self.softness_spin.setSingleStep(0.5)
        self.softness_spin.setDecimals(1)
        self.softness_spin.setValue(softness_percent)
        self.softness_spin.setSuffix(" %")
        layout.addRow("Edge softness:", self.softness_spin)

        self.min_size_spin = QDoubleSpinBox()
        self.min_size_spin.setRange(0.0, 100.0)
        self.min_size_spin.setSingleStep(0.1)
        self.min_size_spin.setDecimals(2)
        self.min_size_spin.setValue(min_object_size_percent)
        self.min_size_spin.setSuffix(" %")
        layout.addRow("Minimum object size:", self.min_size_spin)

        self.cleanup_spin = QDoubleSpinBox()
        self.cleanup_spin.setRange(0.0, 20.0)
        self.cleanup_spin.setSingleStep(0.1)
        self.cleanup_spin.setDecimals(2)
        self.cleanup_spin.setValue(cleanup_percent)
        self.cleanup_spin.setSuffix(" %")
        self.cleanup_spin.setToolTip("Morphological cleanup size relative to the smaller side of the actual content area.")
        layout.addRow("Mask cleanup:", self.cleanup_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.threshold_spin.setToolTip("How different a pixel must be from the background to be considered part of the character.")
        self.softness_spin.setToolTip("Width of the transparency gradient as a percentage of the smaller side of the actual content area.")
        self.min_size_spin.setToolTip("Minimum detected object size as a percentage of the actual content area.")

    @property
    def threshold(self):
        return self.threshold_spin.value()

    @property
    def softness_percent(self):
        return self.softness_spin.value()

    @property
    def min_object_size_percent(self):
        return self.min_size_spin.value()

    @property
    def cleanup_percent(self):
        return self.cleanup_spin.value()

    def save_and_accept(self):
        settings = QSettings("kPanorama", "kPanorama")
        settings.setValue("smart_mask/threshold", self.threshold_spin.value())
        settings.setValue("smart_mask/softness_percent", self.softness_spin.value())
        settings.setValue("smart_mask/min_object_size_percent", self.min_size_spin.value())
        settings.setValue("smart_mask/cleanup_percent", self.cleanup_spin.value())
        settings.sync()
        self.accept()


################################################################################
## Action

class SmartMaskAction():

    def apply_smart_mask(self):

        layer = self.selected_layer()

        if not layer:
            self.status.setText("No layer selected")
            return

        if layer is self.layers[0]:
            self.status.setText("Background layer cannot be smart masked")
            return

        layer.clip_alpha_to_original_bbox()

        bbox = layer.original_visible_bbox()

        if bbox is None:
            self.status.setText("Layer has no visible content")
            return

        x0, y0, x1, y1 = bbox
        width = x1 - x0
        height = y1 - y0

        if width <= 0 or height <= 0:
            return

        dialog = SmartMaskDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        threshold = dialog.threshold
        softness_percent = dialog.softness_percent
        min_object_size_percent = dialog.min_object_size_percent
        cleanup_percent = dialog.cleanup_percent

        min_side = min(width, height)
        softness = softness_percent / 100.0 * min_side
        softness = min(softness, min_side / 2.0)

        min_object_size = min_object_size_percent / 100.0 * (width * height)

        cleanup = cleanup_percent / 100.0 * min_side
        cleanup = max(1, int(round(cleanup))) if cleanup_percent > 0 else 0

        layer_x = int(round(layer.x))
        layer_y = int(round(layer.y))

        canvas_x0 = layer_x + x0
        canvas_y0 = layer_y + y0
        canvas_x1 = layer_x + x1
        canvas_y1 = layer_y + y1

        crop_x0 = max(0, canvas_x0)
        crop_y0 = max(0, canvas_y0)
        crop_x1 = min(self.canvas_width, canvas_x1)
        crop_y1 = min(self.canvas_height, canvas_y1)

        if crop_x1 <= crop_x0 or crop_y1 <= crop_y0:
            self.status.setText("Layer content is outside the canvas")
            return

        local_x0 = crop_x0 - layer_x
        local_y0 = crop_y0 - layer_y
        local_x1 = crop_x1 - layer_x
        local_y1 = crop_y1 - layer_y

        layer_crop = layer.image.crop((local_x0, local_y0, local_x1, local_y1))
        background = self.layers[0]
        background_crop = background.image.crop((crop_x0, crop_y0, crop_x1, crop_y1))

        layer_rgb = np.asarray(layer_crop, dtype=np.uint8)
        background_rgb = np.asarray(background_crop, dtype=np.uint8)

        difference = np.mean(np.abs(layer_rgb - background_rgb), axis=2)
        character_mask = difference >= threshold

        source_alpha = np.asarray(layer.alpha.crop((local_x0, local_y0, local_x1, local_y1)), dtype=np.uint8)
        character_mask &= source_alpha > 0

        if cleanup > 0:
            structure = ndimage.generate_binary_structure(2, 2)
            character_mask = ndimage.binary_closing(
                character_mask,
                structure=structure,
                iterations=cleanup,
            )
            character_mask = ndimage.binary_opening(
                character_mask,
                structure=structure,
                iterations=cleanup,
            )

        if min_object_size > 0:
            labels, count = ndimage.label(character_mask)
            if count > 0:
                sizes = np.bincount(labels.ravel())
                keep = sizes >= min_object_size
                keep[0] = False
                character_mask = keep[labels]

        if not np.any(character_mask):
            self.status.setText("Character could not be detected")
            return

        character_mask = ndimage.binary_fill_holes(character_mask)

        outside_distance = ndimage.distance_transform_edt(~character_mask)


        if softness <= 0:
            generated_alpha = character_mask.astype(np.float32) * 255.0

        else:
            # ---------------------------------------------------------
            # Расширяем маску перед сглаживанием.
            #
            # Это компенсирует "съедание" границы при feathering:
            # исходный контур остаётся внутри полностью непрозрачной
            # области, а плавный переход начинается уже за ним.
            # ---------------------------------------------------------

            expansion = max(1.0, float(softness)) * 0.25

            # Евклидово расстояние от каждого внешнего пикселя
            # до исходной маски.
            distance_from_mask = ndimage.distance_transform_edt(
                ~character_mask
            )

            # Расширяем маску на softness пикселей.
            expanded_mask = distance_from_mask <= expansion

            # Расстояние наружу уже от расширенной маски.
            outside_distance = ndimage.distance_transform_edt(
                ~expanded_mask
            )

            # Плавный переход.
            t = np.clip(
                outside_distance / softness,
                0.0,
                1.0,
            )

            # Smoothstep.
            smooth = t * t * (3.0 - 2.0 * t)

            generated_alpha = (1.0 - smooth) * 255.0

            # Вся расширенная область полностью непрозрачная.
            generated_alpha[expanded_mask] = 255.0

        generated_alpha = np.minimum(
            generated_alpha,
            source_alpha.astype(np.float32),
        )

        before = layer.alpha.copy()

        full_alpha = np.asarray(
            layer.alpha,
            dtype=np.uint8,
        ).copy()

        full_alpha[
            local_y0:local_y1,
            local_x0:local_x1,
        ] = generated_alpha.astype(np.uint8)

        after = Image.fromarray(
            full_alpha,
            mode="L",
        )

        if np.array_equal(
            np.asarray(before),
            np.asarray(after),
        ):
            self.status.setText("Smart Mask made no changes")
            return

        layer.alpha = after
        layer.recalculate_content_bbox()

        index = self.layers.index(layer)

        self.push_undo({
            "type": "smart_mask",
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
            f"Smart Mask applied "
            f"(threshold {threshold:.1f}, "
            f"softness {softness_percent:.1f}%, "
            f"min object {min_object_size_percent:.2f}%, "
            f"cleanup {cleanup_percent:.2f}%)"
        )
