"""Błędy silników wyszukiwania."""


class SearchEngineError(Exception):
    """Ogólny błąd silnika wyszukiwania."""


class MissingEngineConfigError(SearchEngineError):
    """Brak konfiguracji (kluczy Google) albo zależności (np. pakietu ddgs)."""