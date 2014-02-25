#! /usr/bin/env python

#-----------------------------------------------------------------------------
# Copyright (c) 2013, The bipy Developers.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

from __future__ import absolute_import, division

import numpy as np
from scipy.stats import rankdata

from bipy.core.distance import SymmetricDistanceMatrix
from .base import CategoricalStatsResults


class PERMANOVA(object):
    short_method_name = 'PERMANOVA'
    long_method_name = 'Permutational Multivariate Analysis of Variance'

    def __init__(self, distance_matrix, grouping):
        if not isinstance(distance_matrix, SymmetricDistanceMatrix):
            raise TypeError("Input must be a SymmetricDistanceMatrix.")
        if len(grouping) != distance_matrix.num_samples:
            raise ValueError("Grouping vector size must match the number of "
                             "sample IDs in the distance matrix.")

        grouping = np.asarray(grouping)
        groups = np.unique(grouping)

        if len(groups) == len(grouping):
            raise ValueError("All values in the grouping vector are unique. "
                             "PERMANOVA cannot operate on a grouping vector with "
                             "only unique values (e.g., there are no 'within' "
                             "distances because each group of samples "
                             "contains only a single sample).")
        if len(groups) == 1:
            raise ValueError("All values in the grouping vector are the same. "
                             "PERMANOVA cannot operate on a grouping vector with "
                             "only a single group of samples (e.g., there are "
                             "no 'between' distances because there is only a "
                             "single group).")

        self._dm = distance_matrix
        self._divisor = self._dm.num_samples * ((self._dm.num_samples - 1) / 4)
        self._grouping = grouping
        self._groups = groups
        self._ranked_dists = rankdata(self._dm.condensed_form(),
                                      method='average')
        self._tri_idxs = np.triu_indices(self._dm.num_samples, k=1)

    def __call__(self, permutations=999):
        if permutations < 0:
            raise ValueError("Number of permutations must be greater than or "
                             "equal to zero.")

        f_stat = self._permanova(self._grouping)

        p_value = None
        if permutations > 0:
            perm_stats = np.empty(permutations, dtype=np.float64)

            for i in range(permutations):
                perm_grouping = np.random.permutation(self._grouping)
                perm_stats[i] = self._permanova(perm_grouping)

            p_value = ((perm_stats >= f_stat).sum() + 1) / (permutations + 1)

        return CategoricalStatsResults(self.short_method_name,
                                       self.long_method_name,
                                       self._dm.num_samples, self._groups,
                                       f_stat, p_value, permutations)

    def _permanova(self, grouping):
        """Compute PERMANOVA pseudo-F statistic."""
        samples = self._dm.sample_ids

        # Number of samples in each group.
        unique_n = []
        group_map = {}

        # Calculate number of groups and unique 'n's.
        # TODO: try SO post http://stackoverflow.com/a/21124789
        num_groups = len(self._groups)
        for i, i_string in enumerate(self._groups):
            group_map[i_string] = i
            unique_n.append(list(grouping).count(i_string))

        # Create grouping matrix.
        grouping_matrix = -1 * np.ones(self._dm.shape)
        for i, grouping_i in enumerate(grouping):
            for j, grouping_j in enumerate(grouping):
                if grouping_i == grouping_j:
                    grouping_matrix[i][j] = group_map[grouping_i]

        # Extract upper triangle.
        distances = self._dm.data[np.tri(self._dm.num_samples) == 0]
        groups = grouping_matrix[np.tri(len(grouping_matrix)) == 0]

        # Compute F value.
        return self._compute_f_stat(distances, groups, self._dm.num_samples,
                                    num_groups, unique_n)

    def _compute_f_stat(self, distances, groupings, num_samples, num_groups,
                        unique_n):
        """Performs the calculations for the F value.

        Arguments:
            distances - a list of the distances
            groupings - a list associating the distances to their groups
            num_samples - how many samples there are
            num_groups - how many groups there are
            unique_n - list containing how many samples are in each within
                group
        """
        a = num_groups
        N = num_samples

        # Calculate s_T.
        s_T = sum(distances * distances) / N

        # Calculate s_W for each group, this accounts for different group
        # sizes.
        s_W = 0
        for i in range(num_groups):
            group_ix = groupings == i
            diffs = distances[group_ix]
            s_W = s_W + sum(diffs ** 2) / unique_n[i]

        # Execute the formula.
        s_A = s_T - s_W
        return (s_A / (a - 1)) / (s_W / (N - a))
