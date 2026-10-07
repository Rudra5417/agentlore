# Hazards

<!-- agentlore: one entry per '## ' heading -->

## an sdist ships untracked files unless MANIFEST.in prunes them
<!-- agentlore
id: HAZ-2026-10-07-e6a2
type: hazard
status: accepted
anchors: MANIFEST.in
owner: maintainer
enforcement: tests.yml, package job (asserts the sdist carries only tracked files)
author: Rudra5417
created: 2026-10-07
verified_at: f3fee94
anchor_hash: 7bd6fbf2cd75232b
anchor_norm: f7b1afee155f5bd0
-->

sdist file discovery does not consult .gitignore, so bench run output, .test-failures/ and agentlore.egg-info shipped silently until MANIFEST.in pruned them. Anything .gitignore hides has to be mirrored here, or the source tarball carries someone's local scratch state.


## git diff needs --relative or anchors never match from a subdirectory
<!-- agentlore
id: HAZ-2026-10-07-4365
type: hazard
status: accepted
anchors: agentlore
owner: maintainer
enforcement: tests/test_agentlore.py, TestSubdirectoryLayout
author: Rudra5417
created: 2026-10-07
verified_at: f3fee94
anchor_hash: 0fa0c6e0cb3d0198
anchor_norm: e5d8fb0fc7b639ac
-->

git reports paths relative to the repo ROOT, but anchors and .memory/ paths are relative to the WORKING DIRECTORY, which is the memory root. Without --relative the two never match whenever agentlore runs from a subdirectory, so the change-scoped check sees nothing. git ls-files --others is already cwd-relative, which is how the inconsistency hid.
