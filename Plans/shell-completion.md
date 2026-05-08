# Plan: Add Shell Completion Support to SuperCopy

Add a new command `completion` to generate shell completion scripts for PowerShell, Bash, and Zsh, with a priority on PowerShell.

## Objective
Enable users to generate and install shell completions for `supercopy` to improve the command-line experience.

## Key Files & Context
- `supercopy.py`: The main entry point where CLI arguments are defined and handled.
- `package.json`: Used for versioning, and defines the `supercopy` bin command.

## Proposed Changes

### 1. `supercopy.py`
- Refactor `main_cli()` to handle the `completion` command before parsing other arguments.
- Implement a `generate_completion(parser, shell)` function that:
    - Extracts all available flags from the `argparse` parser.
    - Generates a PowerShell script using `Register-ArgumentCompleter`.
    - Generates a Bash completion script.
    - Generates a Zsh completion script.
- Support both `supercopy` and `SuperCopy` as command names in the completion scripts.

#### PowerShell Completion Logic:
The script will use `Register-ArgumentCompleter -Native` to provide completion for flags. It will also support path completion by default when no flags match.

#### Bash/Zsh Completion Logic:
Basic completion for available flags and file paths.

### 2. Implementation Details in `main_cli()`:
```python
def main_cli():
    # ... parser setup ...
    
    if len(sys.argv) > 1 and sys.argv[1] == "completion":
        shell = sys.argv[2] if len(sys.argv) > 2 else "powershell"
        # generate and print completion script
        sys.exit(0)
    
    # ... parser.parse_args() ...
```

## Verification & Testing
1. **Manual Verification of Output:**
   - Run `python supercopy.py completion powershell` and verify the output script.
   - Run `python supercopy.py completion bash` and verify the output script.
   - Run `python supercopy.py completion zsh` and verify the output script.
2. **Functional Test (if possible):**
   - Source the generated script in a local shell and verify tab completion works for flags like `--unpack`, `--verify`, etc.
3. **Regression Test:**
   - Ensure `supercopy source destination` still works as expected.
   - Ensure `supercopy --help` still works.

## Alternatives Considered
- **`shtab` library:** While powerful, it adds a dependency. A manual implementation for these simple flags is preferred to keep the project lightweight.
- **`argcomplete` library:** Primarily for bash/zsh and requires global installation/registration, which is less user-friendly for a standalone tool.
