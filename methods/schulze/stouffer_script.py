import os

import click as click
import pandas as pd
import numpy as np
from scipy.stats import combine_pvalues, uniform
import statsmodels.sandbox.stats.multicomp as multicomp


DEFAULT_METHODS = ['oncodrivefml', 'oncodriveclust', 'oncodriveomega', 'hotmapssignature', 'mutsigcv']


def parse_optimized_weights(path_weights):
    cap = lambda a: a[:-2]
    df = pd.read_csv(path_weights, sep='\t', compression="gzip")
    del df['Objective_Function']
    dict_weight = df.to_dict()
    return {cap(k): v[0] for k, v in dict_weight.items()}


def retrieve_ranking(df, path_ranking):
    """
    df: dataframe with p-values per method
    tumor_type: str
    """

    ranking_dict = pd.read_csv(path_ranking,
                       sep='\t',
                       usecols=['SYMBOL', 'RANKING', 'Median_Ranking', 'Total_Bidders', 'All_Bidders'],
                       low_memory=False,
                               compression="gzip"
                       )
    cols = ['SYMBOL']
    return pd.merge(left=df, right=ranking_dict, left_on=cols, right_on=cols, how="left")


def stouffer_w(pvals, weights=None):

    return combine_pvalues(pvals, method='stouffer', weights=weights)[1]


def impute(pvals):
    """
    impute array-like instance with uniform [0,1] distribution
    """

    mask1 = np.isnan(pvals)
    mask2 = (pvals == 1)
    mask = mask1 | mask2
    pvals[mask] = uniform.rvs(size=len(pvals[mask]))
    return pvals


def combine_pvals(df, path_weights):

    weight_dict = parse_optimized_weights(path_weights)
    weights = np.array([weight_dict[m] for m in DEFAULT_METHODS])
    func = lambda x: stouffer_w(impute(x), weights=weights)
    df['PVALUE_' + 'stouffer_w'] = df[['PVALUE_' + m for m in DEFAULT_METHODS]].apply(func, axis=1)
    df['QVALUE_' + 'stouffer_w'] = multicomp.multipletests(df['PVALUE_' + 'stouffer_w'].values, method='fdr_bh')[1]
    return df


def partial_correction(df, fml_data):

    dh = pd.merge(left=df, right=fml_data[['SYMBOL', 'Q_VALUE']], left_on=['SYMBOL'], right_on=['SYMBOL'], how="left")
    c = dh['Q_VALUE'].values
    mask = ~np.isnan(c)
    a = dh['PVALUE_' + 'stouffer_w'].values
    c[mask] = multicomp.multipletests(a[mask], method='fdr_bh')[1]
    dh['QVALUE_' + 'stouffer_w'] = c
    del dh['Q_VALUE']
    return dh


def combine_from_tumor(df, path_to_output, path_fml):
    fml_data = pd.read_csv(path_fml, sep='\t', compression="gzip")
    dh = partial_correction(df, fml_data)
    dh.to_csv(path_to_output, sep='\t', index=False, compression="gzip")


@click.command()
@click.option('--input_path', type=click.Path(exists=True), help="Path to input dataframe with SYMBOL and p-value for each method", required=True)
@click.option('--output_path', type=click.Path(), help="Path to output dataframe", required=True)
@click.option('--path_rankings', type=click.Path(), help="Path to dataframe produced by the voting system", required=True)
@click.option('--path_weights', type=click.Path(), help="Path to dataframe with weights", required=True)
@click.option('--path_fml', type=click.Path(), help="Path to OncodriveFML results folder", required=True)
def run_stouffer_script(input_path, output_path, path_rankings, path_weights, path_fml):

    df = pd.read_csv(input_path, sep='\t', compression="gzip")
    dg = retrieve_ranking(df, path_rankings)
    dh = combine_pvals(dg, path_weights)
    combine_from_tumor(dh, output_path, path_fml)


if __name__ == '__main__':
    run_stouffer_script()
