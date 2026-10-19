from sklearn.feature_extraction.text import TfidfVectorizer

from scripts.thai import normalize_thai, tokenize


def test_split_sara_am_is_joined():
    assert normalize_thai("ดําเนินการ") == "ดำเนินการ"  # Tesseract output: nikhahit + sara aa
    assert normalize_thai("น้ํา") == "น้ำ"  # tone mark before nikhahit


def test_nfc_keeps_sara_am():
    assert normalize_thai("กำหนด") == "กำหนด"


def test_pua_glyphs_are_mapped():
    assert normalize_thai("ก") == "ก่"  # lowered mai ek
    assert normalize_thai("ป") == "ปิ"  # left-shifted sara i
    assert normalize_thai("าน") == "ฐาน"  # tho than without descender


def test_mark_order_and_typing_errors():
    assert normalize_thai("ก่ี") == "กี่"  # tone typed before upper vowel
    assert normalize_thai("ก่่") == "ก่"
    assert normalize_thai("เเก้ไข") == "แก้ไข"
    assert normalize_thai("ภาษา​ไทย") == "ภาษาไทย"


def test_tokenize_gives_real_thai_words():
    tokens = tokenize("มาตรฐานการรักษาความมั่นคงปลอดภัยสำหรับเว็บไซต์คืออะไร")
    assert {"มาตรฐาน", "ปลอดภัย", "เว็บไซต์"} <= set(tokens)
    assert "บเว" not in tokens  # fragment produced by the old tokenizer


def test_tokenize_is_robust_to_ocr_quirks():
    assert tokenize("ดําเนินการ") == tokenize("ดำเนินการ")
    assert tokenize("ความมั่น คง") == tokenize("ความมั่นคง")  # space inserted by OCR
    assert "2568" in tokenize("ปี ๒๕๖๘")


def test_english_tokens_unchanged():
    text = "Broken Access Control: violation of the principle of least privilege, e.g. CWE-200 (2021)."
    default = TfidfVectorizer(lowercase=True, stop_words="english").build_analyzer()
    assert tokenize(text.lower()) == default(text)
