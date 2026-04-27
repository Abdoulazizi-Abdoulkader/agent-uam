# Configuration file for the Sphinx documentation builder.

import os
import sys

# Mettre le répertoire parent dans le path pour que Sphinx trouve les modules
sys.path.insert(0, os.path.abspath('../../'))

project = 'Agent UAM'
copyright = '2026, Équipe Agent UAM'
author = 'Équipe Agent UAM'
release = '1.0.0'

# Extensions utiles
extensions = [
    'sphinx.ext.autodoc',       # Génère la doc à partir des docstrings
    'sphinx.ext.napoleon',      # Support des docstrings Google/NumPy
    'sphinx.ext.viewcode',      # Ajoute des liens vers le code source
    'sphinx_rtd_theme',         # Thème Read The Docs
]

templates_path = ['_templates']
exclude_patterns = []

# Thème HTML
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Configuration de autodoc
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'private-members': False,
    'show-inheritance': True,
}
