# Dead ends

<!-- agentlore: one entry per '## ' heading -->

## setuptools auto-discovery claimed site/ and broke the release build (settled)
<!-- agentlore
id: DEAD-2026-10-07-4fbd
type: dead-end
status: accepted
anchors: pyproject.toml
evidence: publish run 37552779568; fixed in 6e7f584
author: Rudra5417
created: 2026-10-07
verified_at: f3fee94
anchor_hash: d0969c35bbc522f9
anchor_norm: 8859880330c1f593
resolved_by: 6e7f584
-->

In a flat layout setuptools treats every top-level directory as a package. Once site/ existed, uv build failed with 'Multiple top-level packages discovered in a flat-layout: [site, bench]' -- but only at release time, because the directory was new and no earlier build had seen it. packages = [] and py-modules = [] stop discovery from running at all.
