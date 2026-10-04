"""Super Monkey — PHASE 1 ONLY. Blender 4.2+ / 5.x.
Paste this entire file into Blender's Scripting workspace and Run Script.
WARNING: clears the current scene. Save other work first.
Outputs: C:/Users/HP/Downloads/hackathon/pitch/phase1_output
Photo-derived reconstruction, NOT a measured or render-validated replica.
No animation is generated before model approval.
"""
import bpy
import os
import math
import json
import html
from pathlib import Path
from mathutils import Vector
from math import sin, cos, pi

# ---------------- USER SETTINGS / OUTPUT PATH ----------------
SOURCE = Path(r'C:\Users\HP\Downloads\hackathon\pitch')
OUT = SOURCE / 'phase1_output'
RENDER_STILLS = os.environ.get('SM_RENDER_STILLS', '1') == '1'
RESOLUTION = int(os.environ.get('SM_RESOLUTION', '1200'))
SAMPLES = int(os.environ.get('SM_SAMPLES', '48'))
# Modelling coordinates are millimetres, converted to metres before export.
MM = 0.001
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'stills').mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'MILLIMETERS'
scene.render.engine = 'CYCLES'
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.image_settings.file_format = 'PNG'
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.view_settings.view_transform = 'AgX'
scene.world.color = (0.7, 0.7, 0.7)
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.75,.75,.78,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .45

parts = []
groups = {}
def material(name, color, roughness=.35, metallic=0, transmission=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color,1)
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Transmission Weight'].default_value = transmission
    return m
white = material('Satin white moulded plastic', (.83,.845,.86), .29)
green = material('Soft green rubber', (.20,.48,.065), .32)
black = material('Matte black insulation', (.009,.012,.014), .64)
brown = material('Brown insulation', (.23,.065,.035), .55)
boardmat = material('Black PCB; no text or logos', (.014,.022,.019), .55)
silver = material('Brushed pouch aluminium', (.66,.69,.72), .30, .86)
silver.node_tree.nodes['Principled BSDF'].inputs['Anisotropic'].default_value = .65
amber = material('Translucent amber tape', (.9,.48,.018), .20, 0, .72)
amber.node_tree.nodes['Principled BSDF'].inputs['IOR'].default_value = 1.46
lensmat = material('Black optical glass', (.004,.007,.014), .075, .12, .18)
lensmat.node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value = .65
contactmat = material('Muted solder contacts', (.38,.39,.36), .3, .8)

def active(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o

def apply(o, mod):
    active(o)
    bpy.ops.object.modifier_apply(modifier=mod.name)

def bevel(o, amount=.35, segments=3):
    m = o.modifiers.new('Small moulded edge radii', 'BEVEL')
    m.width = amount
    m.segments = segments
    apply(o,m)
    return o

def finish(o, name, mat, group):
    o.name = name
    if mat: o.data.materials.append(mat)
    if group:
        parts.append(o)
        groups[o.name] = group
    return o

def box(name, loc, dims, mat=white, group=None, radius=.35):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.dimensions = dims
    active(o)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if radius: bevel(o, radius)
    return finish(o,name,mat,group)

def cylinder(name, loc, radius, depth, mat=white, group=None, axis='Z', edge=.18):
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=depth, location=loc)
    o = bpy.context.object
    if axis == 'Y': o.rotation_euler.x = pi/2
    if axis == 'X': o.rotation_euler.y = pi/2
    active(o)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if edge: bevel(o,edge)
    return finish(o,name,mat,group)

def sphere(name, loc, radius, mat=white, group=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=radius, location=loc)
    o = bpy.context.object
    for p in o.data.polygons: p.use_smooth = True
    return finish(o,name,mat,group)

def boolean(o, cutter, operation='DIFFERENCE'):
    m = o.modifiers.new('Mating geometry', 'BOOLEAN')
    m.operation = operation
    m.solver = 'EXACT'
    m.object = cutter
    apply(o,m)
    bpy.data.objects.remove(cutter, do_unlink=True)

def join_into(o, others):
    # Union is used for solid plastic bodies, not loose overlapping primitives.
    for other in others: boolean(o, other, 'UNION')
    return o

def curve(name, points, radius, mat, group=None, cyclic=False):
    c = bpy.data.curves.new(name, 'CURVE')
    c.dimensions = '3D'
    c.resolution_u = 24
    c.bevel_depth = radius
    c.bevel_resolution = 4
    c.use_fill_caps = True
    s = c.splines.new('BEZIER')
    s.bezier_points.add(len(points)-1)
    for bp, p in zip(s.bezier_points, points):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    s.use_cyclic_u = cyclic
    o = bpy.data.objects.new(name,c)
    scene.collection.objects.link(o)
    active(o)
    bpy.ops.object.convert(target='MESH')
    return finish(bpy.context.object,name,mat,group)

def prism(name, outline, depth, mat=None, group=None):
    n = len(outline)
    verts = [(x,-depth/2,z) for x,z in outline] + [(x,depth/2,z) for x,z in outline]
    faces = [tuple(reversed(range(n))), tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    o = bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(o)
    active(o)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    return finish(o,name,mat,group)

def lathe(name, profile, mat, group=None):
    # Closed radial cross-section including inner surfaces, revolved around Z.
    n = 96
    verts = [(r*cos(2*pi*j/n),r*sin(2*pi*j/n),z) for r,z in profile for j in range(n)]
    faces = []
    for i in range(len(profile)):
        k = (i+1)%len(profile)
        for j in range(n):
            faces.append((i*n+j,i*n+(j+1)%n,k*n+(j+1)%n,k*n+j))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    o = bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(o)
    for p in mesh.polygons: p.use_smooth = True
    return finish(o,name,mat,group)

# ---------------- CLIP: coplanar split pivot, not stacked clothespin ----------------
# Axis Z points toward camera housing. Front optical direction is -Y.
pivot_z = 39
base = cylinder('Clip silhouette tool', (0,0,pivot_z), 14, 5, None, axis='Y', edge=0)
join_into(base,[box('Tip blank',(0,0,14),(10,5,28),None,radius=1.6),
               box('Left lever',(-8.5,0,62),(4.4,5,25),None,radius=1),
               box('Right stem',(8.5,0,62),(4.4,5,25),None,radius=1),
               cylinder('Rounded paddle',(-10,0,75),3.6,5,None,axis='Y',edge=.5)])
boolean(base,cylinder('Pivot through hole',(0,0,39),7.1,12,None,axis='Y',edge=0))
# Four genuine through-slots on the circular pivot.
for start,end in [(18,70),(103,158),(197,248),(283,337)]:
    pts = [(10.7*cos(math.radians(a)),0,39+10.7*sin(math.radians(a)))
           for a in range(start,end+1,3)]
    # Swept rectangular slot volume spans the full jaw thickness.
    outer = [(11.65*cos(math.radians(a)),39+11.65*sin(math.radians(a))) for a in range(start,end+1)]
    inner = [(9.75*cos(math.radians(a)),39+9.75*sin(math.radians(a))) for a in range(end,start-1,-1)]
    boolean(base,prism('Curved slot cutter',outer+inner,12))
# Split the body into two complete jaws with complementary zigzag mating faces.
seam = [(0,-3)]
for z in range(0,32):
    seam.append((.95*sin(z*pi/3.7),float(z)))
seam += [(0,33),(0,80)]
leftmask = prism('Left jaw split mask',[(-40,-3)]+seam+[(-40,80)],18)
rightmask = prism('Right jaw split mask',seam+[(40,80),(40,-3)],18)
right = base.copy()
right.data = base.data.copy()
scene.collection.objects.link(right)
boolean(base,leftmask,'INTERSECT')
boolean(right,rightmask,'INTERSECT')
base.location.x -= .16
right.location.x += .16
bevel(base,.20,3)
bevel(right,.20,3)
finish(base,'08_Clip_lever_jaw',white,'lever_jaw')
finish(right,'09_Clip_stem_jaw',white,'stem_jaw')
# Socket in stem-end: small actual ball seated in a closed-bottom spherical cavity.
socket = cylinder('10_Ball_socket', (8.66,0,76.7),5.3,5.8,white,'stem_jaw',edge=.35)
boolean(socket,sphere('Socket cavity tool',(8.66,0,79.1),3.7,None))
boolean(socket,cylinder('Socket mouth tool',(8.66,0,81.5),2.7,5,None,edge=0))
ball = sphere('07a_Concealed_ball',(8.66,0,79.1),3.45,white,'joint')
# Offset is visible in the reference clip: long axis passes through the stem, not hole.
AX = 8.66
neck = lathe('07b_Flared_joint_neck',[(1.8,81.7),(1.8,83),(5.3,83.5),(7.8,84.4),
             (7.6,85.1),(5.6,86),(4.3,88),(4.3,89.1),(0,89.1),(0,81.7)],white,'joint')
neck.location.x = AX
# One continuous rubber band with four turns and a closure on the back.
rubber_points=[]
for i in range(161):
    t=i/160
    a=2*pi*4*t
    # Rounded rectangular loop; soft corners rather than a circular band.
    x=5.9*math.copysign(abs(cos(a))**.48,cos(a))
    y=3.5*math.copysign(abs(sin(a))**.48,sin(a))
    rubber_points.append((x,y,10+9*t))
rubber_points += [(6.1,4,17),(6.2,4,12),(5.9,0,10)]
curve('11_Green_rubber_band_four_turns',rubber_points,.83,green,'rubber',True)

# ---------------- RIBBED RING / FLANGE ----------------
ring = lathe('06_Ribbed_ring_body',[(14.1,89.2),(14.3,89.7),(14.3,98),
             (13.9,98.5),(3,98.5),(3,96.7),(4.6,96.7),(4.6,89.2)],white,'ring')
ring.location.x=AX
# Integrate forty ribs into the ring's one watertight body.
for i in range(40):
    a=i*2*pi/40
    rib=box('Grip rib tool',(AX+14.1*cos(a),14.1*sin(a),93.85),(1.5,1.05,8.5),None,radius=.40)
    rib.rotation_euler.z=a
    boolean(ring,rib,'UNION')
gasket=lathe('05_Thin_green_band',[(12.6,98.65),(12.6,100.1),(3,100.1),(3,98.65)],green,'flange')
gasket.location.x=AX
flange=lathe('04_White_disc_flange',[(13.3,100.15),(13.3,102.2),(3,102.2),(3,100.15)],white,'flange')
flange.location.x=AX
bevel(flange,.2)
# Socket-like recesses / bore are retained, not filled with intersecting caps.

# ---------------- BATTERY / CAMERA ----------------
battery=box('03a_Silver_foil_pouch',(AX,0,104.7),(35,23,4.4),silver,'battery',radius=1.2)
# A shallow folded pouch perimeter, joined as part of the battery shell.
# Foil has a restrained brushed surface, without printed labels.
nt=silver.node_tree
tex=nt.nodes.new('ShaderNodeTexNoise')
tex.inputs['Scale'].default_value=180
tex.inputs['Detail'].default_value=2
bump=nt.nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value=.10
bump.inputs['Distance'].default_value=.000035
nt.links.new(tex.outputs['Fac'],bump.inputs['Height'])
nt.links.new(bump.outputs['Normal'],nt.nodes['Principled BSDF'].inputs['Normal'])
tape=box('03b_Amber_tape_wrap',(AX+14.3,0,104.7),(6.9,23.35,4.75),amber,'battery',radius=1.2)
boolean(tape,box('Tape hollow tool',(AX+14.3,0,104.7),(7.8,23.02,4.43),None,radius=1.1))
# Closed housing, recessed front bezel and a physical top USB-C recess.
housing=box('01a_Camera_housing',(AX,0,118.1),(21,14,22),white,'housing',radius=1.6)
portcut=box('USB C cavity tool',(AX,-.1,129),(8.7,3.4,4.0),None,radius=1.5)
boolean(housing,portcut)
port=box('01d_USB_C_metal_liner',(AX,-.1,128.05),(8.25,3.0,1.6),silver,'housing',radius=1.25)
boolean(port,box('USB opening tool',(AX,-.1,128.5),(7.65,2.35,2.2),None,radius=1.0))
box('01e_USB_C_dark_recess',(AX,-.1,127.4),(7.5,2.25,.25),black,'housing',radius=.1)
box('01f_USB_C_contact_tongue',(AX,-.1,128),(5.6,.65,.4),black,'housing',radius=.18)
bezel=box('01b_Raised_square_bezel',(AX,-8.05,120),(13.2,3.3,13.2),white,'housing',radius=1.1)
boolean(bezel,cylinder('Lens seat cutter',(AX,-8.5,120),4.55,6,None,axis='Y',edge=0))
cylinder('01c_Black_lens_barrel',(AX,-8.25,120),4.38,2.7,black,'housing',axis='Y',edge=.2)
cylinder('01g_Optical_glass',(AX,-9.67,120),3.65,.24,lensmat,'housing',axis='Y',edge=.10)
# Back board lies on the back of the housing. No speculative lettering/components.
box('02a_Back_circuit_board',(AX,7.7,122.2),(12.5,1.1,24),boardmat,'board',radius=.25)
# Only muted contact pads, visible in the supplied rear reference.
for i in range(3):
    box('02b_Solder_pad_%02d'%i,(AX-4+i*3.5,8.32,111.7),(1.25,.12,1.8),contactmat,'board',radius=.08)
curve('02c_Brown_battery_wire',[(AX-3,8.5,112),(AX-11,8.9,110),(AX-12,3,121),
      (AX-10,-2,132),(AX-5,-3,133),(AX+8,2,132),(AX+18,5,110),(AX+16,3,105)],.61,brown,'board')
curve('02d_Black_battery_wire',[(AX+3,8.5,112),(AX-10,10,109),(AX-13,5,118),
      (AX-11,-.5,130),(AX-7,-1,132),(AX+9,4,131),(AX+18,7,109),(AX+16,5,105)],.53,black,'board')
curve('02e_Antenna_coax',[(AX+4,7.9,129),(AX+2,9,134),(AX-14,8,133),
      (AX-25,5,126),(AX-29,3,119)],.43,black,'board')
# Flexible strip follows a curved ribbon; no reference branding reproduced.
verts=[]
for i in range(25):
    t=i/24
    x=AX-29-2*sin(pi*t)
    y=3-3*sin(pi*t)
    z=119-25*t
    verts += [(x-4,y,z),(x+4,y,z)]
mesh=bpy.data.meshes.new('Curved antenna ribbon mesh')
mesh.from_pydata(verts,[],[(2*i,2*i+1,2*i+3,2*i+2) for i in range(24)])
mesh.update()
ribbon=bpy.data.objects.new('02f_Flexible_antenna_strip',mesh)
scene.collection.objects.link(ribbon)
sol=ribbon.modifiers.new('Real strip thickness','SOLIDIFY'); sol.thickness=.25
apply(ribbon,sol)
bevel(ribbon,.10,2)
finish(ribbon,ribbon.name,black,'board')

# ---------------- CENTRES, SCALE, ROOT, EXPORT ----------------
root=bpy.data.objects.new('Super_Monkey_ROOT',None)
scene.collection.objects.link(root)
root.empty_display_type='PLAIN_AXES'
root.empty_display_size=.02
manifest=[]
for o in parts:
    active(o)
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY',center='BOUNDS')
    for v in o.data.vertices: v.co *= MM
    o.location *= MM
    o.parent=root
    o['assembly_group']=groups[o.name]
    o['status']='Photo-derived draft; hidden geometry assumed; approval required'
    manifest.append({'name':o.name,'assembly_group':groups[o.name],
                     'dimensions_mm':[round(v/MM,3) for v in o.dimensions]})
bpy.context.view_layer.update()
# Refresh dimensions after scaling mesh data.
for row,o in zip(manifest,parts): row['dimensions_mm']=[round(v/MM,3) for v in o.dimensions]
(OUT/'parts_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
bpy.ops.object.select_all(action='DESELECT')
root.select_set(True)
for o in parts: o.select_set(True)
bpy.context.view_layer.objects.active=root
bpy.ops.export_scene.gltf(filepath=str(OUT/'super_monkey_model.glb'),export_format='GLB',use_selection=True)

# ---------------- REVIEW STUDIO ----------------
background=material('Light grey review background',(.913,.913,.930),.8)
# Camera-facing seamless background is the world; floor is below clip tip.
floor=box('STUDIO_ground',(0,0,-.004),(2,2,.006),background,radius=0)
# box() is in current coordinate units: these are already metres.

def area(name,loc,power,size,target):
    d=bpy.data.lights.new(name,'AREA'); d.energy=power; d.shape='DISK'; d.size=size
    o=bpy.data.objects.new(name,d); scene.collection.objects.link(o); o.location=loc
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    return o
area('Large soft upper-left key',(-.16,-.18,.28),12,.20,(0,0,.075))
area('Gentle fill',(.17,-.08,.15),5,.17,(0,0,.075))
area('Soft rim',(.04,.16,.23),10,.15,(0,0,.075))
d=bpy.data.cameras.new('Review_camera')
cam=bpy.data.objects.new('Review_camera',d)
scene.collection.objects.link(cam)
scene.camera=cam
d.type='ORTHO'; d.lens=65; d.clip_start=.001; d.clip_end=10

def camera_view(target,direction,scale,roll=0):
    target=Vector(target)
    cam.location=target+Vector(direction).normalized()*.48
    q=(target-cam.location).to_track_quat('-Z','Y')
    from mathutils import Quaternion
    cam.rotation_euler=(q @ Quaternion((0,0,1),roll)).to_euler()
    d.ortho_scale=scale

views=[]
def render(name,target,direction,scale,roll=0,reference=None,square=False):
    camera_view(target,direction,scale,roll)
    scene.render.resolution_x=RESOLUTION
    scene.render.resolution_y=RESOLUTION if square else round(RESOLUTION*9/16)
    scene.render.filepath=str(OUT/'stills'/f'{name}.png')
    if RENDER_STILLS: bpy.ops.render.render(write_still=True)
    views.append({'name':name,'reference':reference,'image':f'stills/{name}.png'})

# Pose / optics are initial approximations, not solved camera matches.
# Hide floor for rotated photo compositions; avoids an incorrect diagonal horizon.
floor.hide_render=True
render('01_front_photo_angle',(.001,0,.068),(.22,-1,.18),.30,math.radians(22),
       'full front view.jpg.jpeg')
render('02_back_photo_angle',(.001,0,.069),(-.28,1,.25),.205,math.radians(-90),
       'full back view.jpg.jpeg')
render('03_head_photo_angle',(.008,0,.109),(.40,-1,.50),.095,math.radians(76),
       'close-up of the camera, battery and ring.jpg.jpeg')
render('04_clip_photo_angle',(.004,0,.043),(.1,-1,.22),.125,math.radians(75),
       'close-up of the clip and ball joint.jpg.jpeg')
for name,direction in [('front',(0,-1,0)),('back',(0,1,0)),('left',(-1,0,0)),
                       ('right',(1,0,0)),('top',(0,0,1)),('bottom',(0,0,-1))]:
    render('turnaround_'+name,(0,0,.067),direction,.175,square=True)
# Fully separated illustration: each named part gets its own axial gap.
# This is not the later animation's functional group explosion.
original={o.name:o.location.copy() for o in parts}
ordered=sorted(parts,key=lambda o:(o.location.z,o.name))
z_cursor=0
for o in ordered:
    half=o.dimensions.z/2
    o.location.z=z_cursor+half
    z_cursor+=o.dimensions.z+.009
render('11_all_parts_axial_separation',(.003,0,z_cursor/2),(.32,-1,.12),
       z_cursor*1.14,square=True)
for o in parts: o.location=original[o.name]
# Additional group explosion is easier to read at normal product-review scale.
offsets={'rubber':-.045,'lever_jaw':0,'stem_jaw':.070,'joint':.115,
         'ring':.145,'flange':.17,'battery':.195,'board':.24,'housing':.28}
for o in parts:
    o.location.z+=offsets[groups[o.name]]
    if groups[o.name]=='board': o.location.y+=.028
render('12_functional_groups_separated',(.003,0,.185),(.45,-1,.14),.50,square=True)
for o in parts: o.location=original[o.name]
floor.hide_render=False
camera_view((0,0,.069),(.22,-1,.18),.24)
scene.render.resolution_x=1920; scene.render.resolution_y=1080
scene.render.fps=24
scene['phase']='1 — draft, awaiting rendered comparison and approval'
scene['dimensions']='135 / 30 / 80 mm are unverified supplied estimates'
scene['reference_folder']=str(SOURCE)
scene['coordinate_system']='Metres; long axis +Z; lens faces -Y; clip lies in XZ'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'super_monkey_phase1.blend'))

# A local HTML comparison sheet uses original photos without resampling them.
page=['<!doctype html><meta charset="utf-8"><title>Super Monkey — Phase 1 review</title>',
      '<style>body{font:16px system-ui;background:#eee;color:#222;margin:28px}section{margin-bottom:32px}img{max-width:48%;max-height:680px;object-fit:contain;background:#ddd}h2{font-weight:500}.grid{display:grid;grid-template-columns:repeat(3,1fr)}.grid img{max-width:100%}</style>',
      '<h1>Super Monkey — Phase 1 draft review</h1>',
      '<p>Reference photos are ground truth. These renders have NOT been validated automatically. Supplied dimensions and hidden geometry remain assumptions. No Phase 2 approval is implied.</p>']
for v in views[:4]:
    page += ['<section><h2>'+html.escape(v['name'])+'</h2>',
             '<p>Left: original reference. Right: initial reconstruction.</p>',
             '<img src="'+html.escape('../'+v['reference'],quote=True)+'">',
             '<img src="'+v['image']+'"></section>']
page += ['<h2>Six-view turnaround</h2><div class="grid">']
for v in views[4:10]: page += ['<div><p>'+v['name']+'</p><img src="'+v['image']+'"></div>']
page += ['</div>']
for v in views[10:]: page += ['<h2>'+v['name']+'</h2><img style="max-width:100%" src="'+v['image']+'">']
(OUT/'review.html').write_text('\n'.join(page),encoding='utf-8')
print('\nPHASE 1 DRAFT COMPLETE:',OUT)
print('Open review.html; inspect comparisons; revise before approval. No animation rendered.')
