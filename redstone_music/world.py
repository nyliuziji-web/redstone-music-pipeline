"""Portable Java 1.21.1 NBT/Anvil and Litematica export. No Minecraft binaries."""
from collections import defaultdict
import gzip
import io
import math
from pathlib import Path
import struct
import time
import zlib


def nbt():
    try:
        import nbtlib
    except ImportError as exc:
        raise RuntimeError('World export requires nbtlib: install the package requirements first') from exc
    return nbtlib


def tag(value):
    n = nbt()
    if isinstance(value, bool): return n.Byte(value)
    if isinstance(value, int): return n.Int(value) if -(1<<31)<=value<(1<<31) else n.Long(value)
    if isinstance(value, float): return n.Double(value)
    if isinstance(value, str): return n.String(value)
    if isinstance(value, dict): return n.Compound({k: tag(v) for k, v in value.items()})
    if isinstance(value, list):
        return n.List[type(tag(value[0]))]([tag(v) for v in value]) if value else n.List[n.Compound]([])
    raise ValueError(f'Unsupported NBT value {type(value)}')


def block_state(state):
    name, sep, props = state.partition('[')
    result = {'Name': name}
    if sep: result['Properties'] = dict(p.split('=') for p in props.rstrip(']').split(','))
    return tag(result)


def signed(value): return value if value < (1 << 63) else value - (1 << 64)


def pack(values, bits, padded=True):
    if padded:
        per = 64 // bits
        data = [0] * math.ceil(len(values) / per)
        for i, value in enumerate(values): data[i // per] |= int(value) << ((i % per) * bits)
    else:
        data = [0] * math.ceil(len(values) * bits / 64)
        for i, value in enumerate(values):
            word, offset = divmod(i * bits, 64)
            data[word] |= (int(value) << offset) & ((1 << 64) - 1)
            if offset + bits > 64: data[word + 1] |= int(value) >> (64 - offset)
    return [signed(v) for v in data]


def write_litematic(path, blocks, info):
    n = nbt(); origin = info['origin']; bounds = info['bounds']
    width, height, length = (bounds[k] for k in ('width', 'height', 'length'))
    palette = ['minecraft:air']; indices = {'minecraft:air': 0}
    values = [0] * (width * height * length); entities = []
    for b in blocks:
        state = b['state']
        if state not in indices: indices[state] = len(palette); palette.append(state)
        x, y, z = (b[k] - origin[k] for k in ('x', 'y', 'z'))
        if not (0 <= x < width and 0 <= y < height and 0 <= z < length): raise ValueError('Block outside schematic')
        values[(y * length + z) * width + x] = indices[state]
        if 'nbt' in b:
            t = tag(b['nbt']); t.update({k: n.Int(v) for k, v in zip(('x','y','z'), (x,y,z))}); entities.append(t)
    region = n.Compound({'Position': tag({'x':0,'y':0,'z':0}), 'Size':tag({'x':width,'y':height,'z':length}),
        'BlockStatePalette': n.List[n.Compound]([block_state(s) for s in palette]),
        'BlockStates': n.LongArray(pack(values, max(2,(len(palette)-1).bit_length()),False)),
        'TileEntities': n.List[n.Compound](entities), 'Entities': n.List[n.Compound]([]),
        'PendingBlockTicks':n.List[n.Compound]([]),'PendingFluidTicks':n.List[n.Compound]([])})
    now = int(time.time()*1000)
    document = n.File({'Version':n.Int(6),'SubVersion':n.Int(1),'MinecraftDataVersion':n.Int(3955),
        'Metadata':tag({'Name':info['title'],'Author':'Redstone Music Pipeline','Description':'Physical redstone performance; companion datapack required',
            'RegionCount':1,'TotalVolume':len(values),'TotalBlocks':len(blocks),'TimeCreated':now,'TimeModified':now,
            'EnclosingSize':{'x':width,'y':height,'z':length}}), 'Regions':n.Compound({'Performance':region})},gzipped=True)
    document['Metadata']['TimeCreated'] = n.Long(now); document['Metadata']['TimeModified'] = n.Long(now)
    document.save(str(path))
    # Decode bit packing independently of the writer, including long boundaries.
    loaded = n.load(str(path))['Regions']['Performance']; bits=max(2,(len(palette)-1).bit_length())
    raw = [int(v)&((1<<64)-1) for v in loaded['BlockStates']]
    for b in blocks:
        x,y,z=(b[k]-origin[k] for k in ('x','y','z')); index=(y*length+z)*width+x
        word,offset=divmod(index*bits,64); value=raw[word]>>offset
        if offset+bits>64: value |= raw[word+1]<<(64-offset)
        if value&((1<<bits)-1) != indices[b['state']]: raise ValueError('Schematic roundtrip failed')
    return {'blocks':len(blocks),'everyPlacedBlockExactRoundTrip':True,'minecraftDataVersion':3955}


def write_world(world, blocks, info):
    n = nbt(); world=Path(world); world.mkdir(parents=True,exist_ok=True)
    generator={'type':'minecraft:flat','settings':{'biome':'minecraft:the_void','layers':[{'height':1,'block':'minecraft:air'}],
               'lakes':False,'features':False,'structure_overrides':[]}}
    data=tag({'DataVersion':3955,'version':19133,'Version':{'Name':'1.21.1','Id':3955,'Snapshot':False},
        'LevelName':info['title'],'GameType':1,'allowCommands':True,'hardcore':False,'Difficulty':0,
        'SpawnX':37,'SpawnY':111,'SpawnZ':68,'SpawnAngle':180.0,'Time':0,'DayTime':18000,
        'GameRules':{'doDaylightCycle':'false','doWeatherCycle':'false','doMobSpawning':'false','randomTickSpeed':'0','spawnChunkRadius':'0'},
        'WorldGenSettings':{'seed':0,'generate_features':False,'bonus_chest':False,'dimensions':{
            'minecraft:overworld':{'type':'minecraft:overworld','generator':generator},
            'minecraft:the_nether':{'type':'minecraft:the_nether','generator':{'type':'minecraft:noise','biome_source':{'type':'minecraft:multi_noise','preset':'minecraft:nether'},'settings':'minecraft:nether'}},
            'minecraft:the_end':{'type':'minecraft:the_end','generator':{'type':'minecraft:noise','biome_source':{'type':'minecraft:the_end'},'settings':'minecraft:end'}}}},
        'DataPacks':{'Enabled':['vanilla','file/helper'],'Disabled':[]}})
    for key in ('Time','DayTime'): data[key]=n.Long(int(data[key]))
    data['WorldGenSettings']['seed']=n.Long(0)
    data['Difficulty']=n.Byte(0); data['SpawnAngle']=n.Float(180)
    data['ScheduledEvents']=n.List[n.Compound]([])
    n.File({'Data':data},gzipped=True).save(str(world/'level.dat'))
    chunks=defaultdict(list)
    for b in blocks: chunks[b['x']//16,b['z']//16].append(b)
    regions=defaultdict(dict)
    for (cx,cz),bs in chunks.items():
        sections=defaultdict(list); entities=[]; heights=[0]*256
        for b in bs:
            sections[b['y']//16].append(b)
            heights[(b['z']%16)*16+b['x']%16]=max(heights[(b['z']%16)*16+b['x']%16],b['y']+65)
            if 'nbt' in b:
                t=tag(b['nbt']);t.update({k:n.Int(b[k]) for k in ('x','y','z')});entities.append(t)
        ss=[]
        for sy in range(-4,20):
            palette=['minecraft:air']; lookup={'minecraft:air':0}; values=[0]*4096
            for b in sections[sy]:
                state=b['state']
                if state not in lookup:lookup[state]=len(palette);palette.append(state)
                values[(b['y']%16)*256+(b['z']%16)*16+b['x']%16]=lookup[state]
            states=n.Compound({'palette':n.List[n.Compound]([block_state(s) for s in palette])})
            if len(palette)>1:states['data']=n.LongArray(pack(values,max(4,(len(palette)-1).bit_length())))
            ss.append(n.Compound({'Y':n.Byte(sy),'block_states':states,'biomes':n.Compound({'palette':n.List[n.String](['minecraft:the_void'])})}))
        chunk=n.File({'DataVersion':n.Int(3955),'xPos':n.Int(cx),'zPos':n.Int(cz),'yPos':n.Int(-4),
            'Status':n.String('minecraft:full'),'LastUpdate':n.Long(0),'InhabitedTime':n.Long(0),'isLightOn':n.Byte(0),
            'sections':n.List[n.Compound](ss),'block_entities':n.List[n.Compound](entities),
            'block_ticks':n.List[n.Compound]([]),'fluid_ticks':n.List[n.Compound]([]),
            'Heightmaps':n.Compound({k:n.LongArray(pack(heights,9)) for k in ('MOTION_BLOCKING','WORLD_SURFACE')})})
        stream=io.BytesIO();chunk.write(stream);encoded=zlib.compress(stream.getvalue())
        regions[cx//32,cz//32][(cz%32)*32+cx%32]=struct.pack('>I',len(encoded)+1)+b'\x02'+encoded
    region=world/'region';region.mkdir(exist_ok=True)
    for (rx,rz),cs in regions.items():
        header=bytearray(8192);body=bytearray();offset=2
        for index,payload in sorted(cs.items()):
            sectors=math.ceil(len(payload)/4096)
            if sectors>255:raise ValueError('Chunk exceeds Anvil sector capacity')
            header[index*4:index*4+4]=((offset<<8)|sectors).to_bytes(4,'big')
            body.extend(payload.ljust(sectors*4096,b'\0'));offset+=sectors
        (region/f'r.{rx}.{rz}.mca').write_bytes(header+body)
    return {'chunks':len(chunks),'regions':len(regions),'blocks':len(blocks),'directAnvilExport':True,'runtimeVerified':False}
