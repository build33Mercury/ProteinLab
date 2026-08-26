# Installation

## Recommended Windows installation

Download `ProteinLab.exe` from the latest GitHub Release and open it normally.

The current repository copy is also stored at:

```text
release/ProteinLab.exe
```

On first launch, the application launcher:

1. verifies the embedded Protein Lab payload;
2. installs or repairs a private Python 3.13.15 x64 runtime;
3. downloads missing pinned scientific packages;
4. validates the scientific/runtime stack;
5. prepares optional built-in structures;
6. creates Desktop and Start Menu shortcuts using the Protein Lab icon; and
7. opens the native PySide6/VTK application.

No system Python, conda environment, Node.js runtime, browser, or manual dependency commands are required for normal users.

## Later launches

Use the **Protein Lab** Desktop or Start Menu shortcut. The shortcut launches the installed application and retains the finalized Protein Lab icon.

## Repair or update

Open a newer `ProteinLab.exe` release. The launcher repairs or replaces application/runtime components as needed while preserving user project/data locations intended to survive updates.

## Network requirements

First launch requires network access if the private runtime or pinned packages are not already installed. Optional built-in structures and external ESMFold prediction also require network access.

## Setup failures

Protein Lab is designed to fail closed when a required runtime or release validation check fails. Use the displayed error/log rather than bypassing the check.
