
import io
import uuid

import numpy as np
from PIL import Image

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import (
    QPainter,
)
from PyQt6.QtWidgets import (
    QGraphicsItem
)


class Layer:

    def __init__(
        self,
        name,
        image,
        x=0,
        y=0,
        alpha=None,
        visible=True,
        layer_id=None,
        original_bbox=None,
    ):
        self.id = layer_id or str(uuid.uuid4())

        self.name = name
        self.image = image.convert("RGB")
        self.x = x
        self.y = y

        self.content_alpha = (
            alpha.convert("L").copy()
            if alpha
            else Image.new(
                "L",
                self.image.size,
                255,
            )
        )

        self.alpha = self.content_alpha.copy()

        # Неизменяемая исходная alpha
        self.content_alpha_array = np.asarray(
            self.content_alpha,
            dtype=np.float32,
        )

        self.visible = visible

        self.item = None
        self.list_item = None
        self.eye_button = None

        self.preview_qimage = None
        self.preview_rgb = None

        # encoded data caches
        self.image_cache = None
        self.alpha_cache = None
        self.content_alpha_cache = None

        self.image_dirty = True
        self.alpha_dirty = True
        self.content_alpha_dirty = True

        if original_bbox is not None:
            self._original_visible_bbox = tuple(
                original_bbox
            )
        else:
            alpha_array = np.asarray(
                self.content_alpha
            )

            ys, xs = np.nonzero(
                alpha_array > 0
            )

            if len(xs):
                self._original_visible_bbox = (
                    int(xs.min()),
                    int(ys.min()),
                    int(xs.max()) + 1,
                    int(ys.max()) + 1,
                )
            else:
                self._original_visible_bbox = None

        self.recalculate_content_bbox()

    def rgba(self):
        img = self.image.copy()
        img.putalpha(self.alpha)
        return img

    def get_content_alpha_array(self):
        if not hasattr(self, "content_alpha_array"):
            self.content_alpha_array = np.asarray(
                self.content_alpha,
                dtype=np.uint8,
            )

        return self.content_alpha_array

    def image_bounds(self):
        return (
            self.x,
            self.y,
            self.image.width,
            self.image.height,
        )

    def original_visible_bbox(self):
        return self._original_visible_bbox

    def visible_bbox(self):
        return self.content_bbox

    def visible_bounds(self):
        if self.content_bbox is None:
            return None

        x0, y0, x1, y1 = self.content_bbox

        return (
            self.x + x0,
            self.y + y0,
            x1 - x0,
            y1 - y0,
        )

    def update_content_bbox(self, rect):
        x0, y0, x1, y1 = rect

        if self.content_bbox is None:
            self.content_bbox = (
                x0,
                y0,
                x1,
                y1,
            )
            return

        bx0, by0, bx1, by1 = self.content_bbox

        self.content_bbox = (
            min(bx0, x0),
            min(by0, y0),
            max(bx1, x1),
            max(by1, y1),
        )

    def recalculate_content_bbox(self):
        alpha = np.asarray(
            self.alpha,
            dtype=np.uint8,
        )

        ys, xs = np.nonzero(alpha)

        if len(xs) == 0:
            self.content_bbox = None
            return

        self.content_bbox = (
            int(xs.min()),
            int(ys.min()),
            int(xs.max()) + 1,
            int(ys.max()) + 1,
        )


    def get_image_data(self):
        if self.image_cache is None or self.image_dirty:
            buf = io.BytesIO()

            self.image.save(
                buf,
                "PNG",
                compress_level=1,
            )

            self.image_cache = buf.getvalue()
            self.image_dirty = False

        return self.image_cache


    def get_alpha_data(self):
        if self.alpha_cache is None or self.alpha_dirty:
            buf = io.BytesIO()

            self.alpha.save(
                buf,
                "PNG",
                compress_level=1,
            )

            self.alpha_cache = buf.getvalue()
            self.alpha_dirty = False

        return self.alpha_cache


    def get_content_alpha_data(self):
        if (
            self.content_alpha_cache is None
            or self.content_alpha_dirty
        ):
            content_alpha_array = np.asarray(
                self.content_alpha
            )

            # Полностью непрозрачную маску
            # вообще не нужно сохранять.
            if np.all(
                content_alpha_array == 255
            ):
                self.content_alpha_cache = b""
            else:
                buf = io.BytesIO()

                self.content_alpha.save(
                    buf,
                    "PNG",
                    compress_level=1,
                )

                self.content_alpha_cache = (
                    buf.getvalue()
                )

            self.content_alpha_dirty = False

        return self.content_alpha_cache

class LayerPreviewItem(QGraphicsItem):
    def __init__(self, image):
        super().__init__()

        self.image = image

        self.setAcceptedMouseButtons(
            Qt.MouseButton.NoButton
        )

    def boundingRect(self):
        return QRectF(
            0,
            0,
            self.image.width(),
            self.image.height(),
        )

    def paint(
        self,
        painter,
        option,
        widget=None,
    ):
        exposed = option.exposedRect

        if exposed.isEmpty():
            return

        rect = exposed.intersected(
            self.boundingRect()
        )

        if rect.isEmpty():
            return

        painter.drawImage(
            rect,
            self.image,
            rect,
        )

    def set_image(self, image):
        if image is self.image:
            self.update()
            return

        self.prepareGeometryChange()

        self.image = image

        self.update()

    def update_region(
        self,
        patch,
        x,
        y,
    ):
        if patch.isNull():
            return

        painter = QPainter(self.image)

        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Source
        )

        painter.drawImage(
            x,
            y,
            patch,
        )

        painter.end()

        self.update(
            QRectF(
                x,
                y,
                patch.width(),
                patch.height(),
            )
        )