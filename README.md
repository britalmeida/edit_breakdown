# Edit Breakdown

Get insight on the complexity of an edit in Blender.

## Usage (WIP)
1. In the `Sequencer`, **add new color strips** to represent each shot in the edit.
   1. Mark the color strips for use in the Edit Breakdown in `Strip > Add to Edit Breakdown`.
   2. Workflow Suggestion: add a single color strip under the edit, add it to the Edit Breakdown, then use `K` to blade the strip while playing.
2. Open a new `Sequencer` area in `Preview` mode
   1. Toggle the Edit Breakdown view on the right side of the header (temporarilly called `Display Frames`).
   2. Enable `View > Tool Settings` and from the `Toolbar (T)` select the `Tag Tool`.
3. Click the **Sync** button to generate shots and thumbnails. Syncing is manual.
4. Optionally, add Scenes in Edit Breakdown 'Config' on the Preview right-side N panel.
   1. Select the shot color strips, a scene, and click the assign button next to the scenes list.

## Installation

### Installing as Extension

Note: this add-on is available as an extension, but is not on [extensions.blender.org](https://extensions.blender.org) yet.  
Work in Progress!

1. Download the [latest extension release from GitHub](https://github.com/britalmeida/push_to_talk/releases).
2. `Drag&drop` the ZIP into Blender.


### Installing as Legacy Add-on

For Blender version 4.1 and older.

1. Download the latest extension release or the repository as ZIP file.
2. In Blender's `Edit > Preferences > Add-ons`, click `Install` and select the ZIP.


### Updating

1. Remove a previous version if installed as a legacy add-on:  
   In Blender's `Edit > Preferences > Add-ons`, find this add-on, expand it, and click `Remove`.
2. Download and install a new version as an extension.  
   New versions of an extension can simply be installed on top without needing to manually delete the previous version.


### Compatibility

| Blender Version    | Status      |
|--------------------|-------------|
| 4.3, 4.4, 4.5      | Supported   |
| 4.2 LTS            | Supported   |
| 3.6 LTS            | Supported   |
| 3.3 LTS            | Supported   |
| 2.93 LTS and older | Unsupported |
