# Subject-specific routes and hard checks

Read every section selected in `reconstruction-spec.json.subjectRoutes`. Mixed subjects may require
multiple routes. Copy the exact checklist IDs into `featureContract.subjectChecklistItems` and the
critic report.

## Contents

1. Architecture and environments
2. Products and vehicles
3. Hard-surface props
4. Organic objects and creatures
5. Humans and characters
6. Cloth and hair
7. Botanical systems
8. Transparent and translucent assets
9. Generated and scanned imports

## 1. Architecture and environments

Route ID: `architecture-environment`

Reconstruct the specific composition, not a generic building or scene with a similar style.
Establish world scale, site axes, terrain datum, camera/lens, horizon, and major sightlines before
façade detail. Use plan/section/elevation reasoning even when only perspective evidence exists;
label inferred dimensions and inaccessible regions.

Required checklist:

- `composition-layout-fidelity`: match site footprint, object placement, camera-visible spacing,
  skyline, foreground/midground/background layers, negative space, and focal hierarchy.
- `mass-hierarchy`: preserve dominant, supporting, and tertiary volumes, rooflines, setbacks,
  towers, courtyards, and silhouette rhythm.
- `circulation-access`: provide plausible visible doors, stairs, ramps, paths, gates, bridges,
  loading/access zones, clearances, and movement connections; do not paint access onto walls.
- `facade-detail-visible-elevations`: construct structurally motivated bays, columns, beams,
  openings, balconies, railings, trims, joints, and material breaks on every visible elevation,
  including side/back views. Repeating front-only decoration fails.
- `roof-drainage-support-logic`: resolve roof thickness/slope, parapets, eaves, ridges, valleys,
  gutters/downpipes, waterproofing transitions, foundations, load paths, supports, and cantilevers.
- `windows-interiors`: give windows depth, frames, mullions, sills, glazing response, believable
  interior/parallax cues, and nonuniform occupancy where visible; black rectangles fail.
- `terrain-integration`: connect foundations, retaining walls, paths, vegetation, water, grade
  changes, erosion, drainage, and contact shadows to the site.
- `population-activities-props-signage`: reproduce observed people/vehicles/furniture/equipment,
  activity zones, signage, wayfinding, clutter, and narrative asymmetry at correct scale and density.
- `repetition-control`: preserve intentional modules while varying wear, occupancy, vegetation,
  props, open/closed states, and local damage without random noise.
- `wide-scene-atmospheric-depth`: match aerial perspective, haze, sun/sky direction, shadow scale,
  color separation, distance detail falloff, and layer readability across a wide scene.

Required evidence on every visual pass:

- matched render and overlay;
- clay silhouette and left/right orbit;
- back view;
- orthographic front/left/right/back elevations and top/plan;
- neutral material and grazing-light views;
- critical closeups and previous-iteration comparison.

Treat unsupported/floating structures, inaccessible entrances, façade detail that exists only on the
hero elevation, flat window cards, missing roof/support logic, terrain gaps, uniform copied modules,
and atmosphere used to hide absent geometry as hard failures.

## 2. Products and vehicles

Route ID: `product-vehicle`

Separate primary exterior surfaces, functional openings, panels, seals, trim, glass, tires/contact
parts, fasteners, lights/screens, labels, and underside structure. Product photography may contain
long-lens compression and retouching; solve multiple cameras against one shared object.

Required checklist:

- `stance-contact-points`: stance, wheel/foot/base alignment, suspension/load, and ground contact;
- `panel-flow-gaps-shut-lines`: section continuity, gaps, seals, panel offsets, and local radii;
- `functional-assembly-clearance`: hinges, openings, articulation, handles, controls, and clearance;
- `glass-trim-seals`: real boundaries, thickness, reveal, IOR/reflection behavior, and attachment;
- `underside-rear-volume`: plausible visible lower/back construction outside the hero camera;
- `reflection-continuity`: controlled highlight flow without waviness, pinching, or hidden dents.

## 3. Hard-surface props

Route ID: `hard-surface-prop`

Build countable solids and their construction relationships before decorative cuts. Keep boolean
operands and repeated systems editable. Never invent an internal mechanism from external styling.

Required checklist:

- `construction-axes`: consistent manufacturing axes, alignment, symmetry/asymmetry, and datum;
- `part-boundaries-thickness`: discrete shells/solids, wall thickness, seams, sockets, and overlaps;
- `fastener-clearance-logic`: hardware count, placement, embed depth, tool/access clearance;
- `profile-cross-sections`: evidence-backed section shapes, taper, concavity, thickness, and back;
- `bevel-edge-hierarchy`: physical radii and primary/secondary/tertiary edge sharpness;
- `reflection-flow`: long-highlight continuity and shading quality on manufactured surfaces.

## 4. Organic objects and creatures

Route ID: `organic-creature`

Lock gesture, skeletal landmarks, primary masses, section thickness, and attachment transitions
before anatomy detail. Match the specific creature or stylization instead of importing generic
human/animal priors.

Required checklist:

- `gesture-primary-masses`;
- `skeletal-landmarks`;
- `anatomical-attachment-transitions`;
- `section-thickness`;
- `asymmetry-specificity`;
- `frequency-layering`.

Keep primary, secondary, and tertiary sculpt frequencies separable. Preserve high-resolution source
sculpts and retopologize when deformation, subdivision, UVs, or baking requires it.

## 5. Humans and characters

Route ID: `human-character`

State whether the target is stylized reconstruction or maximum likeness. For likeness, seek
front/side/three-quarter neutral-expression sources with compatible lenses. A single portrait does
not prove skull depth, ears, back of head, body, skin, or hair.

Required checklist:

- `likeness-landmarks`: eye/brow/nose/mouth/jaw/ear/hairline placement and regional confidence;
- `head-body-proportions`: head units, silhouette, body ratios, costume volume, and scale;
- `pose-joint-angles`: weight, joint landmarks, articulation, and camera-caused distortion;
- `eyes-mouth-skin-depth`: cornea/iris, eyelids, oral cavity/lips/teeth, skin roughness/normal/SSS;
- `hair-costume-silhouette`: hairstyle masses, costume layers, accessories, gaps, and contacts;
- `deformation-topology`: loops and deformation zones required by the delivery target.

Projected shadows cannot become skin albedo; accessories cannot remain painted onto the body.

## 6. Cloth and hair

Route ID: `cloth-hair`

Required checklist:

- `construction-layer-order`: garments/clumps/accessories remain separate in correct overlap order;
- `tension-compression-gravity`: folds and strands respond to anchors, pose, gravity, and collision;
- `silhouette-masses-flow`: large hair/cloth masses and direction before strands or weave;
- `seams-hems-piping`: construction features have physical scale and attachment;
- `clump-strand-rhythm`: groom hierarchy, density, parting, breakup, flyaways, and anisotropy;
- `body-contact-clearance`: no floating straps, fused cloth, body penetration, or impossible gaps.

Simulation is a construction aid, not evidence of reference accuracy. Mark hidden groom and garment
regions inferred.

## 7. Botanical systems

Route ID: `botanical`

Use curves, instances, and Geometry Nodes with fixed seeds. More instances cannot rescue a wrong
hierarchy or silhouette.

Required checklist:

- `branching-hierarchy`;
- `density-gradients-gaps`;
- `phyllotaxis-distribution`;
- `scale-orientation-variation`;
- `gravity-wind-light-response`;
- `damage-color-locality`.

Preserve observed cluster rhythm, negative gaps, dead/damaged areas, seasonality, and terrain
attachment. Review repeated assets for obvious cloning.

## 8. Transparent and translucent assets

Route ID: `transparent-translucent`

Required checklist:

- `physical-thickness`;
- `ior-transmission-separation`;
- `absorption-scattering`;
- `reflection-refraction-environment`;
- `internal-form-legibility`;
- `caustic-emission-justification`.

Keep surface transmission, roughness, coating, volume absorption/scattering, SSS, emission, and
normal variation independent. Supply a controlled environment so refraction and reflection can be
judged. Request more evidence when background distortion cannot distinguish IOR from internal shape.

## 9. Generated and scanned imports

Route ID: `generated-scanned-import`

Use an image-to-3D result, photogrammetry/scan, or downloaded base only with user permission and
acceptable provenance/licensing. Treat it as a hypothesis.

Required checklist:

- `source-provenance-license`;
- `original-import-preserved`;
- `floaters-fusions-cleaned`;
- `baked-illusion-rebuilt`;
- `identity-components-reconstructed`;
- `retopo-uv-independent-channels`.

Preserve the original import, align scale/camera, compare silhouette and orbit depth, rebuild wrong
critical components, remove texture-baked geometry illusions, reconstruct independent PBR channels,
and disclose imported versus rebuilt regions.
