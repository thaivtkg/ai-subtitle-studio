import re

class AutoQCService:
    @staticmethod
    def check_glossary_adherence(source_text: str, translated_text: str, glossary_map: dict[str, str]) -> list[str]:
        """
        Checks if the translated text contains the required glossary terms when the source text contains the original terms.
        """
        flags = []
        for src_term, tgt_term in glossary_map.items():
            # Simple case-insensitive match for the source term.
            # In a robust system, this might use word boundaries.
            if src_term.lower() in source_text.lower():
                if tgt_term.lower() not in translated_text.lower():
                    flags.append(f"missing_term: {tgt_term}")
        
        if flags:
            flags.insert(0, "glossary_violation")
            
        return flags

    @staticmethod
    def check_format_injection(source_text: str, translated_text: str) -> list[str]:
        """
        Checks if the LLM hallucinated bracketed notes like (Note: ...) or [Music] when they aren't in the source.
        """
        flags = []
        
        # Check for [] brackets
        source_brackets = re.findall(r'\[.*?\]', source_text)
        translated_brackets = re.findall(r'\[.*?\]', translated_text)
        if len(translated_brackets) > len(source_brackets):
            flags.append("format_injection: [] brackets")
            
        # Check for () brackets
        source_parens = re.findall(r'\(.*?\)', source_text)
        translated_parens = re.findall(r'\(.*?\)', translated_text)
        if len(translated_parens) > len(source_parens):
            flags.append("format_injection: () parens")
            
        # Check for "Note:" or "Translator's Note:"
        if re.search(r'\b(note|translator\'s note):\s', translated_text, re.IGNORECASE) and \
           not re.search(r'\b(note|translator\'s note):\s', source_text, re.IGNORECASE):
            flags.append("format_injection: Note keyword")
            
        return flags

    @staticmethod
    def evaluate_segment(source_text: str, translated_text: str, glossary_map: dict[str, str]) -> list[str]:
        """
        Runs all QC checks and returns a list of qc_flags to attach as metadata.
        """
        flags = []
        flags.extend(AutoQCService.check_glossary_adherence(source_text, translated_text, glossary_map))
        flags.extend(AutoQCService.check_format_injection(source_text, translated_text))
        return flags
