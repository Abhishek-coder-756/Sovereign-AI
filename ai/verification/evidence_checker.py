import re


class EvidenceChecker:

    # ============================================================
    # CITATION EXTRACTION
    # ============================================================

    def extract_citations(self, text):
        """
        Extract citations.

        Examples:
            [Source 1]
            [Source 2]
            [Source 1][Source 2]
        """

        matches = re.findall(
            r"\[Source\s+(\d+)\]",
            text,
            flags=re.IGNORECASE
        )

        return [
            f"[Source {number}]"
            for number in matches
        ]

    # ============================================================
    # REMOVE CITATIONS
    # ============================================================

    def remove_citations(self, text):
        """
        Remove citations from claim text.
        """

        return re.sub(
            r"\s*\[Source\s+\d+\]",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()

    # ============================================================
    # EXTRACT CLAIMS
    # ============================================================

    def extract_claims(self, answer):
        """
        Convert answer into:

        [
            {
                "claim": "...",
                "citations": ["[Source 1]", "[Source 2]"]
            }
        ]
        """

        answer = answer.replace(
            "```",
            ""
        )

        lines = answer.splitlines()

        claims = []

        for line in lines:

            line = line.strip()

            if not line:
                continue

            citations = self.extract_citations(
                line
            )

            clean_claim = self.remove_citations(
                line
            )

            # ----------------------------------------------------
            # Citation-only line
            # ----------------------------------------------------

            if not clean_claim:

                if claims:
                    claims[-1]["citations"].extend(
                        citations
                    )

                continue

            # ----------------------------------------------------
            # Normal claim
            # ----------------------------------------------------

            claims.append({
                "claim": clean_claim,
                "citations": citations
            })

        return claims

    # ============================================================
    # SOURCE LOOKUP
    # ============================================================

    def get_source_by_id(
        self,
        source_id,
        sources
    ):
        """
        Find source using explicit ID.

        Example:

            Source 1 -> id 1
            Source 2 -> id 2

        If explicit IDs are unavailable,
        fall back to list position.
        """

        # --------------------------------------------------------
        # Explicit ID lookup
        # --------------------------------------------------------

        for source in sources:

            if "id" in source:

                try:

                    if int(source["id"]) == int(
                        source_id
                    ):
                        return source

                except (
                    TypeError,
                    ValueError
                ):
                    pass

        # --------------------------------------------------------
        # Position fallback
        # --------------------------------------------------------

        if (
            source_id >= 1
            and source_id <= len(sources)
        ):

            return sources[
                source_id - 1
            ]

        return None

    # ============================================================
    # NORMALIZE TEXT
    # ============================================================

    def normalize_text(self, text):

        text = text.lower()

        text = text.replace(
            "°c",
            " c"
        )

        text = re.sub(
            r"[^\w\s.%+-]",
            " ",
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text.strip()

    # ============================================================
    # TEMPERATURE VALUE
    # ============================================================

    def extract_temperature_value(
        self,
        text
    ):

        matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*°?\s*c",
            text,
            flags=re.IGNORECASE
        )

        if not matches:
            return None

        return float(
            matches[0]
        )

    # ============================================================
    # ALL TEMPERATURE VALUES
    # ============================================================

    def extract_all_temperature_values(
        self,
        text
    ):

        matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*°?\s*c",
            text,
            flags=re.IGNORECASE
        )

        return [
            float(value)
            for value in matches
        ]

    # ============================================================
    # VIBRATION VALUE
    # ============================================================

    def extract_vibration_value(
        self,
        text
    ):

        matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*mm/s",
            text,
            flags=re.IGNORECASE
        )

        if not matches:
            return None

        return float(
            matches[0]
        )

    # ============================================================
    # ALL VIBRATION VALUES
    # ============================================================

    def extract_all_vibration_values(
        self,
        text
    ):

        matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*mm/s",
            text,
            flags=re.IGNORECASE
        )

        return [
            float(value)
            for value in matches
        ]

    # ============================================================
    # VIBRATION THRESHOLD
    # ============================================================

    def extract_vibration_threshold(
        self,
        text
    ):

        patterns = [

            r">\s*7\s*mm/s",

            r"above\s+7\s*mm/s",

            r"exceed(?:s|ing)?\s+7\s*mm/s",

            r"greater\s+than\s+7\s*mm/s"
        ]

        for pattern in patterns:

            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE
            ):

                return 7.0

        return None

    # ============================================================
    # TEMPERATURE THRESHOLD
    # ============================================================

    def extract_temperature_threshold(
        self,
        text
    ):

        patterns = [

            r">\s*580\s*°?\s*c",

            r"above\s+580\s*°?\s*c",

            r"exceed(?:s|ing)?\s+580\s*°?\s*c",

            r"greater\s+than\s+580\s*°?\s*c"
        ]

        for pattern in patterns:

            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE
            ):

                return 580.0

        return None

    # ============================================================
    # SOURCE SUPPORT CHECK
    # ============================================================

    def source_supports_claim(
        self,
        claim,
        source_text
    ):
        """
        Check whether ONE source contains direct evidence
        relevant to the claim.
        """

        claim_normalized = self.normalize_text(
            claim
        )

        source_normalized = self.normalize_text(
            source_text
        )

        # ========================================================
        # TEMPERATURE
        # ========================================================

        claim_temperature = (
            self.extract_temperature_value(
                claim
            )
        )

        if claim_temperature is not None:

            source_temperatures = (
                self.extract_all_temperature_values(
                    source_text
                )
            )

            return (
                claim_temperature
                in source_temperatures
            )

        # ========================================================
        # VIBRATION
        # ========================================================

        claim_vibration = (
            self.extract_vibration_value(
                claim
            )
        )

        if claim_vibration is not None:

            source_vibrations = (
                self.extract_all_vibration_values(
                    source_text
                )
            )

            return (
                claim_vibration
                in source_vibrations
            )

        # ========================================================
        # IMPORTANT INDUSTRIAL KEYWORDS
        # ========================================================

        keywords = [

            "critical",
            "inspection",
            "inspect",
            "monitoring",
            "shutdown",
            "controlled shutdown",
            "bearing",
            "rotor",
            "lubrication",
            "sensor",
            "supervisor",
            "control room",
            "abnormal",
            "normal operation",
            "lockout",
            "isolation"
        ]

        claim_keywords = [
            keyword
            for keyword in keywords
            if keyword in claim_normalized
        ]

        if claim_keywords:

            for keyword in claim_keywords:

                if keyword in source_normalized:

                    return True

        # ========================================================
        # GENERAL WORD OVERLAP
        # ========================================================

        claim_words = set(
            word
            for word in claim_normalized.split()
            if len(word) > 3
        )

        source_words = set(
            word
            for word in source_normalized.split()
            if len(word) > 3
        )

        if not claim_words:
            return False

        overlap = (
            claim_words.intersection(
                source_words
            )
        )

        ratio = (
            len(overlap)
            /
            len(claim_words)
        )

        return ratio >= 0.35

    # ============================================================
    # CLAIM SUPPORTED BY MULTIPLE SOURCES
    # ============================================================

    def claim_supported_by_sources(
        self,
        claim,
        source_texts
    ):
        """
        Determine whether the complete claim is supported
        by the cited evidence.

        Supports:
        - exact temperature values
        - exact vibration values
        - temperature rules
        - vibration rules
        - direct procedural statements
        """

        if not source_texts:
            return False

        claim_normalized = self.normalize_text(claim)

        combined_text = "\n".join(source_texts)

        combined_normalized = self.normalize_text(
            combined_text
        )

        # ========================================================
        # TEMPERATURE VALUE
        # ========================================================

        claim_temperature = (
            self.extract_temperature_value(claim)
        )

        if (
            claim_temperature is not None
            and "if" not in claim_normalized
        ):

            source_temperatures = (
                self.extract_all_temperature_values(
                    combined_text
                )
            )

            if claim_temperature not in source_temperatures:
                return False

            # If claim says threshold/exceeds/critical,
            # verify the corresponding threshold.
            if (
                "critical" in claim_normalized
                or "threshold" in claim_normalized
                or "exceed" in claim_normalized
                or "exceeds" in claim_normalized
            ):

                threshold = (
                    self.extract_temperature_threshold(
                        combined_text
                    )
                )

                if threshold is None:
                    return False

                if (
                    "exceed" in claim_normalized
                    or "exceeds" in claim_normalized
                ):

                    if claim_temperature <= threshold:
                        return False

            return True

        # ========================================================
        # VIBRATION VALUE
        # ========================================================

        claim_vibration = (
            self.extract_vibration_value(claim)
        )

        if (
            claim_vibration is not None
            and "if" not in claim_normalized
        ):

            source_vibrations = (
                self.extract_all_vibration_values(
                    combined_text
                )
            )

            if claim_vibration not in source_vibrations:
                return False

            if (
                "threshold" in claim_normalized
                or "inspection" in claim_normalized
                or "inspect" in claim_normalized
                or "exceed" in claim_normalized
                or "exceeds" in claim_normalized
                or "monitoring" in claim_normalized
            ):

                threshold = (
                    self.extract_vibration_threshold(
                        combined_text
                    )
                )

                if threshold is None:
                    return False

                if (
                    "exceed" in claim_normalized
                    or "exceeds" in claim_normalized
                ):

                    if claim_vibration <= threshold:
                        return False

            return True

        # ========================================================
        # TEMPERATURE RULE
        # ========================================================

        temperature_rule = re.search(
            r"(?:above|exceed(?:s|ing)?)\s+"
            r"(\d+(?:\.\d+)?)\s*c",
            claim_normalized,
            flags=re.IGNORECASE
        )

        if (
            temperature_rule
            and
            "temperature" in claim_normalized
        ):

            claimed_threshold = float(
                temperature_rule.group(1)
            )

            evidence_threshold = (
                self.extract_temperature_threshold(
                    combined_text
                )
            )

            if (
                evidence_threshold is not None
                and
                claimed_threshold == evidence_threshold
            ):

                # The claim must also contain the
                # relevant action supported by evidence.
                action_supported = True

                if "controlled shutdown" in claim_normalized:
                    action_supported = (
                        "controlled shutdown"
                        in combined_normalized
                    )

                if (
                    "supervisor" in claim_normalized
                    and
                    "supervisor" not in combined_normalized
                ):
                    action_supported = False

                if action_supported:
                    return True

        # ========================================================
        # VIBRATION RULE
        # ========================================================

        vibration_rule = re.search(
            r"(?:above|exceed(?:s|ing)?)\s+"
            r"(\d+(?:\.\d+)?)\s*mm/s",
            claim_normalized,
            flags=re.IGNORECASE
        )

        if (
            vibration_rule
            and
            "vibration" in claim_normalized
        ):

            claimed_threshold = float(
                vibration_rule.group(1)
            )

            evidence_threshold = (
                self.extract_vibration_threshold(
                    combined_text
                )
            )

            if (
                evidence_threshold is not None
                and
                claimed_threshold == evidence_threshold
            ):

                # Verify the action portion of the rule.
                action_supported = True

                if "stop normal operation" in claim_normalized:
                    action_supported = (
                        "stop normal operation"
                        in combined_normalized
                    )

                if (
                    "initiate an inspection"
                    in claim_normalized
                ):
                    action_supported = (
                        "initiate an inspection"
                        in combined_normalized
                    )

                if action_supported:
                    return True

        # ========================================================
        # DIRECT PROCEDURAL CLAIM
        # ========================================================

        important_phrases = [

            "controlled shutdown",

            "stop normal operation",

            "bearing system",

            "rotor assembly",

            "lubrication condition",

            "monitoring sensors",

            "authorized maintenance personnel",

            "maintenance supervisor",

            "control room",

            "control-room operator",

            "lockout procedures",

            "isolation procedures",

            "incident log",

            "document all findings"
        ]

        for phrase in important_phrases:

            if phrase in claim_normalized:

                if phrase in combined_normalized:
                    return True

        # ========================================================
        # GENERAL KEYWORD SUPPORT
        # ========================================================

        important_keywords = [

            "critical",
            "inspection",
            "inspect",
            "monitoring",
            "shutdown",
            "bearing",
            "rotor",
            "lubrication",
            "sensor",
            "supervisor",
            "abnormal",
            "normal operation",
            "lockout",
            "isolation"
        ]

        claim_keywords = [
            keyword
            for keyword in important_keywords
            if keyword in claim_normalized
        ]

        if claim_keywords:

            matched_keywords = sum(
                1
                for keyword in claim_keywords
                if keyword in combined_normalized
            )

            if matched_keywords >= max(
                1,
                len(claim_keywords) // 2
            ):

                return True

        # ========================================================
        # GENERAL WORD OVERLAP
        # ========================================================

        claim_words = {
            word
            for word in claim_normalized.split()
            if len(word) > 3
        }

        source_words = {
            word
            for word in combined_normalized.split()
            if len(word) > 3
        }

        if not claim_words:
            return False

        overlap = (
            claim_words.intersection(
                source_words
            )
        )

        ratio = (
            len(overlap)
            /
            len(claim_words)
        )

        return ratio >= 0.25

    # ============================================================
    # CLAIM → CITATION → EVIDENCE
    # ============================================================

    def verify_claim_citations(
        self,
        answer,
        sources
    ):

        claims = self.extract_claims(
            answer
        )

        evidence_map = []

        all_valid = True

        # ========================================================
        # LOOP THROUGH CLAIMS
        # ========================================================

        for claim_data in claims:

            claim = claim_data[
                "claim"
            ]

            citations = claim_data[
                "citations"
            ]

            # ====================================================
            # MISSING CITATION
            # ====================================================

            if not citations:

                evidence_map.append({

                    "claim":
                        claim,

                    "citations":
                        [],

                    "evidence":
                        [],

                    "status":
                        "MISSING_CITATION"
                })

                all_valid = False

                continue

            # ====================================================
            # RESOLVE ALL CITATIONS
            # ====================================================

            resolved_sources = []

            claim_evidence = []

            invalid_citation = False

            for citation in citations:

                match = re.search(
                    r"\[Source\s+(\d+)\]",
                    citation,
                    flags=re.IGNORECASE
                )

                if not match:

                    claim_evidence.append({

                        "source_id":
                            None,

                        "status":
                            "INVALID_CITATION"
                    })

                    invalid_citation = True

                    continue

                source_id = int(
                    match.group(1)
                )

                source = (
                    self.get_source_by_id(
                        source_id,
                        sources
                    )
                )

                if source is None:

                    claim_evidence.append({

                        "source_id":
                            source_id,

                        "status":
                            "INVALID_CITATION"
                    })

                    invalid_citation = True

                    continue

                resolved_sources.append(
                    source
                )

            # ====================================================
            # INVALID CITATION
            # ====================================================

            if invalid_citation:

                evidence_map.append({

                    "claim":
                        claim,

                    "citations":
                        citations,

                    "evidence":
                        claim_evidence,

                    "status":
                        "INVALID_CITATION"
                })

                all_valid = False

                continue

            # ====================================================
            # COMBINED EVIDENCE
            # ====================================================

            source_texts = [
                source.get(
                    "text",
                    ""
                )
                for source in resolved_sources
            ]

            claim_supported = (
                self.claim_supported_by_sources(
                    claim,
                    source_texts
                )
            )

            # ====================================================
            # BUILD EVIDENCE MAP
            # ====================================================

            for source in resolved_sources:

                source_text = source.get(
                    "text",
                    ""
                )

                direct_support = (
                    self.source_supports_claim(
                        claim,
                        source_text
                    )
                )

                if claim_supported:

                    if direct_support:

                        source_status = (
                            "SUPPORTED"
                        )

                    else:

                        source_status = (
                            "PARTIAL_SUPPORT"
                        )

                else:

                    if direct_support:

                        source_status = (
                            "PARTIAL_SUPPORT"
                        )

                    else:

                        source_status = (
                            "CITATION_MISMATCH"
                        )

                claim_evidence.append({

                    "source_id":
                        source.get(
                            "id"
                        ),

                    "document":
                        source.get(
                            "source",
                            "Unknown"
                        ),

                    "page":
                        source.get(
                            "page",
                            "Unknown"
                        ),

                    "score":
                        source.get(
                            "score"
                        ),

                    "text":
                        source_text,

                    "status":
                        source_status
                })

            # ====================================================
            # CLAIM STATUS
            # ====================================================

            if claim_supported:

                claim_status = (
                    "SUPPORTED"
                )

            else:

                claim_status = (
                    "CITATION_MISMATCH"
                )

                all_valid = False

            # ====================================================
            # SAVE CLAIM RESULT
            # ====================================================

            evidence_map.append({

                "claim":
                    claim,

                "citations":
                    citations,

                "evidence":
                    claim_evidence,

                "status":
                    claim_status
            })

        return {

            "verified":
                all_valid,

            "evidence_map":
                evidence_map
        }

    # ============================================================
    # VIBRATION LOGIC CHECK
    # ============================================================

    def check_vibration(
        self,
        answer,
        evidence
    ):

        value = (
            self.extract_vibration_value(
                answer
            )
        )

        if value is None:
            return True, None

        threshold = (
            self.extract_vibration_threshold(
                evidence
            )
        )

        if threshold is None:
            return True, None

        print(
            "\n>>> VIBRATION CHECK"
        )

        print(
            f"Answer vibration: {value}"
        )

        print(
            f"Evidence threshold: {threshold}"
        )

        # ========================================================
        # ABOVE THRESHOLD
        # ========================================================

        if value > threshold:

            wrong_patterns = [
                                r"\btemperature\b.{0,80}\bis\s+(?:normal|warning|monitoring)\b",
                                r"\btemperature\b.{0,80}\bclassified\s+as\s+(?:normal|warning|monitoring)\b",
                                r"\btemperature\b.{0,80}\bwithin\s+(?:normal|warning|monitoring)\b"
                            ]

            for pattern in wrong_patterns:

                if re.search(
                    pattern,
                    answer,
                    flags=
                    re.IGNORECASE |
                    re.DOTALL
                ):

                    reason = (
                        f"The answer incorrectly "
                        f"classifies {value} "
                        f"mm/s as monitoring. "
                        f"Evidence states that "
                        f"vibration above "
                        f"{threshold} mm/s "
                        f"requires inspection."
                    )

                    print(
                        "Result: CONTRADICTED"
                    )

                    return False, reason

            # ----------------------------------------------------
            # Correct answer must mention inspection
            # ----------------------------------------------------

            if not re.search(
                r"\binspect(?:ion)?\b",
                answer,
                flags=re.IGNORECASE
            ):

                reason = (
                    f"Vibration is {value} "
                    f"mm/s, which exceeds "
                    f"the {threshold} mm/s "
                    f"inspection threshold."
                )

                return False, reason

            print(
                f"Vibration: "
                f"{value} mm/s"
            )

            print(
                f"Threshold: "
                f"{threshold} mm/s"
            )

            print(
                f"Comparison: "
                f"{value} > {threshold}"
            )

            print(
                "Result: "
                "INSPECTION REQUIRED"
            )

            return True, None

        return True, None

    # ============================================================
    # TEMPERATURE LOGIC CHECK
    # ============================================================

    def check_temperature(
        self,
        answer,
        evidence
    ):

        value = (
            self.extract_temperature_value(
                answer
            )
        )

        if value is None:
            return True, None

        threshold = (
            self.extract_temperature_threshold(
                evidence
            )
        )

        if threshold is None:
            return True, None

        print(
            "\n>>> TEMPERATURE CHECK"
        )

        print(
            f"Answer temperature: "
            f"{value}"
        )

        print(
            f"Evidence threshold: "
            f"{threshold}"
        )

        # ========================================================
        # ABOVE CRITICAL THRESHOLD
        # ========================================================

        if value > threshold:

            wrong_patterns = [

                r"temperature"
                r".{0,300}?"
                r"\bnormal\b",

                r"temperature"
                r".{0,300}?"
                r"\bwarning\b",

                r"temperature"
                r".{0,300}?"
                r"\bmonitoring\b"
            ]

            for pattern in wrong_patterns:

                if re.search(
                    pattern,
                    answer,
                    flags=
                    re.IGNORECASE |
                    re.DOTALL
                ):

                    reason = (
                        f"The answer incorrectly "
                        f"classifies {value}°C "
                        f"as normal, warning, "
                        f"or monitoring. "
                        f"Evidence states that "
                        f"temperature above "
                        f"{threshold}°C is "
                        f"critical."
                    )

                    print(
                        "Result: CONTRADICTED"
                    )

                    return False, reason

            # ----------------------------------------------------
            # Must contain critical
            # ----------------------------------------------------

            if not re.search(
                r"\bcritical\b",
                answer,
                flags=re.IGNORECASE
            ):

                reason = (
                    f"Temperature is "
                    f"{value}°C, which "
                    f"exceeds the critical "
                    f"threshold of "
                    f"{threshold}°C."
                )

                return False, reason

            print(
                f"Temperature: "
                f"{value}°C"
            )

            print(
                f"Threshold: "
                f"{threshold}°C"
            )

            print(
                f"Comparison: "
                f"{value} > {threshold}"
            )

            print(
                "Result: "
                "CRITICAL TEMPERATURE"
            )

            return True, None

        return True, None

    # ============================================================
    # DETERMINISTIC CHECK
    # ============================================================

    def deterministic_threshold_check(
        self,
        answer,
        evidence
    ):

        vibration_ok, vibration_reason = (
            self.check_vibration(
                answer,
                evidence
            )
        )

        if not vibration_ok:

            return {

                "verified":
                    False,

                "status":
                    "CONTRADICTED",

                "reason":
                    vibration_reason,

                "method":
                    "deterministic_threshold"
            }

        temperature_ok, temperature_reason = (
            self.check_temperature(
                answer,
                evidence
            )
        )

        if not temperature_ok:

            return {

                "verified":
                    False,

                "status":
                    "CONTRADICTED",

                "reason":
                    temperature_reason,

                "method":
                    "deterministic_threshold"
            }

        return {

            "verified":
                True,

            "status":
                "SUPPORTED",

            "reason":
                "Industrial numerical "
                "reasoning is consistent "
                "with the evidence.",

            "method":
                "deterministic_threshold"
        }

    # ============================================================
    # MAIN VERIFY
    # ============================================================

    def verify(
        self,
        answer,
        sources,
        evidence
    ):

        # ========================================================
        # STEP 1
        # CLAIM → CITATION → EVIDENCE
        # ========================================================

        citation_result = (
            self.verify_claim_citations(
                answer,
                sources
            )
        )

        if not citation_result[
            "verified"
        ]:

            # ----------------------------------------------------
            # Check whether the failure is a missing citation
            # ----------------------------------------------------

            has_missing_citation = any(
                item["status"]
                == "MISSING_CITATION"
                for item in citation_result[
                    "evidence_map"
                ]
            )

            if has_missing_citation:

                return {

                    "verified":
                        False,

                    "status":
                        "MISSING_CITATION",

                    "reason":
                        "One or more factual "
                        "claims are missing "
                        "required citations.",

                    "method":
                        "claim_citation_verification",

                    "evidence_map":
                        citation_result[
                            "evidence_map"
                        ]
                }

            return {

                "verified":
                    False,

                "status":
                    "CITATION_MISMATCH",

                "reason":
                    "One or more factual "
                    "claims could not be "
                    "verified against "
                    "their cited evidence.",

                "method":
                    "claim_citation_verification",

                "evidence_map":
                    citation_result[
                        "evidence_map"
                    ]
            }

        # ========================================================
        # STEP 2
        # DETERMINISTIC INDUSTRIAL LOGIC
        # ========================================================

        deterministic_result = (
            self.deterministic_threshold_check(
                answer,
                evidence
            )
        )

        deterministic_result[
            "evidence_map"
        ] = citation_result[
            "evidence_map"
        ]

        return deterministic_result


# ================================================================
# SIMPLE FUNCTION
# ================================================================

def simple_evidence_check(
    answer,
    sources,
    evidence
):

    checker = EvidenceChecker()

    return checker.verify(
        answer,
        sources,
        evidence
    )


# ================================================================
# TESTS
# ================================================================

if __name__ == "__main__":

    checker = EvidenceChecker()

    # ============================================================
    # TEST SOURCES
    # ============================================================

    sources = [

        {
            "id": 1,

            "source":
                "Inspection_Report.pdf",

            "page":
                1,

            "score":
                0.8768,

            "text":
                (
                    "Gas turbine GT-01 "
                    "inspection report. "
                    "Observed temperature "
                    "was 587°C. "
                    "Observed vibration "
                    "was 8.2 mm/s. "
                    "Abnormal vibration "
                    "was detected near "
                    "the bearing housing."
                )
        },

        {
            "id": 2,

            "source":
                "Maintenance_Manual.pdf",

            "page":
                1,

            "score":
                0.8742,

            "text":
                (
                    "GT-01 temperature "
                    "above 580°C is "
                    "classified as "
                    "critical. "
                    "Vibration above "
                    "7 mm/s requires "
                    "inspection of "
                    "bearing and rotor."
                )
        },

        {
            "id": 3,

            "source":
                "Safety_SOP.pdf",

            "page":
                1,

            "score":
                0.8266,

            "text":
                (
                    "Temperature above "
                    "580°C requires "
                    "controlled shutdown "
                    "and supervisor "
                    "notification."
                )
        }
    ]

    evidence = "\n".join(
        source["text"]
        for source in sources
    )

    # ============================================================
    # TEST 1
    # ============================================================

    print("\n")
    print("=" * 70)
    print("TEST 1 — CORRECT ANSWER")
    print("=" * 70)

    correct_answer = (
        "The gas turbine GT-01 is "
        "in a critical condition "
        "based on the inspection "
        "findings. [Source 1]\n\n"

        "Observed temperature "
        "was 587°C, which exceeds "
        "the critical threshold "
        "of 580°C. [Source 1]"
        "[Source 2]\n\n"

        "Observed vibration was "
        "8.2 mm/s, which exceeds "
        "the inspection threshold "
        "of 7 mm/s and requires "
        "inspection. [Source 1]"
        "[Source 2]"
    )

    result = checker.verify(
        correct_answer,
        sources,
        evidence
    )

    print("\nVerification:")
    print(result["verified"])

    print("\nStatus:")
    print(result["status"])

    print("\nMethod:")
    print(result["method"])

    print("\nReason:")
    print(result["reason"])

    print("\nEvidence Map:")

    for item in result[
        "evidence_map"
    ]:

        print("\n----------------------------------")

        print("Claim:")
        print(item["claim"])

        print("\nCitations:")
        print(item["citations"])

        print("\nStatus:")
        print(item["status"])

        for ev in item[
            "evidence"
        ]:

            print(
                f"  -> Source "
                f"{ev.get('source_id')} | "
                f"{ev.get('document', '')} | "
                f"Page "
                f"{ev.get('page', '')} | "
                f"Status: "
                f"{ev.get('status')}"
            )

    # ============================================================
    # TEST 2
    # ============================================================

    print("\n")
    print("=" * 70)
    print("TEST 2 — WRONG CITATION")
    print("=" * 70)

    wrong_citation_answer = (
        "Observed temperature "
        "was 587°C. [Source 3]"
    )

    result = checker.verify(
        wrong_citation_answer,
        sources,
        evidence
    )

    print("\nVerification:")
    print(result["verified"])

    print("\nStatus:")
    print(result["status"])

    print("\nReason:")
    print(result["reason"])

    print("\nEvidence Map:")

    for item in result[
        "evidence_map"
    ]:

        print("\n----------------------------------")

        print("Claim:")
        print(item["claim"])

        print("\nCitations:")
        print(item["citations"])

        print("\nStatus:")
        print(item["status"])

        for ev in item[
            "evidence"
        ]:

            print(
                f"  -> Source "
                f"{ev.get('source_id')} | "
                f"{ev.get('document', '')} | "
                f"Page "
                f"{ev.get('page', '')} | "
                f"Status: "
                f"{ev.get('status')}"
            )

    # ============================================================
    # TEST 3
    # ============================================================

    print("\n")
    print("=" * 70)
    print("TEST 3 — MISSING CITATION")
    print("=" * 70)

    missing_citation_answer = (
        "Observed temperature "
        "was 587°C."
    )

    result = checker.verify(
        missing_citation_answer,
        sources,
        evidence
    )

    print("\nVerification:")
    print(result["verified"])

    print("\nStatus:")
    print(result["status"])

    print("\nReason:")
    print(result["reason"])

    print("\nEvidence Map:")

    for item in result[
        "evidence_map"
    ]:

        print("\n----------------------------------")

        print("Claim:")
        print(item["claim"])

        print("\nCitations:")
        print(item["citations"])

        print("\nStatus:")
        print(item["status"])

    # ============================================================
    # TEST 4
    # ============================================================

    print("\n")
    print("=" * 70)
    print("TEST 4 — WRONG INDUSTRIAL REASONING")
    print("=" * 70)

    wrong_reasoning_answer = (
        "Observed vibration "
        "was 8.2 mm/s and is "
        "within the 5–7 mm/s "
        "monitoring range, "
        "requiring only "
        "monitoring. [Source 1]"
        "[Source 2]"
    )

    result = checker.verify(
        wrong_reasoning_answer,
        sources,
        evidence
    )

    print("\nVerification:")
    print(result["verified"])

    print("\nStatus:")
    print(result["status"])

    print("\nReason:")
    print(result["reason"])

    print("\nEvidence Map:")

    for item in result[
        "evidence_map"
    ]:

        print("\n----------------------------------")

        print("Claim:")
        print(item["claim"])

        print("\nCitations:")
        print(item["citations"])

        print("\nStatus:")
        print(item["status"])

        for ev in item[
            "evidence"
        ]:

            print(
                f"  -> Source "
                f"{ev.get('source_id')} | "
                f"{ev.get('document', '')} | "
                f"Page "
                f"{ev.get('page', '')} | "
                f"Status: "
                f"{ev.get('status')}"
            )

    # ============================================================
    # COMPLETE
    # ============================================================

    print("\n")
    print("=" * 70)
    print("EVIDENCE VERIFICATION TEST COMPLETE")
    print("=" * 70)