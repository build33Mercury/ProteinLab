# Protein Lab User Guide

This document mirrors the built-in **Help Aid** content for Protein Lab 1.0.3. Research mode is the default.

## Quick start

*Category: Getting started*

The shortest reliable path from opening Protein Lab to a useful result.

Research mode is the default. A normal workflow is:

1. Open Protein Toolbox.
2. Load a built-in protein, Import Your Own Protein, or Create Protein.
3. Inspect the structure and choose a viewport representation.
4. For simulation, run Prepare Simulation before Energy Inspector, Minimization, or Molecular Dynamics.
5. For trajectory work, run Molecular Dynamics and then use Trajectory Playback, RMSD, RMSF, Free-Energy Landscape, or Residue Interaction Network.
6. Use Experiment Notebook and Generate Methods to preserve provenance.
7. Save a .plab project when you want to move or archive the workspace.

The app distinguishes experimental structures, generated starting geometries, predicted structures, prepared systems, minimized structures, and molecular-dynamics results. Do not treat them as interchangeable evidence.

## Protein Toolbox

*Category: Interface*

Cello-style searchable chooser for proteins and tools.

Click Protein Toolbox or press Ctrl+K. The chooser contains four prominent actions at the top: Import Your Own Protein, Create Protein, My Proteins, and Built-in Proteins.

The search field searches names, PDB identifiers, tools, and concepts. The category dropdown can restrict results to built-ins, My Proteins, view tools, inspect tools, measurements, editing, simulations, or analyses.

Protein rows use thumbnails derived from their stored coordinates. Tool rows use category-specific icons. Clicking a protein loads it; clicking a tool activates that operation.

## Import Your Own Protein

*Category: Protein input*

Import a PDB or PDBx/mmCIF file into the persistent My Proteins library.

Open Protein Toolbox → Import Your Own Protein, or use File → Import Your Own Protein. Select a .pdb, .cif, or .mmcif structure file. Protein Lab copies the file into its local library, validates that the structure can be parsed, and loads it in the viewport.

Imported files remain in My Proteins until removed. Importing a structure does not imply that it is experimentally determined or suitable for simulation; the source metadata and preparation state still matter.

## Create Protein

*Category: Protein input*

Create an initial peptide/protein model from amino-acid or coding-DNA text.

Open Protein Toolbox → Create Protein. Choose Amino-acid sequence or Coding DNA, enter a name, paste/type the sequence, and choose an initial geometry.

Coding DNA is only an input encoding. Protein Lab translates reading frame 0 into amino acids; no DNA molecule is created in the viewport. The builder supports the 20 standard amino acids.

The initial Extended, Alpha helix, or Beta strand geometry is a constructed starting model. It is not a native-structure prediction. Automatic Fold Prediction is enabled by default and runs after the starting strand is created.

## Automatic Fold / Structure Prediction

*Category: Protein input*

Replace the initial strand with a predicted folded structure when the prediction returns.

When automatic prediction is enabled in Create Protein, the starting peptide appears immediately. Protein Lab then sends the amino-acid sequence to the configured ESMFold service in a background thread. When a valid predicted PDB returns, the predicted protein is saved as a separate My Proteins entry and loaded automatically.

This is sequence-to-structure prediction, not a movie of physical folding and not experimental evidence. The initial strand remains saved separately. The predicted structure can subsequently be prepared, minimized, simulated, validated, and compared.

If the external prediction service is unavailable, the locally created strand remains usable. The app does not fabricate replacement coordinates.

## 3D Viewport

*Category: Interface*

Rotate, zoom, inspect, and change structural representation.

The central viewport is native VTK and displays stored atomic coordinates. Drag to rotate, use the normal VTK camera controls to zoom/pan, and click near an atom to inspect it. Reset View fits the protein back into the camera.

Representation options include Ribbon, Ball and stick, Sticks, and Space filling. Ribbon view is intended for overall protein architecture; atomic representations are better for local chemistry and measurement. A change in representation does not change the molecular coordinates.

## Inspector

*Category: Interface*

Context panel for protein, atom selection, sequence, and provenance information.

The Inspector on the right changes meaning according to what is selected. Protein summarizes the loaded record and structure size. Selection reports an atom/residue clicked in the viewport. Sequence shows standard amino-acid sequences by chain. Provenance records where the structure came from and the metadata attached to generated or simulated records.

Use provenance when deciding what claims are allowed. A predicted model, minimized model, and experimental structure should never be silently treated as the same source type.

## Distance, Angle, and Dihedral

*Category: Geometry*

Exact coordinate geometry from selected atoms.

Choose Measure Distance, Measure Angle, or Measure Dihedral from Protein Toolbox or Analysis. The cursor switches to selection mode. Click 2, 3, or 4 atoms respectively.

Distance uses Euclidean distance. Angle uses the vector dot product and arccos. Dihedral uses projected vectors and atan2 to preserve sign. Results are based on the exact coordinates stored in the current structure/frame. Open Calculation Inspector to see the equations and assumptions.

## Prepare Simulation

*Category: Simulation*

Convert a structure into a force-field-parameterized OpenMM system.

Simulation preparation is required before Energy Inspector, Minimization, or Molecular Dynamics. The workflow can clean selected heterogens, add hydrogens at a chosen pH, optionally add explicit water and ions, and validate that the selected OpenMM force field can parameterize the resulting topology.

Preparation changes the model. Added hydrogens, protonation choices, solvent, ions, and cleanup decisions belong in Methods and provenance. Unsupported chemistry should fail loudly rather than receive invented parameters.

## Energy Inspector

*Category: Simulation*

Evaluate molecular-mechanics potential energy and inspect force groups.

Energy Inspector queries the OpenMM Context created from the prepared system. It reports total potential energy and contributions grouped by OpenMM Force object. Standard bonded terms include bond stretching, angle bending, and periodic torsions. NonbondedForce combines electrostatic and Lennard-Jones interactions in the reported force-group energy.

Potential energy is force-field dependent. It is not automatically a folding free energy, binding affinity, or experimental observable. Use Calculation Inspector for the mathematical forms.

## Energy Minimization

*Category: Simulation*

Locally relax a prepared structure toward lower potential energy.

Choose Energy Minimization after preparing the system. Protein Lab uses OpenMM local energy minimization and saves the resulting coordinates as a new My Proteins record, leaving the original unchanged.

Minimization is local optimization. It can resolve bad contacts and relax geometry, but it does not establish equilibrium, prove the native fold, or replace molecular dynamics/free-energy sampling.

## Molecular Dynamics

*Category: Simulation*

Integrate atomic motion with OpenMM and save a trajectory.

Prepare a structure, then choose Molecular Dynamics. Research mode exposes ensemble, temperature, timestep, friction, number of steps, report interval, seed, and—when physically available—pressure/barostat settings.

Protein Lab records actual coordinates, state data, and a final structure. Trajectory playback displays those stored frames; it is not a decorative animation. NPT requires a periodic solvated system. Short simulations should not be interpreted as converged thermodynamic sampling merely because they ran successfully.

## Environment Controls

*Category: Simulation*

Set pH/ionic-strength preparation choices and MD temperature/pressure conditions.

The Environment controls route settings into the appropriate physical workflow. pH is used for hydrogen/protonation decisions during preparation; ionic strength affects explicit ion addition when solvating; temperature is a molecular-dynamics thermostat parameter; pressure is used only with a compatible NPT periodic system and barostat.

Changing a number does not directly deform the protein. The structure changes only when a preparation or simulation calculation produces new coordinates.

## Trajectory Playback

*Category: Analysis*

Play and scrub the coordinate frames produced by Protein Lab MD.

Load an MD-result protein and choose Trajectory Playback. Use Play/Pause, the frame slider, or step controls. The viewport is updated from the stored frame coordinates without resetting the camera.

Playback speed is a visualization setting. It does not alter the physical timestep or simulated time represented by the trajectory.

## RMSD

*Category: Analysis*

Kabsch-aligned root-mean-square displacement from a reference frame.

RMSD first least-squares aligns the selected coordinates to the reference with the Kabsch algorithm, then calculates the root-mean-square coordinate displacement. Protein Lab currently uses C-alpha atoms for the trajectory RMSD workflow.

RMSD reports structural displacement after rigid-body alignment. It does not directly measure stability, function, free energy, or experimental accuracy.

## RMSF

*Category: Analysis*

Per-residue fluctuation around the time-averaged aligned coordinates.

RMSF aligns frames and measures the root-mean-square fluctuation of selected atoms around their mean positions. In the current workflow, C-alpha RMSF is reported per residue.

Large RMSF can indicate greater sampled mobility in that trajectory. It is trajectory-, model-, temperature-, and sampling-dependent; it is not automatically experimental flexibility.

## Conformational Explorer

*Category: Simulation*

Physics-based heating/cooling sampling of alternative conformations.

Conformational Explorer runs explicit OpenMM sampling protocols with defined temperature stages/replicas and records resulting coordinates. It is intended to explore alternative conformations and test model behavior.

This is not a guaranteed native-fold solver. A sampled low-energy or frequently visited state is still conditional on force field, protocol, solvent model, and sampling depth.

## Free-Energy Landscape

*Category: Analysis*

Occupancy-derived surface from trajectory collective variables.

The current landscape uses trajectory RMSD and radius of gyration as collective variables. Histogram occupancy P is converted to a relative free-energy surface using F = -RT ln(P/Pmax).

This interpretation requires meaningful sampling at a defined temperature. Sparse or short trajectories can give misleading landscapes. Protein Lab reports warnings instead of treating every histogram as a converged thermodynamic result.

## Residue Interaction Network

*Category: Analysis*

Convert residue proximity into a contact graph.

Residues are represented by C-beta coordinates with C-alpha fallback where appropriate. Two residues form an edge when their representative distance satisfies the chosen cutoff; trajectories can additionally report contact occupancy.

A contact graph is a geometric network, not a direct energetic interaction map. Contact cutoff and occupancy threshold are explicit analysis parameters.

## Hydrogen Bonds

*Category: Analysis*

Explicit-hydrogen D-H···A geometry screening with stated criteria.

Hydrogen Bonds searches for N/O/S donor atoms carrying an explicit hydrogen and N/O/S candidate acceptors. The default geometric screen requires D···A ≤ 3.5 Å, H···A ≤ 2.5 Å, and D-H···A ≥ 120°.

The method is intentionally transparent and conservative. It does not assign full protonation chemistry or hydrogen-bond energies. Structures without explicit hydrogens should be prepared before this analysis.

## Solvent-Accessible Surface Area (SASA)

*Category: Analysis*

Total and per-residue Shrake-Rupley solvent-accessible area.

SASA uses Biopython's Shrake-Rupley implementation with an explicit solvent probe radius and sphere-sampling density. The default Protein Lab workflow uses a 1.4 Å probe and reports total and per-residue accessible area in Å².

SASA is a geometric accessibility calculation for the stored coordinates. It is not a molecular surface rendering, solvation free energy, binding affinity, or experimental measurement.

## Mutate Residue

*Category: Editing*

Create a standard amino-acid substitution as a separate structure.

Select a residue, open Mutate Residue, and choose the target amino acid. Protein Lab creates the substitution using PDBFixer templates and stores a new record. The immediate mutant is labeled unrelaxed.

For a physically interpretable structural comparison, prepare/minimize or simulate the mutant using a stated protocol. A visual side-chain replacement by itself is not a measured stability effect or ΔΔG.

## Ligands & Binding Pockets

*Category: Analysis*

Identify non-protein components and nearby protein residues.

Choose Ligands & Binding Pockets. Select a detected non-protein component and a heavy-atom distance cutoff. Protein Lab reports protein residues whose minimum heavy-atom distance to the selected component is within the cutoff.

This is pocket/contact geometry. It is not docking, binding affinity, or a free-energy calculation. Arbitrary ligands also require valid force-field parameters before MD.

## Complex Interfaces

*Category: Analysis*

Analyze contacts between protein chains.

For multichain structures, Complex Interfaces identifies inter-chain residue pairs that satisfy an explicit heavy-atom distance criterion and summarizes interface residues by chain.

Interface contacts are structural proximity. They should not be described as binding energies without a separate validated energetic method.

## Build Membrane System

*Category: Simulation*

Construct an explicit lipid/water/ion environment around an oriented membrane protein.

Build Membrane System uses OpenMM membrane-building functionality with supported lipid choices and explicit solvent/ions. The protein must already be oriented consistently with the membrane convention used by the builder.

Membrane construction can be computationally expensive and changes the topology substantially. Always inspect the resulting system before simulation and preserve the chosen lipid, ionic strength, padding, and force-field settings in provenance.

## Structural Validation

*Category: Analysis*

Transparent geometry checks for common structural problems.

Structural Validation checks backbone completeness, peptide-chain continuity, backbone torsions, and conservative steric-overlap warnings using explicit geometric criteria.

These checks are useful quality control, not a replacement for full wwPDB/MolProbity-style experimental-structure validation. Passing Protein Lab geometry checks does not prove that a model is biologically correct.

## Compare / Align Structures

*Category: Analysis*

Sequence-guided structural superposition and per-residue displacement.

Choose Compare / Align Structures and select another protein record. Protein Lab sequence-aligns compatible chains, pairs corresponding C-alpha atoms, performs a Kabsch rigid-body superposition, and reports RMSD plus per-residue displacement.

The comparison answers how similar the selected coordinate sets are after alignment. It does not by itself determine which structure is experimentally correct.

## Calculation Inspector

*Category: Research workflow*

Search the exact equations, mathematical forms, and assumptions used by Protein Lab.

Open Calculation Inspector from Analysis/Learn or Protein Toolbox. Search by concept such as distance, torsion, RMSD, RMSF, free energy, Lennard-Jones, or electrostatics.

Each entry distinguishes the mathematical form from its interpretation and limitations. Use this whenever you need to verify what a displayed number actually means.

## Experiment Notebook

*Category: Research workflow*

Persistent provenance ledger for computational operations.

Experiment Notebook records UTC timestamp, protein identifier, action, method, parameters, results, and notes for supported operations. It is intended to make simulation history auditable and reproducible.

The notebook is not proof that an operation was scientifically appropriate; it records what was done. Use Validation Center and the scientific caveats in Help Aid to judge validity.

## Generate Methods

*Category: Research workflow*

Create a Methods draft from settings actually recorded in the experiment notebook.

Generate Methods reads recorded computational operations and converts their explicit settings into a publication-style draft. It does not infer missing parameters or invent methods that were not logged.

Review the generated text before publication and add context such as scientific rationale, convergence testing, hardware details, and external analyses when applicable.

## Projects and Exports

*Category: Research workflow*

Save a portable workspace or export structures/results in standard forms.

Save Project creates a .plab archive containing My Proteins records included in the project plus experiment provenance. Open Project imports the archived structures into the local library with new identifiers.

Export options include structure files, FASTA, notebook JSON, Methods text, and simulation bundles where available. Prefer PDBx/mmCIF for archival structure exchange when legacy PDB limitations matter.

## Research vs Student mode

*Category: Interface*

Two presentation modes, one scientific engine.

Research mode is the default and keeps full scientific controls visible. Student mode uses the same calculations but emphasizes guided explanations and learning workflows. Switching mode does not substitute a simplified or fake physics engine.

For coursework, use Student Lab Guide together with Calculation Inspector. For research, keep Research mode and preserve all model/setup parameters in the notebook.

## Evidence, confidence, and claim limits

*Category: Scientific integrity*

How to interpret the different kinds of output produced by the app.

Protein Lab outputs fall into different evidence classes:

• Imported experimental structure metadata: source-dependent experimental evidence.
• Generated peptide geometry: constructed starting coordinates.
• Predicted fold: model prediction.
• Force-field energy/minimization/MD: molecular-mechanics model results.
• Geometry analyses: direct calculations from stored coordinates.
• Occupancy/free-energy analyses: trajectory-derived estimates conditional on sampling.

Do not collapse these into one generic word such as “accurate”. State the method, model, assumptions, and validation evidence behind the result.

## Validation Center

*Category: Quality control*

Run deterministic benchmarks, QA checks, dependency checks, and built-in structure integrity tests.

Validation Center is Protein Lab's internal quality-control dashboard. Core benchmarks use known numerical cases for geometry, alignment, sequence translation, and analysis behavior. QA checks deliberately feed invalid inputs and verify that they are rejected. Runtime checks report critical scientific dependencies and force-field resources. Built-in structure checks verify that local files parse and contain atoms.

A PASS means the tested implementation behaved as expected under that case. It does not validate every biological claim or prove a force field is exact.

## Troubleshooting

*Category: Getting started*

What to do when an operation fails.

Import failure: confirm the file is a valid PDB/PDBx/mmCIF structure.

Preparation failure: inspect nonstandard residues/ligands and force-field compatibility. Protein Lab intentionally refuses unsupported parameterization rather than inventing parameters.

Fold-prediction failure: the external ESMFold service may be unreachable or the sequence may exceed the rapid-workflow limit. Your locally created strand remains saved.

MD/NPT failure: ensure the current record is prepared and that NPT uses a periodic solvated system.

Unexpected numerical results: open Calculation Inspector, confirm units/selection/reference frame, then run Validation Center.

Launcher/setup failure: copy the exact module/traceback reported by the launcher/setup log. It is designed to fail loudly rather than hide a broken science stack.

## Keyboard and navigation shortcuts

*Category: Interface*

Fast access to common actions.

Ctrl+K — open Protein Toolbox.
Ctrl+O — import your own protein structure.
F1 — open Help Aid.
R — reset the viewport camera.
Ctrl+Q — exit.

Most scientific tools are also available through Protein Toolbox search, which is usually faster than memorizing menu locations.

## Complete tool reference

*Category: Reference*

Every Protein Toolbox operation in the current build, in one place.

Import structure [Protein]
Import PDB or PDBx/mmCIF into My Proteins.
Status: Available

Create protein [Protein]
Create an idealized peptide/protein starting structure from amino-acid or coding-DNA text.
Status: Available

Pointer / rotate [View]
Normal viewport interaction; drag to rotate and click an atom to inspect it.
Status: Available

Reset view [View]
Fit the current protein in the viewport.
Status: Available

Representation [View]
Switch ribbon, ball-and-stick, sticks, or space filling.
Status: Available

Protein information [Inspect]
Open structure summary and metadata.
Status: Available

Sequence [Inspect]
Open the amino-acid sequence for the loaded structure.
Status: Available

Measure distance [Measure]
Click two atoms; calculate Euclidean distance in ångström from stored coordinates.
Status: Available

Measure angle [Measure]
Click three atoms; calculate the geometric angle from the vector dot product.
Status: Available

Measure dihedral [Measure]
Click four atoms; calculate the signed torsion angle with vector projections and atan2.
Status: Available

Prepare simulation [Simulation]
Use OpenMM to add hydrogens, optionally solvate/add ions, and validate force-field parameterization.
Status: Available

Energy inspector [Simulation]
Evaluate the actual OpenMM potential energy and decompose it by force group.
Status: Available

Energy minimization [Simulation]
Run OpenMM local L-BFGS energy minimization and save the minimized coordinates.
Status: Available

Molecular dynamics [Simulation]
Run real NVT Langevin-middle molecular dynamics and save the final structure plus state log.
Status: Available

Mutate residue [Edit]
Create a standard amino-acid substitution with PDBFixer templates; the mutant is explicitly marked unrelaxed until minimized.
Status: Available

Trajectory playback [Analyze]
Play, scrub, step, and inspect the actual coordinate frames stored by Protein Lab molecular dynamics.
Status: Available

Trajectory RMSD [Analyze]
Calculate Kabsch-aligned C-alpha RMSD against a reference frame using the stored MD coordinates.
Status: Available

Per-residue RMSF [Analyze]
Calculate C-alpha root-mean-square fluctuations over the aligned trajectory.
Status: Available

Environment controls [Simulation]
Set preparation pH/ionic strength and run NVT or NPT dynamics with explicit temperature/pressure models.
Status: Available

Conformational explorer [Simulation]
Run explicit OpenMM heating/cooling replicas to sample alternative conformations. This is physics-based sampling, not native-fold prediction.
Status: Available

Free-energy landscape [Analyze]
Estimate an occupancy-derived 2D free-energy surface from a constant-temperature MD trajectory using RMSD and radius of gyration.
Status: Available

Residue interaction network [Analyze]
Build a residue contact graph from Cβ/Cα representative-atom distances and trajectory contact occupancy.
Status: Available

Ligands & binding pockets [Analyze]
Identify non-protein components and map protein residues within an explicit heavy-atom distance cutoff.
Status: Available

Complex interfaces [Analyze]
Analyze protein-chain interfaces from explicit inter-chain heavy-atom residue contacts.
Status: Available

Build membrane system [Simulation]
Use OpenMM Modeller.addMembrane to build an explicit lipid/water/ion system around a pre-oriented membrane protein.
Status: Available

Structural validation [Analyze]
Run transparent geometry QC for backbone completeness, peptide continuity, φ/ψ/ω torsions, and conservative steric-overlap warnings.
Status: Available

Compare / align structures [Analyze]
Sequence-align two protein chains, Kabsch-superpose their aligned Cα atoms, and report RMSD plus per-residue displacement.
Status: Available

Fold / predict structure [Protein]
Predict a 3D structure from the current amino-acid sequence with ESMFold, then save the returned coordinates as a separate predicted protein.
Status: Available

Calculation inspector [Inspect]
Browse the exact equations, assumptions, and scientific meaning behind Protein Lab calculations.
Status: Available

Experiment notebook [Inspect]
View the persistent record of computational operations, parameters, and outputs.
Status: Available

Generate Methods [Inspect]
Generate a publication-style methods draft directly from recorded computational settings.
Status: Available

Save Protein Lab project [Protein]
Save My Proteins and experiment provenance into a portable .plab project archive.
Status: Available

Validation Center [Inspect]
Run deterministic numerical benchmarks, defensive QA, runtime dependency checks, and built-in structure integrity checks.
Status: Available

Help Aid [Inspect]
Search the complete built-in manual: what every workflow does, how to use it, mathematics, caveats, and troubleshooting.
Status: Available

Hydrogen bonds [Analyze]
Detect explicit-hydrogen D-H···A geometry using transparent distance/angle criteria.
Status: Available

Residue contacts [Analyze]
Open the residue interaction-network/contact analysis using explicit distance and occupancy thresholds.
Status: Available

Solvent-accessible surface area (SASA) [Analyze]
Calculate total and per-residue Shrake-Rupley solvent-accessible surface area from stored coordinates.
Status: Available

## Built-in protein collection

*Category: Reference*

The curated structures offered by the built-in protein chooser.

Crambin — PDB 1CRN
Small 46-residue protein; useful for geometry and viewport tests.

Ubiquitin — PDB 1UBQ
Compact protein with alpha-helical and beta-sheet secondary structure.

Myoglobin — PDB 1MBN
Classic alpha-helical globular protein with a heme cofactor.

Hemoglobin — PDB 4HHB
Tetrameric hemoglobin; useful for multi-chain structure viewing.

Lysozyme — PDB 1LYZ
Enzyme containing alpha helices, beta structure, and disulfide bonds.

Trp-cage — PDB 1L2Y
20-residue NMR miniprotein; useful for small-protein structure and sampling exercises.

Villin headpiece — PDB 1VII
Small helical villin headpiece subdomain; useful for compact-fold examples.

Adenylate kinase — PDB 1AKE
Enzyme complex containing a nucleotide-like inhibitor; useful for ligand-pocket analysis.

Barnase–barstar — PDB 1BRS
Protein-protein complex for chain-interface and recognition exercises.

Trypsin–BPTI — PDB 2PTC
Protease-inhibitor complex for active-site and protein-interface analysis.

Protein kinase complex — PDB 1ATP
cAMP-dependent protein kinase complex with nucleotide and peptide inhibitor.

Rhodopsin — PDB 1F88
Membrane GPCR structure for transmembrane-protein viewing and membrane workflows.

Triosephosphate isomerase — PDB 1TIM
Classic enzyme fold useful for secondary-structure and multimer analysis.
