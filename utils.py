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


import colorsys
import pathlib
import random
import sys

import bpy
from bpy.types import UILayout


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


def draw_frame_prop(layout: UILayout, prop_label: str, prop_value: int) -> None:
    """Add a property to Blender's UI, showing timestamp and number of frames"""

    split = layout.split(factor=0.4, align=True)
    split.alignment = 'RIGHT'
    split.label(text=prop_label)
    split = split.split(factor=0.75, align=True)
    split.label(text=timestamp_str(prop_value))
    split.alignment = 'RIGHT'
    split.label(text=f"{prop_value} ")


def draw_stat_label(layout: UILayout, label: str, value: str) -> None:
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
    else:
        raise RuntimeError("Unsupported platform")


def create_unique_name(base_name: str, existing_objects: list) -> str:
    """Returns a name not yet present in existing_objects which starts with base_name.

    Names follow Blender convention: base_name, base_name.001, base_name.002, etc.
    e.g.: create_unique_name("Object", all_objects)
    - all_objects = [] -> "Object"
    - all_objects = ["Object"] -> "Object.001"
    - all_objects = ["Object.002"] -> "Object"
    """

    # Get the object names.
    existing_names = (ob.name for ob in existing_objects)

    # If this is the first of its name, no need to add a suffix.
    if base_name not in existing_names:
        return base_name

    # Construct a sorted list of number suffixes already in use for base_name.
    offset = len(base_name) + 1
    suffixes = (name[offset:] for name in existing_names if name.startswith(base_name + '.'))
    numbers = sorted(int(suffix) for suffix in suffixes if suffix.isdigit())

    # Find the first unused number.
    min_index = 1
    for num in numbers:
        if min_index < num:
            break
        min_index = num + 1

    return f"{base_name}.{min_index:03d}"


def get_random_pastel_color_rgb():
    """Returns a randomly generated color with high brightness and low saturation."""

    hue = random.random()
    saturation = random.uniform(0.25, 0.33)
    brightness = random.uniform(0.75, 0.83)

    color = colorsys.hsv_to_rgb(hue, saturation, brightness)
    return color[0], color[1], color[2], 1.0


def get_goldenratio_index_color_rgb(idx):
    """Returns a color with hue as far apart from the previous colors as possible."""

    # Get a hue using a multiple of the conjugate of the golden ratio
    hue = 0.1 + (0.618033988749895 * idx)
    hue -= int(hue)

    saturation = random.uniform(0.25, 0.33)
    brightness = random.uniform(0.75, 0.83)

    color = colorsys.hsv_to_rgb(hue, saturation, brightness)
    return color[0], color[1], color[2], 1.0
