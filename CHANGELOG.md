# Changelog

All notable changes to SuperCopy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Shell completion support for PowerShell, Bash, and Zsh
- `--version` / `-v` flag to display version
- Keyboard shortcuts in GUI (Ctrl+O, Ctrl+D, Enter)
- Improved progress reporting with speed and ETA
- Version display in GUI header

### Changed
- Updated README with comprehensive documentation
- Build script now extracts version from package.json
- Installer version now syncs with package.json

### Fixed
- Version synchronization between package.json and NSIS installer
- RAR unpacking error handling improvements

## [0.0.9] - 2026-08-10

### Added
- GUI mode with modern dark theme using CustomTkinter
- Dual progress bars (file count + total size)
- Archive unpacking support for .zip, .7z, .rar
- Multi-threaded file copying with configurable workers
- SHA-256 verification option (--verify)
- CLI mode with argparse
- Windows installer via NSIS
- npm package distribution

### Changed
- Refactored code into CopyEngine and UnpackEngine classes
- Improved error handling and reporting
- Better progress callbacks for both GUI and CLI

## [0.0.8] - 2026-07-15

### Added
- Basic CLI file copying
- Multi-threading support
- Buffer size configuration

### Fixed
- Large file handling
- Directory copy logic

## [0.0.7] - 2026-06-01

### Added
- Initial CLI implementation
- Basic file copy functionality
- Progress bar with tqdm

---

## Release Process

1. Update version in `package.json`: `npm version patch|minor|major`
2. Run build: `npm run build`
3. Create installer: `makensis /DVERSION=%VERSION% installer.nsi`
4. Publish: `npm publish --access public`
5. Create GitHub Release with installer asset