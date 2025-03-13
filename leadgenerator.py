import requests
import pandas as pd
import time
import threading
import random
import streamlit as st
from googletrans import Translator

# ---- CONFIGURATION ----
API_KEY = "TA_CLE_GOOGLE_PLACES"  # Remplace par ta clé Google Places API
BASE_URL_NEARBY = "https://places.googleapis.com/v1/places:searchNearby"
BASE_URL_TEXT = "https://places.googleapis.com/v1/places:searchText"
translator = Translator()

# ---- INTERFACE STREAMLIT ----
st.title("🔍 Google Maps Lead Generator")

# 📌 Saisie des paramètres utilisateur
type_place_fr = st.text_input("Que recherches-tu ?", "restaurant")
latitude = st.number_input("Latitude du point GPS", value=48.8566)
longitude = st.number_input("Longitude du point GPS", value=2.3522)
radius = st.slider("Rayon de recherche (mètres)", min_value=100, max_value=50000, value=5000)
filter_contact = st.checkbox("Seulement les établissements avec téléphone/site web ?")

# Bouton pour démarrer la recherche
if st.button("🚀 Lancer la recherche"):

    # 🌍 Traduction automatique du type d'établissement
    type_place_en = translator.translate(type_place_fr, src='fr', dest='en').text.lower()
    st.write(f"🔎 Recherche pour **{type_place_en}** (traduction de '{type_place_fr}')")

    # ---- CONFIGURATION DE LA REQUÊTE ----
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.nationalPhoneNumber,places.websiteUri"
    }

    # ---- FONCTION DE SCRAPING ----
    def get_places(lat, lon, radius, results, search_type):
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
                st.warning(f"⚠ Erreur API ({search_type}): {data}")
                return

            for place in data.get("places", []):
                name = place.get("displayName", {}).get("text", "N/A")
                lat = place.get("location", {}).get("latitude", "N/A")
                lon = place.get("location", {}).get("longitude", "N/A")
                phone = place.get("nationalPhoneNumber", "N/A")
                website = place.get("websiteUri", "N/A")

                if filter_contact and phone == "N/A" and website == "N/A":
                    continue

                results.append((name, phone, website, lat, lon))

            time.sleep(0.2)
        except Exception as e:
            st.error(f"⚠ Exception lors de la requête {search_type} : {e}")

    # ---- DÉCOUPAGE EN SOUS-ZONES ----
    places = []
    step = radius / 12
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

    # ---- AFFICHAGE DES RÉSULTATS ----
    if places:
        df = pd.DataFrame(places, columns=["Nom", "Téléphone", "Site Web", "Latitude", "Longitude"])
        st.write(f"✅ **{len(places)} établissements trouvés !**")

        # Affichage des résultats sous forme de tableau interactif
        st.dataframe(df)

        # ---- TÉLÉCHARGEMENT ----
        excel_filename = "google_places_results.xlsx"
        df.to_excel(excel_filename, index=False)
        
        with open(excel_filename, "rb") as file:
            st.download_button("📥 Télécharger le fichier Excel", file, file_name=excel_filename)
    else:
        st.warning("⚠ Aucune donnée trouvée. Vérifie tes paramètres ou ton quota API.")
