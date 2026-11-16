"""Offline realization coverage. Counts are not GPU work or execution time."""
from collections import defaultdict


def analyze(lines):
    fields = defaultdict(list)
    tables = defaultdict(list)
    kernels = []
    for line in lines:
        p = line.split()
        if len(p) == 4 and p[0] == 'GPU_KERNEL':
            kernels.append({'generation': int(p[1]), 'phase': int(p[2]), 'name': p[3]})
        elif len(p) == 8 and p[0] == 'PRODUCE':
            fields[p[1]].append(tuple(map(int, p[2:])))
        elif len(p) >= 3 and p[0] == 'PRODUCE_ND':
            dimensions = int(p[2])
            if dimensions < 0 or dimensions % 2 or len(p) != 3 + dimensions:
                raise ValueError('invalid ND realization')
            coordinates = tuple(map(int, p[3:]))
            if any(n < 0 for n in coordinates[1::2]):
                raise ValueError('negative realization extent')
            tables[p[1]].append(coordinates)
    result = {}
    for name, regions in fields.items():
        if any(min(w, h, n) < 0 for _, w, _, h, _, n in regions):
            raise ValueError('negative realization extent')
        positive = [r for r in regions if r[1] and r[3] and r[5]]
        shapes = {(x, w, c, n) for x, w, _, _, c, n in positive}
        row = {'realizations': len(regions), 'positive_realizations': len(positive),
               'regions': regions, 'realized_elements': sum(w*h*n for _, w, _, h, _, n in regions)}
        if len(shapes) == 1:
            end = None
            union = 0
            for lo, hi in sorted((y, y+h) for _, _, y, h, _, _ in positive):
                union += max(0, hi - max(lo, end if end is not None else lo))
                end = max(hi, end if end is not None else hi)
            _, w, _, n = next(iter(shapes))
            total = sum(r[3] for r in positive)
            row.update(realized_rows=total, union_rows=union, extra_realization_ratio=total/union-1,
                       union_elements=w*union*n, union_f32_bytes=w*union*n*4)
        else:
            row['coverage_unavailable_reason'] = 'empty or changing x/channel domain; no row-union estimate'
        result[name] = row
    return {'scope': __doc__, 'fields': result, 'gpu_kernel_bindings': kernels,
            'other_realizations': {name: {'realizations': len(values), 'regions': values}
                                   for name, values in tables.items()}}
