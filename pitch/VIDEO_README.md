# Super Monkey — actual rendered pitch preview

## Watch first

**`Super_Monkey_pitch_preview.mp4`** — combined 25-second silent pitch film.

Full path:
`C:\Users\HP\Downloads\hackathon\pitch\Super_Monkey_pitch_preview.mp4`

Open `video_output\watch.html` for the video, individual shot players, storyboard and model links.

## What is delivered now

- 960×540, 24 fps, H.264/yuv420p preview, 600 frames, exactly 25 seconds.
- `video_output\previews\shot1.mp4` — 6 seconds: macro tour from clip to lens, focus pull.
- `video_output\previews\shot2.mp4` — 8 seconds: staggered exploded assembly, hold, reverse assembly.
- `video_output\previews\shot3.mp4` — 6 seconds: rising 360-degree rotation, opposing camera orbit, antenna sway.
- `video_output\previews\shot4.mp4` — 5 seconds: locked hero pose; title fade begins at 2.5 seconds.
- `video_output\previews\final_preview.mp4` — same master as the convenient copy in this folder.
- `video_output\super_monkey_pitch.blend` — editable 600-frame camera/object animation and studio.
- `phase1_output\super_monkey_phase1.blend` — assembled model and original review studio.
- `phase1_output\super_monkey_model.glb` — assembled model only.
- `phase1_output\stills\` — 4 reference-angle draft stills, 6 inspection views, 2 separated-parts stills.
- `phase1_output\review.html` — references beside the model-review stills.
- `video_output\hero_poster.jpg` and `storyboard.jpg`.
- `video_output\previews\validation.json` — actual encoded durations, dimensions, frame counts and absence of audio.
- `video_output\continuity_check.json` — zero root/camera matrix differences at shot 2→3 and 3→4 joins.

There is a 0.5-second fade-through-white around the first transition only. It does not overlap/delete frames or alter the 25-second duration. No transitions interrupt shots 2–4. There is no audio in any MP4.

## Rendering work actually performed

A portable Blender 4.5.14 LTS was downloaded from the official Blender release server, under `tools\blender-4.5.14-windows-x64`. Nothing was installed system-wide. The prototype was built from the supplied phase-1 reconstruction script and exported. The video scene was built, sampled, corrected and rendered with Eevee and screen-space ray tracing on the available RTX 3050 GPU.

Corrections made after inspecting actual rendered check frames:

- Reduced overexposed studio lights so white parts and green rubber remain distinguishable.
- Added a curved cyclorama to remove the visible background horizon.
- Improved cavity shading at the zigzag clip seam and housing/bezel joins.
- Corrected macro camera aim and end-of-shot optical focus.
- Pulled back/recentred the exploded-shot camera so the detached rubber band remains in frame.
- Corrected typography to use one shared baseline, keeping lowercase letters and punctuation aligned.
- Verified exact matching camera/root boundary transforms between shots 2/3 and 3/4.
- Encoded and probed all four shots and the assembled master.

## Honest limitations / preview approval

This is a **rendered creative draft**, not a measured engineering replica or approved final.

- The supplied 135 / 30 / 80 mm remain unverified estimates. Hidden socket and inner ring geometry were inferred.
- The clip's moulded contours, lever curvature and slot end radii need refinement; the draft's clip has straighter stems and a more rectangular tip than the reference.
- The battery is too regular: foil folds, pouch seams and exact amber tape overlap are not reconstructed in detail.
- The board uses simple visible contacts, not a component-for-component electronic layout. No text/logos are reproduced.
- The ball/socket transition is more visibly segmented than the reference. The hidden mating structure is a modelling assumption.
- Lens glass is represented by a barrel and front disc, not the complete internal optical stack. Highlight appearance differs by angle.
- Antenna shape follows a single approximate hanging pose; it does not match the raised rear-reference posture.
- Assembly uses small lateral/back clearance moves as well as axial separation. It is not a collision-certified simulation, and no claim of zero mesh intersections is made.
- Macro bevel facets and temporal ray-tracing noise can remain at 16-sample preview quality. Final resolution/sampling will improve noise, not change underlying geometry.
- The backdrop is visually light grey, not a calibrated pixel-perfect #F5F5F7 throughout. Soft floor shadows are subtle; the requested shrinking/fading shadow is not separately art-directed in this draft.
- The source-photo cameras were not solved. Review angles are approximate.

Please approve or request changes to the model appearance, framing, pacing and title before rendering the 1920×1080 finals.

## Reproduce / render after approval

Scripts:

1. `phase1_model.py` — builds the model and exports it.
2. `phase2_video.py` — loads the model and builds/renders the animation.
3. `encode_video.py` — composites tracked thin-sans typography and encodes the videos.

`phase2_video.py` reads these environment variables:

- `SM_ACTION=BUILD`: build scene and render 11 check stills (default).
- `SM_ACTION=SCENE`: build scene without rendering.
- `SM_ACTION=RENDER`: render 600 frames, then call the encoder.
- `SM_MODE=PREVIEW`: 960×540, 16 samples (default).
- `SM_MODE=FINAL`: 1920×1080, 64 samples, motion blur. Use only after preview approval.

`RENDER_1080P_AFTER_APPROVAL.bat` is supplied but **has not been run**. It asks for confirmation, then runs the full-resolution render and encoder. Expected finals go to `video_output\finals\shot1.mp4` through `shot4.mp4` and `final.mp4`, with an additional `final.mp4` in the pitch folder.

The frame renderer resumes existing files. If changing scene/model settings, rename or remove the relevant `preview_frames` or `final_frames` folder before rerendering to prevent mixing old and new versions. Do not delete the original photographs.

The tracked title is composited by `encode_video.py` using Pillow and Segoe UI Light. Editable hidden text guides also exist in the Blender scene. Blender-only F12 renders therefore do not include the final title; run the encoder for the finished typography.

Dependencies now available: portable Blender, system FFmpeg, Python 3.11 and Pillow. Original photographs remain untouched.
