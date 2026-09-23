################################################################################
## Project I/O

import io
import json
import os
import zipfile

import numpy as np
from PIL import Image

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from core.layer import Layer


class ProjectIO():

    ############################################################################
    # Alpha normalization

    def _normalize_alpha_for_save(self, image, threshold=0.975):
        """
        При сохранении округляет почти полностью непрозрачные
        пиксели до полной непрозрачности.

        Исходное изображение в памяти не изменяется.
        """

        alpha = np.asarray(image, dtype=np.uint8).copy()
        threshold = int(threshold * 255)
        alpha[alpha > threshold] = 255

        return Image.fromarray(alpha, "L")

    def _get_normalized_alpha_data(self, layer):
        """
        Возвращает PNG-данные alpha после нормализации.

        Используется только при сохранении проекта.
        """

        alpha = self._normalize_alpha_for_save(layer.alpha)
        buffer = io.BytesIO()
        alpha.save(buffer, format="PNG", compress_level=1, optimize=False)

        return buffer.getvalue()

    def _get_normalized_content_alpha_data(self, layer):
        """
        Возвращает PNG-данные content_alpha после нормализации.
        """

        content_alpha = self._normalize_alpha_for_save(layer.content_alpha)
        buffer = io.BytesIO()
        content_alpha.save(buffer, format="PNG", compress_level=1, optimize=False)

        return buffer.getvalue()

    ############################################################################
    # Save project

    def save_project(self):
        if not self.layers:
            return False

        if not self.project_path:
            return self.save_project_as()

        return self.write_project(self.project_path)

    def save_project_as(self):
        if not self.layers:
            return False

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            "",
            "kPanorama Project (*.kpp)",
        )

        if not path:
            return False

        if not path.lower().endswith(".kpp"):
            path += ".kpp"

        return self.write_project(path)

    def write_project(self, path):

        try:
            with zipfile.ZipFile(
                path,
                "w",
                compression=zipfile.ZIP_STORED,
            ) as z:

                project = {
                    "version": 10,
                    "canvas": [
                        self.canvas_width,
                        self.canvas_height,
                    ],
                    "layers": [],
                }

                for i, layer in enumerate(self.layers):
                    image_name = f"layer_{i}.png"

                    # RGB-изображение всегда сохраняется lossless.
                    # Если кэш актуален — PNG повторно не кодируется.
                    z.writestr(
                        image_name,
                        layer.get_image_data(),
                    )

                    is_background = (
                        i == 0
                        or layer is self.layers[0]
                    )

                    alpha_name = None
                    content_alpha_name = None
                    original_bbox = None

                    # Фоновому слою альфа не нужна вообще.
                    if not is_background:
                        alpha_name = f"alpha_{i}.png"

                        # --------------------------------------------------
                        # Alpha нормализуется только при сохранении.
                        #
                        # 253 / 254 / 255 -> 255
                        # 252 и ниже остаются без изменений.
                        # --------------------------------------------------

                        alpha_data = (
                            self._get_normalized_alpha_data(
                                layer
                            )
                        )

                        z.writestr(
                            alpha_name,
                            alpha_data,
                        )

                        # --------------------------------------------------
                        # Content alpha
                        # --------------------------------------------------

                        content_alpha_data = (
                            self._get_normalized_content_alpha_data(
                                layer
                            )
                        )

                        if content_alpha_data:
                            content_alpha_name = (
                                f"content_alpha_{i}.png"
                            )

                            z.writestr(
                                content_alpha_name,
                                content_alpha_data,
                            )

                        original_bbox = (
                            layer.original_visible_bbox()
                        )

                    project["layers"].append({
                        "name": layer.name,
                        "image": image_name,
                        "alpha": alpha_name,
                        "opacity" : layer.opacity,
                        "tag" : layer.tag,
                        "content_alpha": content_alpha_name,
                        "original_bbox": (
                            list(original_bbox)
                            if original_bbox is not None
                            else None
                        ),
                        "x": layer.x,
                        "y": layer.y,
                        "visible": layer.visible,
                    })

                z.writestr(
                    "project.json",
                    json.dumps(
                        project,
                        ensure_ascii=False,
                        indent=2,
                    ),
                )

            self.project_path = os.path.abspath(path)

            self.mark_project_saved()
            self.status.setText("Project saved")
            self.update_project_stats()

            return True

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error saving",
                str(e),
            )

            return False

    ############################################################################
    # Load project

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            "kPanorama Project (*.kpp)",
        )

        if not path:
            return

        self.load_project_from_path(path)

    def load_project_from_path(self, path):

        try:
            with zipfile.ZipFile(
                path,
                "r",
            ) as z:

                project = json.loads(
                    z.read("project.json")
                )

                if project.get("version") != 10:
                    raise ValueError(
                        "Unsupported project version"
                    )

                self.layers.clear()

                (
                    self.canvas_width,
                    self.canvas_height,
                ) = project["canvas"]

                for i, data in enumerate(
                    project["layers"]
                ):
                    image_name = data["image"]

                    image_data = z.read(
                        image_name
                    )

                    rgb = (
                        Image.open(
                            io.BytesIO(image_data)
                        ).convert("RGB")
                    )

                    is_background = i == 0

                    if is_background:
                        alpha = Image.new(
                            "L",
                            rgb.size,
                            255,
                        )

                        content_alpha = Image.new(
                            "L",
                            rgb.size,
                            255,
                        )

                        alpha_data = None
                        content_alpha_data = b""

                    else:
                        alpha_name = data["alpha"]

                        if not alpha_name:
                            raise ValueError(
                                f"У слоя {i} отсутствует alpha"
                            )

                        alpha_data = z.read(
                            alpha_name
                        )

                        alpha = (
                            Image.open(
                                io.BytesIO(alpha_data)
                            ).convert("L")
                        )

                        content_alpha_name = (
                            data["content_alpha"]
                        )

                        if content_alpha_name:
                            content_alpha_data = z.read(
                                content_alpha_name
                            )

                            content_alpha = (
                                Image.open(
                                    io.BytesIO(
                                        content_alpha_data
                                    )
                                ).convert("L")
                            )

                        else:
                            content_alpha_data = b""

                            content_alpha = Image.new(
                                "L",
                                rgb.size,
                                255,
                            )

                    layer = Layer(
                        data["name"],
                        rgb,
                        data["x"],
                        data["y"],
                        alpha,
                        data["visible"],
                        original_bbox=data[
                            "original_bbox"
                        ],
                        opacity=data.get("opacity", 100),
                        tag=data.get("tag", None)
                    )

                    # В проекте content_alpha хранится
                    # отдельно от текущей alpha.
                    layer.content_alpha = (
                        content_alpha
                    )

                    # ВАЖНО:
                    # пересоздаём numpy-кэш именно
                    # из загруженной content_alpha.
                    layer.content_alpha_array = (
                        np.asarray(
                            content_alpha,
                            dtype=np.float32,
                        )
                    )

                    # Кэши PNG
                    layer.image_cache = image_data
                    layer.image_dirty = False

                    layer.alpha_cache = alpha_data
                    layer.alpha_dirty = False

                    layer.content_alpha_cache = (
                        content_alpha_data
                    )

                    layer.content_alpha_dirty = False

                    self.layers.append(layer)

            self.undo_stack.clear()
            self.redo_stack.clear()

            self.rebuild_scene()

            self.project_path = os.path.abspath(
                path
            )

            self.update_project_stats()

            if self.layers:
                self.select_layer(
                    len(self.layers) - 1
                )

            self.mark_project_saved()

            self.status.setText(
                "Project loaded"
            )

            QTimer.singleShot(0, self.fit_canvas_to_view)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error loading",
                str(e),
            )
