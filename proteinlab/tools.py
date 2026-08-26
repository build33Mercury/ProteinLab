from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolSpec:
    key: str
    name: str
    category: str
    description: str
    phase: int
    available: bool = False
    icon: str = "analysis"
    keywords: str = ""


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("import", "Import structure", "Protein", "Import PDB or PDBx/mmCIF into My Proteins.", 2, True, "import", "file pdb cif mmcif"),
    ToolSpec("build-protein", "Create protein", "Protein", "Create an idealized peptide/protein starting structure from amino-acid or coding-DNA text.", 5, True, "create", "sequence peptide dna"),
    ToolSpec("pointer", "Pointer / rotate", "View", "Normal viewport interaction; drag to rotate and click an atom to inspect it.", 3, True, "pointer"),
    ToolSpec("reset-camera", "Reset view", "View", "Fit the current protein in the viewport.", 3, True, "reset", "camera fit"),
    ToolSpec("representation", "Representation", "View", "Switch ribbon, ball-and-stick, sticks, or space filling.", 3, True, "representation", "ribbon cartoon atoms"),
    ToolSpec("protein-info", "Protein information", "Inspect", "Open structure summary and metadata.", 3, True, "info", "metadata properties"),
    ToolSpec("sequence", "Sequence", "Inspect", "Open the amino-acid sequence for the loaded structure.", 3, True, "sequence", "amino acids fasta"),
    ToolSpec("distance", "Measure distance", "Measure", "Click two atoms; calculate Euclidean distance in ångström from stored coordinates.", 4, True, "distance", "ruler geometry"),
    ToolSpec("angle", "Measure angle", "Measure", "Click three atoms; calculate the geometric angle from the vector dot product.", 4, True, "angle", "geometry"),
    ToolSpec("dihedral", "Measure dihedral", "Measure", "Click four atoms; calculate the signed torsion angle with vector projections and atan2.", 4, True, "dihedral", "torsion phi psi geometry"),
    ToolSpec("prepare", "Prepare simulation", "Simulation", "Use OpenMM to add hydrogens, optionally solvate/add ions, and validate force-field parameterization.", 7, True, "prepare", "openmm force field hydrogens solvent"),
    ToolSpec("energy", "Energy inspector", "Simulation", "Evaluate the actual OpenMM potential energy and decompose it by force group.", 8, True, "energy", "potential forcefield equation"),
    ToolSpec("minimize", "Energy minimization", "Simulation", "Run OpenMM local L-BFGS energy minimization and save the minimized coordinates.", 9, True, "minimize", "lbfgs relax"),
    ToolSpec("md", "Molecular dynamics", "Simulation", "Run real NVT Langevin-middle molecular dynamics and save the final structure plus state log.", 10, True, "md", "dynamics trajectory nvt langevin"),
    ToolSpec("mutate", "Mutate residue", "Edit", "Create a standard amino-acid substitution with PDBFixer templates; the mutant is explicitly marked unrelaxed until minimized.", 13, True, "mutant", "substitution variant mutant pdbfixer"),
    ToolSpec("trajectory", "Trajectory playback", "Analyze", "Play, scrub, step, and inspect the actual coordinate frames stored by Protein Lab molecular dynamics.", 11, True, "trajectory", "frames play scrub md dcd"),
    ToolSpec("rmsd", "Trajectory RMSD", "Analyze", "Calculate Kabsch-aligned C-alpha RMSD against a reference frame using the stored MD coordinates.", 12, True, "rmsd", "root mean square deviation kabsch trajectory"),
    ToolSpec("rmsf", "Per-residue RMSF", "Analyze", "Calculate C-alpha root-mean-square fluctuations over the aligned trajectory.", 12, True, "rmsf", "fluctuation residue mobility trajectory"),
    ToolSpec("environment", "Environment controls", "Simulation", "Set preparation pH/ionic strength and run NVT or NPT dynamics with explicit temperature/pressure models.", 14, True, "environment", "temperature ph salt ionic pressure npt nvt barostat"),
    ToolSpec("conformational", "Conformational explorer", "Simulation", "Run explicit OpenMM heating/cooling replicas to sample alternative conformations. This is physics-based sampling, not native-fold prediction.", 15, True, "explore", "fold folding sample anneal conformation replica"),
    ToolSpec("landscape", "Free-energy landscape", "Analyze", "Estimate an occupancy-derived 2D free-energy surface from a constant-temperature MD trajectory using RMSD and radius of gyration.", 16, True, "landscape", "free energy boltzmann rmsd radius gyration pmf"),
    ToolSpec("contact-network", "Residue interaction network", "Analyze", "Build a residue contact graph from Cβ/Cα representative-atom distances and trajectory contact occupancy.", 17, True, "network", "contact graph network residue occupancy hub"),
    ToolSpec("ligand-pocket", "Ligands & binding pockets", "Analyze", "Identify non-protein components and map protein residues within an explicit heavy-atom distance cutoff.", 18, True, "ligand", "ligand cofactor ion pocket binding site hetero"),
    ToolSpec("complex-interface", "Complex interfaces", "Analyze", "Analyze protein-chain interfaces from explicit inter-chain heavy-atom residue contacts.", 19, True, "interface", "complex multimer chain interface contact"),
    ToolSpec("membrane", "Build membrane system", "Simulation", "Use OpenMM Modeller.addMembrane to build an explicit lipid/water/ion system around a pre-oriented membrane protein.", 19, True, "membrane", "lipid bilayer popc pope membrane openmm"),
    ToolSpec("validate-structure", "Structural validation", "Analyze", "Run transparent geometry QC for backbone completeness, peptide continuity, φ/ψ/ω torsions, and conservative steric-overlap warnings.", 20, True, "validate", "validation clash ramachandran torsion backbone chain break geometry qc"),
    ToolSpec("compare-structures", "Compare / align structures", "Analyze", "Sequence-align two protein chains, Kabsch-superpose their aligned Cα atoms, and report RMSD plus per-residue displacement.", 21, True, "compare", "align compare experimental predicted kabsch rmsd overlay"),
    ToolSpec("fold-predict", "Fold / predict structure", "Protein", "Predict a 3D structure from the current amino-acid sequence with ESMFold, then save the returned coordinates as a separate predicted protein.", 22, True, "fold", "fold protein prediction sequence esmfold predicted structure"),
    ToolSpec("calculation-inspector", "Calculation inspector", "Inspect", "Browse the exact equations, assumptions, and scientific meaning behind Protein Lab calculations.", 22, True, "equation", "equation formula math calculation method assumptions"),
    ToolSpec("experiment-notebook", "Experiment notebook", "Inspect", "View the persistent record of computational operations, parameters, and outputs.", 25, True, "notebook", "experiment notebook reproducibility provenance log"),
    ToolSpec("methods-generator", "Generate Methods", "Inspect", "Generate a publication-style methods draft directly from recorded computational settings.", 26, True, "methods", "methods reproducibility publication report"),
    ToolSpec("save-project", "Save Protein Lab project", "Protein", "Save My Proteins and experiment provenance into a portable .plab project archive.", 28, True, "project", "save project archive workspace"),
    ToolSpec("validation-center", "Validation Center", "Inspect", "Run deterministic numerical benchmarks, defensive QA, runtime dependency checks, and built-in structure integrity checks.", 29, True, "benchmark", "validate benchmark qa self test runtime scientific integrity"),
    ToolSpec("help-aid", "Help Aid", "Inspect", "Search the complete built-in manual: what every workflow does, how to use it, mathematics, caveats, and troubleshooting.", 35, True, "help", "help manual guide instructions how to use documentation"),
    ToolSpec("hydrogen-bonds", "Hydrogen bonds", "Analyze", "Detect explicit-hydrogen D-H···A geometry using transparent distance/angle criteria.", 35, True, "hbond", "hydrogen bond donor acceptor geometry prepared hydrogens"),
    ToolSpec("contacts", "Residue contacts", "Analyze", "Open the residue interaction-network/contact analysis using explicit distance and occupancy thresholds.", 35, True, "contacts", "residue contact distance occupancy network"),
    ToolSpec("surface", "Solvent-accessible surface area (SASA)", "Analyze", "Calculate total and per-residue Shrake-Rupley solvent-accessible surface area from stored coordinates.", 35, True, "surface", "sasa solvent accessible surface shrake rupley area"),
)
