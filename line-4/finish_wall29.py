"""One-shot conservation of the image-generated three-part conflict mark."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    codec = load('png29', 'finish_wall22.py')
    preview = load('jpeg29', 'preview_jpeg27.py')
    ancestor = Path('artifacts/line-4/wall.png')
    output = Path('artifacts/line-4/wall-v11.png')
    assert ancestor.read_bytes() == Path('artifacts/line-4/wall-v10.png').read_bytes()
    assert not Path('dist/line-4/29.json').exists()
    oldhash = hashlib.sha256(ancestor.read_bytes()).hexdigest()
    width, height, original = codec.read_png(ancestor)
    dw, dh, draft = codec.read_png(output)
    assert (width, height) == (dw, dh) == (1254, 1254)
    final = original[:]
    circles = [(1122,862,15), (1086,915,16), (1154,916,16)]
    segments = [(1120,871,1092,905), (1097,916,1143,917), (1147,906,1126,873)]
    for y in range(840,940):
        for x in range(1065,1177):
            distance = min(math.hypot(x-cx,y-cy)-radius for cx,cy,radius in circles)
            for ax,ay,bx,by in segments:
                t = max(0,min(1,((x-ax)*(bx-ax)+(y-ay)*(by-ay))/((bx-ax)**2+(by-ay)**2)))
                distance = min(distance, math.hypot(x-ax-t*(bx-ax),y-ay-t*(by-ay))-7)
            alpha = max(0,min(1,-distance/3))
            if alpha:
                at = (y*width+x)*3
                for c in range(3):
                    final[at+c] = round(original[at+c]*(1-alpha)+draft[at+c]*alpha)
    changed = [i for i in range(width*height) if final[i*3:i*3+3] != original[i*3:i*3+3]]
    assert changed and all(1065 <= i%width < 1177 and 840 <= i//width < 940 for i in changed)
    sha = codec.write_png(output,width,height,final)
    assert codec.read_png(output)[2] == final
    jpeg = preview.encode(preview.resize(final,width,height),512,512,quality=40)
    assert len(jpeg) < 100000
    Path('dist/line-4/29.jpg').write_bytes(jpeg)
    ancestor.write_bytes(output.read_bytes())
    evidence = {'ancestor_sha256':oldhash,'wall_sha256':sha,'dimensions':[width,height],
                'format':'PNG','mode':'RGB','changed_pixels':len(changed),
                'changed_pixels_outside_mark_region':0,'mark_region_xyxy':[1065,840,1177,940],
                'method':'Only image-generated pigment within feathered stone-and-line masks was retained; all other pixels equal the ancestor.',
                'preview':{'path':'dist/line-4/29.jpg','format':'JPEG','dimensions':[512,512],'bytes':len(jpeg)},
                'unmet_visual_requirements':[]}
    Path('line-4/IMAGE-29.json').write_text(json.dumps(evidence,indent=2)+'\n')
    record = {'name':'Each Stone Matters','image':'https://api.imd.fun/artifacts/'+sha,
              'attributes':[{'trait_type':'Cave','value':'Crystal'}, {'trait_type':'Wall','value':'Line 4'},
                            {'trait_type':'Number','value':29}, {'trait_type':'Left behind','value':'Core Audit'},
                            {'trait_type':'Meaning','value':'Three ochre stones joined in charcoal show a conflict whose every part matters.'},
                            {'trait_type':'One thing','value':'Finite offline dependency resolution'}]}
    Path('dist/line-4/29.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(evidence,indent=2))


if __name__ == '__main__':
    main()
