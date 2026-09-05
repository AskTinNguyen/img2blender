# img2blender updates

## 2026-09-05 — constrained redesign and component refinement

The Jade Threshold door project exposed a gap between a visual requirement such as “equal glass
openings” and what the numerical checker actually measured. It also showed that repeated closeups
of a concealed hinge cannot establish installed fit. This update adds explicit measurement and
inspection contracts while keeping the existing independent review gates and round limits.

### Behavior added

- Optional schema-v2 task modes and reference authority for faithful reconstruction and authorized
  redesign. New projects record validation scope; existing projects retain their prior behavior.
- Executable invariants for dimensions, exact named target counts, numeric properties and sampled
  rotations. Opening dimensions use real evaluated mesh vertex groups. Controller advancement
  requires complete passing evidence pinned to the current scene, contract and pass. All declared
  invariants are checked again at final delivery even if intermediate passes are narrowed.
- Inspection plans distinguish assembled, isolated and section views. Isolated views cannot claim
  installed fit. Manifest provenance identifies retained neighbors and disclosure; the renderer
  rejects excluded, hidden, holdout or camera-invisible declared neighbors.
- Component refinement records hash-checked baseline files, changed components and interfaces,
  and requires an integrated context render. Building-level changes retain the full architecture
  route. No automatic stale-render reuse or critic-counter reset was introduced.
- Portable render preflight checks a tiny disposable Cycles scene, detects devices, and retries
  failed GPU attempts in a fresh CPU process. It records actual probe devices separately from
  source scene settings. The observed Metal workaround remains explicit and process-local.
- Delivery packaging accepts explicit project-relative inputs, hashes archive contents, and verifies
  the archive before replacing the output. Packaging does not substitute for reopening Blender files.

### Verification

The original 18 controller/comparison tests passed before modification. The final expanded suite
passes all **60 tests**. Expanded tests cover
absolute expectations (including equal-but-wrong peers), malformed and nonfinite values, stale and
mislabelled reports, controller advancement, reference authority, scoped baselines, inspection
provenance, crashes/timeouts/fallback, and archive integrity. Blender integration fixtures exercise
actual evaluated modifiers, transformed coordinate frames, opening boundary groups and drivers.
The new checker also passed four invariant groups on the actual door file: both pairs of pane
dimensions and both hinge pivots at baseline plus 30, 57 and 90 degree inputs. Opening-boundary
checks are independently exercised in the fixture; pane checks are not labelled opening checks.
CPU and Metal preflight smoke tests passed against the delivered door file on the local Blender
5.2.0 LTS build; its SHA-256 remained unchanged. No all-version compatibility claim is made.

### Assessment using the skill-improvement rubric

These are editorial assessments, not benchmark measurements or a claim that every existing API
has been independently revalidated. The baseline uses the prior skill and six focused retrospective
reviews; the updated assessment adds readback, tests and independent code/document review.

| Criterion | Before | After | Reason |
|---|---:|---:|---|
| Structure and conformance | 14/15 | 14/15 | Existing structure preserved; entry point remains below 500 lines. |
| Description | 7/10 | 7/10 | Existing broad description deliberately retained. |
| Accuracy and freshness | 17/20 | 18/20 | Local runtime exercised; measurement and provenance claims narrowed. |
| Actionability | 15/20 | 19/20 | Runnable assertions, scoped validation and explicit fallback behavior. |
| Progressive disclosure | 11/15 | 11/15 | New detail lives in one linked guide; existing controller remains large. |
| Examples and patterns | 7/10 | 9/10 | Door invariants, rig samples, cutaway contract and tested failure cases. |
| Conciseness | 7/10 | 6/10 | Additional schemas and tools add length, kept outside the entry point. |
| Total | 78/100 | 84/100 | Targeted improvement; no wholesale restructuring. |

### Deliberate limits

Vertex spans prove dimensions, not profile curvature or the semantic correctness of a selected
boundary group. A numeric property proves that property, not the geometry it describes. Render-enabled
neighbors establish provenance, not unoccluded pixels or physical contact. Independent visual
judgment remains mandatory. Scope labels do not implement mechanical certification or waive pinned
critical features. Reports with unresolved critical evidence remain conditional/stopped.
