"""
Script to create warp value analysis plots similar to the reference image.
Left panel: Scatter plot with LOWESS trend lines showing normalized warp value vs age difference.
Right panel: Violin plots comparing matching vs mismatching age groups.
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Try to import LOWESS for trend lines
try:
    from statsmodels.nonparametric.smoothers_lowess import lowess
    HAS_LOWESS = True
except ImportError:
    HAS_LOWESS = False
    print("Warning: statsmodels not available, using rolling mean for trend lines")

# Configuration
BASE_DIR = Path('/path/to/cast-project/DeformationAnalysis')
CSV_PATH = BASE_DIR / 'test_set_dc_metrics_merged.csv'
PLOTS_DIR = BASE_DIR / 'plots'
PLOTS_DIR.mkdir(exist_ok=True)

# Color palette - similar to reference image (swapped to match reference)
COLORS = {
    'female': '#4169E1',  # Royal Blue (like IPCAS in reference)
    'male': '#DC143C',    # Crimson Red (like NKI in reference)
}

def load_data():
    """Load and preprocess the data."""
    df = pd.read_csv(CSV_PATH)
    
    # Calculate age difference (subject_age - template_age)
    df['age_diff'] = df['subject_age'] - df['template_age']
    
    # Filter out extreme outliers (use IQR method or percentile cutoff)
    # Based on data inspection, most values are < 2, with few extreme outliers
    q99 = df['normalized_warp_value'].quantile(0.99)
    df = df[df['normalized_warp_value'] <= q99].copy()
    
    # Define matching vs mismatching based on age proximity
    # Matching: when |age_diff| <= 1 year
    df['match_status'] = df['age_diff'].abs().apply(
        lambda x: 'matching' if x <= 1 else 'mismatching'
    )
    
    return df

def compute_trend(x, y, frac=0.3):
    """Compute LOWESS or rolling mean trend line."""
    # Sort by x
    sort_idx = np.argsort(x)
    x_sorted = np.array(x)[sort_idx]
    y_sorted = np.array(y)[sort_idx]
    
    if HAS_LOWESS:
        smoothed = lowess(y_sorted, x_sorted, frac=frac, return_sorted=True)
        return smoothed[:, 0], smoothed[:, 1]
    else:
        # Fallback to rolling mean
        window = max(5, int(len(x) * 0.15))
        x_trend = pd.Series(x_sorted).rolling(window, min_periods=1, center=True).mean().values
        y_trend = pd.Series(y_sorted).rolling(window, min_periods=1, center=True).mean().values
        return x_trend, y_trend

def create_combined_plot(df, output_name='warp_value_analysis.png'):
    """Create the combined plot with scatter+trend and violin plots."""
    
    # Set up the figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [1.2, 1]})
    
    # --- Left Panel: Scatter plot with trend lines ---
    # Plot in order: male first (background), then female (foreground) to match reference
    for sex in ['male', 'female']:
        color = COLORS[sex]
        subset = df[df['template_sex'] == sex]
        
        # Scatter plot with transparency - smaller dots
        ax1.scatter(
            subset['age_diff'], 
            subset['normalized_warp_value'],
            c=color, alpha=0.45, s=12, label=sex.capitalize(), edgecolors='none'
        )
        
        # Add trend line
        if len(subset) > 10:
            x_trend, y_trend = compute_trend(
                subset['age_diff'].values, 
                subset['normalized_warp_value'].values,
                frac=0.4
            )
            ax1.plot(x_trend, y_trend, color=color, linewidth=4, alpha=1.0)
    
    ax1.set_xlabel('Age differences between individual and template brain (year)', fontsize=12)
    ax1.set_ylabel('Warp value (Normalized)', fontsize=12)
    ax1.legend(loc='upper right', frameon=True, fancybox=True, framealpha=0.9)
    
    # Set x-axis range based on data
    x_min = df['age_diff'].min() - 0.5
    x_max = df['age_diff'].max() + 0.5
    ax1.set_xlim(x_min, x_max)
    
    # Set y-axis with Min/Max labels
    y_min, y_max = df['normalized_warp_value'].min(), df['normalized_warp_value'].max()
    ax1.set_ylim(y_min - 0.02, y_max + 0.05)
    ax1.set_yticks([y_min, y_max])
    ax1.set_yticklabels(['Min', 'Max'])
    
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(False)
    
    # --- Right Panel: Violin plots ---
    # Prepare data for violin plot
    violin_data = []
    order = []
    
    for sex in ['female', 'male']:
        for status in ['matching', 'mismatching']:
            subset = df[(df['template_sex'] == sex) & (df['match_status'] == status)]
            label = f"{sex.capitalize()} {status}"
            order.append(label)
            for val in subset['normalized_warp_value']:
                violin_data.append({'Category': label, 'Warp value': val, 'Sex': sex})
    
    violin_df = pd.DataFrame(violin_data)
    
    # Plot violins with different transparency for matching/mismatching
    positions = [0, 1, 2.5, 3.5]  # Add gap between female and male
    widths = 0.7
    
    for i, (label, pos) in enumerate(zip(order, positions)):
        subset_vals = violin_df[violin_df['Category'] == label]['Warp value'].values
        sex = 'female' if 'Female' in label else 'male'
        is_matching = 'matching' in label and 'mismatching' not in label
        
        color = COLORS[sex]
        alpha = 0.8 if is_matching else 0.5
        
        # Create violin
        parts = ax2.violinplot([subset_vals], positions=[pos], widths=widths, showmeans=False, showmedians=False)
        
        # Color the violin
        for pc in parts['bodies']:
            pc.set_facecolor(color)
            pc.set_alpha(alpha)
            pc.set_edgecolor(color)
            pc.set_linewidth(1.5)
        
        # Style the lines
        for partname in ('cbars', 'cmins', 'cmaxs'):
            if partname in parts:
                parts[partname].set_color(color)
                parts[partname].set_linewidth(1.5)
        
        # Add mean marker (cross)
        mean_val = np.mean(subset_vals)
        ax2.plot([pos], [mean_val], marker='+', markersize=18, markeredgewidth=2.5, color='black')
    
    ax2.set_xticks(positions)
    ax2.set_xticklabels(['Female\nmatching', 'Female\nmismatching', 'Male\nmatching', 'Male\nmismatching'], fontsize=10)
    ax2.set_ylabel('Warp value (Normalized)', fontsize=12)
    
    # Set y-axis with Min/Max labels
    ax2.set_ylim(y_min - 0.02, y_max + 0.05)
    ax2.set_yticks([y_min, y_max])
    ax2.set_yticklabels(['Min', 'Max'])
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLORS['female'], alpha=0.8, label='Female'),
        Patch(facecolor=COLORS['male'], alpha=0.8, label='Male'),
    ]
    ax2.legend(handles=legend_elements, loc='upper right', frameon=True, fancybox=True)
    
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.grid(False)
    
    plt.tight_layout()
    
    # Save the figure
    output_path = PLOTS_DIR / output_name
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved plot to: {output_path}")
    
    plt.close(fig)
    return fig

def main():
    """Main function to run the analysis."""
    print("Loading data...")
    df = load_data()
    
    print(f"Total samples: {len(df)}")
    print(f"Template sexes: {df['template_sex'].unique()}")
    print(f"Age difference range: [{df['age_diff'].min():.1f}, {df['age_diff'].max():.1f}]")
    print(f"Matching samples: {(df['match_status'] == 'matching').sum()}")
    print(f"Mismatching samples: {(df['match_status'] == 'mismatching').sum()}")
    
    print("\nCreating plot...")
    create_combined_plot(df)
    
    print("Done!")

if __name__ == '__main__':
    main()
