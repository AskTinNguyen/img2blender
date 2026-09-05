# Independent visual review and bounded correction

Read this file before the first visual pass and again after a plateau, oscillation, or hard-gate
failure.

## Contents

1. Role separation
2. Deterministic evidence packet
3. Universal visual checklist
4. Structured critic report
5. Bounded rounds and stop rules
6. Prompt templates
7. Separate-thread handoff

For scoped redesign, numeric constraints and concealed attachments, also use
[constrained-refinement.md](constrained-refinement.md). The declared validation scope determines
what must be established; it cannot waive a critical feature after seeing a failed result.

## 1. Role separation

Use three bounded roles:

- **Builder**: author the current Blender pass, render deterministic evidence, and correct exactly
  one root cause selected by the critic. The builder cannot score or approve its own pass.
- **Independent Visual Critic**: use a fresh subagent or fresh context that did not author the
  current pass. Judge only the supplied reference, contract excerpt, current evidence, and previous
  comparison. Return the schema-v2 report; do not edit the `.blend`.
- **Forensic/Subject-Matter Critic**: optionally inspect a narrow ambiguity such as anatomy,
  architecture, vehicle construction, optical material behavior, scan provenance, or contradictory
  evidence. Do not let this role replace the independent visual critic.

Give every builder, critic, and context a stable ID. The state controller rejects a critic ID that
matches the builder, a reused critic identity on the same pass, or any reused critic context.

Prefer subagents for these bounded roles. A builder subagent owns only the current pass correction;
an independent critic owns only the report. Tell every subagent that it is not alone in the
workspace and must not revert unrelated edits.

## 2. Deterministic evidence packet

Preserve camera transforms, render settings, seed, resolution, display transform, and filenames
between rounds. Supply only evidence needed to judge the current pass:

- admitted source images and the relevant reconstruction-contract rows;
- `reference-match`: matched-camera render;
- `reference-overlay`: controlled overlay plus difference or side-by-side;
- `clay-silhouette`: untextured form/silhouette view;
- `orbit-left` and `orbit-right`: meaningful, non-degenerate three-quarter views;
- `back` when the contract marks it relevant;
- `neutral-material`: neutral broad-light material view;
- `grazing-light`: low-angle view exposing bevel, roughness, tiling, normals, and displacement;
- `critical-closeup:<feature-id>` for every critical feature reviewed in the pass;
- `previous-iteration`: fixed-camera previous/current comparison.

Treat evidence roles as case-insensitive tokens and store/compare them in lowercase. A critic may
cite `critical-closeup:D01`, but the admitted role and manifests record
`critical-closeup:d01`; the feature review ID itself remains the case-sensitive `D01`.

For architecture/environment also supply `ortho-front`, `ortho-left`, `ortho-right`, `ortho-back`,
and `ortho-top`. These prove layout, visible elevations, roofs, supports, access, terrain contact,
and back-side construction. Use additional closeups for circulation, façades, windows/interiors,
population, signage, and repeated systems when the wide views cannot judge them.

The first visual pass still needs `previous-iteration`: use the start-of-pass checkpoint as the
previous state. Never substitute the source image for the previous reconstruction.

Build comparisons:

```bash
python3 <skill-root>/scripts/build_review_comparisons.py \
  --reference <reference.png> \
  --current <current-reference-render.png> \
  --previous <start-or-prior-reference-render.png> \
  --out-dir <project>/reviews/<pass>/round-<n>
```

The comparison tool refuses dimension mismatches instead of silently rescaling framing evidence.

Render role-tagged cameras:

```bash
blender --background <checkpoint.blend> \
  --python <skill-root>/scripts/render_review_views.py -- \
  --out-dir <project>/renders/<pass>/round-<n> \
  --all-tagged \
  --required-role reference-match \
  --required-role clay-silhouette \
  --required-role orbit-left \
  --required-role orbit-right \
  --required-role neutral-material \
  --required-role grazing-light
```

Use a separate scene/view-layer/material override when a role needs a different rig or clay
material. Set `img2blender_view_layer` on the evidence camera. A clay view layer must have a material
override; neutral/grazing cameras require `img2blender_light_rig="neutral"` or `"grazing"`.
Orthographic roles require actual orthographic cameras. The render manifest records the checkpoint
hash, render hashes, camera matrices, view layer, overrides, rigs, and render settings; the state
controller cross-checks it and the comparison manifest before accepting any critic report.

### Concealed details and ineffective views

An isolated part proves its modeled detail, not installed fit. Plan a retained-neighbor section
when the assembled interface is hidden. After one unjudgeable closeup, diagnose whether the issue
is evidence, geometry, or missing external information; do not spend repeated rounds rendering
the same occlusion. Use `inspectionPlan` and camera provenance from the refinement guide.
The critic must judge actual pixels; names, render-enabled neighbors and numeric metadata do not
prove visibility or contact.

## 3. Universal visual checklist

Evaluate every item on every visual pass. Mark an item `not-applicable` only with a concrete reason.
Later-pass concerns may be provisionally judged against the current pass scope, but they may not be
omitted.

1. `camera-framing`: lens family, perspective/orthographic choice, transform, crop, occupancy,
   landmark reprojection, and locked reference camera.
2. `silhouette-proportion`: outer contour, negative spaces, major ratios, asymmetry, and mass
   hierarchy.
3. `depth-cross-section`: thickness, taper, curvature, section shape, underside/back volume, and
   stability outside the reference camera.
4. `structural-attachment-contact`: hierarchy, sockets, overlaps, seams, supports, ground/contact
   shadows, clearances, and absence of floating, accidental fusion, or penetration.
5. `topology-shading`: normals, continuity, faceting, pinching, modifier behavior, non-manifold
   intent, UV/bake suitability, and deformation/export topology.
6. `material-physicality-tiling`: scale-correct reflectance, roughness, metal/dielectric behavior,
   transmission/SSS, independent channels, projection seams, repetition, and tiling.
7. `lighting-color`: neutral truth, reference-match key/fill/reflection structure, exposure,
   background, display transform, and absence of lighting baked into albedo.
8. `scale-cues`: known dimensions, human/repeated-standard cues, bevel/texture/detail scale, and
   unit consistency.
9. `environment-grounding`: terrain/floor integration, contact, gravity, atmospheric placement,
   reflections, occlusion, and horizon/perspective agreement.
10. `narrative-detail-density`: source-specific wear, use, population, props, signs, asymmetry,
    detail hierarchy, and avoidance of generic category filler.
11. `presentation`: readable views, uncropped critical regions, clean noise level, comparison
    labeling, consistent settings, and defect-revealing lighting.
12. `delivery-integrity`: checkpoint provenance, file links, textures/color spaces, naming,
    collections, scale/origins, UVs, exports, manifests, and audit status.

Also evaluate every checklist item for each selected subject route in
[subject-routes.md](subject-routes.md). Hard gates override all scores.

## 4. Structured critic report

Use this required shape. Include all universal items and all selected subject-route items.

```json
{
  "schemaVersion": 2,
  "contractSha256": "<pinned reconstruction-spec SHA-256>",
  "checkpointSha256": "<reviewed .blend SHA-256>",
  "critic": {
    "id": "critic-p03-r02",
    "contextId": "fresh-agent-or-thread-id",
    "role": "independent-visual-critic",
    "authoredCurrentPass": false
  },
  "decision": "refine-scene",
  "viewEvidence": [
    {
      "role": "reference-match",
      "kind": "render",
      "path": "/absolute/path/reference-match.png",
      "judgeable": true,
      "notes": "Camera and silhouette are legible."
    }
  ],
  "evidenceSufficiency": {
    "sufficient": true,
    "missingOrUnjudgeable": [],
    "rationale": "All contract-required views and closeups are readable."
  },
  "scorecard": {
    "overall": 0.81,
    "aggregation": "hard-gates-then-weighted-judgment",
    "priorityWeights": {
      "identity-and-silhouette": 0.45,
      "depth-and-structure": 0.35,
      "surface-and-presentation": 0.2
    },
    "overallRationale": "Not a blind mean: identity and cross-section dominate this pass.",
    "layers": {
      "camera-framing": 0.9,
      "silhouette-proportion": 0.86,
      "depth-cross-section": 0.74,
      "structural-attachment-contact": 0.8,
      "topology-shading": 0.78,
      "material-physicality-tiling": 0.72,
      "lighting-color": 0.8,
      "scale-cues": 0.75,
      "environment-grounding": 0.8,
      "narrative-detail-density": 0.7,
      "presentation": 0.88,
      "delivery-integrity": 0.82
    }
  },
  "deltaFromPrior": {
    "overall": 0.03,
    "criticalFeatures": {"vent-profile": 0.04},
    "summary": "Silhouette improved; rear section remains too round."
  },
  "universalChecklist": [
    {
      "id": "camera-framing",
      "status": "pass",
      "evidenceRoles": ["reference-match", "reference-overlay"],
      "notes": "Locked camera and landmarks agree."
    }
  ],
  "subjectChecklist": [
    {
      "id": "profile-cross-sections",
      "status": "fail",
      "evidenceRoles": ["orbit-left", "orbit-right", "clay-silhouette"],
      "notes": "Rear section is cylindrical rather than flattened."
    }
  ],
  "hardGates": [
    {
      "id": "multi-view-consistency",
      "status": "fail",
      "evidenceRoles": ["orbit-left", "orbit-right"],
      "finding": "Reference-facing match collapses in the right orbit."
    }
  ],
  "criticalFeatures": [
    {
      "id": "vent-profile",
      "score": 0.84,
      "visible": true,
      "supported": true,
      "attached": true,
      "freeOfIntersection": true,
      "multiViewConsistent": false,
      "onlyReferenceCamera": true,
      "evidenceRoles": ["critical-closeup:vent-profile", "orbit-right"],
      "notes": "Spacing matches, but depth exists only in the matched view."
    }
  ],
  "highestImpactFinding": {
    "id": "rear-cross-section",
    "rootCause": "Primary housing section profile is too circular.",
    "affectedContractIds": ["housing-depth", "vent-profile"],
    "correctionBrief": "Flatten the rear section without changing camera, material, or lighting."
  },
  "trajectory": {
    "status": "improving",
    "rationale": "Score rose 0.03 without degrading orbit views."
  }
}
```

For the first round, set `deltaFromPrior.overall` to `null` and trajectory to `first-round`.
The state controller recomputes later overall deltas. A passing overall score cannot override a
failed hard gate, insufficient evidence, or a critical feature that is below threshold, invisible,
unsupported, unattached, intersecting, inconsistent across views, or correct only from the
reference camera.

## 5. Bounded rounds and stop rules

Use this sequence on every visual pass:

1. Assign one builder and save the start-of-pass checkpoint.
2. Render the complete fixed evidence set.
3. Dispatch a fresh independent critic with only the bounded packet.
4. Record the critic report.
5. If the decision is a refinement, have the assigned builder correct only
   `highestImpactFinding.id`, record exact Blender data changed, and save a new checkpoint.
6. Rerender the identical roles and dispatch a fresh critic identity/context.
7. Continue only when the controller accepts every gate.

Use `open-pass` before editing to pin the actual pre-pass `.blend` and its baseline matched-camera
render. The first `previous-iteration` input must hash-match that baseline; later ones must
hash-match the preceding critic round. The comparison reference must hash-match an admitted pinned
reference. The controller also requires invariant render settings between rounds and resolves every
checklist/hard-gate/critical-feature `evidenceRoles` citation to admitted files.

Record a visual review with `--checkpoint`, `--render-manifest`, and `--comparison-manifest` plus
all role-qualified `--render`/`--comparison` paths. The checkpoint must match the manifest hash and
the latest recorded correction. On `continue`, every required view must be positively judgeable,
and every universal checklist, subject checklist, and hard gate must be `pass`; `not-applicable`
cannot satisfy advancement.

Require at least two independent rounds per visual pass for `complex` and `ultra`. The first round
must therefore select the highest-impact remaining defect; the second or later round independently
verifies the correction. Simple/moderate work still needs at least one independent critic.

Default maximum: four critic rounds per pass. Never evade the cap by renaming the same pass or
reusing a critic context.
The final permitted round may only `continue` or `stop`; another refinement or input cycle is
forbidden.

Stop or reroute under these conditions:

- **plateau**: absolute overall delta is below `0.02` for two consecutive corrected rounds;
- **oscillation**: one correction alternately fixes one view and breaks another, or revisits a
  prior parameter state;
- **repeated defect**: the same root cause survives a targeted correction;
- **evidence ceiling**: the next identity-bearing decision needs another view, measurement, map,
  specialist, or reconstruction method;
- **round cap**: four rounds are exhausted.

On plateau, oscillation, or repeated defect, use `refine-spec`, `request-input`, or `stop`; do not
continue local scene/camera tweaking. On evidence ceiling, request the smallest missing input. The
controller rejects `continue` and further local correction when the report declares plateau or
oscillation.

Record `refine-spec` with the typed `revise-spec` transition after validation; never satisfy it with
a `.blend` change. Record resumed input with hashed artifacts. Contract/reference hashes are pinned
at intake, and every state transition is appended to a hash-chained ledger.

On a conditional stop, deliver separate statements for visual acceptance, technical checks, and
unresolved evidence. Preserve the stopped state and its reason. A high visual score does not
change controller status, and a concealed interface is not automatically a demonstrated defect.

## 6. Prompt templates

### Builder

```text
Role: Builder for img2blender pass <pass-id>.
Ownership: only <checkpoint/scene components for this pass>. You are not alone in the workspace;
do not revert unrelated edits.
Inputs: reconstruction-contract rows <ids>, admitted references <paths>, prior checkpoint <path>,
critic highestImpactFinding <exact object>.
Task: correct only root cause <id>. Do not change camera/material/lighting unless the root cause
explicitly names that group. Record exact objects, modifiers, nodes/sockets, sculpt regions, UVs,
textures, cameras, or lights changed. Save a new versioned checkpoint and rerender the same evidence
roles. Do not score or approve the pass.
Return: change list, checkpoint path, render manifest, remaining known differences.
```

### Independent Visual Critic

Include declared `taskMode`, `validationScope`, reference authorities, relevant invariant results
and inspection intent in the packet. Separate numerical failure from an unjudgeable view. Do not
add manufacturing or full-motion requirements to a visual-asset task late in review. Do not waive
any pinned critical relationship or infer assembly fit from an isolated hardware image.

```text
Role: Independent Visual Critic. You did not author this pass and must not edit the scene.
Judge only the supplied admitted references, reconstruction-contract excerpt, current deterministic
evidence, and previous-iteration comparison. Do not infer success from filenames or builder claims.
Evaluate every universal and selected subject-route checklist item. Verify every hard gate and
critical feature across views. Compute delta against the supplied prior round. Choose exactly one
decision and one highest-impact root cause. Overall is weighted judgment, never a blind average;
hard gates override it. Return only a schema-v2 critic report plus a one-sentence verdict.
```

### Forensic/Subject-Matter Critic

```text
Role: Forensic/Subject-Matter Critic for <narrow question>.
Inspect only <specific evidence and contract rows>. Distinguish observation from domain prior.
Return: supported findings, contradictions, confidence, smallest missing evidence, and whether the
reconstruction contract or subject checklist must change. Do not approve the pass or edit Blender.
```

## 7. Separate-thread handoff

Use a separate user-visible thread only when the user explicitly wants that coordination surface.
Send the same bounded critic prompt and evidence paths, not the whole builder conversation. Record
the created thread/context ID as `critic.contextId`. When it returns:

1. save its raw schema-v2 report under `reviews/<pass>/round-<n>/critic-report.json`;
2. record it through `reconstruction_pipeline.py review`;
3. give only `highestImpactFinding` plus relevant contract rows to the builder;
4. record the correction through `reconstruction_pipeline.py correct`;
5. resume in the original thread with the updated state path and checkpoint.

Never ask the critic thread to continue building, and never send the critic the intended score,
suspected fix, or prior private reasoning.
