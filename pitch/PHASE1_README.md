# Super Monkey — Phase 1 handoff

## Current status

UPDATE: After the user's instruction to proceed with the video, a portable official Blender 4.5.14 runtime was downloaded into `tools`. The model script was executed successfully, including a runtime fix for the anisotropic material input. The .blend and .glb now exist. Twelve supplementary review stills were rendered using the tested video studio.

**An actual 25-second, 960×540, 24 fps silent video preview now exists: `Super_Monkey_pitch_preview.mp4`. Open `video_output/watch.html` for all four shots. See `VIDEO_README.md` for current deliverables and limitations.**

The user authorized proceeding into video production. This is still a provisional reconstruction, not an accuracy-certified finished model. The 1920×1080 finals remain gated on preview approval.

## Run Phase 1

1. Use Blender 4.2 or newer. Save any open work: the script clears the scene.
2. Open **Scripting → Text → Open** and select:
   `C:\Users\HP\Downloads\hackathon\pitch\phase1_model.py`
3. Click **Run Script**. Alternatively paste the entire script into a new text block.
4. Wait for modelling, export and 12 still renders. Boolean construction of the ring and clip can take time. Blender may appear unresponsive while rendering.
5. Open `phase1_output\review.html` in a browser for side-by-side reference images and reconstruction renders.
6. Return the four comparison renders and the separated-parts still for inspection and correction. Do not treat a successful script run as model approval.

All outputs stay beneath:
`C:\Users\HP\Downloads\hackathon\pitch\phase1_output\`

Expected outputs after a successful Blender run:

- `super_monkey_phase1.blend` — assembled model and review studio
- `super_monkey_model.glb` — assembled model only, in metres; no studio
- `parts_manifest.json` — separate named object dimensions and functional grouping
- `review.html` — four photo comparisons, six views, two exploded views
- `stills\01_front_photo_angle.png`
- `stills\02_back_photo_angle.png`
- `stills\03_head_photo_angle.png`
- `stills\04_clip_photo_angle.png`
- `stills\turnaround_front.png`, `back`, `left`, `right`, `top`, `bottom`
- `stills\11_all_parts_axial_separation.png` — every named object separated along Z
- `stills\12_functional_groups_separated.png` — additional functional-group overview

The default review render uses CPU Cycles, 48 samples, denoising and a 1200-pixel long edge. Change `RESOLUTION` and `SAMPLES` at the top for faster drafts. `RENDER_STILLS = False` builds and exports without rendering; the HTML will then reference stills that do not exist.

## Estimated parts list (mm)

Axes: Z is the long axis toward the camera housing, -Y is the lens direction, and XZ is the flat clip plane. Dimensions are local envelopes, not manufacturing drawings.

| Part | Draft dimensions / construction |
|---|---|
| Overall rigid assembly | Approximately 135 long, pending measurement; flexible antenna posture is excluded from the length convention |
| Camera housing | 21 wide × 14 deep × 22 long, moulded corner radius 1.6 |
| Raised square bezel | 13.2 × 13.2 face, 3.3 deep |
| Lens | 8.76 barrel diameter, 7.3 optical glass diameter |
| USB-C opening | Approx. 8.7 × 3.4, recessed on the top end |
| Back circuit board | 12.5 × 24 × 1.1; no readable labels |
| Brown / black battery wires | 1.22 / 1.06 diameter; spline paths inferred from photographs |
| Antenna coax | 0.86 diameter |
| Flexible antenna strip | 8 × 25 × 0.25; curved, unbranded |
| Battery pouch | 35 × 23 × 4.4; broad face transverse to the device axis |
| Amber tape | Approx. 6.9-wide wrap at one lateral battery end, about 0.15 shell thickness |
| White flange | 26.6 diameter × 2.05; assumed 6 diameter centre bore |
| Green spacer band | 25.2 outer diameter × 1.45; assumed 6 diameter bore |
| Ribbed ring | Approx. 30 diameter × 9.3, forty integrated longitudinal ribs |
| Ring inner bore | Stepped 9.2 / 6 diameter, inferred rather than observed |
| Ball | 6.9 diameter, concealed in socket |
| Socket | 10.6 outer diameter × 5.8, 7.4 spherical cavity, 5.4 mouth |
| Flared joint neck | 15.6 maximum diameter, approx. 7.4 axial length |
| Clip jaws | Approx. 79 end-to-end; each coplanar jaw 5 thick |
| Circular pivot region | 28 outer diameter, 14.2 central through-hole |
| Curved pivot slots | Four through-slots, approx. 1.9 radial width |
| Lever / paddle | 4.4-wide stem, 7.2-diameter rounded paddle |
| Tip toothed seam | Approx. 1.9 peak-to-peak lateral excursion; rounded zigzag contour |
| Tip rubber band | 1.66 round-section diameter, four connected turns over a 9-long region |

The supplied 135 / 30 / 80 values were explicitly estimates. There is no calibrated scale or ruler in the images: they cannot honestly be replaced with measured values from these photos. Ring diameter is the provisional proportion anchor. Please measure overall rigid length, ring diameter and clip end-to-end length for a dimensionally reliable next iteration.

## Photo observations and reconstruction assumptions

- The jaws are coplanar split-ring pieces, not two conventional stacked clamp plates. The seam continues from the central hole toward the clip tip.
- The joint stem is offset laterally from the pivot-hole centre. The draft long axis follows that stem.
- The battery is an edge-on pouch sitting across the axial stack, not a tall brick above the ring. Its long in-plane dimension is provisional.
- The references show different antenna poses. The front-view hanging posture is the default; the rear photo's raised posture is not matched by the same static geometry.
- The inner ring bore, flange bore, socket retention geometry, ball diameter and hidden housing construction are not visible. The script uses plausible closed solids with mating cavities. These are assumptions, not evidence of the prototype's actual engineering.
- No screws, springs, extra electronics, text or logos are invented. Small solder pads approximate visible rear contacts; the board's exact component layout is not reconstructed.
- The foil uses smooth metal and subtle bump rather than matching every wrinkle. Tape is a hollow transmissive wrap. A physically folded pouch seam is not yet reconstructed.
- The socket is modelled as a separate object to expose its cavity for review. Whether the real socket is integral to a jaw cannot be established from the images.
- Camera viewpoints, roll and framing are hand-estimated. The script uses orthographic review cameras: it does not solve the photos' perspective lenses.
- Every model mesh is individually named, has a bounding-box-centred origin and is parented directly to `Super_Monkey_ROOT`. Functional membership is stored in `assembly_group` for later animation.

## Comparison and correction status

Video check frames have been inspected and lighting, backdrop horizon, macro focus, text baselines and camera framing were corrected and re-rendered. Supplementary photo-angle stills now exist. Exact photo-camera matching and a comprehensive geometry correction pass are NOT complete. The HTML is a review layout, not an automatic similarity test.

Known draft limitations to inspect first:

1. Front: camera-to-ring proportions, lean, PCB exposure and antenna curl.
2. Back: raised antenna pose differs deliberately from the default hanging pose; board detail, wire routing and pouch silhouette remain approximate.
3. Head: exact USB opening placement, bezel contour, battery foil folds and tape overlap are approximate; the draft lacks the photograph's local wrinkles.
4. Clip: exact slot end shapes, seam tooth rhythm, tip taper, lever curvature and stem-to-flare blend require silhouette refinement against the close-up. Draft lever stems are straighter than the photographed moulded transitions.
5. All images: perspective, soft contact shadows, exact edge radii and white/green colour matching require rendered review.
6. Six views / exploded views: inspect manifold geometry, Boolean artefacts, socket/ball clearances, exposed inner faces and unintended intersections. No automated collision guarantee has been made.
7. GLB: inspect in a glTF viewer. Blender procedural foil bump may not transfer; geometry and base PBR materials export, while transmission support depends on the viewer.

## Phase 2, after approval

Only after correcting and approving Phase 1 should the separate Phase 2 script/scene be made. The requested deliverables remain four low-resolution approval previews, then 1920×1080/24 fps `shot1.mp4` through `shot4.mp4` and `final.mp4`, with no audio. Shots 2–4 need shared boundary transforms; shot 1 alone gets a fade-through-white transition. Wire routing during separation and the sliding rubber band need special handling and collision inspection; simply moving these draft objects by group is not a validated animation.
