# Known limitations

- Automatic sequence-to-structure uses an external public ESMFold service and therefore requires network access; service availability and latency are outside Protein Lab's control.
- The rapid automatic fold-prediction route is currently limited to 400 residues by Protein Lab.
- Predicted coordinates are not experimental structures and are not literal physical folding trajectories.
- Protein Lab does not currently perform full constant-pH molecular dynamics or rigorous residue pKa estimation.
- Arbitrary ligands/nonstandard residues are not silently parameterized. Simulation requires compatible force-field parameters.
- Hydrogen-bond analysis is an explicit-hydrogen geometric screen, not a full protonation/quantum-chemical interaction model.
- SASA uses a Shrake-Rupley geometric accessibility calculation and is not solvation free energy.
- Structural validation is transparent local geometry QC, not a replacement for the complete wwPDB/MolProbity validation ecosystem.
- Free-energy landscapes derived from occupancy require adequate equilibrium sampling; short trajectories can be misleading.
- Production-scale MD can exceed the practical memory/compute envelope of an interactive desktop application. Protein Lab warns about large trajectories but does not pretend to replace HPC workflow managers.
- The current membrane builder assumes the protein is already correctly oriented for the membrane convention used by OpenMM.
- Research conclusions remain the responsibility of the investigator; software PASS status does not establish a biological claim.
