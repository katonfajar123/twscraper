# Data Directory

This directory stores datasets and samples for the annotation and modeling pipeline.

## Contents
- `annotation_template.csv`: Full direct reply set with empty labels for annotation.
- `pilot_annotation_300.csv`: 300 candidate samples for pilot annotation.

## Important Rules
- **NO RAW DATASET COPIES**: Do not copy the raw dataset into this directory. Reference the parent output directory directly.
- **TWEET IDS ARE STRINGS**: Tweet IDs (e.g., `Tweet_ID`, `Root_Tweet_ID`) are treated as strings to avoid precision loss. **DO NOT** open these CSV files directly in Excel without using the Data Import feature to force string types for ID columns.

## Provenance Info
- **Source File**: `../output/MBG_Dataset_DirectReplies_20260907_0825.csv`
- **Expected Total Rows**: 20,000
- **Direct Replies**: 17,694
