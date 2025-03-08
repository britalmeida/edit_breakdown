# Release Notes

A summary of noteworthy changes for each release. Made for humans. 🧻  
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Wip wip...


## [0.5.0] - 2025-03-08

### Shiny and New
- Tested to work with Blender 3.6, 4.2, 4.3, 4.4 and 4.5.
- Packaged as extension so it is nicer to install and can be published to the official extensions
platform in the future.

### Fixed
- Support for Blender 4.4 API with Sequencer Strips instead of Sequences.


## [0.4.0] - 2024-01-03

### Shiny and New
- Added `Generate Edit Breakdown Thumbnails` operator which can be run independently from the Sync
to help with troubleshooting. It is available from the search (no shortcut, no button).

### Fixed
- Fixed "KeyError" when doing 'Sync'. It was introduced by v0.3.0.
- Fixed errors when there are issues with the thumbnails on disk.  
  It's now resilient to a missing/deleted thumbnails folder and to it having a .DS_Store file.
- Fixed thumbnails jumping/disappearing after multiple undo steps.


## [0.3.0] - 2023-11-01

### Fixed
- Fixed "KeyError" when addon folder name is different from expected. Fixes #1 and #8.
- Update code API to work with Blender 4.0.0. No functional changes.


## [0.2.0] - 2023-07-21

### Fixed
- Update code API for compatibility with upcoming newer Blender versions.
- Tested to work with Blender versions 3.3.8 LTS, 3.6.0 LTS and 4.0.0-dev.
