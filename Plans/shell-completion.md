# Plan: Shell Completion Support (implemented)

Status: **done** (with follow-up polish from the CLI improvement pass).

## What shipped
- `supercopy completion [bash|zsh|powershell]` (default: powershell)
- Completes flags for `supercopy`, `SuperCopy`, and `scpy`
- PowerShell: flag matches first; otherwise path completion fallback
- Bash: flags or filenames
- Zsh: `_arguments` with single-line help strings + file completion
- Documented in `--help` epilog and README

## Verify
```shell
python supercopy.py completion powershell
python supercopy.py completion bash
python supercopy.py completion zsh
```
