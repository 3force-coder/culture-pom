# utils/geocoding.py
"""
Module utilitaire de géocodage pour POMI.

Utilise l'API officielle française (Géoplateforme / BAN) :
- Gratuite, sans clé API
- Limite : 50 req/s/IP
- Nouvelle URL : data.geopf.fr/geocodage (l'ancienne api-adresse.data.gouv.fr a
  été décommissionnée en janvier 2026)

Documentation officielle :
- https://geoservices.ign.fr/documentation/services/services-geoplateforme/geocodage
- https://cartes.gouv.fr/aide/fr/guides-utilisateur/utiliser-les-services-de-la-geoplateforme/geocodage/

Fonctions exposées :
- search_adresse(query, limit=5) : recherche / autocomplétion
- geocode_adresse(adresse) : adresse texte -> lat/lng
- reverse_geocode(lat, lng) : lat/lng -> adresse
"""
import requests

# URLs officielles Géoplateforme (post-migration janvier 2026)
GEOCODE_SEARCH_URL = "https://data.geopf.fr/geocodage/search"
GEOCODE_REVERSE_URL = "https://data.geopf.fr/geocodage/reverse"

# Timeout standard pour ne pas bloquer l'UI Streamlit
DEFAULT_TIMEOUT = 5


def _parse_feature(feature):
    """Convertit une feature GeoJSON renvoyée par l'API en dict normalisé.

    Format de retour identique pour search_adresse, geocode_adresse, reverse_geocode :
        {
            'label': str,        # libellé complet
            'name': str,         # rue / numéro
            'postcode': str,
            'city': str,
            'departement': str,  # 2 premiers chiffres du CP (ou '' si absent)
            'latitude': float ou None,
            'longitude': float ou None,
        }
    """
    if not feature:
        return None
    props = feature.get('properties', {}) or {}
    coords = (feature.get('geometry') or {}).get('coordinates') or [None, None]
    postcode = props.get('postcode') or ''
    return {
        'label': props.get('label', '') or '',
        'name': props.get('name', '') or '',
        'postcode': postcode,
        'city': props.get('city', '') or '',
        'departement': postcode[:2] if postcode else '',
        'latitude': float(coords[1]) if coords and coords[1] is not None else None,
        'longitude': float(coords[0]) if coords and coords[0] is not None else None,
    }


def search_adresse(query, limit=5):
    """Recherche une adresse (autocomplétion).

    Args:
        query: chaîne de recherche (min 3 caractères)
        limit: nombre max de résultats (1-10)

    Returns:
        list[dict] : liste de résultats normalisés (vide si pas trouvé ou erreur)
    """
    if not query or len(str(query).strip()) < 3:
        return []
    try:
        response = requests.get(
            GEOCODE_SEARCH_URL,
            params={
                "q": str(query).strip(),
                "limit": int(limit),
                "autocomplete": 1,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code != 200:
            return []
        data = response.json()
        results = []
        for feature in data.get('features', []) or []:
            parsed = _parse_feature(feature)
            if parsed:
                results.append(parsed)
        return results
    except requests.RequestException:
        return []
    except (ValueError, KeyError):
        return []


def geocode_adresse(adresse_complete):
    """Géocode une adresse complète (texte) -> coordonnées.

    Args:
        adresse_complete: adresse texte (ex: "10 rue de la Paix 51200 Épernay")

    Returns:
        dict normalisé ou None si pas trouvé / erreur.
    """
    if not adresse_complete or len(str(adresse_complete).strip()) < 3:
        return None
    try:
        response = requests.get(
            GEOCODE_SEARCH_URL,
            params={"q": str(adresse_complete).strip(), "limit": 1},
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        features = data.get('features') or []
        if not features:
            return None
        return _parse_feature(features[0])
    except requests.RequestException:
        return None
    except (ValueError, KeyError):
        return None


def reverse_geocode(latitude, longitude):
    """Géocodage inverse : coordonnées -> adresse.

    Args:
        latitude, longitude: coordonnées géographiques (float)

    Returns:
        dict normalisé ou None si pas trouvé / erreur.
    """
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return None
    try:
        response = requests.get(
            GEOCODE_REVERSE_URL,
            params={"lat": lat, "lon": lng, "limit": 1},
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        features = data.get('features') or []
        if not features:
            return None
        return _parse_feature(features[0])
    except requests.RequestException:
        return None
    except (ValueError, KeyError):
        return None
