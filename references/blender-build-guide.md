# Blender reconstruction build guide

Read this file before selecting a modeling route or editing the scene.

## Contents

1. Scene and checkpoint discipline
2. Camera matching
3. Modeling-route selection
4. Pass-specific construction
5. Retopology and UV
6. Materials and projection
7. Lighting and rendering
8. Blender Python practices
9. Frequent failure patterns

## 1. Scene and checkpoint discipline

Use meters or a documented alternative. Anchor scale from evidence when possible. Keep the subject
near a stable origin and choose object origins that reflect assembly, articulation, or export needs.

Use these collections:

- `REF`
- `MODEL_SOURCE`
- `MODEL_FINAL`
- `DETAIL`
- `LOOKDEV`
- `CAMERAS`
- `LIGHTS`
- `EXPORT`

Keep a master `.blend` plus versioned pass files such as `subject_p03_primary-form_v02.blend`. Before
destructive operations—voxel remesh, modifier application, decimation, destructive booleans, UV
rebuild, or bake—duplicate the relevant collection or save a checkpoint.

Name components by function, not primitive origin. Add an `img2blender_component_id` custom property
matching the reconstruction spec. Store deliberate audit exceptions as custom properties rather than
depending on memory.

## 2. Camera matching

Camera errors contaminate every modeling decision. Solve the camera before fine form.

1. Set the render aspect ratio and crop to the source.
2. Place the source as a camera background or non-rendering image plane.
3. Identify verticals, horizontals, vanishing tendencies, symmetry axes, and widely spaced
   landmarks.
4. Estimate lens family, camera elevation/azimuth/roll, object orientation, distance, and camera
   shift.
5. Adjust lens and distance together: lens changes perspective; distance/framing changes occupancy.
6. Align landmark reprojection and silhouette. Lock the matched camera, name it descriptively, and
   tag it `img2blender_role="reference-match"`.

Use orthographic only when parallel edges, depth foreshortening, and source provenance support it.
For asymmetrical perspective references, avoid forcing bilateral geometry to match both sides in
screen space. Inspect the model from orbit before accepting any shape correction.

For multi-view references, create one camera per source and solve a shared object. Conflicting
landmarks usually indicate inconsistent reference drawings, lens differences, or a wrong scale—not
permission to deform each side independently.

## 3. Modeling-route selection

Choose per component, not once for the entire subject.

### Hard-surface and manufactured

Use direct mesh modeling, booleans, bevel, weighted/split normals where appropriate, subdivision,
arrays, mirrors, curves, and Geometry Nodes. Establish large plane breaks and construction
relationships before small booleans. Use real bevel geometry wherever the highlight width matters.

Prefer a clean modifier stack:

1. symmetry or array;
2. primary deformation;
3. booleans and construction cuts;
4. bevel or subdivision;
5. normal handling;
6. surface detail that genuinely belongs after the base form.

The exact order depends on the asset; record why a nonstandard order is needed.

### Organic and sculptural

Block gesture and primary masses first. Use symmetry only while supported by the reference. Choose:

- voxel remesh for rapid continuous mass changes;
- multiresolution for controlled frequency layering;
- subdivision with shrinkwrap/retopology for clean animation surfaces;
- curves for horns, tendrils, stylized hair masses, veins, or cables.

Work from primary to secondary to tertiary forms. Do not use pores, scales, or alphas to disguise
incorrect anatomy or volume.

### Conforming shells, cloth, and layered surfaces

Build over the supporting form with shrinkwrap, solidify, surface deform, or cloth simulation.
Establish silhouette-changing folds as geometry. Use normal/displacement for smaller fold breakup.
Separate construction seams, hems, piping, and stitching by their true scale and function.

### Repeated systems and strands

Use Geometry Nodes, curves, instances, arrays, or hair systems. Keep seed values stable. Expose
count, spacing, orientation, scale variance, clustering, and exclusion masks as named parameters.
Realize instances only when export or local editing requires it.

### Material-only and relief

Use decals, masks, normal/bump, displacement, or shallow geometry based on final screen size.
Engraving that casts a visible shadow needs depth; printed linework does not. Never model a painted
mark as a groove merely because it is dark.

## 4. Pass-specific construction

### Blockout

Use low-resolution primitives, broad sculpt masses, or profile extrusions. Match:

- outer contour;
- dominant negative spaces;
- relative component extents;
- front-to-back depth and center of mass.

Keep modifiers inexpensive and topology disposable. Render the full deterministic evidence set,
including clay silhouette, both orbit views, neutral/grazing views, reference overlay, critical
closeups, and the start-of-pass comparison. Later-stage checks may be provisional but may not be
omitted.

### Primary form

Establish cross-sections and transitions. Use section cuts or temporary clipping planes to inspect
depth. For blades, shells, limbs, faces, vessels, and product housings, the cross-section often
matters more than the front silhouette.

### Secondary form

Add visible subassemblies and attachment logic. Build seams, joints, sockets, handles, panels,
fold families, facial planes, muscle groups, hair clumps, and repeated hardware. Use contact
shadows and isolated views to expose floating parts or penetrations.

### Microdetail

Split frequency bands:

- macro: color zones, large dents, broad wear, large-scale displacement;
- meso: seams, folds, grain bands, brushed direction, chipped clusters, panel variation;
- micro: pores, fine scratches, weave, dust, tiny pits.

Vary frequency, amplitude, and locality independently. Uniform noise across the entire object is
not realism.

## 5. Retopology and UV

Retopologize when the asset must deform, subdivide predictably, export efficiently, bake cleanly, or
support stable UVs. A hero still can preserve high-resolution source geometry, but delivery meshes
still need deliberate normals, material boundaries, and manageable data.

Check:

- edge flow around deformation and silhouette;
- support for intended subdivision and displacement;
- no accidental internal surfaces, duplicates, zero-area faces, or inverted normals;
- intentional boundaries versus accidental non-manifold edges;
- consistent scale before baking;
- UV seams placed away from hero views when possible;
- texel density matched to importance and final resolution;
- enough padding for mipmapping and bake dilation;
- tangent-space normal convention expected by the export target.

Use UDIMs when a single atlas cannot meet the hero texel-density requirement or when component
organization benefits materially. Do not use UDIMs by reflex for a simple asset.

## 6. Materials and projection

Use Principled BSDF as the default physical surface model. Treat color spaces deliberately:

- base color and emission images: color-managed color data;
- roughness, metallic, normal, height, AO, and masks: non-color data;
- packed maps: document channel decoding and do not connect the same channel blindly to unrelated
  inputs.

For each material establish:

- base-color palette and regional masks;
- metallic/dielectric behavior;
- roughness base, range, and local variation;
- normal/bump/displacement at appropriate physical scale;
- coat, anisotropy, sheen, transmission, SSS, or emission only when supported;
- cavity, contact, handling, edge, and gravity-aware wear.

### Projection-first surface fidelity

Use a de-lit source projection when exact visible pattern placement, facial color, a decal, painted
art, or an irregular finish matters.

1. Match and lock the source camera.
2. Create or obtain a de-lit image with baked highlights and shadows reduced.
3. Fit geometry before projection; pixels are color evidence, not geometry truth.
4. Project from the matched camera and bake into stable UVs.
5. Derive or author roughness, normal/height, AO, and masks independently.
6. Inspect from orbit for stretching, seams, and view-dependent collapse.
7. Fill unseen areas using additional views, symmetry where valid, or clearly labeled inference.

Never present front projection coverage as full-surface reconstruction.

## 7. Lighting and rendering

Maintain separate rigs:

- `neutral`: broad, soft, color-neutral form and albedo inspection;
- `grazing`: smaller low-angle source that exposes bevels, roughness, normals, displacement,
  faceting, and tiling;
- `reference-match`: source-like key direction, softness, fill, reflections, background, exposure;
- optional `turntable`: stable studio presentation.

Create separate scene/view-layer arrangements where necessary and tag the actual evidence cameras
with exact schema-v2 roles: `reference-match`, `clay-silhouette`, `orbit-left`, `orbit-right`,
`back`, `neutral-material`, `grazing-light`, `critical-closeup:<feature-id>`, and subject-specific
orthographic roles. A role tag is a manifest contract; it does not replace the material override or
lighting setup the role describes.

Set `img2blender_view_layer` for role-specific view layers. Require a material override on the clay
view layer and set `img2blender_light_rig` to `neutral` or `grazing` on the corresponding cameras.
The renderer records these values, camera matrices, image hashes, and the source `.blend` hash so
the pipeline can reject evidence from the wrong checkpoint or rig.

For architecture/environment create true orthographic front/left/right/back/top cameras aligned to
the documented site axes. Keep elevation scale consistent so mass, grade, openings, roof/support
logic, and repetition can be compared without perspective hiding errors.

For final quality, prefer Cycles unless the delivery target specifically requires real-time
rendering. Use enough samples for stable material and shadow judgment, denoise with care, and inspect
whether denoising erases microdetail. Record engine, device, sample count, denoise, resolution,
display transform, look, exposure, environment, and light settings in the render manifest.

Use contact shadows and reflection structure that reveal construction without hiding defects.
Material truth must survive neutral lighting before reference lighting is tuned.

## 8. Blender Python practices

- Make scripts idempotent when practical: find data by stable name or custom ID before creating it.
- Avoid relying on selection or active-object state unless the script establishes it explicitly.
- Link objects and collections intentionally; do not leave orphaned duplicates after iterations.
- Set random seeds for procedural placement and noise.
- Log exact object, modifier, node, socket, value, and reason for every automated change.
- Save to a new checkpoint after meaningful automated edits.
- Run automation in background mode for audit and rendering; inspect visual output before approval.
- Give builders stable IDs, but never let the builder emit or approve the independent critic report.
- Save one checkpoint after correcting the critic's single highest-impact root cause; do not bundle
  unrelated geometry, material, camera, and light experiments into the same correction.
- Detect Blender API differences rather than pinning the workflow to one version without reason.

## 9. Frequent failure patterns

- **Perfect front silhouette, toy-like orbit:** add real depth, taper, bevel, cross-section changes,
  and back-side construction; do not tune the front image further.
- **Detail-rich but wrong identity:** remove or ignore microdetail and correct the top one or two
  critical proportion/component errors.
- **Projected texture looks photographic only head-on:** improve geometry fit, de-lighting, UV bake,
  unseen-region treatment, and multi-view coverage.
- **Plastic-looking metal:** correct metallic behavior, roughness distribution, bevels, normals,
  reflection environment, and real-world scale.
- **Everything looks equally noisy:** separate macro/meso/micro frequency bands and mask detail by
  construction, handling, gravity, and wear exposure.
- **Camera-matching changes break orbit views:** revisit the camera solve; do not sculpt lens
  distortion into the object.
- **Boolean-heavy topology shades poorly:** clean operands, bevel at physical scale, inspect normals,
  simplify coplanar cuts, and retopologize or bake when the modifier stack stops serving the target.
- **Denoised render hides surface evidence:** raise samples, improve lighting, inspect raw or less
  denoised output, and judge at final resolution.

## Render preflight and device fallback

Use `scripts/render_preflight.py` from host Python before a costly batch:

```bash
python3 <skill-root>/scripts/render_preflight.py \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --scene project/doors.blend --out project/reviews/render-preflight.json \
  --device auto --timeout 60
```

Resolve the executable for the current machine; the macOS path is an example. The preflight opens
the source with factory preferences and automatic script execution disabled, then renders a small
disposable scene. It detects supported devices and records the selected backend, actual device,
Blender build, source hash and source render settings. A GPU render failure, crash, invalid report or timeout
gets one fresh CPU attempt. During automatic discovery, unavailable backends may instead be skipped
and CPU selected within the first process. The timeout is per attempt; total work can take approximately twice
that duration. No .blend or preferences are saved. A passing probe establishes runtime health,
not that a complex production scene will render successfully.

GPU and CPU may produce different noise/performance. Use the passing backend explicitly for the
production render and record effective settings separately from saved scene defaults. Do not claim
that saved CPU settings prove a render used CPU. The production review renderer records `configuredCyclesMode` (CPU/GPU), not a measured hardware
backend; include a production log if the effective backend/device claim matters. The preflight
manifest identifies devices for its own tiny probe only.

In the Jade Threshold door run on one M4 Max, asynchronous Metal compilation crashed; CPU was
reliable. A subsequent Metal render succeeded with MetalRT off and these process-local overrides:

```bash
--device METAL --metalrt off \
--cycles-env CYCLES_METAL_SPECIALIZATION_LEVEL=0 \
--cycles-env CYCLES_METAL_ADAPTIVE_COMPILE=0
```

These are an observed local workaround, not a universal fix or default. The preflight applies no
overrides unless explicitly supplied (and records allowlisted inherited values). Capability-guard
optional Blender properties; report the tested build instead of assuming all later versions work.

For reproducible delivery, derive project paths from the script or accept arguments; avoid embedded
user-home paths. Reuse named camera/text datablocks or document a required fresh checkpoint. Include
final scene(s), source, selected reference/prompt provenance, render/check manifests, checksums and
conditional review notes. Reopen the saved files, check resource links, and test the archive.

Build an archive from explicit project-relative inclusions with the reusable helper:

```bash
python3 <skill-root>/scripts/package_delivery.py \
  --project-dir project --out project/delivery.zip \
  --include blender/final.blend --include references --include renders --include reviews
```

Add the source script directory and any required textures explicitly. The archive contains a
`delivery-manifest.json` with sizes and SHA-256 hashes. The helper rejects traversal and symlinks,
omits backups/logs/cache/Git data, and checks archive CRCs, hashes and source stability before an
atomic output replacement. Existing output survives errors. It verifies packaging only; reopening
scene files, resource checks and visual review remain separate requirements. The root manifest
filename is reserved; do not include an existing file with that name.
