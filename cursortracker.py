import bpy
from bpy.props import CollectionProperty, StringProperty, IntProperty, BoolProperty
from bpy.types import Panel, Operator, PropertyGroup, UIList
from bpy.app.handlers import persistent
import bmesh
from mathutils import Vector


# Property group to store cursor history entries
class CursorHistoryEntry(PropertyGroup):
    location: bpy.props.FloatVectorProperty(
        name="Location",
        description="3D Cursor position",
        size=3,
        subtype='TRANSLATION'
    )

    timestamp: StringProperty(
        name="Time",
        description="When this position was recorded"
    )


# Custom UIList for displaying cursor history
class CURSOR_UL_history_list(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=f"{index + 1}:")
            row.label(text=f"X: {item.location[0]:.3f}")
            row.label(text=f"Y: {item.location[1]:.3f}")
            row.label(text=f"Z: {item.location[2]:.3f}")
            row.label(text=item.timestamp)
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=f"{index + 1}")


# Operator to start recording
class CURSOR_OT_start_recording(Operator):
    bl_idname = "cursor.start_recording"
    bl_label = "Start Recording"
    bl_description = "Start recording 3D cursor position changes"

    def execute(self, context):
        props = context.scene.cursor_history_props
        props.is_recording = True

        # Set the last cursor position to current position to avoid duplicate recording
        current_pos = context.scene.cursor.location.copy()
        props.last_cursor_pos = current_pos

        # Add current cursor position as first entry
        add_cursor_history_entry(current_pos)

        self.report({'INFO'}, "Started recording cursor history")
        return {'FINISHED'}


# Operator to stop recording
class CURSOR_OT_stop_recording(Operator):
    bl_idname = "cursor.stop_recording"
    bl_label = "Stop Recording"
    bl_description = "Stop recording 3D cursor position changes"

    def execute(self, context):
        context.scene.cursor_history_props.is_recording = False
        self.report({'INFO'}, "Stopped recording cursor history")
        return {'FINISHED'}


# Operator to delete selected entry
class CURSOR_OT_delete_entry(Operator):
    bl_idname = "cursor.delete_entry"
    bl_label = "Delete Entry"
    bl_description = "Delete selected cursor history entry"

    def execute(self, context):
        props = context.scene.cursor_history_props
        if props.history_list and props.active_index >= 0:
            props.history_list.remove(props.active_index)
            if props.active_index >= len(props.history_list):
                props.active_index = len(props.history_list) - 1
            self.report({'INFO'}, "Deleted cursor history entry")
        return {'FINISHED'}


# Operator to clear all entries
class CURSOR_OT_clear_history(Operator):
    bl_idname = "cursor.clear_history"
    bl_label = "Clear All"
    bl_description = "Clear all cursor history entries"

    def execute(self, context):
        context.scene.cursor_history_props.history_list.clear()
        context.scene.cursor_history_props.active_index = 0
        self.report({'INFO'}, "Cleared cursor history")
        return {'FINISHED'}


# Operator to jump to selected position
class CURSOR_OT_jump_to_position(Operator):
    bl_idname = "cursor.jump_to_position"
    bl_label = "Jump to Position"
    bl_description = "Move 3D cursor to selected position"

    def execute(self, context):
        props = context.scene.cursor_history_props
        if props.history_list and props.active_index >= 0:
            entry = props.history_list[props.active_index]
            # Temporarily stop recording to avoid adding this position change
            was_recording = props.is_recording
            props.is_recording = False
            context.scene.cursor.location = entry.location
            # Update last_cursor_pos to prevent duplicate recording when resuming
            props.last_cursor_pos = entry.location
            props.is_recording = was_recording
            self.report({'INFO'}, f"Moved cursor to position {props.active_index + 1}")
        return {'FINISHED'}


# Property group to hold all cursor history data
class CursorHistoryProperties(PropertyGroup):
    history_list: CollectionProperty(type=CursorHistoryEntry)
    active_index: IntProperty(default=0)
    is_recording: BoolProperty(default=False)
    last_cursor_pos: bpy.props.FloatVectorProperty(size=3)


# Panel in the N-panel
class CURSOR_PT_history_panel(Panel):
    bl_label = "3D Cursor History"
    bl_idname = "CURSOR_PT_history_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Cursor History"

    def draw(self, context):
        layout = self.layout
        props = context.scene.cursor_history_props

        # Recording controls
        row = layout.row(align=True)
        if props.is_recording:
            row.operator("cursor.stop_recording", icon='PAUSE')
            row.label(text="Recording...", icon='REC')
        else:
            row.operator("cursor.start_recording", icon='PLAY')
            row.label(text="Not Recording")

        layout.separator()

        # Current cursor position
        cursor_pos = context.scene.cursor.location
        col = layout.column(align=True)
        col.label(text="Current Position:")
        row = col.row(align=True)
        row.label(text=f"X: {cursor_pos[0]:.3f}")
        row.label(text=f"Y: {cursor_pos[1]:.3f}")
        row.label(text=f"Z: {cursor_pos[2]:.3f}")

        layout.separator()

        # History list
        col = layout.column()
        col.label(text=f"History ({len(props.history_list)} entries):")

        if props.history_list:
            col.template_list(
                "CURSOR_UL_history_list", "",
                props, "history_list",
                props, "active_index",
                rows=5
            )

            # Controls for selected entry
            row = col.row(align=True)
            row.operator("cursor.jump_to_position", text="Go To", icon='CURSOR')
            row.operator("cursor.delete_entry", text="Delete", icon='X')

            col.operator("cursor.clear_history", text="Clear All", icon='TRASH')
        else:
            col.label(text="No history entries")


# Function to add a new cursor history entry
def add_cursor_history_entry(location):
    import datetime

    props = bpy.context.scene.cursor_history_props
    entry = props.history_list.add()
    entry.location = location
    entry.timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    # Keep list at reasonable size (optional)
    max_entries = 100
    if len(props.history_list) > max_entries:
        props.history_list.remove(0)

    # Update active index to show newest entry
    props.active_index = len(props.history_list) - 1


# Handler to detect cursor position changes
@persistent
def cursor_position_handler(scene, depsgraph=None):
    if not hasattr(scene, 'cursor_history_props'):
        return

    props = scene.cursor_history_props

    if not props.is_recording:
        return

    current_pos = scene.cursor.location.copy()
    last_pos = Vector(props.last_cursor_pos)

    # Check if position has changed (with small tolerance for floating point)
    if (current_pos - last_pos).length > 0.001:
        add_cursor_history_entry(current_pos)
        props.last_cursor_pos = current_pos


# Registration
classes = [
    CursorHistoryEntry,
    CursorHistoryProperties,
    CURSOR_UL_history_list,
    CURSOR_OT_start_recording,
    CURSOR_OT_stop_recording,
    CURSOR_OT_delete_entry,
    CURSOR_OT_clear_history,
    CURSOR_OT_jump_to_position,
    CURSOR_PT_history_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.cursor_history_props = bpy.props.PointerProperty(
        type=CursorHistoryProperties
    )

    # Add the handler
    if cursor_position_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(cursor_position_handler)


def unregister():
    # Remove the handler
    if cursor_position_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(cursor_position_handler)

    del bpy.types.Scene.cursor_history_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()