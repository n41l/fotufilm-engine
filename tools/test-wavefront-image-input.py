#!/usr/bin/env python3
"""Independent color/row-order invariants for corpus input preparation (macOS)."""
from array import array
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from PIL import Image

spec=importlib.util.spec_from_file_location('prepare',Path(__file__).with_name('prepare-wavefront-corpus.py'))
prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)


class InputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name);cls.converter=cls.root/'convert'
        subprocess.run(['xcrun','swiftc','-O',str(Path(__file__).with_name('wavefront-image-input.swift')),
                        '-o',str(cls.converter)],check=True)

    def convert(self,image,width,height):
        source=self.root/'input.png';output=self.root/'output.rgba32f'
        image.save(source,icc_profile=prepare.srgb_profile())
        subprocess.run([str(self.converter),str(source),str(width),str(height),str(output)],
                       check=True,capture_output=True)
        self.assertEqual(output.stat().st_size,width*height*16)
        values=array('f');values.frombytes(output.read_bytes());return values

    def test_native_primaries_gray_and_top_left_row_order(self):
        image=Image.new('RGB',(2,2));image.putdata([(255,0,0),(0,255,0),(0,0,255),(128,128,128)])
        values=self.convert(image,2,2)
        expected=[.6274,.0691,.0164,1,.3293,.9195,.0880,1,.0433,.0114,.8956,1,.21586,.21586,.21586,1]
        self.assertLess(max(abs(a-b) for a,b in zip(values,expected)),.001)
        self.assertTrue(all(values[i]==1 for i in (3,7,11,15)))

    def test_neutral_survives_cover_crop_and_resize(self):
        values=self.convert(Image.new('RGB',(17,11),(128,128,128)),65,129)
        for i in range(0,len(values),4):
            for c in range(3):self.assertAlmostEqual(values[i+c],.21586,delta=.001)
            self.assertEqual(values[i+3],1)

    def test_profile_bytes_are_reproducible(self):
        self.assertEqual(prepare.srgb_profile(),prepare.srgb_profile())

    def test_invalid_dimensions_are_an_error_without_crashing(self):
        result=subprocess.run([str(self.converter),'unused.png','0','2',str(self.root/'bad')],capture_output=True)
        self.assertEqual(result.returncode,2)
        self.assertFalse((self.root/'bad').exists())


if __name__=='__main__':unittest.main()
