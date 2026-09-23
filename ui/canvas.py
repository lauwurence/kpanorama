################################################################################
## Canvas

import os

import numpy as np
from PIL import Image

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QRadialGradient, QGuiApplication
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView


class CanvasView(QGraphicsView):

    def __init__(self, window):
        super().__init__()
        self.window = window

        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        self.painting = False
        self.stroke_layer = None
        self.stroke_patches = []
        self.stroke_alpha_start = None
        self.stroke_mask = None

        self.brush_ctrl_locked = False
        self.brush_shift_locked = False
        self.cursor_pos = None

        self.grabbing = False
        self.grab_last_pos = None
        self.resizing_brush = False

        self.brush_resize_start_x = 0
        self.brush_resize_last_x = 0
        self.brush_resize_start_size = 0

        self.brush_hardness_start_y = 0
        self.brush_hardness_start_value = 50.0

        self.adjusting_brush_strength = False
        self.brush_strength_start_x = 0
        self.brush_strength_start_y = 0
        self.brush_strength_start_value = 100

        self.brush_mask = None
        self.brush_mask_key = None

        # Последняя точка для Shift-сглаживания.
        self.last_paint_x = None
        self.last_paint_y = None

        # Последняя точка непрерывного штриха.
        #
        # Отдельные координаты нужны, чтобы интерполяция
        # не конфликтовала с логикой Shift.
        self.last_stroke_x = None
        self.last_stroke_y = None
        self._blur_kernel_cache = {}

    # -------------------------------------------------------------------------
    # Drag & Drop
    # -------------------------------------------------------------------------

    def dragEnterEvent(self, e):
        if not e.mimeData().hasUrls():
            e.ignore()
            return

        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]

        valid_files = [
            path
            for path in files
            if (
                path.lower().endswith(".kpp")
                or path.lower().endswith((
                    ".png", ".jpg", ".jpeg", ".webp",
                    ".bmp", ".tif", ".tiff",
                ))
            )
        ]

        if valid_files:
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if not e.mimeData().hasUrls():
            e.ignore()
            return

        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]

        if any(
            path.lower().endswith(".kpp")
            or path.lower().endswith((
                ".png", ".jpg", ".jpeg", ".webp",
                ".bmp", ".tif", ".tiff",
            ))
            for path in files
        ):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]

        for path in files:
            if not os.path.isfile(path):
                continue

            if path.lower().endswith(".kpp"):
                self.window.load_project_from_path(path)
            else:
                self.window.add_image(path)

        e.acceptProposedAction()

    # -------------------------------------------------------------------------
    # View / Zoom
    # -------------------------------------------------------------------------

    def wheelEvent(self, e):
        old_pos = self.mapToScene(e.position().toPoint())
        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15

        self.scale(factor, factor)

        new_pos = self.mapToScene(e.position().toPoint())
        delta = new_pos - old_pos

        self.translate(delta.x(), delta.y())

        self.window.update_zoom_status()
        self.viewport().update()

        e.accept()

    # -------------------------------------------------------------------------
    # Keyboard
    # -------------------------------------------------------------------------

    def keyPressEvent(self, e):
        # Во время рисования не обрабатываем горячие клавиши,
        # которые могут переключить режим отображения.
        #
        # Сам Ctrl при этом не меняет состояние painting.
        if self.painting:
            e.accept()
            return

        if e.key() == Qt.Key.Key_V and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            clipboard = QGuiApplication.clipboard()
            mime = clipboard.mimeData()

            if mime.hasImage():
                print(mime)

                image = clipboard.image()

                if not image.isNull():
                    self.window.add_image_from_clipboard(image)
                    e.accept()
                    return

        if e.nativeScanCode() == 33 and not e.isAutoRepeat():
            local_pos = self.mapFromGlobal(self.cursor().pos())

            self.resizing_brush = True

            self.brush_resize_last_x = local_pos.x()
            self.brush_resize_start_x = local_pos.x()
            self.brush_resize_start_size = self.window.brush_size

            self.brush_hardness_start_y = local_pos.y()
            self.brush_hardness_start_value = self.window.brush_hardness

            # Shift + F = регулировка силы
            self.adjusting_brush_strength = bool(
                e.modifiers() & Qt.KeyboardModifier.ShiftModifier
            )

            if self.adjusting_brush_strength:
                self.brush_strength_start_x = local_pos.x()
                self.brush_strength_start_y = local_pos.y()
                self.brush_strength_start_value = self.window.brush_strength

                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.SizeAllCursor)

            self.viewport().update()

            e.accept()
            return

        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.nativeScanCode() == 33 and not e.isAutoRepeat():
            self.resizing_brush = False
            self.adjusting_brush_strength = False

            if not self.grabbing:
                self.setCursor(Qt.CursorShape.ArrowCursor)

            self.viewport().update()

            e.accept()
            return

        super().keyReleaseEvent(e)

    # -------------------------------------------------------------------------
    # Mouse
    # -------------------------------------------------------------------------

    def mouseMoveEvent(self, e):
        self.cursor_pos = e.position()
        self.viewport().update()

        # F + движение = размер / жёсткость кисти
        if self.resizing_brush:

            # Shift + F = сила кисти
            if self.adjusting_brush_strength:
                delta_x = e.position().x() - self.brush_strength_start_x
                delta_y = self.brush_strength_start_y - e.position().y()
                delta = delta_x + delta_y

                new_strength = self.brush_strength_start_value + delta * 0.5
                new_strength = max(1, min(100, int(new_strength)))

                self.window.set_brush_strength(new_strength)
                self.viewport().update()
                return

            # Обычный F
            delta_x = e.position().x() - self.brush_resize_last_x

            if delta_x != 0:
                current_size = self.window.brush_size
                scale = max(1.0, current_size / 200.0)
                new_size = max(1, int(current_size + delta_x * scale))

                self.window.set_brush_size(new_size)
                self.brush_resize_last_x = e.position().x()

            delta_y = self.brush_hardness_start_y - e.position().y()
            new_hardness = self.brush_hardness_start_value + delta_y * 0.5
            new_hardness = max(0.0, min(100.0, new_hardness))

            self.window.set_brush_hardness(new_hardness)
            self.viewport().update()
            return

        # СКМ = Grab
        if self.grabbing and self.grab_last_pos is not None:
            delta = e.position() - self.grab_last_pos
            self.grab_last_pos = e.position()

            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )

            return

        # ЛКМ = непрерывная кисть
        if self.painting and self.stroke_layer:
            self.paint_line_to(e.position())
            return

        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        # СКМ = Grab
        if e.button() == Qt.MouseButton.MiddleButton:
            if self.painting:
                e.accept()
                return

            self.grabbing = True
            self.grab_last_pos = e.position()

            self.setCursor(Qt.CursorShape.ClosedHandCursor)

            e.accept()
            return

        # ЛКМ = кисть
        if e.button() == Qt.MouseButton.LeftButton:
            layer = self.window.selected_layer()

            if not layer:
                e.accept()
                return

            if layer is self.window.layers[0]:
                e.accept()
                return

            if layer:
                # Начало мазка.
                self.painting = True

                # Ctrl и Shift фиксируются именно
                # в момент начала мазка.
                self.brush_ctrl_locked = bool(
                    e.modifiers() & Qt.KeyboardModifier.ControlModifier
                )
                self.brush_shift_locked = bool(
                    e.modifiers() & Qt.KeyboardModifier.ShiftModifier
                )

                self.stroke_layer = layer
                self.stroke_patches = []

                self.stroke_alpha_start = np.asarray(
                    layer.alpha,
                    dtype=np.uint8,
                ).copy()

                self.stroke_mask = np.zeros(
                    (layer.alpha.height, layer.alpha.width),
                    dtype=np.float32,
                )

                # Начальная точка непрерывного штриха.
                self.last_stroke_x = e.position().x()
                self.last_stroke_y = e.position().y()

                # Shift использует собственную систему координат.
                self.last_paint_x = None
                self.last_paint_y = None

                self.paint_at(e.position())

                e.accept()
                return

        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):

        # СКМ = Grab
        if e.button() == Qt.MouseButton.MiddleButton:
            if self.painting:
                e.accept()
                return

            self.grabbing = False
            self.grab_last_pos = None

            self.setCursor(Qt.CursorShape.ArrowCursor)

            e.accept()
            return

        # ЛКМ = завершение мазка
        if e.button() == Qt.MouseButton.LeftButton:

            if self.painting:
                self.painting = False

                if self.stroke_layer and self.stroke_patches:
                    self.window.finish_brush_action(
                        self.stroke_layer,
                        self.stroke_patches,
                    )
                    self.stroke_layer.recalculate_content_bbox()

                self.stroke_layer = None
                self.stroke_patches = []

                self.stroke_alpha_start = None
                self.stroke_mask = None

                # Сброс непрерывного штриха.
                self.last_stroke_x = None
                self.last_stroke_y = None

                # Сброс Shift.
                self.last_paint_x = None
                self.last_paint_y = None

                # Снимаем зафиксированные модификаторы.
                self.brush_ctrl_locked = False
                self.brush_shift_locked = False

                self.viewport().update()

                e.accept()
                return

        super().mouseReleaseEvent(e)

    def leaveEvent(self, e):
        self.cursor_pos = None
        self.viewport().update()
        super().leaveEvent(e)

    # -------------------------------------------------------------------------
    # Painting
    # -------------------------------------------------------------------------

    def paint_line_to(self, pos):
        """
        Рисует непрерывный штрих от предыдущей точки до pos.

        mouseMoveEvent не гарантированно приходит для каждого
        пикселя движения мыши. Поэтому между двумя событиями
        добавляются промежуточные отпечатки кисти.
        """
        current_x = pos.x()
        current_y = pos.y()

        if self.last_stroke_x is None or self.last_stroke_y is None:
            self.paint_at(pos)

            self.last_stroke_x = current_x
            self.last_stroke_y = current_y

            return

        start_x = self.last_stroke_x
        start_y = self.last_stroke_y

        dx = current_x - start_x
        dy = current_y - start_y
        distance = np.sqrt(dx * dx + dy * dy)

        # Расстояние между отпечатками.
        #
        # 0.20 диаметра кисти означает, что отпечатки
        # сильно перекрываются и между ними не образуются
        # пустые промежутки.
        step = max(1.0, self.window.brush_size * 0.20)
        steps = max(1, int(np.ceil(distance / step)))

        for i in range(1, steps + 1):
            t = i / steps

            x = start_x + dx * t
            y = start_y + dy * t

            self.paint_at(QPointF(x, y))

        # Сохраняем именно реальную последнюю позицию мыши.
        self.last_stroke_x = current_x
        self.last_stroke_y = current_y

    def paint_at(self, pos):
        layer = self.stroke_layer

        if not layer:
            return

        if layer is self.window.layers[0]:
            return

        if self.stroke_alpha_start is None:
            return

        if self.stroke_mask is None:
            return

        scene_pos = self.mapToScene(int(pos.x()), int(pos.y()))
        s = self.window.preview_scale

        cx = int(scene_pos.x() / s) - layer.x
        cy = int(scene_pos.y() / s) - layer.y

        r = self.window.brush_size

        if r <= 0:
            return

        layer.mask_dirty = True

        # Shift = рисование отдельными отпечатками.
        #
        # Здесь остаётся существующее ограничение частоты
        # нанесения кисти.
        if self.brush_shift_locked:
            if self.last_paint_x is not None and self.last_paint_y is not None:
                dx = cx - self.last_paint_x
                dy = cy - self.last_paint_y

                min_distance = max(2, r // 4)

                if dx * dx + dy * dy < min_distance * min_distance:
                    return

            self.last_paint_x = cx
            self.last_paint_y = cy

        x0 = max(0, cx - r)
        y0 = max(0, cy - r)
        x1 = min(layer.alpha.width, cx + r + 1)
        y1 = min(layer.alpha.height, cy + r + 1)

        if x1 <= x0 or y1 <= y0:
            return

        mask = self.get_brush_mask()

        mx0 = x0 - (cx - r)
        my0 = y0 - (cy - r)
        mx1 = mx0 + (x1 - x0)
        my1 = my0 + (y1 - y0)

        brush_strength = mask[my0:my1, mx0:mx1]
        stroke_mask = self.stroke_mask[y0:y1, x0:x1]

        if self.brush_shift_locked:
            stroke_strength = brush_strength
        else:
            old_mask = stroke_mask.copy()

            np.maximum(
                stroke_mask,
                brush_strength,
                out=stroke_mask,
            )

            if np.array_equal(old_mask, stroke_mask):
                return

            stroke_strength = stroke_mask

        # ==============================================================
        # SHIFT = сглаживание
        # ==============================================================

        if self.brush_shift_locked:
            smooth_radius = max(1, int(round(r * 0.25)))
            blur_radius = max(1, int(np.ceil((smooth_radius / 2.0) * 3.0)))

            # Расширенная область для blur.
            #
            # Она нужна, чтобы blur имел доступ к пикселям
            # за пределами самой кисти.
            sx0 = max(0, x0 - blur_radius)
            sy0 = max(0, y0 - blur_radius)
            sx1 = min(layer.alpha.width, x1 + blur_radius)
            sy1 = min(layer.alpha.height, y1 + blur_radius)

            current_extended = np.asarray(
                layer.alpha.crop((sx0, sy0, sx1, sy1)),
                dtype=np.float32,
            )

            # Blur только небольшой расширенной области.
            smoothed_extended = self.smooth_alpha_numpy(
                current_extended,
                smooth_radius,
            )

            # Возвращаем только область кисти.
            crop_x0 = x0 - sx0
            crop_y0 = y0 - sy0
            crop_x1 = crop_x0 + (x1 - x0)
            crop_y1 = crop_y0 + (y1 - y0)

            smoothed_alpha = smoothed_extended[
                crop_y0:crop_y1,
                crop_x0:crop_x1,
            ]

            current_alpha = current_extended[
                crop_y0:crop_y1,
                crop_x0:crop_x1,
            ]

            result = smoothed_alpha - current_alpha
            result *= stroke_strength
            result += current_alpha

        # ==============================================================
        # CTRL = уменьшение alpha
        # ==============================================================

        elif self.brush_ctrl_locked:
            start_alpha = self.stroke_alpha_start[y0:y1, x0:x1].astype(
                np.float32,
                copy=False,
            )

            result = start_alpha * (1.0 - stroke_mask)

        # ==============================================================
        # ОБЫЧНАЯ КИСТЬ
        # ==============================================================

        else:
            start_alpha = self.stroke_alpha_start[y0:y1, x0:x1].astype(
                np.float32,
                copy=False,
            )

            content = layer.content_alpha_array[y0:y1, x0:x1]

            result = start_alpha + (content - start_alpha) * stroke_mask
            result = np.minimum(result, content)

        result = np.clip(result, 0, 255).astype(np.uint8)

        # ==============================================================
        # Undo patch
        # ==============================================================

        before_array = self.stroke_alpha_start[y0:y1, x0:x1]
        before = Image.fromarray(before_array.copy(), "L")
        after = Image.fromarray(result, "L")

        layer.alpha.paste(after, (x0, y0))

        if not np.array_equal(before_array, result):
            self.stroke_patches.append(
                (
                    (x0, y0, x1, y1),
                    before,
                    after.copy(),
                )
            )

        layer.alpha_dirty = True

        self.window.update_layer_preview_region(
            layer,
            (x0, y0, x1, y1),
        )

    # -------------------------------------------------------------------------
    # Brush Mask
    # -------------------------------------------------------------------------

    def get_brush_mask(self):
        r = self.window.brush_size
        hardness = self.window.brush_hardness
        strength = self.window.brush_strength

        key = (r, round(hardness, 3), round(strength, 4))

        if self.brush_mask is not None and self.brush_mask_key == key:
            return self.brush_mask

        size = r * 2 + 1

        yy, xx = np.ogrid[:size, :size]

        dx = xx - r
        dy = yy - r

        dist = np.sqrt(dx * dx + dy * dy)

        t = np.clip(dist / max(1, r), 0.0, 1.0)

        # Photoshop-like hardness curve.
        #
        # Hardness управляет не линейно, а через плавную кривую:
        #
        # 0%   -> очень мягкая кисть
        # 50%  -> заметно более плотное ядро
        # 100% -> почти жёсткий край
        #
        # Кривая smoothstep дополнительно сохраняет мягкий переход
        # без резкого излома на границе hard_edge.
        hardness_value = np.clip(hardness / 100.0, 0.0, 1.0)

        hardness_curve = (
            hardness_value
            * hardness_value
            * (3.0 - 2.0 * hardness_value)
        )

        hard_edge = hardness_curve * 0.95

        if hard_edge >= 0.999:
            edge = np.clip((1.0 - t) / 0.05, 0.0, 1.0)
            mask = edge
        else:
            fade = np.clip(
                (t - hard_edge) / (1.0 - hard_edge),
                0.0,
                1.0,
            )

            # Smoothstep:
            # плавное начало и плавное завершение затухания.
            fade = fade * fade * (3.0 - 2.0 * fade)
            mask = 1.0 - fade

        # brush_strength = 0..100
        mask *= strength / 100.0

        self.brush_mask = mask.astype(np.float32)
        self.brush_mask_key = key

        return self.brush_mask

    def get_blur_kernel(self, radius):
        kernel = self._blur_kernel_cache.get(radius)

        if kernel is not None:
            return kernel

        sigma = max(0.5, radius / 2.0)
        kernel_radius = max(1, int(np.ceil(sigma * 3.0)))

        x = np.arange(
            -kernel_radius,
            kernel_radius + 1,
            dtype=np.float32,
        )

        kernel = np.exp(
            -(x * x) / (2.0 * sigma * sigma)
        )

        kernel /= kernel.sum()

        self._blur_kernel_cache[radius] = kernel

        return kernel

    def smooth_alpha_numpy(self, arr, radius):
        if radius <= 0:
            return arr.astype(np.float32, copy=False)

        arr = arr.astype(np.float32, copy=False)

        kernel = self.get_blur_kernel(radius)
        kernel_radius = len(kernel) // 2

        # Horizontal pass
        padded = np.pad(
            arr,
            ((0, 0), (kernel_radius, kernel_radius)),
            mode="edge",
        )

        horizontal = np.empty_like(arr)

        for y in range(arr.shape[0]):
            horizontal[y] = np.convolve(
                padded[y],
                kernel,
                mode="valid",
            )

        # Vertical pass
        padded = np.pad(
            horizontal,
            ((kernel_radius, kernel_radius), (0, 0)),
            mode="edge",
        )

        result = np.empty_like(arr)

        for x in range(arr.shape[1]):
            result[:, x] = np.convolve(
                padded[:, x],
                kernel,
                mode="valid",
            )

        return result

    # -------------------------------------------------------------------------
    # Paint Cursor
    # -------------------------------------------------------------------------

    def paintEvent(self, e):
        super().paintEvent(e)

        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Bounding boxes активного слоя.
        layer = self.window.selected_layer()

        if layer and layer.visible and layer is not self.window.layers[0]:
            s = self.window.preview_scale

            p.setBrush(Qt.BrushStyle.NoBrush)

            # Original bounding box.
            # Полный размер исходного изображения.
            original_bbox = layer.original_visible_bbox()

            if original_bbox:
                x0, y0, x1, y1 = original_bbox

                original_x0 = (layer.x + x0) * s
                original_y0 = (layer.y + y0) * s
                original_x1 = (layer.x + x1) * s
                original_y1 = (layer.y + y1) * s

                p1 = self.mapFromScene(original_x0, original_y0)
                p2 = self.mapFromScene(original_x1, original_y1)

                p.setPen(
                    QPen(
                        QColor(255, 255, 0, 220),
                        1,
                        Qt.PenStyle.DashLine,
                    )
                )

                p.drawRect(
                    p1.x(),
                    p1.y(),
                    p2.x() - p1.x(),
                    p2.y() - p1.y(),
                )

            # Visible bounding box.
            # Существующий bbox по применённой маске.
            bbox = layer.visible_bbox()

            if bbox:
                x0, y0, x1, y1 = bbox

                scene_x0 = (layer.x + x0) * s
                scene_y0 = (layer.y + y0) * s
                scene_x1 = (layer.x + x1) * s
                scene_y1 = (layer.y + y1) * s

                p1 = self.mapFromScene(scene_x0, scene_y0)
                p2 = self.mapFromScene(scene_x1, scene_y1)

                p.setPen(
                    QPen(
                        QColor(255, 255, 255, 220),
                        1,
                        Qt.PenStyle.DashLine,
                    )
                )

                p.drawRect(
                    p1.x(),
                    p1.y(),
                    p2.x() - p1.x(),
                    p2.y() - p1.y(),
                )

        # Курсор кисти.
        if self.cursor_pos is None:
            p.end()
            return

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        zoom = self.transform().m11()
        radius = self.window.brush_size * self.window.preview_scale * zoom

        if radius < 1:
            p.end()
            return

        if self.resizing_brush and self.adjusting_brush_strength:
            strength = self.window.brush_strength
            alpha = int(strength / 100.0 * 255)

            p.setBrush(QColor(120, 120, 120, alpha))
            p.setPen(QPen(QColor(255, 75, 75, 255), 2))

            p.drawEllipse(
                self.cursor_pos,
                radius,
                radius,
            )

            p.setPen(QColor(255, 255, 255, 230))

            p.drawText(
                round(self.cursor_pos.x() + radius + 10),
                round(self.cursor_pos.y() - 10),
                f"Strength {strength}%",
            )

            p.end()
            return

        # Preview мягкости при зажатой F.
        if self.resizing_brush:
            hardness_value = np.clip(
                self.window.brush_hardness / 100.0,
                0.0,
                1.0,
            )

            hardness_curve = (
                hardness_value
                * hardness_value
                * (3.0 - 2.0 * hardness_value)
            )

            fade_start = max(0.0, min(0.99, hardness_curve))

            gradient = QRadialGradient(
                self.cursor_pos,
                radius,
            )

            gradient.setColorAt(
                0.0,
                QColor(120, 120, 120, 255),
            )

            if fade_start > 0.0:
                gradient.setColorAt(
                    fade_start,
                    QColor(120, 120, 120, 255),
                )

            gradient.setColorAt(
                1.0,
                QColor(120, 120, 120, 0),
            )

            # Мягкая внутренняя часть.
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(gradient)

            p.drawEllipse(
                self.cursor_pos,
                radius,
                radius,
            )

            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(25, 255, 255, 255), 2))

            p.drawEllipse(
                self.cursor_pos,
                radius,
                radius,
            )

            # Текст.
            p.setPen(QColor(255, 255, 255, 230))

            text = (
                f"Size {self.window.brush_size}px "
                f"Hardness {self.window.brush_hardness:.0f}%"
            )

            p.drawText(
                round(self.cursor_pos.x() + radius + 10),
                round(self.cursor_pos.y() - 10),
                text,
            )
        else:
            # Обычный курсор кисти.
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 230), 2))

            p.drawEllipse(
                self.cursor_pos,
                radius,
                radius,
            )

            p.setPen(QPen(QColor(0, 0, 0, 180), 1))

            p.drawEllipse(
                self.cursor_pos,
                radius + 1,
                radius + 1,
            )

        p.end()

    def leaveEvent(self, e):
        self.cursor_pos = None
        self.viewport().update()
        super().leaveEvent(e)
