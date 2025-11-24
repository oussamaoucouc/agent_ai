"""
Fix literal \\n characters in ConfigPage.tsx
"""

path = r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace literal \n with actual newline
new_content = content.replace('\\n', '\n')

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('✅ Fixed literal newlines in ConfigPage.tsx')
