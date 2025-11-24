"""
Add multimodal checkboxes to ConfigPage - v2 with correct pattern
"""

# Read the file
with open(r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find line with TrashIcon and insert checkboxes after its parent div closes
output = []
i = 0
inserted = False

while i < len(lines):
    line = lines[i]
    output.append(line)
    
    # Look for the line with TrashIcon (around line 307)
    if '<TrashIcon className="w-5 h-5" />' in line and not inserted:
        # Add this line
        i += 1
        output.append(lines[i])  # </button>
        i += 1  
        output.append(lines[i])  # </div> closing the flex row
        
        # Now insert the checkboxes div
        indent = '                      '
        output.append(indent + '{/* Multimodal Capabilities */}\n')
        output.append(indent + '<div className="flex items-center gap-4 mt-2 ml-4 text-xs">\n')
        
        # Images
        output.append(indent + '  <label className="flex items-center gap-2 text-slate-400 cursor-pointer hover:text-slate-300">\n')
        output.append(indent + '    <input type="checkbox" checked={m.supports_images || false}\n')
        output.append(indent + '      onChange={(e) => { if (!config) return; const newList = (config.available_models_labeled || []).map((model, i) => i === idx ? { ...model, supports_images: e.target.checked } : model); updateModelsList(newList); }}\n')
        output.append(indent + '      className="w-4 h-4 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700" />\n')
        output.append(indent + '    <span>📷 Images</span>\n')
        output.append(indent + '  </label>\n')
        
        # Audio
        output.append(indent + '  <label className="flex items-center gap-2 text-slate-400 cursor-pointer hover:text-slate-300">\n')
        output.append(indent + '    <input type="checkbox" checked={m.supports_audio || false}\n')
        output.append(indent + '      onChange={(e) => { if (!config) return; const newList = (config.available_models_labeled || []).map((model, i) => i === idx ? { ...model, supports_audio: e.target.checked } : model); updateModelsList(newList); }}\n')
        output.append(indent + '      className="w-4 h-4 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700" />\n')
        output.append(indent + '    <span>🎵 Audio</span>\n')
        output.append(indent + '  </label>\n')
        
        # Videos
        output.append(indent + '  <label className="flex items-center gap-2 text-slate-400 cursor-pointer hover:text-slate-300">\n')
        output.append(indent + '    <input type="checkbox" checked={m.supports_videos || false}\n')
        output.append(indent + '      onChange={(e) => { if (!config) return; const newList = (config.available_models_labeled || []).map((model, i) => i === idx ? { ...model, supports_videos: e.target.checked } : model); updateModelsList(newList); }}\n')
        output.append(indent + '      className="w-4 h-4 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700" />\n')
        output.append(indent + '    <span>🎬 Videos</span>\n')
        output.append(indent + '  </label>\n')
        
        output.append(indent + '</div>\n')
        
        inserted = True
        i += 1
    else:
        i += 1

# Write back
with open(r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx', 'w', encoding='utf-8') as f:
    f.writelines(output)

if inserted:
    print('✅ ConfigPage.tsx updated successfully!')
    print('   Added multimodal capability checkboxes below model rows')
else:
    print('❌ ERROR: Could not find TrashIcon line to insert checkboxes')
