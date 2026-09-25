################################################################################
## Layer

import io
import uuid

import numpy as np
from PIL import Image, ImageOps

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QGraphicsItem


class LayerGroup():

    def __init__(self, name="Group", group_id=None):
        self.id = group_id or str(uuid.uuid4())
        self._name = ""
        self.name = name
        self.visible = True
        self.expanded = True
        self.tag = None

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name.replace(" ", "_").strip()


class Layer():

    def __init__(self,
            name,
            image=None,
            x=0,
            y=0,
            alpha=None,
            visible=True,
            layer_id=None,
            original_bbox=None,
            opacity=100,
            tag=None,
            mode='image',
            fill_color=None,
            width=None,
            height=None):

        self.id = layer_id or str(uuid.uuid4())
        self.group_id = None

        self._name = ""

        self.mode = mode
        self.name = name
        self.x = x
        self.y = y

        self.tag = tag if tag in [None, "HQ", "MQ", "LQ", "SQ"] else None

        # Собственный цвет слоя
        if mode == 'image':
            self._image = image.convert("RGB")
            self.fill_color = None
            self.width = self.image.width
            self.height = self.image.height

            # Собственная прозрачностость
            if alpha:
                self._content_alpha = alpha.convert("L").copy()
            else:
                self._content_alpha = Image.new("L", self.size, 255)

            # Изменяемая прозрачность
            self.alpha = self.content_alpha.copy()

        # Заливка цветом
        elif mode == 'solid':
            self._image = None
            self.fill_color = tuple(fill_color) if fill_color else (255, 255, 255)

            if width is None or height is None:
                raise Exception(f'Solid mode requires `width` and `height` to be defined.')

            self.width = width
            self.height = height
            self._content_alpha = None

            # Изменяемая прозрачность
            self.alpha = alpha.copy() if alpha else self.content_alpha.copy()

        # Та же прозрачность, но в numpy
        self.content_alpha_array = np.asarray(self.content_alpha, dtype=np.uint8)

        self.visible = visible
        self.opacity = max(0, min(100, int(opacity)))

        self.item = None
        self.list_item = None
        self.eye_button = None

        self.preview_qimage = None
        self.preview_rgb = None

        self.preview_normal_qimage = None
        self.preview_mask_qimage = None

        # Encoded data caches
        self.image_cache = None
        self.image_dirty = True

        self.mask_dirty = False

        if original_bbox is not None:
            self._original_visible_bbox = tuple(original_bbox)

        else:
            alpha_array = np.asarray(self.content_alpha)

            ys, xs = np.nonzero(alpha_array > 0)

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

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name.replace(" ", "_").strip()

    @property
    def image(self):
        if self.is_image:
            return self._image
        elif not self._image:
            self._image = Image.new("RGB", self.size, self.fill_color)
        return self._image

    @image.setter
    def image(self, image):
        self._image = image
        # if self.is_image:
        # else:
        #     self._image = None

    @property
    def content_alpha(self):
        if self.is_image:
            return self._content_alpha
        elif not self._content_alpha:
            self._content_alpha = Image.new("L", self.size, 255)
        return self._content_alpha

    @content_alpha.setter
    def content_alpha(self, alpha):
        self._content_alpha = alpha
        # if self.is_image:
        # else:
        #     self._content_alpha = None

    @property
    def size(self):
        return (self.width, self.height)

    @property
    def is_solid(self):
        return self.mode == 'solid'

    @property
    def is_image(self):
        return self.mode == 'image'

    def copy(self):
        """
        Return layer copy.
        """

        if self.is_solid:
            layer = Layer(
                name=f"{self.name} copy",
                image=None,
                x=self.x,
                y=self.y,
                alpha=self.alpha.copy(),
                visible=self.visible,
                original_bbox=self._original_visible_bbox,
                opacity=self.opacity,
                tag=self.tag,

                mode="solid",
                fill_color=self.fill_color,
                width=self.width,
                height=self.height,
            )

        else:
            layer = Layer(
                name=f"{self.name} copy",
                image=self.image.copy(),
                x=self.x,
                y=self.y,
                alpha=self.alpha.copy(),
                visible=self.visible,
                original_bbox=self._original_visible_bbox,
                opacity=self.opacity,
                tag=self.tag,

                mode="image",
            )

        layer.group_id = self.group_id

        return layer


    def rgba(self):
        """
        Возвращает полноценное RGBA изображение.

        ВНИМАНИЕ:
        для solid-слоя этот метод создаёт большой массив.
        Поэтому использовать его только там, где действительно
        нужен полноценный PIL Image.
        """

        if self.is_solid:
            img = Image.new("RGB", (self.width, self.height), self.fill_color)
        else:
            img = self.image.copy()

        alpha = self.alpha.copy()

        if self.opacity != 100:
            alpha = alpha.point(lambda a: int(a * self.opacity / 100))

        img.putalpha(alpha)

        return img


    def invert_alpha(self):
        self.alpha = ImageOps.invert(self.alpha)
        self.mask_dirty = True
        self.recalculate_content_bbox()


    def original_visible_bbox(self):
        return self._original_visible_bbox


    def visible_bbox(self):
        return self.content_bbox


    def visible_bounds(self):
        if self.content_bbox is None:
            return None

        x0, y0, x1, y1 = self.content_bbox

        return (self.x + x0, self.y + y0, x1 - x0, y1 - y0)


    def recalculate_content_bbox(self):
        alpha = np.asarray(self.alpha)

        rows = np.any(alpha > 0, axis=1)
        cols = np.any(alpha > 0, axis=0)

        if not rows.any():
            self.content_bbox = None
            return

        y0 = np.argmax(rows)
        y1 = len(rows) - np.argmax(rows[::-1])

        x0 = np.argmax(cols)
        x1 = len(cols) - np.argmax(cols[::-1])

        self.content_bbox = (
            int(x0),
            int(y0),
            int(x1),
            int(y1),
        )


    def get_image_data(self):

        if self.image_cache is None or self.image_dirty:
            buf = io.BytesIO()

            self.image.save(buf, "PNG", compress_level=1, optimize=False)
            self.image_cache = buf.getvalue()
            self.image_dirty = False

        return self.image_cache


    def clip_alpha_to_original_bbox(self):
        bbox = self.original_visible_bbox()

        if bbox is None:
            self.alpha = Image.new("L", self.size, 0)
            return

        ox0, oy0, ox1, oy1 = bbox

        alpha = np.asarray(self.alpha, dtype=np.uint8).copy()

        alpha[:oy0, :] = 0
        alpha[oy1:, :] = 0
        alpha[:, :ox0] = 0
        alpha[:, ox1:] = 0

        self.alpha = Image.fromarray(alpha, "L")
        self.recalculate_content_bbox()


    def free_memory(self):
        self.image_cache = None
        self.image_dirty = True

        self.preview_qimage = None
        self.preview_rgb = None

        self.preview_normal_qimage = None
        self.preview_mask_qimage = None


class LayerPreviewItem(QGraphicsItem):

    def __init__(self, image):
        super().__init__()

        self.image = image

        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)


    def boundingRect(self):
        return QRectF(0, 0, self.image.width() if self.image else 1, self.image.height() if self.image else 1)


    def paint(self, painter, option, widget=None):

        if not self.image:
            return

        exposed = option.exposedRect

        if exposed.isEmpty():
            return

        rect = exposed.intersected(self.boundingRect())

        if rect.isEmpty():
            return

        painter.drawImage(rect, self.image, rect)


    def set_image(self, image):

        if image is self.image:
            self.update()
            return

        self.prepareGeometryChange()
        self.image = image

        self.update()


    def update_region(self, patch, x, y):

        if not self.image:
            return

        if patch.isNull():
            return

        painter = QPainter(self.image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(x, y, patch)
        painter.end()

        self.update(QRectF(x, y, patch.width(), patch.height()) )
