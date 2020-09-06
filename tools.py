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

import logging

import bpy
from bpy.types import (
    Operator,
    WorkSpaceTool,
)
from bpy.props import (
    BoolProperty,
)

from . import view

log = logging.getLogger(__name__)



# Tools ###########################################################################################

def get_thumbnail_under_mouse(mouse_x, mouse_y) -> view.ThumbnailImage:
    """Return the ThumbnailImage currently under the mouse. Possibly None."""

    for thumb in view.thumbnail_images:
        if (mouse_x >= thumb.pos[0] and mouse_x <= thumb.pos[0] + view.thumbnail_size[0] and
            mouse_y >= thumb.pos[1] and mouse_y <= thumb.pos[1] + view.thumbnail_size[1]):
            return thumb

    return None


class SEQUENCER_OT_thumbnail_select(Operator):
    bl_idname = "sequencer.thumbnail_select"
    bl_label = "Thumbnail Select"
    bl_description = "Selects edit breakdown thumbnails"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        """Called when this operator is triggered by user input."""

        if event.type == 'MOUSEMOVE':
            # Determine the thumbnail that is currently under the mouse (if any).
            view.hovered_thumbnail = get_thumbnail_under_mouse(event.mouse_region_x,
                                                               event.mouse_region_y)
        else:
            # Select.

            # Early out when clicking outside the thumbnail draw area.
            # This can happen when clicking on transparent panels that overlap the window area.
            mouse_x = event.mouse_region_x
            mouse_y = event.mouse_region_y
            if (mouse_x < view.thumbnail_draw_region[0] or
                mouse_y < view.thumbnail_draw_region[1] or
                mouse_x > view.thumbnail_draw_region[2] or
                mouse_y > view.thumbnail_draw_region[3]):
                return {'FINISHED'}

            self.execute(context)

        # Request a redraw so that the selection and mouse hover effects are updated.
        context.area.tag_redraw()

        return {'FINISHED'}


    def execute(self, context):
        """Mark the thumbnail under the mouse as selected."""

        # Update draw data
        view.active_selected_thumbnail = view.hovered_thumbnail

        # Update Blender persisted data
        if view.active_selected_thumbnail:
            for i, thumb in enumerate(view.thumbnail_images):
                if thumb == view.hovered_thumbnail:
                    context.scene.edit_breakdown.selected_shot_idx = i
        else:
            context.scene.edit_breakdown.selected_shot_idx = -1

        return {'FINISHED'}


class ThumbnailSelectTool(WorkSpaceTool):
    bl_space_type = 'IMAGE_EDITOR'
    bl_context_mode = 'UV'

    bl_idname = __name__+".thumbnail_select_tool"
    bl_label = "Thumbnail Select"
    bl_description = "This is a tooltip"
    bl_icon = "ops.generic.select_box"
    bl_widget = None
    bl_keymap = (
        # Update mouse hover feedback
        (
            "sequencer.thumbnail_select",
            {"type": 'MOUSEMOVE', "value": 'ANY'},
            {"properties": []}
        ),
        # Execute selection
        (
            "sequencer.thumbnail_select",
            {"type": 'LEFTMOUSE', "value": 'PRESS'},
            {"properties": []}
        ),
        (
            "sequencer.thumbnail_select",
            {"type": 'RIGHTMOUSE', "value": 'PRESS'},
            {"properties": []}
        ),
    )



# Add-on Registration #############################################################################

classes = (
    SEQUENCER_OT_thumbnail_select,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.utils.register_tool(ThumbnailSelectTool)


def unregister():

    bpy.utils.unregister_tool(ThumbnailSelectTool)

    for cls in classes:
        bpy.utils.unregister_class(cls)
