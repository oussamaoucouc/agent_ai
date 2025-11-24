"""
Fix missing imports in ConfigPage.tsx
Adds ImageIcon and VideoIcon to the import statement.
"""

path = r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the import line
old_import = "import { PlusIcon, TrashIcon } from './icons';"
new_import = "import { PlusIcon, TrashIcon, ImageIcon, VideoIcon } from './icons';"

if old_import in content:
    new_content = content.replace(old_import, new_import)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('✅ Added missing icon imports to ConfigPage.tsx')
else:
    print('❌ ERROR: Could not find import line to replace')
