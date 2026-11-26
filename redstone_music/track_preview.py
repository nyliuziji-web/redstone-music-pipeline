"""Design review plate made from the exact block coordinates, before client capture."""
from pathlib import Path

from .core import atomic_json, read_json

COLORS = {
    'waxed_cut_copper': (190,112,66),
    'dark_prismarine': (55,130,126),
    'prismarine_bricks': (91,166,155),
    'smooth_quartz': (206,216,236),
    'polished_blackstone': (63,67,81),
    'deepslate_tiles': (66,78,94),
    'deepslate_tile_slab': (58,71,87),
    'polished_deepslate': (74,86,107),
    'ochre_froglight': (255,222,153),
    'verdant_froglight': (192,255,185),
    'pearlescent_froglight': (255,227,249),
    'note_block': (217,144,97),
    'redstone_lamp': (143,111,76),
}


def preview_track(placement, out):
    from PIL import Image, ImageDraw, ImageFont

    value = read_json(placement)
    plan = value.get('info',{}).get('trackPlan')
    if not plan or not value.get('blocks'):
        raise ValueError('Use placed_blocks.json from a score-track build')
    folder = Path(out).resolve()
    folder.mkdir(parents=True,exist_ok=False)
    # Keep the preview to eight phrase cards; leave all layout facts in the plan.
    sections = plan['sections']
    indexes = sorted({round(i*(len(sections)-1)/max(1,min(8,len(sections))-1))
                      for i in range(min(8,len(sections)))})
    panels = [sections[i] for i in indexes]
    wide, tall = 584, 390
    sheet = Image.new('RGB',(38+wide*min(3,len(panels)),82+tall*((len(panels)+2)//3)), '#0e1720')
    draw = ImageDraw.Draw(sheet)
    def font(size):
        try:
            return ImageFont.truetype('DejaVuSans.ttf',size)
        except OSError:
            return ImageFont.load_default(size)
    draw.text((24,20),'MUSICAL TRACK / BLOCK GEOMETRY',fill='#ebf2f4',font=font(22))
    draw.text((24,51),'Isometric excerpts from the exported layout',fill='#9fb2c6',font=font(13))
    panel_rows = []
    for i,section in enumerate(panels):
        mid=(section['beginGT']+section['endGT'])//2+80
        lower=max(section['beginGT']+80,mid-27)
        upper=min(section['endGT']+80,lower+55)
        ox,oy=24+(i%3)*wide,80+(i//3)*tall
        draw.rounded_rectangle((ox,oy,ox+wide-20,oy+tall-18),12,fill='#152331')
        draw.text((ox+16,oy+12),f"{section['index']+1:02}  {section['label']}",font=font(18),fill='#edf3f8')
        draw.text((ox+16,oy+39),f"{section['style'].title()}  /  {len(section['lanes'])} clock lanes  /  "
                  f"{section['peakStarts']} max starts per tick",font=font(13),fill='#a9b9c8')
        blocks=[b for b in value['blocks'] if lower<=b['z']<upper]
        def project(x,y,z):
            return (x-(z-lower)*.72,(x+(z-lower)*.8)*.36-(y-88)*.91)
        faces=[]
        for b in blocks:
            x,y,z=b['x'],b['y'],b['z']
            name=b['state'].split('[',1)[0].removeprefix('minecraft:')
            color=COLORS.get(name,(111,129,147))
            h=.5 if name.endswith('_slab') else .22 if name in ('repeater','redstone_wire') else 1.
            corners=[(x,y,z),(x+1,y,z),(x+1,y,z+1),(x,y,z+1)]
            corners += [(a,c+h,d) for a,c,d in corners]
            for face, shade in [((1,2,6,5),.68),((2,3,7,6),.82),((4,5,6,7),1.)]:
                pts=[project(*corners[j]) for j in face]
                faces.append((x+(z-lower)*.8+y*.18,pts,tuple(round(k*shade) for k in color)))
        if faces:
            pts=[v for _,polygon,_ in faces for v in polygon]
            minx,maxx=min(x for x,_ in pts),max(x for x,_ in pts)
            miny,maxy=min(y for _,y in pts),max(y for _,y in pts)
            scale=min((wide-60)/max(1,maxx-minx),290/max(1,maxy-miny))
            for _,poly,col in sorted(faces,key=lambda x:x[0]):
                draw.polygon([(ox+30+(x-minx)*scale,oy+66+(y-miny)*scale) for x,y in poly],fill=col)
        panel_rows.append({'phrase':section['index'],'zStart':lower,'zEnd':upper,'blocks':len(blocks)})
    media=folder/'track-review.png'
    sheet.save(media)
    report={'schemaVersion':1,'image':str(media),'panels':panel_rows,
            'actualMinecraftImage':False,'source':'isometric projection of compiled placed blocks'}
    atomic_json(folder/'review.json',report)
    return report
