# Intake, evidence, and quality contract

Read this file before opening Blender or creating geometry.

## Contents

1. Reference admission
2. Layered observation
3. Camera and scale evidence
4. Complexity and suitability
5. Reconstruction contract
6. Quality contract
7. Feature coverage and detail inventory
8. Uncertainty and contradictions

## 1. Reference admission

For every source image record:

- absolute path or stable URL;
- file hash for a local image;
- pixel dimensions and orientation;
- role: primary, front, side, back, three-quarter, top, underside, material close-up, detail
  close-up, or scale evidence;
- whether it is a photograph, orthographic drawing, concept art, render, or generated image;
- subject coverage, cropping, occlusion, blur, compression, lens distortion, reflections, and
  baked lighting;
- whether another source duplicates or contradicts it.

Classify the full reference set:

- `pass`: identity, silhouette, major materials, and enough depth evidence are legible;
- `conditional`: useful reconstruction is possible, but important regions require inference;
- `request-input`: the smallest additional view or measurement can resolve a blocking unknown;
- `reject`: the target is ambiguous or the requested accuracy cannot follow from the evidence.

Do not treat a polished product render as orthographic merely because the background is clean. Do
not infer geometry from filenames, marketing names, or aspect ratio when the pixels disagree.

## 2. Layered observation

Keep observation and inference in separate fields. Use object-space directions rather than image
left/right whenever the subject orientation is known.

### Identification

Record the most specific supported noun, broad class, subject domain (`object`, `character`,
`hybrid`, `environment-element`), confidence, and any alternate interpretation.

### Overall form

Describe:

- bounding volume and aspect ratios;
- bilateral, radial, repeated, approximate, or absent symmetry;
- dominant axes, center of mass, negative spaces, and silhouette breaks;
- geometric, organic, manufactured, eroded, fabric-like, strand-like, or mixed form language.

Use ratios tied to a named reference dimension. Avoid "large", "small", "nice", or "smooth"
without a measurable relation or surface description.

### Macro, meso, and micro hierarchy

- `macro`: independent major masses or assemblies;
- `meso`: subassemblies, plane changes, folds, panels, muscle groups, hair masses, hardware systems;
- `micro`: surface marks, pores, scratches, stitching, engraving, weave, chips, edge wear, decals.

Express attachments as triples such as `<guard, overlaps, grip>` and record the contact as butt,
overlap, socket, embed, hinge, weld, seam, conforming shell, or intentionally separated.

### Surface topology class

Assign one class before choosing a Blender technique:

- `continuous-sculpt`: smoothly varying mass; sculpt, subdivision, multiresolution, voxel remesh,
  curves, or carefully lofted topology;
- `assembled-solid`: discrete rigid part with countable planes or simple curvature; direct
  modeling, booleans, bevels, arrays, subdivision, or CAD-like construction;
- `conforming-shell`: thin layer following another surface; shrinkwrap, solidify, cloth, surface
  deform, or retopology over a base;
- `surface-relief`: feature riding on a surface; geometry, displacement, normal, bump, or decal
  according to final pixel size and silhouette impact;
- `fiber-strand`: elongated path-following or repeated strands; curves, hair/particle systems, or
  Geometry Nodes;
- `material-only`: color/roughness/normal/mask change with no meaningful geometric footprint.

Classify by surface behavior, not physical size.

### Materials and finish

For each visible material region record:

- likely substance and confidence;
- de-lit base-color palette by region;
- metallic versus dielectric behavior;
- roughness range and directional response;
- coat, sheen, anisotropy, transmission, subsurface, emission, or thin-film cues when observed;
- macro, meso, and micro normal/height structure;
- local wear, dirt, stains, oxidation, fingerprints, scratches, fading, edge polish, and cavities;
- which properties are observed and which are inferred from common material behavior.

Highlights and shadows are lighting evidence, not automatically base color.

### Identity-defining features

List features that distinguish this specific subject from a generic class member. Include unusual
proportions, profile breaks, asymmetry, openings, hardware layout, seams, logos, text, wear,
hairstyle masses, facial landmarks, color zones, and pattern placement. Promote each one to a
critical or important review target.

## 3. Camera and scale evidence

Record:

- perspective or orthographic likelihood;
- converging parallels and foreshortening clues;
- estimated focal-length family: wide, normal, short telephoto, long telephoto, or unknown;
- camera elevation, azimuth, roll, and target point;
- image crop and subject occupancy;
- known dimensions, repeated standard parts, human-scale cues, or explicit absence of scale.

Separate camera-caused distortion from object shape. Use at least four widely separated landmarks
for camera alignment when possible. A single known length does not provide manufacturing accuracy;
it only anchors global scale.

## 4. Complexity and suitability

Score each axis `0` to `3`:

- silhouette interruption;
- component count and hierarchy depth;
- cross-section variation;
- repetition density;
- material layer count;
- local detail density;
- occlusion and hidden-region risk;
- camera ambiguity;
- topology/rig/export difficulty.

Map the total judgment to:

- `simple`: few forms, low occlusion, limited detail;
- `moderate`: several parts or visible local detail;
- `complex`: multiple systems, materials, or topology challenges;
- `ultra`: dense identity detail, character likeness, intricate mechanical assembly, layered
  clothing/hair, or a hero close-up where surface fidelity is central.

Complexity is a planning and evidence burden, not permission to invent more parts.

## 5. Reconstruction contract

Fill `reconstruction-spec.json` produced by `reconstruction_pipeline.py init`. Keep these records
explicit:

- `subjectRoutes`: every applicable route from `subject-routes.md`;
- `referenceAnalysis`: classification, suitability, observations, `observedFeatures`, inference,
  camera, scale, and contradictions;
- `componentPlan`: stable IDs, hierarchy, topology class, observed dimensions or ratios,
  attachments, modeling route, symmetry, confidence, and evidence refs;
- `materialPlan`: component assignment, shader model, independent channels, projection/UV method,
  texture resolution, local overrides, and provenance;
- `featureContract`: an exact mapping for every observed particular feature;
- `detailInventory`: a frequency/detail inventory supporting the feature contract;
- `unknowns`: region, impact, confidence, chosen treatment, and whether another input is required;
- `qualityContract`: the object-specific definition of done.

Avoid a component plan that could describe many objects of the same category. The spec must encode
the source's particular proportions, relationships, and identity features.

Intake pins the validated spec SHA-256 and every admitted reference SHA-256. Never edit them
silently after intake. Route critic-directed contract changes through `revise-spec`; route new user
evidence through a hashed input-resolution transition. Every visual critic report cites the pinned
contract and reviewed checkpoint hashes.

### Observed features

Create one `referenceAnalysis.observedFeatures` row for every particular feature that distinguishes
the source from a generic category member. The `particular` field must be concrete: ratio, count,
placement, profile break, attachment, pattern, material boundary, wear mark, landscape relationship,
pose, activity, sign, or asymmetry. Link it to admitted reference IDs and confidence.

### Feature contract

Map every observed-feature ID exactly once. Each `featureContract` row requires:

- `featureId` and the same `observedParticular`;
- `implementation.kind`: `geometry`, `material-mask`, `decal`, `node-system`, `displacement`,
  `texture`, or explicit `deferred`;
- `implementation.target`: the exact Blender component/feature, material mask, image/decal, node
  group/system, displacement layer, or documented deferment—not a vague category;
- one or more exact `subjectChecklistItems`;
- one or more deterministic `reviewCameras`;
- confidence and admitted `evidenceRefs`;
- `critical: true|false`.

Critical mappings must include `critical-closeup:<feature-id>` in `reviewCameras` and appear with the
same ID in `qualityContract.criticalFeatures`. The controller rejects missing, extra, or duplicate
mappings. Generic resemblance, a broad component list, or prose that never maps to the scene cannot
pass intake.

Example:

```json
{
  "featureId": "south-facade-seven-bays",
  "observedParticular": "Seven unequal bays; the third bay is the narrow entry bay.",
  "implementation": {
    "kind": "node-system",
    "target": "GN_SouthFacade_Bays with bay_widths=[4.1,4.1,2.6,4.1,4.1,4.1,4.1]"
  },
  "subjectChecklistItems": [
    "composition-layout-fidelity",
    "facade-detail-visible-elevations",
    "circulation-access",
    "repetition-control"
  ],
  "reviewCameras": [
    "reference-match",
    "ortho-front",
    "critical-closeup:south-facade-seven-bays"
  ],
  "confidence": 0.91,
  "evidenceRefs": ["ref-01", "ref-03"],
  "critical": true
}
```

## 6. Quality contract

Define before modeling:

- concrete `definitionOfDone` statements;
- `criticalFeatures` with an evidence reference and threshold;
- `requiredViews`: reference-match, reference-overlay, clay silhouette, left/right orbit,
  neutral-material, grazing-light, previous-iteration, every critical closeup, plus relevant back
  and subject-specific views;
- `backReviewRequired` as an explicit boolean;
- `failureModes` that block advancement;
- `deliverables`;
- `detailMinimum` based on observed complexity;
- `globalThreshold` and `criticalThreshold`.

For hero-quality work, start with `globalThreshold: 0.82` and `criticalThreshold: 0.85`. Raise them
when references are comprehensive and controlled. Do not lower them to force a pass; lower them
only when the user explicitly accepts a simpler target.

Strong contract:

> The upper housing maintains the reference's 1.42:1 length-to-height ratio, the vent array follows
> the observed seven-slot spacing and curvature, all shell seams remain attached in orbit views,
> and brushed metal anisotropy stays directional under grazing light.

Weak contract:

> Make the model detailed and realistic.

For architecture/environment, require back plus orthographic front/left/right/back/top on every
visual pass. Do not lower thresholds to force advancement.

## 7. Feature coverage and detail inventory

Scan by component zones or a 3×3/4×4 image grid. Start with these minimum counts:

- simple: 3;
- moderate: 6;
- complex: 10;
- ultra: 16.

Each record needs:

- `id`, `kind`, `region`, `scale`, `affects`, `evidenceRef`, and `confidence`;
- `mapsTo`: component feature, material mask, decal, Geometry Nodes system, displacement, texture,
  or explicit deferment;
- `reviewView`: the camera or close-up where it can be judged.

The detail inventory does not replace `observedFeatures` or `featureContract`. Use it to track
frequency/detail work; use the feature contract to prove that every observed particular reaches an
implementation, checklist, camera, and evidence source.

Useful kinds include bevel, fastener, hole, groove, ridge, seam, stitch, fold, panel break, strand
cluster, pore, scratch, chip, stain, patina, edge wear, gloss zone, anisotropic brushing, decal,
engraving, emission, transparency, and subsurface cue.

A bright edge may imply a real bevel, but label that as inference until a secondary view confirms
the cross-section. Relief that changes the silhouette must be geometry or displacement-capable
topology; relief smaller than a final pixel may remain a normal/bump contribution.

## 8. Uncertainty and contradictions

Use one disposition for every unknown:

- `request-view`;
- `infer-by-symmetry`;
- `infer-by-continuity`;
- `infer-by-domain-prior`;
- `neutral-simplification`;
- `exclude-from-scope`.

Give each inferred region a confidence score and explain its impact. When sources disagree:

1. preserve both observations;
2. prefer the source with clearer coverage, lower distortion, and more authoritative provenance;
3. never silently average incompatible designs;
4. ask the user when the contradiction changes identity or delivery.

The final report must distinguish observed reconstruction, evidence-backed inference, and artistic
completion.
