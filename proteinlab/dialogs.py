from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from .builder import analyze_sequence, normalize_amino_sequence, translate_coding_dna


class CreateProteinDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Protein")
        self.resize(680, 570)
        self.setModal(True)
        self.sequence: str | None = None
        self.source_kind = "amino-acid sequence"

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        form = QFormLayout()
        self.name_edit = QLineEdit("Custom protein")
        form.addRow("Name", self.name_edit)

        self.input_type = QComboBox()
        self.input_type.addItems(["Amino-acid sequence", "Coding DNA"])
        self.input_type.currentTextChanged.connect(self._update_input_help)
        form.addRow("Input", self.input_type)

        self.conformation = QComboBox()
        self.conformation.addItems(["Extended", "Alpha helix", "Beta strand"])
        self.conformation.setToolTip(
            "This chooses only the initial idealized geometry. It is not a folding prediction."
        )
        form.addRow("Starting geometry", self.conformation)

        self.auto_fold = QCheckBox("Automatically predict the folded 3D structure after creation")
        self.auto_fold.setChecked(True)
        self.auto_fold.setToolTip("The extended/idealized peptide appears first. Protein Lab then sends the amino-acid sequence to the public ESMFold prediction service and replaces the viewport with the returned predicted structure when it arrives.")
        form.addRow("After creation", self.auto_fold)
        root.addLayout(form)

        file_row = QHBoxLayout()
        self.input_help = QLabel()
        self.input_help.setWordWrap(True)
        file_row.addWidget(self.input_help, 1)
        load_button = QPushButton("Load .txt / FASTA…")
        load_button.clicked.connect(self._load_text_file)
        file_row.addWidget(load_button)
        root.addLayout(file_row)

        self.sequence_edit = QPlainTextEdit()
        self.sequence_edit.setPlaceholderText("Paste sequence here…")
        self.sequence_edit.textChanged.connect(self._preview)
        root.addWidget(self.sequence_edit, 1)

        preview_group = QGroupBox("Validated sequence preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("Enter a sequence above.")
        self.preview_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.preview_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_label)
        root.addWidget(preview_group)

        note = QLabel(
            "The peptide strand is constructed locally from standard amino-acid geometry. When automatic prediction is enabled, "
            "the amino-acid sequence is then sent to the public ESMFold service; the returned structure is a model prediction, "
            "not an experimental structure or a time-resolved folding trajectory."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttons.button(QDialogButtonBox.Ok).setText("Create")
        self.buttons.accepted.connect(self._accept_validated)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._update_input_help()

    def _update_input_help(self) -> None:
        if self.input_type.currentText() == "Coding DNA":
            self.input_help.setText(
                "Paste a coding DNA sequence (A/C/G/T). Reading frame 0 is used; a terminal stop codon is allowed. "
                "DNA is only sequence input—the viewport contains the protein, not a DNA molecule."
            )
        else:
            self.input_help.setText("Paste a one-letter amino-acid sequence using the 20 standard amino acids.")
        self._preview()

    def _load_text_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Sequence",
            "",
            "Sequence text (*.txt *.fa *.fasta *.faa *.fna);;All files (*.*)",
        )
        if not filename:
            return
        try:
            self.sequence_edit.setPlainText(Path(filename).read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            QMessageBox.warning(self, "Could not read file", str(exc))

    def _get_sequence(self) -> tuple[str, str]:
        text = self.sequence_edit.toPlainText()
        if self.input_type.currentText() == "Coding DNA":
            _, sequence = translate_coding_dna(text)
            return sequence, "coding DNA"
        return normalize_amino_sequence(text), "amino-acid sequence"

    def _preview(self) -> None:
        try:
            sequence, _ = self._get_sequence()
            props = analyze_sequence(sequence)
            wrapped = " ".join(sequence[i:i+10] for i in range(0, len(sequence), 10))
            self.preview_label.setText(
                f"{wrapped}\n\n"
                f"Length: {props.length} residues    "
                f"Sequence molecular weight: {props.molecular_weight_da:.2f} Da    "
                f"pI: {props.isoelectric_point:.2f}"
            )
        except Exception as exc:
            self.preview_label.setText(str(exc))

    def _accept_validated(self) -> None:
        try:
            self.sequence, self.source_kind = self._get_sequence()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid sequence", str(exc))
            return
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Name required", "Give the protein a name.")
            return
        self.accept()

    @property
    def protein_name(self) -> str:
        return self.name_edit.text().strip()

    @property
    def starting_conformation(self) -> str:
        return self.conformation.currentText()


class PrepareSimulationDialog(QDialog):
    def __init__(self, parent=None, *, default_ph: float = 7.0, default_ionic: float = 0.15) -> None:
        super().__init__(parent)
        self.setWindowTitle("Prepare Simulation System")
        self.resize(560, 430)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        intro = QLabel(
            "Prepare the selected structure with OpenMM. The operation adds hydrogens using the selected pH, "
            "optionally solvates/neutralizes the system, and validates that a force-field System can be created."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        self.forcefield = QComboBox()
        self.forcefield.addItem("AMBER19 protein + TIP3P water", "amber19")
        form.addRow("Force field", self.forcefield)

        self.ph = QDoubleSpinBox()
        self.ph.setRange(0.0, 14.0)
        self.ph.setDecimals(2)
        self.ph.setValue(default_ph)
        form.addRow("Hydrogen pH", self.ph)

        self.remove_heterogens = QCheckBox("Remove waters and nonstandard residues before parameterization")
        self.remove_heterogens.setChecked(True)
        form.addRow("Cleanup", self.remove_heterogens)

        self.solvate = QCheckBox("Add explicit TIP3P water box")
        self.solvate.setChecked(False)
        self.solvate.toggled.connect(self._solvation_changed)
        form.addRow("Solvation", self.solvate)

        self.padding = QDoubleSpinBox()
        self.padding.setRange(0.5, 5.0)
        self.padding.setDecimals(2)
        self.padding.setSingleStep(0.1)
        self.padding.setValue(1.0)
        self.padding.setSuffix(" nm")
        form.addRow("Water padding", self.padding)

        self.ionic = QDoubleSpinBox()
        self.ionic.setRange(0.0, 2.0)
        self.ionic.setDecimals(3)
        self.ionic.setSingleStep(0.05)
        self.ionic.setValue(default_ionic)
        self.ionic.setSuffix(" M")
        form.addRow("Ionic strength", self.ionic)
        root.addLayout(form)

        warning = QLabel(
            "Strict mode: missing heavy atoms or unsupported chemistry will cause preparation to fail rather than "
            "invent parameters. Nonstandard ligands/cofactors need explicit parameterization in a later phase."
        )
        warning.setWordWrap(True)
        root.addWidget(warning)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("Prepare")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._solvation_changed(False)

    def _solvation_changed(self, checked: bool) -> None:
        self.padding.setEnabled(checked)
        self.ionic.setEnabled(checked)


class MinimizeDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Energy Minimization")
        self.resize(500, 300)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        intro = QLabel(
            "Run a real OpenMM local potential-energy minimization. OpenMM uses L-BFGS and stops when the force tolerance is reached or the iteration limit is exhausted."
        )
        intro.setWordWrap(True); root.addWidget(intro)
        form = QFormLayout()
        self.tolerance = QDoubleSpinBox(); self.tolerance.setRange(0.01, 10000.0); self.tolerance.setDecimals(3); self.tolerance.setValue(10.0); self.tolerance.setSuffix(" kJ/mol/nm")
        self.max_iterations = QSpinBox(); self.max_iterations.setRange(0, 100000); self.max_iterations.setValue(500); self.max_iterations.setSpecialValueText("Unlimited")
        form.addRow("RMS force tolerance", self.tolerance)
        form.addRow("Maximum iterations", self.max_iterations)
        root.addLayout(form)
        note = QLabel("The minimized coordinates are saved as a new item in My Proteins; the original structure is never overwritten.")
        note.setWordWrap(True); root.addWidget(note); root.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("Minimize")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)


class MolecularDynamicsDialog(QDialog):
    def __init__(self, parent=None, *, default_temperature: float = 300.0, default_pressure: float = 1.0) -> None:
        super().__init__(parent)
        self.setWindowTitle("Molecular Dynamics")
        self.resize(560, 535)
        root = QVBoxLayout(self); root.setContentsMargins(14,14,14,14)
        intro = QLabel(
            "Run molecular dynamics with OpenMM's Langevin-middle integrator. NVT controls temperature; "
            "NPT additionally uses an OpenMM Monte Carlo barostat and therefore requires an explicitly solvated periodic system."
        )
        intro.setWordWrap(True); root.addWidget(intro)
        form = QFormLayout()
        self.ensemble = QComboBox(); self.ensemble.addItems(["NVT", "NPT"]); self.ensemble.currentTextChanged.connect(self._ensemble_changed)
        self.temperature = QDoubleSpinBox(); self.temperature.setRange(1, 2000); self.temperature.setDecimals(1); self.temperature.setValue(default_temperature); self.temperature.setSuffix(" K")
        self.pressure = QDoubleSpinBox(); self.pressure.setRange(0.001, 10000.0); self.pressure.setDecimals(3); self.pressure.setValue(default_pressure); self.pressure.setSuffix(" bar")
        self.barostat_interval = QSpinBox(); self.barostat_interval.setRange(1, 1000000); self.barostat_interval.setValue(25); self.barostat_interval.setSuffix(" steps")
        self.friction = QDoubleSpinBox(); self.friction.setRange(0.001, 100.0); self.friction.setDecimals(3); self.friction.setValue(1.0); self.friction.setSuffix(" /ps")
        self.timestep = QDoubleSpinBox(); self.timestep.setRange(0.1, 4.0); self.timestep.setDecimals(2); self.timestep.setValue(2.0); self.timestep.setSuffix(" fs")
        self.steps = QSpinBox(); self.steps.setRange(1, 100000000); self.steps.setValue(2500); self.steps.setSingleStep(500)
        self.report_interval = QSpinBox(); self.report_interval.setRange(1, 1000000); self.report_interval.setValue(250); self.report_interval.setSingleStep(50)
        self.seed = QSpinBox(); self.seed.setRange(1, 2147483647); self.seed.setValue(20260814)
        self.minimize_first = QCheckBox("Minimize before assigning velocities")
        self.minimize_first.setChecked(True)
        for label, widget in [
            ("Ensemble", self.ensemble), ("Temperature", self.temperature), ("Pressure", self.pressure),
            ("Barostat frequency", self.barostat_interval), ("Friction", self.friction), ("Timestep", self.timestep),
            ("Steps", self.steps), ("Trajectory/state interval", self.report_interval), ("Random seed", self.seed),
            ("Pre-run", self.minimize_first),
        ]:
            form.addRow(label, widget)
        root.addLayout(form)
        self.time_label = QLabel(); root.addWidget(self.time_label)
        self.steps.valueChanged.connect(self._update_time); self.timestep.valueChanged.connect(self._update_time); self._update_time()
        note = QLabel(
            "Every report interval is saved as a real coordinate frame for playback and RMSD/RMSF analysis, and a standard DCD trajectory is written too. "
            "NPT is blocked unless the prepared structure has a periodic explicit-solvent box."
        )
        note.setWordWrap(True); root.addWidget(note); root.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText("Run MD")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._ensemble_changed(self.ensemble.currentText())

    def _update_time(self) -> None:
        ps = self.steps.value() * self.timestep.value() / 1000.0
        frame_count = 1 + (self.steps.value() + self.report_interval.value() - 1) // max(1, self.report_interval.value())
        self.time_label.setText(f"Simulated time: {ps:g} ps    •    approximately {frame_count} stored playback frames")

    def _ensemble_changed(self, value: str) -> None:
        npt = value.upper() == "NPT"
        self.pressure.setEnabled(npt)
        self.barostat_interval.setEnabled(npt)


class MutationDialog(QDialog):
    def __init__(self, residues: list[tuple[str, str, str]], parent=None, *, selected: tuple[str, str] | None = None, default_ph: float = 7.0) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mutate Residue")
        self.resize(560, 430)
        root = QVBoxLayout(self); root.setContentsMargins(14,14,14,14)
        intro = QLabel(
            "Create a standard amino-acid substitution with PDBFixer residue templates. This constructs the mutant starting geometry; "
            "it does not claim a stability effect or relaxed mutant conformation until you prepare/minimize/simulate it."
        )
        intro.setWordWrap(True); root.addWidget(intro)
        form = QFormLayout()
        self.residue = QComboBox()
        for chain, number, name in residues:
            self.residue.addItem(f"Chain {chain} · {name} {number}", (chain, number, name))
        if selected:
            for i in range(self.residue.count()):
                data = self.residue.itemData(i)
                if data and data[0] == selected[0] and str(data[1]) == str(selected[1]):
                    self.residue.setCurrentIndex(i); break
        self.target = QComboBox()
        aa = [
            ("Alanine", "ALA"), ("Arginine", "ARG"), ("Asparagine", "ASN"), ("Aspartate", "ASP"),
            ("Cysteine", "CYS"), ("Glutamine", "GLN"), ("Glutamate", "GLU"), ("Glycine", "GLY"),
            ("Histidine", "HIS"), ("Isoleucine", "ILE"), ("Leucine", "LEU"), ("Lysine", "LYS"),
            ("Methionine", "MET"), ("Phenylalanine", "PHE"), ("Proline", "PRO"), ("Serine", "SER"),
            ("Threonine", "THR"), ("Tryptophan", "TRP"), ("Tyrosine", "TYR"), ("Valine", "VAL"),
        ]
        for human, code in aa:
            self.target.addItem(f"{human} ({code})", code)
        self.ph = QDoubleSpinBox(); self.ph.setRange(0,14); self.ph.setDecimals(2); self.ph.setValue(default_ph)
        form.addRow("Residue", self.residue); form.addRow("Mutate to", self.target); form.addRow("Hydrogen completion pH", self.ph)
        root.addLayout(form)
        warning = QLabel(
            "Scientific boundary: PDBFixer supplies standard residue geometry and missing atoms/hydrogens. Protein Lab marks the result as UNRELAXED. "
            "Use Prepare Simulation → Energy Minimization before interpreting local geometry or running dynamics."
        )
        warning.setWordWrap(True); root.addWidget(warning); root.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText("Create Mutant")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    @property
    def residue_data(self) -> tuple[str, str, str]:
        return tuple(self.residue.currentData())

    @property
    def target_code(self) -> str:
        return str(self.target.currentData())


class ConformationalExplorerDialog(QDialog):
    def __init__(self, parent=None, *, default_temperature: float = 300.0) -> None:
        super().__init__(parent)
        self.setWindowTitle("Conformational Explorer")
        self.resize(600, 560)
        root = QVBoxLayout(self); root.setContentsMargins(14,14,14,14)
        intro = QLabel(
            "Explore alternative conformations with real OpenMM Langevin dynamics using repeated heating/cooling replicas. "
            "This is a non-equilibrium sampling protocol, not an AlphaFold-style structure predictor and not proof of the native fold."
        )
        intro.setWordWrap(True); root.addWidget(intro)
        form = QFormLayout()
        self.target_temp = QDoubleSpinBox(); self.target_temp.setRange(1, 1000); self.target_temp.setDecimals(1); self.target_temp.setValue(default_temperature); self.target_temp.setSuffix(" K")
        self.high_temp = QDoubleSpinBox(); self.high_temp.setRange(1, 1500); self.high_temp.setDecimals(1); self.high_temp.setValue(max(450.0, default_temperature)); self.high_temp.setSuffix(" K")
        self.replicas = QSpinBox(); self.replicas.setRange(1, 32); self.replicas.setValue(2)
        self.cycles = QSpinBox(); self.cycles.setRange(1, 50); self.cycles.setValue(2)
        self.points = QSpinBox(); self.points.setRange(2, 20); self.points.setValue(5)
        self.steps_per_temp = QSpinBox(); self.steps_per_temp.setRange(1, 10000000); self.steps_per_temp.setValue(100); self.steps_per_temp.setSingleStep(100)
        self.timestep = QDoubleSpinBox(); self.timestep.setRange(0.1, 4.0); self.timestep.setDecimals(2); self.timestep.setValue(2.0); self.timestep.setSuffix(" fs")
        self.friction = QDoubleSpinBox(); self.friction.setRange(0.001, 100); self.friction.setDecimals(3); self.friction.setValue(1.0); self.friction.setSuffix(" /ps")
        self.seed = QSpinBox(); self.seed.setRange(1, 2147483647); self.seed.setValue(20260814)
        self.minimize_first = QCheckBox("Minimize each replica before sampling"); self.minimize_first.setChecked(True)
        for label, widget in [
            ("Target temperature", self.target_temp), ("High temperature", self.high_temp),
            ("Independent replicas", self.replicas), ("Heating/cooling cycles", self.cycles),
            ("Temperature points per leg", self.points), ("Steps at each temperature", self.steps_per_temp),
            ("Timestep", self.timestep), ("Friction", self.friction), ("Base random seed", self.seed),
            ("Pre-run", self.minimize_first),
        ]:
            form.addRow(label, widget)
        root.addLayout(form)
        self.total = QLabel(); self.total.setWordWrap(True); root.addWidget(self.total)
        for w in (self.replicas, self.cycles, self.points, self.steps_per_temp): w.valueChanged.connect(self._update_total)
        self._update_total()
        note = QLabel(
            "Interpretation rule: the saved structure is the lowest potential-energy snapshot sampled by this protocol, not a guaranteed global minimum or native conformation. "
            "Because temperature changes during the protocol, these samples are not used for equilibrium free-energy estimation."
        )
        note.setWordWrap(True); root.addWidget(note); root.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText("Run exploration")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _update_total(self) -> None:
        stages_per_cycle = self.points.value()*2 - 1
        stages = self.replicas.value()*self.cycles.value()*stages_per_cycle
        steps = stages*self.steps_per_temp.value()
        self.total.setText(f"Protocol size: {stages} temperature stages · {steps:,} integration steps total")


class FreeEnergyLandscapeDialog(QDialog):
    def __init__(self, parent=None, *, default_temperature: float = 300.0) -> None:
        super().__init__(parent)
        self.setWindowTitle("Free-Energy Landscape")
        self.resize(560, 360)
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14)
        intro=QLabel(
            "Estimate an occupancy-derived 2D free-energy surface from stored constant-temperature MD frames using Cα RMSD and protein-heavy-atom radius of gyration."
        ); intro.setWordWrap(True); root.addWidget(intro)
        form=QFormLayout()
        self.temperature=QDoubleSpinBox(); self.temperature.setRange(1,2000); self.temperature.setDecimals(1); self.temperature.setValue(default_temperature); self.temperature.setSuffix(" K")
        self.bins=QSpinBox(); self.bins.setRange(6,100); self.bins.setValue(24)
        form.addRow("Trajectory temperature",self.temperature); form.addRow("Histogram bins / axis",self.bins); root.addLayout(form)
        equation=QLabel("F(s) = −RT ln[P(s)/Pmax]"); ef=equation.font(); ef.setBold(True); equation.setFont(ef); root.addWidget(equation)
        warning=QLabel(
            "Scientific boundary: this relation is meaningful as a free-energy estimate only when the sampled distribution is representative of equilibrium at the stated temperature. "
            "Short or poorly converged MD produces a sampling-dependent apparent landscape, not a converged thermodynamic free-energy surface."
        ); warning.setWordWrap(True); root.addWidget(warning); root.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText("Calculate")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)


class ContactNetworkDialog(QDialog):
    def __init__(self, parent=None, *, has_trajectory: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("Residue Interaction Network")
        self.resize(570, 400)
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14)
        intro=QLabel(
            "Build a residue contact graph. Each standard residue is represented by Cβ (Cα for glycine/fallback), and an edge exists when the representative-atom distance is within the chosen threshold."
        ); intro.setWordWrap(True); root.addWidget(intro)
        form=QFormLayout()
        self.threshold=QDoubleSpinBox(); self.threshold.setRange(1.0,30.0); self.threshold.setDecimals(2); self.threshold.setValue(8.0); self.threshold.setSuffix(" Å")
        self.occupancy=QDoubleSpinBox(); self.occupancy.setRange(0,100); self.occupancy.setDecimals(1); self.occupancy.setValue(25.0 if has_trajectory else 100.0); self.occupancy.setSuffix(" %")
        self.exclude_adjacent=QCheckBox("Exclude directly adjacent residues in the same chain"); self.exclude_adjacent.setChecked(True)
        form.addRow("Contact threshold",self.threshold); form.addRow("Minimum frame occupancy",self.occupancy); form.addRow("Backbone neighbors",self.exclude_adjacent); root.addLayout(form)
        mode = "The current trajectory will be used, so occupancy is the fraction of stored frames satisfying the distance criterion." if has_trajectory else "No trajectory is attached, so the current static structure is analyzed as one frame."
        note=QLabel(mode+" The threshold is a user-defined graph criterion, not a universal physical interaction energy cutoff."); note.setWordWrap(True); root.addWidget(note); root.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText("Build network")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)


class LigandPocketDialog(QDialog):
    def __init__(self, components, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ligands, Cofactors & Binding Pocket")
        self.resize(520, 280)
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14)
        form=QFormLayout()
        self.component=QComboBox()
        for c in components:
            self.component.addItem(f"{c.label}  —  {c.category}  ({c.heavy_atoms} heavy atoms)", c.key)
        self.cutoff=QDoubleSpinBox(); self.cutoff.setRange(1.0,12.0); self.cutoff.setDecimals(2); self.cutoff.setValue(4.0); self.cutoff.setSuffix(" Å")
        form.addRow("Ligand / component",self.component); form.addRow("Pocket cutoff",self.cutoff); root.addLayout(form)
        note=QLabel("Pocket residues are standard protein residues with at least one heavy atom within the selected geometric distance of a heavy atom in the chosen ligand/cofactor. This is a structural contact definition, not a binding-energy calculation.")
        note.setWordWrap(True); root.addWidget(note); root.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText("Analyze pocket"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    @property
    def component_key(self) -> str:
        return str(self.component.currentData())


class InterfaceAnalysisDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Protein Complex Interface Analysis"); self.resize(500,250)
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); form=QFormLayout()
        self.cutoff=QDoubleSpinBox(); self.cutoff.setRange(2.0,12.0); self.cutoff.setDecimals(2); self.cutoff.setValue(5.0); self.cutoff.setSuffix(" Å")
        form.addRow("Heavy-atom contact cutoff",self.cutoff); root.addLayout(form)
        note=QLabel("For every pair of protein chains, Protein Lab identifies residue pairs whose heavy atoms approach within the selected cutoff. It reports geometry and interface-residue membership; it does not convert a distance contact into a binding free energy.")
        note.setWordWrap(True); root.addWidget(note); root.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText("Analyze interfaces"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)


class ValidationDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Structural Validation"); self.resize(540,310)
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); form=QFormLayout()
        self.clash_overlap=QDoubleSpinBox(); self.clash_overlap.setRange(0.0,1.5); self.clash_overlap.setDecimals(2); self.clash_overlap.setValue(0.40); self.clash_overlap.setSuffix(" Å")
        self.break_distance=QDoubleSpinBox(); self.break_distance.setRange(1.4,5.0); self.break_distance.setDecimals(2); self.break_distance.setValue(1.80); self.break_distance.setSuffix(" Å")
        form.addRow("Potential-clash overlap threshold",self.clash_overlap); form.addRow("C–N chain-break warning threshold",self.break_distance); root.addLayout(form)
        note=QLabel("Validation in this build is transparent geometry QC: missing N/CA/C/O backbone atoms, peptide C–N continuity, exact φ/ψ/ω torsions, and conservative nonbonded heavy-atom overlap warnings using tabulated van der Waals radii. Same-residue and adjacent-residue atom pairs are excluded from clash screening. It is not branded as MolProbity and does not invent empirical percentile scores.")
        note.setWordWrap(True); root.addWidget(note); root.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText("Run validation"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)


class StructureComparisonDialog(QDialog):
    def __init__(self, current_record, records, parent=None) -> None:
        super().__init__(parent); self.current=current_record; self.records=[r for r in records if r.id != current_record.id]
        self.setWindowTitle("Compare / Align Structures"); self.resize(560,350)
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); form=QFormLayout()
        self.comparison=QComboBox()
        for r in self.records: self.comparison.addItem(f"{r.name}  [{r.origin}]",r.id)
        self.current_chain=QComboBox(); self.other_chain=QComboBox()
        from .structural_analysis import protein_chain_ids
        for c in protein_chain_ids(current_record): self.current_chain.addItem(c)
        self._record_map={r.id:r for r in self.records}
        self.comparison.currentIndexChanged.connect(self._update_chains); self._update_chains()
        form.addRow("Current structure",QLabel(current_record.name)); form.addRow("Current chain",self.current_chain); form.addRow("Comparison structure",self.comparison); form.addRow("Comparison chain",self.other_chain); root.addLayout(form)
        note=QLabel("Protein Lab globally aligns the two chain sequences, pairs Cα coordinates across aligned sequence blocks, then uses a least-squares Kabsch rigid-body superposition. RMSD and per-residue displacements are computed only for those aligned Cα pairs. The comparison structure is overlaid in red after the same rigid transform is applied to all of its atoms.")
        note.setWordWrap(True); root.addWidget(note); root.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText("Align & compare"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _update_chains(self) -> None:
        self.other_chain.clear()
        if not self.records: return
        from .structural_analysis import protein_chain_ids
        rec=self._record_map.get(str(self.comparison.currentData()))
        if rec:
            for c in protein_chain_ids(rec): self.other_chain.addItem(c)

    @property
    def comparison_record(self):
        return self._record_map.get(str(self.comparison.currentData()))


class MembranePreparationDialog(QDialog):
    def __init__(self, parent=None, *, default_ph: float=7.0, default_ionic: float=0.15) -> None:
        super().__init__(parent); self.setWindowTitle("Build Explicit Membrane System"); self.resize(580,390)
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); form=QFormLayout()
        self.lipid=QComboBox(); self.lipid.addItems(["POPC","POPE","DLPC","DLPE","DMPC","DOPC","DPPC"])
        self.padding=QDoubleSpinBox(); self.padding.setRange(0.5,4.0); self.padding.setValue(1.0); self.padding.setDecimals(2); self.padding.setSuffix(" nm")
        self.ionic=QDoubleSpinBox(); self.ionic.setRange(0.0,2.0); self.ionic.setValue(default_ionic); self.ionic.setDecimals(3); self.ionic.setSuffix(" M")
        self.ph=QDoubleSpinBox(); self.ph.setRange(0.0,14.0); self.ph.setValue(default_ph); self.ph.setDecimals(2)
        self.remove_heterogens=QCheckBox("Remove nonstandard residues/ligands before parameterization"); self.remove_heterogens.setChecked(True)
        form.addRow("Lipid",self.lipid); form.addRow("Minimum periodic padding",self.padding); form.addRow("Ionic strength",self.ionic); form.addRow("Hydrogen-addition pH",self.ph); form.addRow("Cleanup",self.remove_heterogens); root.addLayout(form)
        warning=QLabel("IMPORTANT ORIENTATION ASSUMPTION: OpenMM builds the membrane in the XY plane with its normal along Z. Protein Lab does not infer membrane orientation in this phase. Use a structure that is already correctly positioned/oriented; otherwise the membrane may be physically misplaced.")
        warning.setWordWrap(True); root.addWidget(warning)
        note=QLabel("OpenMM Modeller.addMembrane constructs the lipid bilayer together with explicit water and ions and relaxes the inserted membrane. This can be substantially slower and larger than ordinary protein preparation.")
        note.setWordWrap(True); root.addWidget(note); root.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText("Build membrane system"); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
