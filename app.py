import uuid
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Accompagnement-Lux", page_icon="🎓")

# ---------- Connexion à Supabase (un client par visiteur) ----------
if "client" not in st.session_state:
    st.session_state.client = create_client(
        st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    )
if "user" not in st.session_state:
    st.session_state.user = None

client = st.session_state.client

# ---------- Données du parcours ----------
ETAPES_MASTER = [
    "Rassembler les documents (passeport, diplômes, relevés de notes, certificat de langue B2)",
    "Choisir jusqu'à 3 programmes",
    "Déposer les demandes d'admission (100 € par programme)",
    "Attendre la décision de l'université",
    "Recevoir la lettre d'admission",
    "Faire l'équivalence de diplôme",
    "Demander le visa",
    "S'inscrire à l'université",
]
ETAPES_LICENCE = [
    "Rassembler les documents (passeport, diplômes, relevés de notes, certificat de langue B2)",
    "Faire l'équivalence de diplôme",
    "Choisir jusqu'à 3 programmes",
    "Déposer les demandes d'admission (100 € par programme)",
    "Attendre la décision de l'université",
    "Recevoir la lettre d'admission",
    "Demander le visa",
    "S'inscrire à l'université",
]
TYPES_DOCUMENTS = {
    "passeport": "Passeport",
    "diplome": "Diplôme",
    "releve_notes": "Relevé de notes",
    "certificat_langue": "Certificat de langue (B2)",
    "lettre_admission": "Lettre d'admission",
    "autre": "Autre",
}
STATUTS = {"a_faire": "À faire", "en_cours": "En cours", "terminee": "Terminée"}
NIVEAUX = {"master": "Master", "licence": "Licence"}


# ---------- Connexion / inscription ----------
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


# ---------- Dossiers ----------
def creer_dossier(user_id, niveau):
    res = client.table("dossiers").insert(
        {"candidat_id": user_id, "niveau": niveau}
    ).execute()
    dossier_id = res.data[0]["id"]
    modele = ETAPES_MASTER if niveau == "master" else ETAPES_LICENCE
    lignes = [
        {"dossier_id": dossier_id, "ordre": i + 1, "titre": titre}
        for i, titre in enumerate(modele)
    ]
    client.table("etapes").insert(lignes).execute()


def maj_statut(etape_id, cle):
    client.table("etapes").update({"statut": st.session_state[cle]}).eq(
        "id", etape_id
    ).execute()


def supprimer_document(doc):
    # La base décide qui a le droit de supprimer : si ce n'est pas autorisé,
    # aucune ligne n'est supprimée et le fichier n'est pas touché
    res = client.table("documents").delete().eq("id", doc["id"]).execute()
    if res.data:
        client.storage.from_("documents").remove([doc["chemin_storage"]])
        return True
    st.error("Suppression non autorisée.")
    return False


def masquer_document(doc):
    client.table("documents_masques").insert({"document_id": doc["id"]}).execute()


def afficher_dossier(dossier_id, prefixe, candidat_id):
    moi = st.session_state.user.id
    proprietaire = moi == candidat_id

    # --- Étapes ---
    st.subheader("Étapes du parcours")
    etapes = (
        client.table("etapes")
        .select("*")
        .eq("dossier_id", dossier_id)
        .order("ordre")
        .execute()
        .data
    )
    for e in etapes:
        col1, col2 = st.columns([3, 1])
        col1.write(f"**{e['ordre']}.** {e['titre']}")
        cle = f"{prefixe}_statut_{e['id']}"
        col2.selectbox(
            "Statut",
            list(STATUTS),
            index=list(STATUTS).index(e["statut"]),
            format_func=lambda s: STATUTS[s],
            key=cle,
            label_visibility="collapsed",
            on_change=maj_statut,
            args=(e["id"], cle),
        )

    # --- Documents ---
    st.subheader("Documents")
    type_doc = st.selectbox(
        "Type de document",
        list(TYPES_DOCUMENTS),
        format_func=lambda t: TYPES_DOCUMENTS[t],
        key=f"{prefixe}_type_{dossier_id}",
    )
    fichier = st.file_uploader(
        "Choisis un fichier (PDF, JPG ou PNG)",
        type=["pdf", "jpg", "jpeg", "png"],
        key=f"{prefixe}_fichier_{dossier_id}",
    )
    if fichier and st.button("Envoyer le document", key=f"{prefixe}_envoi_{dossier_id}"):
        extension = fichier.name.rsplit(".", 1)[-1].lower()
        chemin = f"{dossier_id}/{uuid.uuid4()}.{extension}"
        try:
            client.storage.from_("documents").upload(
                chemin, fichier.getvalue(), {"content-type": fichier.type}
            )
            client.table("documents").insert(
                {
                    "dossier_id": dossier_id,
                    "type": type_doc,
                    "nom_fichier": fichier.name,
                    "chemin_storage": chemin,
                }
            ).execute()
            st.rerun()
        except Exception as e:
            st.error(f"Envoi impossible : {e}")

    documents = (
        client.table("documents")
        .select("*")
        .eq("dossier_id", dossier_id)
        .order("created_at")
        .execute()
        .data
    )
    # Les documents que j'ai retirés de ma liste (visible par moi seulement)
    masques = {
        m["document_id"]
        for m in client.table("documents_masques").select("document_id").execute().data
    }
    if not proprietaire:
        documents = [d for d in documents if d["id"] not in masques]

    if not documents:
        st.info("Aucun document pour le moment.")
    for d in documents:
        col1, col2, col3 = st.columns([3, 1, 1.4])
        col1.write(f"**{TYPES_DOCUMENTS.get(d['type'], d['type'])}** : {d['nom_fichier']}")
        try:
            res = client.storage.from_("documents").create_signed_url(
                d["chemin_storage"], 300
            )
            lien = res.get("signedURL") or res.get("signedUrl")
            if lien:
                col2.link_button("Ouvrir", lien)
        except Exception:
            col2.write("—")

        peut_supprimer = proprietaire or d.get("depose_par") == moi
        if peut_supprimer:
            if col3.button("Supprimer", key=f"{prefixe}_suppr_{d['id']}"):
                if supprimer_document(d):
                    st.rerun()
        else:
            if col3.button("Retirer de ma liste", key=f"{prefixe}_masquer_{d['id']}"):
                masquer_document(d)
                st.rerun()


def vue_candidat(user):
    dossiers = (
        client.table("dossiers").select("*").eq("candidat_id", user.id).execute().data
    )
    if not dossiers:
        st.subheader("Ouvre ton dossier")
        niveau = st.radio(
            "Quel niveau d'études vises-tu ?",
            list(NIVEAUX),
            format_func=lambda n: NIVEAUX[n],
        )
        if st.button("Créer mon dossier"):
            try:
                creer_dossier(user.id, niveau)
                st.rerun()
            except Exception as e:
                st.error(f"Création impossible : {e}")
        return

    dossier = dossiers[0]
    st.write(f"Dossier : **{NIVEAUX[dossier['niveau']]}**")

    # --- Mon accompagnateur ---
    st.subheader("Mon accompagnateur")
    if dossier["accompagnateur_id"]:
        st.success("Un accompagnateur a accès à ton dossier.")
        if st.button("Retirer l'accès à mon accompagnateur", key="retirer_acc"):
            client.rpc("retirer_accompagnateur").execute()
            st.rerun()
    else:
        code = st.text_input("Code de ton accompagnateur", key="code_acc")
        if st.button("Me rattacher à mon accompagnateur", key="rattacher_acc"):
            try:
                res = client.rpc("rattacher_accompagnateur", {"p_code": code}).execute()
                if res.data:
                    st.rerun()
                else:
                    st.error("Code inconnu. Vérifie-le auprès de ton accompagnateur.")
            except Exception as e:
                st.error(f"Rattachement impossible : {e}")

    afficher_dossier(dossier["id"], "candidat", dossier["candidat_id"])


def vue_accompagnateur(code=None):
    if code:
        st.write("Ton code personnel, à donner à tes candidats :")
        st.code(code, language=None)

    dossiers = client.table("dossiers").select("*").execute().data
    if not dossiers:
        st.info("Aucun dossier pour le moment.")
        return

    profils = client.table("profiles").select("id, email").execute().data
    emails = {p["id"]: p["email"] for p in profils}

    # Progression de chaque dossier (étapes terminées / total)
    etapes = client.table("etapes").select("dossier_id, statut").execute().data
    total, faites = {}, {}
    for e in etapes:
        total[e["dossier_id"]] = total.get(e["dossier_id"], 0) + 1
        if e["statut"] == "terminee":
            faites[e["dossier_id"]] = faites.get(e["dossier_id"], 0) + 1

    par_id = {d["id"]: d for d in dossiers}
    options = {
        d["id"]: (
            f"{emails.get(d['candidat_id'], 'Candidat')} : {NIVEAUX[d['niveau']]}"
            f" · {faites.get(d['id'], 0)}/{total.get(d['id'], 0)} étapes terminées"
        )
        for d in dossiers
    }
    choix = st.selectbox("Dossier", list(options), format_func=lambda i: options[i])
    afficher_dossier(choix, "staff", par_id[choix]["candidat_id"])


# ---------- Page principale ----------
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
    profil = client.table("profiles").select("*").eq("id", user.id).execute().data
    role = profil[0]["role"] if profil else "inconnu"
    code_perso = profil[0].get("code_accompagnateur") if profil else None

    st.caption(f"Connectée : {user.email} · rôle : {role}")
    st.button("Se déconnecter", on_click=se_deconnecter)

    if role == "candidat":
        vue_candidat(user)
    elif role == "accompagnateur":
        vue_accompagnateur(code_perso)
    elif role == "admin":
        onglet1, onglet2 = st.tabs(["Mon dossier (test)", "Tous les dossiers"])
        with onglet1:
            vue_candidat(user)
        with onglet2:
            vue_accompagnateur()
