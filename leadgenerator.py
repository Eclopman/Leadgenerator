import streamlit as st
import requests
import pandas as pd
import time
import threading
import random
from googletrans import Translator

# ---- AUTHENTIFICATION ----
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

st.sidebar.title("🔒 Connexion")

if not st.session_state.authenticated:
    if "USERNAME" not in st.secrets or "PASSWORD" not in st.secrets:
        st.sidebar.error("⚠ Erreur : Identifiants non configurés dans Streamlit Secrets.")
        st.stop()

    user_input = st.sidebar.text_input("Identifiant", value="", type="default")
    password_input = st.sidebar.text_input("Mot de passe", value="", type="password")

    if st.sidebar.button("Se connecter"):
        if user_input == st.secrets["USERNAME"] and password_input == st.secrets["PASSWORD"]:
            st.session_state.authenticated = True
            st.sidebar.success("✅ Connexion réussie !")
            st.rerun()
        else:
            st.sidebar.error("❌ Identifiant ou mot de passe incorrect.")

    st.stop()

# ---- CONFIGURATION ----
st.title("Lead Generator 📍")
st.write("Trouvez des entreprises autour d’un point GPS.")

if "API_KEY" not in st.secrets:
    st.error("⚠ Erreur : Clé API manquante. Configure-la dans Streamlit Secrets.")
    st.stop()

API_KEY = st.secrets["API_KEY"]
BASE_URL_NEARBY = "https://places.googleapis.com/v1/places:searchNearby"
BASE_URL_TEXT = "https://places.googleapis.com/v1/places:searchText"
translator = Translator()

# Champs de saisie
type_place_fr = st.text_input("Que recherches-tu ? (ex: restaurant, hôtel, cinéma, etc.)")
latitude = st.number_input("Entrez la latitude du point GPS :", format="%.6f")
longitude = st.number_input("Entrez la longitude du point GPS :", format="%.6f")
radius = st.slider("Rayon de recherche (mètres)", min_value=100, max_value=5000, value=1000)
filter_contact = st.checkbox("Seulement avec téléphone ou site web")

if st.button("Lancer la recherche"):
    type_place_en = translator.translate(type_place_fr, src='fr', dest='en').text.lower()
    st.write(f"🔍 Recherche pour : {type_place_en}")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.nationalPhoneNumber,places.websiteUri"
    }

    def get_places(lat, lon, radius, results, seen_places, search_type):
        """ Effectue une requête Nearby ou Text Search et récupère les résultats sans doublon. """
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
                return

            for place in data.get("places", []):
                name = place.get("displayName", {}).get("text", "N/A")
                address = place.get("formattedAddress", "N/A")  # On utilise l'adresse pour éviter les doublons
                lat = place.get("location", {}).get("latitude", "N/A")
                lon = place.get("location", {}).get("longitude", "N/A")
                phone = place.get("nationalPhoneNumber", "N/A")
                website = place.get("websiteUri", "N/A")

                if filter_contact and phone == "N/A" and website == "N/A":
                    continue

                place_identifier = (name, address)  # Identifiant unique basé sur le nom et l'adresse

                if place_identifier not in seen_places:
                    seen_places.add(place_identifier)
                    results.append([name, address, phone, website, lat, lon])

            time.sleep(0.2)
        except Exception as e:
            st.error(f"Erreur API ({search_type}): {e}")

    # Lancer la recherche
    places = []
    seen_places = set()  # Set pour stocker les lieux déjà ajoutés
    step = radius / 12  
    offset_lat = step / 111320
    offset_lon = step / (40075000 * abs(latitude) / 360)

    grid_points = [(latitude + (i * offset_lat + random.uniform(-0.0001, 0.0001)),
                    longitude + (j * offset_lon + random.uniform(-0.0001, 0.0001)))
                   for i in range(-6, 7) for j in range(-6, 7)]

    threads = []

    for lat, lon in grid_points:
        t = threading.Thread(target=get_places, args=(lat, lon, step, places, seen_places, "nearby"))
        t.start()
        threads.append(t)

    for lat, lon in grid_points:
        t = threading.Thread(target=get_places, args=(lat, lon, step, places, seen_places, "text"))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    if places:
        df = pd.DataFrame(places, columns=["Nom", "Adresse", "Téléphone", "Site Web", "Latitude", "Longitude"])
        st.write(df)

        # Générer un fichier Excel
        excel_filename = "google_places_results.xlsx"
        df.to_excel(excel_filename, index=False)

        with open(excel_filename, "rb") as f:
            st.download_button(label="📥 Télécharger les résultats", data=f, file_name=excel_filename)

    else:
        st.warning("⚠ Aucune donnée trouvée. Vérifie tes paramètres ou ton quota API.")
