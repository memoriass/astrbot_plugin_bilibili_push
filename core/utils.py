"""工具函数"""
from difflib import SequenceMatcher

def text_similarity(text1: str, text2: str) -> float:
    return SequenceMatcher(None, text1, text2).ratio()

def decode_unicode_escapes(text: str) -> str:
    # 简单实现，如果需要处理复杂转义，可以使用 codec
    return text.encode('utf-8').decode('unicode_escape') if text else ""
