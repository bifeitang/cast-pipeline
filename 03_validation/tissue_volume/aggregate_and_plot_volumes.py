#!/usr/bin/env python3
"""
Aggregate tissue volume results and generate publication-quality plots.

This script:
1. Collects all per-subject CSV files from tissue_volume_results/per_subject/
2. Merges into a single summary table
3. Generates a 4-panel figure (ICV, WM, GM, CSF vs Age) with:
   - Scatter points: male (black), female (gray)
   - LOWESS trend lines per sex

Usage:
    python aggregate_and_plot_volumes.py [--input-dir DIR] [--output-dir DIR]

Dependencies: pandas, numpy, matplotlib, scipy (for LOWESS) or statsmodels
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path
from typing import Optional

import warnings
warnings.filterwarnings('ignore')


def check_dependencies():
    """Check and import required dependencies."""
    try:
        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Please install: pip install pandas numpy matplotlib")
        return False


def aggregate_csv_files(input_dir: str) -> "pd.DataFrame":
    """Aggregate all per-subject CSV files into a single DataFrame."""
    import pandas as pd
    
    csv_pattern = os.path.join(input_dir, "Age*_*_*.csv")
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found matching pattern: {csv_pattern}")
    
    print(f"Found {len(csv_files)} CSV files to aggregate")
    
    dfs = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            dfs.append(df)
        except Exception as e:
            print(f"  Warning: Failed to read {csv_file}: {e}")
    
    if not dfs:
        raise ValueError("No valid CSV files could be read")
    
    combined = pd.concat(dfs, ignore_index=True)
    
    # Ensure numeric columns
    numeric_cols = ['age', 'wm_mm3', 'gm_mm3', 'csf_mm3', 'icv_mm3', 
                    'wm_ml', 'gm_ml', 'csf_ml', 'icv_ml',
                    'brainmask_mm3', 'brainmask_ml', 'etiv_mm3', 'etiv_ml']
    for col in numeric_cols:
        if col in combined.columns:
            combined[col] = pd.to_numeric(combined[col], errors='coerce')
    
    # Sort by age and sex
    combined = combined.sort_values(['age', 'sex', 'subject_id']).reset_index(drop=True)
    
    return combined


def lowess_smooth(x, y, frac: float = 0.3):
    """
    Apply LOWESS smoothing. Falls back to polynomial if statsmodels unavailable.
    """
    import numpy as np
    
    # Remove NaN values
    mask = ~(np.isnan(x) | np.isnan(y))
    x_clean = x[mask]
    y_clean = y[mask]
    
    if len(x_clean) < 3:
        return x_clean, y_clean
    
    # Sort by x
    sort_idx = np.argsort(x_clean)
    x_sorted = x_clean[sort_idx]
    y_sorted = y_clean[sort_idx]
    
    try:
        from statsmodels.nonparametric.smoothers_lowess import lowess
        smoothed = lowess(y_sorted, x_sorted, frac=frac, return_sorted=True)
        return smoothed[:, 0], smoothed[:, 1]
    except ImportError:
        # Fallback to polynomial fit
        try:
            coeffs = np.polyfit(x_sorted, y_sorted, deg=3)
            y_smooth = np.polyval(coeffs, x_sorted)
            return x_sorted, y_smooth
        except:
            return x_sorted, y_sorted


def create_volume_plots(df: "pd.DataFrame", output_path: str, 
                        lowess_frac: float = 0.4):
    """
    Create a 4-panel figure showing ICV, WM, GM, CSF vs Age.
    
    Style mimics the reference image (CCNP/eNKI style) with:
    - Scatter points: male (black squares), female (gray circles)
    - Trend lines: thick solid lines for each sex
    - Legend in each panel showing Male/Female
    """
    import numpy as np
    import matplotlib.pyplot as plt
    
    # Configure plot style to match reference image
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.size': 10,
        'axes.labelsize': 12,
        'axes.titlesize': 12,
        'axes.linewidth': 1.0,
        'legend.fontsize': 9,
        'legend.frameon': True,
        'legend.edgecolor': 'black',
        'legend.fancybox': False,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'xtick.direction': 'out',
        'ytick.direction': 'out',
        'xtick.major.width': 1.0,
        'ytick.major.width': 1.0,
    })
    
    # Create figure with 4 subplots (matching reference layout)
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.2))
    
    # Volume metrics to plot (same order as reference: ICV, WM, GM, CSF)
    metrics = [
        ('icv_ml', 'ICV (mL)'),
        ('wm_ml', 'WM (mL)'),
        ('gm_ml', 'GM (mL)'),
        ('csf_ml', 'Ventricular / Core CSF (mL)'),
    ]
    
    # Colors and markers - distinct colors like reference (orange/purple style)
    male_color = '#FF8C00'    # Dark orange for male
    female_color = '#8B008B'  # Dark magenta/purple for female
    male_marker = 'o'  # circle (filled)
    female_marker = 'o'  # circle (filled)
    marker_size = 15
    alpha = 0.5  # transparency for scatter points
    line_width = 3.0  # thick trend lines like in reference
    
    for ax, (metric, ylabel) in zip(axes, metrics):
        # Separate by sex
        male_data = df[df['sex'] == 'male'].dropna(subset=['age', metric])
        female_data = df[df['sex'] == 'female'].dropna(subset=['age', metric])
        
        # Scatter plots with distinct colors
        if len(male_data) > 0:
            ax.scatter(male_data['age'], male_data[metric], 
                      c=male_color, marker=male_marker, s=marker_size, 
                      alpha=alpha, label='Male', edgecolors='none', zorder=2)
        
        if len(female_data) > 0:
            ax.scatter(female_data['age'], female_data[metric], 
                      c=female_color, marker=female_marker, s=marker_size, 
                      alpha=alpha, label='Female', edgecolors='none', zorder=2)
        
        # LOWESS trend lines - thick solid lines with matching colors
        if len(male_data) >= 5:
            x_smooth, y_smooth = lowess_smooth(
                male_data['age'].values, 
                male_data[metric].values,
                frac=lowess_frac
            )
            ax.plot(x_smooth, y_smooth, color=male_color, linewidth=line_width, 
                   linestyle='-', zorder=3)
        
        if len(female_data) >= 5:
            x_smooth, y_smooth = lowess_smooth(
                female_data['age'].values, 
                female_data[metric].values,
                frac=lowess_frac
            )
            ax.plot(x_smooth, y_smooth, color=female_color, linewidth=line_width, 
                   linestyle='-', zorder=3)
        
        # Formatting
        ax.set_xlabel('Age (year)')
        ax.set_ylabel(ylabel)
        ax.set_xlim(4, 19)
        
        # Set y-axis limits based on actual data range with 5% padding
        # This ensures the variation is visible
        all_values = df[metric].dropna()
        y_data_min = all_values.min()
        y_data_max = all_values.max()
        y_range = y_data_max - y_data_min
        padding = y_range * 0.05  # 5% padding on each side
        ax.set_ylim(y_data_min - padding, y_data_max + padding)
        
        # Light grid for readability
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        
        # Add legend - position based on metric trend
        # ICV and GM tend to decrease with age, put legend upper right
        # WM tends to increase, put legend upper left
        # CSF increases, put legend upper left
        if metric in ['icv_ml', 'gm_ml']:
            legend_loc = 'upper right'
        else:
            legend_loc = 'upper left'
        ax.legend(loc=legend_loc, framealpha=0.9, 
                 handletextpad=0.3, borderpad=0.3)
        
        # Clean up spines
        ax.spines['top'].set_visible(True)
        ax.spines['right'].set_visible(True)
    
    plt.tight_layout(pad=1.0)
    
    # Save figure
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"Saved plot to: {output_path}")


def create_summary_statistics(df: "pd.DataFrame") -> "pd.DataFrame":
    """Create summary statistics by age and sex."""
    import pandas as pd
    
    summary = df.groupby(['age', 'sex']).agg({
        'subject_id': 'count',
        'wm_ml': ['mean', 'std'],
        'gm_ml': ['mean', 'std'],
        'csf_ml': ['mean', 'std'],
        'icv_ml': ['mean', 'std'],
    }).round(3)
    
    # Flatten column names
    summary.columns = ['_'.join(col).strip() for col in summary.columns.values]
    summary = summary.rename(columns={'subject_id_count': 'n_subjects'})
    summary = summary.reset_index()
    
    return summary


def main():
    parser = argparse.ArgumentParser(
        description='Aggregate tissue volumes and generate plots'
    )
    parser.add_argument(
        '--input-dir',
        default=None,
        help='Input directory containing per-subject CSVs (default: auto-detect)'
    )
    parser.add_argument(
        '--output-dir',
        default=None,
        help='Output directory for summary files (default: auto-detect)'
    )
    parser.add_argument(
        '--lowess-frac',
        type=float,
        default=0.4,
        help='LOWESS smoothing fraction (default: 0.4)'
    )
    args = parser.parse_args()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    import pandas as pd
    
    # Determine paths
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent
    
    input_dir = args.input_dir or str(base_dir / 'tissue_volume_results' / 'per_subject')
    output_dir = args.output_dir or str(base_dir / 'tissue_volume_results' / 'summary')
    
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Aggregate CSV files
    print("\nAggregating CSV files...")
    df = aggregate_csv_files(input_dir)
    print(f"Total subjects: {len(df)}")
    print(f"Age range: {df['age'].min()} - {df['age'].max()}")
    print(f"Sex distribution: {df['sex'].value_counts().to_dict()}")
    
    # Save aggregated data
    all_csv_path = os.path.join(output_dir, 'tissue_volumes_all.csv')
    df.to_csv(all_csv_path, index=False)
    print(f"\nSaved aggregated data to: {all_csv_path}")
    
    # Create summary statistics
    print("\nGenerating summary statistics...")
    summary = create_summary_statistics(df)
    summary_path = os.path.join(output_dir, 'tissue_volumes_summary_by_age_sex.csv')
    summary.to_csv(summary_path, index=False)
    print(f"Saved summary to: {summary_path}")
    
    # Create plots
    print("\nGenerating plots...")
    plot_path = os.path.join(output_dir, 'tissue_volumes_plot.png')
    create_volume_plots(df, plot_path, lowess_frac=args.lowess_frac)
    
    # Also save as PDF for publication
    pdf_path = os.path.join(output_dir, 'tissue_volumes_plot.pdf')
    create_volume_plots(df, pdf_path, lowess_frac=args.lowess_frac)
    
    # Print summary table
    print("\n" + "=" * 70)
    print("Subject Count by Age and Sex")
    print("=" * 70)
    pivot = df.groupby(['age', 'sex']).size().unstack(fill_value=0)
    pivot['Total'] = pivot.sum(axis=1)
    print(pivot.to_string())
    print(f"\nTotal subjects: Male={len(df[df['sex']=='male'])}, Female={len(df[df['sex']=='female'])}, All={len(df)}")
    
    print("\n" + "=" * 70)
    print("Mean Volumes (mL) by Age and Sex")
    print("=" * 70)
    for sex in ['male', 'female']:
        sex_data = df[df['sex'] == sex]
        if len(sex_data) > 0:
            print(f"\n{sex.upper()}:")
            stats = sex_data.groupby('age')[['icv_ml', 'wm_ml', 'gm_ml', 'csf_ml']].agg(['mean', 'std']).round(1)
            # Flatten column names
            stats.columns = [f"{col[0]}_{col[1]}" for col in stats.columns]
            print(stats.to_string())
    
    print("\n" + "=" * 70)
    print("Output Files Generated:")
    print("=" * 70)
    print(f"  - {all_csv_path}")
    print(f"  - {summary_path}")
    print(f"  - {plot_path}")
    print(f"  - {pdf_path}")
    print("\nDone!")


if __name__ == '__main__':
    main()
