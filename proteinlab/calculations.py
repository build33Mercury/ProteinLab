from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CalculationSpec:
    key: str
    name: str
    category: str
    equation: str
    description: str
    assumptions: str


CALCULATIONS = (
    CalculationSpec("distance", "Cartesian distance", "Geometry", "d = sqrt((x2-x1)^2 + (y2-y1)^2 + (z2-z1)^2)", "Euclidean distance between two stored atomic coordinates.", "Coordinates are interpreted in angstroms."),
    CalculationSpec("angle", "Bond / geometric angle", "Geometry", "theta = arccos((a·b)/(|a||b|))", "Angle between two vectors defined by three selected atoms.", "Undefined if either vector has zero length."),
    CalculationSpec("dihedral", "Signed dihedral", "Geometry", "phi = atan2((n1×bhat2)·n2, n1·n2)", "Signed torsion angle from four atomic coordinates.", "Uses the selected atom order."),
    CalculationSpec("rmsd", "Kabsch-aligned RMSD", "Trajectory", "RMSD = sqrt((1/N) Σ ||R xi - yi||^2)", "Root-mean-square deviation after optimal least-squares rigid-body superposition.", "Default trajectory analysis uses corresponding C-alpha atoms."),
    CalculationSpec("rmsf", "Per-residue RMSF", "Trajectory", "RMSF_i = sqrt(<||ri(t)-<ri>||^2>)", "Time-averaged fluctuation of a residue after frame alignment.", "Depends on the selected trajectory and atom mapping."),
    CalculationSpec("rg", "Radius of gyration", "Trajectory", "Rg = sqrt(Σ mi ||ri-rCOM||^2 / Σ mi)", "Mass-weighted compactness around the molecular center of mass.", "Protein heavy atoms are used in the free-energy workflow."),
    CalculationSpec("free-energy", "Occupancy-derived free energy", "Thermodynamics", "F(s) = -R T ln(P(s)/Pmax)", "Converts sampled state occupancy into a relative molar free-energy surface.", "Only thermodynamically interpretable when the trajectory is a representative equilibrium sample at the stated temperature."),
    CalculationSpec("bond", "Harmonic bond potential", "Force field", "U = 1/2 k (r-r0)^2", "Standard bonded stretching term used by classical molecular mechanics.", "Parameters k and r0 come from the selected force field."),
    CalculationSpec("angle-energy", "Harmonic angle potential", "Force field", "U = 1/2 k (theta-theta0)^2", "Standard valence-angle term.", "Parameters come from the selected force field."),
    CalculationSpec("torsion-energy", "Periodic torsion potential", "Force field", "U = k [1 + cos(n theta - theta0)]", "Periodic torsional energy term.", "Actual force-field implementations may contain multiple periodic terms for one torsion."),
    CalculationSpec("lj", "Lennard-Jones 12-6", "Force field", "U_LJ = 4 epsilon [(sigma/r)^12 - (sigma/r)^6]", "Classical van der Waals repulsion/dispersion model.", "OpenMM NonbondedForce combines this with electrostatics in the queried force-group energy."),
    CalculationSpec("coulomb", "Coulomb electrostatics", "Force field", "U = (1/(4 pi epsilon0)) q1 q2 / r", "Pairwise electrostatic interaction; periodic systems use the selected long-range treatment such as PME.", "Charges and long-range treatment are force-field/system dependent."),
    CalculationSpec("contact", "Residue contact criterion", "Network", "edge(i,j)=1 if d_ij <= r_cut", "Explicit geometric graph criterion for residue contacts.", "A contact cutoff is a modeling/analysis definition, not a binding-energy threshold."),
)
