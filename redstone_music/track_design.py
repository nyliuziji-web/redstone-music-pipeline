"""Place bounded, independent physical clock banks in response to musical phrases."""
from collections import Counter, defaultdict
import math

from .core import atomic_json, read_json

PALETTES = {
    'copper': ('waxed_cut_copper','deepslate_tiles','ochre_froglight'),
    'tide': ('dark_prismarine','prismarine_bricks','verdant_froglight'),
    'moon': ('smooth_quartz','polished_blackstone','pearlescent_froglight'),
}
FOREGROUND = {'theme_attack','voice'}
LOW_ROLES = {'sub_bass','mid_bass','kick','snare','hats','fx'}


def local_tick(event, timing):
    return event.get('q',event['gt']-timing.get('sourceOffsetGT',0))


def _sections(events, ticks):
    """Prefer real source markers; otherwise cut by a local valley in attacks."""
    end = events['musicGT']
    known = {s['beginGT']:s['name'] for s in events.get('sections',[]) if 0<s['beginGT']<end}
    bounds = [0]
    while end-bounds[-1] > 159:
        previous = bounds[-1]
        choices = [t for t in known if previous+80<=t<=min(previous+320,end-65)]
        if choices:
            target = min(choices,key=lambda t:(abs(t-previous-160),t))
        else:
            high = min(end-65,previous+212)
            if high < previous+80:
                break
            target = min(range(previous+80,high+1),key=lambda t:(
                sum(ticks.get(q,0) for q in range(t-2,t+3)),abs(t-previous-160),t%2,t))
        bounds.append(target)
    bounds.append(end)
    return [{'beginGT':a,'endGT':b,'label':known.get(a,f'Phrase {i+1}')}
            for i,(a,b) in enumerate(zip(bounds,bounds[1:]))]


def _override(data, events, roles):
    if data is None:
        return {}
    if (not isinstance(data,dict) or data.get('schemaVersion')!=1
            or set(data)-{'schemaVersion','style','sections','sourceMidiSha256'}):
        raise ValueError('Track design needs schemaVersion 1 with optional style and sections')
    if 'sourceMidiSha256' in data and data['sourceMidiSha256']!=events.get('sourceMidiSha256'):
        raise ValueError('Track design binds a different MIDI master')
    style = data.get('style','copper')
    if not isinstance(style,str) or style not in PALETTES:
        raise ValueError('Unknown passive architectural palette')
    sections = data.get('sections')
    if sections is None:
        return data
    if not isinstance(sections,list) or not 1<=len(sections)<=256:
        raise ValueError('Track design needs 1..256 contiguous phrases')
    cursor = 0
    for row in sections:
        if not isinstance(row,dict) or set(row)-{'beginGT','endGT','label','style','focus','spread','terrace','turn','anchors'}:
            raise ValueError('Unknown track phrase property')
        a,b = row.get('beginGT'),row.get('endGT')
        if (type(a) is not int or type(b) is not int or a!=cursor or not a<b<=events['musicGT']
                or (len(sections)>1 and b-a<40)):
            raise ValueError('Track phrases must cover the score in order and span at least 40 GT each')
        label, focus = row.get('label','Phrase'),row.get('focus')
        chosen_style = row.get('style',style)
        if (not isinstance(label,str) or not 1<=len(label)<=48 or not label.isprintable()
                or focus is not None and (not isinstance(focus,str) or focus not in roles)
                or not isinstance(chosen_style,str) or chosen_style not in PALETTES):
            raise ValueError('Invalid phrase label, focus role or architectural palette')
        for key,lo,hi in [('spread',0,3),('terrace',-2,2),('turn',-1,1)]:
            v = row.get(key,0)
            if type(v) is not int or not lo<=v<=hi:
                raise ValueError(f'Invalid phrase {key} ({lo}..{hi})')
        anchors = row.get('anchors',{})
        if not isinstance(anchors,dict) or any(
                key not in roles or not isinstance(p,list) or len(p)!=2
                or not all(type(x) is int for x in p) or not (7<=p[0]<=72 and 92<=p[1]<=125)
                for key,p in anchors.items()):
            raise ValueError('Phrase anchors map roles to absolute [x,y] inside the clock corridor')
        cursor = b
    if cursor != events['musicGT']:
        raise ValueError('Track phrases must end at the last tick of the physical score')
    return data


def design_track(events, roles, design=None, preferred=None, camera=None):
    all_ticks = Counter(local_tick(n,events) for n in events['candidates'])
    if not all_ticks or any(type(t) is not int or not 0<=t<events['musicGT'] for t in all_ticks):
        raise ValueError('Track design needs a nonempty score on one valid game clock')
    if any(n['family'] not in roles for n in events['candidates']):
        raise ValueError('Unsupported event family in track design')
    data = _override(design,events,roles)
    sections = data.get('sections') or _sections(events,all_ticks)
    points = [(x,y) for x in range(7,73) for y in range(92,126)]
    camera = camera or {'x':37.5,'eyeY':112.5}
    # Positions are continuous integer choices; reserve each electrical footprint
    # until its last note plus a gap for the next bank's head.
    reserved = []
    previous_pos = {}
    previous_density = 0
    previous_turn = 0
    output = []
    assigned = []
    for index, anchor in enumerate(sections):
        a,b = anchor['beginGT'],anchor['endGT']
        events_here = defaultdict(lambda: defaultdict(list))
        for n in events['candidates']:
            tick = local_tick(n,events)
            if a<=tick<b:
                events_here[n['family']][tick].append(n)
        density = max((all_ticks[q] for q in all_ticks if a<=q<b),default=0)
        family_counts = {family:sum(map(len,by_tick.values())) for family,by_tick in events_here.items()}
        focus = anchor.get('focus')
        if focus is None and family_counts:
            focus = min(family_counts,key=lambda family:(
                family not in FOREGROUND,-family_counts[family],family in LOW_ROLES,family))
        low_activity = sum(count for family,count in family_counts.items() if family in LOW_ROLES)
        other_activity = sum(family_counts.values())-low_activity
        if density == 0:
            direction = previous_turn
        elif low_activity > other_activity:
            direction = -1
        elif density > previous_density and (previous_density > 0 or density >= 5):
            direction = 1
        else:
            direction = previous_turn
        rise = 1 if density >= 5 and density > previous_density else 0
        if index and density < previous_density and low_activity > other_activity:
            rise = -1
        spread = anchor.get('spread',min(3,max(0,(density-1)//2)))
        turn = anchor.get('turn',direction)
        terrace = anchor.get('terrace',rise)
        previous_density, previous_turn = density, turn
        if focus is not None and focus not in events_here:
            raise ValueError(f'Phrase {index+1} has no events in its focus role {focus}')
        anchors = anchor.get('anchors',{})
        if anchors.keys()-events_here.keys():
            raise ValueError(f'Phrase {index+1} has an anchor for an inactive role')
        row = {**anchor,'label':anchor.get('label',f'Phrase {index+1}'),'index':index,
               'style':anchor.get('style',data.get('style','copper')),'spread':spread,
               'turn':turn,'terrace':terrace,'peakStarts':density,'lanes':[]}
        if 'focus' not in anchor:
            row['focus'] = focus
        if not {'focus','spread','terrace','turn'} <= anchor.keys():
            row['scoreActivity'] = {'onsetsByFamily':family_counts,'lowOnsets':low_activity}
        # Preserve priority for audible foreground, then place strongest entries first.
        family_order = sorted(events_here,key=lambda name:(
            name not in anchors,name!=focus,name not in FOREGROUND,-family_counts[name],name))
        reserved = [(x,y,until) for x,y,until in reserved if until>a+11]
        for fi, family in enumerate(family_order):
            at_ticks = events_here[family]
            rows = math.ceil(max(map(len,at_ticks.values()))/2)
            allocation = [defaultdict(list) for _ in range(rows)]
            for tick, packet in sorted(at_ticks.items()):
                for i,n in enumerate(sorted(packet,key=lambda n:(n['note'],n['id']))):
                    allocation[i//2][tick].append(n)
            for lane_index, group in enumerate(allocation):
                last = max(group)
                central = family in FOREGROUND or family==focus
                low = family in LOW_ROLES
                desired_x = 37+turn*(5+2*spread) if central else 37 + (-1 if (fi+index)%2 else 1)*(12+4*spread)
                desired_y = (115 if central else 98 if low else 116) + 3*terrace
                if preferred and family in preferred:
                    desired_x,desired_y = preferred[family]
                if family in anchors:
                    desired_x,desired_y = anchors[family]
                prev = previous_pos.get((family,lane_index))
                # Rails start at phrase+11, and stop just after their last tap.
                # Include extra z clearance before reusing a lane in a later phrase.
                def safe(p):
                    x,y = p
                    if abs(x-camera['x'])<6 and abs(y-camera['eyeY'])<5:
                        return False
                    if 26<=x<=48 and 106<=y<=114 and a+11<=69:
                        return False
                    return not any(abs(x-lx)<11 and abs(y-ly)<8 for lx,ly,_ in reserved)
                choices = [tuple(anchors[family])] if family in anchors and lane_index==0 else points
                free = [p for p in choices if safe(p)]
                if not free:
                    raise ValueError(f'Phrase {index+1}: no isolated lane for {family}/{lane_index+1}; '
                                     'move its anchor, adjust an adjacent phrase, or revoice the dense passage')
                def cost(p):
                    x,y=p
                    return (abs(x-desired_x)+1.3*abs(y-desired_y)
                            +(.22*(abs(x-prev[0])+abs(y-prev[1])) if prev else 0),p)
                x,y = min(free,key=cost)
                reserved.append((x,y,87+last))
                previous_pos[family,lane_index] = x,y
                lane = {'family':family,'row':lane_index,'x':x,'y':y,'launchGT':a,
                        'lastGT':last,'events':sum(map(len,group.values()))}
                row['lanes'].append(lane)
                assigned.append((lane,group))
        output.append(row)
    report = {'schemaVersion':1,'mode':'score-banks','sourceMidiSha256':events.get('sourceMidiSha256'),
              'musicGT':events['musicGT'],'sections':output,'clockBanks':sum(bool(x['lanes']) for x in output),
              'ticksPerSecond':20,'counterpart':'physical repeaters with independently pulsed phrase heads',
              'artisticApproval':False}
    return report, assigned


def create_track_plan(events_path,out,design_path=None):
    from pathlib import Path

    events = read_json(events_path)
    cfg = read_json(design_path) if design_path else None
    layout = read_json(Path(__file__).parent/'assets/layout.json')
    report,_ = design_track(events,{x['id'] for x in layout},cfg)
    folder = Path(out).resolve()
    folder.mkdir(parents=True,exist_ok=False)
    atomic_json(folder/'track-plan.json',report)
    return {**report,'path':str(folder/'track-plan.json')}
