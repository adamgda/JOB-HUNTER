from app.search.languages import detect_languages


def test_python_from_title():
    assert detect_languages("Senior Python Developer (Django)") == ["Python"]


def test_javascript_and_typescript():
    assert detect_languages("Frontend Dev — React/TS, js bonus") == [
        "JavaScript",
        "TypeScript",
    ]


def test_golang_only_not_go_word():
    assert detect_languages("Go home now") == []
    assert detect_languages("Golang Backend Engineer") == ["Go"]


def test_cpp_csharp_and_c():
    assert detect_languages("C++ game dev") == ["C++"]
    assert detect_languages("C# .NET developer") == ["C#"]
    assert detect_languages("C embedded") == ["C"]


def test_java_not_javascript():
    assert detect_languages("Java Kotlin mobile") == ["Java", "Kotlin"]
    assert detect_languages("JavaScript engineer") == ["JavaScript"]


def test_multiple_and_case_insensitive():
    assert detect_languages("python + RUST, php? RAILS") == [
        "Python",
        "PHP",
        "Ruby",
        "Rust",
    ]


def test_empty():
    assert detect_languages(None, "") == []


from app.search.textlang import detect_text_lang


def test_polski_przez_diakrytyki():
    assert detect_text_lang("Firma z Warszawy poszukuje engineer — praca, kąty") == "pl"


def test_polski_przez_slowa_ogloszenia():
    assert detect_text_lang("Zatrudnimy do zespołu. Wynagrodzenie 15k. Praca zdalna") == "pl"


def test_angielski_langdetect():
    assert detect_text_lang(
        "Senior DevOps Engineer. We are looking for an experienced candidate who will join our team in Krakow "
        "office. You will work with Kubernetes and maintain CI/CD pipelines. Apply now with your resume."
    ) == "en"


def test_za_krotki_tekst_unknown():
    assert detect_text_lang("DevOps") == "unknown"
    assert detect_text_lang(None) == "unknown"