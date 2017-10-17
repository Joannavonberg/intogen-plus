import os
import csv
import gzip
import logging
import numpy as np

from bgreference import hg19
from .base import Filter
from collections import Counter, defaultdict
from intervaltree import IntervalTree

logger = logging.getLogger(__name__)


class VariantsFilter(Filter):

    KEY = "variants"

    # Minimum cutoff
    MIN_CUTOFF = 1000
    CHROMOSOMES = set([str(c) for c in range(1, 23)] + ['X', 'Y'])

    def __init__(self, parent):
        super().__init__(parent)

    def hypermutators_cutoff(self, snp_per_sample):
        vals = list(snp_per_sample.values())
        iqr = np.subtract(*np.percentile(vals, [75, 25]))
        q3 = np.percentile(vals, 75)
        computed_cutoff = (q3 + 1.5 * iqr)
        cutoff = max(self.MIN_CUTOFF, computed_cutoff)
        return cutoff, computed_cutoff, set([k for k, v in snp_per_sample.items() if v > cutoff])

    def sample_stats(self, group_key, group_data):

        donors = {}
        mut_per_sample = {}
        snp_per_sample = {}
        indel_per_sample = {}

        for m in self.parent.run(group_key, group_data):
            s = m['SAMPLE']
            if m['ALT_TYPE'] == 'snp':
                snp_per_sample[s] = snp_per_sample.get(s, 0) + 1

            elif m['ALT_TYPE'] == 'indel':
                indel_per_sample[s] = indel_per_sample.get(s, 0) + 1

            mut_per_sample[s] = mut_per_sample.get(s, 0) + 1
            s = donors.get(m['DONOR'], set())
            s.add(m['SAMPLE'])
            donors[m['DONOR']] = s

        return indel_per_sample, mut_per_sample, snp_per_sample, donors

    def run(self, group_key, group_data):

        # To store errors and statistics
        self.stats[group_key] = {}

        # Compute sample and donor statistics
        indel_per_sample, mut_per_sample, snp_per_sample, donors = self.sample_stats(group_key, group_data)
        self.stats[group_key]['samples'] = {
            'count': len(mut_per_sample),
            'mut_per_sample': mut_per_sample,
            'snp_per_sample': snp_per_sample,
            'indel_per_sample': indel_per_sample
        }
        self.stats[group_key]['donors'] = {d: list(s) for d, s in donors.items()}

        if len(snp_per_sample) < 1:
            self.stats[group_key]['error_no_samples_with_snp'] = "Any sample has a SNP variant"
            return

        cutoff, theorical_cutoff, hypermutators = self.hypermutators_cutoff(snp_per_sample)
        self.stats[group_key]['hypermutators'] = {
            'cutoff': cutoff,
            'computed_cutoff': theorical_cutoff,
            'hypermutators': list(hypermutators)
        }

        # Load coverage regions tree
        regions_file = os.environ['COVERAGE_REGIONS']
        coverage_tree = defaultdict(IntervalTree)
        with gzip.open(regions_file, 'rt') as fd:
            reader = csv.reader(fd, delimiter='\t')
            for i, r in enumerate(reader, start=1):
                coverage_tree[r[0]][int(r[1]):(int(r[2]) + 1)] = i

        # Stats counter
        skip_hypermutators = 0
        skip_chromosome = 0
        skip_chromosome_names = set()
        skip_coverage = 0
        skip_coverage_positions = []

        count_before = 0
        count_after = 0
        count_snp = 0
        count_indel = 0
        count_mismatch = 0

        # Read variants

        signature = {}

        for v in self.parent.run(group_key, group_data):
            count_before += 1

            # Skip hypermutators
            if v['SAMPLE'] in hypermutators:
                skip_hypermutators += 1
                continue

            if v['CHROMOSOME'] not in self.CHROMOSOMES:
                skip_chromosome_names.add(v['CHROMOSOME'])
                skip_chromosome += 1
                continue

            if v['CHROMOSOME'] in coverage_tree:
                if len(coverage_tree[v['CHROMOSOME']][v['POSITION']]) == 0:
                    skip_coverage += 1
                    skip_coverage_positions.append((v['SAMPLE'], v['CHROMOSOME'], v['POSITION']))
                    continue

            count_after += 1
            if v['ALT_TYPE'] == 'snp':
                count_snp += 1

                # Compute signature and count mismatch
                ref = hg19(v['CHROMOSOME'], v['POSITION'] - 1, size=3).upper()
                alt = ''.join([ref[0], v['ALT'], ref[2]])
                if ref[1] != v['REF']:
                    count_mismatch += 1
                signature_key = "{}>{}".format(ref, alt)
                signature[signature_key] = signature.get(signature_key, 0) + 1

            elif v['ALT_TYPE'] == 'indel':
                count_indel += 1

            yield v

        self.stats[group_key]['signature'] = signature

        self.stats[group_key]['skip'] = {
            'hypermuptators': (skip_hypermutators, None),
            'invalid_chromosome': (skip_chromosome, list(skip_chromosome_names)),
            'coverage': (skip_coverage, skip_coverage_positions)
        }

        self.stats[group_key]['count'] = {
            'before': count_before,
            'after': count_after,
            'snp': count_snp,
            'indel': count_indel,
            'mismatch': count_mismatch
        }

        self.stats[group_key]['signature'] = signature

        ratio_mismatch = count_mismatch / count_snp
        if ratio_mismatch > 0.1:
            self.stats[group_key]["error_genome_reference_mismatch"] = "There are {} of {} genome reference mismatches. More than 10%, skipping this dataset.".format(count_mismatch, count_snp)
        elif ratio_mismatch > 0.05:
            self.stats[group_key]["warning_genome_reference_mismatch"] = "There are {} of {} genome reference mismatches.".format(count_mismatch, count_snp)

        if count_after == 0:
            self.stats[group_key]["error_no_entries"] = "There are no variants after filtering"