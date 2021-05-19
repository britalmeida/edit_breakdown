# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

import binascii
import io
import json
import logging
import os
import sys

import bpy
from bpy.props import StringProperty, EnumProperty, IntProperty
from bpy.types import Operator

from .. import data
from .. import utils

log = logging.getLogger(__name__)


class SEQUENCER_OT_add_custom_shot_prop(Operator):
    bl_idname = "edit_breakdown.add_custom_shot_prop"
    bl_label = "Add Shot Property"
    bl_description = "Add a new custom property to the edit's shots"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action."""

        scene = context.scene
        user_configured_props = scene.edit_breakdown.shot_custom_props

        new_prop = user_configured_props.add()
        # Generate an unique identifier for the property that will never be changed.
        new_prop.identifier = f"cp_{binascii.hexlify(os.urandom(4)).decode()}"

        # Generate a random color
        new_prop.color = utils.get_random_pastel_color_rgb()

        shot_cls = data.SEQUENCER_EditBreakdown_Shot
        data.register_custom_prop(shot_cls, new_prop)

        return {'FINISHED'}


class SEQUENCER_OT_del_custom_shot_prop(Operator):
    bl_idname = "edit_breakdown.del_custom_shot_prop"
    bl_label = "Delete Shot Property"
    bl_description = "Remove custom property from the edit's shots and delete associated data"
    bl_options = {'REGISTER', 'UNDO'}

    prop_id: StringProperty(
        name="Prop Identifier",
        description="Identifier of the custom property to be deleted",
        default="",
    )

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action."""

        scene = context.scene
        user_configured_props = scene.edit_breakdown.shot_custom_props

        # Find the index of the custom property to remove
        try:
            idx_to_remove = next(
                (
                    i
                    for i, prop in enumerate(user_configured_props)
                    if prop.identifier == self.prop_id
                )
            )
        except StopIteration:
            log.error("Tried to remove a custom shot property that does not exist")
            return {'CANCELLED'}

        # Delete the property from all shots
        shots = scene.edit_breakdown.shots
        # TODO

        # Delete the user configuration for the property
        user_configured_props.remove(idx_to_remove)

        # Delete the property definition
        shot_cls = data.SEQUENCER_EditBreakdown_Shot
        data.unregister_custom_prop(shot_cls, self.prop_id)

        return {'FINISHED'}


class SEQUENCER_OT_edit_custom_shot_prop(Operator):
    bl_idname = "edit_breakdown.edit_custom_shot_prop"
    bl_label = "Edit Shot Property"
    bl_description = "Configure a shot custom property"
    bl_options = {'REGISTER', 'UNDO'}

    prop_id: StringProperty(
        name="Prop Identifier",
        description="Identifier of the custom property to be edited",
        default="",
    )

    name: StringProperty(
        name="Name",
        description="Name to display in the UI. Can be renamed",
    )
    description: StringProperty(
        name="Description",
        description="Details on the meaning of the property",
    )
    data_type: EnumProperty(
        name="Data Type",
        description="The type of data that this property holds",
        items=data.custom_prop_data_types,
    )
    range_min: IntProperty(
        name="Min",
        description="The minimum value that the property can have",
    )
    range_max: IntProperty(
        name="Max",
        description="The maximum value that the property can have",
    )
    enum_items: StringProperty(
        name="Items",
        description="Possible values for the property. Comma separated list of options",
    )

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        """Custom UI for the operator's properties."""
        layout = self.layout

        # Always allow editing of "cosmetic" values
        col = layout.column()
        col.prop(self, "name")
        col.prop(self, "description")

        # If 'prop_id' is not registered for shots, early out of any
        # potentially data changing operations.
        if not data.SEQUENCER_EditBreakdown_Shot.has_prop(self.prop_id):
            col.label(
                icon='ERROR',
                text="Shots don't have this property registered. Try reloading the file.",
            )
            return

        def is_prop_already_used(shots, prop_id):
            """Check if any shot already has data introduced by the user for the given property."""
            is_used = False
            for shot in shots:
                if shot.is_property_set(prop_id):
                    is_used = True
                    break
            return is_used

        def get_prop_used_range(shots, prop_id):
            """Get the minimum and maximum values actually in use for the given property."""
            min_val = sys.maxsize
            max_val = ~sys.maxsize
            for shot in shots:
                val = int(shot.get_prop_value(prop_id))
                min_val = min(min_val, val)
                max_val = max(max_val, val)
            return min_val, max_val

        shots = context.scene.edit_breakdown.shots
        is_used = is_prop_already_used(shots, self.prop_id)

        col = layout.column()
        col.enabled = not is_used
        col.prop(self, "data_type")
        if is_used:
            col.label(text="Type can not be edited after the property is already in use")

        col = layout.column()
        # Additional configuration according to the data type
        if self.data_type == 'INT':
            row = col.row()
            row.prop(self, "range_min")
            row.prop(self, "range_max")
            min_used_val, max_used_val = get_prop_used_range(shots, self.prop_id)
            if is_used and (self.range_min > min_used_val or self.range_max < max_used_val):
                col.label(
                    icon='ERROR',  # Actually the triangle warning icon
                    text="There is existing data outside the new range. Values outside the range will be clamped.",
                )
        elif self.data_type == 'ENUM_VAL' or self.data_type == 'ENUM_FLAG':
            col.prop(self, "enum_items")

    def invoke(self, context, event):
        """On user interaction, show a popup with the properties that only executes on 'OK'."""
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=450)

    def execute(self, context):
        """Called to finish this operator's action."""

        scene = context.scene
        user_configured_props = scene.edit_breakdown.shot_custom_props

        # Find the custom property to edit
        try:
            prop = next((p for p in user_configured_props if p.identifier == self.prop_id))
        except StopIteration:
            log.error("Tried to edit a custom shot property that does not exist")
            return {'CANCELLED'}

        # Apply changes to the user configuration for the property
        prop.name = self.name
        prop.description = self.description
        prop.data_type = self.data_type
        if self.data_type == 'INT':
            prop.range_min = self.range_min
            prop.range_max = self.range_max
        elif self.data_type == 'ENUM_VAL' or self.data_type == 'ENUM_FLAG':
            prop.enum_items = self.enum_items

        # Re-register the property definition
        shot_cls = data.SEQUENCER_EditBreakdown_Shot
        data.unregister_custom_prop(shot_cls, self.prop_id)
        data.register_custom_prop(shot_cls, prop)

        # Conform the existing data in all shots
        if data.SEQUENCER_EditBreakdown_Shot.has_prop(self.prop_id):
            shots = scene.edit_breakdown.shots
            if self.data_type == 'INT':
                # Update the default value if the new minimum is bigger than 0.
                default_value = max(0, self.range_min)
                prop.default = default_value
                # Clamp all values to the new range
                log.debug(f"[{self.range_min}, {self.range_max}]")
                for shot in shots:
                    val = int(shot.get(self.prop_id, default_value))
                    new_val = max(self.range_min, min(val, self.range_max))
                    shot.set_prop_value(self.prop_id, new_val)
            elif self.data_type == 'ENUM_VAL' or self.data_type == 'ENUM_FLAG':
                items = [i.strip() for i in self.enum_items.split(',')]

        # Redraw the list of properties with the inlined property information.
        context.region.tag_redraw()

        return {'FINISHED'}


class SEQUENCER_OT_copy_custom_shot_props(Operator):
    bl_idname = "edit_breakdown.copy_custom_shot_props"
    bl_label = "Copy Custom Properties Configuration"
    bl_description = "Copy the configuration of custom properties. Can be pasted in another file"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action."""

        # Write to memory
        outbuf = io.StringIO()
        json.dump(['test'], outbuf)

        # Push to the clipboard
        bpy.context.window_manager.clipboard = outbuf.getvalue()

        return {'FINISHED'}


class SEQUENCER_OT_paste_custom_shot_props(Operator):
    bl_idname = "edit_breakdown.paste_custom_shot_props"
    bl_label = "Paste Custom Properties Configuration"
    bl_description = "Paste the configuration of custom properties for shots"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action."""

        return {'FINISHED'}


class UI_OT_shot_properties_tooltip(Operator):
    bl_idname = "edit_breakdown.shot_properties_tooltip"
    bl_label = "Custom Shot Properties"
    bl_description = "Show information about the custom properties present on this file"
    bl_options = {'INTERNAL', 'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        """On user interaction, show a popup with information."""
        wm = context.window_manager
        return wm.invoke_popup(self, width=400)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        """Custom UI for the operator's properties."""
        layout = self.layout

        col = layout.column()
        col.label(text=self.bl_label)
        col.separator()

        scene = context.scene
        user_configured_props = scene.edit_breakdown.shot_custom_props
        col.label(text=f"File has {len(user_configured_props)} user-configured properties.")

        shot_cls = data.SEQUENCER_EditBreakdown_Shot
        blend_file_data_props = shot_cls.get_custom_properties()
        col.label(text=f"File has {len(blend_file_data_props)} registered properties.")

        col.separator()
        col.label(text="Note: Custom properties are saved per file (not a user preference)")


class SEQUENCER_OT_assign_shots_to_scene(Operator):
    bl_idname = "edit_breakdown.assign_shots_to_scene"
    bl_label = "Assign Edit Breakdown Scene"
    bl_description = "Assign the selected Edit Breakdown scene to the selected timeline strips"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # This operator is available only in the sequence editor.
        is_sequence_editor = context.space_data.type == 'SEQUENCE_EDITOR'

        # Needs edit breakdown strips to operate on.
        strips = context.scene.sequence_editor.sequences
        selected_eb_strips = [s for s in strips if s.use_for_edit_breakdown and s.select]

        return is_sequence_editor and selected_eb_strips

    def execute(self, context):
        """Called to finish this operator's action."""

        edit_breakdown = context.scene.edit_breakdown
        selected_eb_scene = edit_breakdown.scenes[edit_breakdown.active_scene_idx]

        shots = edit_breakdown.shots
        strips = bpy.context.scene.sequence_editor.sequences
        selected_eb_strips = [s for s in strips if s.use_for_edit_breakdown and s.select]

        # Assign a scene UUID to the shot matching the selected strip(s)
        for strip in selected_eb_strips:

            # Find the strip's associated shot and scene
            shot = next((s for s in shots if strip.name == s.strip_name), None)

            # Assign the scene UUID to the shot and update the strip color
            eb_scene_color = (1.0, 0.0, 0.0)  # Default to a red error color
            if (shot and selected_eb_scene):
                shot.scene_uuid = selected_eb_scene.uuid
                eb_scene_color = selected_eb_scene.color[0:3]
            strip.color = eb_scene_color

        return {'FINISHED'}


classes = (
    SEQUENCER_OT_add_custom_shot_prop,
    SEQUENCER_OT_del_custom_shot_prop,
    SEQUENCER_OT_edit_custom_shot_prop,
    SEQUENCER_OT_copy_custom_shot_props,
    SEQUENCER_OT_paste_custom_shot_props,
    UI_OT_shot_properties_tooltip,
    SEQUENCER_OT_assign_shots_to_scene,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
