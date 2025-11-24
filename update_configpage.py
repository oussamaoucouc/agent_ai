"""Add multimodal checkboxes to ConfigPage models"""
# Read current file
with open(r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and modify the model rows section
output = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Check if we're at the model row div
    if 'key={idx} className="flex items-center gap-3"' in line and i > 290:
        # Change to space-y-2 wrapper
        output.append(line.replace('className="flex items-center gap-3"', 'className="space-y-2"'))
        i += 1
        # Add new flex div for inputs
        indent = '                        '
        output.append(indent + '<div className="flex items-center gap-3">\n')
        
        # Copy all lines until closing </div> of the row
        while i < len(lines) and '</div>' not in lines[i]:
            # Adjust widths
            adjusted = lines[i].replace('w-40', 'w-32')
            output.append(adjusted)
            i += 1
        
        output.append(lines[i])  # Add </div> for row
        i += 1
        
        # Now add checkboxes div
        output.append(indent + '<div className="flex items-center gap-4 pl-4 text-xs">\n')
        
        # Images checkbox  
        cb_indent = indent + '  '
        output.append(cb_indent + '<label className="flex items-center gap-2 text-slate-400 cursor-pointer">\n')
        output.append(cb_indent + '  <input type="checkbox" checked={m.supports_images || false}\n')
        output.append(cb_indent + '    onChange={(e) => { if (!config) return; const newList = (config.available_models_labeled || []).map((model, i) => i === idx ? { ...model, supports_images: e.target.checked } : model); updateModelsList(newList); }}\n')
        output.append(cb_indent + '    className="w-4 h-4 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700" />\n')
        output.append(cb_indent + '  <span>📷 Images</span>\n')
        output.append(cb_indent + '</label>\n')
        
        # Audio checkbox
        output.append(cb_indent + '<label className="flex items-center gap-2 text-slate-400 cursor-pointer">\n')
        output.append(cb_indent + '  <input type="checkbox" checked={m.supports_audio || false}\n')
        output.append(cb_indent + '    onChange={(e) => { if (!config) return; const newList = (config.available_models_labeled || []).map((model, i) => i === idx ? { ...model, supports_audio: e.target.checked } : model); updateModelsList(newList); }}\n')
        output.append(cb_indent + '    className="w-4 h-4 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700" />\n')
        output.append(cb_indent + '  <span>🎵 Audio</span>\n')
        output.append(cb_indent + '</label>\n')
        
        # Videos checkbox
        output.append(cb_indent + '<label className="flex items-center gap-2 text-slate-400 cursor-pointer">\n')
        output.append(cb_indent + '  <input type="checkbox" checked={m.supports_videos || false}\n')
        output.append(cb_indent + '    onChange={(e) => { if (!config) return; const newList = (config.available_models_labeled || []).map((model, i) => i === idx ? { ...model, supports_videos: e.target.checked } : model); updateModelsList(newList); }}\n')
        output.append(cb_indent + '    className="w-4 h-4 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700" />\n')
        output.append(cb_indent + '  <span>🎬 Videos</span>\n')
        output.append(cb_indent + '</label>\n')
        
        output.append(indent + '</div>\n')  # Close checkboxes div
        output.append(indent + '</div>\n')  # Close space-y-2 wrapper
        # Skip the next closing div that was for the old structure
        if i < len(lines) and '</div>' in lines[i]:
            i += 1
    else:
        output.append(line)
        i += 1

# Write back
with open(r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx', 'w', encoding='utf-8') as f:
    f.writelines(output)

print('✅ ConfigPage.tsx updated with multimodal capability checkboxes!')
