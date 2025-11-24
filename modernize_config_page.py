"""
Modernize ConfigPage.tsx with a card-based UI and improved styling.
Replaces the plain list with styled cards, better inputs, and toggle badges.
"""

# Read the file
with open(r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# We will replace the entire "Available Models" section content
# From <span ...>Available Models</span> down to the end of the Add Model block

start_marker = '<span className="block text-sm font-medium text-slate-400 mb-2">Available Models</span>'
end_marker = '<span className="block text-sm font-medium text-slate-400 mb-2">Available Voices</span>'

# Find start
start_idx = content.find(start_marker)
if start_idx == -1:
    print("❌ ERROR: Could not find start marker")
    exit(1)

# Find end (start of next section)
end_idx = content.find(end_marker)
if end_idx == -1:
    print("❌ ERROR: Could not find end marker")
    exit(1)

# We need to find the closing </div> of the previous section before end_marker
# The structure is:
# <div>
#   <span>Available Models</span>
#   <div space-y-2>
#      ... content ...
#   </div>
# </div>
# <div> ... next section

# So we want to replace everything inside the outer div of this section, OR replace the whole section.
# Let's look at the context. The start_marker is inside a div.
# Let's replace from start_marker to the closing </div> of that container.
# Actually, it's safer to replace the inner content.

# Let's construct the new modern HTML/JSX
new_section = '''<span className="block text-sm font-medium text-slate-400 mb-3">Available Models</span>
                  <div className="grid grid-cols-1 gap-4">
                    {(config.available_models_labeled || []).map((m, idx) => (
                      <div key={idx} className="group relative bg-slate-800/40 border border-slate-700/50 rounded-xl p-4 transition-all hover:border-sky-500/30 hover:shadow-lg hover:shadow-sky-500/5">
                        
                        {/* Header: Label & Provider */}
                        <div className="flex items-start justify-between gap-4 mb-2">
                          <div className="flex-1">
                            <input 
                              type="text" 
                              value={m.label} 
                              onChange={(e) => updateModel(idx, 'label', e.target.value)} 
                              className="w-full bg-transparent border-none p-0 text-lg font-semibold text-slate-200 placeholder-slate-600 focus:ring-0" 
                              placeholder="Model Name" 
                            />
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-slate-600 text-xs font-mono">ID:</span>
                              <input 
                                type="text" 
                                value={m.id} 
                                onChange={(e) => updateModel(idx, 'id', e.target.value)} 
                                className="flex-1 bg-transparent border-none p-0 text-xs font-mono text-slate-500 focus:text-sky-400 focus:ring-0 transition-colors" 
                                placeholder="model-id" 
                              />
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-2">
                            <select
                              value={m.provider || 'openai'}
                              onChange={(e) => updateModel(idx, 'provider', e.target.value)}
                              className="bg-slate-900/50 border border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-400 focus:border-sky-500 focus:ring-1 focus:ring-sky-500 outline-none cursor-pointer hover:bg-slate-900"
                            >
                              <option value="openai">OpenAI</option>
                              <option value="google">Google</option>
                              <option value="openrouter">OpenRouter</option>
                              <option value="ollama">Ollama</option>
                            </select>
                            <button 
                              onClick={() => removeModel(idx)} 
                              className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-400/10 transition-colors opacity-0 group-hover:opacity-100" 
                              title="Remove Model"
                            >
                              <TrashIcon className="w-4 h-4" />
                            </button>
                          </div>
                        </div>

                        {/* Capabilities Badges */}
                        <div className="flex flex-wrap items-center gap-2 mt-4 pt-3 border-t border-slate-700/30">
                          <span className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mr-1">Capabilities:</span>
                          
                          <label className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all cursor-pointer select-none ${m.supports_images ? 'bg-sky-500/10 border-sky-500/30 text-sky-400' : 'bg-slate-800/50 border-slate-700 text-slate-500 hover:border-slate-600'}`}>
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
                              className="hidden" 
                            />
                            <ImageIcon className="w-3.5 h-3.5" />
                            <span>Images</span>
                          </label>

                          <label className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all cursor-pointer select-none ${m.supports_audio ? 'bg-purple-500/10 border-purple-500/30 text-purple-400' : 'bg-slate-800/50 border-slate-700 text-slate-500 hover:border-slate-600'}`}>
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
                              className="hidden" 
                            />
                            <span className="text-sm">🎵</span>
                            <span>Audio</span>
                          </label>

                          <label className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all cursor-pointer select-none ${m.supports_videos ? 'bg-pink-500/10 border-pink-500/30 text-pink-400' : 'bg-slate-800/50 border-slate-700 text-slate-500 hover:border-slate-600'}`}>
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
                              className="hidden" 
                            />
                            <VideoIcon className="w-3.5 h-3.5" />
                            <span>Videos</span>
                          </label>
                        </div>
                      </div>
                    ))}

                    {/* Add New Model Card */}
                    <div className="relative group border-2 border-dashed border-slate-700/50 rounded-xl p-4 hover:border-sky-500/40 hover:bg-slate-800/30 transition-all">
                      <div className="flex items-center gap-3">
                        <div className="flex-1 space-y-2">
                          <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                              <span className="text-slate-500 text-xs">🏷️</span>
                            </div>
                            <input 
                              type="text" 
                              value={newModel.label} 
                              onChange={(e) => setNewModel(prev => ({ ...prev, label: e.target.value }))} 
                              placeholder="New Model Name" 
                              className="w-full bg-slate-900/50 border border-slate-700 rounded-lg py-2 pl-9 pr-3 text-sm text-slate-200 placeholder-slate-500 focus:ring-1 focus:ring-sky-500 focus:border-sky-500 transition-all" 
                            />
                          </div>
                          <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                              <span className="text-slate-500 text-xs">🆔</span>
                            </div>
                            <input 
                              type="text" 
                              value={newModel.id} 
                              onChange={(e) => setNewModel(prev => ({ ...prev, id: e.target.value }))} 
                              placeholder="Model ID (e.g. gpt-4o)" 
                              className="w-full bg-slate-900/50 border border-slate-700 rounded-lg py-2 pl-9 pr-3 text-sm text-slate-200 placeholder-slate-500 focus:ring-1 focus:ring-sky-500 focus:border-sky-500 transition-all" 
                            />
                          </div>
                        </div>
                        
                        <div className="flex flex-col gap-2">
                          <select
                            value={newModel.provider}
                            onChange={(e) => setNewModel(prev => ({ ...prev, provider: e.target.value }))}
                            className="bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-400 focus:border-sky-500 focus:ring-1 focus:ring-sky-500 outline-none"
                          >
                            <option value="openai">OpenAI</option>
                            <option value="google">Google</option>
                            <option value="openrouter">OpenRouter</option>
                            <option value="ollama">Ollama</option>
                          </select>
                          <button 
                            onClick={addModel} 
                            className="flex items-center justify-center gap-2 bg-sky-600 hover:bg-sky-500 text-white rounded-lg py-2 px-4 text-sm font-medium transition-colors shadow-lg shadow-sky-900/20"
                          >
                            <PlusIcon className="w-4 h-4" />
                            <span>Add</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>'''

# We need to be careful about where we slice.
# We want to replace from start_marker to the closing </div> of the container.
# The container starts with <div> (lines 291 in original view)
# We can just replace the content between start_marker and the line before end_marker that closes the div.

# Let's find the last </div> before end_marker
search_area = content[start_idx:end_idx]
last_div_idx = search_area.rfind('</div>')
second_last_div_idx = search_area.rfind('</div>', 0, last_div_idx)

# The structure is:
# <div> (outer)
#   <span>Available Models</span>
#   <div space-y-2> (inner)
#      ...
#   </div> (inner close)
# </div> (outer close)

# So we want to replace from start_marker up to the second_last_div_idx + 6 (length of </div>)
# Actually, let's just replace the whole block including the outer div closing, and reconstruct it.
# The previous view showed:
# 380:                 </div>
# 381:                 <div>
# 382:                   <span ...>Available Voices</span>

# So end_idx points to line 382.
# The lines before are 380 (</div>) and 381 (<div>).
# We want to replace up to line 380's closing div.

# Let's try to match the exact string of the previous section end to be safe.
# It ends with:
#                     </div>
#                   </div>
#                 </div>

# Let's just find the start of the next section and backtrack to the previous </div>
# end_idx is at <span ... Available Voices
# The character before that is likely a newline or >
# Let's look at the content just before end_idx
pre_end = content[:end_idx].rstrip()
# It should end with </div>. Let's find the last </div>
last_div = pre_end.rfind('</div>')
# And the one before that (closing the inner list)
prev_div = pre_end.rfind('</div>', 0, last_div)
# And the one before that (closing the model item)
# This is getting risky with string searching.

# Safer approach:
# We know the start marker.
# We know the end marker.
# We want to replace everything between them with our new content + the closing div of the previous section.
# Wait, my new_section includes the start_marker.
# And it ends with </div> (closing the grid).
# The original code had an outer <div> wrapping the whole thing.
# My new code has <div className="grid..."> which replaces <div className="space-y-2">.
# But I need to close the outer div too?
# Let's check the original structure again.
# 291: <div className="space-y-2">
# ...
# 379: </div> (closes space-y-2)
# 380: </div> (closes outer container?)
# 381: <div> (starts voices container)

# So between start_marker and end_marker, there are TWO closing divs.
# My new_section ends with the closing div of the grid.
# So I need to add one more </div> to close the outer container.
# AND I need to make sure I consume the old closing divs.

# Let's replace everything from start_marker up to end_marker with:
# new_section + "\n</div>\n<div>\n"
# Because end_marker starts with <span...>, it is inside the NEXT div.
# So I need to reconstruct the boundary.

final_replacement = new_section + '\\n                </div>\\n                <div>\\n                  '

# Perform replacement
new_content = content[:start_idx] + final_replacement + content[end_idx:]

# Write back
with open(r'c:\Users\PC\Desktop\prod\prodv1\Artificial_Intelligence_Frontend\components\ConfigPage.tsx', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('✅ ConfigPage.tsx modernized! Replaced model list with card-based UI.')
