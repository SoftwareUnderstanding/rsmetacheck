"""Family-aware P002 tests.

GPL/LGPL/AGPL/Apache/MPL/EPL/CDDL ship an appendix of instructions whose
placeholder tokens are part of the licence; those must never be reported.
Permissive licences (MIT/MIT-0/BSD/0BSD/ISC/X11/zlib/Unlicense) are checked in
the copyright header only.
"""
import pytest

from rsmetacheck.scripts.pitfalls import p002

GPL3 = """GNU GENERAL PUBLIC LICENSE
Version 3, 29 June 2007

Copyright (C) 2007 Free Software Foundation, Inc.

Everyone is permitted to copy and distribute verbatim copies of this license
document, but changing it is not allowed.

END OF TERMS AND CONDITIONS

How to Apply These Terms to Your New Programs

  <one line to give the program's name and a brief idea of what it does.>
  Copyright (C) <year>  <name of author>

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License.
"""

APACHE2 = """Apache License
Version 2.0, January 2004

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

APPENDIX: How to apply the Apache License to your work.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0.
"""

MIT_TEMPLATE = """MIT License

Copyright (c) <year> <copyright holders>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software").
"""

MIT_FILLED = """MIT License

Copyright (c) 2026 Jane Doe

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software").
"""

BSD3_TEMPLATE = """BSD 3-Clause License

Copyright (c) <year>, <copyright holder>
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
"""

ISC_TEMPLATE = """ISC License

Copyright (c) 4-digit year, Company or Person's Name

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.
"""

ZERO_BSD_TEMPLATE = """Zero-Clause BSD

Copyright (C) YEAR by AUTHOR EMAIL

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted.
"""

X11_TEMPLATE = """X11 License

Copyright (C) <year> X Consortium

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software").

Except as contained in this notice, the name of the X Consortium shall not be
used in advertising.
"""

ZLIB_TEMPLATE = """zlib License

Copyright (C) <year> Jean-loup Gailly and Mark Adler

This software is provided 'as-is', without any express or implied warranty.

The origin of this software must not be misrepresented.
"""


@pytest.mark.parametrize("content,family", [
    (GPL3, "gpl"),
    (APACHE2, "apache"),
    (MIT_TEMPLATE, "mit"),
    (BSD3_TEMPLATE, "bsd"),
    (ISC_TEMPLATE, "isc"),
    (X11_TEMPLATE, "x11"),
    (ZLIB_TEMPLATE, "zlib"),
    ("This is free and unencumbered software released into the public domain.", "unlicense"),
    ("Some bespoke terms.\nCopyright 2026 ACME.", ""),
])
def test_family_detection(content, family):
    assert p002.detect_license_family(content) == family


def test_agpl_and_lgpl_are_detected_before_gpl():
    assert p002.detect_license_family(
        "GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3") == "agpl"
    assert p002.detect_license_family(
        "GNU LESSER GENERAL PUBLIC LICENSE\nVersion 3") == "lgpl"


@pytest.mark.parametrize("content", [GPL3, APACHE2])
def test_appendix_families_never_flagged(content):
    """The 34-false-positive class: GPL/Apache appendix boilerplate."""
    analysis = p002.analyze_license_placeholders(content)
    assert analysis["has_pitfall"] is False
    assert analysis["decision"] == "exempt_appendix_family"
    assert analysis["placeholders"] == []


@pytest.mark.parametrize("content,token_hint", [
    (MIT_TEMPLATE, "<year>"),
    (BSD3_TEMPLATE, "<year>"),
    (ISC_TEMPLATE, "4-digit year"),
    (ZERO_BSD_TEMPLATE, "YEAR"),
    (X11_TEMPLATE, "<year>"),
    (ZLIB_TEMPLATE, "<year>"),
])
def test_permissive_templates_are_flagged(content, token_hint):
    analysis = p002.analyze_license_placeholders(content)
    assert analysis["has_pitfall"] is True, analysis
    assert analysis["decision"] == "placeholder_in_copyright_header"
    assert any(token_hint.lower() in token.lower() for token in analysis["placeholders"]), analysis


def test_filled_mit_is_clean():
    analysis = p002.analyze_license_placeholders(MIT_FILLED)
    assert analysis["has_pitfall"] is False
    assert analysis["decision"] == "clean"


def test_zero_bsd_is_not_reported_as_isc():
    assert p002.detect_license_family(ZERO_BSD_TEMPLATE) == "0bsd"
    assert p002.detect_license_family(ISC_TEMPLATE) == "isc"


def test_placeholder_in_licence_body_is_ignored():
    """Unknown licence, token appears only after the body grant starts."""
    content = """Custom Licence

Copyright 2026 ACME

The Software is provided as is, and you may use <year> freely.
"""
    analysis = p002.analyze_license_placeholders(content)
    assert analysis["has_pitfall"] is False


def test_unknown_licence_placeholder_in_header_is_flagged():
    content = """Custom Licence

Copyright (c) <year> <owner>
All rights reserved.
"""
    assert p002.analyze_license_placeholders(content)["has_pitfall"] is True


def test_empty_content_is_clean():
    assert p002.analyze_license_placeholders("")["has_pitfall"] is False
    assert p002.check_license_template_placeholders(None) is False


def _somef(license_text, source="https://example.org/repo/LICENSE"):
    return {"license": [{
        "source": source,
        "technique": "file_exploration",
        "result": {"value": license_text, "type": "File_dump"},
    }]}


def test_detector_exempts_gpl(monkeypatch):
    monkeypatch.setattr(p002, "fetch_text", lambda url, **kw: None)
    result = p002.detect_license_template_placeholders(_somef(GPL3), "test.json")
    assert result["has_pitfall"] is False
    assert result["license_family"] == "gpl"
    assert result["decision"] == "exempt_appendix_family"


def test_detector_flags_mit_template(monkeypatch):
    monkeypatch.setattr(p002, "fetch_text", lambda url, **kw: None)
    result = p002.detect_license_template_placeholders(_somef(MIT_TEMPLATE), "test.json")
    assert result["has_pitfall"] is True
    assert result["license_family"] == "mit"
    assert result["placeholders_found"] is True
    assert "<year>" in result["placeholders"]


def test_detector_result_structure(monkeypatch):
    monkeypatch.setattr(p002, "fetch_text", lambda url, **kw: None)
    result = p002.detect_license_template_placeholders(_somef(MIT_FILLED), "test.json")
    for key in ("has_pitfall", "file_name", "license_source", "placeholders_found",
                "license_family", "placeholders", "decision"):
        assert key in result
