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
    EnumProperty,
    IntProperty,
)

from . import view
from . import data

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
                    break
        else:
            context.scene.edit_breakdown.selected_shot_idx = -1

        return {'FINISHED'}



class SEQUENCER_OT_thumbnail_tag(Operator):
    bl_idname = "sequencer.thumbnail_tag"
    bl_label = "Thumbnail Tag"
    bl_description = "Sets properties of edit breakdown thumbnails"
    bl_options = {'REGISTER', 'UNDO'}

    tag: EnumProperty(
        name="Tag",
        description="Property to set on the shots",
        items=[
            ("has_fx", "Has FX", "If a shot requires VFX work"),
            ("has_crowd", "Has Crowd", "If a shot shows a crowd"),
            ("has_character", "Characters", "The characters present in each shot"),
            ("animation_complexity", "Anim Complexity", "The difficulty factor of a shot, all things considered"),
        ],
        default="has_fx",
    )

    character: EnumProperty(
        name="Characters",
        description="All the characters in the movie",
        items=data.characters,
    )

    tag_value: IntProperty(
        name="Tag Value",
        description="Value to set the chosen property to",
        default=1,
        min=0,
    )

    def get_hovered_thumb(self, context):
        """ Get the thumbnail under the mouse, if any."""

        # Find the hovered thumbnail index in the edit breakdown shot data
        hovered_thumbnail_idx =-1
        for i, thumb in enumerate(view.thumbnail_images):
            if thumb == view.hovered_thumbnail:
                hovered_thumbnail_idx = i
                break

        if hovered_thumbnail_idx < 0:
            return None

        shots = context.scene.edit_breakdown.shots
        return shots[hovered_thumbnail_idx]


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
            # Set a shot property to a predetermined or input value.

            # Early out when clicking outside the thumbnail draw area.
            # This can happen when clicking on transparent panels that overlap the window area.
            mouse_x = event.mouse_region_x
            mouse_y = event.mouse_region_y
            if (mouse_x < view.thumbnail_draw_region[0] or
                mouse_y < view.thumbnail_draw_region[1] or
                mouse_x > view.thumbnail_draw_region[2] or
                mouse_y > view.thumbnail_draw_region[3]):
                return {'FINISHED'}

            # Get the thumbnail under the mouse, if any.
            hovered_shot = self.get_hovered_thumb(context)
            if not hovered_shot:
                return {'FINISHED'}

            # Toggle the tag - Determine the new value to set the property to.
            if event.type == 'LEFTMOUSE':

                # Get the current value of the property
                tag_rna = hovered_shot.rna_type.properties[self.tag]
                is_enum_flag = tag_rna.type == 'ENUM' and tag_rna.is_enum_flag
                if is_enum_flag:
                    #default_value = tag_rna.default_flag
                    #prev_value = hovered_shot.get(self.tag, default_value)
                    # Convert the bitflag value to a set of strings
                    prev_value = hovered_shot.has_character
                else:
                    default_value = tag_rna.default
                    prev_value = hovered_shot.get(self.tag, default_value)

                if tag_rna.type == 'BOOLEAN':
                    # Toggle
                    self.tag_value = not prev_value
                elif tag_rna.type == 'INT':
                    # Cyclic increment
                    self.tag_value = prev_value + 1
                    if self.tag_value > tag_rna.hard_max:
                        self.tag_value = tag_rna.hard_min
                elif is_enum_flag:
                    # Toggle flag
                    self.tag_value = self.character not in prev_value

            # Assign the new tag value
            self.execute(context)

        # Request a redraw so that the selection and mouse hover effects are updated.
        context.area.tag_redraw()

        return {'FINISHED'}


    def execute(self, context):
        """Set the tag to a certain value for the hovered shot."""

        hovered_shot = self.get_hovered_thumb(context)

        if hovered_shot.rna_type.properties[self.tag].type == 'ENUM':
            log.debug(f"Setting '{self.tag}':'{self.character}' to {self.tag_value}")
            character_set = hovered_shot.has_character
            character_set.add(self.character) if self.tag_value else character_set.remove(self.character)
            hovered_shot.has_character = character_set
        else:
            log.debug(f"Setting '{self.tag}' to {self.tag_value}")
            hovered_shot[self.tag] = self.tag_value

        return {'FINISHED'}


class ThumbnailSelectTool(WorkSpaceTool):
    bl_space_type = 'IMAGE_EDITOR'
    bl_context_mode = 'UV'

    bl_idname = __name__+".thumbnail_select_tool"
    bl_label = "Thumbnail Select"
    bl_description = "Select shot Thumbnails"
    bl_icon = "ops.generic.select_box"
    bl_widget = None
    bl_keymap = (
        # Update mouse hover feedback
        (
            "sequencer.thumbnail_select",
            {"type": 'MOUSEMOVE', "value": 'ANY'},
            None
        ),
        # Execute selection
        (
            "sequencer.thumbnail_select",
            {"type": 'LEFTMOUSE', "value": 'PRESS'},
            None
        ),
        (
            "sequencer.thumbnail_select",
            {"type": 'RIGHTMOUSE', "value": 'PRESS'},
            None
        ),
    )


class ThumbnailTagTool(WorkSpaceTool):
    bl_space_type = 'IMAGE_EDITOR'
    bl_context_mode = 'UV'

    bl_idname = __name__+".thumbnail_tag_tool"
    bl_label = "Thumbnail Tag"
    bl_description = "Tag shots with properties"
    bl_icon = "brush.paint_texture.clone"# Stamp-like icon.
    bl_widget = None
    bl_keymap = (
        # Update mouse hover feedback
        (
            "sequencer.thumbnail_tag",
            {"type": 'MOUSEMOVE', "value": 'ANY'},
            None
        ),
        # Tag with pre-selected value
        (
            "sequencer.thumbnail_tag",
            {"type": 'LEFTMOUSE', "value": 'PRESS'},
            None
        ),
        # Tag with numeric value
        (
            "sequencer.thumbnail_tag",
            {"type": 'NUMPAD_0', "value": 'PRESS'},
            {"properties": [("tag_value", 0)]}
        ),
        (
            "sequencer.thumbnail_tag",
            {"type": 'NUMPAD_1', "value": 'PRESS'},
            {"properties": [("tag_value", 1)]}
        ),
        (
            "sequencer.thumbnail_tag",
            {"type": 'NUMPAD_2', "value": 'PRESS'},
            {"properties": [("tag_value", 2)]}
        ),
        (
            "sequencer.thumbnail_tag",
            {"type": 'NUMPAD_3', "value": 'PRESS'},
            {"properties": [("tag_value", 3)]}
        ),
        # Selection
        (
            "sequencer.thumbnail_select",
            {"type": 'RIGHTMOUSE', "value": 'PRESS'},
            None
        ),
    )

    def draw_settings(context, layout, tool):
        props = tool.operator_properties("sequencer.thumbnail_tag")
        layout.prop(props, "tag")
        if props.tag == 'has_character':
            layout.prop(props, "character", text="")



# Add-on Registration #############################################################################

classes = (
    SEQUENCER_OT_thumbnail_select,
    SEQUENCER_OT_thumbnail_tag,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.utils.register_tool(ThumbnailSelectTool)
    bpy.utils.register_tool(ThumbnailTagTool)


def unregister():

    bpy.utils.unregister_tool(ThumbnailSelectTool)
    bpy.utils.unregister_tool(ThumbnailTagTool)

    for cls in classes:
        bpy.utils.unregister_class(cls)
