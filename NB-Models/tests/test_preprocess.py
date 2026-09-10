"""Tests for preprocessing pipeline."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.preprocess import (
    normalize_unicode,
    lowercase,
    replace_urls,
    replace_mentions,
    normalize_slang,
    remove_stopwords,
    stem_text,
    preprocess_text,
    preprocess_dataframe,
    NEGATION_WORDS,
    DOMAIN_TERMS,
)
import pandas as pd


class TestURLReplacement:
    def test_http_url(self):
        assert 'URL' in replace_urls('kunjungi http://example.com ya')

    def test_https_url(self):
        assert 'URL' in replace_urls('lihat https://t.co/abc123')

    def test_no_url(self):
        text = 'tidak ada url di sini'
        assert replace_urls(text) == text


class TestMentionReplacement:
    def test_single_mention(self):
        result = replace_mentions('hai @user123 apa kabar')
        assert '@user123' not in result
        assert 'USER' in result

    def test_multiple_mentions(self):
        result = replace_mentions('@a @b ini MBG')
        assert result.count('USER') == 2

    def test_no_mention(self):
        text = 'tanpa mention'
        assert replace_mentions(text) == text


class TestNegationPreservation:
    @pytest.mark.parametrize('word', ['tidak', 'bukan', 'belum', 'jangan', 'kurang', 'tanpa'])
    def test_negation_preserved_in_preprocessing(self, word):
        text = f'{word} enak makanannya'
        result = preprocess_text(text)
        assert word in result

    def test_negation_in_stopword_removal(self):
        text = 'ini tidak enak untuk saya'
        result = remove_stopwords(text, preserve_negation=True)
        assert 'tidak' in result


class TestDomainTermPreservation:
    @pytest.mark.parametrize('term', ['mbg', 'sppg', 'bgn', '3t', 'slhs', 'haccp'])
    def test_domain_term_preserved_after_lowercase(self, term):
        """Domain terms should survive preprocessing (lowercased)."""
        text = f'Program {term.upper()} sangat baik'
        result = preprocess_text(text)
        assert term in result

    def test_domain_in_stopword_removal(self):
        text = 'ini mbg untuk saya'
        result = remove_stopwords(text, preserve_domain=True)
        assert 'mbg' in result


class TestSlangNormalization:
    def test_gak_to_tidak(self):
        result = normalize_slang('gak enak', {'gak': 'tidak'})
        assert 'tidak' in result

    def test_yg_to_yang(self):
        result = normalize_slang('yg penting', {'yg': 'yang'})
        assert 'yang' in result

    def test_no_change_without_dict(self):
        text = 'gak enak'
        assert normalize_slang(text, {}) == text


class TestRawTextPreservation:
    def test_original_unchanged_in_dataframe(self):
        df = pd.DataFrame({
            'Tweet_ID': ['1', '2'],
            'Teks_Komentar': [
                'MBG @user http://link.com gak enak 🍚',
                'Porsinya kurang untuk anak SMP',
            ],
        })
        original_texts = df['Teks_Komentar'].tolist()
        result = preprocess_dataframe(df.copy())
        assert result['Teks_Komentar'].tolist() == original_texts
        assert 'Teks_Model' in result.columns


class TestUnicodeNormalization:
    def test_nfc_normalization(self):
        import unicodedata
        text = 'caf\u0065\u0301'  # 'e' + combining acute
        result = normalize_unicode(text)
        assert result == unicodedata.normalize('NFC', text)


class TestIDRemainsString:
    def test_id_string_after_preprocess(self):
        df = pd.DataFrame({
            'Tweet_ID': ['1234567890123456789'],
            'Teks_Komentar': ['test text'],
        })
        result = preprocess_dataframe(df.copy())
        assert result['Tweet_ID'].dtype == object
        assert result['Tweet_ID'].iloc[0] == '1234567890123456789'


class TestEmojiPreservation:
    def test_emoji_not_removed(self):
        text = 'enak banget 🍚🍗 mantap'
        result = preprocess_text(text)
        assert '🍚' in result
        assert '🍗' in result
