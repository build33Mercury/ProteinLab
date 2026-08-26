from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict

import gemmi
import numpy as np
from Bio.Align import PairwiseAligner

from .library import CACHE_DIR, ensure_dirs
from .models import ProteinRecord
from .structure import AA3, read_structure

WATER_NAMES = {"HOH", "WAT", "H2O", "DOD"}
COMMON_COFACTORS = {
    "HEM", "HEC", "HEA", "FAD", "FMN", "NAD", "NAP", "NDP", "NAI", "ATP", "ADP", "AMP",
    "GTP", "GDP", "GMP", "SAM", "SAH", "COA", "PLP", "TPP", "THF", "B12", "RET", "FES",
}
ION_NAMES = {
    "NA", "K", "CL", "CA", "MG", "ZN", "FE", "MN", "CU", "CO", "NI", "CD", "HG", "CS", "LI",
    "BR", "IOD", "I", "SR", "BA",
}
VDW_RADII = {
    "H": 1.20, "C": 1.70, "N": 1.55, "O": 1.52, "F": 1.47, "P": 1.80, "S": 1.80,
    "CL": 1.75, "BR": 1.85, "I": 1.98, "FE": 1.80, "ZN": 1.39, "MG": 1.73, "CA": 1.94,
}
BACKBONE_REQUIRED = ("N", "CA", "C", "O")
STANDARD_AA = set(AA3)


def _resnum(residue: gemmi.Residue) -> str:
    try:
        n = str(residue.seqid.num)
        i = str(residue.seqid.icode).strip()
        return f"{n}{i}" if i else n
    except Exception:
        return "?"


def _heavy_atoms(residue: gemmi.Residue):
    return [a for a in residue if a.element.name.upper() != "H"]


def _distance(a: gemmi.Atom, b: gemmi.Atom) -> float:
    dx = float(a.pos.x - b.pos.x)
    dy = float(a.pos.y - b.pos.y)
    dz = float(a.pos.z - b.pos.z)
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _dihedral(p0, p1, p2, p3) -> float:
    p0 = np.asarray(p0, dtype=float); p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float); p3 = np.asarray(p3, dtype=float)
    b0 = -(p1 - p0); b1 = p2 - p1; b2 = p3 - p2
    norm = np.linalg.norm(b1)
    if norm < 1e-12:
        return float("nan")
    b1 /= norm
    v = b0 - np.dot(b0, b1) * b1
    w = b2 - np.dot(b2, b1) * b1
    nv = np.linalg.norm(v); nw = np.linalg.norm(w)
    if nv < 1e-12 or nw < 1e-12:
        return float("nan")
    x = np.dot(v, w)
    y = np.dot(np.cross(b1, v), w)
    return float(np.degrees(np.arctan2(y, x)))


def _pos(atom: gemmi.Atom) -> tuple[float, float, float]:
    return (float(atom.pos.x), float(atom.pos.y), float(atom.pos.z))


def _atom(residue: gemmi.Residue, name: str) -> gemmi.Atom | None:
    name = name.upper()
    for a in residue:
        if a.name.strip().upper() == name:
            return a
    return None


@dataclass(slots=True)
class ComponentRecord:
    key: str
    chain: str
    residue_name: str
    residue_number: str
    category: str
    atoms: int
    heavy_atoms: int

    @property
    def label(self) -> str:
        return f"{self.chain}:{self.residue_name}{self.residue_number}"


@dataclass(slots=True)
class PocketResidue:
    residue: str
    residue_name: str
    chain: str
    residue_number: str
    minimum_distance_angstrom: float
    contacting_atom_pairs: int


@dataclass(slots=True)
class PocketResult:
    ligand: ComponentRecord
    cutoff_angstrom: float
    residues: list[PocketResidue]


@dataclass(slots=True)
class InterfaceContact:
    chain_a: str
    chain_b: str
    residue_a: str
    residue_b: str
    minimum_distance_angstrom: float
    atom_contacts: int


@dataclass(slots=True)
class InterfaceResult:
    cutoff_angstrom: float
    contacts: list[InterfaceContact]
    chain_pairs: dict[str, int]
    interface_residues: dict[str, list[str]]


@dataclass(slots=True)
class MissingBackbone:
    residue: str
    missing_atoms: str


@dataclass(slots=True)
class ChainBreak:
    chain: str
    residue_a: str
    residue_b: str
    c_n_distance_angstrom: float


@dataclass(slots=True)
class ClashRecord:
    atom_a: str
    atom_b: str
    distance_angstrom: float
    overlap_angstrom: float


@dataclass(slots=True)
class BackboneTorsion:
    residue: str
    phi_deg: float | None
    psi_deg: float | None
    omega_to_next_deg: float | None


@dataclass(slots=True)
class ValidationResult:
    standard_residues: int
    missing_backbone: list[MissingBackbone]
    chain_breaks: list[ChainBreak]
    clashes: list[ClashRecord]
    torsions: list[BackboneTorsion]
    clash_overlap_threshold_angstrom: float
    chain_break_threshold_angstrom: float


@dataclass(slots=True)
class ResidueDisplacement:
    current_residue: str
    comparison_residue: str
    distance_angstrom: float


@dataclass(slots=True)
class StructureComparisonResult:
    current_chain: str
    comparison_chain: str
    aligned_residues: int
    sequence_identity: float
    rmsd_angstrom: float
    displacements: list[ResidueDisplacement]
    aligned_comparison_pdb: Path


def list_nonprotein_components(record: ProteinRecord) -> list[ComponentRecord]:
    st = read_structure(record)
    out: list[ComponentRecord] = []
    if not len(st):
        return out
    for chain in st[0]:
        for residue in chain:
            name = residue.name.upper().strip()
            if name in STANDARD_AA or name in WATER_NAMES:
                continue
            atoms = list(residue)
            if not atoms:
                continue
            heavy = [a for a in atoms if a.element.name.upper() != "H"]
            elem_names = {a.element.name.upper() for a in atoms if a.element}
            if name in COMMON_COFACTORS:
                category = "Cofactor"
            elif name in ION_NAMES or (len(heavy) == 1 and len(elem_names) == 1):
                category = "Ion"
            else:
                category = "Ligand / non-polymer"
            num = _resnum(residue)
            key = f"{chain.name}|{name}|{num}"
            out.append(ComponentRecord(key, chain.name or "?", name, num, category, len(atoms), len(heavy)))
    return out


def analyze_binding_pocket(record: ProteinRecord, component_key: str, cutoff_angstrom: float = 4.0) -> PocketResult:
    if cutoff_angstrom <= 0:
        raise ValueError("Pocket cutoff must be positive.")
    st = read_structure(record)
    if not len(st):
        raise ValueError("Structure has no model.")
    target = None
    target_component = None
    for component in list_nonprotein_components(record):
        if component.key == component_key:
            target_component = component
            break
    if target_component is None:
        raise ValueError("Selected ligand/cofactor is no longer present in the structure.")
    for chain in st[0]:
        for residue in chain:
            if chain.name == target_component.chain and residue.name.upper().strip() == target_component.residue_name and _resnum(residue) == target_component.residue_number:
                target = residue
                break
    if target is None:
        raise ValueError("Could not locate selected component atoms.")
    ligand_atoms = _heavy_atoms(target)
    if not ligand_atoms:
        raise ValueError("Selected component contains no heavy atoms.")
    rows: list[PocketResidue] = []
    for chain in st[0]:
        for residue in chain:
            name = residue.name.upper().strip()
            if name not in STANDARD_AA:
                continue
            protein_atoms = _heavy_atoms(residue)
            dmin = float("inf"); count = 0
            for pa in protein_atoms:
                for la in ligand_atoms:
                    d = _distance(pa, la)
                    if d <= cutoff_angstrom:
                        count += 1
                        dmin = min(dmin, d)
            if count:
                num = _resnum(residue)
                rows.append(PocketResidue(f"{chain.name}:{name}{num}", name, chain.name or "?", num, dmin, count))
    rows.sort(key=lambda x: (x.minimum_distance_angstrom, x.residue))
    return PocketResult(target_component, float(cutoff_angstrom), rows)


def analyze_chain_interfaces(record: ProteinRecord, cutoff_angstrom: float = 5.0) -> InterfaceResult:
    if cutoff_angstrom <= 0:
        raise ValueError("Interface cutoff must be positive.")
    st = read_structure(record)
    if not len(st):
        raise ValueError("Structure has no model.")
    protein_by_chain: dict[str, list[tuple[gemmi.Residue, list[gemmi.Atom]]]] = {}
    for chain in st[0]:
        residues = []
        for residue in chain:
            if residue.name.upper().strip() in STANDARD_AA:
                heavy = _heavy_atoms(residue)
                if heavy:
                    residues.append((residue, heavy))
        if residues:
            protein_by_chain[chain.name or "?"] = residues
    chains = list(protein_by_chain)
    if len(chains) < 2:
        raise ValueError("Interface analysis requires at least two protein chains.")

    contacts: list[InterfaceContact] = []
    chain_pairs: dict[str, int] = defaultdict(int)
    interface_residues: dict[str, set[str]] = defaultdict(set)
    cutoff2 = cutoff_angstrom * cutoff_angstrom

    # Grid-hash the atoms for the second chain of every pair to avoid O(N^2) behavior on large complexes.
    for i, ca in enumerate(chains):
        for cb in chains[i+1:]:
            cells: dict[tuple[int, int, int], list[tuple[gemmi.Residue, gemmi.Atom]]] = defaultdict(list)
            for residue, atoms in protein_by_chain[cb]:
                for atom in atoms:
                    key = (math.floor(atom.pos.x/cutoff_angstrom), math.floor(atom.pos.y/cutoff_angstrom), math.floor(atom.pos.z/cutoff_angstrom))
                    cells[key].append((residue, atom))
            pair_stats: dict[tuple[int, int], tuple[gemmi.Residue, gemmi.Residue, float, int]] = {}
            for ra, atoms_a in protein_by_chain[ca]:
                for aa in atoms_a:
                    cell = (math.floor(aa.pos.x/cutoff_angstrom), math.floor(aa.pos.y/cutoff_angstrom), math.floor(aa.pos.z/cutoff_angstrom))
                    for dx in (-1,0,1):
                        for dy in (-1,0,1):
                            for dz in (-1,0,1):
                                for rb, ab in cells.get((cell[0]+dx,cell[1]+dy,cell[2]+dz), []):
                                    x=float(aa.pos.x-ab.pos.x); y=float(aa.pos.y-ab.pos.y); z=float(aa.pos.z-ab.pos.z)
                                    d2=x*x+y*y+z*z
                                    if d2 <= cutoff2:
                                        k=(id(ra),id(rb)); d=math.sqrt(d2)
                                        if k not in pair_stats:
                                            pair_stats[k]=(ra,rb,d,1)
                                        else:
                                            _ra,_rb,old,c=pair_stats[k]; pair_stats[k]=(_ra,_rb,min(old,d),c+1)
            for ra, rb, dmin, count in pair_stats.values():
                la=f"{ca}:{ra.name.upper()}{_resnum(ra)}"; lb=f"{cb}:{rb.name.upper()}{_resnum(rb)}"
                contacts.append(InterfaceContact(ca,cb,la,lb,dmin,count))
                chain_pairs[f"{ca}–{cb}"] += 1
                interface_residues[ca].add(la); interface_residues[cb].add(lb)
    contacts.sort(key=lambda x:(x.chain_a,x.chain_b,x.minimum_distance_angstrom,x.residue_a,x.residue_b))
    return InterfaceResult(float(cutoff_angstrom), contacts, dict(chain_pairs), {k:sorted(v) for k,v in interface_residues.items()})


def validate_structure_geometry(
    record: ProteinRecord,
    *,
    clash_overlap_threshold_angstrom: float = 0.4,
    chain_break_threshold_angstrom: float = 1.8,
    max_clashes: int = 500,
) -> ValidationResult:
    if clash_overlap_threshold_angstrom < 0:
        raise ValueError("Clash overlap threshold cannot be negative.")
    st=read_structure(record)
    if not len(st):
        raise ValueError("Structure has no model.")
    missing: list[MissingBackbone]=[]; breaks: list[ChainBreak]=[]; torsions: list[BackboneTorsion]=[]
    standard_count=0
    ordered_residues: dict[str,list[gemmi.Residue]]={}
    residue_index: dict[tuple[str,str],int]={}
    for chain in st[0]:
        residues=[r for r in chain if r.name.upper().strip() in STANDARD_AA]
        if not residues: continue
        ordered_residues[chain.name or "?"]=residues
        for idx,r in enumerate(residues): residue_index[(chain.name or "?",_resnum(r))]=idx
        for idx,r in enumerate(residues):
            standard_count += 1
            names={a.name.strip().upper() for a in r}
            miss=[n for n in BACKBONE_REQUIRED if n not in names]
            label=f"{chain.name}:{r.name.upper()}{_resnum(r)}"
            if miss: missing.append(MissingBackbone(label,", ".join(miss)))
            prev=residues[idx-1] if idx>0 else None; nxt=residues[idx+1] if idx+1<len(residues) else None
            phi=psi=omega=None
            if prev and _atom(prev,"C") and _atom(r,"N") and _atom(r,"CA") and _atom(r,"C"):
                phi=_dihedral(_pos(_atom(prev,"C")),_pos(_atom(r,"N")),_pos(_atom(r,"CA")),_pos(_atom(r,"C")))
            if nxt and _atom(r,"N") and _atom(r,"CA") and _atom(r,"C") and _atom(nxt,"N"):
                psi=_dihedral(_pos(_atom(r,"N")),_pos(_atom(r,"CA")),_pos(_atom(r,"C")),_pos(_atom(nxt,"N")))
            if nxt and _atom(r,"CA") and _atom(r,"C") and _atom(nxt,"N") and _atom(nxt,"CA"):
                omega=_dihedral(_pos(_atom(r,"CA")),_pos(_atom(r,"C")),_pos(_atom(nxt,"N")),_pos(_atom(nxt,"CA")))
                d=_distance(_atom(r,"C"),_atom(nxt,"N"))
                if d > chain_break_threshold_angstrom:
                    breaks.append(ChainBreak(chain.name or "?",label,f"{chain.name}:{nxt.name.upper()}{_resnum(nxt)}",d))
            torsions.append(BackboneTorsion(label,phi,psi,omega))

    # Conservative geometry-only clash search. Same-residue and adjacent-residue atom pairs are excluded
    # because covalent connectivity is not inferred here.
    atoms=[]
    for chain in st[0]:
        for residue in chain:
            if residue.name.upper().strip() not in STANDARD_AA: continue
            num=_resnum(residue)
            for atom in _heavy_atoms(residue):
                elem=atom.element.name.upper()
                if elem in VDW_RADII:
                    atoms.append((chain.name or "?",num,residue.name.upper(),atom,VDW_RADII[elem]))
    cell_size=4.0; grid: dict[tuple[int,int,int],list[int]]=defaultdict(list); clashes=[]
    for idx,(ch,num,rn,a,rad) in enumerate(atoms):
        cell=(math.floor(a.pos.x/cell_size),math.floor(a.pos.y/cell_size),math.floor(a.pos.z/cell_size))
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for dz in (-1,0,1):
                    for j in grid.get((cell[0]+dx,cell[1]+dy,cell[2]+dz),[]):
                        ch2,num2,rn2,b,rad2=atoms[j]
                        if ch==ch2 and num==num2: continue
                        if ch==ch2:
                            ia=residue_index.get((ch,num)); ib=residue_index.get((ch2,num2))
                            if ia is not None and ib is not None and abs(ia-ib)<=1: continue
                        d=_distance(a,b); overlap=rad+rad2-d
                        if overlap >= clash_overlap_threshold_angstrom:
                            la=f"{ch}:{rn}{num}:{a.name.strip()}"; lb=f"{ch2}:{rn2}{num2}:{b.name.strip()}"
                            clashes.append(ClashRecord(la,lb,d,overlap))
                            if len(clashes)>=max_clashes: break
                    if len(clashes)>=max_clashes: break
                if len(clashes)>=max_clashes: break
            if len(clashes)>=max_clashes: break
        grid[cell].append(idx)
        if len(clashes)>=max_clashes: break
    clashes.sort(key=lambda c:-c.overlap_angstrom)
    return ValidationResult(standard_count,missing,breaks,clashes,torsions,float(clash_overlap_threshold_angstrom),float(chain_break_threshold_angstrom))


def protein_chain_ids(record: ProteinRecord) -> list[str]:
    st=read_structure(record); out=[]
    if not len(st): return out
    for chain in st[0]:
        if any(r.name.upper().strip() in STANDARD_AA for r in chain): out.append(chain.name or "?")
    return out


def _chain_residues(record: ProteinRecord, chain_id: str):
    st=read_structure(record)
    if not len(st): return [], ""
    residues=[]; seq=[]
    for chain in st[0]:
        if (chain.name or "?") != chain_id: continue
        for r in chain:
            aa=AA3.get(r.name.upper().strip()); ca=_atom(r,"CA")
            if aa and ca is not None:
                residues.append((r, np.array([ca.pos.x,ca.pos.y,ca.pos.z],dtype=float))); seq.append(aa)
    return residues,"".join(seq)


def _kabsch_transform(mobile: np.ndarray, reference: np.ndarray):
    mob_center=mobile.mean(axis=0); ref_center=reference.mean(axis=0)
    x=mobile-mob_center; y=reference-ref_center
    u,_s,vt=np.linalg.svd(x.T@y); correction=np.eye(3); correction[-1,-1]=np.sign(np.linalg.det(u@vt)); rot=u@correction@vt
    return rot,mob_center,ref_center


def compare_structures(current: ProteinRecord, comparison: ProteinRecord, current_chain: str, comparison_chain: str) -> StructureComparisonResult:
    a_res,a_seq=_chain_residues(current,current_chain); b_res,b_seq=_chain_residues(comparison,comparison_chain)
    if len(a_res)<3 or len(b_res)<3:
        raise ValueError("Both selected chains need at least three residues with Cα atoms.")
    aligner=PairwiseAligner(); aligner.mode="global"; aligner.match_score=2.0; aligner.mismatch_score=-1.0; aligner.open_gap_score=-3.0; aligner.extend_gap_score=-0.5
    alignment=aligner.align(a_seq,b_seq)[0]
    a_blocks,b_blocks=alignment.aligned
    pairs=[]
    for ab,bb in zip(a_blocks,b_blocks,strict=True):
        alen=int(ab[1]-ab[0]); blen=int(bb[1]-bb[0])
        if alen != blen: continue
        for off in range(alen): pairs.append((int(ab[0])+off,int(bb[0])+off))
    if len(pairs)<3: raise ValueError("Sequence alignment produced fewer than three comparable Cα positions.")
    A=np.vstack([a_res[i][1] for i,j in pairs]); B=np.vstack([b_res[j][1] for i,j in pairs])
    rot,mob_center,ref_center=_kabsch_transform(B,A); Baligned=(B-mob_center)@rot+ref_center
    delta=Baligned-A; distances=np.sqrt(np.sum(delta*delta,axis=1)); rmsd=float(np.sqrt(np.mean(distances*distances)))
    identical=sum(1 for i,j in pairs if a_seq[i]==b_seq[j]); identity=identical/len(pairs)
    disp=[]
    for (i,j),d in zip(pairs,distances,strict=True):
        ra=a_res[i][0]; rb=b_res[j][0]
        disp.append(ResidueDisplacement(f"{current_chain}:{ra.name.upper()}{_resnum(ra)}",f"{comparison_chain}:{rb.name.upper()}{_resnum(rb)}",float(d)))

    # Write the entire comparison structure after applying the same rigid-body transform.
    st=read_structure(comparison)
    for model in st:
        for chain in model:
            for residue in chain:
                for atom in residue:
                    xyz=np.array([atom.pos.x,atom.pos.y,atom.pos.z],dtype=float)
                    out=(xyz-mob_center)@rot+ref_center
                    atom.pos=gemmi.Position(float(out[0]),float(out[1]),float(out[2]))
    ensure_dirs(); target=CACHE_DIR/f"aligned_compare_{uuid.uuid4().hex[:12]}.pdb"; st.write_pdb(str(target))
    return StructureComparisonResult(current_chain,comparison_chain,len(pairs),float(identity),rmsd,disp,target)
