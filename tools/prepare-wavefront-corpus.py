#!/usr/bin/env python3
"""Color-managed SDR corpus preparation, outside engine timing (Pillow + macOS converter)."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import PIL
from PIL import Image, ImageCms, ImageOps


def srgb_profile():
    data = bytearray(ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
    # Normalize generated ICC timestamps and leave the optional profile ID unset.
    data[24:36] = struct.pack('>6H',2000,1,1,0,0,0)
    data[84:100] = bytes(16)
    return bytes(data)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--converter',required=True,type=Path)
    args=parser.parse_args()
    manifest=json.loads(Path(__file__).with_name('wavefront-corpus.json').read_text())
    canonical=args.output/'canonical'; native=args.output/'native'
    canonical.mkdir(parents=True,exist_ok=True);native.mkdir(parents=True,exist_ok=True)
    profile=srgb_profile();target=ImageCms.ImageCmsProfile(io.BytesIO(profile))
    records=[]
    for item in manifest['images']:
        source=args.sources/item['file']
        if sha(source)!=item['sha256']:raise ValueError('source changed')
        with Image.open(source) as original:
            embedded=original.info.get('icc_profile')
            pixels=ImageOps.exif_transpose(original)
            if embedded:
                pixels=ImageCms.profileToProfile(pixels,ImageCms.ImageCmsProfile(io.BytesIO(embedded)),
                                                target,outputMode='RGB')
            else:
                pixels=pixels.convert('RGB')
            name=Path(item['file']).stem
            path=canonical/f'{name}.png'
            pixels.save(path,format='PNG',icc_profile=profile,compress_level=6)
            width,height=pixels.size
        raw=native/f'{name}-{width}x{height}.rgba32f'
        subprocess.run([str(args.converter.resolve()),str(path.resolve()),str(width),str(height),str(raw.resolve())],check=True)
        records.append({'id':name,'split':item['split'],'source_sha256':item['sha256'],
                        'canonical':str(path.resolve()),'canonical_sha256':sha(path),
                        'native_width':width,'native_height':height,'native_linear_input':str(raw.resolve()),
                        'native_input_sha256':sha(raw),'profile_source':'embedded' if embedded else 'assumed sRGB',
                        'linear_input_space':'extended linear Rec.2020, opaque RGBA float32, top-left row order'})
    workloads=[]
    for width,height in ((1920,1080),(3840,2160)):
        path=args.output/f'coffee-{width}x{height}.rgba32f'
        subprocess.run([str(args.converter.resolve()),str((canonical/'coffee.png').resolve()),str(width),str(height),str(path.resolve())],check=True)
        workloads.append({'id':f'coffee-{width}x{height}','source':'coffee','width':width,'height':height,
                          'path':str(path.resolve()),'sha256':sha(path),'transform':'aspect-cover crop, high interpolation',
                          'upscaled':True,'scope':'performance workload; not native 1080p/4K quality evidence'})
    record={'pillow':PIL.__version__,'converter_sha256':sha(args.converter),
            'srgb_profile_sha256':hashlib.sha256(profile).hexdigest(),'images':records,'workloads':workloads}
    (args.output/'prepared.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__':main()
