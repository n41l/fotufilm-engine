#!/usr/bin/env python3
import unittest
from wavefront_region_analysis import analyze


class CoverageTests(unittest.TestCase):
    def test_union_overlapping_out_of_order_regions_and_halo(self):
        result = analyze(['PRODUCE f 0 8 2 5 0 3', 'PRODUCE f 0 8 -2 6 0 3',
                          'PRODUCE f 0 8 12 2 0 3'])['fields']['f']
        self.assertEqual(result['realized_rows'], 13)
        self.assertEqual(result['union_rows'], 11)
        self.assertEqual(result['union_elements'], 264)

    def test_empty_region_does_not_extend_coverage(self):
        result = analyze(['PRODUCE f 0 8 0 3 0 3', 'PRODUCE f 0 8 999 0 0 3'])['fields']['f']
        self.assertEqual(result['union_rows'], 3)
        self.assertEqual(result['positive_realizations'], 1)

    def test_variable_channel_or_x_domain_is_not_approximated(self):
        result = analyze(['PRODUCE f 0 8 0 3 0 3', 'PRODUCE f 1 8 3 3 0 3'])['fields']['f']
        self.assertNotIn('extra_realization_ratio', result)

    def test_nd_tables_record_count_and_domain(self):
        result = analyze(['PRODUCE_ND t 2 -1 3', 'PRODUCE_ND t 2 -1 3',
                          'PRODUCE_ND c 4 0 2048 0 3'])['other_realizations']
        self.assertEqual(result['t']['realizations'], 2)
        self.assertEqual(result['c']['regions'], [(0,2048,0,3)])

    def test_realization_does_not_imply_gpu_kernel_execution(self):
        result = analyze(['PRODUCE horizontal 0 8 0 3 0 3',
                          'GPU_KERNEL 1 1 fused_vertical'])
        self.assertIn('horizontal',result['fields'])
        self.assertEqual(result['gpu_kernel_bindings'],
                         [{'generation':1,'phase':1,'name':'fused_vertical'}])

    def test_invalid_extents_or_nd_dimensions_rejected(self):
        for line in ('PRODUCE f 0 8 0 -1 0 3', 'PRODUCE_ND f 2 0 -1',
                     'PRODUCE_ND f 3 0 2 0', 'PRODUCE_ND f 4 0 2'):
            with self.subTest(line=line), self.assertRaises(ValueError):
                analyze([line])


if __name__ == '__main__':
    unittest.main()
