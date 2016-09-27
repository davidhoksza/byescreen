#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Analyzes Bayes activity model.

"""

import argparse
import logging

import numpy as np
import csv
import json
import math
from rdkit import Chem
import common

__author__ = "David Hoksza"
__email__ = "david.hoksza@mff.cuni.cz"
__license__ = 'X11'


def score_feature_vector(feature_vector, probs, cnt_bins):
    ix = 0
    score = 0
    for feature_value in feature_vector:
        fv = int(math.floor(feature_value * cnt_bins))  # feature values are scaled to [0,1]
        if fv == cnt_bins: fv -= 1  # feature_value 1 will map to the last bin
        score += math.log(
            (probs["feature_value_in_actives"][ix][fv]) / probs["feature_value_in_inactives"][ix][fv])
        ix += 1
    score += math.log(probs["active"]/probs["inactive"])
    return score


def screen(fn_ds_json, model, fragments_features):
    with common.open_file(fn_ds_json) as f:
        mols = json.load(f)
        for mol in mols:
            fragments_scores = []
            processed_frags = []
            for frag in mol["fragments"]:
                if frag["smiles"] not in processed_frags:
                    processed_frags.append(frag["smiles"])
                    fragments_scores.append(score_feature_vector(fragments_features[frag["smiles"]], model["probabilities"], model["cnt_bins"]))

            if len(fragments_scores) > 0:
                # mol["score"] = np.nanmean(fragments_scores) #not available for np < 1.7
                mol["score"] = np.mean([x for x in fragments_scores if x is not np.nan and x is not None])

    result = [{"molecule": mol["name"], "score": mol["score"]} for mol in mols if "score" in mol.keys()]
    # return sorted(result, key=lambda x: x["score"], reverse=True)
    return result


def get_normalized_features(fn_ds_csv, model):
    feature_names = model["features_names"]
    ixs_uncorr_features = []
    features = []

    fragments = []
    for row in csv.reader(common.open_file(fn_ds_csv)):
        if not row: continue
        if len(ixs_uncorr_features) == 0:
            for ix in range(len(row)):
                if row[ix] in feature_names:
                    features.append([])
                    ixs_uncorr_features.append(ix)
        else:
            fragments.append(row[0])
            for ix in range(len(ixs_uncorr_features)) :
                features[ix].append(row[ixs_uncorr_features[ix]])

    # Convert strings to numbers
    features = [[common.to_float(y) for y in x] for x in features]

    # Imputation
    for ix in range(len(features)):
        features[ix] = [model["normalization"]["imputation_values"][ix] if math.isnan(x) else x for x in features[ix]]

    # Normalization
    # Some values in test set can be out of the min-max range of train set, therefore we set
    # such values to the max/mins
    feature_matrix = np.array(features)
    for ix in range(len(model["normalization"]["mins"])):
        feature_matrix[ix] = feature_matrix[ix].clip(model["normalization"]["mins"][ix], model["normalization"]["maxs"][ix])
        for ix1 in range(len(feature_matrix[ix])):
            if feature_matrix[ix][ix1] < model["normalization"]["mins"][ix] or feature_matrix[ix][ix1] > model["normalization"]["maxs"][ix]:
                print(ix, ix1)
    feature_matrix = feature_matrix.transpose()
    feature_matrix = (feature_matrix - np.array(model["normalization"]["mins"])) / \
                     (np.array(model["normalization"]["maxs"]) - np.array(model["normalization"]["mins"]))
    fragments_features = {}
    for ix in range(len(fragments)):
        fragments_features[fragments[ix]] = feature_matrix[ix]

    # with open("normalized.features.screen.csv", "w") as f:
    #     line = "Name"
    #     for name in model["features_names"]: line += ",{}".format(name)
    #     f.write(line + "\n")
    #     for ix in range(len(fragments)):
    #         line = fragments[ix]
    #         for feature in feature_matrix[ix]: line += ",{}".format(feature)
    #         f.write(line + "\n")

    return fragments_features


def main():
    common.init_logging()

    with common.open_file(args.model) as f:
        model = json.load(f)

        [fn_ds_json] = common.fragments_extraction([args.dataset], model["fragment_types"])
        [fn_ds_csv] = common.descriptors_extraction([fn_ds_json], model["features_generator"], model["path_to_padel"])
        fragments_features = get_normalized_features(fn_ds_csv, model)

        results = screen(fn_ds_json, model, fragments_features)
        with common.open_file(args.output, "w") as f:
            for r in results:
                f.write("{}: {}\n".format(r["molecule"], r["score"]))

        if args.clean:
            common.delete_files([fn_ds_json, fn_ds_csv])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument("-m", "--model",
                        required=True,
                        help="Output JSON file containing the resulting model.")
    parser.add_argument("-d", "--dataset",
                        required=True,
                        help="Molecules in SDF or SMILES format to rank.")
    parser.add_argument("-o", "--output",
                        required=True,
                        help="Output file for resulting ranking.")
    parser.add_argument("-c", "--clean",
                        action='store_true',
                        help="Delete the fragment and features files.")
    args = parser.parse_args()

    main()