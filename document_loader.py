"""
Chargement et indexation des documents pour la base de connaissances
"""
import os
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langsmith import traceable
from config import LLMProvider
from llm_utils import initialize_embeddings


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
    print(" Chargement des documents...")

    # Normaliser le chemin
    pdf_directory = os.path.abspath(pdf_directory)
    if not os.path.exists(pdf_directory):
        raise ValueError(f" Le dossier '{pdf_directory}' n'existe pas.")

    print(f"  Dossier: {pdf_directory}")

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
        print(f"    Erreur chargement TXT: {e}")
        import traceback
        traceback.print_exc()

    # 3. Charger les fichiers Markdown (optionnel)
    try:
        from langchain_community.document_loaders import UnstructuredMarkdownLoader
        md_loader = DirectoryLoader(
            pdf_directory,
            glob="**/*.md",
            loader_cls=UnstructuredMarkdownLoader,
            show_progress=False
        )
        md_docs = md_loader.load()
        all_documents.extend(md_docs)
        print(f"  ✓ {len(md_docs)} fichier(s) Markdown chargé(s)")
    except Exception as e:
        if "No module named" not in str(e):
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
        raise ValueError(
            f" Aucun document trouvé dans {pdf_directory}\n"
            f" Vérifiez que le dossier contient des fichiers PDF (.pdf) ou TXT (.txt)"
        )

    print(f"  Total: {len(all_documents)} document(s) chargé(s)")

    # Découper les documents en chunks
    print("  🔪 Découpage des documents en chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    splits = text_splitter.split_documents(all_documents)

    print(f" {len(all_documents)} document(s) total chargé(s) et divisé(s) en {len(splits)} chunks")

    # Créer l'index vectoriel avec les embeddings appropriés
    embeddings = initialize_embeddings(provider)
    vectorstore = FAISS.from_documents(splits, embeddings)

    return vectorstore

