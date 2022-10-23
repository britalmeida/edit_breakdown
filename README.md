# Edit Breakdown

Get insight on the complexity of an edit.

## Usage (WIP)
1. In the `Sequencer`, **add new color strips** to represent each shot in the edit.
2. Mark the color strips for use in the Edit Breakdown in `Strip > Add to Edit Breakdown`.
2. Open a new `Sequencer` area in `Preview` mode, and toggle the Edit Breakdown view on the right side of the header (temp: called `Display Frames`).
3. Click the **Sync** button to generate shots and thumbnails. Syncing is manual.
4. Optionally, add Scenes in Edit Breakdown 'Config' on the Preview right-side N panel. Select the shot color strips, a scene, and click the assign button next to the scenes list.

## Installation

1. Download this repository as ZIP file.
2. In Blender's `Edit > Preferences > Add-ons`, click `Install` and select the ZIP.

### Updating

1. Download the newest version ZIP.
2. In Blender's `Edit > Preferences > Add-ons`, find this add-on, expand it, and click `Remove`.
3. Click `Install` and select the ZIP.

**Alternatively:** this git repository can be **cloned** to a folder on disk and that folder linked to the `scripts/addons` folder of the Blender executable. This way, the add-on and be kept up to date with `git pull` without the need to remove/install it.

### Requirements
- Blender 2.91 or later. Tested for  Blender 3.3.
