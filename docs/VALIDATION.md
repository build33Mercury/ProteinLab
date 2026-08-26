# Validation strategy

Protein Lab separates software validation from biological validation.

## Software/numerical validation

The stable release contains deterministic numerical benchmarks, defensive QA tests, dependency checks, force-field resource checks, project-format checks, and built-in structure-integrity checks. These are available through **Validation Center** and `python -m proteinlab.selftest`.

A PASS means the tested implementation behaved as expected for that case. It does **not** mean that every force field, predicted structure, or simulation result is biologically correct.

## Claim-specific scientific validation

Research use still requires method-specific validation, including appropriate controls, convergence/sensitivity analysis, comparison against experimental/reference data where applicable, and explicit reporting of force field, solvent, protonation, sampling, and analysis settings.

## Release gate

The Windows launcher performs the following on first launch or repair:

1. installs/updates the scientific dependencies;
2. validates critical runtime imports and OpenMM force-field resources;
3. downloads/caches the curated built-in PDB structures when network access permits;
4. runs the repository unit-test suite;
5. runs the full Protein Lab self-test;
6. launches the desktop application only if required checks pass.

Missing optional built-in downloads can appear as warnings when network access is unavailable; failed required numerical/runtime checks stop the release gate.
