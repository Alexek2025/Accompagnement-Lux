import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Accompagnement-Lux", page_icon="🎓")

# Un client Supabase par visiteur (jamais partagé entre utilisateurs)
if "client" not in st.session_state:
    st.session_state.client = create_client(
        st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    )
if "user" not in st.session_state:
    st.session_state.user = None

client = st.session_state.client


def se_connecter(email, mot_de_passe):
    try:
        res = client.auth.sign_in_with_password(
            {"email": email, "password": mot_de_passe}
        )
        st.session_state.user = res.user
        st.rerun()
    except Exception:
        st.error("Connexion impossible : vérifie ton email et ton mot de passe.")


def creer_compte(email, mot_de_passe):
    try:
        client.auth.sign_up({"email": email, "password": mot_de_passe})
        st.success(
            "Compte créé. Regarde ta boîte mail et clique sur le lien de confirmation, "
            "puis reviens te connecter."
        )
    except Exception as e:
        st.error(f"Création impossible : {e}")


def se_deconnecter():
    client.auth.sign_out()
    st.session_state.user = None
    st.rerun()


st.title("🎓 Accompagnement-Lux")

if st.session_state.user is None:
    onglet_connexion, onglet_inscription = st.tabs(["Se connecter", "Créer un compte"])

    with onglet_connexion:
        email = st.text_input("Email", key="email_connexion")
        mdp = st.text_input("Mot de passe", type="password", key="mdp_connexion")
        if st.button("Se connecter"):
            se_connecter(email, mdp)

    with onglet_inscription:
        email2 = st.text_input("Email", key="email_inscription")
        mdp2 = st.text_input(
            "Mot de passe (8 caractères minimum)", type="password", key="mdp_inscription"
        )
        if st.button("Créer mon compte"):
            creer_compte(email2, mdp2)
else:
    user = st.session_state.user
    profil = (
        client.table("profiles").select("*").eq("id", user.id).execute().data
    )
    role = profil[0]["role"] if profil else "inconnu"

    st.success(f"Connectée : {user.email}")
    st.write(f"Ton rôle : **{role}**")
    st.button("Se déconnecter", on_click=se_deconnecter)
