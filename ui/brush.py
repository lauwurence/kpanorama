################################################################################
## Brush

class MainWindowBrush():


    def set_brush_size(self, value):
        value = max(1, min(3000, int(value)))

        self.brush_size = value

        if self.brush_size_slider.value() != value:
            self.brush_size_slider.setValue(value)

        self.brush_size_label.setText(f"{value}px")

        self.view.viewport().update()


    def set_brush_strength(self, value):
        value = max(1, min(100, int(value)))

        self.brush_strength = value

        if self.brush_strength_slider.value() != value:
            self.brush_strength_slider.setValue(value)

        self.brush_strength_label.setText(f"{value}%")

        self.view.viewport().update()


    def set_brush_hardness(self, value):
        value = max(0.0, min(100.0, float(value)))

        self.brush_hardness = value

        slider_value = int(round(value))

        if self.brush_hardness_slider.value() != slider_value:
            self.brush_hardness_slider.setValue(slider_value)

        # Обновляем число справа.
        self.brush_hardness_label.setText(f"{value:.0f}%")

        self.view.viewport().update()
