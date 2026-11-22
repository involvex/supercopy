# Changelog

All notable changes to SuperCopy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CLI: `--on-conflict overwrite|skip|update`
- CLI: `--dry-run`, `--exclude` / `--include`, `-q/--quiet`, `--json`
- CLI: `--retries` / `--retry-wait`, `--mirror`, `--move`
- CLI: `--list` for archives; `--password` for encrypted archives
- CLI: empty-directory recreation; metadata preservation (mtime/attrs)
- CLI: Windows long-path (`\\?\`) support
- Archive formats: `.tar`, `.tar.gz`/`.tgz`, `.tar.bz2`, `.tar.xz`
- Bun-friendly shim with missing-exe guidance; `.npmignore` ships `dist/SuperCopy.exe`
- Slim CLI build: `build.bat --cli` / `bun run build:cli`
- pytest suite under `tests/`

### Changed
- Copy failures now exit non-zero; invalid `--buffer` exits `2`
- GUI imports are lazy (CLI no longer loads CustomTkinter at import time)
- Console output uses encoding-safe printing (no emoji crash on cp1252)
- Shell completion: path fallback, `scpy` alias, single-line Zsh help
- `build.bat` supports `--nopause` / skips pause under npm/CI
- README focused on CLI + Bun usage; package description updated

### Fixed
- Bun/Node shim `close` with null exit code no longer reports success
- Partial copy error lists go to stderr; scripts can detect failure
- RAR unpack preserves 7-Zip exit code in error messages
- Unpack warns when copy-only flags are passed

## [0.0.10]

### Added
- Shell completion support for PowerShell, Bash, and Zsh
- `--version` / `-v` flag to display version

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
2. Run build: `npm run build` or `bun run build`
3. Create installer: `makensis /DVERSION=<version> installer.nsi`
4. Publish: `npm publish --access public`
5. Create GitHub Release with installer asset
