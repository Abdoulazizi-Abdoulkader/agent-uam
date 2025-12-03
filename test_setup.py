"""
Script de test pour vérifier l'installation de l'Agent UAM
Exécutez ce script avant de lancer l'agent principal
"""

import sys
import os
from pathlib import Path

def print_status(check_name, passed, message=""):
    """Affiche le statut d'un test"""
    status = "✅" if passed else "❌"
    print(f"{status} {check_name}")
    if message:
        print(f"   → {message}")
    return passed

def check_python_version():
    """Vérifie la version de Python"""
    version = sys.version_info
    is_valid = version.major == 3 and version.minor >= 8
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    return print_status(
        "Version Python",
        is_valid,
        f"Python {version_str} {'✓' if is_valid else '✗ Nécessite Python 3.8+'}"
    )

def check_package(package_name, import_name=None):
    """Vérifie si un package est installé"""
    import_name = import_name or package_name
    try:
        __import__(import_name)
        return print_status(f"Package: {package_name}", True, "Installé")
    except ImportError:
        return print_status(
            f"Package: {package_name}",
            False,
            f"Manquant - Installer avec: pip install {package_name}"
        )

def check_env_file():
    """Vérifie le fichier .env"""
    if not Path(".env").exists():
        return print_status(
            "Fichier .env",
            False,
            "Manquant - Copier .env.example vers .env"
        )
    
    # Vérifier le contenu
    with open(".env", "r") as f:
        content = f.read()
        has_groq = "GROQ_API_KEY" in content and "gsk_" in content
        
        if not has_groq:
            return print_status(
                "Clé API Groq",
                False,
                "Non configurée dans .env"
            )
    
    return print_status("Configuration .env", True, "Fichier présent et configuré")

def check_documents_folder():
    """Vérifie le dossier documents"""
    docs_path = Path("documents_uam")
    
    if not docs_path.exists():
        return print_status(
            "Dossier documents_uam/",
            False,
            "Manquant - Créer avec: mkdir documents_uam"
        )
    
    # Compter les PDFs
    pdfs = list(docs_path.glob("*.pdf"))
    
    if len(pdfs) == 0:
        return print_status(
            "Documents PDF",
            False,
            "Aucun PDF trouvé dans documents_uam/"
        )
    
    return print_status(
        "Documents PDF",
        True,
        f"{len(pdfs)} fichier(s) trouvé(s)"
    )

def check_main_script():
    """Vérifie le script principal"""
    exists = Path("agent_uam.py").exists()
    return print_status(
        "Script agent_uam.py",
        exists,
        "Présent" if exists else "Manquant"
    )

def test_groq_connection():
    """Test de connexion à Groq"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return print_status(
                "Test connexion Groq",
                False,
                "GROQ_API_KEY non trouvée"
            )
        
        from langchain_groq import ChatGroq
        
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=50
        )
        
        # Test simple
        response = llm.invoke("Dis bonjour en un mot")
        
        return print_status(
            "Test connexion Groq",
            True,
            f"Connexion réussie - Réponse: {response.content[:30]}..."
        )
        
    except Exception as e:
        return print_status(
            "Test connexion Groq",
            False,
            f"Erreur: {str(e)[:50]}"
        )

def test_pdf_loading():
    """Test de chargement PDF"""
    try:
        from langchain_community.document_loaders import PyPDFLoader
        
        docs_path = Path("documents_uam")
        pdfs = list(docs_path.glob("*.pdf"))
        
        if not pdfs:
            return print_status(
                "Test chargement PDF",
                False,
                "Aucun PDF à tester"
            )
        
        # Tester le premier PDF
        loader = PyPDFLoader(str(pdfs[0]))
        docs = loader.load()
        
        return print_status(
            "Test chargement PDF",
            len(docs) > 0,
            f"{len(docs)} page(s) chargée(s) depuis {pdfs[0].name}"
        )
        
    except Exception as e:
        return print_status(
            "Test chargement PDF",
            False,
            f"Erreur: {str(e)[:50]}"
        )

def test_embeddings():
    """Test des embeddings"""
    try:
        from sentence_transformers import SentenceTransformer
        
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embedding = model.encode("Test")
        
        return print_status(
            "Test embeddings",
            len(embedding) > 0,
            f"Vecteur de dimension {len(embedding)} généré"
        )
        
    except Exception as e:
        return print_status(
            "Test embeddings",
            False,
            f"Erreur: {str(e)[:50]}"
        )

def main():
    """Exécute tous les tests"""
    print("=" * 60)
    print("🔍 VÉRIFICATION DE L'INSTALLATION - AGENT UAM")
    print("=" * 60)
    print()
    
    results = []
    
    # Tests de base
    print("📋 Tests de base:")
    print("-" * 60)
    results.append(check_python_version())
    results.append(check_env_file())
    results.append(check_documents_folder())
    results.append(check_main_script())
    print()
    
    # Tests des packages
    print("📦 Packages Python:")
    print("-" * 60)
    packages = [
        ("langchain", "langchain"),
        ("langchain-community", "langchain_community"),
        ("langchain-groq", "langchain_groq"),
        ("langgraph", "langgraph"),
        ("sentence-transformers", "sentence_transformers"),
        ("pypdf", "pypdf"),
        ("faiss-cpu", "faiss"),
        ("python-dotenv", "dotenv"),
    ]
    
    for package, import_name in packages:
        results.append(check_package(package, import_name))
    print()
    
    # Tests fonctionnels
    print("🧪 Tests fonctionnels:")
    print("-" * 60)
    results.append(test_groq_connection())
    results.append(test_pdf_loading())
    results.append(test_embeddings())
    print()
    
    # Résumé
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    percentage = (passed / total) * 100
    
    if percentage == 100:
        print(f"✅ TOUS LES TESTS RÉUSSIS ({passed}/{total})")
        print()
        print("🚀 Vous pouvez lancer l'agent avec:")
        print("   python agent_uam.py")
    elif percentage >= 80:
        print(f"⚠️  LA PLUPART DES TESTS RÉUSSIS ({passed}/{total})")
        print()
        print("L'agent devrait fonctionner, mais vérifiez les tests échoués.")
    else:
        print(f"❌ PLUSIEURS TESTS ONT ÉCHOUÉ ({passed}/{total})")
        print()
        print("Veuillez corriger les erreurs avant de lancer l'agent.")
    
    print("=" * 60)
    
    return percentage == 100

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)