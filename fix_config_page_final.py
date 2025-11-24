"""
Fix ConfigPage.tsx by completely rewriting the model mapping section.
This removes duplicates and ensures clean structure.
"""

# Read the file
with open(r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the start and end markers for the section we want to replace
start_marker = '{(config.available_models_labeled || []).map((m, idx) => ('
end_marker = '))} ' # Note: there might be a space or newline after

# We'll find the start, then find the matching closing parenthesis for the map
start_idx = content.find(start_marker)

if start_idx == -1:
    print("❌ ERROR: Could not find start marker")
    exit(1)

# Find the end of the map function
# It ends with ))} before the <div className="flex items-center gap-3 pt-2">
next_section_marker = '<div className="flex items-center gap-3 pt-2">'
end_idx = content.find(next_section_marker, start_idx)

if end_idx == -1:
    print("❌ ERROR: Could not find end marker")
    exit(1)

# Backtrack from end_idx to find the closing ))}
# The content we want to replace is everything from start_marker up to (but not including) next_section_marker
# But we need to keep the closing ))} for the map if it's not part of the replacement string

# Let's construct the clean replacement string
replacement = '''{(config.available_models_labeled || []).map((m, idx) => (
                      <div key={idx} className="space-y-2">
                        <div className="flex items-center gap-3">
                          <input type="text" value={m.label} onChange={(e) => updateModel(idx, 'label', e.target.value)} className={`w-32 ${inputBaseStyle}`} placeholder="Label" />
                          <input type="text" value={m.id} onChange={(e) => updateModel(idx, 'id', e.target.value)} className={`flex-1 ${inputBaseStyle}`} placeholder="Model ID" />
                          <select
                            value={m.provider || 'openai'}
                            onChange={(e) => updateModel(idx, 'provider', e.target.value)}
                            className={`w-24 ${inputBaseStyle}`}
                          >
                            <option value="openai">OpenAI</option>
                            <option value="google">Google</option>
                            <option value="openrouter">OpenRouter</option>
                            <option value="ollama">Ollama</option>
                          </select>
                          <button onClick={() => removeModel(idx)} className={buttonRemoveIconStyle} title="Remove Model">
                            <TrashIcon className="w-5 h-5" />
                          </button>
                        </div>
                        {/* Multimodal Capabilities */}
                        <div className="flex items-center gap-4 pl-4 text-xs">
                          <label className="flex items-center gap-2 text-slate-400 cursor-pointer hover:text-slate-300">
                            <input
                              type="checkbox"
                              checked={m.supports_images || false}
                              onChange={(e) => {
                                if (!config) return;
                                const newList = (config.available_models_labeled || []).map((model, i) => 
                                  i === idx ? { ...model, supports_images: e.target.checked } : model
                                );
                                updateModelsList(newList);
                              }}
                              className="w-4 h-4 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700"
                            />
                            <span>📷 Images</span>
                          </label>
                          <label className="flex items-center gap-2 text-slate-400 cursor-pointer hover:text-slate-300">
                            <input
                              type="checkbox"
                              checked={m.supports_audio || false}
                              onChange={(e) => {
                                if (!config) return;
                                const newList = (config.available_models_labeled || []).map((model, i) => 
                                  i === idx ? { ...model, supports_audio: e.target.checked } : model
                                );
                                updateModelsList(newList);
                              }}
                              className="w-4 h-4 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700"
                            />
                            <span>🎵 Audio</span>
                          </label>
                          <label className="flex items-center gap-2 text-slate-400 cursor-pointer hover:text-slate-300">
                            <input
                              type="checkbox"
                              checked={m.supports_videos || false}
                              onChange={(e) => {
                                if (!config) return;
                                const newList = (config.available_models_labeled || []).map((model, i) => 
                                  i === idx ? { ...model, supports_videos: e.target.checked } : model
                                );
                                updateModelsList(newList);
                              }}
                              className="w-4 h-4 rounded border-slate-600 text-sky-600 focus:ring-sky-500 bg-slate-700"
                            />
                            <span>🎬 Videos</span>
                          </label>
                        </div>
                      </div>
                    ))}
                    '''

# Now we need to identify exactly what to replace.
# We will replace everything from start_idx to the last occurrence of ))} before next_section_marker
# Find the last ))} before end_idx
section_to_replace = content[start_idx:end_idx]
last_paren_idx = section_to_replace.rfind('))}')

if last_paren_idx == -1:
    print("❌ ERROR: Could not find closing parenthesis in section")
    exit(1)

# Calculate the actual end index in the full content
replace_end_idx = start_idx + last_paren_idx + 3 # +3 for ))} length

# Perform replacement
new_content = content[:start_idx] + replacement + content[replace_end_idx:]

# Write back
with open(r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('✅ ConfigPage.tsx fixed! Replaced entire model mapping section with clean version.')
