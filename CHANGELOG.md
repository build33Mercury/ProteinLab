# Changelog

## 1.1 — 2026-08-31

- Published Protein Lab v1.1 as the current stable Windows release.
- Bundled all 13 curated built-in protein structures directly with the application so the built-in bank no longer depends on first-run RCSB downloads.
- Added SHA-256 validation for bundled built-in structures and automatic recovery of missing or corrupted files.
- Added installed-payload fingerprint verification so stale or incomplete application payloads are replaced automatically rather than reused because the version string happens to match.
- Added startup graphics preflight in an isolated child process to reduce whole-application crashes caused by native VTK/Qt/OpenGL initialization failures.
- Added Safe Graphics fallback when the normal graphics backend is unstable.
- Improved startup logging and visible failure reporting for recoverable Python-level startup errors.
- Preserved user projects and imported proteins across application-payload repairs and upgrades.
- Retained the single-executable Windows GUI distribution, startup splash screen, and automatic Desktop/Start Menu shortcut creation.

### Built-in protein bank

The stable release includes local coordinate files for:

- 1CRN — Crambin
- 1UBQ — Ubiquitin
- 1MBN — Myoglobin
- 4HHB — Hemoglobin
- 1LYZ — Lysozyme
- 1L2Y — Trp-cage
- 1VII — Villin headpiece
- 1AKE — Adenylate kinase
- 1BRS — Barnase–barstar
- 2PTC — Trypsin–BPTI
- 1ATP — Protein kinase complex
- 1F88 — Rhodopsin
- 1TIM — Triosephosphate isomerase

## 1.0.7

- Added exact application-payload fingerprint validation.
- Required the installed built-in protein bank to pass manifest checks before an existing installation can be reused.
- Fixed the stale-install condition in which a previously broken installation could survive a corrected build carrying the same version number.

## 1.0.6

- Added the complete 13-structure built-in PDB collection to the packaged application payload.
- Added release checks covering presence and parseability of every bundled built-in structure.

## 1.0.5

- Added automatic recovery for missing built-in PDB files.
- Added atomic validation of downloaded coordinate data before it can replace a local structure file.
- Kept RCSB retrieval as a recovery path rather than inventing fallback coordinates.

## 1.0.4

- Hardened startup against native graphics-stack failures.
- Added isolated VTK/OpenGL preflight and Safe Graphics fallback.
- Reduced startup-time native imports in the primary application process.
- Added improved startup diagnostics and fault logging.

## 1.0.3 — 2026-08-20

- Applied the finalized Protein Lab icon to application and Desktop/Start Menu shortcut branding.
- Updated splash-screen and public repository branding.
- Standardized source-available licensing, citation metadata, public version strings, and release notes.
- Retained the pinned Python 3.13.15 runtime and scientific dependency lock.
- Retained the v1 validation gate, Help Aid, Validation Center, and reproducibility workflow.

## 1.0.2

- Consolidated the Windows public distribution into a single `ProteinLab.exe` launcher.
- Added automatic private-runtime installation and pinned dependency recovery.
- Added cryptographic verification of the Python runtime download and embedded application payload.

## 1.0.1

- Replaced the command-wrapper public launch path with a Windows GUI executable.
- Added first-run repair behavior, Desktop and Start Menu shortcuts, and GUI-visible startup failure reporting.

## 1.0.0

- First stable Protein Lab release.
- Added Help Aid, Validation Center, deterministic numerical benchmarks, destructive QA, performance guardrails, and the complete public scientific toolset.

## 0.15.0-alpha.10

- Added automatic sequence-to-structure prediction, Calculation Inspector, Experiment Notebook, Methods generator, exports, and portable `.plab` projects.

## 0.12.0-alpha.9

- Added ligand/pocket, complex-interface, membrane, structural-validation, and structure-comparison workflows.

## 0.10.0-alpha.8

- Added conformational exploration, occupancy-derived free-energy landscapes, and residue interaction networks.

## 0.8.0-alpha.7

- Added trajectory playback, RMSD/RMSF, mutation workflow, environment controls, and the redesigned Protein Toolbox.

## 0.6.0-alpha.6

- Added molecular-mechanics energy inspection, energy minimization, and molecular dynamics.
