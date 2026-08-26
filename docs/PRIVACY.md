# Privacy and network behavior

Protein Lab is primarily a local desktop application. Structure files, simulations, trajectories, notebooks, and `.plab` projects remain on the user's machine unless the user explicitly exports or transmits them.

## Network operations

The public Windows launcher may access the network to:

- download the pinned private Python runtime on first installation or repair;
- download missing pinned Python packages;
- obtain optional built-in public protein structures; and
- submit an amino-acid sequence to an external ESMFold service when automatic structure prediction is enabled.

## Sequence-to-structure prediction

Automatic ESMFold prediction is an external computation. The submitted amino-acid sequence leaves the local machine and is processed by the configured external service.

Do not submit confidential, proprietary, clinical, patient-derived, embargoed, export-controlled, or otherwise restricted sequences unless the applicable data-governance rules permit that external transmission.

Users can disable automatic prediction and continue using local structure construction, viewing, preparation, simulation, and analysis workflows.

## Logs

Installation/runtime logs can contain software paths, package versions, error messages, and filenames. Review logs before posting them publicly if filenames or paths are sensitive.
