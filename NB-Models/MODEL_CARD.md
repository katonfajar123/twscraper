# Model Card: MBG Aspect Classifier (Naive Bayes)

**STATUS**: MODEL BELUM DILATIH

## Model Details
- **Model Name**: MBG Aspect Classifier (Naive Bayes)
- **Model Architecture**: Multinomial Naive Bayes (with TF-IDF word and character n-grams)
- **Target Tasks**: Aspect classification for MBG comments
- **Target Categories**: 3 aspects (Mutu_Gizi, Tata_Kelola, Distribusi)

## Training Data
- **Status**: Not yet available (pending human annotation)

## Performance Metrics
- **Macro F1**: TBD
- **Recall**: TBD
- **Balanced Accuracy**: TBD
- **Validation-Test Gap**: TBD

## Intended Use
- Classification of public comments regarding the Makan Bergizi Gratis (MBG) program into distinct operational aspects to facilitate monitoring and evaluation.
- Pipeline focuses on multi-label or independent binary classifiers for the three aspect categories.

## Limitations
- Model relies strictly on textual features; missing context from external sources (e.g., attached images, linked articles) may degrade performance.
- Not designed to assess sentiment (positive/negative/neutral), only aspect categorization.

## Ethical Considerations
- Bias may exist toward dominant dialects or specific regional issues overrepresented in the dataset.
- Potential misclassification can misroute feedback; therefore, critical issues should be reviewed manually.
- Assumes no personal identifiable information (PII) is used as primary decision features.

## Version History
- TBD
