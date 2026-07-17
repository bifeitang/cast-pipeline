"""
Plot age-wise Jacobian profiles similar to the reference image.
Shows mean_logJ and std_logJ across subject ages for male and female templates.
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Set style
plt.style.use('seaborn-whitegrid')

# Load data
df = pd.read_csv('test_set_dc_metrics_merged.csv')

# Remove outliers (likely failed registrations)
# mean_logJ should be roughly in range [-1, 1] for valid registrations
df = df[(df['mean_logJ'].abs() < 1) & (df['std_logJ'] < 1)]

# Create subject age bins (floor to integer)
df['subject_age_bin'] = df['subject_age'].apply(lambda x: int(np.floor(x)))

# Get unique template ages for filtering
unique_template_ages = sorted(df['template_age'].unique())

# Filter to reasonable age range (5-14 years)
df_filtered = df[(df['subject_age_bin'] >= 5) & (df['subject_age_bin'] <= 14)]

# Get unique age bins present in data
age_bins = sorted(df_filtered['subject_age_bin'].unique())

# Function to calculate mean and 95% CI
def get_stats(group, column):
    mean = group[column].mean()
    std = group[column].std()
    n = len(group)
    if n > 1:
        se = std / np.sqrt(n)
        ci_95 = 1.96 * se
    else:
        ci_95 = 0
    return pd.Series({
        'mean': mean,
        'std': std,
        'ci_lower': mean - ci_95,
        'ci_upper': mean + ci_95,
        'n': n
    })

# Calculate statistics for each template_sex, template_age, and subject_age_bin
stats_list = []
for template_sex in ['male', 'female']:
    for template_age in unique_template_ages:
        for age_bin in age_bins:
            mask = (df_filtered['template_sex'] == template_sex) & \
                   (df_filtered['template_age'] == template_age) & \
                   (df_filtered['subject_age_bin'] == age_bin)
            group = df_filtered[mask]
            if len(group) >= 3:  # Require at least 3 samples for meaningful stats
                for metric in ['mean_logJ', 'std_logJ']:
                    stats_row = get_stats(group, metric)
                    stats_row['template_sex'] = template_sex
                    stats_row['template_age'] = template_age
                    stats_row['subject_age_bin'] = age_bin
                    stats_row['metric'] = metric
                    stats_list.append(stats_row)

stats_df = pd.DataFrame(stats_list)

# Create the plot - 2 rows (mean_logJ, std_logJ) x 2 columns (male, female template)
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Color palette - viridis-style gradient from dark blue to yellow
from matplotlib import cm
viridis = cm.get_cmap('viridis', len(unique_template_ages))
colors = {age: viridis(i) for i, age in enumerate(unique_template_ages)}

metrics = ['mean_logJ', 'std_logJ']
metric_labels = [
    'mean_logJ\n(log volume scale; target ≈ 0)',
    'std_logJ\n(smoothness; lower = smoother)'
]

template_sexes = ['male', 'female']

for col_idx, template_sex in enumerate(template_sexes):
    for row_idx, (metric, metric_label) in enumerate(zip(metrics, metric_labels)):
        ax = axes[row_idx, col_idx]
        
        for template_age in unique_template_ages:
            mask = (stats_df['template_sex'] == template_sex) & \
                   (stats_df['template_age'] == template_age) & \
                   (stats_df['metric'] == metric)
            data = stats_df[mask].sort_values('subject_age_bin')
            
            if len(data) >= 3:  # Only plot if we have enough data points
                color = colors.get(template_age, '#333333')
                
                # Plot line with markers
                ax.plot(data['subject_age_bin'], data['mean'], 
                       marker='o', markersize=5, linewidth=1.5,
                       color=color, label=f'Age-{template_age}')
                
                # Plot confidence interval as shaded region
                ax.fill_between(data['subject_age_bin'], 
                              data['ci_lower'], data['ci_upper'],
                              alpha=0.15, color=color)
        
        # Add horizontal line at 0 for mean_logJ
        if metric == 'mean_logJ':
            ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.7)
        
        ax.set_ylabel(metric_label, fontsize=10)
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        ax.tick_params(axis='both', which='major', labelsize=9)
        
        # Set x-axis ticks to integer ages
        ax.set_xticks(age_bins)
        
        if row_idx == 0:
            ax.set_title(f'Template gender: {template_sex}', fontsize=12, fontweight='bold')
        
        if row_idx == 1:
            ax.set_xlabel('Subject Age (years)', fontsize=11)
        
        # Add legend to top-right subplot
        if row_idx == 0 and col_idx == 1:
            ax.legend(title='Template Age', loc='upper left', fontsize=8, 
                     bbox_to_anchor=(1.02, 1), borderaxespad=0)

# Synchronize y-axis limits for same rows
for row_idx in range(2):
    ymin = min(axes[row_idx, 0].get_ylim()[0], axes[row_idx, 1].get_ylim()[0])
    ymax = max(axes[row_idx, 0].get_ylim()[1], axes[row_idx, 1].get_ylim()[1])
    # Add some padding
    padding = (ymax - ymin) * 0.05
    for col_idx in range(2):
        axes[row_idx, col_idx].set_ylim(ymin - padding, ymax + padding)

plt.suptitle('Age-wise Jacobian profiles when registering to various templates', 
             fontsize=14, fontweight='bold')
plt.tight_layout()
plt.subplots_adjust(top=0.92, right=0.85)
plt.savefig('jacobian_profiles.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.savefig('jacobian_profiles.pdf', bbox_inches='tight', facecolor='white')
print('Saved: jacobian_profiles.png and jacobian_profiles.pdf')
plt.close()
