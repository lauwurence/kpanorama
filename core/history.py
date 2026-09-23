################################################################################
## History

MAX_UNDO = 100

class History():

    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def push_undo(self, action):
        self.undo_stack.append(action)

        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)

        self.redo_stack.clear()

    @property
    def can_undo(self): return bool(self.undo_stack)

    @property
    def can_redo(self): return bool(self.redo_stack)

    @property
    def current_history(self):
        return tuple(id(action) for action in self.undo_stack)

    ############################################################################
    # Undo

    def undo(self):
        if not self.undo_stack:
            return

        action = self.undo_stack.pop()
        typ = action["type"]

        if typ == "brush":
            self.apply_brush_patches(action, True)

        elif typ == "fill_alpha":
            self.apply_fill_alpha(action, True)

        elif typ == "add":
            index = action["index"]

            if 0 <= index < len(self.layers):
                self.layers.pop(index)

            self.rebuild_scene()

        elif typ == "delete":
            index = action["index"]
            layer = action["layer"]

            self.layers.insert(min(index, len(self.layers)), layer)
            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "smart_mask":
            self.apply_smart_mask_history(action, True)

        elif typ == "edge_mask":
            self.apply_edge_mask_history(action, True)

        elif typ == "replace_image":
            index = action["index"]
            self.layers[index].image = action["old_image"]

            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "rename_layer":
            index = action["index"]

            if 0 <= index < len(self.layers):
                self.layers[index].name = action["old_name"]

            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "merge_with_background":
            self.apply_merge_with_background(action, True)

        elif typ == "reorder":
            self.restore_layer_order(action["old_ids"])

        elif typ == "opacity":
            index = action["index"]

            if 0 <= index < len(self.layers):
                layer = self.layers[index]
                layer.opacity = action["old"]

                self.update_layer_preview(layer)

        self.redo_stack.append(action)

        self.update_window_title()
        self.update_project_stats()
        self.update_history_buttons()


    ############################################################################
    # Redo

    def redo(self):
        if not self.redo_stack:
            return

        action = self.redo_stack.pop()
        typ = action["type"]

        if typ == "brush":
            self.apply_brush_patches(action, False)

        elif typ == "fill_alpha":
            self.apply_fill_alpha(action, False)

        elif typ == "add":
            index = action["index"]
            layer = action["layer"]

            self.layers.insert(min(index, len(self.layers)), layer)
            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "delete":
            index = action["index"]

            if 0 <= index < len(self.layers):
                self.layers.pop(index)

            self.rebuild_scene()

        elif typ == "smart_mask":
            self.apply_smart_mask_history(action, False)

        elif typ == "edge_mask":
            self.apply_edge_mask_history(action, False)

        elif typ == "replace_image":
            index = action["index"]
            self.layers[index].image = action["new_image"]

            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "rename_layer":
            index = action["index"]

            if 0 <= index < len(self.layers):
                self.layers[index].name = action["new_name"]

            self.rebuild_scene()
            self.select_layer(index)

        elif typ == "merge_with_background":
            self.apply_merge_with_background(action, False)

        elif typ == "reorder":
            self.restore_layer_order(action["new_ids"])

        elif typ == "opacity":
            index = action["index"]

            if 0 <= index < len(self.layers):
                layer = self.layers[index]
                layer.opacity = action["new"]

                self.update_layer_preview(layer)

        self.undo_stack.append(action)

        self.update_window_title()
        self.update_project_stats()
        self.update_history_buttons()


    ############################################################################

    def apply_smart_mask_history(
        self,
        action,
        undo,
    ):
        index = action["index"]

        if not (
            0 <= index < len(self.layers)
        ):
            return

        layer = self.layers[index]

        layer.alpha = (
            action["before"].copy()
            if undo
            else action["after"].copy()
        )

        layer.alpha_dirty = True

        layer.recalculate_content_bbox()

        self.update_layer_preview(
            layer
        )

        self.update_project_stats()
        self.update_window_title()

        self.view.viewport().update()

    def apply_edge_mask_history(self, action, undo):
        index = action["index"]

        if not 0 <= index < len(self.layers):
            return

        layer = self.layers[index]

        layer.alpha = (
            action["before"].copy()
            if undo
            else action["after"].copy()
        )

        layer.alpha_dirty = True
        layer.recalculate_content_bbox()

        self.update_layer_preview(layer)
        self.update_project_stats()
        self.update_window_title()
        self.view.viewport().update()
