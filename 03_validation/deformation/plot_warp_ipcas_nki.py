"""
Script to create warp value analysis plots comparing IPCAS vs NKI templates.
Merges subject age info from hbn_subject_info_all.txt with metrics data.
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re
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
METRICS_PATH = BASE_DIR / 'test_set_on_template_metrics_all.csv'
SUBJECT_INFO_PATH = BASE_DIR / 'hbn_subject_info_all.txt'
PLOTS_DIR = BASE_DIR / 'plots'
PLOTS_DIR.mkdir(exist_ok=True)

# Color palette - matching reference image
COLORS = {
    'My Template': '#0066CC',  # Blue
    'Reference Template': '#CC3333',    # Red
}

# Display names mapping
DATASET_NAMES = {
    'IPCAS': 'My Template',
    'NKI': 'Reference Template',
}

def extract_template_age(template_name):
    """Extract age from template name."""
    # Match patterns like 'NKI_age10_brain_template' or 'age10_female_template'
    match = re.search(r'age(\d+)', template_name)
    if match:
        return int(match.group(1))
    return None

def identify_dataset(template_name):
    """Identify dataset from template name."""
    if template_name.startswith('NKI_'):
        return 'NKI'
    else:
        return 'IPCAS'

def load_and_merge_data():
    """Load and merge metrics with subject info."""
    # Load metrics
    metrics_df = pd.read_csv(METRICS_PATH)
    
    # Load subject info
    subject_df = pd.read_csv(SUBJECT_INFO_PATH)
    subject_df = subject_df.rename(columns={'EID': 'subject_id'})
    
    # Merge on subject_id
    merged = metrics_df.merge(subject_df[['subject_id', 'Age', 'Sex_Text']], 
                               on='subject_id', how='left')
    
    # Extract template age from template name
    merged['template_age'] = merged['template'].apply(extract_template_age)
    
    # Use the age_dir as template age if extraction failed
    merged['template_age'] = merged['template_age'].fillna(merged['age_dir'])
    
    # Identify dataset
    merged['dataset'] = merged['template'].apply(identify_dataset)
    
    # Calculate age difference (subject_age - template_age)
    merged['age_diff'] = merged['Age'] - merged['template_age']
    
    # Drop rows without age info
    merged = merged.dropna(subset=['Age', 'age_diff'])
    
    # Filter outliers in normalized_warp_value
    q99 = merged['normalized_warp_value'].quantile(0.99)
    merged = merged[merged['normalized_warp_value'] <= q99].copy()
    
    # Define matching vs mismatching based on age proximity
    # Matching: when |age_diff| <= 1 year
    merged['match_status'] = merged['age_diff'].abs().apply(
        lambda x: 'matching' if x <= 1 else 'mismatching'
    )
    
    return merged

def compute_trend(x, y, frac=0.4):
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

def create_combined_plot(df, output_name='warp_value_ipcas_nki.png'):
    """Create the combined plot with scatter+trend and violin plots, with sex differentiation."""
    
    # Map dataset names to display names
    df['display_dataset'] = df['dataset'].map(DATASET_NAMES)
    
    # Set up the figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [1.2, 1]})
    
    # Define markers for sex
    SEX_MARKERS = {'male': 'o', 'female': '^'}
    
    # Define line styles for trend lines
    LINE_STYLES = {
        'My Template_male': '-',      # solid
        'My Template_female': '--',   # dashed
        'Reference Template': '-',    # solid
    }
    
    # --- Left Panel: Scatter plot with trend lines ---
    # Plot by dataset and sex
    for dataset_orig in ['NKI', 'IPCAS']:
        display_name = DATASET_NAMES[dataset_orig]
        color = COLORS[display_name]
        dataset_subset = df[df['dataset'] == dataset_orig]
        
        # Plot each sex with different markers
        for sex in ['male', 'female']:
            subset = dataset_subset[dataset_subset['Sex_Text'] == sex]
            if len(subset) == 0:
                continue
            
            marker = SEX_MARKERS[sex]
            label = f"{display_name} {sex}"
            
            # Scatter plot with transparency
            ax1.scatter(
                subset['age_diff'], 
                subset['normalized_warp_value'],
                c=color, alpha=0.45, s=15, marker=marker, 
                label=label, edgecolors='none'
            )
        
        # Add trend lines
        if display_name == 'My Template':
            # Separate trend lines for male and female
            for sex in ['male', 'female']:
                subset = dataset_subset[dataset_subset['Sex_Text'] == sex]
                if len(subset) > 10:
                    x_trend, y_trend = compute_trend(
                        subset['age_diff'].values, 
                        subset['normalized_warp_value'].values,
                        frac=0.4
                    )
                    linestyle = LINE_STYLES[f'{display_name}_{sex}']
                    ax1.plot(x_trend, y_trend, color=color, linewidth=4, alpha=1.0, 
                            linestyle=linestyle)
        else:
            # Single trend line for Reference Template (combined sexes)
            if len(dataset_subset) > 10:
                x_trend, y_trend = compute_trend(
                    dataset_subset['age_diff'].values, 
                    dataset_subset['normalized_warp_value'].values,
                    frac=0.4
                )
                ax1.plot(x_trend, y_trend, color=color, linewidth=4, alpha=1.0)
    
    ax1.set_xlabel('Age differences between individual and template brain (year)', fontsize=12)
    ax1.set_ylabel('Warp value (Normalized)', fontsize=12)
    
    # Create custom legend with dataset colors and sex markers
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor=COLORS['My Template'], 
               markersize=8, label='My Template male'),
        Line2D([0], [0], marker='^', color='w', markerfacecolor=COLORS['My Template'], 
               markersize=8, label='My Template female'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor=COLORS['Reference Template'], 
               markersize=8, label='Reference Template male'),
        Line2D([0], [0], marker='^', color='w', markerfacecolor=COLORS['Reference Template'], 
               markersize=8, label='Reference Template female'),
        Line2D([0], [0], color=COLORS['My Template'], linewidth=3, linestyle='-', 
               label='My Template male trend'),
        Line2D([0], [0], color=COLORS['My Template'], linewidth=3, linestyle='--', 
               label='My Template female trend'),
        Line2D([0], [0], color=COLORS['Reference Template'], linewidth=3, linestyle='-', 
               label='Reference Template trend'),
    ]
    ax1.legend(handles=legend_elements, loc='upper right', frameon=True, 
               fancybox=True, framealpha=0.9, fontsize=8)
    
    # Set x-axis range
    x_min = df['age_diff'].min() - 0.5
    x_max = df['age_diff'].max() + 0.5
    ax1.set_xlim(x_min, min(x_max, 10))  # Cap at 10 like reference
    
    # Set y-axis with actual numeric values
    y_min_val = df['normalized_warp_value'].min()
    y_max_val = df['normalized_warp_value'].max()
    ax1.set_ylim(y_min_val - 0.01, y_max_val + 0.02)
    # Use nice tick values
    ax1.yaxis.set_major_locator(plt.MaxNLocator(5))
    
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(False)
    
    # --- Right Panel: Violin plots ---
    # Prepare data for violin plot
    violin_data = []
    order = []
    order_display = []
    
    for dataset_orig in ['IPCAS', 'NKI']:
        display_name = DATASET_NAMES[dataset_orig]
        for status in ['matching', 'mismatching']:
            subset = df[(df['dataset'] == dataset_orig) & (df['match_status'] == status)]
            label = f"{dataset_orig} {status}"
            display_label = f"{display_name} {status}"
            order.append(label)
            order_display.append(display_label)
            for _, row in subset.iterrows():
                violin_data.append({
                    'Category': label, 
                    'DisplayCategory': display_label,
                    'Warp value': row['normalized_warp_value'], 
                    'Dataset': dataset_orig,
                    'DisplayDataset': display_name,
                    'Sex': row['Sex_Text']
                })
    
    violin_df = pd.DataFrame(violin_data)
    
    # Plot violins
    positions = [0, 1, 2.5, 3.5]  # Add gap between My Template and Reference Template
    widths = 0.7
    
    for i, (label, display_label, pos) in enumerate(zip(order, order_display, positions)):
        subset_vals = violin_df[violin_df['Category'] == label]['Warp value'].values
        if len(subset_vals) == 0:
            continue
            
        dataset_orig = 'IPCAS' if 'IPCAS' in label else 'NKI'
        display_name = DATASET_NAMES[dataset_orig]
        is_matching = 'matching' in label and 'mismatching' not in label
        
        color = COLORS[display_name]
        alpha = 0.8 if is_matching else 0.5
        
        # Create violin
        parts = ax2.violinplot([subset_vals], positions=[pos], widths=widths, 
                               showmeans=False, showmedians=False)
        
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
        
        # Add sex-specific mean markers
        subset_df = violin_df[violin_df['Category'] == label]
        for sex, marker in SEX_MARKERS.items():
            sex_vals = subset_df[subset_df['Sex'] == sex]['Warp value'].values
            if len(sex_vals) > 0:
                sex_mean = np.mean(sex_vals)
                offset = -0.15 if sex == 'male' else 0.15
                ax2.plot([pos + offset], [sex_mean], marker=marker, markersize=8, 
                        markerfacecolor='white', markeredgecolor='black', markeredgewidth=1.5)
    
    ax2.set_xticks(positions)
    ax2.set_xticklabels(['My Template\nmatching', 'My Template\nmismatching', 
                         'Reference\nmatching', 'Reference\nmismatching'], fontsize=9)
    ax2.set_ylabel('Warp value (Normalized)', fontsize=12)
    
    # Set y-axis with actual numeric values
    ax2.set_ylim(y_min_val - 0.01, y_max_val + 0.02)
    ax2.yaxis.set_major_locator(plt.MaxNLocator(5))
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLORS['My Template'], alpha=0.8, label='My Template'),
        Patch(facecolor=COLORS['Reference Template'], alpha=0.8, label='Reference Template'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='white', 
               markeredgecolor='black', markersize=8, label='Male mean'),
        Line2D([0], [0], marker='^', color='w', markerfacecolor='white', 
               markeredgecolor='black', markersize=8, label='Female mean'),
    ]
    ax2.legend(handles=legend_elements, loc='upper right', frameon=True, fancybox=True, fontsize=9)
    
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
    print("Loading and merging data...")
    df = load_and_merge_data()
    
    print(f"Total samples after merge: {len(df)}")
    print(f"Datasets: {df['dataset'].value_counts().to_dict()}")
    print(f"Age difference range: [{df['age_diff'].min():.1f}, {df['age_diff'].max():.1f}]")
    print(f"Matching samples: {(df['match_status'] == 'matching').sum()}")
    print(f"Mismatching samples: {(df['match_status'] == 'mismatching').sum()}")
    
    # Summary by dataset
    print("\nSummary by dataset:")
    for dataset in ['IPCAS', 'NKI']:
        subset = df[df['dataset'] == dataset]
        print(f"  {dataset}: {len(subset)} samples, "
              f"age_diff range [{subset['age_diff'].min():.1f}, {subset['age_diff'].max():.1f}]")
    
    print("\nCreating plot...")
    create_combined_plot(df)
    
    # Also save the merged data
    output_csv = BASE_DIR / 'test_set_on_template_metrics_with_subject_age.csv'
    df.to_csv(output_csv, index=False)
    print(f"Saved merged data to: {output_csv}")
    
    print("Done!")

if __name__ == '__main__':
    main()
