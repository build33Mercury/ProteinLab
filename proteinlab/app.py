from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QProgressDialog,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .builder import build_peptide_structure
from .folding import FoldPredictionResult, FoldPredictionThread
from .dialogs import (
    CreateProteinDialog, MolecularDynamicsDialog, MinimizeDialog, MutationDialog, PrepareSimulationDialog,
    ConformationalExplorerDialog, FreeEnergyLandscapeDialog, ContactNetworkDialog, LigandPocketDialog,
    InterfaceAnalysisDialog, ValidationDialog, StructureComparisonDialog, MembranePreparationDialog,
)
from .geometry import MeasurementResult, measure
from .analysis import compute_rmsd, compute_rmsf, load_trajectory, trajectory_path_for_record, write_trajectory_frame
from .advanced_analysis import compute_free_energy_landscape, compute_residue_contact_network
from .analysis_extra import compute_sasa, detect_hydrogen_bonds
from .structural_analysis import (
    list_nonprotein_components, analyze_binding_pocket, analyze_chain_interfaces, validate_structure_geometry, compare_structures,
)
from .membrane import MembranePreparationOptions, prepare_membrane_system
from .conformational import ConformationalOptions, run_conformational_exploration
from .icons import make_icon
from .notebook import append_entry, load_entries, save_entries, methods_text
from .projects import load_project, save_project
from .workflow_dialogs import CalculationInspectorDialog, ExperimentNotebookDialog, StudentLearningDialog, TextReportDialog
from .help_dialog import HelpAidDialog
from .validation_dialog import ValidationCenterDialog
from .performance import structure_advice, trajectory_advice
from .library import (
    builtins_from_project,
    import_structure,
    load_user_library,
    remove_user_record,
    save_user_library,
)
from .models import ProteinRecord
from .mutation import mutate_residue
from .preparation import PreparationOptions, prepare_simulation_system
from .physics import (
    MDOptions, MinimizationOptions, evaluate_energy, is_simulation_ready,
    minimize_structure, run_molecular_dynamics,
)
from .structure import AtomRecord, inspect_structure, pdb_path_for_vtk, read_structure
from .theme import apply_dark_theme, apply_light_theme
from .tools import TOOLS, ToolSpec
from .toolbox_dialog import ProteinToolboxDialog
from .ui_widgets import LinePlotWidget, HeatmapWidget
from .viewer import ProteinViewer


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.settings = QSettings("ProteinLab", "ProteinLabNative")
        self.project_root = Path(__file__).resolve().parents[1]
        self.builtins = builtins_from_project(self.project_root)
        self.user_records = load_user_library()
        self.current_record: ProteinRecord | None = None
        self.current_pdb_path: Path | None = None
        self.current_atoms: list[AtomRecord] = []
        self.measurement_kind: str | None = None
        self.measurement_atoms: list[AtomRecord] = []
        self.last_selected_atom: AtomRecord | None = None
        self.toolbox_dialog: ProteinToolboxDialog | None = None
        self.fold_thread: FoldPredictionThread | None = None
        self.trajectory_data = None
        self.trajectory_frame = 0
        self.trajectory_timer = QTimer(self)
        self.trajectory_timer.setInterval(130)
        self.trajectory_timer.timeout.connect(self._trajectory_tick)

        self.setWindowTitle(f"Protein Lab {__version__}")
        self.resize(1480, 900)
        self.setMinimumSize(1080, 700)
        self.setDockNestingEnabled(True)
        self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        self._make_actions()
        self._make_menu_bar()
        self._make_toolbar()
        self._make_central_view()
        self._make_info_dock()
        self._make_bottom_dock()
        self.statusBar().showMessage(f"Protein Lab {__version__}")

        dark = self.settings.value("dark_mode", False, type=bool)
        self.dark_toggle.setChecked(dark)
        self._apply_theme(dark)

        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        window_state = self.settings.value("window_state")
        if window_state is not None:
            self.restoreState(window_state)
        self._load_first_available_builtin()

    # ---------- shell ----------
    def _make_actions(self) -> None:
        self.toolbox_action = QAction(make_icon("toolbox"), "Protein Toolbox", self)
        self.toolbox_action.setShortcut("Ctrl+K")
        self.toolbox_action.triggered.connect(self.open_protein_toolbox)
        self.import_action = QAction(make_icon("import"), "Import Your Own Protein…", self)
        self.import_action.setShortcut(QKeySequence.Open); self.import_action.triggered.connect(self.import_structure_dialog)
        self.new_protein_action = QAction(make_icon("create"), "Create Protein…", self); self.new_protein_action.triggered.connect(self.create_protein_dialog)
        self.remove_action = QAction("Remove from My Proteins", self); self.remove_action.triggered.connect(self.remove_current)
        self.reset_camera_action = QAction(make_icon("reset"), "Reset View", self); self.reset_camera_action.setShortcut("R"); self.reset_camera_action.triggered.connect(lambda: self.viewer.reset_camera())
        self.prepare_action = QAction(make_icon("prepare"), "Prepare Simulation…", self); self.prepare_action.triggered.connect(self.prepare_simulation_dialog)
        self.energy_action = QAction(make_icon("energy"), "Energy Inspector", self); self.energy_action.triggered.connect(self.evaluate_current_energy)
        self.minimize_action = QAction(make_icon("minimize"), "Energy Minimization…", self); self.minimize_action.triggered.connect(self.minimize_current_structure)
        self.md_action = QAction(make_icon("md"), "Molecular Dynamics…", self); self.md_action.triggered.connect(self.run_md_dialog)
        self.trajectory_action = QAction(make_icon("trajectory"), "Trajectory Playback", self); self.trajectory_action.triggered.connect(self.open_trajectory_panel)
        self.rmsd_action = QAction(make_icon("rmsd"), "RMSD", self); self.rmsd_action.triggered.connect(self.calculate_rmsd)
        self.rmsf_action = QAction(make_icon("rmsf"), "RMSF", self); self.rmsf_action.triggered.connect(self.calculate_rmsf)
        self.mutate_action = QAction(make_icon("mutant"), "Mutate Residue…", self); self.mutate_action.triggered.connect(self.mutate_current_residue)
        self.environment_action = QAction(make_icon("environment"), "Environment", self); self.environment_action.triggered.connect(self.open_environment_panel)
        self.conformational_action = QAction(make_icon("explore"), "Conformational Explorer…", self); self.conformational_action.triggered.connect(self.run_conformational_explorer)
        self.landscape_action = QAction(make_icon("landscape"), "Free-Energy Landscape…", self); self.landscape_action.triggered.connect(self.calculate_free_energy_landscape)
        self.network_action = QAction(make_icon("network"), "Residue Interaction Network…", self); self.network_action.triggered.connect(self.build_contact_network)
        self.hbond_action = QAction(make_icon("hbond"), "Hydrogen Bonds…", self); self.hbond_action.triggered.connect(self.analyze_hydrogen_bonds)
        self.sasa_action = QAction(make_icon("surface"), "Solvent-Accessible Surface Area…", self); self.sasa_action.triggered.connect(self.calculate_sasa)
        self.ligand_action = QAction(make_icon("ligand"), "Ligands & Binding Pockets…", self); self.ligand_action.triggered.connect(self.analyze_ligand_pocket)
        self.interface_action = QAction(make_icon("interface"), "Complex Interfaces…", self); self.interface_action.triggered.connect(self.analyze_complex_interfaces)
        self.membrane_action = QAction(make_icon("membrane"), "Build Membrane System…", self); self.membrane_action.triggered.connect(self.prepare_membrane_dialog)
        self.validation_action = QAction(make_icon("validate"), "Structural Validation…", self); self.validation_action.triggered.connect(self.run_structural_validation)
        self.compare_action = QAction(make_icon("compare"), "Compare / Align Structures…", self); self.compare_action.triggered.connect(self.compare_structures_dialog)
        self.fold_action = QAction(make_icon("fold"), "Fold / Predict Structure", self); self.fold_action.triggered.connect(self.predict_current_structure)
        self.calculation_action = QAction(make_icon("equation"), "Calculation Inspector…", self); self.calculation_action.triggered.connect(self.open_calculation_inspector)
        self.notebook_action = QAction(make_icon("notebook"), "Experiment Notebook…", self); self.notebook_action.triggered.connect(self.open_experiment_notebook)
        self.methods_action = QAction(make_icon("methods"), "Generate Methods…", self); self.methods_action.triggered.connect(self.generate_methods_report)
        self.student_guide_action = QAction(make_icon("learn"), "Student Lab Guide…", self); self.student_guide_action.triggered.connect(lambda: StudentLearningDialog(self).exec())
        self.save_project_action = QAction(make_icon("project"), "Save Project…", self); self.save_project_action.triggered.connect(self.save_project_dialog)
        self.load_project_action = QAction(make_icon("project"), "Open Project…", self); self.load_project_action.triggered.connect(self.load_project_dialog)
        self.export_structure_action = QAction(make_icon("export"), "Export Current Structure…", self); self.export_structure_action.triggered.connect(self.export_current_structure)
        self.export_fasta_action = QAction(make_icon("export"), "Export FASTA…", self); self.export_fasta_action.triggered.connect(self.export_current_fasta)
        self.export_simulation_action = QAction(make_icon("export"), "Export Simulation Bundle…", self); self.export_simulation_action.triggered.connect(self.export_simulation_bundle)
        self.export_notebook_action = QAction(make_icon("export"), "Export Experiment Notebook…", self); self.export_notebook_action.triggered.connect(self.export_notebook_json)
        self.exit_action = QAction("Exit", self); self.exit_action.setShortcut(QKeySequence.Quit); self.exit_action.triggered.connect(self.close)
        self.validation_center_action = QAction(make_icon("benchmark"), "Validation Center…", self); self.validation_center_action.triggered.connect(self.open_validation_center)
        self.help_aid_action = QAction(make_icon("help"), "Help Aid", self); self.help_aid_action.setShortcut(QKeySequence.HelpContents); self.help_aid_action.triggered.connect(self.open_help_aid)
        self.about_action = QAction("About Protein Lab", self); self.about_action.triggered.connect(self.show_about)

    def _make_menu_bar(self) -> None:
        file_menu=self.menuBar().addMenu("&File"); file_menu.addAction(self.toolbox_action); file_menu.addSeparator(); file_menu.addAction(self.import_action); file_menu.addAction(self.new_protein_action); file_menu.addSeparator(); file_menu.addAction(self.save_project_action); file_menu.addAction(self.load_project_action); file_menu.addSeparator(); file_menu.addAction(self.export_structure_action); file_menu.addAction(self.export_fasta_action); file_menu.addAction(self.export_simulation_action); file_menu.addAction(self.export_notebook_action); file_menu.addSeparator(); file_menu.addAction(self.remove_action); file_menu.addSeparator(); file_menu.addAction(self.exit_action)
        protein_menu=self.menuBar().addMenu("&Protein"); protein_menu.addAction(self.toolbox_action); protein_menu.addAction(self.fold_action); protein_menu.addAction(self.mutate_action); protein_menu.addSeparator(); protein_menu.addAction(self.reset_camera_action)
        sim_menu=self.menuBar().addMenu("&Simulation"); sim_menu.addAction(self.prepare_action); sim_menu.addAction(self.membrane_action); sim_menu.addAction(self.environment_action); sim_menu.addSeparator(); sim_menu.addAction(self.energy_action); sim_menu.addAction(self.minimize_action); sim_menu.addAction(self.md_action); sim_menu.addSeparator(); sim_menu.addAction(self.conformational_action)
        analysis_menu=self.menuBar().addMenu("&Analysis"); analysis_menu.addAction(self.trajectory_action); analysis_menu.addAction(self.rmsd_action); analysis_menu.addAction(self.rmsf_action); analysis_menu.addSeparator(); analysis_menu.addAction(self.landscape_action); analysis_menu.addAction(self.network_action); analysis_menu.addAction(self.hbond_action); analysis_menu.addAction(self.sasa_action); analysis_menu.addSeparator(); analysis_menu.addAction(self.ligand_action); analysis_menu.addAction(self.interface_action); analysis_menu.addAction(self.validation_action); analysis_menu.addAction(self.compare_action); analysis_menu.addSeparator(); analysis_menu.addAction(self.calculation_action); analysis_menu.addAction(self.notebook_action); analysis_menu.addAction(self.methods_action); analysis_menu.addSeparator()
        for label,kind,icon in (("Measure Distance","Distance","distance"),("Measure Angle","Angle","angle"),("Measure Dihedral","Dihedral","dihedral")):
            a=QAction(make_icon(icon),label,self); a.triggered.connect(lambda _checked=False,k=kind:self._activate_measurement(k)); analysis_menu.addAction(a)
        view_menu=self.menuBar().addMenu("&View"); view_menu.addAction(self.reset_camera_action)
        learn_menu=self.menuBar().addMenu("&Learn"); learn_menu.addAction(self.student_guide_action); learn_menu.addAction(self.calculation_action); learn_menu.addAction(self.help_aid_action)
        help_menu=self.menuBar().addMenu("&Help"); help_menu.addAction(self.help_aid_action); help_menu.addAction(self.validation_center_action); help_menu.addSeparator(); help_menu.addAction(self.about_action)

    def _make_toolbar(self) -> None:
        toolbar=QToolBar("Main",self); toolbar.setObjectName("MainToolbar"); toolbar.setMovable(False); toolbar.setIconSize(QSize(24,24)); toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); self.addToolBar(Qt.TopToolBarArea,toolbar)
        toolbar.addAction(self.toolbox_action); toolbar.addSeparator(); toolbar.addAction(self.import_action); toolbar.addAction(self.new_protein_action); toolbar.addAction(self.fold_action); toolbar.addSeparator()
        sim_button=QToolButton(); sim_button.setText("Simulate"); sim_button.setIcon(make_icon("md")); sim_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); sim_button.setPopupMode(QToolButton.InstantPopup)
        sim_menu=QMenu(sim_button); [sim_menu.addAction(a) for a in (self.prepare_action,self.membrane_action,self.environment_action,self.energy_action,self.minimize_action,self.md_action,self.conformational_action)]; sim_button.setMenu(sim_menu); toolbar.addWidget(sim_button)
        analysis_button=QToolButton(); analysis_button.setText("Analyze"); analysis_button.setIcon(make_icon("analysis")); analysis_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); analysis_button.setPopupMode(QToolButton.InstantPopup)
        analysis_menu=QMenu(analysis_button); [analysis_menu.addAction(a) for a in (self.trajectory_action,self.rmsd_action,self.rmsf_action,self.landscape_action,self.network_action,self.hbond_action,self.sasa_action,self.ligand_action,self.interface_action,self.validation_action,self.compare_action)]; analysis_button.setMenu(analysis_menu); toolbar.addWidget(analysis_button)
        edit_button=QToolButton(); edit_button.setText("Edit"); edit_button.setIcon(make_icon("mutant")); edit_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); edit_button.setPopupMode(QToolButton.InstantPopup); em=QMenu(edit_button); em.addAction(self.mutate_action); edit_button.setMenu(em); toolbar.addWidget(edit_button)
        toolbar.addSeparator(); toolbar.addAction(self.reset_camera_action); toolbar.addWidget(QLabel("Representation"))
        self.representation=QComboBox(); self.representation.addItems(["Ribbon","Ball and stick","Sticks","Space filling"]); self.representation.setMinimumWidth(135); self.representation.currentTextChanged.connect(self._representation_changed); toolbar.addWidget(self.representation)
        spacer=QWidget(); spacer.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred); toolbar.addWidget(spacer)
        toolbar.addAction(self.validation_center_action); toolbar.addAction(self.help_aid_action); toolbar.addSeparator()
        self.mode_combo=QComboBox(); self.mode_combo.addItems(["Research","Student"]); self.mode_combo.setCurrentText("Research"); self.mode_combo.setToolTip("Research is the default. Student mode uses the same scientific engine with additional guidance."); self.mode_combo.currentTextChanged.connect(self._mode_changed); toolbar.addWidget(self.mode_combo); self.dark_toggle=QCheckBox("Dark mode"); self.dark_toggle.toggled.connect(self._theme_toggled); toolbar.addWidget(self.dark_toggle)

    def _make_central_view(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(3, 3, 3, 3)
        self.viewer = ProteinViewer()
        self.viewer.atomPicked.connect(self._atom_picked)
        layout.addWidget(self.viewer, 1)
        self.setCentralWidget(central)

    # ---------- Cello-style Protein Toolbox chooser ----------
    def open_protein_toolbox(self) -> None:
        dialog=ProteinToolboxDialog([*self.builtins,*self.user_records],self)
        self.toolbox_dialog=dialog
        if dialog.exec()!=QDialog.Accepted or not dialog.selection: return
        kind,key=dialog.selection.split("|",1)
        if kind=="protein":
            record=self._record_by_id(key)
            if record: self.load_record(record)
        else: self._activate_tool(key)

    def _refresh_toolbox(self) -> None:
        # Chooser is rebuilt from the current records every time it opens.
        return

    def _activate_tool(self,key:str) -> None:
        tool=next((t for t in TOOLS if t.key==key),None)
        if not tool: return
        if not tool.available:
            self.statusBar().showMessage(f"{tool.name} is unavailable in this installation."); return
        actions={
            "import":self.import_structure_dialog,"build-protein":self.create_protein_dialog,"reset-camera":self.viewer.reset_camera,
            "prepare":self.prepare_simulation_dialog,"energy":self.evaluate_current_energy,"minimize":self.minimize_current_structure,"md":self.run_md_dialog,
            "trajectory":self.open_trajectory_panel,"rmsd":self.calculate_rmsd,"rmsf":self.calculate_rmsf,"mutate":self.mutate_current_residue,"environment":self.open_environment_panel,
            "conformational":self.run_conformational_explorer,"landscape":self.calculate_free_energy_landscape,"contact-network":self.build_contact_network,
            "ligand-pocket":self.analyze_ligand_pocket,"complex-interface":self.analyze_complex_interfaces,"membrane":self.prepare_membrane_dialog,
            "validate-structure":self.run_structural_validation,"compare-structures":self.compare_structures_dialog,
            "fold-predict":self.predict_current_structure,"calculation-inspector":self.open_calculation_inspector,
            "experiment-notebook":self.open_experiment_notebook,"methods-generator":self.generate_methods_report,
            "save-project":self.save_project_dialog,
            "hydrogen-bonds":self.analyze_hydrogen_bonds,"contacts":self.build_contact_network,"surface":self.calculate_sasa,
            "validation-center":self.open_validation_center,"help-aid":self.open_help_aid,
        }
        if key in actions: actions[key](); return
        if key=="pointer": self._stop_measurement(clear=True)
        elif key=="representation": self.representation.setFocus(); self.representation.showPopup()
        elif key=="protein-info": self.info_tabs.setCurrentWidget(self.summary_tab)
        elif key=="sequence": self.info_tabs.setCurrentWidget(self.sequence_text)
        elif key=="distance": self._activate_measurement("Distance")
        elif key=="angle": self._activate_measurement("Angle")
        elif key=="dihedral": self._activate_measurement("Dihedral")

    # ---------- right inspector ----------
    def _make_info_dock(self) -> None:
        dock = QDockWidget("Inspector", self)
        dock.setObjectName("InspectorDock")
        tabs = QTabWidget()

        summary = QWidget()
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(8, 8, 8, 8)
        self.name_label = QLabel("No protein loaded")
        font = self.name_label.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        self.name_label.setFont(font)
        summary_layout.addWidget(self.name_label)

        self.description_label = QLabel("")
        self.description_label.setWordWrap(True)
        summary_layout.addWidget(self.description_label)

        self.info_table = QTableWidget(0, 2)
        self.info_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.info_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.info_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.info_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.info_table.setShowGrid(False)
        summary_layout.addWidget(self.info_table, 1)
        tabs.addTab(summary, make_icon("protein"), "Protein")
        self.summary_tab = summary

        self.selection_text = QTextEdit()
        self.selection_text.setReadOnly(True)
        self.selection_text.setPlainText("Click an atom in the 3D viewport to inspect its exact structure coordinates.")
        tabs.addTab(self.selection_text, make_icon("pointer"), "Selection")

        self.sequence_text = QTextEdit()
        self.sequence_text.setReadOnly(True)
        self.sequence_text.setLineWrapMode(QTextEdit.NoWrap)
        tabs.addTab(self.sequence_text, make_icon("sequence"), "Sequence")

        self.provenance_text = QTextEdit()
        self.provenance_text.setReadOnly(True)
        tabs.addTab(self.provenance_text, make_icon("info"), "Source")

        dock.setWidget(tabs)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setMinimumWidth(310)
        dock.resize(340, 600)
        self.info_tabs = tabs

    # ---------- compact experiment / math / simulation area ----------
    def _make_bottom_dock(self) -> None:
        dock=QDockWidget("Analysis & Simulation",self); dock.setObjectName("ExperimentDock")
        tabs=QTabWidget(); self.experiment_tabs=tabs

        # Geometry
        measurements=QWidget(); mlayout=QHBoxLayout(measurements); mlayout.setContentsMargins(8,8,8,8)
        self.measurement_table=QTableWidget(0,3); self.measurement_table.setHorizontalHeaderLabels(["Measurement","Value","Atoms"]); self.measurement_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents); self.measurement_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents); self.measurement_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch); self.measurement_table.verticalHeader().setVisible(False); self.measurement_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.measurement_table.itemSelectionChanged.connect(self._measurement_history_selected); mlayout.addWidget(self.measurement_table,3)
        detail=QWidget(); dl=QVBoxLayout(detail); dl.setContentsMargins(6,0,0,0); self.measurement_equation=QLabel("Choose a measurement tool from Protein Toolbox."); f=self.measurement_equation.font(); f.setBold(True); self.measurement_equation.setFont(f); self.measurement_equation.setWordWrap(True); dl.addWidget(self.measurement_equation); self.measurement_detail=QTextEdit(); self.measurement_detail.setReadOnly(True); dl.addWidget(self.measurement_detail,1); clear=QPushButton(make_icon("reset"),"Clear measurements"); clear.clicked.connect(self._clear_measurements); dl.addWidget(clear); mlayout.addWidget(detail,2)
        tabs.addTab(measurements,make_icon("distance"),"Geometry"); self.measurements_tab=measurements

        # Energy
        energy=QWidget(); el=QHBoxLayout(energy); el.setContentsMargins(8,8,8,8); left=QVBoxLayout(); ar=QHBoxLayout()
        eb=QPushButton(make_icon("energy"),"Evaluate energy"); eb.clicked.connect(self.evaluate_current_energy); mb=QPushButton(make_icon("minimize"),"Minimize"); mb.clicked.connect(self.minimize_current_structure); db=QPushButton(make_icon("md"),"Run MD"); db.clicked.connect(self.run_md_dialog); [ar.addWidget(x) for x in (eb,mb,db)]; ar.addStretch(1); left.addLayout(ar)
        self.energy_table=QTableWidget(0,3); self.energy_table.setHorizontalHeaderLabels(["Force term","Energy (kJ/mol)","OpenMM force"]); self.energy_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents); self.energy_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents); self.energy_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch); self.energy_table.verticalHeader().setVisible(False); self.energy_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.energy_table.itemSelectionChanged.connect(self._energy_term_selected); left.addWidget(self.energy_table,1); self.energy_summary=QLabel("Prepare a structure, then evaluate its force-field potential energy."); self.energy_summary.setWordWrap(True); left.addWidget(self.energy_summary); el.addLayout(left,3); self.energy_detail=QTextEdit(); self.energy_detail.setReadOnly(True); el.addWidget(self.energy_detail,2)
        tabs.addTab(energy,make_icon("energy"),"Energy"); self.energy_tab=energy

        # MD run log
        dynamics=QWidget(); d=QVBoxLayout(dynamics); d.setContentsMargins(8,8,8,8); top=QHBoxLayout(); self.md_status=QLabel("No molecular-dynamics run in this session."); self.md_status.setWordWrap(True); rb=QPushButton(make_icon("md"),"Run molecular dynamics…"); rb.clicked.connect(self.run_md_dialog); top.addWidget(self.md_status,1); top.addWidget(rb); d.addLayout(top); self.md_table=QTableWidget(0,5); self.md_table.setHorizontalHeaderLabels(["Step","Time (ps)","Potential","Kinetic","Total (kJ/mol)"]); self.md_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.md_table.verticalHeader().setVisible(False); self.md_table.setEditTriggers(QAbstractItemView.NoEditTriggers); d.addWidget(self.md_table,1)
        tabs.addTab(dynamics,make_icon("md"),"Dynamics"); self.dynamics_tab=dynamics

        # Trajectory playback
        traj=QWidget(); tl=QVBoxLayout(traj); tl.setContentsMargins(8,8,8,8); tr=QHBoxLayout()
        self.traj_prev=QPushButton("◀"); self.traj_play=QPushButton(make_icon("trajectory"),"Play"); self.traj_next=QPushButton("▶"); self.traj_prev.clicked.connect(lambda:self._step_trajectory(-1)); self.traj_next.clicked.connect(lambda:self._step_trajectory(1)); self.traj_play.clicked.connect(self._toggle_trajectory_playback); tr.addWidget(self.traj_prev); tr.addWidget(self.traj_play); tr.addWidget(self.traj_next)
        self.traj_slider=QSlider(Qt.Horizontal); self.traj_slider.setRange(0,0); self.traj_slider.valueChanged.connect(self._trajectory_slider_changed); tr.addWidget(self.traj_slider,1); self.traj_label=QLabel("No trajectory loaded"); tr.addWidget(self.traj_label); tl.addLayout(tr)
        self.traj_energy_plot=LinePlotWidget(); tl.addWidget(self.traj_energy_plot,1); self.traj_note=QLabel("MD results store real coordinate frames plus a standard DCD trajectory. Load an MD result to scrub the frames."); self.traj_note.setWordWrap(True); tl.addWidget(self.traj_note)
        tabs.addTab(traj,make_icon("trajectory"),"Trajectory"); self.trajectory_tab=traj

        # Analysis
        analysis=QWidget(); al=QHBoxLayout(analysis); al.setContentsMargins(8,8,8,8); ah=QVBoxLayout(); br=QHBoxLayout(); rdb=QPushButton(make_icon("rmsd"),"Calculate RMSD"); rdb.clicked.connect(self.calculate_rmsd); rfb=QPushButton(make_icon("rmsf"),"Calculate RMSF"); rfb.clicked.connect(self.calculate_rmsf); br.addWidget(rdb); br.addWidget(rfb); br.addStretch(1); ah.addLayout(br); self.analysis_plot=LinePlotWidget(); ah.addWidget(self.analysis_plot,1); al.addLayout(ah,3); self.analysis_detail=QTextEdit(); self.analysis_detail.setReadOnly(True); self.analysis_detail.setPlainText("Load an MD trajectory, then calculate a coordinate-based analysis. RMSD/RMSF use Kabsch alignment and C-alpha atoms by default."); al.addWidget(self.analysis_detail,2)
        tabs.addTab(analysis,make_icon("analysis"),"Analysis"); self.analysis_tab=analysis

        # Conformational exploration
        explore=QWidget(); exl=QHBoxLayout(explore); exl.setContentsMargins(8,8,8,8); exleft=QVBoxLayout(); exbar=QHBoxLayout(); exrun=QPushButton(make_icon("explore"),"Run conformational exploration…"); exrun.clicked.connect(self.run_conformational_explorer); exbar.addWidget(exrun); exbar.addStretch(1); exleft.addLayout(exbar); self.explore_plot=LinePlotWidget(); exleft.addWidget(self.explore_plot,1); exl.addLayout(exleft,3); self.explore_detail=QTextEdit(); self.explore_detail.setReadOnly(True); self.explore_detail.setPlainText("Heating/cooling exploration uses real OpenMM dynamics but is explicitly non-equilibrium and is not labeled as native-fold prediction."); exl.addWidget(self.explore_detail,2); tabs.addTab(explore,make_icon("explore"),"Explore"); self.explore_tab=explore

        # Occupancy-derived free-energy landscape
        landscape=QWidget(); lal=QHBoxLayout(landscape); lal.setContentsMargins(8,8,8,8); laleft=QVBoxLayout(); labar=QHBoxLayout(); lab=QPushButton(make_icon("landscape"),"Calculate free-energy landscape…"); lab.clicked.connect(self.calculate_free_energy_landscape); labar.addWidget(lab); labar.addStretch(1); laleft.addLayout(labar); self.landscape_heatmap=HeatmapWidget(); laleft.addWidget(self.landscape_heatmap,1); lal.addLayout(laleft,3); self.landscape_detail=QTextEdit(); self.landscape_detail.setReadOnly(True); self.landscape_detail.setPlainText("Requires a constant-temperature MD trajectory. Protein Lab reports the exact histogram equation and warns when the result is sampling-limited."); lal.addWidget(self.landscape_detail,2); tabs.addTab(landscape,make_icon("landscape"),"Landscape"); self.landscape_tab=landscape

        # Residue interaction network
        network=QWidget(); nwl=QHBoxLayout(network); nwl.setContentsMargins(8,8,8,8); nwleft=QVBoxLayout(); nwbar=QHBoxLayout(); nwb=QPushButton(make_icon("network"),"Build residue network…"); nwb.clicked.connect(self.build_contact_network); nwbar.addWidget(nwb); nwbar.addStretch(1); nwleft.addLayout(nwbar); self.network_table=QTableWidget(0,5); self.network_table.setHorizontalHeaderLabels(["Residue A","Residue B","Occupancy","Mean distance (Å)","Min distance (Å)"]); self.network_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.network_table.verticalHeader().setVisible(False); self.network_table.setEditTriggers(QAbstractItemView.NoEditTriggers); nwleft.addWidget(self.network_table,1); nwl.addLayout(nwleft,3); self.network_detail=QTextEdit(); self.network_detail.setReadOnly(True); self.network_detail.setPlainText("Build a transparent residue contact graph from Cβ/Cα representative-atom distances. Thresholds are explicit user-defined graph criteria."); nwl.addWidget(self.network_detail,2); tabs.addTab(network,make_icon("network"),"Network"); self.network_tab=network

        # Ligands/cofactors and distance-defined binding pockets
        ligand=QWidget(); lgl=QVBoxLayout(ligand); lgl.setContentsMargins(8,8,8,8); lgbar=QHBoxLayout(); lgb=QPushButton(make_icon("ligand"),"Analyze ligand / pocket…"); lgb.clicked.connect(self.analyze_ligand_pocket); lgbar.addWidget(lgb); lgbar.addStretch(1); lgl.addLayout(lgbar)
        self.ligand_summary=QLabel("Identify non-protein components and inspect the protein residues geometrically surrounding a selected ligand or cofactor."); self.ligand_summary.setWordWrap(True); lgl.addWidget(self.ligand_summary)
        self.ligand_table=QTableWidget(0,4); self.ligand_table.setHorizontalHeaderLabels(["Component","Category","Atoms","Heavy atoms"]); self.ligand_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.ligand_table.verticalHeader().setVisible(False); self.ligand_table.setEditTriggers(QAbstractItemView.NoEditTriggers); lgl.addWidget(self.ligand_table,1)
        self.pocket_table=QTableWidget(0,3); self.pocket_table.setHorizontalHeaderLabels(["Pocket residue","Minimum distance (Å)","Heavy-atom contacts"]); self.pocket_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.pocket_table.verticalHeader().setVisible(False); self.pocket_table.setEditTriggers(QAbstractItemView.NoEditTriggers); lgl.addWidget(self.pocket_table,1)
        tabs.addTab(ligand,make_icon("ligand"),"Ligands"); self.ligand_tab=ligand

        # Multi-chain interfaces + explicit membrane construction
        complex_tab=QWidget(); cxl=QVBoxLayout(complex_tab); cxl.setContentsMargins(8,8,8,8); cxbar=QHBoxLayout(); cxb=QPushButton(make_icon("interface"),"Analyze chain interfaces…"); cxb.clicked.connect(self.analyze_complex_interfaces); memb=QPushButton(make_icon("membrane"),"Build membrane system…"); memb.clicked.connect(self.prepare_membrane_dialog); cxbar.addWidget(cxb); cxbar.addWidget(memb); cxbar.addStretch(1); cxl.addLayout(cxbar)
        self.interface_summary=QLabel("Inter-chain contacts are reported from explicit heavy-atom geometry. Membrane building uses OpenMM and assumes the input protein is already correctly oriented relative to the XY membrane plane."); self.interface_summary.setWordWrap(True); cxl.addWidget(self.interface_summary)
        self.interface_table=QTableWidget(0,5); self.interface_table.setHorizontalHeaderLabels(["Chain pair","Residue A","Residue B","Min distance (Å)","Atom contacts"]); self.interface_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.interface_table.verticalHeader().setVisible(False); self.interface_table.setEditTriggers(QAbstractItemView.NoEditTriggers); cxl.addWidget(self.interface_table,1)
        tabs.addTab(complex_tab,make_icon("interface"),"Complex"); self.complex_tab=complex_tab

        # Transparent structural geometry validation
        validation=QWidget(); vll=QVBoxLayout(validation); vll.setContentsMargins(8,8,8,8); vlbar=QHBoxLayout(); vlb=QPushButton(make_icon("validate"),"Run structural validation…"); vlb.clicked.connect(self.run_structural_validation); vlbar.addWidget(vlb); vlbar.addStretch(1); vll.addLayout(vlbar)
        self.validation_summary=QLabel("Geometry QC has not been run for the current structure."); self.validation_summary.setWordWrap(True); vll.addWidget(self.validation_summary)
        self.validation_views=QTabWidget(); self.validation_issues=QTableWidget(0,4); self.validation_issues.setHorizontalHeaderLabels(["Type","Location A","Location B / detail","Value"]); self.validation_issues.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.validation_issues.verticalHeader().setVisible(False); self.validation_issues.setEditTriggers(QAbstractItemView.NoEditTriggers); self.validation_views.addTab(self.validation_issues,"Issues")
        self.torsion_table=QTableWidget(0,4); self.torsion_table.setHorizontalHeaderLabels(["Residue","φ (deg)","ψ (deg)","ω→next (deg)"]); self.torsion_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.torsion_table.verticalHeader().setVisible(False); self.torsion_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.validation_views.addTab(self.torsion_table,"Backbone torsions"); vll.addWidget(self.validation_views,1)
        tabs.addTab(validation,make_icon("validate"),"Validate"); self.validation_tab=validation

        # Experimental/predicted or arbitrary structure comparison
        compare=QWidget(); cpl=QVBoxLayout(compare); cpl.setContentsMargins(8,8,8,8); cpbar=QHBoxLayout(); cpb=QPushButton(make_icon("compare"),"Compare / align structures…"); cpb.clicked.connect(self.compare_structures_dialog); cpc=QPushButton("Clear overlay"); cpc.clicked.connect(self.clear_structure_comparison); cpbar.addWidget(cpb); cpbar.addWidget(cpc); cpbar.addStretch(1); cpl.addLayout(cpbar)
        self.compare_summary=QLabel("Choose a second saved/built-in protein to sequence-align and Kabsch-superpose against the current chain."); self.compare_summary.setWordWrap(True); cpl.addWidget(self.compare_summary)
        self.compare_table=QTableWidget(0,3); self.compare_table.setHorizontalHeaderLabels(["Current residue","Comparison residue","Cα displacement (Å)"]); self.compare_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.compare_table.verticalHeader().setVisible(False); self.compare_table.setEditTriggers(QAbstractItemView.NoEditTriggers); cpl.addWidget(self.compare_table,1)
        tabs.addTab(compare,make_icon("compare"),"Compare"); self.compare_tab=compare

        # Environment: inputs only become physics when preparation/MD runs.
        env=QWidget(); ev=QHBoxLayout(env); ev.setContentsMargins(10,8,10,8); host=QWidget(); form=QFormLayout(host); self.temperature=QDoubleSpinBox(); self.temperature.setRange(1,2000); self.temperature.setValue(300); self.temperature.setSuffix(" K"); self.ph=QDoubleSpinBox(); self.ph.setRange(0,14); self.ph.setDecimals(2); self.ph.setValue(7); self.ionic=QDoubleSpinBox(); self.ionic.setRange(0,5); self.ionic.setDecimals(3); self.ionic.setValue(.15); self.ionic.setSuffix(" M"); self.pressure=QDoubleSpinBox(); self.pressure.setRange(.001,10000); self.pressure.setValue(1); self.pressure.setSuffix(" bar");
        for label,w in (("MD temperature",self.temperature),("Preparation pH",self.ph),("Preparation ionic strength",self.ionic),("NPT pressure",self.pressure)): form.addRow(label,w)
        ev.addWidget(host); sep=QFrame(); sep.setFrameShape(QFrame.VLine); ev.addWidget(sep); note=QLabel("These are experiment defaults, not decorative sliders. pH and ionic strength are applied when Prepare Simulation rebuilds chemistry; temperature is passed to the Langevin integrator; pressure is applied only in NPT through OpenMM's MonteCarloBarostat on an explicit periodic solvent system."); note.setWordWrap(True); note.setMaximumWidth(650); ev.addWidget(note,1)
        tabs.addTab(env,make_icon("environment"),"Environment"); self.environment_tab=env

        dock.setWidget(tabs); self.addDockWidget(Qt.BottomDockWidgetArea,dock); dock.setMinimumHeight(225); dock.resize(1000,300); self.experiment_dock=dock; dock.hide()

    def _show_experiment_tab(self, widget: QWidget) -> None:
        self.experiment_dock.show(); self.experiment_tabs.setCurrentWidget(widget); self.experiment_dock.raise_()

    # ---------- library ----------
    def _record_by_id(self, record_id: str) -> ProteinRecord | None:
        return next((r for r in [*self.builtins, *self.user_records] if r.id == record_id), None)

    def _load_first_available_builtin(self) -> None:
        for record in self.builtins:
            if record.file_path.exists():
                self.load_record(record)
                return
        self.statusBar().showMessage(
            "Built-in structures are unavailable. Use Import structure from the Toolbox or rerun the installer while online."
        )

    # ---------- structure loading ----------
    def load_record(self, record: ProteinRecord) -> None:
        try:
            pdb_path = pdb_path_for_vtk(record)
            info = inspect_structure(record)
            self.viewer.load_pdb(pdb_path, self.representation.currentText())
            self.viewer.set_atom_records(info.atom_records)
        except Exception as exc:
            QMessageBox.critical(self, "Could not load structure", str(exc))
            self.statusBar().showMessage(f"Load failed: {exc}")
            return

        self.current_record = record
        self.current_pdb_path = pdb_path
        self.current_atoms = info.atom_records
        self.measurement_atoms.clear()
        self.viewer.clear_selection_overlay()
        self.last_selected_atom = None

        self.name_label.setText(record.name)
        self.description_label.setText(record.description)
        origin_labels = {
            "builtin": "Built-in protein",
            "imported": "My Proteins — imported",
            "generated": "My Proteins — created peptide",
            "predicted": "My Proteins — predicted fold",
            "project": "My Proteins — project import",
            "prepared": "My Proteins — prepared",
            "minimized": "My Proteins — minimized",
            "dynamics": "My Proteins — molecular dynamics",
            "mutated": "My Proteins — mutant (unrelaxed)",
            "conformer": "My Proteins — sampled conformer",
        }
        evidence_labels = {
            "builtin": "archived structure coordinates; inspect source metadata",
            "imported": "imported coordinates; evidence class depends on source",
            "generated": "constructed starting geometry",
            "predicted": "structure prediction",
            "project": "project-imported coordinates; inspect original provenance",
            "prepared": "force-field-prepared molecular model",
            "minimized": "molecular-mechanics minimized model",
            "dynamics": "molecular-dynamics model result",
            "mutated": "template-built mutant; unrelaxed",
            "conformer": "sampled molecular-dynamics conformation",
        }
        self._set_info_rows([
            ("Source", origin_labels.get(record.origin, record.origin)),
            ("Evidence class", evidence_labels.get(record.origin, "model/source-specific coordinates")),
            ("PDB ID", record.pdb_id or "—"),
            ("Format", "PDB" if record.format == "pdb" else "PDBx/mmCIF"),
            ("Models", str(info.models)),
            ("Chains", str(info.chains)),
            ("Residues", str(info.residues)),
            ("Atoms", str(info.atoms)),
            ("Sequence length", str(info.sequence_length)),
        ])
        self.sequence_text.setPlainText(
            "\n\n".join(f"Chain {chain}\n{seq}" for chain, seq in info.sequences.items())
            or "No standard amino-acid sequence found."
        )
        metadata_text = "\n".join(f"{key}: {value}" for key, value in record.metadata.items())
        self.provenance_text.setPlainText(
            f"Name: {record.name}\n"
            f"Origin: {record.origin}\n"
            f"PDB ID: {record.pdb_id or 'local/generated file'}\n"
            f"Stored file: {record.file_path}\n"
            f"Rendered input: {pdb_path}\n"
            + (f"\nMetadata\n--------\n{metadata_text}\n" if metadata_text else "")
            + "\nRendering: native Python + VTK.\n"
            "Geometry measurements use the exact stored atomic coordinates.\n"
            "No molecular dynamics has been run unless a later simulation record explicitly says so."
        )
        self.selection_text.setPlainText("Click an atom in the 3D viewport to inspect it.")
        self._load_trajectory_for_current()
        perf = structure_advice(info.atoms)
        status = f"Loaded {record.name} — {info.chains} chain(s), {info.residues} residues, {info.atoms} atoms"
        if perf is not None:
            status += f" · Performance note: {perf.message}"
        self.statusBar().showMessage(status)

    def _set_info_rows(self, rows: list[tuple[str, str]]) -> None:
        self.info_table.setRowCount(len(rows))
        for row, (label, value) in enumerate(rows):
            self.info_table.setItem(row, 0, QTableWidgetItem(label))
            self.info_table.setItem(row, 1, QTableWidgetItem(value))

    def import_structure_dialog(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import Protein Structure",
            "",
            "Protein structures (*.pdb *.cif *.mmcif);;PDB files (*.pdb);;PDBx/mmCIF files (*.cif *.mmcif)",
        )
        if not filename:
            return
        try:
            record = import_structure(Path(filename))
            inspect_structure(record)
            self.user_records.insert(0, record)
            save_user_library(self.user_records)
            self._refresh_toolbox()
            self.load_record(record)
            append_entry(action="Import protein structure", protein_id=record.id, protein_name=record.name, method="Local structure import", parameters={"format": record.format}, results={"structure_file": str(record.file_path)})
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))

    def create_protein_dialog(self) -> None:
        dialog = CreateProteinDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        assert dialog.sequence is not None
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            record = build_peptide_structure(
                dialog.sequence,
                name=dialog.protein_name,
                source_kind=dialog.source_kind,
                starting_conformation=dialog.starting_conformation,
            )
            self.user_records.insert(0, record)
            save_user_library(self.user_records)
            self._refresh_toolbox()
            self.load_record(record)
            append_entry(
                action="Create peptide/protein starting structure", protein_id=record.id, protein_name=record.name,
                method="PeptideBuilder idealized geometry",
                parameters={"source": dialog.source_kind, "starting_geometry": dialog.starting_conformation, "sequence_length": len(dialog.sequence)},
                results={"structure_file": str(record.file_path)},
                notes="Initial geometry only; not a native-fold prediction.",
            )
            self.statusBar().showMessage(f"Created {record.name}. Initial peptide coordinates are displayed.")
        except Exception as exc:
            QMessageBox.critical(self, "Could not create protein", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        if dialog.auto_fold.isChecked():
            # Give the viewport a moment to visibly display the peptide strand first.
            QTimer.singleShot(850, lambda seq=dialog.sequence, nm=dialog.protein_name, src=record: self._start_fold_prediction(seq, nm, src))

    def _sequence_for_record(self, record: ProteinRecord) -> str:
        seq = record.metadata.get("amino_acid_sequence", "").strip().upper()
        if seq:
            return seq
        info = inspect_structure(record)
        if len(info.sequences) != 1:
            raise ValueError("Fold prediction currently requires one continuous protein chain. Select or create a single-chain protein.")
        return next(iter(info.sequences.values()))

    def predict_current_structure(self) -> None:
        if not self.current_record:
            QMessageBox.information(self, "Protein Lab", "Create or load a single-chain protein first.")
            return
        try:
            sequence = self._sequence_for_record(self.current_record)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot predict fold", str(exc)); return
        self._start_fold_prediction(sequence, self.current_record.name.replace(" — predicted fold", ""), self.current_record)

    def _start_fold_prediction(self, sequence: str, name: str, source_record: ProteinRecord) -> None:
        if self.fold_thread is not None and self.fold_thread.isRunning():
            self.statusBar().showMessage("A fold prediction is already running.")
            return
        self.statusBar().showMessage(f"Predicting folded 3D structure for {name} with ESMFold… the peptide strand remains visible while this runs.")
        self.fold_action.setEnabled(False)
        worker = FoldPredictionThread(sequence, name, source_record, self)
        self.fold_thread = worker
        worker.succeeded.connect(self._fold_prediction_succeeded)
        worker.failed.connect(self._fold_prediction_failed)
        worker.finished.connect(lambda: self.fold_action.setEnabled(True))
        worker.start()

    def _fold_prediction_succeeded(self, result: FoldPredictionResult) -> None:
        record = result.record
        self.user_records.insert(0, record); save_user_library(self.user_records); self._refresh_toolbox(); self.load_record(record)
        append_entry(
            action="Predict folded structure", protein_id=record.id, protein_name=record.name, method=result.method,
            parameters={"sequence_length": result.sequence_length, "service": "ESM Metagenomic Atlas"},
            results={"mean_pLDDT": result.mean_plddt if result.mean_plddt is not None else "not available", "structure_file": str(record.file_path)},
            notes="Predicted coordinates; not an experimental structure and not a time-resolved molecular-dynamics folding trajectory.",
        )
        confidence = f" Mean pLDDT: {result.mean_plddt:.1f}." if result.mean_plddt is not None else ""
        self.statusBar().showMessage(f"Predicted folded structure loaded.{confidence}")
        self.fold_thread = None

    def _fold_prediction_failed(self, message: str) -> None:
        self.fold_thread = None
        self.statusBar().showMessage("Automatic fold prediction failed; the constructed peptide strand was kept.")
        QMessageBox.warning(self, "Fold prediction unavailable", message + "\n\nThe locally constructed peptide remains in My Proteins. Protein Lab does not fabricate a folded structure when the prediction service fails.")

    def remove_current(self) -> None:
        record = self.current_record
        if not record or record.origin == "builtin":
            QMessageBox.information(self, "Protein Lab", "Select a protein from My Proteins before removing it.")
            return
        answer = QMessageBox.question(self, "Remove Protein", f"Remove '{record.name}' from My Proteins?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.user_records = remove_user_record(record, self.user_records)
        self.current_record = None
        self.current_pdb_path = None
        self.current_atoms = []
        self.viewer.clear()
        self._refresh_toolbox()
        self._load_first_available_builtin()

    # ---------- exact geometry measurements ----------
    def _measurement_required(self, kind: str) -> int:
        return {"Distance": 2, "Angle": 3, "Dihedral": 4}[kind]

    def _activate_measurement(self, kind: str) -> None:
        if not self.current_record:
            QMessageBox.information(self, "Protein Lab", "Load a protein before measuring geometry.")
            return
        self.measurement_kind = kind
        self.measurement_atoms.clear()
        self.viewer.clear_selection_overlay()
        self.viewer.set_picking_mode(True, crosshair=True)
        self._show_experiment_tab(self.measurements_tab)
        n = self._measurement_required(kind)
        self.measurement_equation.setText(f"{kind}: select {n} atoms in order.")
        self.measurement_detail.setPlainText("Click atoms directly in the 3D viewport. Drag still rotates the structure.")
        self.statusBar().showMessage(f"{kind} tool active — click {n} atoms in the viewport.")

    def _stop_measurement(self, *, clear: bool) -> None:
        self.measurement_kind = None
        self.measurement_atoms.clear()
        self.viewer.set_picking_mode(True, crosshair=False)
        if clear:
            self.viewer.clear_selection_overlay()

    def _atom_picked(self, atom: AtomRecord) -> None:
        self.last_selected_atom = atom
        self._show_atom_selection(atom)

        if self.measurement_kind is None:
            self.viewer.show_selected_atoms([atom], connect=False)
            return

        required = self._measurement_required(self.measurement_kind)
        if len(self.measurement_atoms) >= required:
            self.measurement_atoms.clear()
        self.measurement_atoms.append(atom)
        self.viewer.show_selected_atoms(self.measurement_atoms, connect=True)
        self.measurement_equation.setText(
            f"{self.measurement_kind}: selected {len(self.measurement_atoms)} / {required} atoms"
        )

        if len(self.measurement_atoms) == required:
            try:
                result = measure(self.measurement_kind, self.measurement_atoms)
            except Exception as exc:
                QMessageBox.warning(self, "Measurement failed", str(exc))
                return
            self._append_measurement(result)
            self.measurement_equation.setText(f"{result.kind}: {result.display_value}    |    {result.equation}")
            self.measurement_detail.setPlainText(
                "Selected atoms\n"
                + "\n".join(f"{i+1}. {a.label}   ({a.x:.4f}, {a.y:.4f}, {a.z:.4f}) Å" for i, a in enumerate(result.atoms))
                + "\n\nCalculation\n-----------\n"
                + result.calculation
            )
            self.statusBar().showMessage(f"{result.kind}: {result.display_value}")

    def _show_atom_selection(self, atom: AtomRecord) -> None:
        self.selection_text.setPlainText(
            f"Atom\n----\n"
            f"Label: {atom.label}\n"
            f"Element: {atom.element}\n"
            f"Atom name: {atom.atom_name}\n"
            f"Residue: {atom.residue_name} {atom.residue_number}\n"
            f"Chain: {atom.chain}\n"
            f"Model: {atom.model}\n\n"
            f"Coordinates (Å)\n---------------\n"
            f"x = {atom.x:.6f}\n"
            f"y = {atom.y:.6f}\n"
            f"z = {atom.z:.6f}\n\n"
            f"Occupancy: {atom.occupancy:.4f}\n"
            f"B factor: {atom.b_factor:.4f}\n"
            f"AltLoc: {atom.altloc or '—'}"
        )
        self.info_tabs.setCurrentWidget(self.selection_text)

    def _append_measurement(self, result: MeasurementResult) -> None:
        row = self.measurement_table.rowCount()
        self.measurement_table.insertRow(row)
        atoms = " → ".join(a.label for a in result.atoms)
        self.measurement_table.setItem(row, 0, QTableWidgetItem(result.kind))
        self.measurement_table.setItem(row, 1, QTableWidgetItem(result.display_value))
        self.measurement_table.setItem(row, 2, QTableWidgetItem(atoms))
        self.measurement_table.item(row, 0).setData(Qt.UserRole, result)
        self.measurement_table.selectRow(row)

    def _measurement_history_selected(self) -> None:
        row = self.measurement_table.currentRow()
        if row < 0:
            return
        item = self.measurement_table.item(row, 0)
        if not item:
            return
        result = item.data(Qt.UserRole)
        if not isinstance(result, MeasurementResult):
            return
        self.viewer.show_selected_atoms(list(result.atoms), connect=True)
        self.measurement_equation.setText(f"{result.kind}: {result.display_value}    |    {result.equation}")
        self.measurement_detail.setPlainText(
            "Selected atoms\n"
            + "\n".join(f"{i+1}. {a.label}" for i, a in enumerate(result.atoms))
            + "\n\nCalculation\n-----------\n"
            + result.calculation
        )

    def _clear_measurements(self) -> None:
        self.measurement_table.setRowCount(0)
        self.measurement_equation.setText("Choose Measure distance/angle/dihedral from the Toolbox.")
        self.measurement_detail.clear()
        self.measurement_atoms.clear()
        self.viewer.clear_selection_overlay()

    # ---------- strict OpenMM preparation ----------
    def prepare_simulation_dialog(self) -> None:
        if not self.current_record:
            QMessageBox.information(self, "Protein Lab", "Load a protein before preparing a simulation system.")
            return
        dialog = PrepareSimulationDialog(self, default_ph=self.ph.value(), default_ionic=self.ionic.value())
        if dialog.exec() != QDialog.Accepted:
            return

        options = PreparationOptions(
            ph=dialog.ph.value(),
            remove_heterogens=dialog.remove_heterogens.isChecked(),
            solvate=dialog.solvate.isChecked(),
            padding_nm=dialog.padding.value(),
            ionic_strength_m=dialog.ionic.value(),
            forcefield_key=str(dialog.forcefield.currentData()),
        )
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            result = prepare_simulation_system(self.current_record, options)
            self.user_records.insert(0, result.record)
            save_user_library(self.user_records)
            self._refresh_toolbox()
            self.load_record(result.record)
            append_entry(
                action="Prepare simulation system", protein_id=result.record.id, protein_name=result.record.name, method="OpenMM Modeller + force-field validation",
                parameters={"pH": options.ph, "remove_heterogens": options.remove_heterogens, "solvate": options.solvate, "padding_nm": options.padding_nm, "ionic_strength_M": options.ionic_strength_m, "forcefield": options.forcefield_key},
                results={"original_atoms": result.original_atoms, "prepared_atoms": result.prepared_atoms, "particles": result.particles, "removed_residues": result.removed_residues},
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Simulation preparation failed",
                str(exc)
                + "\n\nProtein Lab intentionally stops here instead of guessing missing chemistry or force-field parameters.",
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        QMessageBox.information(
            self,
            "Preparation complete",
            f"Prepared structure saved to My Proteins.\n\n"
            f"Original atoms: {result.original_atoms}\n"
            f"Prepared atoms: {result.prepared_atoms}\n"
            f"Force-field particles: {result.particles}\n"
            f"Residues removed during cleanup: {result.removed_residues}\n\n"
            "No minimization or molecular dynamics was run in this phase.",
        )

    # ---------- Phases 8-10: real OpenMM energy, minimization, MD ----------
    def _require_simulation_ready(self) -> bool:
        if not self.current_record:
            QMessageBox.information(self, "Protein Lab", "Load a protein first.")
            return False
        if is_simulation_ready(self.current_record):
            return True
        answer = QMessageBox.question(
            self,
            "Prepare simulation first",
            "This operation needs a force-field-prepared structure. Prepare the current protein now?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.prepare_simulation_dialog()
        return False

    def evaluate_current_energy(self) -> None:
        if not self._require_simulation_ready():
            return
        assert self.current_record is not None
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            result = evaluate_energy(self.current_record)
        except Exception as exc:
            QMessageBox.critical(self, "Energy evaluation failed", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.energy_table.setRowCount(0)
        total_row = self.energy_table.rowCount(); self.energy_table.insertRow(total_row)
        total_label = QTableWidgetItem("TOTAL POTENTIAL"); tf=total_label.font(); tf.setBold(True); total_label.setFont(tf)
        total_value = QTableWidgetItem(f"{result.total_kj_mol:.6f}"); vf=total_value.font(); vf.setBold(True); total_value.setFont(vf)
        self.energy_table.setItem(total_row,0,total_label); self.energy_table.setItem(total_row,1,total_value); self.energy_table.setItem(total_row,2,QTableWidgetItem("OpenMM Context"))
        for term in result.terms:
            row=self.energy_table.rowCount(); self.energy_table.insertRow(row)
            name=QTableWidgetItem(term.name); name.setData(Qt.UserRole, term)
            self.energy_table.setItem(row,0,name); self.energy_table.setItem(row,1,QTableWidgetItem(f"{term.energy_kj_mol:.6f}")); self.energy_table.setItem(row,2,QTableWidgetItem(term.force_class))
        self.energy_summary.setText(
            f"Total potential: {result.total_kj_mol:.6f} kJ/mol   ·   RMS force: {result.rms_force_kj_mol_nm:.6f} kJ/mol/nm   ·   {result.nonbonded_method}"
        )
        self.energy_detail.setPlainText(
            "Method\n------\n"
            f"Force field: {result.forcefield}\n"
            f"Atoms: {result.atom_count}\n"
            f"Nonbonded method: {result.nonbonded_method}\n\n"
            "The table is decomposed by actual OpenMM Force groups. NonbondedForce combines Coulomb/electrostatic and Lennard-Jones terms, so Protein Lab does not fabricate separate numeric values for them."
        )
        self._show_experiment_tab(self.energy_tab)
        self.statusBar().showMessage(f"Potential energy: {result.total_kj_mol:.6f} kJ/mol")
        append_entry(action="Evaluate force-field energy", protein_id=self.current_record.id, protein_name=self.current_record.name, method=f"OpenMM {result.forcefield}", parameters={"nonbonded_method": result.nonbonded_method}, results={"potential_kJ_mol": result.total_kj_mol, "rms_force_kJ_mol_nm": result.rms_force_kj_mol_nm})

    def _energy_term_selected(self) -> None:
        row=self.energy_table.currentRow()
        if row < 0: return
        item=self.energy_table.item(row,0)
        if not item: return
        term=item.data(Qt.UserRole)
        if term is None: return
        self.energy_detail.setPlainText(
            f"{term.name}\n{'='*len(term.name)}\n"
            f"OpenMM class: {term.force_class}\n"
            f"Energy: {term.energy_kj_mol:.8f} kJ/mol\n\n"
            f"Equation / mathematical form\n----------------------------\n{term.equation}\n\n"
            f"Interpretation\n--------------\n{term.explanation}\n\n"
            "The displayed energy is queried from the OpenMM Context for this force group; the equation is the corresponding standard force form used by the configured molecular-mechanics model."
        )

    def minimize_current_structure(self) -> None:
        if not self._require_simulation_ready(): return
        assert self.current_record is not None
        dialog=MinimizeDialog(self)
        if dialog.exec()!=QDialog.Accepted: return
        options=MinimizationOptions(tolerance_kj_mol_nm=dialog.tolerance.value(), max_iterations=dialog.max_iterations.value())
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            result=minimize_structure(self.current_record, options)
            self.user_records.insert(0,result.record); save_user_library(self.user_records); self._refresh_toolbox(); self.load_record(result.record)
            append_entry(action="Energy minimization", protein_id=result.record.id, protein_name=result.record.name, method="OpenMM LocalEnergyMinimizer (L-BFGS)", parameters={"tolerance_kJ_mol_nm": options.tolerance_kj_mol_nm, "max_iterations": options.max_iterations}, results={"energy_before_kJ_mol": result.energy_before_kj_mol, "energy_after_kJ_mol": result.energy_after_kj_mol, "rms_force_before": result.rms_force_before, "rms_force_after": result.rms_force_after})
        except Exception as exc:
            QMessageBox.critical(self,"Energy minimization failed",str(exc)); return
        finally:
            QApplication.restoreOverrideCursor()
        self._show_experiment_tab(self.energy_tab)
        self.energy_summary.setText(
            f"Minimization complete: {result.energy_before_kj_mol:.6f} → {result.energy_after_kj_mol:.6f} kJ/mol; RMS force {result.rms_force_before:.6f} → {result.rms_force_after:.6f} kJ/mol/nm."
        )
        QMessageBox.information(
            self,"Minimization complete",
            f"Saved as: {result.record.name}\n\nPotential energy: {result.energy_before_kj_mol:.6f} → {result.energy_after_kj_mol:.6f} kJ/mol\n"
            f"RMS force: {result.rms_force_before:.6f} → {result.rms_force_after:.6f} kJ/mol/nm\n\nThe original structure was not overwritten."
        )

    def run_md_dialog(self) -> None:
        if not self._require_simulation_ready(): return
        assert self.current_record is not None
        dialog=MolecularDynamicsDialog(self, default_temperature=self.temperature.value(), default_pressure=self.pressure.value())
        if dialog.exec()!=QDialog.Accepted: return
        options=MDOptions(
            temperature_k=dialog.temperature.value(), friction_per_ps=dialog.friction.value(), timestep_fs=dialog.timestep.value(),
            steps=dialog.steps.value(), report_interval=dialog.report_interval.value(), random_seed=dialog.seed.value(),
            minimize_before=dialog.minimize_first.isChecked(), ensemble=dialog.ensemble.currentText(),
            pressure_bar=dialog.pressure.value(), barostat_interval=dialog.barostat_interval.value(),
        )
        self.temperature.setValue(options.temperature_k); self.pressure.setValue(options.pressure_bar)
        self.md_table.setRowCount(0)
        progress_dialog=QProgressDialog("Running real OpenMM molecular dynamics…", "Cancel", 0, options.steps, self)
        progress_dialog.setWindowTitle("Molecular Dynamics"); progress_dialog.setMinimumDuration(0); progress_dialog.setValue(0)

        def on_progress(done: int, total: int, sample) -> None:
            progress_dialog.setMaximum(total); progress_dialog.setValue(done)
            if sample is not None:
                row=self.md_table.rowCount(); self.md_table.insertRow(row)
                for col,text in enumerate((str(sample.step),f"{sample.time_ps:.6f}",f"{sample.potential_kj_mol:.6f}",f"{sample.kinetic_kj_mol:.6f}",f"{sample.total_kj_mol:.6f}")):
                    self.md_table.setItem(row,col,QTableWidgetItem(text))
                self.md_table.scrollToBottom()
                self.md_status.setText(f"Running: step {done}/{total} · {sample.time_ps:.6f} ps · potential {sample.potential_kj_mol:.3f} kJ/mol")
            QApplication.processEvents()

        self._show_experiment_tab(self.dynamics_tab)
        try:
            result=run_molecular_dynamics(self.current_record, options, progress=on_progress, cancelled=progress_dialog.wasCanceled)
            self.user_records.insert(0,result.record); save_user_library(self.user_records); self._refresh_toolbox(); self.load_record(result.record)
            append_entry(action="Molecular dynamics", protein_id=result.record.id, protein_name=result.record.name, method="OpenMM LangevinMiddleIntegrator", parameters={"ensemble": options.ensemble, "temperature_K": options.temperature_k, "pressure_bar": options.pressure_bar if options.ensemble == "NPT" else "n/a", "friction_ps^-1": options.friction_per_ps, "timestep_fs": options.timestep_fs, "steps": options.steps, "seed": options.random_seed}, results={"frames": result.frame_count, "simulated_time_ps": result.simulated_time_ps, "platform": result.platform, "trajectory": result.trajectory_path})
            self._show_experiment_tab(self.trajectory_tab)
        except Exception as exc:
            if "cancelled" in str(exc).lower():
                QMessageBox.information(self,"Molecular dynamics cancelled",str(exc))
            else:
                QMessageBox.critical(self,"Molecular dynamics failed",str(exc))
            return
        finally:
            progress_dialog.close()
        self.md_status.setText(
            f"Completed {result.ensemble} {result.steps} steps = {result.simulated_time_ps:g} ps at {result.temperature_k:g} K · {result.frame_count} stored frames · platform {result.platform}"
        )
        QMessageBox.information(
            self,"Molecular dynamics complete",
            f"Real OpenMM {result.ensemble} dynamics completed.\n\nSimulated time: {result.simulated_time_ps:g} ps\nSteps: {result.steps}\nTimestep: {result.timestep_fs:g} fs\nStored frames: {result.frame_count}\nDCD: {result.dcd_path}\nPlatform: {result.platform}\n\nFinal coordinates and the full trajectory were saved. The original was not overwritten."
        )

    # ---------- Phases 11-14: trajectories, RMSD/RMSF, mutation, environment ----------
    def _load_trajectory_for_current(self) -> None:
        self.trajectory_timer.stop()
        self.traj_play.setText("Play")
        self.trajectory_data = None
        self.trajectory_frame = 0
        if not self.current_record or trajectory_path_for_record(self.current_record) is None:
            self.traj_slider.blockSignals(True); self.traj_slider.setRange(0,0); self.traj_slider.setValue(0); self.traj_slider.blockSignals(False)
            self.traj_label.setText("No trajectory attached")
            self.traj_energy_plot.clear()
            return
        try:
            self.trajectory_data = load_trajectory(self.current_record)
        except Exception as exc:
            self.traj_label.setText(f"Trajectory unavailable: {exc}")
            return
        t=self.trajectory_data
        self.traj_slider.blockSignals(True); self.traj_slider.setRange(0,max(0,t.frame_count-1)); self.traj_slider.setValue(0); self.traj_slider.blockSignals(False)
        self.traj_energy_plot.set_series(t.times_ps,t.potential_kj_mol,title="Potential energy through stored MD frames",x_label="Time (ps)",y_label="Potential (kJ/mol)")
        self._update_trajectory_label()
        perf = trajectory_advice(t.frame_count, t.atom_count)
        if perf is not None:
            self.statusBar().showMessage(perf.message)

    def open_trajectory_panel(self) -> None:
        if not self.current_record or trajectory_path_for_record(self.current_record) is None:
            QMessageBox.information(self,"Trajectory Playback","Load a Protein Lab molecular-dynamics result first. New MD runs store playback frames automatically."); return
        if self.trajectory_data is None: self._load_trajectory_for_current()
        self._show_experiment_tab(self.trajectory_tab)

    def _update_trajectory_label(self) -> None:
        if self.trajectory_data is None: self.traj_label.setText("No trajectory loaded"); return
        i=self.trajectory_frame; t=self.trajectory_data
        self.traj_label.setText(f"Frame {i+1}/{t.frame_count} · step {int(t.steps[i])} · {t.times_ps[i]:.4g} ps")

    def _show_trajectory_frame(self,index:int) -> None:
        if self.trajectory_data is None or not self.current_record: return
        index=max(0,min(int(index),self.trajectory_data.frame_count-1)); self.trajectory_frame=index
        try:
            frame_path=write_trajectory_frame(self.current_record,self.trajectory_data,index)
            self.viewer.load_trajectory_frame(frame_path)
            frame_record=ProteinRecord(id="trajectory-frame",name=self.current_record.name,path=str(frame_path),format="pdb",origin=self.current_record.origin)
            info=inspect_structure(frame_record); self.current_atoms=info.atom_records; self.viewer.set_atom_records(self.current_atoms); self.viewer.clear_selection_overlay()
        except Exception as exc:
            self.trajectory_timer.stop(); QMessageBox.warning(self,"Trajectory frame error",str(exc)); return
        self.traj_slider.blockSignals(True); self.traj_slider.setValue(index); self.traj_slider.blockSignals(False); self._update_trajectory_label()

    def _trajectory_slider_changed(self,value:int) -> None:
        self._show_trajectory_frame(value)

    def _step_trajectory(self,delta:int) -> None:
        if self.trajectory_data is None: self.open_trajectory_panel(); return
        self._show_trajectory_frame(self.trajectory_frame+delta)

    def _toggle_trajectory_playback(self) -> None:
        if self.trajectory_data is None: self.open_trajectory_panel(); return
        if self.trajectory_timer.isActive(): self.trajectory_timer.stop(); self.traj_play.setText("Play")
        else: self.trajectory_timer.start(); self.traj_play.setText("Pause")

    def _trajectory_tick(self) -> None:
        if self.trajectory_data is None: self.trajectory_timer.stop(); return
        nxt=self.trajectory_frame+1
        if nxt>=self.trajectory_data.frame_count: nxt=0
        self._show_trajectory_frame(nxt)

    def calculate_rmsd(self) -> None:
        if not self.current_record or trajectory_path_for_record(self.current_record) is None:
            QMessageBox.information(self,"RMSD","Load a Protein Lab MD result containing a trajectory first."); return
        try:
            if self.trajectory_data is None: self.trajectory_data=load_trajectory(self.current_record)
            result=compute_rmsd(self.current_record,self.trajectory_data,selection="Cα atoms",reference_frame=0)
        except Exception as exc:
            QMessageBox.critical(self,"RMSD failed",str(exc)); return
        t=self.trajectory_data
        self.analysis_plot.set_series(t.times_ps,result.values_angstrom,title="Cα RMSD vs first stored frame",x_label="Time (ps)",y_label="RMSD (Å)")
        self.analysis_detail.setPlainText(
            "RMSD — Cα atoms\n================\n"
            "Each frame is least-squares superposed onto frame 0 with the Kabsch algorithm before RMSD is calculated.\n\n"
            "RMSD(t) = sqrt[(1/N) Σ_i || R x_i(t) − x_i(ref) ||²]\n\n"
            f"Atoms: {len(result.atom_indices)}\nFrames: {len(result.values_angstrom)}\n"
            f"Minimum: {result.values_angstrom.min():.5f} Å\nMaximum: {result.values_angstrom.max():.5f} Å\nMean: {result.values_angstrom.mean():.5f} Å\n\n"
            "R removes global translation/rotation; the remaining deviation therefore reports structural coordinate change for the selected atoms."
        ); self._show_experiment_tab(self.analysis_tab)

    def calculate_rmsf(self) -> None:
        if not self.current_record or trajectory_path_for_record(self.current_record) is None:
            QMessageBox.information(self,"RMSF","Load a Protein Lab MD result containing a trajectory first."); return
        try:
            if self.trajectory_data is None: self.trajectory_data=load_trajectory(self.current_record)
            result=compute_rmsf(self.current_record,self.trajectory_data,selection="Cα atoms",reference_frame=0)
        except Exception as exc:
            QMessageBox.critical(self,"RMSF failed",str(exc)); return
        x=list(range(1,len(result.values_angstrom)+1)); self.analysis_plot.set_series(x,result.values_angstrom,title="Cα RMSF by residue",x_label="Selected residue index",y_label="RMSF (Å)")
        largest=sorted(zip(result.values_angstrom,result.labels),reverse=True)[:10]
        self.analysis_detail.setPlainText(
            "RMSF — Cα atoms\n================\n"
            "Frames are first Kabsch-aligned to remove global rigid-body motion. Fluctuation is then measured around each atom's time-averaged position.\n\n"
            "RMSF_i = sqrt[(1/T) Σ_t || x_i(t) − <x_i> ||²]\n\n"
            f"Residues/Cα atoms: {len(result.values_angstrom)}\nMean RMSF: {result.values_angstrom.mean():.5f} Å\nMaximum RMSF: {result.values_angstrom.max():.5f} Å\n\nMost mobile selected residues\n-----------------------------\n"
            + "\n".join(f"{label}: {value:.5f} Å" for value,label in largest)
        ); self._show_experiment_tab(self.analysis_tab)

    def mutate_current_residue(self) -> None:
        if not self.current_record:
            QMessageBox.information(self,"Mutate Residue","Load a protein first."); return
        seen=set(); residues=[]
        for a in self.current_atoms:
            key=(a.chain,a.residue_number,a.residue_name)
            if a.residue_name in {"ALA","ARG","ASN","ASP","CYS","GLN","GLU","GLY","HIS","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL"} and key not in seen:
                seen.add(key); residues.append(key)
        if not residues:
            QMessageBox.information(self,"Mutate Residue","No standard amino-acid residues were found."); return
        selected=(self.last_selected_atom.chain,self.last_selected_atom.residue_number) if self.last_selected_atom else None
        dialog=MutationDialog(residues,self,selected=selected,default_ph=self.ph.value())
        if dialog.exec()!=QDialog.Accepted: return
        chain,number,_old=dialog.residue_data
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor); result=mutate_residue(self.current_record,chain_id=chain,residue_number=number,target_residue=dialog.target_code,ph=dialog.ph.value())
            self.user_records.insert(0,result.record); save_user_library(self.user_records); self.load_record(result.record)
        except Exception as exc:
            QMessageBox.critical(self,"Mutation failed",str(exc)); return
        finally: QApplication.restoreOverrideCursor()
        QMessageBox.information(self,"Mutant created",f"Created {result.original_residue}{result.residue_number}{result.target_residue} in chain {result.chain}.\n\nThe new side-chain geometry comes from PDBFixer templates and is marked UNRELAXED. Prepare and minimize it before interpreting local structure or running MD.")

    def open_environment_panel(self) -> None:
        self._show_experiment_tab(self.environment_tab)
        self.statusBar().showMessage("Environment defaults: pH/ionic strength apply during preparation; temperature/pressure apply during MD.")

    # ---------- Phases 15-17: conformational sampling, landscapes, residue networks ----------
    def run_conformational_explorer(self) -> None:
        if not self._require_simulation_ready():
            return
        assert self.current_record is not None
        dialog=ConformationalExplorerDialog(self,default_temperature=self.temperature.value())
        if dialog.exec()!=QDialog.Accepted:
            return
        if dialog.high_temp.value() < dialog.target_temp.value():
            QMessageBox.warning(self,"Conformational Explorer","High temperature must be greater than or equal to target temperature."); return
        options=ConformationalOptions(
            target_temperature_k=dialog.target_temp.value(), high_temperature_k=dialog.high_temp.value(),
            replicas=dialog.replicas.value(), cycles=dialog.cycles.value(), temperature_points_per_leg=dialog.points.value(),
            steps_per_temperature=dialog.steps_per_temp.value(), timestep_fs=dialog.timestep.value(), friction_per_ps=dialog.friction.value(),
            random_seed=dialog.seed.value(), minimize_before=dialog.minimize_first.isChecked(),
        )
        total_stages=options.replicas*options.cycles*(options.temperature_points_per_leg*2-1)
        pd=QProgressDialog("Running real OpenMM conformational exploration…","Cancel",0,total_stages,self); pd.setWindowModality(Qt.WindowModal); pd.setMinimumDuration(0); pd.setValue(0)
        cancelled=lambda: pd.wasCanceled()
        def progress(done,total,sample):
            pd.setMaximum(total); pd.setValue(done)
            if sample is not None:
                pd.setLabelText(f"Replica {sample.replica}/{options.replicas} · cycle {sample.cycle}/{options.cycles} · T={sample.temperature_k:g} K · U={sample.potential_kj_mol:.4g} kJ/mol")
            QApplication.processEvents()
        try:
            result=run_conformational_exploration(self.current_record,options,progress=progress,cancelled=cancelled)
        except Exception as exc:
            pd.close()
            if "cancelled" not in str(exc).lower(): QMessageBox.critical(self,"Conformational exploration failed",str(exc))
            return
        finally:
            pd.close()
        self.user_records.insert(0,result.record); save_user_library(self.user_records); self.load_record(result.record)
        x=list(range(1,len(result.samples)+1)); y=[sample.potential_kj_mol for sample in result.samples]
        self.explore_plot.set_series(x,y,title="Potential energy across heating/cooling samples",x_label="Stored sample",y_label="Potential (kJ/mol)")
        self.explore_detail.setPlainText(
            "Conformational Explorer\n=======================\n"
            "Protocol: independent OpenMM Langevin-middle heating/cooling replicas. The integrator heat-bath temperature is explicitly changed at each stage.\n\n"
            f"Replicas: {options.replicas}\nCycles/replica: {options.cycles}\nTemperature range: {options.target_temperature_k:g}–{options.high_temperature_k:g} K\n"
            f"Total integration steps: {result.total_steps:,}\nStored samples: {len(result.samples)}\nLowest sampled potential: {result.lowest_energy_kj_mol:.6g} kJ/mol\nPlatform: {result.platform}\n\n"
            "SCIENTIFIC LIMIT: this is non-equilibrium conformational sampling. The lowest-energy snapshot is not automatically the global minimum or the native fold, and these changing-temperature samples are not used for equilibrium free-energy estimation."
        ); self._show_experiment_tab(self.explore_tab)

    def calculate_free_energy_landscape(self) -> None:
        if not self.current_record or trajectory_path_for_record(self.current_record) is None:
            QMessageBox.information(self,"Free-Energy Landscape","Load a Protein Lab molecular-dynamics result with a stored trajectory first."); return
        if self.current_record.metadata.get("conformational_exploration","").lower()=="true":
            QMessageBox.warning(self,"Free-Energy Landscape","Changing-temperature conformational-exploration samples are non-equilibrium and are intentionally excluded from this calculation."); return
        try:
            if self.trajectory_data is None: self.trajectory_data=load_trajectory(self.current_record)
            default_t=float(self.current_record.metadata.get("temperature_K", self.temperature.value()))
        except Exception as exc:
            QMessageBox.critical(self,"Trajectory unavailable",str(exc)); return
        dialog=FreeEnergyLandscapeDialog(self,default_temperature=default_t)
        if dialog.exec()!=QDialog.Accepted: return
        try:
            result=compute_free_energy_landscape(self.current_record,self.trajectory_data,temperature_k=dialog.temperature.value(),bins=dialog.bins.value())
        except Exception as exc:
            QMessageBox.critical(self,"Landscape calculation failed",str(exc)); return
        self.landscape_heatmap.set_data(result.rmsd_centers_angstrom,result.rg_centers_angstrom,result.free_energy_kj_mol,title="Occupancy-derived apparent free-energy surface",x_label="Cα RMSD (Å)",y_label="Protein Rg (Å)",legend="ΔF (kJ/mol)")
        finite=result.free_energy_kj_mol[~__import__('numpy').isnan(result.free_energy_kj_mol)]
        maxf=float(finite.max()) if len(finite) else 0.0
        self.landscape_detail.setPlainText(
            "Free-Energy Landscape\n=====================\n"
            "Collective variables: Cα Kabsch-aligned RMSD to the first stored frame and mass-weighted protein-heavy-atom radius of gyration.\n\n"
            "P(x,y) = n(x,y) / N\nF(x,y) = −RT ln[P(x,y)/Pmax]\n\n"
            f"Temperature: {result.temperature_k:g} K\nBins/axis: {result.bins}\nFrames: {self.trajectory_data.frame_count}\nLargest finite relative value: {maxf:.6g} kJ/mol\nSaved data: {result.output_npz}\n\n"
            "INTERPRETATION: this is an occupancy-derived estimate. It approaches a thermodynamic free-energy surface only if the trajectory adequately samples the equilibrium distribution at the stated temperature. A short MD run can look smooth and still be unconverged."
        ); self._show_experiment_tab(self.landscape_tab)

    def build_contact_network(self) -> None:
        if not self.current_record:
            QMessageBox.information(self,"Residue Interaction Network","Load a protein first."); return
        traj=None
        if trajectory_path_for_record(self.current_record) is not None:
            try:
                traj=self.trajectory_data or load_trajectory(self.current_record)
                self.trajectory_data=traj
            except Exception:
                traj=None
        dialog=ContactNetworkDialog(self,has_trajectory=traj is not None)
        if dialog.exec()!=QDialog.Accepted: return
        try:
            result=compute_residue_contact_network(self.current_record,traj,threshold_angstrom=dialog.threshold.value(),minimum_occupancy=dialog.occupancy.value()/100.0,exclude_adjacent=dialog.exclude_adjacent.isChecked())
        except Exception as exc:
            QMessageBox.critical(self,"Network calculation failed",str(exc)); return
        self.network_table.setRowCount(len(result.edges))
        for row,e in enumerate(result.edges):
            for col,val in enumerate((e.residue_a,e.residue_b,f"{100*e.occupancy:.1f}%",f"{e.mean_distance_angstrom:.3f}",f"{e.minimum_distance_angstrom:.3f}")):
                self.network_table.setItem(row,col,QTableWidgetItem(val))
        hubs=sorted(result.weighted_degree.items(),key=lambda kv:(-kv[1],kv[0]))[:12]
        self.network_detail.setPlainText(
            "Residue Interaction Network\n===========================\n"
            "Node = standard amino-acid residue. Representative coordinate = Cβ; glycine/fallback = Cα.\n"
            "Edge = representative distance ≤ threshold. Trajectory occupancy = frames satisfying that criterion / total frames.\n\n"
            f"Threshold: {result.threshold_angstrom:g} Å\nMinimum occupancy: {100*result.minimum_occupancy:g}%\nFrames analyzed: {result.frames}\nNodes: {result.node_count}\nEdges retained: {len(result.edges)}\nCSV: {result.output_csv}\n\nTop weighted-degree residues\n----------------------------\n"
            + ("\n".join(f"{label}: weighted degree {value:.3f} · degree {result.degree[label]}" for label,value in hubs) if hubs else "No edges passed the selected criterion.")
            + "\n\nThe distance threshold defines a structural graph; it is not itself an interaction energy or proof of biochemical coupling."
        ); self._show_experiment_tab(self.network_tab)

    # ---------- Phases 18-21: ligands, complexes/membranes, validation, comparison ----------
    def analyze_ligand_pocket(self) -> None:
        if not self.current_record:
            QMessageBox.information(self,"Ligands & Binding Pockets","Load a protein structure first."); return
        try:
            components=list_nonprotein_components(self.current_record)
        except Exception as exc:
            QMessageBox.critical(self,"Component analysis failed",str(exc)); return
        self.ligand_table.setRowCount(len(components))
        for row,c in enumerate(components):
            for col,value in enumerate((c.label,c.category,str(c.atoms),str(c.heavy_atoms))): self.ligand_table.setItem(row,col,QTableWidgetItem(value))
        if not components:
            self.pocket_table.setRowCount(0)
            self.ligand_summary.setText("No non-water, non-standard-amino-acid components were found in the current structure.")
            self._show_experiment_tab(self.ligand_tab); return
        dialog=LigandPocketDialog(components,self)
        if dialog.exec()!=QDialog.Accepted: return
        try:
            result=analyze_binding_pocket(self.current_record,dialog.component_key,cutoff_angstrom=dialog.cutoff.value())
        except Exception as exc:
            QMessageBox.critical(self,"Pocket analysis failed",str(exc)); return
        self.pocket_table.setRowCount(len(result.residues))
        for row,r in enumerate(result.residues):
            for col,value in enumerate((r.residue,f"{r.minimum_distance_angstrom:.3f}",str(r.contacting_atom_pairs))): self.pocket_table.setItem(row,col,QTableWidgetItem(value))
        self.ligand_summary.setText(
            f"{result.ligand.label} · {result.ligand.category} · pocket cutoff {result.cutoff_angstrom:g} Å · "
            f"{len(result.residues)} protein residues contacted. Criterion: min(i∈residue,j∈ligand) ||r_i−r_j|| ≤ r_cut. "
            "This is a geometric heavy-atom neighborhood, not a binding-energy estimate."
        )
        pocket_keys={(r.chain,r.residue_number) for r in result.residues}
        highlight=[]
        for a in self.current_atoms:
            if a.chain==result.ligand.chain and a.residue_name==result.ligand.residue_name and a.residue_number==result.ligand.residue_number and a.element.upper()!="H": highlight.append(a)
            elif (a.chain,a.residue_number) in pocket_keys and a.atom_name.upper()=="CA": highlight.append(a)
        self.viewer.show_selected_atoms(highlight[:300],connect=False)
        self._show_experiment_tab(self.ligand_tab)

    def analyze_complex_interfaces(self) -> None:
        if not self.current_record:
            QMessageBox.information(self,"Complex Interfaces","Load a protein structure first."); return
        dialog=InterfaceAnalysisDialog(self)
        if dialog.exec()!=QDialog.Accepted: return
        try:
            result=analyze_chain_interfaces(self.current_record,cutoff_angstrom=dialog.cutoff.value())
        except Exception as exc:
            QMessageBox.critical(self,"Interface analysis failed",str(exc)); return
        self.interface_table.setRowCount(len(result.contacts))
        for row,c in enumerate(result.contacts):
            for col,value in enumerate((f"{c.chain_a}–{c.chain_b}",c.residue_a,c.residue_b,f"{c.minimum_distance_angstrom:.3f}",str(c.atom_contacts))): self.interface_table.setItem(row,col,QTableWidgetItem(value))
        pair_text=", ".join(f"{pair}: {count} residue-pair contacts" for pair,count in sorted(result.chain_pairs.items())) or "No chain-pair contacts"
        residue_counts=", ".join(f"chain {ch}: {len(vals)} interface residues" for ch,vals in sorted(result.interface_residues.items()))
        self.interface_summary.setText(
            f"Heavy-atom cutoff {result.cutoff_angstrom:g} Å · {len(result.contacts)} residue-pair contacts. {pair_text}. "
            + (residue_counts if residue_counts else "No interface residues met the criterion.")
            + " Edge criterion: min(i∈residue A,j∈residue B) ||r_i−r_j|| ≤ r_cut. Distance contacts are structural criteria, not binding free energies."
        )
        interface_keys=set()
        for vals in result.interface_residues.values():
            for label in vals:
                try:
                    chain,rest=label.split(":",1)
                    number="".join(ch for ch in rest if ch.isdigit() or ch in "-.")
                    interface_keys.add((chain,number))
                except Exception: pass
        # Highlight interface Cα atoms without connecting unrelated chains.
        atoms=[a for a in self.current_atoms if a.atom_name.upper()=="CA" and any(a.label.startswith(lbl.split(":",1)[0]+":") and f"{a.residue_name}{a.residue_number}"==lbl.split(":",1)[1] for vals in result.interface_residues.values() for lbl in vals)]
        self.viewer.show_selected_atoms(atoms[:400],connect=False)
        self._show_experiment_tab(self.complex_tab)

    def prepare_membrane_dialog(self) -> None:
        if not self.current_record:
            QMessageBox.information(self,"Build Membrane System","Load a protein structure first."); return
        dialog=MembranePreparationDialog(self,default_ph=self.ph.value(),default_ionic=self.ionic.value())
        if dialog.exec()!=QDialog.Accepted: return
        options=MembranePreparationOptions(
            lipid_type=dialog.lipid.currentText(), minimum_padding_nm=dialog.padding.value(), ionic_strength_m=dialog.ionic.value(),
            ph=dialog.ph.value(), remove_heterogens=dialog.remove_heterogens.isChecked(),
        )
        answer=QMessageBox.question(self,"Confirm membrane orientation",
            "Protein Lab will preserve the current coordinates and ask OpenMM to build the membrane in the XY plane with its normal along Z.\n\n"
            "Continue only if the protein is already oriented/positioned appropriately for a membrane system.")
        if answer!=QMessageBox.StandardButton.Yes: return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            result=prepare_membrane_system(self.current_record,options)
            self.user_records.insert(0,result.record); save_user_library(self.user_records); self.load_record(result.record)
        except Exception as exc:
            QMessageBox.critical(self,"Membrane construction failed",str(exc)+"\n\nProtein Lab stops instead of inventing missing lipid/protein parameters."); return
        finally:
            QApplication.restoreOverrideCursor()
        self._show_experiment_tab(self.complex_tab)
        self.interface_summary.setText(
            f"Built explicit {options.lipid_type} membrane system: {result.atoms:,} atoms · {result.residues:,} residues · "
            f"{result.lipid_residues:,} lipid residues · {result.water_residues:,} waters · {result.particles:,} validated force-field particles."
        )
        QMessageBox.information(self,"Membrane system complete",
            f"Saved to My Proteins as:\n{result.record.name}\n\nAtoms: {result.atoms:,}\nLipids: {result.lipid_residues:,}\nWaters: {result.water_residues:,}\n"
            "The system is periodic and simulation-ready with the membrane-specific force-field preset recorded in provenance.")

    def run_structural_validation(self) -> None:
        if not self.current_record:
            QMessageBox.information(self,"Structural Validation","Load a protein structure first."); return
        dialog=ValidationDialog(self)
        if dialog.exec()!=QDialog.Accepted: return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            result=validate_structure_geometry(self.current_record,clash_overlap_threshold_angstrom=dialog.clash_overlap.value(),chain_break_threshold_angstrom=dialog.break_distance.value())
        except Exception as exc:
            QMessageBox.critical(self,"Structural validation failed",str(exc)); return
        finally: QApplication.restoreOverrideCursor()
        issues=[]
        for x in result.missing_backbone: issues.append(("Missing backbone",x.residue,x.missing_atoms,"—"))
        for x in result.chain_breaks: issues.append(("Possible chain break",x.residue_a,x.residue_b,f"C–N {x.c_n_distance_angstrom:.3f} Å"))
        for x in result.clashes: issues.append(("Potential steric overlap",x.atom_a,x.atom_b,f"overlap {x.overlap_angstrom:.3f} Å; d={x.distance_angstrom:.3f} Å"))
        self.validation_issues.setRowCount(len(issues))
        for row,vals in enumerate(issues):
            for col,val in enumerate(vals): self.validation_issues.setItem(row,col,QTableWidgetItem(str(val)))
        self.torsion_table.setRowCount(len(result.torsions))
        def deg(v): return "—" if v is None or not __import__('math').isfinite(v) else f"{v:.2f}"
        for row,t in enumerate(result.torsions):
            for col,val in enumerate((t.residue,deg(t.phi_deg),deg(t.psi_deg),deg(t.omega_to_next_deg))): self.torsion_table.setItem(row,col,QTableWidgetItem(val))
        self.validation_summary.setText(
            f"Geometry QC: {result.standard_residues} standard residues · {len(result.missing_backbone)} missing-backbone warnings · "
            f"{len(result.chain_breaks)} peptide-continuity warnings · {len(result.clashes)} conservative heavy-atom overlap warnings. "
            f"Clash threshold = van der Waals overlap ≥ {result.clash_overlap_threshold_angstrom:g} Å; chain-break warning C–N > {result.chain_break_threshold_angstrom:g} Å. "
            "Potential clash metric: δ = r_vdW,i + r_vdW,j − d_ij. φ/ψ/ω values are exact coordinate-derived signed dihedrals; no fake quality percentile is assigned."
        )
        self._show_experiment_tab(self.validation_tab)

    def compare_structures_dialog(self) -> None:
        if not self.current_record:
            QMessageBox.information(self,"Compare Structures","Load the reference/current protein first."); return
        records=[*self.builtins,*self.user_records]
        if len([r for r in records if r.id!=self.current_record.id])<1:
            QMessageBox.information(self,"Compare Structures","Import or create at least one other protein first."); return
        dialog=StructureComparisonDialog(self.current_record,records,self)
        if dialog.exec()!=QDialog.Accepted: return
        other=dialog.comparison_record
        if other is None or not dialog.current_chain.currentText() or not dialog.other_chain.currentText():
            QMessageBox.warning(self,"Compare Structures","Both structures need a protein chain containing Cα atoms."); return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            result=compare_structures(self.current_record,other,dialog.current_chain.currentText(),dialog.other_chain.currentText())
            self.viewer.show_comparison_ribbon(result.aligned_comparison_pdb,opacity=0.48)
        except Exception as exc:
            QMessageBox.critical(self,"Structure comparison failed",str(exc)); return
        finally: QApplication.restoreOverrideCursor()
        ordered=sorted(result.displacements,key=lambda d:d.distance_angstrom,reverse=True)
        self.compare_table.setRowCount(len(ordered))
        for row,d in enumerate(ordered):
            for col,val in enumerate((d.current_residue,d.comparison_residue,f"{d.distance_angstrom:.3f}")): self.compare_table.setItem(row,col,QTableWidgetItem(val))
        self.compare_summary.setText(
            f"Current chain {result.current_chain} vs {other.name} chain {result.comparison_chain} · {result.aligned_residues} sequence-aligned Cα pairs · "
            f"sequence identity {100*result.sequence_identity:.1f}% · Kabsch RMSD {result.rmsd_angstrom:.4f} Å. "
            "Kabsch fit: R* = argmin_R Σ_i ||(x_i−x̄)R − (y_i−ȳ)||²; RMSD = sqrt[(1/N)Σ_i d_i²]. "
            "Blue = current structure; translucent red = rigid-body-aligned comparison. Per-residue displacement is calculated after the same least-squares superposition."
        )
        self._show_experiment_tab(self.compare_tab)

    def clear_structure_comparison(self) -> None:
        self.viewer.clear_comparison_overlay()
        if hasattr(self,"compare_summary"):
            self.compare_summary.setText("Comparison overlay cleared. Choose Compare / align structures to create another coordinate-based superposition.")

    def calculate_sasa(self) -> None:
        if not self.current_record:
            QMessageBox.information(self, "SASA", "Load a protein first."); return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            result = compute_sasa(self.current_record, probe_radius_angstrom=1.4, n_points=100)
        except Exception as exc:
            QMessageBox.critical(self, "SASA failed", str(exc)); return
        finally:
            QApplication.restoreOverrideCursor()
        rows = sorted(result.residues, key=lambda r: r.sasa_angstrom2, reverse=True)
        detail = [
            f"Solvent-accessible surface area — {self.current_record.name}",
            "=" * (34 + len(self.current_record.name)), "",
            f"Method: Shrake-Rupley (Biopython)",
            f"Probe radius: {result.probe_radius_angstrom:g} Å",
            f"Sphere points per atom: {result.n_points}",
            f"Total residue-summed SASA: {result.total_sasa_angstrom2:.3f} Å²", "",
            "Top residues by SASA", "--------------------",
        ]
        detail.extend(f"{r.chain}:{r.residue_name}{r.residue_number}    {r.sasa_angstrom2:.3f} Å²" for r in rows[:80])
        detail += ["", "Interpretation", "--------------", "SASA is a geometric solvent-accessibility measure for these coordinates and parameters. It is not a solvation free energy."]
        append_entry(action="SASA analysis", protein_id=self.current_record.id, protein_name=self.current_record.name, method="Shrake-Rupley via Biopython", parameters={"probe_radius_A": result.probe_radius_angstrom, "sphere_points": result.n_points}, results={"total_SASA_A2": result.total_sasa_angstrom2, "residues": len(result.residues)})
        TextReportDialog("Solvent-Accessible Surface Area", "\n".join(detail), self).exec()

    def analyze_hydrogen_bonds(self) -> None:
        if not self.current_record:
            QMessageBox.information(self, "Hydrogen Bonds", "Load a protein first."); return
        try:
            result = detect_hydrogen_bonds(self.current_record)
        except Exception as exc:
            QMessageBox.critical(self, "Hydrogen-bond analysis failed", str(exc)); return
        lines = [
            f"Hydrogen-bond geometry — {self.current_record.name}",
            "=" * (27 + len(self.current_record.name)), "",
            f"D···A cutoff: ≤ {result.donor_acceptor_cutoff_angstrom:g} Å",
            f"H···A cutoff: ≤ {result.hydrogen_acceptor_cutoff_angstrom:g} Å",
            f"Minimum D-H···A angle: ≥ {result.minimum_angle_deg:g}°",
            f"Detected bonds: {len(result.bonds)}", "", result.note, "",
            "D-H···A contacts", "---------------",
        ]
        if result.bonds:
            lines.extend(f"{b.donor} — {b.hydrogen} ··· {b.acceptor}    D-A {b.donor_acceptor_angstrom:.3f} Å    H-A {b.hydrogen_acceptor_angstrom:.3f} Å    angle {b.angle_deg:.1f}°" for b in result.bonds[:300])
        else:
            lines.append("No contacts met the criteria. If this structure lacks explicit hydrogens, prepare/add hydrogens before using this analysis.")
        append_entry(action="Hydrogen-bond geometry", protein_id=self.current_record.id, protein_name=self.current_record.name, method="Explicit-hydrogen geometric D-H···A screen", parameters={"DA_cutoff_A": result.donor_acceptor_cutoff_angstrom, "HA_cutoff_A": result.hydrogen_acceptor_cutoff_angstrom, "minimum_angle_deg": result.minimum_angle_deg}, results={"detected_bonds": len(result.bonds)})
        TextReportDialog("Hydrogen Bonds", "\n".join(lines), self).exec()

    # ---------- view/theme ----------
    def _representation_changed(self, name: str) -> None:
        if self.current_pdb_path:
            try:
                self.viewer.set_representation(name, self.current_pdb_path)
                self.viewer.set_atom_records(self.current_atoms)
                if self.measurement_atoms:
                    self.viewer.show_selected_atoms(self.measurement_atoms, connect=True)
                elif self.last_selected_atom:
                    self.viewer.show_selected_atoms([self.last_selected_atom], connect=False)
            except Exception as exc:
                QMessageBox.warning(self, "Representation error", str(exc))

    def _theme_toggled(self, dark: bool) -> None:
        self.settings.setValue("dark_mode", dark)
        self._apply_theme(dark)

    def _apply_theme(self, dark: bool) -> None:
        if dark:
            apply_dark_theme(self.app)
            if hasattr(self, "viewer"):
                self.viewer.set_dark_background()
        else:
            apply_light_theme(self.app)
            if hasattr(self, "viewer"):
                self.viewer.set_light_background()

    def open_help_aid(self, topic_key: str | None = None) -> None:
        HelpAidDialog(self, topic_key=topic_key).exec()

    def open_validation_center(self) -> None:
        ValidationCenterDialog(self.project_root, self).exec()

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Protein Lab",
            f"Protein Lab {__version__}\n\n"
            "Native Python molecular-biophysics workstation for protein construction, structure prediction, visualization, molecular mechanics, simulation, mutation, and quantitative structural analysis.\n\n"
            "Research mode and light mode are the defaults. Open Help Aid (F1) for the complete workflow guide, equations, scientific boundaries, and troubleshooting. Validation Center reports deterministic numerical and runtime checks for this installation.\n\n"
            "Protein Lab distinguishes experimental/source coordinates, predicted structures, constructed geometry, force-field models, minimized structures, and molecular-dynamics results rather than presenting them as equivalent evidence.",
        )

    # ---------- math transparency, modes, provenance, projects ----------
    def open_calculation_inspector(self) -> None:
        CalculationInspectorDialog(self).exec()

    def open_experiment_notebook(self) -> None:
        ExperimentNotebookDialog(load_entries(), self).exec()

    def generate_methods_report(self) -> None:
        protein_id = self.current_record.id if self.current_record else None
        text = methods_text(load_entries(), protein_id=protein_id)
        TextReportDialog("Generated Computational Methods", text, self).exec()

    def _mode_changed(self, mode: str) -> None:
        research = mode == "Research"
        # Both modes use the same scientific engine. Student mode changes guidance, not equations.
        self.statusBar().showMessage("Research mode: full scientific controls visible." if research else "Student mode: same scientific calculations with guided explanations. Open Learn → Student Lab Guide.")
        if not research:
            self.student_guide_action.setEnabled(True)

    def export_current_structure(self) -> None:
        if not self.current_record:
            QMessageBox.information(self, "Protein Lab", "Load a protein first."); return
        suffix = ".pdb" if self.current_record.format == "pdb" else ".cif"
        filename,_ = QFileDialog.getSaveFileName(self, "Export Current Structure", self.current_record.name.replace(" ", "_") + suffix, "Protein structure (*.pdb *.cif *.mmcif);;All files (*.*)")
        if not filename: return
        target = Path(filename)
        suffix = target.suffix.lower()
        if suffix == ".pdb":
            import shutil
            shutil.copy2(pdb_path_for_vtk(self.current_record), target)
        elif suffix in {".cif", ".mmcif"}:
            st = read_structure(self.current_record)
            st.make_mmcif_document().write_file(str(target))
        else:
            QMessageBox.warning(self, "Unsupported export", "Use .pdb, .cif, or .mmcif for structure export."); return
        self.statusBar().showMessage(f"Exported structure to {filename}")

    def export_current_fasta(self) -> None:
        if not self.current_record:
            QMessageBox.information(self, "Protein Lab", "Load a protein first."); return
        info = inspect_structure(self.current_record)
        if not info.sequences:
            QMessageBox.warning(self, "No sequence", "No standard amino-acid sequence was found."); return
        filename,_=QFileDialog.getSaveFileName(self,"Export FASTA",self.current_record.name.replace(" ","_")+".fasta","FASTA (*.fasta *.fa);;Text (*.txt)")
        if not filename: return
        lines=[]
        for chain,seq in info.sequences.items(): lines += [f">{self.current_record.name}|chain_{chain}", seq]
        Path(filename).write_text("\n".join(lines)+"\n",encoding="utf-8")
        self.statusBar().showMessage(f"Exported FASTA to {filename}")

    def export_simulation_bundle(self) -> None:
        if not self.current_record:
            QMessageBox.information(self, "Protein Lab", "Load a simulation result first."); return
        candidates = []
        for key in ("state_log_csv", "trajectory_npz", "trajectory_dcd"):
            value = self.current_record.metadata.get(key, "").strip()
            if value and Path(value).exists(): candidates.append(Path(value))
        if not candidates:
            QMessageBox.information(self, "No simulation outputs", "The current protein has no attached MD output files."); return
        filename,_=QFileDialog.getSaveFileName(self,"Export Simulation Bundle",self.current_record.name.replace(" ","_")+"_simulation.zip","ZIP archive (*.zip)")
        if not filename: return
        import zipfile
        with zipfile.ZipFile(filename,"w",zipfile.ZIP_DEFLATED) as z:
            z.write(pdb_path_for_vtk(self.current_record), "final_structure.pdb")
            for path in candidates: z.write(path, path.name)
            z.writestr("metadata.json", __import__("json").dumps(self.current_record.metadata, indent=2))
        self.statusBar().showMessage(f"Exported simulation bundle to {filename}")

    def export_notebook_json(self) -> None:
        filename,_=QFileDialog.getSaveFileName(self,"Export Experiment Notebook","ProteinLab_experiment_notebook.json","JSON (*.json)")
        if not filename: return
        import json
        Path(filename).write_text(json.dumps([e.to_dict() for e in load_entries()], indent=2, default=str), encoding="utf-8")
        self.statusBar().showMessage(f"Exported experiment notebook to {filename}")

    def save_project_dialog(self) -> None:
        filename,_=QFileDialog.getSaveFileName(self,"Save Protein Lab Project","ProteinLab_Project.plab","Protein Lab project (*.plab)")
        if not filename: return
        try:
            save_project(Path(filename), self.user_records, load_entries(), current_id=self.current_record.id if self.current_record else None)
            self.statusBar().showMessage(f"Project saved to {filename}")
        except Exception as exc:
            QMessageBox.critical(self,"Project save failed",str(exc))

    def load_project_dialog(self) -> None:
        filename,_=QFileDialog.getOpenFileName(self,"Open Protein Lab Project","","Protein Lab project (*.plab)")
        if not filename: return
        try:
            records, project_entries, current_id = load_project(Path(filename), self.user_records)
            self.user_records = records
            existing = load_entries(); existing.extend(project_entries); save_entries(existing)
            self._refresh_toolbox()
            record = self._record_by_id(current_id) if current_id else (records[0] if records else None)
            if record: self.load_record(record)
            self.statusBar().showMessage(f"Project opened: {filename}")
        except Exception as exc:
            QMessageBox.critical(self,"Project open failed",str(exc))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("ProteinLab")
    app.setApplicationName("Protein Lab")
    app.setApplicationVersion(__version__)
    if sys.platform.startswith("win"):
        app.setFont(QFont("Segoe UI", 9))
    window = MainWindow(app)
    window.show()
    return app.exec()
