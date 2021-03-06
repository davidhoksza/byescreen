#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This script aggregates results of multiple model analyzes. This can be useful when having multiple splits
of train and test data and want to compare the models coming from different train splits, or when evaluating
multiple models of the same target based on different sets of known active and inactive compounds.

The script takes a directory on its input, finds all models (*.am). From the files, the top N (parameter of the script)
features with highest likelihood ratios are taken. The output reports in how many models given feature value was found
among the top N most important features. Since Bayescreen does binning, we track ranges of values not the
values themselves. However, in each model the ranges can differ slightly due to different min-max normalization.
Two ranges are thus deemed identical if they intersect. Each feature value/range is formatted as follows:

    feature_name(range_of_values): average_likelihood

"""

import argparse
import common

__author__ = "David Hoksza"
__email__ = "david.hoksza@mff.cuni.cz"
__license__ = 'X11'

model_suffix = "am"

def get_overlap(a, b):
    """
    Finds out whether two intervals intersect.

    :param a: Two-element array representing an interval
    :param b: Two-element array representing an interval
    :return: True if the intervals intersect, false otherwise
    """
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def read_model(fm):
    """
    Reads in model in the format generated by the analyze_model script.

    :param fm: Filename with the model
    :return: Dictionary with the model analyzed
    """
    features = []
    in_section = False
    for line in fm:
        if "Features values importance" in line: in_section = True
        if in_section:
            s_line = line.split(",")
            if len(s_line) == 4:
                features.append({
                    "name": s_line[1],
                    "ratio": common.to_float(s_line[0]),
                    "interval": [common.to_float(x) for x in s_line[3].strip(" \n").strip("()").split(";")],
                    "cnt": 1
                })
                if len(features) >= args.n: break;
    return features


def merge_features(features, aux_features):
    """
    For two list of features values and for each value finds out whether it intersect with any feature value
    in the second list.
    :param features: Feature values dict (feature_name, interval, likelihood_ratio, number_of_intersected)
    :param aux_features: Feature values dict (feature_name, interval, likelihood_ratio, number_of_intersected)
    :return: Merged feature values dict (feature_name, interval, likelihood_ratio, number_of_intersected)
    """
    for val1 in aux_features:
        intersected = False
        for ix2 in range(len(features)):
            val2 = features[ix2]
            if val1["name"] == val2["name"] and bool(get_overlap(val1["interval"], val2["interval"])):
                features[ix2]["interval"] = [min(val1["interval"][0], val2["interval"][0]),
                                             max(val1["interval"][1], val2["interval"][1])]
                features[ix2]["ratio"] += val1["ratio"]
                features[ix2]["cnt"] += 1
                intersected = True
        if not intersected:
            features.append(val1)

    return features


def analyze_models(dir):
    """
    Takes all model analyzes in a dictionary and merges their top N feature values.
    :param dir: Direcotry to scan
    :return:
    """
    features = []
    for model in common.find_files_recursively(dir, "*.{}".format(model_suffix)):
        with common.open_file(model) as fm:
            aux_features = read_model(fm)
            features = merge_features(features, aux_features)

    features_factors = {}
    for val in features:
        if val["cnt"] not in features_factors:
            features_factors[val["cnt"]] = [val]
        else:
            features_factors[val["cnt"]].append(val)

    compressed = ""
    for key in sorted(features_factors, reverse=True):
        print(key)
        for val in sorted(features_factors[key], key=lambda x: x["ratio"], reverse=True):
            print("{}({};{}): {}".format(val["name"], val["interval"][0], val["interval"][1], val["ratio"]/val["cnt"]))
            compressed = "{}, {}-{} ({} - {:.2f})".format(compressed, val["name"], round(val["interval"][1] - val["interval"][0],1), key, val["ratio"]/val["cnt"])
        print("")

    print("Compressed:")
    print(compressed.strip(", "))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--directory",
                        required=True,
                        help="Directory with the analyzed models (.{} suffix).".format(model_suffix))
    parser.add_argument("-n",
                        type=int,
                        default=20,
                        help="Top n features to be considered in each model")

    args = parser.parse_args()

    analyze_models(args.directory)