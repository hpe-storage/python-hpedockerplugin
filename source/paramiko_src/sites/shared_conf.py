from datetime import datetime

import alabaster


# Alabaster theme + mini-extension
html_theme_path = [alabaster.get_path()]
extensions = ['alabaster', 'sphinx.ext.intersphinx']
# Paths relative to invoking conf.py - not this shared file
html_theme = 'alabaster'
html_theme_options = {
    'description': "A Python implementation of SSHv2.",
    'github_user': 'paramiko',
    'github_repo': 'paramiko',
    'analytics_id': 'UA-18486793-2',
    'travis_button': True,
}
html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'searchbox.html',
        'donate.html',
    ]
}

# Everything intersphinx's to Python
intersphinx_mapping = {
    'python': ('http://docs.python.org/2.6', None),
}

# Regular settings
project = 'Paramiko'
year = datetime.now().year
copyright = '%d Jeff Forcier' % year
master_doc = 'index'
templates_path = ['_templates']
exclude_trees = ['_build']
source_suffix = '.rst'
default_role = 'obj'
