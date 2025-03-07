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

import bpy
from bpy.app.handlers import persistent
from bpy.types import (
    AddonPreferences,
    PropertyGroup,
)
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,  # Needed to register a custom prop with exec
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from . import ADDON_ID
from . import utils

# Note:
# __name__  expected to be: (add-on) edit_breakdown.data
#                       or  (extson) bl_ext.addons_dev.edit_breakdown.data
# package_name  expected to be: edit_breakdown
# package_name = pathlib.Path(__file__).parent.name
log = logging.getLogger(__name__)


custom_prop_data_types = [
    ("BOOLEAN", "True/False", "Property that is on or off. A Boolean", 'CHECKMARK', 0),
    ("INT", "Number", "An integer value within a custom range", 'DRIVER_TRANSFORM', 1),
    ("ENUM_FLAG", "Multiple Choice", "Any combination of a custom item set", 'PIVOT_INDIVIDUAL', 2),
    ("ENUM_VAL", "Single Choice", "One of a set of custom items", 'PIVOT_ACTIVE', 3),
    ("STRING", "Text", "Additional details accessible in the properties panel", 'SMALL_CAPS', 4),
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
        default="ENUM_FLAG",
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
        description="Possible values for the property if it is an enum. "
                    "Comma separated list of options",
        default="Option 1, Option 2",
    )
    color: FloatVectorProperty(
        name="Color",
        description="Associated color to be used by the Tag tool",
        subtype="COLOR_GAMMA",
        size=[4],
        min=0.0,
        max=1.0,
        default=[0.4, 0.6, 0.75, 1.0],  # Some blue
    )


class SEQUENCER_EditBreakdown_Scene(PropertyGroup):
    """Properties of a scene."""

    uuid: StringProperty(
        name="UUID",
        description="Unique identifier for this scene",
    )
    color: FloatVectorProperty(
        name="Color",
        description="Color used to visually distinguish this scene from others",
        subtype="COLOR_GAMMA",
        size=[4],
        min=0.0,
        max=1.0,
        default=[0.88, 0.58, 0.38, 1.0],  # Pale peach
    )


class SEQUENCER_EditBreakdown_Shot(PropertyGroup):
    """Properties of a shot."""

    frame_start: IntProperty(
        name="Start Frame",
        description="Frame at which this shot starts",
        subtype="TIME",
    )
    frame_count: IntProperty(
        name="Frame Count",
        description="Total number of frames this shot has",
        subtype="TIME",
        soft_min=0,
        default=0,
    )
    thumbnail_file: StringProperty(
        name="Thumbnail File",
        description="Filename of the thumbnail image for this shot",
    )
    strip_name: StringProperty(
        name="Strip Name",
        description="Unequivocally links this shot with a sequencer strip",
    )
    scene_uuid: StringProperty(
        name="Scene UUID",
        description="UUID of the edit scene that this shot is part of",
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
        return ['name', 'frame_start', 'frame_count', 'thumbnail_file', 'strip_name', 'scene_uuid']

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
        """Returns a list of human-readable names for the CSV column headers"""
        attrs = ['Name', 'Thumbnail File', 'Start Frame', 'Timestamp', 'Duration (s)', 'Scene']
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

        # Add values of the hardcoded properties
        values = [
            self.name,
            self.thumbnail_file,
            self.frame_start,
            utils.timestamp_str(self.frame_start),
            self.duration_seconds,
        ]
        # Add the scene this shot belongs to by name
        edit_breakdown = bpy.context.scene.edit_breakdown
        eb_scene = edit_breakdown.find_scene(self.scene_uuid)
        values.append(eb_scene.name if eb_scene else "")

        # Add values of the user-defined properties
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

    view_grouped_by_scene: BoolProperty(
        name="View Grouped by Scene",
        description="Should the shot thumbnails show grouped by scene?",
        default=False,
    )

    @property
    def total_frames(self):
        """The total number of frames in the edit, including overlapping frames"""
        num_frames = 0
        for shot in self.shots:
            num_frames += shot.frame_count
        return num_frames

    def find_scene(self, scene_uuid: str) -> SEQUENCER_EditBreakdown_Scene:
        """Returns the edit scene matching the given UUID"""
        return next((sc for sc in self.scenes if sc.uuid == scene_uuid), None)


# Settings ########################################################################################


class SEQUENCER_EditBreakdown_Preferences(AddonPreferences):
    bl_idname = ADDON_ID

    def get_thumbnails_dir(self) -> str:
        """Generate a path based on get_datadir and the current file name.

        The path is constructed by combining the OS application data dir,
        "blender-edit-breakdown" and a hashed version of the filepath.

        Note: If a file is moved, the thumbnails will need to be recomputed.
        """
        hashed_filename = hashlib.md5(bpy.data.filepath.encode()).hexdigest()
        storage_dir = utils.get_datadir() / 'blender-edit-breakdown' / hashed_filename
        storage_dir.mkdir(parents=True, exist_ok=True)
        return str(storage_dir)

    edit_shots_folder: StringProperty(
        name="Edit Shots",
        description="Folder with image thumbnails for each shot",
        default="",
        subtype="DIR_PATH",
        get=get_thumbnails_dir,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False

        col = layout.column()
        col.prop(self, "edit_shots_folder", text="Thumbnails Folder")


# Property Registration On File Load ##############################################################

def register_custom_prop(data_cls, prop):
    prop_ctor = ""
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
    """Register the custom shot and scene data.

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

    # Register custom scene properties
    pass


@persistent
def unregister_custom_properties(scene):
    """Unregister the custom shot and scene data"""

    log.info("Unregistering custom properties for loaded file")

    # Unregister custom shot properties
    shot_cls = SEQUENCER_EditBreakdown_Shot
    custom_props = bpy.context.scene.edit_breakdown.shot_custom_props
    log.debug(f"{len(custom_props)} custom props")
    for prop in custom_props:
        unregister_custom_prop(shot_cls, prop.identifier)

    # Unregister custom scene properties
    pass


# Add-on Registration #############################################################################

classes = (
    SEQUENCER_EditBreakdown_Preferences,
    SEQUENCER_EditBreakdown_CustomProp,
    SEQUENCER_EditBreakdown_Scene,
    SEQUENCER_EditBreakdown_Shot,
    SEQUENCER_EditBreakdown_Data,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.edit_breakdown = PointerProperty(
        name="Edit Breakdown",
        type=SEQUENCER_EditBreakdown_Data,
        description="Shot data used by the Edit Breakdown add-on.",
    )

    bpy.types.Sequence.use_for_edit_breakdown = BoolProperty(
        name="Use For Edit Breakdown",
        default=False,
        description="If this strip should be included as a shot in the edit breakdown view",
    )

    # TODO Extending space data doesn't work?
    # bpy.types.SpaceSequenceEditor.show_edit_breakdown_view = BoolProperty(
    #     name="Show Edit Breakdown",
    #     default=False,
    #     description="Display the Edit Breakdown thumbnail grid view",
    # )

    bpy.app.handlers.load_pre.append(unregister_custom_properties)
    bpy.app.handlers.load_post.append(register_custom_properties)


def unregister():

    bpy.app.handlers.load_pre.remove(unregister_custom_properties)
    bpy.app.handlers.load_post.remove(register_custom_properties)

    # del bpy.types.SpaceSequenceEditor.show_edit_breakdown_view
    del bpy.types.Sequence.use_for_edit_breakdown
    del bpy.types.Scene.edit_breakdown

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
