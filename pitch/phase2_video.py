"""Super Monkey cinematic pitch — Blender 4.5 LTS.
Run AFTER phase1_model.py. Loads that model, builds and saves the animation.
Outputs: pitch/video_output; mode is PREVIEW unless SM_MODE=FINAL.
SM_ACTION: BUILD (scene+sample frames), RENDER (all frames+MP4), SCENE (scene only).
SM_MODE=FINAL is for after preview approval. No audio.
The model remains a photo-derived draft; this is not a collision-certified simulation.
"""
import bpy, os, math, json, shutil, subprocess
from pathlib import Path
from mathutils import Vector, Quaternion, Euler

BASE=Path(r'C:\Users\HP\Downloads\hackathon\pitch')
OUT=BASE/'video_output'
OUT.mkdir(exist_ok=True)
MODE=os.environ.get('SM_MODE','PREVIEW').upper()
ACTION=os.environ.get('SM_ACTION','BUILD').upper()
PREVIEW=MODE!='FINAL'
WIDTH,HEIGHT=(960,540) if PREVIEW else (1920,1080)
SAMPLES=16 if PREVIEW else 64
FPS=24
SHOTS=[('shot1',1,144),('shot2',145,336),('shot3',337,480),('shot4',481,600)]
FRAMES=OUT/('preview_frames' if PREVIEW else 'final_frames')
FRAMES.mkdir(exist_ok=True)
model=BASE/'phase1_output'/'super_monkey_phase1.blend'
if not model.exists(): raise RuntimeError('Run phase1_model.py first: '+str(model))
bpy.ops.wm.open_mainfile(filepath=str(model))
scene=bpy.context.scene
scene.render.engine='BLENDER_EEVEE_NEXT'
scene.eevee.taa_render_samples=SAMPLES
scene.eevee.use_raytracing=True
scene.render.resolution_x=WIDTH
scene.render.resolution_y=HEIGHT
scene.render.resolution_percentage=100
scene.render.fps=FPS
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGB'
scene.render.image_settings.color_depth='8'
scene.render.film_transparent=False
scene.render.use_file_extension=True
scene.render.film_transparent=False
scene.render.image_settings.compression=20
scene.render.use_persistent_data=True
scene.render.use_motion_blur=not PREVIEW
scene.render.motion_blur_shutter=.25
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.view_settings.exposure=0
scene.render.fps_base=1
scene.frame_start=1; scene.frame_end=600
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.80,.83,.88,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
root=bpy.data.objects['Super_Monkey_ROOT']
parts=[o for o in bpy.data.objects if o.parent==root and o.type=='MESH']
centre=Vector((.00866,0,.067))
for o in parts:
    o.location-=centre
    o.animation_data_clear()
root.animation_data_clear()
root.rotation_mode='QUATERNION'
rest={o.name:o.location.copy() for o in parts}
for o in list(bpy.data.objects):
    if o.type in {'LIGHT','CAMERA'} or o.name.startswith('STUDIO_'):
        bpy.data.objects.remove(o,do_unlink=True)

# Weighted normals keep broad plastic faces planar and bevels satin smooth.
for o in parts:
    for p in o.data.polygons: p.use_smooth=True
    if not any(w in o.name.lower() for w in ['wire','coax','rubber','ball','neck']):
        m=o.modifiers.new('Satin surface weighted normals','WEIGHTED_NORMAL')
        m.keep_sharp=True; m.weight=50
    o['draft_validation']='Model proportions/hidden surfaces remain provisional.'
plastic=bpy.data.materials.get('Satin white moulded plastic')
if plastic:
    nodes=plastic.node_tree.nodes
    ao=nodes.new('ShaderNodeAmbientOcclusion')
    ao.inputs['Color'].default_value=(.83,.845,.86,1)
    ao.inputs['Distance'].default_value=.004
    ao.samples=16
    plastic.node_tree.links.new(ao.outputs['Color'],nodes['Principled BSDF'].inputs['Base Color'])
# EEVEE transparency is less reliable for a foil wrap; retain a warm coated tape.
tape=bpy.data.materials.get('Translucent amber tape')
if tape:
    p=tape.node_tree.nodes.get('Principled BSDF')
    p.inputs['Transmission Weight'].default_value=.25
    p.inputs['Coat Weight'].default_value=.5
    p.inputs['Metallic'].default_value=.16
    p.inputs['Base Color'].default_value=(.92,.48,.012,1)

# ---------------- SEAMLESS STUDIO ----------------
def mat(name,rgb,rough=.7):
    m=bpy.data.materials.new(name); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*rgb,1)
    p.inputs['Roughness'].default_value=rough
    return m
floor_mat=mat('Studio very light neutral grey',(.85,.85,.87))
fp=floor_mat.node_tree.nodes.get('Principled BSDF')
fp.inputs['Emission Color'].default_value=(.85,.85,.87,1)
fp.inputs['Emission Strength'].default_value=1.5
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001))
floor=bpy.context.object; floor.name='STUDIO_Infinite_seamless_floor'
floor.data.materials.append(floor_mat)
# Curved cyclorama covers rays above the horizontal floor: no horizon line.
profile=[(-2,-.001),(.35,-.001)]
for i in range(1,65):
    a=(math.pi/2)*i/64
    profile.append((.35+.65*math.sin(a),-.001+.65*(1-math.cos(a))))
profile.append((1,10))
verts=[(x,y,z) for y,z in profile for x in [-10,10]]
faces=[(2*i,2*i+1,2*i+3,2*i+2) for i in range(len(profile)-1)]
mesh=bpy.data.meshes.new('Seamless curved sweep'); mesh.from_pydata(verts,[],faces); mesh.update()
cyc=bpy.data.objects.new('STUDIO_Cyclorama',mesh); scene.collection.objects.link(cyc)
cyc.data.materials.append(floor_mat)
for p in mesh.polygons: p.use_smooth=True

def light(name,loc,energy,size,target,shape='DISK',color=(1,1,1)):
    data=bpy.data.lights.new(name,'AREA'); data.energy=energy*.12; data.shape=shape
    data.size=size; data.color=color
    o=bpy.data.objects.new(name,data); scene.collection.objects.link(o)
    o.location=loc
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    return o
light('Key_large_silk',(-.28,-.35,.58),24,.40,(0,0,.16),color=(1,.975,.94))
light('Fill_softbox',(.34,-.15,.34),10,.32,(0,0,.16),color=(.93,.96,1))
light('Rim_edge_separation',(.15,.28,.44),28,.28,(0,0,.16))
strip=light('Lens_clean_strip_reflection',(-.06,-.24,.20),2,.18,(.03,0,.05),shape='RECTANGLE')
strip.data.size_y=.018
# Ambient world is not an HDR reflection map. A very large ceiling softbox
# provides a smooth light-grey seamless floor without a visible horizon.
light('Backdrop_broad_soft_light',(0,0,1.8),140,2.5,(0,0,0))

cd=bpy.data.cameras.new('Cinematic_camera'); cd.type='PERSP'; cd.lens=65
cd.sensor_width=36; cd.clip_start=.001; cd.clip_end=500
cam=bpy.data.objects.new('Cinematic_camera',cd); scene.collection.objects.link(cam)
cam.rotation_mode='QUATERNION'; scene.camera=cam
focus=bpy.data.objects.new('Focus_pull_target',None); scene.collection.objects.link(focus)
cd.dof.use_dof=True; cd.dof.focus_object=focus; cd.dof.aperture_blades=9

# Soft secondary sway uses a shape key, keeping the coax attachment fixed.
antenna=[]
for name in ['02e_Antenna_coax','02f_Flexible_antenna_strip']:
    o=bpy.data.objects.get(name)
    if not o: continue
    o.shape_key_add(name='Basis')
    key=o.shape_key_add(name='Subtle_air_sway')
    for v,k in zip(o.data.vertices,key.data):
        local=v.co+rest[o.name]
        # The strip and distal coax sway; the board-end remains pinned.
        weight=max(0,min(1,(-local.x-.009)/.025))
        k.co.y+=.0035*weight*weight
    key.slider_min=-1; key.slider_max=1
    antenna.append(key)

# ---------------- CAMERA-LOCKED HERO TYPE ----------------
font_path=Path(r'C:\Windows\Fonts\segoeuil.ttf')
font=bpy.data.fonts.load(str(font_path)) if font_path.exists() else None

def srgb(v): return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4

def title(name,text,size,y,rgb,spacing):
    data=bpy.data.curves.new(name,'FONT'); data.body=text
    data.align_x='CENTER'; data.align_y='CENTER'; data.size=size; data.space_character=spacing
    if font: data.font=font
    ob=bpy.data.objects.new(name,data); scene.collection.objects.link(ob)
    ob.parent=cam; ob.location=(0,y,-.20)
    material=bpy.data.materials.new(name+'_fade'); material.use_nodes=True
    n=material.node_tree.nodes; n.clear()
    out=n.new('ShaderNodeOutputMaterial'); mix=n.new('ShaderNodeMixShader')
    transparent=n.new('ShaderNodeBsdfTransparent'); em=n.new('ShaderNodeEmission')
    em.inputs['Color'].default_value=(*[srgb(v/255) for v in rgb],1)
    material.node_tree.links.new(transparent.outputs[0],mix.inputs[1])
    material.node_tree.links.new(em.outputs[0],mix.inputs[2])
    material.node_tree.links.new(mix.outputs[0],out.inputs['Surface'])
    data.materials.append(material)
    # Text rendered separately by compositor to keep it unaffected by lens DOF.
    ob.hide_render=True
    return ob,mix.inputs[0]
# The authoritative title is composited in the encoder. These editable objects
# are kept in the .blend as a layout guide but hidden from the beauty render.
title('HERO_Super_Monkey','Super Monkey',.0065,-.018,(29,29,31),1.25)
title('HERO_Built_in_24_hours','Built in 24 hours.',.00265,-.025,(106,106,110),1.08)

# ---------------- ANIMATION ----------------
def smooth(t):
    t=max(0,min(1,t)); return t*t*(3-2*t)
def smoother(t):
    t=max(0,min(1,t)); return t*t*t*(t*(t*6-15)+10)
def lerp(a,b,t): return a+(b-a)*t
lean=Euler((math.radians(5),math.radians(-12),0),'XYZ').to_quaternion()
lying=Euler((0,math.pi/2,0),'XYZ').to_quaternion()

def camera_to(target,position,lens,fstop):
    cam.location=Vector(position)
    cam.rotation_quaternion=(Vector(target)-cam.location).to_track_quat('-Z','Y')
    cd.lens=lens; cd.dof.aperture_fstop=fstop
    focus.location=Vector(target)

# Staggered functional groups. The board first clears the housing backwards.
# Jaw clearances are deliberate slight lateral/back offsets before axial travel.
explode={
 'housing':Vector((0,0,.068)),
 'board':Vector((-.020,.035,.056)),
 'battery':Vector((0,0,.046)),
 'flange':Vector((0,0,.033)),
 'ring':Vector((0,0,.019)),
 'joint':Vector((0,0,.003)),
 'stem_jaw':Vector((.015,.009,-.027)),
 'lever_jaw':Vector((-.012,-.004,-.076)),
 'rubber':Vector((0,0,-.115)),
}
order=list(explode)

def separation(t,group):
    rank=order.index(group)
    if t<=3:
        return smoother((t-rank*.115)/1.92)
    if t<=5: return 1
    # Last separated component returns first.
    return 1-smoother((t-5-(8-rank)*.10)/1.88)

# Persist transform keys at every frame: playback and farm rendering do not
# depend on callbacks, drivers, or external Python handlers.
for frame in range(1,601):
    scene.frame_set(frame)
    for o in parts: o.location=rest[o.name]
    sway=0
    if frame<=144:
        t=(frame-1)/143
        e=smoother(t)
        root.rotation_quaternion=lying
        root.location=(0,0,.017)
        z=lerp(.012,.120,e)
        local=Vector((lerp(-.00866,0,e),lerp(-.0025,-.00967,e),z-.067))
        target=root.location+lying@local
        delta=Vector((lerp(-.025,.009,e),-.123,lerp(.064,.033,e)))
        camera_to(target,target+delta,lerp(73,82,e),lerp(9,7,e))
    elif frame<=336:
        t=(frame-145)/191*8
        root.location=(0,0,.20)
        spin=math.radians(6)*math.sin(math.pi*smooth(t/8))**2
        root.rotation_quaternion=lean @ Quaternion((0,0,1),spin)
        for o in parts:
            group=o.get('assembly_group')
            if group not in explode: continue
            amount=separation(t,group)
            offset=explode[group]*amount
            if group=='board':
                # Rearward clearance precedes axial displacement.
                offset.y=explode[group].y*smooth(min(1,amount*3))
                offset.z=explode[group].z*smoother(max(0,(amount-.22)/.78))
            elif group in {'lever_jaw','stem_jaw'}:
                offset.x=explode[group].x*smooth(min(1,amount*4))
                offset.y=explode[group].y*smooth(min(1,amount*4))
                offset.z=explode[group].z*smoother(max(0,(amount-.15)/.85))
            o.location=rest[o.name]+offset
        # Gentle dolly creates breathing room for the exploded stack.
        dolly=math.sin(math.pi*smooth(t/8))**2
        dist=lerp(.79,1.22,dolly)
        target=Vector((0,0,lerp(.198,.183,dolly)))
        angle=math.radians(22)
        pos=target+Vector((math.sin(angle)*dist,-math.cos(angle)*dist,.115*dist))
        camera_to(target,pos,65,11)
    elif frame<=480:
        t=(frame-337)/143
        e=smoother(t)
        root.location=(0,0,lerp(.20,.275,e))
        root.rotation_quaternion=lean @ Quaternion((0,0,1),2*math.pi*e)
        target=Vector((0,0,root.location.z-lerp(.002,.036,e)))
        angle=math.radians(22*(1-e))
        dist=lerp(.79,.75,e)
        pos=target+Vector((math.sin(angle)*dist,-math.cos(angle)*dist,.115*dist))
        camera_to(target,pos,65,11)
        sway=math.sin(2*math.pi*t*1.35)*math.sin(math.pi*t)**2*.8
    else:
        t=(frame-481)/119
        root.location=(0,0,.275)
        root.rotation_quaternion=lean @ Quaternion((0,0,1),2*math.pi)
        target=Vector((0,0,.239))
        camera_to(target,target+Vector((0,-.75,.08625)),65,11)
        # The scene opens up very slightly as the hero locks into place.
        world=scene.world.node_tree.nodes['Background'].inputs['Strength']
        world.default_value=lerp(.35,.43,smooth(t))
        world.keyframe_insert('default_value',frame=frame)
    root.keyframe_insert('location',frame=frame)
    root.keyframe_insert('rotation_quaternion',frame=frame)
    for o in parts: o.keyframe_insert('location',frame=frame)
    for key in antenna:
        key.value=sway; key.keyframe_insert('value',frame=frame)
    cam.keyframe_insert('location',frame=frame)
    cam.keyframe_insert('rotation_quaternion',frame=frame)
    focus.keyframe_insert('location',frame=frame)
    cd.keyframe_insert('lens',frame=frame)
    cd.dof.keyframe_insert('aperture_fstop',frame=frame)
# Set the pre-hero world value explicitly (prevents first hero key applying early).
world=scene.world.node_tree.nodes['Background'].inputs['Strength']
world.default_value=.35; world.keyframe_insert('default_value',frame=1)
world.keyframe_insert('default_value',frame=480)
# Sampled smooth trajectories use LINEAR key interpolation to avoid micro-overshoots.
for action in bpy.data.actions:
    try:
        for fc in action.fcurves:
            for k in fc.keyframe_points: k.interpolation='LINEAR'
    except AttributeError: pass
for name,start,end in SHOTS:
    scene.timeline_markers.new(name.upper(),frame=start)
scene['approval_status']='PREVIEW DRAFT — awaiting visual approval before 1080p finals'
scene['source_photos']=str(BASE)
scene['edit_notes']='Shot1 only: fade through white. Shots2-4: exact shared boundary poses.'
scene['title_notes']='Hidden editable text guides; final typography composited by encode_video.py.'
scene.frame_set(545)
scene.render.filepath=str(FRAMES/'frame_')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'super_monkey_pitch.blend'))
# Record continuity: shared boundaries intentionally duplicate one pose.
continuity={}
for a,b in [(336,337),(480,481)]:
    scene.frame_set(a)
    ra=root.matrix_world.copy(); ca=cam.matrix_world.copy()
    scene.frame_set(b)
    continuity[f'{a}->{b}']={
        'root_max_matrix_delta':max(abs(ra[i][j]-root.matrix_world[i][j]) for i in range(4) for j in range(4)),
        'camera_max_matrix_delta':max(abs(ca[i][j]-cam.matrix_world[i][j]) for i in range(4) for j in range(4))}
(OUT/'continuity_check.json').write_text(json.dumps(continuity,indent=2))

if ACTION=='BUILD':
    for frame in [1,72,144,145,218,264,336,400,480,545,600]:
        scene.frame_set(frame)
        scene.render.filepath=str(OUT/f'check_{frame:04d}.png')
        bpy.ops.render.render(write_still=True)
elif ACTION=='RENDER':
    for frame in range(1,601):
        path=FRAMES/f'frame_{frame:04d}.png'
        if path.exists(): continue
        scene.frame_set(frame); scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
    # Use system Python for the encoder (Pillow/ffmpeg are outside Blender).
    py=shutil.which('python')
    if py:
        subprocess.run([py,str(BASE/'encode_video.py'),'--mode',MODE.lower()],check=True)
print('VIDEO SCENE COMPLETE:',OUT,'MODE:',MODE,'ACTION:',ACTION)
