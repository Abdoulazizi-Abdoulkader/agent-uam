"""
Chargement et indexation des documents pour la base de connaissances
"""
import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langsmith import traceable
from app_config import LLMProvider
from app_config import get_config
from llm_utils import initialize_embeddings
from logger_config import get_logger

# Logger pour ce module
logger = get_logger(__name__)


def _generate_structure_documents() -> List[Document]:
    """
    Convertit UAM_STRUCTURES en Documents LangChain pour enrichir l'index FAISS.
    Chaque structure (faculté, institut, école) génère un document texte dense
    couvrant nom, missions, formations, débouchés, départements, etc.
    """
    try:
        from uam_structures import UAM_STRUCTURES
    except ImportError:
        logger.warning("uam_structures non disponible — structures non indexées")
        return []

    docs: List[Document] = []

    category_labels = {
        "facultes": "Faculté",
        "instituts": "Institut",
        "ecoles": "École",
    }

    for category, structures in UAM_STRUCTURES.items():
        label = category_labels.get(category, "Structure")
        for abbrev, info in structures.items():
            lines = [
                f"{label} UAM - {info.get('nom_complet', abbrev)} ({abbrev})",
            ]

            if info.get("localisation"):
                lines.append(f"Localisation : {info['localisation']}")

            if info.get("missions"):
                lines.append(f"Missions : {info['missions']}")

            if info.get("historique"):
                lines.append(f"Historique : {info['historique']}")

            effectifs = info.get("effectifs", {})
            if effectifs:
                parts = []
                if effectifs.get("etudiants"):
                    parts.append(f"étudiants : {effectifs['etudiants']}")
                if effectifs.get("enseignants_chercheurs"):
                    parts.append(f"enseignants-chercheurs : {effectifs['enseignants_chercheurs']}")
                if parts:
                    lines.append("Effectifs : " + ", ".join(parts))

            departements = info.get("departements", [])
            if departements:
                lines.append("Départements : " + ", ".join(departements))

            formations = info.get("formations", [])
            if formations:
                lines.append("Formations proposées : " + " | ".join(formations))

            debouches = info.get("debouches", [])
            if debouches:
                lines.append("Débouchés : " + ", ".join(debouches))

            if info.get("conditions_acces"):
                lines.append(f"Conditions d'accès : {info['conditions_acces']}")

            partenariats = info.get("partenariats", info.get("partenaires", []))
            if partenariats:
                lines.append("Partenariats : " + ", ".join(partenariats))

            activites = info.get("activites", [])
            if activites:
                lines.append("Activités : " + " | ".join(activites))

            # Variantes pour améliorer le recall lors de la recherche
            variantes = info.get("variantes", [])
            if variantes:
                lines.append("Noms alternatifs : " + ", ".join(variantes))

            # Remplacer les caractères typographiques non-ASCII des valeurs source
            text = "\n".join(lines).replace("—", "-").replace("–", "-").replace("«", '"').replace("»", '"').replace("…", "...")
            docs.append(Document(
                page_content=text,
                metadata={"source": f"uam_structures/{abbrev}", "type": category, "abbrev": abbrev},
            ))

    logger.info(f"Structures UAM converties en {len(docs)} document(s) pour l'index FAISS")
    return docs


def _collect_source_files(pdf_directory: str) -> List[Path]:
    """Collecte les fichiers sources pris en compte pour le RAG."""
    base = Path(pdf_directory)
    extensions = {".pdf", ".txt", ".md", ".docx"}
    files: List[Path] = []
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions:
            files.append(path)
    return sorted(files)


def _compute_files_fingerprint(files: List[Path], base_dir: str) -> Tuple[str, int]:
    """Calcule un fingerprint des fichiers pour invalider l'index si besoin."""
    base = Path(base_dir)
    entries = []
    for path in files:
        stat = path.stat()
        entries.append({
            "path": str(path.relative_to(base)),
            "mtime": int(stat.st_mtime),
            "size": stat.st_size
        })
    payload = json.dumps(entries, sort_keys=True, ensure_ascii=False)
    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return fingerprint, len(entries)


def _load_index_meta(meta_path: str) -> Optional[dict]:
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as meta_file:
            return json.load(meta_file)
    except Exception as e:
        logger.warning(f"Impossible de charger les métadonnées d'index: {e}")
        return None


def _write_index_meta(meta_path: str, meta: dict) -> None:
    try:
        with open(meta_path, "w", encoding="utf-8") as meta_file:
            json.dump(meta, meta_file, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Impossible d'écrire les métadonnées d'index: {e}")


def _get_embedding_signature(embeddings) -> str:
    for attr in ("model_name", "model", "model_id", "name", "deployment"):
        value = getattr(embeddings, attr, None)
        if isinstance(value, str) and value:
            return value
    return embeddings.__class__.__name__


@traceable
def load_and_index_documents(pdf_directory: str, provider: LLMProvider) -> FAISS:
    """
    Charge les documents (PDF, TXT, DOCX, MD) et crée un index vectoriel

    Args:
        pdf_directory: Chemin vers le dossier contenant les documents
        provider: Provider LLM pour les embeddings

    Returns:
        Index FAISS pour la recherche sémantique
    """
    logger.info("Début du chargement des documents")
    print(" Chargement des documents...")

    config = get_config()

    # Normaliser le chemin
    pdf_directory = os.path.abspath(pdf_directory)
    if not os.path.exists(pdf_directory):
        error_msg = f"Le dossier '{pdf_directory}' n'existe pas."
        logger.error(error_msg)
        raise ValueError(f" {error_msg}")

    logger.info(f"Chargement depuis le dossier: {pdf_directory}")
    print(f"  Dossier: {pdf_directory}")

    source_files = _collect_source_files(pdf_directory)
    if not source_files:
        error_msg = (
            f"Aucun document trouvé dans {pdf_directory}\n"
            f"Vérifiez que le dossier contient des fichiers PDF (.pdf) ou TXT (.txt)"
        )
        logger.error(error_msg)
        raise ValueError(f" {error_msg}")

    fingerprint, file_count = _compute_files_fingerprint(source_files, pdf_directory)

    embeddings = initialize_embeddings(provider)
    embedding_signature = _get_embedding_signature(embeddings)

    persist_dir = config.vectorstore.persist_directory
    if persist_dir:
        persist_dir = os.path.abspath(persist_dir)

    if persist_dir:
        index_path = os.path.join(persist_dir, "index.faiss")
        meta_path = os.path.join(persist_dir, "index.meta.json")
        existing_meta = _load_index_meta(meta_path)
        if os.path.exists(index_path) and existing_meta:
            if (
                existing_meta.get("fingerprint") == fingerprint
                and existing_meta.get("provider") == provider.value
                and existing_meta.get("embedding") == embedding_signature
            ):
                try:
                    logger.info(f"Chargement de l'index vectoriel existant: {persist_dir}")
                    print("  ♻️ Index vectoriel existant trouvé, chargement...")
                    try:
                        vectorstore = FAISS.load_local(
                            persist_dir,
                            embeddings,
                            allow_dangerous_deserialization=True
                        )
                    except TypeError:
                        vectorstore = FAISS.load_local(persist_dir, embeddings)
                    return vectorstore
                except Exception as e:
                    logger.warning(f"Impossible de charger l'index existant: {e}. Recréation en cours.")
            else:
                logger.info("Index vectoriel existant invalide ou obsolète, reconstruction en cours.")
        elif os.path.exists(index_path) and not existing_meta:
            logger.info("Index vectoriel sans métadonnées détecté, reconstruction en cours.")

    all_documents = []

    # 1. Charger les PDFs
    try:
        pdf_files = list(Path(pdf_directory).glob("**/*.pdf"))
        print(f"   {len(pdf_files)} fichier(s) PDF trouvé(s)")

        if pdf_files:
            pdf_loader = DirectoryLoader(
                pdf_directory,
                glob="**/*.pdf",
                loader_cls=PyPDFLoader,
                show_progress=False,
                silent_errors=False
            )
            pdf_docs = pdf_loader.load()
            all_documents.extend(pdf_docs)
            print(f"  ✓ {len(pdf_docs)} PDF(s) chargé(s) avec succès")
        else:
            print(f"    Aucun fichier PDF trouvé dans {pdf_directory}")
    except Exception as e:
        error_msg = f"Erreur lors du chargement des PDFs: {e}"
        logger.error(error_msg, exc_info=True)
        print(f"    Erreur chargement PDF: {e}")
        import traceback
        traceback.print_exc()

    # 2. Charger les fichiers TXT
    try:
        txt_files = list(Path(pdf_directory).glob("**/*.txt"))
        print(f"  🔍 {len(txt_files)} fichier(s) TXT trouvé(s)")

        if txt_files:
            txt_loader = DirectoryLoader(
                pdf_directory,
                glob="**/*.txt",
                loader_cls=TextLoader,
                loader_kwargs={"encoding": "utf-8"},
                show_progress=False,
                silent_errors=False
            )
            txt_docs = txt_loader.load()
            all_documents.extend(txt_docs)
            print(f"  ✓ {len(txt_docs)} fichier(s) TXT chargé(s) avec succès")
        else:
            print(f"    Aucun fichier TXT trouvé dans {pdf_directory}")
    except Exception as e:
        error_msg = f"Erreur lors du chargement des fichiers TXT: {e}"
        logger.error(error_msg, exc_info=True)
        print(f"    Erreur chargement TXT: {e}")
        import traceback
        traceback.print_exc()

    # 3. Charger les fichiers Markdown avec TextLoader (pas de dépendance externe)
    try:
        md_files = list(Path(pdf_directory).glob("**/*.md"))
        if md_files:
            md_loader = DirectoryLoader(
                pdf_directory,
                glob="**/*.md",
                loader_cls=TextLoader,
                loader_kwargs={"encoding": "utf-8"},
                show_progress=False,
                silent_errors=False
            )
            md_docs = md_loader.load()
            all_documents.extend(md_docs)
            print(f"  ✓ {len(md_docs)} fichier(s) Markdown chargé(s)")
    except Exception as e:
        logger.error(f"Erreur lors du chargement des fichiers Markdown: {e}", exc_info=True)
        print(f"    Erreur chargement Markdown: {e}")

    # 4. Charger les fichiers DOCX (optionnel)
    try:
        from langchain_community.document_loaders import Docx2txtLoader
        docx_loader = DirectoryLoader(
            pdf_directory,
            glob="**/*.docx",
            loader_cls=Docx2txtLoader,
            show_progress=False
        )
        docx_docs = docx_loader.load()
        all_documents.extend(docx_docs)
        print(f"  ✓ {len(docx_docs)} fichier(s) DOCX chargé(s)")
    except Exception as e:
        if "No module named" not in str(e):
            print(f"    Erreur chargement DOCX: {e}")

    if len(all_documents) == 0:
        error_msg = (
            "Aucun document n'a pu être chargé malgré la présence de fichiers.\n"
            "Vérifiez que les formats sont valides et lisibles."
        )
        logger.error(error_msg)
        raise ValueError(f" {error_msg}")

    print(f"  Total: {len(all_documents)} document(s) chargé(s)")

    # Découper les documents en chunks
    print("  🔪 Découpage des documents en chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.vectorstore.chunk_size,
        chunk_overlap=config.vectorstore.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    splits = text_splitter.split_documents(all_documents)

    # Ajouter les structures UAM statiques (non soumises au chunking — déjà denses)
    structure_docs = _generate_structure_documents()
    if structure_docs:
        splits.extend(structure_docs)
        print(f"  ✓ {len(structure_docs)} structure(s) UAM injectée(s) dans l'index")

    print(f" {len(all_documents)} document(s) total chargé(s) et divisé(s) en {len(splits)} chunks")

    # Créer l'index vectoriel avec les embeddings appropriés
    logger.info(f"Création de l'index vectoriel avec {len(splits)} chunks...")
    try:
        vectorstore = FAISS.from_documents(splits, embeddings)
        if persist_dir:
            try:
                vectorstore.save_local(persist_dir)
                meta = {
                    "fingerprint": fingerprint,
                    "file_count": file_count,
                    "provider": provider.value,
                    "embedding": embedding_signature,
                    "updated_at": datetime.now().isoformat()
                }
                _write_index_meta(os.path.join(persist_dir, "index.meta.json"), meta)
                logger.info(f"Index vectoriel persisté dans {persist_dir}")
            except Exception as e:
                logger.warning(f"Impossible de persister l'index vectoriel: {e}")
        logger.info("Index vectoriel créé avec succès")
        return vectorstore
    except Exception as e:
        error_msg = f"Erreur lors de la création de l'index vectoriel: {e}"
        logger.error(error_msg, exc_info=True)
        raise RuntimeError(error_msg) from e
