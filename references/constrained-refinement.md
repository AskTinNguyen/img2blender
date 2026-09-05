# Constrained redesign and component refinement

Use this extension when a user changes design direction, declares exact repeated geometry, or asks
to refine one component of an existing scene. The schema-v2 additions are optional for existing
projects; new `init` commands emit task mode, validation scope, invariant and inspection fields.
They do not waive critical-feature gates, reset critic counters, or certify prior work retroactively.

## 1. Establish intent and reference authority

Initialize with `--task-mode faithful-reconstruction|constrained-redesign|creative-redesign` and
`--validation-scope visual-asset|animated-assembly|fabrication`. Defaults preserve faithful
reconstruction and visual-asset scope.

For either redesign mode, fill all three `designIntent` strings:

```json
{
  "taskMode": "creative-redesign",
  "validationScope": "visual-asset",
  "designIntent": {
    "authorization": "User permits a new door design and generated design references.",
    "preservedRequirements": "Four equal visible glass openings; retain the entrance fit.",
    "allowedChanges": "Door ornament, material treatment, moldings and hardware styling."
  }
}
```

Each redesign reference also needs an `authority`: `geometry-evidence`, `design-proposal`,
`material-inspiration`, or `context`. Record source type, version, prompt provenance and scope in
reference metadata. A generated concept normally has `authority: design-proposal`; it does not
establish measured real-world dimensions or unseen mechanical construction.

Apply this precedence: latest explicit user constraints, earlier compatible user requirements,
the selected design reference within its assigned scope, contextual references, then inference.
Carry the same constraint IDs into ImageGen prompts, the Blender contract and critic packets.
A change in direction already authorized by the user needs no additional design-approval gate.

When using ImageGen, follow the installed imagegen skill. Inspect the generated image, save the
selected version and its prompt, admit its hash, and mark superseded versions clearly. For repeated
openings, develop a straight-on design view with unobscured boundaries before ornament detail.
An apparently orthographic generated image remains design intent unless projection is established.

Do not silently edit a pinned contract. Before intake, update and validate directly. After intake,
use the existing typed `refine-spec`/`revise-spec` or input-resolution transitions. A genuinely new
component-redesign task can start a separate scoped project referencing the earlier deliverable;
retain its history and do not rename the same stalled pass to evade the round cap.

## 2. Scope component work without re-auditing the entire building

Select `subjectRoutes` for the components being changed. A door in a building can use
`hard-surface-prop` and `transparent-translucent`. Record its existing architectural scene as
context. Add `refinementScope`:

```json
{
  "refinementScope": {
    "changedComponents": ["door-left", "door-right", "fixed-frame"],
    "affectedInterfaces": ["frame-to-wall", "leaf-to-hinge", "leaf-to-threshold"],
    "baselineCheckpoint": {"path": "/project/entrance.blend", "sha256": "<actual SHA-256>"},
    "baselineEvidence": {"path": "/project/entrance-review.json", "sha256": "<actual SHA-256>"},
    "rationale": "Door assembly changes; building layout and supporting structure are outside this edit."
  }
}
```

Both baseline records must exist and hash-match. Add `integration-context` to required views;
the controller requires this role for component refinements. Keep the normal component evidence,
critical closeups, before/after comparison and independent review minimum. Complexity describes the
change being made, not the size of the containing scene.

If layout, major structural connections, circulation or building mass changes, use the full
`architecture-environment` route, omit `refinementScope`, and retain its orthographic/back checks.
The controller rejects combining that route with a narrowed component refinement.

Prior evidence establishes the baseline; it does not prove the changed asset. This version does
not automatically reuse old renders as current-pass evidence. Generate current evidence with the
current checkpoint hash. This avoids a supposed optimization silently accepting stale geometry.

## 3. Express measurable requirements as invariants

Use one shared construction parameter for intentionally identical parts. Separately test each
required measurement against its absolute expected value. Four equal but wrong objects must fail.

Distinguish:

- `pane`: physical glass geometry;
- `rough-opening`: the actual structural cutout boundary;
- `visible-opening`: the clear opening bounded by installed trim;
- `component`: another geometric part;
- `rig`: a rotation or numeric control requirement.

Add `geometryInvariants` rows. Each `featureId` must name an observed/user-constrained feature in
`referenceAnalysis.observedFeatures`, with the normal feature-contract mapping. Allowed kinds are
`dimensions`, `count`, `property`, and `rotation`.

```json
{
  "id": "four-pane-size",
  "featureId": "equal-openings",
  "measurement": "pane",
  "kind": "dimensions",
  "targets": ["Glass L1", "Glass L2", "Glass R1", "Glass R2"],
  "frame": "Closed assembly datum",
  "expected": [0.710, 0.0285, 3.490],
  "tolerance": 0.00001,
  "applicablePasses": ["secondary-form", "topology-uv", "materials", "lighting", "microdetail", "final-delivery"]
}
```

`targets` are exact object names, not glob patterns. A named frame is an exact scene object; its
inverse evaluated transform expresses measurements in that frame. `object-local` instead measures
untransformed local coordinates; use a named unscaled assembly datum when scene scale matters.
Dimensions are evaluated mesh-vertex spans ordered X, Y, Z in the declared frame. Modifiers apply.
Specify scene units; the numeric checker does not convert them into meters automatically.
`applicablePasses` selects intermediate checks; every declared invariant is always required again
at `final-delivery`. Retire a temporary construction requirement through a typed contract revision,
not by excluding the final pass.

For opening dimensions, `vertexGroup` is mandatory. Assign it to the actual boundary vertices on
the evaluated leaf or surround. Use separate rows/groups for separate openings. Measure all groups
in compatible leaf/datum frames, in a defined closed pose. An arbitrary proxy object or a group
containing the glass is not opening evidence; the critic checks the semantic mapping.

Bounding spans establish size, not curvature, profile identity, clearance, or watertightness.
Retain front/clay/oblique checks for the capsule profile and installed relationship. Do not label a
numeric custom property as geometric proof: `property` checks only its declared metadata value.
`count` checks the exact named target set, not whether additional similarly named objects exist.
For `count`, use expected integer equal to the target-list length and tolerance zero.

Rotation rows use evaluated XYZ Euler radians in the declared frame, with componentwise absolute
tolerance. Use one row per opposite-moving leaf, baseline `expected`, and optional samples:

```json
{
  "id": "left-opens-57",
  "featureId": "opening-motion",
  "measurement": "rig",
  "kind": "rotation",
  "targets": ["Left hinge pivot"],
  "frame": "object-local",
  "expected": [0, 0, 0],
  "tolerance": 0.00001,
  "samples": [{
    "controlObject": "Open angle control",
    "inputProperty": "opening_degrees",
    "inputValue": 57,
    "expected": [0, 0, 0.9948376736]
  }],
  "applicablePasses": ["secondary-form", "final-delivery"]
}
```

The checker restores sampled control values and never saves the scene. Sampled angles prove those
poses, not continuous swept clearance. `animated-assembly` and `fabrication` scopes must declare
any additional motion/load/tolerance evidence in their quality contract before review.

Run inside Blender, using paths appropriate to the project:

```bash
blender --background project/doors.blend --python-exit-code 1 \
  --python <skill-root>/scripts/check_geometry_invariants.py -- \
  --spec project/reconstruction-spec.json --pass-id final-delivery \
  --out project/reviews/geometry-invariants.json
```

Expected result: one measured row per applicable invariant, no measurement errors, and every
expected-value comparison passes. The report pins the scene and spec hashes and pass ID. Add
`--invariant-report project/reviews/geometry-invariants.json` to the normal controller `review`
command. `continue` requires this report whenever applicable invariants exist; stale, missing,
nonfinite, mislabelled and falsely successful evidence cannot advance. Numerical failures may be
recorded with `refine-scene` or `stop`; failures never satisfy `continue`.

## 4. Plan concealed-detail inspection before expensive critique rounds

Use the smallest view that answers the question:

| View | Can establish | Cannot establish alone |
|---|---|---|
| Assembled | Visible placement, contact, scale | Occluded interfaces |
| Isolated | Actual component geometry and detail | Fit after neighbors are removed |
| Installed section/cutaway | Contact and clearance with neighbors retained | Full motion or load behavior |

Add an optional `inspectionPlan`. Its roles become required evidence. For example:

```json
{
  "inspectionPlan": [{
    "featureId": "hinge-contact",
    "views": [{
      "role": "section:hinge-contact",
      "mode": "section",
      "proves": "installed-fit",
      "retainedNeighbors": ["Left hinge plate", "Leaf section", "Jamb section"]
    }]
  }]
}
```

The controller forbids `mode: isolated` with `proves: installed-fit`. Before continuing, it checks
render-manifest inspection mode, disclosure and retained-neighbor names. The renderer checks that
those objects are present and enabled for rendering in the selected view layer. This is provenance,
not a guarantee of pixel visibility; the critic must still judge occlusion and contact.

Prepare a non-destructive review view layer or diagnostic scene variant retaining the interface.
The renderer does not automatically cut geometry or hide objects based on tags. On the camera set:

```python
camera['img2blender_inspection_mode'] = 'section'
camera['img2blender_inspection_disclosure'] = 'Leaf and jamb sectioned to expose the installed hinge interface.'
camera['img2blender_retained_neighbors'] = '["Left hinge plate", "Leaf section", "Jamb section"]'
camera['img2blender_view_layer'] = 'Hinge section'
```

After one unjudgeable view, classify the problem: bad evidence, a geometric defect, or missing
external reference. Repair a bad camera/cutaway before another full batch. Request new user input
only when the existing scene and admitted references cannot supply the required information.

## 5. Keep scope and stopping decisions honest

For `visual-asset`, assess the declared visible/structural requirements. For `animated-assembly`,
include the specified motion range and collision tests. For `fabrication`, name dimensions,
tolerances, topology and engineering deliverables. Scope labels alone do not implement those checks
or exempt concealed critical interfaces. Do not silently downgrade an existing contract at the cap.

At conditional stop, report independently:

1. visual result achieved;
2. technical checks passed;
3. unresolved relationship and evidence needed to assess it.

Door example: "Four equal panes and the rendered redesign are verified. An isolated hinge view
shows its modeled detail. Installed hinge fit remains unverified because the adjoining geometry
obscures it; a retained-neighbor section would resolve that evidence gap." Do not turn an unknown
into a defect, manufacture a pass, or present a high visual score as formal controller completion.
