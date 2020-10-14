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
import contextlib
import csv
import io
import logging
import pathlib
import os
import sys

import bpy
from bpy.types import Operator
from bpy.props import (
    EnumProperty,
    IntProperty,
    StringProperty,
)

from . import data
from . import view

log = logging.getLogger(__name__)


# Operators #######################################################################################




class SEQUENCER_OT_sync_edit_breakdown(Operator):
    bl_idname = "edit_breakdown.sync_edit_breakdown"
    bl_label = "Sync Edit Breakdown"
    bl_description = "Ensure the edit breakdown is up-to-date with the edit"
    bl_options = {'REGISTER'}

    @contextlib.contextmanager
    def override_render_settings(self, context, thumbnail_width=256):
        """Overrides the render settings for thumbnail size in a 'with' block scope."""

        rd = context.scene.render

        # Remember current render settings in order to restore them later.
        orig_percentage = rd.resolution_percentage
        orig_file_format = rd.image_settings.file_format
        orig_quality = rd.image_settings.quality

        try:
            # Set the render settings to thumbnail size.
            # Update resolution % instead of the actual resolution to scale text strips properly.
            rd.resolution_percentage = round(thumbnail_width * 100 / rd.resolution_x)
            rd.image_settings.file_format = 'JPEG'
            rd.image_settings.quality = 80
            yield
        finally:
            # Return the render settings to normal.
            rd.resolution_percentage = orig_percentage
            rd.image_settings.file_format = orig_file_format
            rd.image_settings.quality = orig_quality

    def save_render(self, datablock, file_name):
        """Save the current render image to disk"""

        addon_prefs = bpy.context.preferences.addons['edit_breakdown'].preferences
        folder_name = addon_prefs.edit_shots_folder

        # Ensure folder exists
        folder_path = pathlib.Path(folder_name)
        folder_path.mkdir(parents=True, exist_ok=True)

        path = folder_path.joinpath(file_name)
        datablock.save_render(str(path))


    def calculate_shots_duration(self, context):
        shots = context.scene.edit_breakdown.shots

        accumulated_total_frames = 0
        last_frame = max(context.scene.frame_end, shots[-1].frame_start)
        for shot in reversed(shots):
            shot.frame_count = last_frame - shot.frame_start
            last_frame = shot.frame_start
            accumulated_total_frames += shot.frame_count

        scene = context.scene
        scene_total_frames = scene.frame_end - scene.frame_start
        if scene_total_frames != accumulated_total_frames:
            self.report({'WARNING'},
                "The frame range does not match the sequencer strips. Edit Breakdown will report incorrect duration")

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action.

        Recreate the edit breakdown data based on the current edit.
        """

        log.debug("sync_edit_breakdown: execute")

        scene = context.scene
        sequence_ed = scene.sequence_editor
        shots = scene.edit_breakdown.shots

        # Clear the previous runtime data.
        view.thumbnail_images.clear()
        view.thumbnail_size = (0, 0)
        view.hovered_thumbnail = None
        view.active_selected_thumbnail = None

        # Ensure the thumbnails folder exists and clear old thumbnails.
        addon_prefs = bpy.context.preferences.addons['edit_breakdown'].preferences
        folder_name = addon_prefs.edit_shots_folder
        folder_path = pathlib.Path(folder_name)
        folder_path.mkdir(parents=True, exist_ok=True)
        for path in folder_path.iterdir():
            if path.suffix == ".jpg":
                path.unlink()

        # Render a thumbnail to disk per each frame
        log.info("Creating thumbnails")
        markers = scene.timeline_markers
        with self.override_render_settings(context):
            for m in markers:
                scene.frame_current = m.frame
                bpy.ops.render.render()
                file_name = f'{str(context.scene.frame_current)}.jpg'
                self.save_render(bpy.data.images['Render Result'], file_name)

        # Load data from the sequence markers marked for use in the edit breakdown
        def WIP_fake_behaviour():
            view.load_edit_thumbnails()
            log.debug(f"Thumbnails: {len(view.thumbnail_images)}")

            # Delete shots that no longer match a marker
            shot_data_to_delete = []
            for i, shot in enumerate(shots):
                for thumb in view.thumbnail_images:
                    if shot.frame_start == int(thumb.name):
                        break #  Found it, do nothing. Skip to next shot.
                    elif shot.frame_start > int(thumb.name):
                        shot_data_to_delete.append(i)
                        break
            if shot_data_to_delete:
                self.report({'WARNING'},
                    f"Orphan shots (currently not deleted): {shot_data_to_delete}")

            for thumb in view.thumbnail_images:
                # Try to find existing shot data
                found = False
                for i, shot in enumerate(shots):
                    if shot.frame_start == int(thumb.name):
                        found = True
                        break #  Found it, do nothing. Skip to next shot.
                    elif shot.frame_start > int(thumb.name):
                        break

                if not found:
                    new_shot = shots.add()
                    new_shot.shot_name = str(thumb.name)
                    new_shot.frame_start = thumb.name

            log.debug(f"Shots: {len(shots)}")

        WIP_fake_behaviour()

        self.calculate_shots_duration(context)

        # Position the images according to the available space.
        view.fit_thumbnails_in_region()

        return {'FINISHED'}


class SEQUENCER_OT_copy_edit_breakdown_as_csv(Operator):
    bl_idname = "edit_breakdown.copy_edit_breakdown_as_csv"
    bl_label = "Copy Edit Breakdown as CSV"
    bl_description = "Copy Edit Breakdown data as CSV in the clipboard"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action."""

        log.debug("copy_edit_breakdown_as_csv: execute")

        sequence_ed = context.scene.sequence_editor
        shots = context.scene.edit_breakdown.shots
        log.info('Saving CSV to clipboard')

        # Create shot list that becomes a CSV, starting with the header
        shots_for_csv = [data.SEQUENCER_EditBreakdown_Shot.get_attributes()]
        # Push each shot in the list
        for shot in shots:
            shots_for_csv.append(shot.as_list())

        # Write the CSV in memory
        outbuf = io.StringIO()
        outcsv = csv.writer(outbuf)
        outcsv.writerows(shots_for_csv)

        # Push the CSV to the clipboard
        bpy.context.window_manager.clipboard = outbuf.getvalue()

        return {'FINISHED'}


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
            idx_to_remove = next((i for i, prop in enumerate(user_configured_props) \
                                if prop.identifier == self.prop_id))
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
            col.label(icon='ERROR',
                      text="Shots don't have this property registered. Try reloading the file.")
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
            default_value = 0 # When property is not set
            min_val = sys.maxsize
            max_val = ~sys.maxsize
            for shot in shots:
                val = int(shot.get(prop_id, default_value))
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
            row=col.row()
            row.prop(self, "range_min")
            row.prop(self, "range_max")
            min_used_val, max_used_val = get_prop_used_range(shots, self.prop_id)
            if is_used and (self.range_min > min_used_val or self.range_max < max_used_val):
                col.label(icon='ERROR', # Actually the triangle warning icon
                          text="There is existing data outside the new range. Values outside the range will be clamped.")
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
                    shot.set_prop(self.prop_id, new_val)
            elif self.data_type == 'ENUM_VAL' or self.data_type == 'ENUM_FLAG':
                items = [i.strip() for i in self.enum_items.split(',')]

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



# UI ##############################################################################################

def draw_sequencer_header_extension(self, context):
    layout = self.layout
    layout.operator("edit_breakdown.sync_edit_breakdown", icon='SEQ_SPLITVIEW') #FILE_REFRESH
    layout.operator("edit_breakdown.copy_edit_breakdown_as_csv", icon='FILE')



# Add-on Registration #############################################################################

classes = (
    SEQUENCER_OT_sync_edit_breakdown,
    SEQUENCER_OT_copy_edit_breakdown_as_csv,
    SEQUENCER_OT_add_custom_shot_prop,
    SEQUENCER_OT_del_custom_shot_prop,
    SEQUENCER_OT_edit_custom_shot_prop,
    UI_OT_shot_properties_tooltip,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.SEQUENCER_HT_header.append(draw_sequencer_header_extension)


def unregister():

    bpy.types.SEQUENCER_HT_header.remove(draw_sequencer_header_extension)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
