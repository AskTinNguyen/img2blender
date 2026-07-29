---
name: img2blender
description: Reconstruct specific objects, architecture/environments, products/vehicles, hard-surface props, organic subjects, humans/characters, cloth/hair, botanical systems, transparent assets, or generated/scanned imports from reference images as evidence-backed Blender assets. Use for image-to-Blender reconstruction, camera matching, staged modeling/sculpting, look development, retopology/UV/export, multi-view validation, or improving a .blend through strict independent visual critique rather than one-camera resemblance.
---

# img2blender

Reconstruct the particular visible subject as a defensible three-dimensional Blender asset. Treat
every image as incomplete projection evidence. Optimize for multi-view fidelity, structural logic,
physical material response, and delivery integrity—not a front-camera illusion.

## Non-negotiable rules

- Separate observation, inference, and artistic completion. Cite admitted reference IDs.
- Map every observed particular feature to an exact Blender implementation, subject checklist item,
  review camera, confidence, and evidence source. Generic category resemblance cannot pass.
- Advance only the unlocked pass. Save a versioned checkpoint before and after each correction.
- Never let the builder score or approve its own current pass.
- Dispatch a fresh Independent Visual Critic for every critique round. Give it only the admitted
  references, relevant contract rows, deterministic render evidence, and prior comparison.
- Let the assigned builder correct exactly the critic's single highest-impact root cause. Then
  rerender the same evidence roles and dispatch a fresh critic identity/context.
- Require at least two independent critic rounds on every visual pass for `complex` and `ultra`
  work. Never exceed the configured cap.
- Treat hard gates as overrides. Never average away an invisible, unsupported, floating,
  intersecting, below-threshold, or reference-camera-only critical feature.
- Preserve non-destructive source geometry and disclose hidden/inferred regions.

## Read before acting

Read these files completely at the indicated point:

1. Always read [intake-and-contract.md](references/intake-and-contract.md) before geometry.
2. Always read [blender-build-guide.md](references/blender-build-guide.md) before choosing a build
   route or editing a `.blend`.
3. Read every selected route in [subject-routes.md](references/subject-routes.md) before filling the
   reconstruction contract.
4. Read [review-and-critique.md](references/review-and-critique.md) before the first visual review
   and after any hard-gate failure, plateau, or oscillation. Use its exact role prompts and report
   schema.

## Initialize or resume

Locate the Blender executable without assuming it is on `PATH`. Do not touch an existing project
outside the user-authorized directory.

Check state:

```bash
python3 <skill-root>/scripts/reconstruction_pipeline.py status \
  <project>/reconstruction-state.json
```

Initialize with every applicable subject route:

```bash
python3 <skill-root>/scripts/reconstruction_pipeline.py init \
  --project-dir <project> \
  --name "<specific subject>" \
  --reference <primary-image> \
  --reference <other-image> \
  --target hero-render \
  --complexity complex \
  --subject-route hard-surface-prop
```

Initialization creates schema-v2 state/spec files plus `blender`, `renders`, `reviews`, and
`exports`. Fill the reconstruction contract, then validate:

```bash
python3 <skill-root>/scripts/reconstruction_pipeline.py validate \
  <project>/reconstruction-state.json
```

Record intake only after validation passes:

```bash
python3 <skill-root>/scripts/reconstruction_pipeline.py review \
  <project>/reconstruction-state.json \
  --pass-id intake \
  --action continue \
  --summary "<suitability, evidence, uncertainty, and exact feature coverage>" \
  --artifact <project>/reconstruction-spec.json
```

For schema-v1 projects, run `migrate` first. It creates `.v1.json` backups, preserves legacy status
only as non-authoritative history, and resets the canonical pass machine to intake. Fill subject
routes, checklist mappings, explicit implementation targets, and view relevance, then revalidate
every pass; legacy completion is never grandfathered.

## Build the reconstruction contract

At macro, meso, and micro scales record:

- target classification, subject routes, topology families, symmetry, scale, and camera clues;
- component hierarchy, dimensions/ratios, cross-sections, attachments, contacts, and hidden regions;
- PBR material regions and independent channels;
- critical features and hard failure modes;
- every particular count, ratio, profile break, opening, asymmetry, mark, pattern, wear region,
  layout relationship, activity, prop, sign, or material boundary that identifies this source.

Create one `referenceAnalysis.observedFeatures` row for each particular, then exactly one
`featureContract` mapping to:

- `geometry`, `material-mask`, `decal`, `node-system`, `displacement`, `texture`, or documented
  `deferred`;
- the exact scene target;
- applicable subject checklist IDs;
- deterministic review cameras, including `critical-closeup:<feature-id>` when critical;
- confidence and admitted reference IDs.

Keep feature IDs case-sensitive in the contract, but treat all evidence roles as case-insensitive
and store them canonically in lowercase. For example, feature `D01` uses the canonical evidence
role `critical-closeup:d01`; CLI, camera tags, manifests, and critic citations may supply either
case and are normalized before comparison.

Keep `qualityContract.criticalFeatures` identical to the feature mappings marked critical. Define
thresholds, back relevance, complete view roles, failure modes, deliverables, and concrete
definition-of-done statements. Request more evidence when identity-bearing geometry, material,
text/pattern, scale, or contradictory sources cannot be resolved.

## Execute locked passes

Use the controller's `status` output as the source of truth.

### 1. Intake

Admit references, hash local files, distinguish observation from inference, select subject routes,
fill the exact reconstruction contract, and validate feature coverage.

### 2. Camera match

Solve sensor fit/FOV, lens, transform, roll, camera shift, framing, crop, landmark reprojection, and
object orientation. Tag and lock `reference-match`. Do not sculpt lens error into geometry.

### 3. Blockout

Build only major masses, outer contour, negative spaces, center of mass, and real front-to-back
depth. A material or microdetail cannot rescue this pass.

### 4. Primary form

Establish cross-sections, thickness, taper, curvature, plane changes, gesture/anatomical masses, and
construction axes. Verify back/underside volume.

### 5. Secondary form and assembly

Build every identity-bearing subassembly, seam, socket, overlap, support, fold family, hair mass,
panel, hardware system, opening, façade bay, access route, or repeated subsystem. Prove contacts and
clearances; do not paint geometry into a projection.

### 6. Topology and UV

Retopologize when deformation, real-time/export, subdivision, UV stability, or clean baking needs
it. Fix normals, accidental duplicates/internal surfaces, degenerate faces, negative/non-unit scale,
unintended non-manifold regions, topology shading, UV seams/density/padding, and map conventions.
Run the working scene audit.

### 7. Materials

Build evidence-backed Principled materials with independent base color, roughness, metalness,
normal/height, AO, masks, transmission/SSS/coat/anisotropy/emission as applicable. De-light
projection sources and bake to UVs. Inspect tiling, seams, and unseen-region continuation.

### 8. Lighting and color

Keep reference-match, neutral, grazing, and presentation rigs separable. Match direction, softness,
fill, reflections, contact shadow, exposure, environment, background, and display transform without
baking them into materials.

### 9. Microdetail

Add only source-supported geometry/displacement, pores, scratches, engraving, weave, chips, dust,
edge wear, strands, decals, signage, activity/detail density, and local surface variation. Judge at
delivery distance and critical closeups.

### 10. Final delivery

Run the final audit, render every contract view, open and test requested exports, verify packed or
documented texture links/color spaces, and deliver final plus non-destructive checkpoints,
manifests, critic records, scale/units/origins/naming/UV/export notes, provenance, and confidence by
region.

## Capture the same evidence on every visual pass

Create and preserve:

- `reference-match` render;
- `reference-overlay` comparison;
- `clay-silhouette` render;
- `orbit-left` and `orbit-right` renders;
- relevant `back` render;
- `neutral-material` render;
- `grazing-light` render;
- every `critical-closeup:<feature-id>`;
- `previous-iteration` comparison.

For architecture/environment also require `ortho-front`, `ortho-left`, `ortho-right`, `ortho-back`,
and `ortho-top` every visual pass. The controller lists exact required roles.

Build comparisons with:

```bash
python3 <skill-root>/scripts/build_review_comparisons.py \
  --reference <reference.png> \
  --current <reference-match.png> \
  --previous <previous-reference-match.png> \
  --out-dir <project>/reviews/<pass>/round-<n>
```

Render deterministic tagged cameras with:

```bash
blender --background <checkpoint.blend> \
  --python <skill-root>/scripts/render_review_views.py -- \
  --out-dir <project>/renders/<pass>/round-<n> \
  --all-tagged \
  --seed 230519
```

Set `img2blender_view_layer` on evidence cameras when a dedicated view layer is required. A
`clay-silhouette` view layer must have a material override. Tag `neutral-material` and
`grazing-light` cameras with `img2blender_light_rig="neutral"` and `"grazing"` respectively.
Orthographic evidence cameras must actually use Blender's orthographic camera type.

The render script hashes the `.blend` and every render and records camera matrices, view layer,
material override, light rig, scene variant, seed, and color/render settings. The controller
cross-checks that manifest plus the comparison manifest against the admitted checkpoint and evidence
before it accepts a critic report. Vision-based independent critics still decide visual quality.

## Run the independent critique/correction loop

Use the role prompts and exact critic-report schema in
[review-and-critique.md](references/review-and-critique.md).

1. Pin the builder, true pre-pass `.blend`, and its baseline reference render before editing:

```bash
python3 <skill-root>/scripts/reconstruction_pipeline.py open-pass \
  <project>/reconstruction-state.json \
  --pass-id <pass-id> \
  --builder-id <builder-id> \
  --start-checkpoint <pre-pass.blend> \
  --start-reference-render <pre-pass-reference-render.png>
```

The intake transition pins the validated spec and every reference hash. Later visual transitions
reject direct contract/reference mutation. Critic reports must include the controller-pinned
`contractSha256` and reviewed `checkpointSha256`.

2. Dispatch a fresh critic subagent that did not author the pass. Do not reveal the intended fix,
   expected score, or builder's private reasoning.
3. Save its raw report and record the review with role-qualified evidence:

```bash
python3 <skill-root>/scripts/reconstruction_pipeline.py review \
  <project>/reconstruction-state.json \
  --pass-id <pass-id> \
  --builder-id <builder-id> \
  --action refine-scene \
  --summary "<critic verdict>" \
  --critic-report <critic-report.json> \
  --checkpoint <reviewed-checkpoint.blend> \
  --render-manifest <render-manifest.json> \
  --comparison-manifest <comparison-manifest.json> \
  --render reference-match=<reference-match.png> \
  --render clay-silhouette=<clay.png> \
  --render orbit-left=<left.png> \
  --render orbit-right=<right.png> \
  --render neutral-material=<neutral.png> \
  --render grazing-light=<grazing.png> \
  --comparison reference-overlay=<overlay.png> \
  --comparison previous-iteration=<previous.png>
```

Add every controller-required back, orthographic, and critical-closeup role. Add `--audit` on
audit-gated passes.

4. Have the assigned builder correct only `highestImpactFinding.id`, then record exact changes:

```bash
python3 <skill-root>/scripts/reconstruction_pipeline.py correct \
  <project>/reconstruction-state.json \
  --pass-id <pass-id> \
  --builder-id <builder-id> \
  --root-cause-id <finding-id> \
  --summary "<causal correction and remaining risk>" \
  --changed "<object/modifier/node/socket/region and old→new value>" \
  --checkpoint <new-checkpoint.blend>
```

When the critic chooses `refine-spec`, do not use a Blender correction. Edit the contract, validate
it, then record a typed revision:

```bash
python3 <skill-root>/scripts/reconstruction_pipeline.py revise-spec \
  <project>/reconstruction-state.json \
  --pass-id <pass-id> \
  --builder-id <builder-id> \
  --root-cause-id <finding-id> \
  --summary "<contract correction>" \
  --spec <project>/reconstruction-spec.json
```

For `request-input`, resume only with hashed `--artifact` evidence; if that evidence changes the
contract, update and validate the spec before resume. The final permitted round allows only
`continue` or `stop`, preventing another input/correction cycle from deadlocking the pass.

5. Rerender identical roles and dispatch a fresh critic identity/context.
6. Record `continue` only when evidence is sufficient, all checklists/hard gates pass, every
   critical feature passes independently, score thresholds pass, the minimum round count is met,
   and no plateau/oscillation applies.

Use a separate user-visible thread only when the user explicitly requests it. Follow the bounded
evidence/resume procedure in the review reference.

## Stop, plateau, and oscillation

The default maximum is four critic rounds per pass. If two consecutive corrected rounds each change
overall score by less than `0.02`, declare plateau. If a correction alternates success between
views or revisits a prior state, declare oscillation. If the same defect survives its targeted
correction, treat it as a spec/route problem.

On plateau, oscillation, repeated defect, or evidence ceiling, choose `refine-spec`,
`request-input`, or `stop`; do not keep local tweaking and do not reset the round counter.
At the round cap, stop conditionally rather than opening another correction or input cycle.

## Blender scene and audit contract

Use collections `REF`, `MODEL_SOURCE`, `MODEL_FINAL`, `DETAIL`, `LOOKDEV`, `CAMERAS`, `LIGHTS`, and
`EXPORT`. Tag model objects with `img2blender_component_id`, review cameras with exact
`img2blender_role`, and attachment-dependent objects with `img2blender_requires_attachment`,
`img2blender_attachment_to`, and `img2blender_contact_verified`.

Use documented audit exceptions only when intentional:
`img2blender_allow_open`, `img2blender_uv_not_required`,
`img2blender_allow_nonunit_scale`, and `img2blender_ignore_audit`.
Every exception also requires `img2blender_exception_reason`.

Audit:

```bash
blender --background <scene.blend> \
  --python <skill-root>/scripts/blender_scene_audit.py -- \
  --out <project>/reviews/<pass>/scene-audit.json \
  --stage final \
  --strict \
  --required-role reference-match \
  --required-role orbit-left \
  --required-role orbit-right
```

## Completion gate

Do not claim completion because one render looks close. Completion requires:

- exact observed-feature coverage and disclosed inference;
- independent critic minimum rounds and no unresolved hard gate;
- critical features above threshold, visible, supported, attached, intersection-free, and
  consistent beyond the reference camera;
- silhouette, depth, cross-section, structure, materials, grounding, narrative detail, and
  presentation surviving the full view set;
- no delivery-relevant audit errors;
- final `.blend`, source checkpoint, textures, manifests, and requested exports opening correctly.

If evidence cannot support the requested fidelity, return a conditional result and request the
smallest specific missing view, measurement, closeup, map, neutral-light material reference, or
subject-matter decision.
