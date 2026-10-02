from jobbot.domain.text import canonical_url, contains_term, job_id_for, normalize_key, strip_html


def test_strip_html_handles_tags_entities_and_double_escaping():
    assert strip_html("<p>Hello&nbsp;<b>world</b></p><ul><li>A</li></ul>") == "Hello world A"
    assert strip_html("&lt;p&gt;Ruby and Go&lt;/p&gt;") == "Ruby and Go"
    assert strip_html("") == ""


def test_canonical_url_drops_tracking_and_trailing_slash():
    a = canonical_url("https://Example.com/jobs/1/?utm_source=x&ref=y&id=5#apply")
    assert a == "https://example.com/jobs/1?id=5"
    assert job_id_for("https://example.com/jobs/1?id=5&utm_medium=z") == job_id_for(a)


def test_normalize_key_ignores_case_punctuation_and_company_suffixes():
    assert normalize_key("Acme Ltd.") == normalize_key("ACME")
    assert normalize_key("Senior Engineer (Remote)") == "senior engineer"


def test_contains_term_whole_word_and_symbols():
    text = "we use c++, c# and node.js; also golang"
    assert contains_term(text, "C++")
    assert contains_term(text, "C#")
    assert contains_term(text, "Node.js")
    assert contains_term(text, "Go") is False  # 'golang' is not 'go'
    assert contains_term("python developer", "PHP") is False
