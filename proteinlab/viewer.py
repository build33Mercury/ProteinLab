from __future__ import annotations

import math
import os
from pathlib import Path

os.environ.setdefault("QT_API", "pyside6")

import vtkmodules.vtkInteractionStyle  # noqa: F401
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.vtkDomainsChemistry import vtkProteinRibbonFilter
from vtkmodules.vtkFiltersCore import vtkTubeFilter
from vtkmodules.vtkFiltersSources import vtkLineSource, vtkSphereSource
from vtkmodules.vtkIOChemistry import vtkPDBReader
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkGlyph3DMapper,
    vtkPolyDataMapper,
    vtkRenderer,
)
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera

from .structure import AtomRecord


class ProteinViewer(QWidget):
    """Native VTK protein viewport displaying actual structure coordinates."""

    atomPicked = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._vtk = QVTKRenderWindowInteractor(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._vtk)

        window = self._vtk.GetRenderWindow()
        window.SetMultiSamples(8)

        self.renderer = vtkRenderer()
        window.AddRenderer(self.renderer)
        self.interactor = window.GetInteractor()
        self.interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
        self._vtk.Initialize()

        self._reader: vtkPDBReader | None = None
        self._actors: list[vtkActor] = []
        self._overlay_actors: list[vtkActor] = []
        self._comparison_actors: list[vtkActor] = []
        self._representation = "Ribbon"
        self._atoms: list[AtomRecord] = []
        self._mouse_press: tuple[int, int] | None = None
        self._picking_enabled = True
        self._pick_radius_px = 13.0

        self.interactor.AddObserver("LeftButtonPressEvent", self._on_left_press, 0.1)
        self.interactor.AddObserver("LeftButtonReleaseEvent", self._on_left_release, 0.1)
        self.set_light_background()

    def set_light_background(self) -> None:
        self.renderer.SetBackground(0.99, 0.99, 0.99)
        self.renderer.SetBackground2(0.95, 0.96, 0.97)
        self.renderer.GradientBackgroundOn()
        self._vtk.GetRenderWindow().Render()

    def set_dark_background(self) -> None:
        self.renderer.SetBackground(0.12, 0.12, 0.13)
        self.renderer.SetBackground2(0.065, 0.065, 0.075)
        self.renderer.GradientBackgroundOn()
        self._vtk.GetRenderWindow().Render()

    def clear(self) -> None:
        self.renderer.RemoveAllViewProps()
        self._actors.clear()
        self._overlay_actors.clear()
        self._comparison_actors.clear()
        self._reader = None
        self._atoms = []
        self._vtk.GetRenderWindow().Render()

    def set_atom_records(self, atoms: list[AtomRecord]) -> None:
        self._atoms = list(atoms)

    def set_picking_mode(self, enabled: bool, *, crosshair: bool = False) -> None:
        self._picking_enabled = enabled
        self.setCursor(Qt.CrossCursor if crosshair else Qt.ArrowCursor)

    def _add_actor(self, actor: vtkActor) -> None:
        self._actors.append(actor)
        self.renderer.AddActor(actor)

    def _build_ribbon(self, reader: vtkPDBReader) -> None:
        ribbon = vtkProteinRibbonFilter()
        ribbon.SetInputConnection(reader.GetOutputPort())
        ribbon.SetCoilWidth(0.22)
        ribbon.SetHelixWidth(1.15)
        ribbon.Update()

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(ribbon.GetOutputPort())
        if ribbon.GetOutput().GetPointData().GetScalars():
            mapper.ScalarVisibilityOn()
        else:
            mapper.ScalarVisibilityOff()

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0.20, 0.42, 0.68)
        actor.GetProperty().SetDiffuse(0.88)
        actor.GetProperty().SetAmbient(0.10)
        actor.GetProperty().SetSpecular(0.18)
        actor.GetProperty().SetSpecularPower(24.0)
        self._add_actor(actor)

    def _build_atoms_and_bonds(self, reader: vtkPDBReader, space_fill: bool, sticks_only: bool) -> None:
        poly = reader.GetOutput()

        tube = vtkTubeFilter()
        tube.SetInputData(poly)
        tube.SetNumberOfSides(10)
        tube.CappingOn()
        tube.SetRadius(0.17 if sticks_only else 0.11)
        tube.Update()
        bond_mapper = vtkPolyDataMapper()
        bond_mapper.SetInputConnection(tube.GetOutputPort())
        bond_mapper.ScalarVisibilityOff()
        bond_actor = vtkActor()
        bond_actor.SetMapper(bond_mapper)
        bond_actor.GetProperty().SetColor(0.48, 0.48, 0.48)
        bond_actor.GetProperty().SetSpecular(0.15)
        self._add_actor(bond_actor)

        if sticks_only:
            return

        sphere = vtkSphereSource()
        sphere.SetThetaResolution(18)
        sphere.SetPhiResolution(18)
        sphere.SetRadius(1.0)

        atom_mapper = vtkGlyph3DMapper()
        atom_mapper.SetInputData(poly)
        atom_mapper.SetSourceConnection(sphere.GetOutputPort())
        atom_mapper.ScalingOn()
        atom_mapper.SetScaleArray("radius")
        atom_mapper.SetScaleModeToScaleByMagnitude()
        atom_mapper.SetScaleFactor(1.0 if space_fill else 0.32)
        atom_mapper.SetScalarModeToUsePointFieldData()
        atom_mapper.SelectColorArray("rgb_colors")
        atom_mapper.SetColorModeToDirectScalars()
        atom_mapper.ScalarVisibilityOn()

        atom_actor = vtkActor()
        atom_actor.SetMapper(atom_mapper)
        atom_actor.GetProperty().SetSpecular(0.22)
        atom_actor.GetProperty().SetSpecularPower(28.0)
        self._add_actor(atom_actor)

    def load_pdb(self, path: Path, representation: str | None = None, *, reset_camera: bool = True) -> None:
        if representation:
            self._representation = representation

        self.renderer.RemoveAllViewProps()
        self._actors.clear()
        self._overlay_actors.clear()
        self._comparison_actors.clear()

        reader = vtkPDBReader()
        reader.SetFileName(str(path))
        reader.Update()
        if reader.GetOutput().GetNumberOfPoints() == 0:
            raise ValueError("The structure contains no atoms that VTK can render.")
        self._reader = reader

        if self._representation == "Ribbon":
            self._build_ribbon(reader)
        elif self._representation == "Sticks":
            self._build_atoms_and_bonds(reader, space_fill=False, sticks_only=True)
        elif self._representation == "Space filling":
            self._build_atoms_and_bonds(reader, space_fill=True, sticks_only=False)
        else:
            self._build_atoms_and_bonds(reader, space_fill=False, sticks_only=False)

        if reset_camera:
            self.renderer.ResetCamera()
            cam = self.renderer.GetActiveCamera()
            cam.Azimuth(22)
            cam.Elevation(13)
            cam.Zoom(0.92)
        self.renderer.ResetCameraClippingRange()
        self._vtk.GetRenderWindow().Render()

    def load_trajectory_frame(self, path: Path) -> None:
        """Replace coordinates for trajectory playback without resetting the user's camera."""
        self.load_pdb(path, self._representation, reset_camera=False)

    def set_representation(self, representation: str, current_path: Path | None) -> None:
        self._representation = representation
        if current_path and current_path.exists():
            self.load_pdb(current_path, representation)

    def reset_camera(self) -> None:
        self.renderer.ResetCamera()
        self.renderer.GetActiveCamera().Zoom(0.92)
        self.renderer.ResetCameraClippingRange()
        self._vtk.GetRenderWindow().Render()


    def clear_comparison_overlay(self) -> None:
        for actor in self._comparison_actors:
            self.renderer.RemoveActor(actor)
        self._comparison_actors.clear()
        self._vtk.GetRenderWindow().Render()

    def show_comparison_ribbon(self, path: Path, *, opacity: float = 0.48) -> None:
        """Overlay a second, already-aligned structure as a translucent ribbon."""
        self.clear_comparison_overlay()
        reader = vtkPDBReader()
        reader.SetFileName(str(path))
        reader.Update()
        if reader.GetOutput().GetNumberOfPoints() == 0:
            raise ValueError("Comparison structure contains no atoms that VTK can render.")
        ribbon = vtkProteinRibbonFilter()
        ribbon.SetInputConnection(reader.GetOutputPort())
        ribbon.SetCoilWidth(0.22)
        ribbon.SetHelixWidth(1.15)
        ribbon.Update()
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(ribbon.GetOutputPort())
        mapper.ScalarVisibilityOff()
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.PickableOff()
        actor.GetProperty().SetColor(0.82, 0.28, 0.25)
        actor.GetProperty().SetOpacity(float(max(0.05, min(opacity, 1.0))))
        actor.GetProperty().SetDiffuse(0.86)
        actor.GetProperty().SetSpecular(0.15)
        self.renderer.AddActor(actor)
        self._comparison_actors.append(actor)
        self.renderer.ResetCameraClippingRange()
        self._vtk.GetRenderWindow().Render()

    # ---------- atom selection / measurement overlay ----------
    def _on_left_press(self, obj, event) -> None:  # noqa: ANN001
        try:
            x, y = self.interactor.GetEventPosition()
            self._mouse_press = (int(x), int(y))
        except Exception:
            self._mouse_press = None

    def _on_left_release(self, obj, event) -> None:  # noqa: ANN001
        if not self._picking_enabled or not self._atoms or self._mouse_press is None:
            return
        try:
            x, y = self.interactor.GetEventPosition()
            dx = int(x) - self._mouse_press[0]
            dy = int(y) - self._mouse_press[1]
            # A drag rotates the camera; a near-stationary click selects an atom.
            if dx * dx + dy * dy > 25:
                return
            atom = self._nearest_atom_on_screen(float(x), float(y))
            if atom is not None:
                self.atomPicked.emit(atom)
        finally:
            self._mouse_press = None

    def _nearest_atom_on_screen(self, x: float, y: float) -> AtomRecord | None:
        best: AtomRecord | None = None
        best_d2 = self._pick_radius_px * self._pick_radius_px
        for atom in self._atoms:
            self.renderer.SetWorldPoint(atom.x, atom.y, atom.z, 1.0)
            self.renderer.WorldToDisplay()
            sx, sy, sz = self.renderer.GetDisplayPoint()
            if sz < 0.0 or sz > 1.0:
                continue
            d2 = (sx - x) ** 2 + (sy - y) ** 2
            if d2 <= best_d2:
                best_d2 = d2
                best = atom
        return best

    def clear_selection_overlay(self) -> None:
        for actor in self._overlay_actors:
            self.renderer.RemoveActor(actor)
        self._overlay_actors.clear()
        self._vtk.GetRenderWindow().Render()

    def show_selected_atoms(self, atoms: list[AtomRecord], *, connect: bool = True) -> None:
        self.clear_selection_overlay()
        if not atoms:
            return

        for atom in atoms:
            sphere = vtkSphereSource()
            sphere.SetCenter(atom.x, atom.y, atom.z)
            sphere.SetRadius(0.30)
            sphere.SetThetaResolution(18)
            sphere.SetPhiResolution(18)
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(sphere.GetOutputPort())
            actor = vtkActor()
            actor.SetMapper(mapper)
            actor.PickableOff()
            actor.GetProperty().SetColor(0.88, 0.22, 0.18)
            actor.GetProperty().SetSpecular(0.2)
            self.renderer.AddActor(actor)
            self._overlay_actors.append(actor)

        if connect and len(atoms) > 1:
            for first, second in zip(atoms[:-1], atoms[1:]):
                line = vtkLineSource()
                line.SetPoint1(*first.coord)
                line.SetPoint2(*second.coord)
                mapper = vtkPolyDataMapper()
                mapper.SetInputConnection(line.GetOutputPort())
                actor = vtkActor()
                actor.SetMapper(mapper)
                actor.PickableOff()
                actor.GetProperty().SetColor(0.20, 0.20, 0.20)
                actor.GetProperty().SetLineWidth(2.2)
                self.renderer.AddActor(actor)
                self._overlay_actors.append(actor)

        self._vtk.GetRenderWindow().Render()
