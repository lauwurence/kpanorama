################################################################################
## Export

import os
import numpy as np

from PyQt6.QtWidgets import QMessageBox, QFileDialog

from PIL.PngImagePlugin import PngInfo


class MainWindowExport():


    def get_layer_save_name(self, layer, tag=True):

        name = os.path.splitext(layer.name.strip())[0]

        if tag and (layer.tag is not None):
            name += f"_{layer.tag}"

        return name


    def get_group_save_name(self, group, tag=True):
        name = os.path.splitext(group.name.strip())[0]

        if tag and (group.tag is not None):
            name += f"_{group.tag}"

        return name


    # ========================================================
    # Export PNG
    # ========================================================

    def export_layer(self):
        layer = self.selected_layer()

        if not layer:
            return

        self.save_layer_as_png(layer)


    def save_layer_as_png(self, layer):
        alpha = np.asarray(layer.alpha)
        ys, xs = np.where(alpha > 0)

        if len(xs) == 0:
            QMessageBox.information(self, "Save Layer", "Layer is completely transparent.")
            return

        layer.clip_alpha_to_original_bbox()

        left = int(xs.min())
        right = int(xs.max()) + 1
        top = int(ys.min())
        bottom = int(ys.max()) + 1

        result = layer.rgba().crop((left, top, right, bottom))

        path, _ = QFileDialog.getSaveFileName(self, "Save PNG", self.get_layer_save_name(layer) + ".png", "PNG (*.png)")

        if not path:
            return

        x = int(layer.x + left)
        y = int(layer.y + top)

        self._remove_images(layer=layer)

        self._save_image(result, path, x=x, y=y, k='layer')


    def save_layer_to_project_folder(self, layer):

        if not self.project_path:
            QMessageBox.information(self, "Save Layer", "Save the project first.")
            return

        layer.clip_alpha_to_original_bbox()

        project_dir = os.path.dirname(os.path.abspath(self.project_path))

        filename = self.get_layer_save_name(layer)
        path = os.path.join(project_dir, filename + ".png")

        alpha = np.asarray(layer.alpha)
        ys, xs = np.where(alpha > 0)

        if len(xs) == 0:
            QMessageBox.information(self, "Save Layer", "Layer is completely transparent.")
            return

        left = int(xs.min())
        right = int(xs.max()) + 1
        top = int(ys.min())
        bottom = int(ys.max()) + 1

        result = layer.rgba().crop((left, top, right, bottom))

        x = int(layer.x + left)
        y = int(layer.y + top)

        self._remove_images(layer=layer)

        self._save_image(result, path, x=x, y=y, k='layer')


    def _remove_images(self, layer=None, group=None):

        if layer:
            filename = self.get_layer_save_name(layer, tag=False)
        elif group:
            filename = self.get_group_save_name(group, tag=False)
        else:
            raise Exception("`layer` or `group` must be provided.")

        project_dir = os.path.dirname(os.path.abspath(self.project_path))

        for suffix in ["", "_HQ", "_MQ", "_LQ", "_SQ"]:
            path = os.path.join(project_dir, filename + suffix + ".png")

            if not os.path.exists(path):
                continue

            try:
                os.remove(path)
            except FileNotFoundError:
                pass


    def _save_image(self, image, path, x, y, k):

        metadata = PngInfo()
        metadata.add_text('x', str(x))
        metadata.add_text('y', str(y))

        try:
            image.save(
                path,
                format="PNG",
                pnginfo=metadata,
                compress_level=1,
                optimize=False
            )

            self.status.setText(f"{k.capitalize()} saved: {os.path.basename(path)}")

        except Exception as e:
            QMessageBox.critical(self, "Error saving", str(e))