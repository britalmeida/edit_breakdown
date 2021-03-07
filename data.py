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

import hashlib
import logging
import sys

import bpy
from bpy.app.handlers import persistent
from bpy.types import (
    AddonPreferences,
    Panel,
    PropertyGroup,
    UIList,
)
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from . import utils
from . import view

log = logging.getLogger(__name__)


# Data ############################################################################################

custom_prop_data_types = [
    ("BOOLEAN", "True/False", "Property that is on or off. A Boolean"),
    ("INT", "Number", "An integer value within a custom range"),
    ("STRING", "Text", "Additional details accessible in the properties panel"),
    ("ENUM_FLAG", "Multiple Choice", "Any combination of a set of custom items (enum flag)"),
    ("ENUM_VAL", "Single Choice", "One of a set of custom items (enum value)"),
]


class SEQUENCER_EditBreakdown_CustomProp(PropertyGroup):
    """Definition of a user defined property for a shot."""

    identifier: StringProperty(
        name="Identifier",
        description="Unique name with which Blender can identify this property. "
        "Does not change if the property is renamed",
    )
    name: StringProperty(
        name="Name",
        description="Name to display in the UI. Can be renamed",
        default="New property",
    )
    description: StringProperty(
        name="Description",
        description="Details on the meaning of the property",
        default="",
    )
    data_type: StringProperty(
        name="Type",
        description="The type of data that this property holds",
        default="BOOLEAN",
    )
    range_min: IntProperty(
        name="Min",
        description="The minimum value that the property can have if it is a number",
        default=0,
    )
    range_max: IntProperty(
        name="Max",
        description="The maximum value that the property can have if it is a number",
        default=5,
    )
    enum_items: StringProperty(
        name="Items",
        description="Possible values for the property if it is an enum. Comma separated list of options",
        default="Option 1, Option 2",
    )
    color: FloatVectorProperty(
        name="Color",
        description="Associated color to be used by the Tag tool",
        subtype="COLOR_GAMMA",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.4, 0.6, 0.75, 1.0),  # Some blue
    )


class SEQUENCER_EditBreakdown_Shot(PropertyGroup):
    """Properties of a shot."""

    name: StringProperty(
        name="Shot Name",
        description="Name of this shot",
    )
    frame_start: IntProperty(
        name="Start Frame",
        description="Frame at which this shot starts",
        subtype="TIME",
    )
    frame_count: IntProperty(
        name="Frame Count",
        description="Total number of frame this shot has",
        subtype="TIME",
        soft_min=0,
        default=0,
    )
    timeline_marker: StringProperty(
        name="Timeline Marker UUID",
        description="Unequivocally links this shot with a timeline marker",
    )

    @property
    def duration_seconds(self):
        """The duration of this shot, in seconds"""
        fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
        return round(self.frame_count / fps, 1)

    def count_bits_in_flag(self, prop_id):
        """The total number of options chosen in a multiple choice property."""
        value = self.get_prop_value(prop_id)
        prop_rna = self.rna_type.properties[prop_id]

        count = 0
        for item in prop_rna.enum_items:
            if int(item.identifier) & value:
                count += 1
        return count, len(prop_rna.enum_items)

    @classmethod
    def has_prop(cls, prop_id: str) -> bool:
        """True if this class has a registered property under the identifier 'prop_id'."""
        properties = {prop.identifier for prop in cls.bl_rna.properties if prop.is_runtime}
        return prop_id in properties

    def set_prop_value(self, prop_id: str, value) -> bool:
        """Set the value of a property."""
        if self.__class__.has_prop(prop_id):
            # Note: See note about 'exec' in register_custom_prop().
            exec(f"self.{prop_id} = {value}")
            return True
        else:
            return False

    def get_prop_value(self, prop_id: str) -> int:
        """Get the current value of the property"""
        prop_rna = self.rna_type.properties[prop_id]
        is_enum_flag = prop_rna.type == 'ENUM' and prop_rna.is_enum_flag
        if is_enum_flag:
            default_value = 0  # prop_rna.default_flag is a set. TODO convert set to int.
        else:
            default_value = prop_rna.default
        return int(self.get(prop_id, default_value))

    @classmethod
    def get_hardcoded_properties(cls):
        """Get a list of the properties that are managed by this add-on (not user defined)"""
        return ['name', 'frame_start', 'frame_count', 'timeline_marker']

    @classmethod
    def get_custom_properties(cls):
        """Get a list of the user defined properties for Shots"""
        custom_rna_properties = {
            prop
            for prop in cls.bl_rna.properties
            if (prop.is_runtime and prop.identifier not in cls.get_hardcoded_properties())
        }
        return sorted(custom_rna_properties, key=lambda x: x.name, reverse=False)

    @classmethod
    def get_csv_export_header(cls):
        """Returns a list of human readable names for the CSV column headers"""
        attrs = ['Name', 'Start Frame', 'Timestamp', 'Duration (s)']
        for prop in cls.get_custom_properties():
            if prop.type == 'INT':
                attrs.append(f"{prop.name} ({prop.hard_min}-{prop.hard_max})")
            elif prop.type == 'ENUM' and prop.is_enum_flag:
                attrs.append(f"{prop.name} Count ({len(prop.enum_items)})")
                for item in prop.enum_items:
                    attrs.append(f"{item.name}")
            elif prop.type == 'ENUM' and not prop.is_enum_flag:
                attrs.append(f"{prop.name} (value)")
                attrs.append(f"{prop.name} (named)")
            else:
                attrs.append(prop.name)
        return attrs

    def get_csv_export_values(self):
        """Returns a list of values for the CSV exported properties"""
        values = [
            self.name,
            self.frame_start,
            utils.timestamp_str(self.frame_start),
            self.duration_seconds,
        ]
        for prop in self.get_custom_properties():
            if prop.type == 'ENUM' and prop.is_enum_flag:
                # Add count
                num_chosen_options, total_options = self.count_bits_in_flag(prop.identifier)
                values.append(num_chosen_options)
                # Add each option as a boolean
                value = self.get_prop_value(prop.identifier)
                for item in prop.enum_items:
                    values.append(1 if int(item.identifier) & value else 0)
            elif prop.type == 'ENUM' and not prop.is_enum_flag:
                option_value = self.get_prop_value(prop.identifier)
                values.append(option_value)
                values.append("" if option_value == -1 else prop.enum_items[option_value].name)
            elif prop.type == 'STRING':
                values.append(self.get(prop.identifier, ""))
            else:
                values.append(self.get_prop_value(prop.identifier))
        return values


class SEQUENCER_EditBreakdown_Scene(PropertyGroup):
    """Properties of a scene."""

    name: StringProperty(
        name="Scene Name",
        description="Name of this scene",
    )


class SEQUENCER_EditBreakdown_Data(PropertyGroup):

    scenes: CollectionProperty(
        type=SEQUENCER_EditBreakdown_Scene,
        name="Scenes",
        description="Set of scenes that logically group shots",
    )

    active_scene_idx: IntProperty(
        name="Active Scene",
        description="Index of the currently active scene in the UIList",
        default=0,
    )

    shots: CollectionProperty(
        type=SEQUENCER_EditBreakdown_Shot,
        name="Shots",
        description="Set of shots that form the edit",
    )

    selected_shot_idx: IntProperty(
        name="Selected Shot",
        description="The active selected shot (last selected, if any).",
        default=-1,
    )

    shot_custom_props: CollectionProperty(
        type=SEQUENCER_EditBreakdown_CustomProp,
        name="Shot Custom Properties",
        description="Data that can be set per shot",
    )

    @property
    def total_frames(self):
        """The total number of frames in the edit, according to the shot range"""

        if len(self.shots) < 1:
            return 0
        first_shot = self.shots[0]
        last_shot = self.shots[-1]
        return last_shot.frame_start + last_shot.frame_count - first_shot.frame_start


# Settings ########################################################################################


class SEQUENCER_EditBreakdown_Preferences(AddonPreferences):
    bl_idname = "edit_breakdown"

    def get_thumbnails_dir(self) -> str:
        """Generate a path based on get_datadir and the current file name.

        The path is constructed by combining the OS application data dir,
        "blender-edit-breakdown" and a hashed version of the filepath.

        Note: If a file is moved, the thumbnails will need to be recomputed.
        """
        hashed_filename = hashlib.md5(bpy.data.filepath.encode()).hexdigest()
        storage_dir = get_datadir() / 'blender-edit-breakdown' / hashed_filename
        storage_dir.mkdir(parents=True, exist_ok=True)
        return str(storage_dir)

    edit_shots_folder: StringProperty(
        name="Edit Shots",
        description="Folder with image thumbnails for each shot",
        default="",
        subtype="FILE_PATH",
        get=get_thumbnails_dir,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False

        col = layout.column()
        col.prop(self, "edit_shots_folder", text="Thumbnails Folder")

        col_props = layout.column()
        row = col_props.row()
        row.label(text="Shot Properties:")
        sub = row.row(align=True)
        sub.enabled = False
        sub.operator("edit_breakdown.copy_custom_shot_props", icon='COPYDOWN', text="")
        sub.operator("edit_breakdown.paste_custom_shot_props", icon='PASTEDOWN', text="")
        row.operator("edit_breakdown.shot_properties_tooltip", icon='QUESTION', text="")

        edit_breakdown = context.scene.edit_breakdown
        user_configured_props = edit_breakdown.shot_custom_props

        def get_ui_name_for_prop_type(prop_type):
            """Get the name to display in the UI for a property type"""
            return next((t[1] for t in custom_prop_data_types if t[0] == prop_type), "Unsupported")

        for prop in user_configured_props:

            box = col_props.box()
            row = box.row()
            row.enabled = prop.data_type in (t[0] for t in custom_prop_data_types)

            split = row.split(factor=0.1)
            row = split.row(align=True)
            row.alignment = 'LEFT'
            row.prop(prop, "color", text="")

            row = split.row(align=True)
            split = row.split(factor=0.2)
            row = split.row(align=True)
            row.alignment = 'LEFT'
            row.label(text=get_ui_name_for_prop_type(prop.data_type))

            row = split.row(align=True)
            split = row.split(factor=0.65)
            row = split.row(align=True)
            row.alignment = 'LEFT'

            row.label(text=prop.name)
            row.label(text=prop.description)

            row = split.row(align=False)
            edit_op = row.operator("edit_breakdown.edit_custom_shot_prop", text="Edit")
            edit_op.prop_id = prop.identifier
            edit_op.name = prop.name
            edit_op.description = prop.description
            edit_op.data_type = prop.data_type
            edit_op.range_min = prop.range_min
            edit_op.range_max = prop.range_max
            edit_op.enum_items = prop.enum_items
            row.operator(
                "edit_breakdown.del_custom_shot_prop", text="Delete"
            ).prop_id = prop.identifier

            if prop.data_type == 'INT':
                row = box.row()
                split = row.split(factor=0.1)
                row = split.row(align=True)
                row = split.row(align=True)
                split = row.split(factor=0.2)
                row = split.row(align=True)
                row.alignment = 'LEFT'
                row.label(text="Range:")

                row = split.row(align=True)
                split = row.split(factor=0.65)
                row = split.row(align=True)
                row.alignment = 'LEFT'
                row.label(text=f"Min: {prop.range_min}  Max: {prop.range_max}")

            elif prop.data_type == 'ENUM_VAL' or prop.data_type == 'ENUM_FLAG':
                row = box.row()
                split = row.split(factor=0.1)
                row = split.row(align=True)
                row = split.row(align=True)
                split = row.split(factor=0.2)
                row = split.row(align=True)
                row.alignment = 'LEFT'
                row.label(text="Items:")

                row = split.row(align=True)
                split = row.split(factor=0.65)
                row = split.row(align=True)
                row.alignment = 'LEFT'
                row.label(text=str(prop.enum_items))

            col_props.separator()

        # 'Add Property' button
        row = col_props.row()
        row.operator("edit_breakdown.add_custom_shot_prop")

        # Sequences configuration
        col = layout.column()
        col.label(text="Scenes:")

        # UI list
        num_rows = 4 if len(edit_breakdown.scenes) > 0 else 1
        row = col.row()
        # fmt: off
        row.template_list(
            "SEQUENCER_UL_Scenes", "",  # Type and unique id.
            edit_breakdown, "scenes",  # Pointer to the CollectionProperty.
            edit_breakdown, "active_scene_idx",  # Pointer to the active identifier.
            rows=num_rows,
        )
        # fmt: on
        but_col = row.column(align=True)
        but_col.operator("edit_breakdown.add_scene", icon='ADD', text="")
        but_col.operator("edit_breakdown.del_scene", icon='REMOVE', text="")


# UI ##############################################################################################


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

        shots = context.scene.edit_breakdown.shots
        sel_idx = context.scene.edit_breakdown.selected_shot_idx

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

        # Show user-defined properties
        shot_cls = SEQUENCER_EditBreakdown_Shot
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


# Property Registration On File Load ##############################################################


def register_custom_prop(data_cls, prop):
    extra_prop_config = ""
    if prop.data_type == 'BOOLEAN':
        prop_ctor = "BoolProperty"
    elif prop.data_type == 'INT':
        prop_ctor = "IntProperty"
        extra_prop_config = f"min={prop.range_min}, max={prop.range_max}"
    elif prop.data_type == 'STRING':
        prop_ctor = "StringProperty"
    elif prop.data_type == 'ENUM_VAL' or prop.data_type == 'ENUM_FLAG':
        prop_ctor = "EnumProperty"

        # Construct the enum items
        enum_items = []
        idx = 1
        items = [i.strip() for i in prop.enum_items.split(',')]
        for item_human_name in items:
            if item_human_name:
                item_code_name = str(idx)
                enum_items.append((item_code_name, item_human_name, ""))
                idx *= 2  # Powers of 2, for use in bit flags.
        extra_prop_config = f"items={enum_items},"

        if prop.data_type == 'ENUM_FLAG':
            extra_prop_config += " options={'ENUM_FLAG'},"
    if prop_ctor:
        # Note: 'exec': is used because prop.identifier is data driven.
        # I don't know of a way to create a new RNA property from a function that
        # receives a string instead of assignment.
        # prop.identifier is fully controlled by code, not user input, and therefore
        # there should be no danger of code injection.
        registration_expr = (
            f"data_cls.{prop.identifier} = {prop_ctor}(name='{prop.name}', "
            f"description='{prop.description}', {extra_prop_config})"
        )
        log.debug(f"Registering custom property: {registration_expr}")
        exec(registration_expr)


def unregister_custom_prop(data_cls, prop_identifier):
    # Note: 'exec': is used because prop.identifier is data driven. See note above.
    exec(f"del data_cls.{prop_identifier}")


@persistent
def register_custom_properties(scene):
    """Register the custom shot and sequence data.

    The custom data is defined on a per-file basis (as opposed to user settings).
    Whenever loading a file, this function ensures that the custom data defined
    for that file is resolved to defined properties.
    """

    log.info("Registering custom properties for loaded file")

    # Register custom shot properties
    shot_cls = SEQUENCER_EditBreakdown_Shot
    custom_props = bpy.context.scene.edit_breakdown.shot_custom_props
    log.debug(f"{len(custom_props)} custom props")
    for prop in custom_props:
        register_custom_prop(shot_cls, prop)

    # Register custom sequence properties
    pass


@persistent
def unregister_custom_properties(scene):
    """Unregister the custom shot and sequence data"""

    log.info("Unregistering custom properties for loaded file")

    # Unregister custom shot properties
    shot_cls = SEQUENCER_EditBreakdown_Shot
    custom_props = bpy.context.scene.edit_breakdown.shot_custom_props
    log.debug(f"{len(custom_props)} custom props")
    for prop in custom_props:
        unregister_custom_prop(shot_cls, prop.identifier)

    # Unregister custom sequence properties
    pass


# Add-on Registration #############################################################################

classes = (
    SEQUENCER_EditBreakdown_Preferences,
    SEQUENCER_EditBreakdown_CustomProp,
    SEQUENCER_EditBreakdown_Shot,
    SEQUENCER_EditBreakdown_Scene,
    SEQUENCER_EditBreakdown_Data,
    SEQUENCER_PT_edit_breakdown_overview,
    SEQUENCER_PT_edit_breakdown_shot,
    SEQUENCER_UL_Scenes,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.edit_breakdown = PointerProperty(
        name="Edit Breakdown",
        type=SEQUENCER_EditBreakdown_Data,
        description="Shot data used by the Edit Breakdown add-on.",
    )

    bpy.app.handlers.load_pre.append(unregister_custom_properties)
    bpy.app.handlers.load_post.append(register_custom_properties)


def unregister():

    bpy.app.handlers.load_pre.remove(unregister_custom_properties)
    bpy.app.handlers.load_post.remove(register_custom_properties)

    del bpy.types.Scene.edit_breakdown

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
