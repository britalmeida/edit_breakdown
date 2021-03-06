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
from bpy.app.handlers import persistent
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
        if (
            mouse_x >= thumb.pos[0]
            and mouse_x <= thumb.pos[0] + view.thumbnail_size[0]
            and mouse_y >= thumb.pos[1]
            and mouse_y <= thumb.pos[1] + view.thumbnail_size[1]
        ):
            return thumb

    return None


def select_shot(scene, new_selected_thumbnail):
    """Select the shot matching the given thumbnail (may be None)."""

    # Update draw data
    view.active_selected_thumbnail = new_selected_thumbnail

    # Update Blender persisted data
    if new_selected_thumbnail:
        for i, thumb in enumerate(view.thumbnail_images):
            if thumb == new_selected_thumbnail:
                scene.edit_breakdown.selected_shot_idx = i
                break
    else:
        scene.edit_breakdown.selected_shot_idx = -1

    # Select corresponding timeline marker
    shots = scene.edit_breakdown.shots
    sel_shot_idx = scene.edit_breakdown.selected_shot_idx
    marker_uuid = shots[sel_shot_idx].timeline_marker
    marker = None

    markers = scene.timeline_markers
    for m in markers:
        m.select = False
        if not m.get('uuid'):
            continue
        if m['uuid'] == marker_uuid:
            marker = m

    if marker:
        marker.select = True


@persistent
def update_selected_shot(scene):
    """Callback when the current frame is changed."""

    shot_idx_to_select = -1

    shots = scene.edit_breakdown.shots
    for i, shot in enumerate(shots):
        if shot.frame_start > scene.frame_current:
            break
        shot_idx_to_select = i

    if shot_idx_to_select >= 0 and shot_idx_to_select < len(view.thumbnail_images):
        thumbnail_to_select = view.thumbnail_images[shot_idx_to_select]
    else:
        thumbnail_to_select = None

    select_shot(scene, thumbnail_to_select)


class SEQUENCER_OT_thumbnail_select(Operator):
    bl_idname = "edit_breakdown.thumbnail_select"
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
            view.hovered_thumbnail = get_thumbnail_under_mouse(
                event.mouse_region_x, event.mouse_region_y
            )
        else:
            # Select.

            # Early out when clicking outside the thumbnail draw area.
            # This can happen when clicking on transparent panels that overlap the window area.
            mouse_x = event.mouse_region_x
            mouse_y = event.mouse_region_y
            if (
                mouse_x < view.thumbnail_draw_region[0]
                or mouse_y < view.thumbnail_draw_region[1]
                or mouse_x > view.thumbnail_draw_region[2]
                or mouse_y > view.thumbnail_draw_region[3]
            ):
                return {'FINISHED'}

            self.execute(context)

        # Request a redraw so that the selection and mouse hover effects are updated.
        context.area.tag_redraw()

        return {'FINISHED'}

    def execute(self, context):
        """Mark the thumbnail under the mouse as selected."""

        select_shot(context.scene, view.hovered_thumbnail)

        # Update the current frame to match
        eb = context.scene.edit_breakdown
        if eb.selected_shot_idx >= 0:
            new_frame = eb.shots[eb.selected_shot_idx].frame_start
            context.scene.frame_current = new_frame

        return {'FINISHED'}


class SEQUENCER_OT_thumbnail_tag(Operator):
    bl_idname = "edit_breakdown.thumbnail_tag"
    bl_label = "Thumbnail Tag"
    bl_description = "Sets properties of edit breakdown thumbnails"
    bl_options = {'REGISTER', 'UNDO'}

    # Workaround Note: Blender will store the current value of dynamic enum props as an int instead
    # of the identifier. This causes issues when deleting/adding custom props as the selected enum
    # item won't be stable. As a workaround, backup the enum value as a string and override the
    # enum prop's get/set to keep its current value in sync by identifier instead of by position.
    tag_str: str = None  # Shadow copy of the current 'tag' enum value as a str.
    tag_enum_items = []

    def populate_enum_items_for_shot_custom_properties(self, context):
        """Generate a complete list of shot properties as an enum list."""

        # Add user-defined properties
        enum_items = []
        user_configured_props = bpy.context.scene.edit_breakdown.shot_custom_props
        for prop in user_configured_props:
            if prop.data_type in ['BOOLEAN', 'INT', 'ENUM_FLAG', 'ENUM_VAL']:
                enum_items.append((prop.identifier, prop.name, prop.description))

        # Store the enum items in this class to workaround a bug where Blender mangles the strings.
        SEQUENCER_OT_thumbnail_tag.tag_enum_items = enum_items

        return SEQUENCER_OT_thumbnail_tag.tag_enum_items

    def populate_enum_items_for_enum_property(self, context):
        """Generate an enum list with the available options for an enum property."""

        # Find the property definition.
        shot_cls = data.SEQUENCER_EditBreakdown_Shot
        prop_rna = shot_cls.bl_rna.properties[self.tag]

        # Copy the property's enum items to the tool's enum item,
        enum_items = []
        if prop_rna.type == 'ENUM':
            for item in prop_rna.enum_items:
                enum_items.append((item.identifier, item.name, item.description))
        return enum_items

    def get_tag(self):
        """Get the current value of the tag enum prop by matching it with tag_str"""

        # Collect the IDs of all taggable custom properties.
        # Note: don't re-use the IDs stored in the class variable to workaround the string mangling.
        prop_ids = []
        user_configured_props = bpy.context.scene.edit_breakdown.shot_custom_props
        for prop in user_configured_props:
            if prop.data_type in ['BOOLEAN', 'INT', 'ENUM_FLAG', 'ENUM_VAL']:
                prop_ids.append(prop.identifier)

        if prop_ids:
            curent_int_value = self["tag"]

            for i, prop_id in enumerate(prop_ids):
                # If the backup enum value as string was not set yet, set it
                if not SEQUENCER_OT_thumbnail_tag.tag_str and i == curent_int_value:
                    SEQUENCER_OT_thumbnail_tag.tag_str = prop_id
                    return i
                # Found prop matching the identifier?
                if prop_id == SEQUENCER_OT_thumbnail_tag.tag_str:
                    return i

        # Could not find a match.
        # Either the previous selected prop was deleted or there are no props.
        SEQUENCER_OT_thumbnail_tag.tag_str = None
        return 0

    def set_tag(self, value):
        """Set the current value of the tag enum prop and of tag_str"""

        # Set the value as normal
        self["tag"] = value

        # Backup the tag value as a string
        enum_item = SEQUENCER_OT_thumbnail_tag.tag_enum_items[value]
        SEQUENCER_OT_thumbnail_tag.tag_str = enum_item[0]

    def on_tag_update(self, context):
        """Callback when the current tag is changed"""

        shot_cls = data.SEQUENCER_EditBreakdown_Shot
        prop_rna = shot_cls.bl_rna.properties[self.tag]
        is_enum = prop_rna.type == 'ENUM'
        self.tag_enum_option = "1"

    tag: EnumProperty(
        name="Tag",
        description="Property to set on the shots",
        items=populate_enum_items_for_shot_custom_properties,
        update=on_tag_update,
        get=get_tag,
        set=set_tag,
    )
    tag_enum_option: EnumProperty(
        name="Options",
        description="Possible values for the chosen property",
        items=populate_enum_items_for_enum_property,
    )
    tag_value: IntProperty(
        name="Tag Value",
        description="Value to set the chosen property to",
        default=1,
    )

    def get_hovered_shot(self, context):
        """Get the shot represented by the thumbnail under the mouse, if any."""

        # Find the hovered thumbnail index in the edit breakdown shot data
        hovered_thumbnail_idx = -1
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
            view.hovered_thumbnail = get_thumbnail_under_mouse(
                event.mouse_region_x, event.mouse_region_y
            )
        else:
            # Set a shot property to a predetermined or input value.

            # Early out when clicking outside the thumbnail draw area.
            # This can happen when clicking on transparent panels that overlap the window area.
            mouse_x = event.mouse_region_x
            mouse_y = event.mouse_region_y
            if (
                mouse_x < view.thumbnail_draw_region[0]
                or mouse_y < view.thumbnail_draw_region[1]
                or mouse_x > view.thumbnail_draw_region[2]
                or mouse_y > view.thumbnail_draw_region[3]
            ):
                return {'FINISHED'}

            # Get the thumbnail under the mouse, if any.
            hovered_shot = self.get_hovered_shot(context)
            if not hovered_shot:
                return {'FINISHED'}

            # Get the current value of the property
            tag_rna = hovered_shot.rna_type.properties[self.tag]
            prev_value = hovered_shot.get_prop_value(self.tag)

            # Toggle the tag - Determine the new value to set the property to.
            if event.type == 'LEFTMOUSE':
                if tag_rna.type == 'BOOLEAN':
                    # Toggle
                    self.tag_value = not prev_value
                elif tag_rna.type == 'INT':
                    # Cyclic increment
                    self.tag_value = prev_value + 1
                    if self.tag_value > tag_rna.hard_max:
                        self.tag_value = tag_rna.hard_min
                elif tag_rna.type == 'ENUM':
                    if tag_rna.is_enum_flag:
                        # Toggle flag
                        self.tag_value = prev_value ^ int(self.tag_enum_option)
                    else:
                        # Set to the currently chosen enum option or unset
                        enum_option_val = int(self.tag_enum_option).bit_length() - 1
                        if prev_value == enum_option_val:
                            self.tag_value = -1
                        else:
                            self.tag_value = enum_option_val

            # Sanitize direct value assignment
            elif event.type in {
                'NUMPAD_0',
                'NUMPAD_1',
                'NUMPAD_2',
                'NUMPAD_3',
                'NUMPAD_4',
                'NUMPAD_5',
                'NUMPAD_6',
                'NUMPAD_7',
                'NUMPAD_8',
                'NUMPAD_9',
                'ONE',
                'TWO',
                'THREE',
                'FOUR',
                'FIVE',
                'SIX',
                'SEVEN',
                'EIGHT',
                'NINE',
            }:

                if tag_rna.type == 'BOOLEAN':  # 0 or 1, not higher
                    self.tag_value = 0 if self.tag_value == 0 else 1
                elif tag_rna.type == 'INT':  # Clamp to user-defined range
                    self.tag_value = max(tag_rna.hard_min, min(self.tag_value, tag_rna.hard_max))
                elif tag_rna.type == 'ENUM':  # Input of 0 or 1 should toggle active flag on/off
                    if tag_rna.is_enum_flag:
                        if self.tag_value == 0:
                            self.tag_value = prev_value & ~int(self.tag_enum_option)
                        else:  # 1 or higher is "turn on"
                            self.tag_value = prev_value | int(self.tag_enum_option)
                    else:
                        if self.tag_value == 0:
                            self.tag_value = -1
                        else:  # 1 or higher is "turn on"
                            self.tag_value = int(self.tag_enum_option).bit_length() - 1

            # Assign the new tag value
            self.execute(context)

        # Request a redraw so that the selection and mouse hover effects are updated.
        context.area.tag_redraw()

        return {'FINISHED'}

    def execute(self, context):
        """Set the tag to a certain value for the hovered shot."""

        hovered_shot = self.get_hovered_shot(context)

        log.debug(f"Setting '{self.tag}' to {self.tag_value}")
        hovered_shot[self.tag] = self.tag_value

        return {'FINISHED'}


class ThumbnailSelectTool(WorkSpaceTool):
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_context_mode = 'PREVIEW'

    bl_idname = "edit_breakdown.thumbnail_select_tool"
    bl_label = "Thumbnail Select"
    bl_description = "Select shot Thumbnails"
    bl_icon = "ops.generic.select_box"
    bl_widget = None
    bl_keymap = (
        # Update mouse hover feedback
        ("edit_breakdown.thumbnail_select", {"type": 'MOUSEMOVE', "value": 'ANY'}, None),
        # Execute selection
        ("edit_breakdown.thumbnail_select", {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),
        ("edit_breakdown.thumbnail_select", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, None),
    )


class ThumbnailTagTool(WorkSpaceTool):
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_context_mode = 'PREVIEW'

    bl_idname = "edit_breakdown.thumbnail_tag_tool"
    bl_label = "Thumbnail Tag"
    bl_description = "Tag shots with properties"
    bl_icon = "brush.paint_texture.clone"  # Stamp-like icon.
    bl_widget = None
    bl_keymap = (
        # Update mouse hover feedback
        ("edit_breakdown.thumbnail_tag", {"type": 'MOUSEMOVE', "value": 'ANY'}, None),
        # Tag with pre-selected value
        ("edit_breakdown.thumbnail_tag", {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),
        # Tag with numeric value
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'NUMPAD_0', "value": 'PRESS'},
            {"properties": [("tag_value", 0)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'NUMPAD_1', "value": 'PRESS'},
            {"properties": [("tag_value", 1)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'NUMPAD_2', "value": 'PRESS'},
            {"properties": [("tag_value", 2)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'NUMPAD_3', "value": 'PRESS'},
            {"properties": [("tag_value", 3)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'NUMPAD_4', "value": 'PRESS'},
            {"properties": [("tag_value", 4)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'NUMPAD_5', "value": 'PRESS'},
            {"properties": [("tag_value", 5)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'NUMPAD_6', "value": 'PRESS'},
            {"properties": [("tag_value", 6)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'NUMPAD_7', "value": 'PRESS'},
            {"properties": [("tag_value", 7)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'NUMPAD_8', "value": 'PRESS'},
            {"properties": [("tag_value", 8)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'NUMPAD_9', "value": 'PRESS'},
            {"properties": [("tag_value", 9)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'ZERO', "value": 'PRESS'},
            {"properties": [("tag_value", 0)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'ONE', "value": 'PRESS'},
            {"properties": [("tag_value", 1)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'TWO', "value": 'PRESS'},
            {"properties": [("tag_value", 2)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'THREE', "value": 'PRESS'},
            {"properties": [("tag_value", 3)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'FOUR', "value": 'PRESS'},
            {"properties": [("tag_value", 4)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'FIVE', "value": 'PRESS'},
            {"properties": [("tag_value", 5)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'SIX', "value": 'PRESS'},
            {"properties": [("tag_value", 6)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'SEVEN', "value": 'PRESS'},
            {"properties": [("tag_value", 7)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'EIGHT', "value": 'PRESS'},
            {"properties": [("tag_value", 8)]},
        ),
        (
            "edit_breakdown.thumbnail_tag",
            {"type": 'NINE', "value": 'PRESS'},
            {"properties": [("tag_value", 9)]},
        ),
        # Selection
        ("edit_breakdown.thumbnail_select", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        props = tool.operator_properties("edit_breakdown.thumbnail_tag")

        if not props.tag:
            layout.label(
                icon='QUESTION',
                text="Shot properties can be configured in the edit breakdown add-on settings",
            )
            return
        layout.prop(props, "tag")

        shot_cls = data.SEQUENCER_EditBreakdown_Shot
        prop_rna = shot_cls.bl_rna.properties[props.tag]
        if prop_rna.type == 'ENUM':
            layout.prop(props, "tag_enum_option", text="")


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

    bpy.app.handlers.frame_change_post.append(update_selected_shot)


def unregister():

    bpy.app.handlers.frame_change_post.remove(update_selected_shot)

    bpy.utils.unregister_tool(ThumbnailSelectTool)
    bpy.utils.unregister_tool(ThumbnailTagTool)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
