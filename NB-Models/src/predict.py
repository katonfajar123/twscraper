import numpy as np
import pandas as pd
import logging
import joblib
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

VALID_CATEGORIES = ['Mutu_Gizi', 'Tata_Kelola', 'Distribusi']
logger = logging.getLogger(__name__)

class AspectPredictor:
    def __init__(self, model_path: Path, config: dict):
        self.model = None
        self.confidence_threshold = config.get('confidence_threshold', 0.6)
        self.margin_threshold = config.get('margin_threshold', 0.15)
        self.model_version = config.get('model_version', 'NONE')
        self.label_guide_version = config.get('label_guide_version', '1.0')
        self.model_path = Path(model_path)
        
    def load_model(self) -> None:
        """
        Load model with joblib, validate it.
        """
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        self.model = joblib.load(self.model_path)
        logger.info(f"Model loaded from {self.model_path}")

    def determine_status(self, confidence: float, margin: float) -> str:
        """
        ACCEPTED if confidence >= threshold AND margin >= margin_threshold
        NEEDS_REVIEW otherwise
        """
        if confidence >= self.confidence_threshold and margin >= self.margin_threshold:
            return 'ACCEPTED'
        return 'NEEDS_REVIEW'

    def predict_single(self, text: str, root_text: str = '') -> dict:
        """
        Returns: kategori, confidence, margin, prediction_status
        """
        if self.model is None:
            raise ValueError("Model not loaded")
            
        proba = self.model.predict_proba([text])[0]
        classes = self.model.classes_
        
        sorted_indices = np.argsort(proba)[::-1]
        top_prob = proba[sorted_indices[0]]
        top_class = classes[sorted_indices[0]]
        
        margin = 0.0
        if len(classes) > 1:
            second_prob = proba[sorted_indices[1]]
            margin = top_prob - second_prob
            
        status = self.determine_status(top_prob, margin)
        
        return {
            'kategori': top_class,
            'confidence': float(top_prob),
            'margin': float(margin),
            'prediction_status': status
        }

    def predict_batch(self, df: pd.DataFrame, text_col: str = 'Teks_Komentar') -> pd.DataFrame:
        """
        Predict for entire dataframe
        Output columns: Kategori_Utama, Confidence, Top2_Margin, Prediction_Status, Model_Version, Label_Guide_Version, Predicted_At
        """
        if self.model is None:
            raise ValueError("Model not loaded")
            
        texts = df[text_col].tolist()
        probas = self.model.predict_proba(texts)
        classes = self.model.classes_
        
        kategori_utama = []
        confidences = []
        margins = []
        statuses = []
        
        for proba in probas:
            sorted_indices = np.argsort(proba)[::-1]
            top_prob = proba[sorted_indices[0]]
            top_class = classes[sorted_indices[0]]
            
            margin = 0.0
            if len(classes) > 1:
                second_prob = proba[sorted_indices[1]]
                margin = top_prob - second_prob
                
            status = self.determine_status(top_prob, margin)
            
            kategori_utama.append(top_class)
            confidences.append(float(top_prob))
            margins.append(float(margin))
            statuses.append(status)
            
        out_df = df.copy()
        out_df['Kategori_Utama'] = kategori_utama
        out_df['Confidence'] = confidences
        out_df['Top2_Margin'] = margins
        out_df['Prediction_Status'] = statuses
        out_df['Model_Version'] = self.model_version
        out_df['Label_Guide_Version'] = self.label_guide_version
        out_df['Predicted_At'] = datetime.now().isoformat()
        
        return out_df

def export_predictions(df: pd.DataFrame, output_path: Path) -> None:
    """
    Save predictions as CSV with:
    - utf-8-sig encoding
    - Tweet_ID as string
    - Raw text preserved
    - All required output columns
    """
    if 'Tweet_ID' in df.columns:
        df['Tweet_ID'] = df['Tweet_ID'].astype(str)
        
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

def calibrate_threshold(model, X_val, y_val, root_ids_val) -> dict:
    """
    Find optimal confidence and margin thresholds using VALIDATION set only.
    Return thresholds and coverage/accuracy tradeoff.
    """
    probas = model.predict_proba(X_val)
    preds = model.predict(X_val)
    classes = model.classes_
    
    margins = []
    confidences = []
    for proba in probas:
        sorted_indices = np.argsort(proba)[::-1]
        confidences.append(proba[sorted_indices[0]])
        if len(classes) > 1:
            margins.append(proba[sorted_indices[0]] - proba[sorted_indices[1]])
        else:
            margins.append(0.0)
            
    confidences = np.array(confidences)
    margins = np.array(margins)
    y_val = np.array(y_val)
    preds = np.array(preds)
    
    best_thresholds = {'confidence': 0.6, 'margin': 0.15}
    best_f1 = 0.0
    best_coverage = 0.0
    
    results = []
    
    for conf_th in np.arange(0.4, 0.9, 0.05):
        for marg_th in np.arange(0.05, 0.3, 0.05):
            mask = (confidences >= conf_th) & (margins >= marg_th)
            coverage = np.mean(mask)
            
            if coverage > 0.1:  # Require at least 10% coverage
                accepted_preds = preds[mask]
                accepted_true = y_val[mask]
                
                from sklearn.metrics import f1_score
                f1 = f1_score(accepted_true, accepted_preds, average='macro', labels=VALID_CATEGORIES, zero_division=0)
                
                results.append({
                    'confidence_threshold': float(conf_th),
                    'margin_threshold': float(marg_th),
                    'coverage': float(coverage),
                    'macro_f1': float(f1)
                })
                
                if f1 > best_f1:
                    best_f1 = f1
                    best_thresholds = {'confidence': float(conf_th), 'margin': float(marg_th)}
                    best_coverage = float(coverage)
                    
    return {
        'optimal_thresholds': best_thresholds,
        'best_macro_f1_on_accepted': best_f1,
        'coverage_at_optimal': best_coverage,
        'calibration_results': results
    }

if __name__ == '__main__':
    print('MODEL BELUM TERSEDIA. Latih model terlebih dahulu setelah ground truth tersedia.')
