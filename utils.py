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


import pathlib

import bpy


def timestamp_str(num_frames: int) -> str:
    """Returns an absolute frame or duration as a timestamp string"""

    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    sign = "-" if num_frames < 0 else ""
    num_frames = abs(num_frames)

    # Note: format is very similar to smpte_from_frame, but with ms instead of sub-second frames.
    h = int(num_frames / (3600 * fps))
    m = int((num_frames / (60 * fps)) % 60)
    s = int((num_frames / fps) % 60)
    ms = int((num_frames % fps) * (1000 / fps))
    return f"{sign}{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def draw_frame_prop(layout: bpy.types.UILayout, prop_label: str, prop_value: int):
    """Add a property to Blender's UI, showing timestamp and number of frames"""

    split = layout.split(factor=0.4, align=True)
    split.alignment = 'RIGHT'
    split.label(text=prop_label)
    split = split.split(factor=0.75, align=True)
    split.label(text=timestamp_str(prop_value))
    split.alignment = 'RIGHT'
    split.label(text=f"{prop_value} ")


def draw_stat_label(layout: bpy.types.UILayout, label: str, value: str):
    """Add a label-value pair to Blender's UI, aligned as a split property"""

    split = layout.split(factor=0.4, align=True)
    split.alignment = 'RIGHT'
    split.label(text=label)
    split.alignment = 'LEFT'
    split.label(text=value)


def get_datadir() -> pathlib.Path:
    """Returns a Path where persistent application data can be stored.

    # linux: ~/.local/share
    # macOS: ~/Library/Application Support
    # windows: C:/Users/<USER>/AppData/Roaming
    """

    home = pathlib.Path.home()

    if sys.platform == "win32":
        return home / "AppData/Roaming"
    elif sys.platform == "linux":
        return home / ".local/share"
    elif sys.platform == "darwin":
        return home / "Library/Application Support"
