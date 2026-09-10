import re
import unicodedata
import logging
import yaml
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

NEGATION_WORDS = {'tidak', 'bukan', 'belum', 'jangan', 'kurang', 'tanpa'}
DOMAIN_TERMS = {'mbg', 'sppg', 'bgn', '3t', 'slhs', 'haccp'}

STOPWORDS = {
    'yang', 'dan', 'di', 'ke', 'dari', 'ini', 'itu', 'untuk', 'dengan', 'pada', 
    'adalah', 'akan', 'juga', 'sudah', 'saya', 'kami', 'mereka', 'kita', 'ada', 
    'bisa', 'atau', 'oleh', 'jika', 'saat', 'agar', 'hanya', 'lebih', 'serta', 
    'antara', 'karena', 'tetapi', 'namun', 'maka', 'lalu', 'pun', 'kalau', 
    'supaya', 'demi', 'selain', 'sebagai', 'yakni', 'bahwa'
}

def normalize_unicode(text: str) -> str:
    """Apply NFC normalization."""
    if not isinstance(text, str):
        return ""
    return unicodedata.normalize('NFC', text)

def lowercase(text: str) -> str:
    """Convert text to lowercase."""
    return text.lower()

def replace_urls(text: str) -> str:
    """Replace URLs with 'URL' token."""
    pattern = r'http[s]?://\S+'
    return re.sub(pattern, 'URL', text)

def replace_mentions(text: str) -> str:
    """Replace @username with 'USER' token."""
    pattern = r'@\w+'
    return re.sub(pattern, 'USER', text)

def normalize_slang(text: str, slang_dict: dict) -> str:
    """Replace slang words using dictionary. Word-boundary aware. Case insensitive matching."""
    if not slang_dict:
        return text
    
    # We create a regex pattern for all slang words to replace them in one pass
    # Using \b to ensure word boundaries
    words = text.split()
    normalized_words = []
    for word in words:
        # Punctuation might need to be handled, but simple split for now
        lower_word = word.lower()
        if lower_word in slang_dict:
            # maintain case? Requirement says lowercase matching, but let's just replace with the dictionary value
            normalized_words.append(slang_dict[lower_word])
        else:
            normalized_words.append(word)
    return " ".join(normalized_words)

def load_slang_dict(path: Path) -> dict:
    """Load slang dictionary from YAML."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load slang dict at {path}: {e}")
        return {}

def load_config(path: Path) -> dict:
    """Load project config."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load config at {path}: {e}")
        return {}

def remove_stopwords(text: str, preserve_negation: bool = True, preserve_domain: bool = True) -> str:
    """Basic stopword removal that ALWAYS preserves negation words and domain terms."""
    words = text.split()
    filtered_words = []
    
    for word in words:
        lower_word = word.lower()
        if preserve_negation and lower_word in NEGATION_WORDS:
            filtered_words.append(word)
        elif preserve_domain and lower_word in DOMAIN_TERMS:
            filtered_words.append(word)
        elif lower_word not in STOPWORDS:
            filtered_words.append(word)
            
    return " ".join(filtered_words)

def stem_text(text: str, use_stemmer: bool = False) -> str:
    """Optional Sastrawi stemming. Default off."""
    if not use_stemmer:
        return text
        
    try:
        from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
        factory = StemmerFactory()
        stemmer = factory.create_stemmer()
        return stemmer.stem(text)
    except ImportError:
        logger.warning("Sastrawi is not installed. Skipping stemming.")
        return text

def preprocess_text(text: str, config: Optional[dict] = None, slang_dict: Optional[dict] = None, use_stemming: bool = False) -> str:
    """
    Full pipeline:
    1. normalize_unicode
    2. lowercase
    3. replace_urls
    4. replace_mentions
    5. normalize_slang (if dict provided)
    6. Optional: stem_text
    7. Strip extra whitespace
    """
    if pd.isna(text) or not isinstance(text, str):
        return ""
        
    text = normalize_unicode(text)
    text = lowercase(text)
    text = replace_urls(text)
    text = replace_mentions(text)
    
    if slang_dict:
        text = normalize_slang(text, slang_dict)
        
    # Could optionally add stopword removal here based on config
    if config and config.get('remove_stopwords', False):
        text = remove_stopwords(text)
        
    if use_stemming:
        text = stem_text(text, True)
        
    # Strip extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def preprocess_dataframe(df: pd.DataFrame, text_column: str = 'Teks_Komentar', output_column: str = 'Teks_Model', config: Optional[dict] = None, slang_dict: Optional[dict] = None) -> pd.DataFrame:
    """Apply preprocessing to entire dataframe. Keep original text. Add new column."""
    if text_column not in df.columns:
        raise ValueError(f"Column {text_column} not found in dataframe.")
        
    use_stemming = config.get('use_stemming', False) if config else False
    
    # Using apply for simplicity, could be optimized for very large datasets
    df[output_column] = df[text_column].apply(
        lambda x: preprocess_text(x, config=config, slang_dict=slang_dict, use_stemming=use_stemming)
    )
    
    return df
