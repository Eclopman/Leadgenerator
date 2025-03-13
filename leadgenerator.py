import requests
import pandas as pd
import time
import threading
import random
from googletrans import Translator


# ---- CONFIGURATION ----
API_KEY = "AIzaSyDPsW5m2k9nrY-uKFGGtrVrxxNc_AuOjEQ"  # Remplace par ta clé Google Places API
BASE_URL_NEARBY = "https://places.googleapis.com/v1/places:searchNearby"
BASE_URL_TEXT = "https://places.googleapis.com/v1/places:searchText"
translator = Translator()


# ---- DEMANDER LES PARAMÈTRES À L'UTILISATEUR ----
type_place_fr = input("Que recherches-tu ? (ex: restaurant, hôtel, cinéma, station-service, décoration d'intérieur) : ")
latitude = float(input("Entrez la latitude du point GPS : "))
longitude = float(input("Entrez la longitude du point GPS : "))
radius = int(input("Entrez le rayon de recherche en mètres : "))
filter_contact = input("Veux-tu seulement les établissements avec un numéro de téléphone ou un site web ? (oui/non) : ").strip().lower()


# 🌍 Traduction automatique
type_place_en = translator.translate(type_place_fr, src='fr', dest='en').text.lower()
print(f"🔍 Recherche pour : {type_place_en} (traduction de '{type_place_fr}')")


# ---- CONFIGURATION DE LA REQUÊTE ----
headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.nationalPhoneNumber,places.websiteUri"
}


# ---- FONCTION DE RÉCUPÉRATION DES DONNÉES ----
def get_places(lat, lon, radius, results, search_type):
    """ Effectue une requête Nearby ou Text Search et récupère les résultats. """
    payload = {"maxResultCount": 20}

    if search_type == "nearby":
        payload["locationRestriction"] = {
            "circle": {"center": {"latitude": lat, "longitude": lon}, "radius": radius}
        }
        payload["includedTypes"] = [type_place_en]
        url = BASE_URL_NEARBY
    else:
        payload["textQuery"] = f"{type_place_en} near {lat},{lon}"
        url = BASE_URL_TEXT


    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()


        if "places" not in data:
            print(f"⚠ Erreur API ({search_type}):", data)
            return


        for place in data.get("places", []):
            name = place.get("displayName", {}).get("text", "N/A")
            lat = place.get("location", {}).get("latitude", "N/A")
            lon = place.get("location", {}).get("longitude", "N/A")
            phone = place.get("nationalPhoneNumber", "N/A")
            website = place.get("websiteUri", "N/A")


            if filter_contact == "oui" and phone == "N/A" and website == "N/A":
                continue


            results.add((name, phone, website, lat, lon))


        time.sleep(0.2)  # Optimisation du délai
    except Exception as e:
        print(f"⚠ Exception lors de la requête {search_type} : {e}")


# ---- DÉCOUPAGE EN SOUS-ZONES ----
places = set()
step = radius / 12  # Plus de sous-zones pour maximiser les résultats


offset_lat = step / 111320
offset_lon = step / (40075000 * abs(latitude) / 360)


grid_points = [(latitude + (i * offset_lat + random.uniform(-0.0001, 0.0001)),
                longitude + (j * offset_lon + random.uniform(-0.0001, 0.0001)))
                for i in range(-6, 7) for j in range(-6, 7)]


threads = []


# 🟢 Lancer Nearby Search sur toutes les zones
for lat, lon in grid_points:
    t = threading.Thread(target=get_places, args=(lat, lon, step, places, "nearby"))
    t.start()
    threads.append(t)


# 🟢 Lancer Text Search sur toutes les zones
for lat, lon in grid_points:
    t = threading.Thread(target=get_places, args=(lat, lon, step, places, "text"))
    t.start()
    threads.append(t)


# Attendre la fin de toutes les requêtes
for t in threads:
    t.join()


# ---- SAUVEGARDE DANS UN FICHIER EXCEL ----
if places:
    df = pd.DataFrame(list(places), columns=["Nom", "Téléphone", "Site Web", "Latitude", "Longitude"])
    excel_filename = "google_places_results.xlsx"
    df.to_excel(excel_filename, index=False)
    print(f"✅ Scraping terminé. {len(places)} établissements trouvés. Fichier Excel généré : {excel_filename}")
else:
    print("⚠ Aucune donnée trouvée. Vérifie tes paramètres ou ton quota API.")