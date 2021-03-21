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
    bl_category = "Edit Breakdown"
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
    bl_category = "Edit Breakdown"
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


class SEQUENCER_UL_Scenes(UIList):
    """UI List for the scenes in the edit."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        sel_set = item
        layout.prop(item, "name", text="", icon='EXPERIMENTAL', emboss=False)
        # if self.layout_type in ('DEFAULT', 'COMPACT'):
        #    layout.prop(item, "is_selected", text="")


# Add-on Registration #############################################################################

classes = (
    SEQUENCER_PT_edit_breakdown_overview,
    SEQUENCER_PT_edit_breakdown_shot,
    SEQUENCER_UL_Scenes,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
