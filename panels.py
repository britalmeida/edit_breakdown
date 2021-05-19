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

import bpy
from bpy.types import (
    Panel,
    UIList,
)

from . import data
from . import utils
from . import view


class SEQUENCER_PT_edit_breakdown_overview(Panel):
    bl_label = "Overview"
    bl_category = "Edit Breakdown - Shot"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'SEQUENCE_EDITOR' and view.is_thumbnail_view()

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        edit_breakdown = context.scene.edit_breakdown

        col = layout.column(align=True)
        utils.draw_stat_label(col, "Scenes", f"{len(edit_breakdown.scenes)}")
        utils.draw_stat_label(col, "Shots", f"{len(edit_breakdown.shots)}")
        utils.draw_frame_prop(col, "Duration", edit_breakdown.total_frames)


class SEQUENCER_PT_edit_breakdown_shot(Panel):
    bl_label = "Shot"
    bl_category = "Edit Breakdown - Shot"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'SEQUENCE_EDITOR' and view.is_thumbnail_view()

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        edit_breakdown = bpy.context.scene.edit_breakdown
        shots = edit_breakdown.shots
        sel_idx = edit_breakdown.selected_shot_idx

        if sel_idx < 0:
            col = layout.column()
            col.label(text=f"No shot selected")
            return

        selected_shot = shots[sel_idx]

        col = layout.column()
        col.prop(selected_shot, "name")

        # Display frame information with a timestamp.
        sub = col.column(align=True)
        utils.draw_frame_prop(sub, "Start Frame", selected_shot.frame_start)
        utils.draw_frame_prop(sub, "Duration", selected_shot.frame_count)

        # Scene that this shot belongs to
        eb_scene = edit_breakdown.find_scene(selected_shot.scene_uuid)
        utils.draw_stat_label(col, "Scene", eb_scene.name if eb_scene else "")

        # Show user-defined properties
        shot_cls = data.SEQUENCER_EditBreakdown_Shot
        blend_file_data_props = shot_cls.get_custom_properties()
        for prop in blend_file_data_props:
            col.prop(selected_shot, prop.identifier)
            # Display a count, if this is an enum
            prop_rna = selected_shot.bl_rna.properties[prop.identifier]
            is_enum_flag = prop_rna.type == 'ENUM' and prop_rna.is_enum_flag
            if is_enum_flag:
                num_chosen_options, num_options = selected_shot.count_bits_in_flag(prop.identifier)
                col.label(text=f"{prop.name} Count: {num_chosen_options} of {num_options}")


class SEQUENCER_UL_edit_breakdown_scenes(UIList):
    """UI List for the scenes in the edit."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        eb_scene = item

        split = layout.split(factor=0.12)
        row = split.row(align=True)
        row.alignment = 'LEFT'
        row.prop(eb_scene, "color", text="", emboss=True)

        row = split.row(align=True)
        row.alignment = 'LEFT'
        row.prop(eb_scene, "name", text="", emboss=False)
        # if self.layout_type in ('DEFAULT', 'COMPACT'):
        #    layout.prop(item, "is_selected", text="")


class SEQUENCER_PT_edit_breakdown_scenes(Panel):
    bl_label = "Scenes"
    bl_category = "Edit Breakdown - Config"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'SEQUENCE_EDITOR' and view.is_thumbnail_view()

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        edit_breakdown = bpy.context.scene.edit_breakdown

        # UI list
        num_rows = 10 if len(edit_breakdown.scenes) > 0 else 3
        row = layout.row()
        # fmt: off
        row.template_list(
            "SEQUENCER_UL_edit_breakdown_scenes", "",  # Type and unique id.
            edit_breakdown, "scenes",  # Pointer to the CollectionProperty.
            edit_breakdown, "active_scene_idx",  # Pointer to the active identifier.
            rows=num_rows,
        )
        # fmt: on

        # Buttons on the right
        but_col = row.column(align=True)
        but_col.operator("edit_breakdown.add_scene", icon='ADD', text="")
        but_col.operator("edit_breakdown.del_scene", icon='REMOVE', text="")
        but_col.separator()
        but_col.operator("edit_breakdown.assign_shots_to_scene", icon='SEQ_SEQUENCER', text="")
        # Specials menu
        but_col.separator()
        but_col.menu("SEQUENCER_MT_scenes_context_menu", icon='DOWNARROW_HLT', text="")
        # Move up&down arrows
        if edit_breakdown.scenes:
            but_col.separator()
            but_col.operator("edit_breakdown.scene_move", icon='TRIA_UP', text="").direction = 'UP'
            but_col.operator("edit_breakdown.scene_move", icon='TRIA_DOWN', text="").direction = 'DOWN'


class SEQUENCER_PT_edit_breakdown_shot_custom_props(Panel):
    bl_label = "Shot Properties"
    bl_category = "Edit Breakdown - Config"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'SEQUENCE_EDITOR' and view.is_thumbnail_view()

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col_props = layout.column()
        row = col_props.row()
        # 'Add Property' button
        row = col_props.row()
        row.operator("edit_breakdown.add_custom_shot_prop")
        # Actions
        sub = row.row(align=True)
        sub.enabled = False
        sub.operator("edit_breakdown.copy_custom_shot_props", icon='COPYDOWN', text="")
        sub.operator("edit_breakdown.paste_custom_shot_props", icon='PASTEDOWN', text="")
        row.operator("edit_breakdown.shot_properties_tooltip", icon='QUESTION', text="")

        edit_breakdown = context.scene.edit_breakdown
        user_configured_props = edit_breakdown.shot_custom_props
        data_types = data.custom_prop_data_types

        def get_ui_icon_for_prop_type(prop_type):
            """Get the name to display in the UI for a property type"""
            return next((t[3] for t in data_types if t[0] == prop_type), 'ERROR')

        for prop in user_configured_props:

            col_props.separator()
            box = col_props.box()
            row = box.row()
            row.enabled = prop.data_type in (t[0] for t in data_types)

            # Color
            split = row.split(factor=0.1)
            row = split.row(align=True)
            row.alignment = 'LEFT'
            row.prop(prop, "color", text="")

            # Data type
            row = split.row(align=True)
            split = row.split(factor=0.75)
            row = split.row(align=False)
            row.alignment = 'LEFT'
            row.label(text="", icon=get_ui_icon_for_prop_type(prop.data_type))

            # Name
            row.label(text=prop.name)

            # Edit button
            row = split.row(align=True)
            row.alignment = 'RIGHT'
            edit_op = row.operator(
                "edit_breakdown.edit_custom_shot_prop", text="", icon="OUTLINER_DATA_GP_LAYER"
            )
            edit_op.prop_id = prop.identifier
            edit_op.name = prop.name
            edit_op.description = prop.description
            edit_op.data_type = prop.data_type
            edit_op.range_min = prop.range_min
            edit_op.range_max = prop.range_max
            edit_op.enum_items = prop.enum_items
            # Delete button
            row.operator(
                "edit_breakdown.del_custom_shot_prop", text="", icon="X"
            ).prop_id = prop.identifier

            # Extra details for specific prop types
            if prop.data_type == 'INT':
                row = box.row()
                split = row.split(factor=0.1)
                row = split.row(align=True)
                # Leave area under color empty, for alignment
                row = split.row(align=True)
                split = row.split(factor=1.0)
                row = split.row(align=True)
                row.alignment = 'LEFT'
                row.label(text=f"Min: {prop.range_min}  Max: {prop.range_max}")

            elif prop.data_type == 'ENUM_VAL' or prop.data_type == 'ENUM_FLAG':
                row = box.row()
                split = row.split(factor=0.1)
                row = split.row(align=True)
                # Leave area under color empty, for alignment
                row = split.row(align=True)
                split = row.split(factor=1.0)
                row = split.row(align=True)
                row.alignment = 'LEFT'
                row.label(text=str(prop.enum_items))


# Add-on Registration #############################################################################

classes = (
    SEQUENCER_PT_edit_breakdown_overview,
    SEQUENCER_PT_edit_breakdown_shot,
    SEQUENCER_UL_edit_breakdown_scenes,
    SEQUENCER_PT_edit_breakdown_scenes,
    SEQUENCER_PT_edit_breakdown_shot_custom_props,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
